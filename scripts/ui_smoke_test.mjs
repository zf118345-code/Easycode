import { spawn } from 'node:child_process'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..')
const edge = process.env.EASYCODE_EDGE_PATH
    || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const url = process.argv[2] || 'http://localhost:5173/index.html'
const projectName = process.argv[3] || 'testisok'
const artifactDir = path.join(root, '.artifacts', 'ui-smoke')
const profileDir = path.join(artifactDir, 'edge-profile')
const port = Number(process.env.EASYCODE_CDP_PORT || 9337)

await rm(artifactDir, { recursive: true, force: true })
await mkdir(profileDir, { recursive: true })

const browser = spawn(edge, [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--window-size=1600,1000',
    'about:blank'
], { stdio: 'ignore', windowsHide: true })

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

async function waitForJson(endpoint, timeoutMs = 12000) {
    const deadline = Date.now() + timeoutMs
    let lastError
    while (Date.now() < deadline) {
        try {
            const response = await fetch(endpoint)
            if (response.ok) return response.json()
        } catch (error) {
            lastError = error
        }
        await delay(100)
    }
    throw new Error(`等待 CDP 端点超时: ${lastError?.message || endpoint}`)
}

class CdpClient {
    constructor(webSocketUrl) {
        this.nextId = 1
        this.pending = new Map()
        this.events = []
        this.socket = new WebSocket(webSocketUrl)
    }

    async connect() {
        await new Promise((resolve, reject) => {
            this.socket.addEventListener('open', resolve, { once: true })
            this.socket.addEventListener('error', reject, { once: true })
        })
        this.socket.addEventListener('message', event => {
            const payload = JSON.parse(event.data)
            if (payload.id) {
                const waiter = this.pending.get(payload.id)
                if (!waiter) return
                this.pending.delete(payload.id)
                if (payload.error) waiter.reject(new Error(payload.error.message))
                else waiter.resolve(payload.result)
                return
            }
            this.events.push(payload)
        })
    }

    send(method, params = {}) {
        const id = this.nextId++
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject })
            this.socket.send(JSON.stringify({ id, method, params }))
        })
    }

    async evaluate(expression, { awaitPromise = true, returnByValue = true } = {}) {
        const result = await this.send('Runtime.evaluate', {
            expression,
            awaitPromise,
            returnByValue,
            userGesture: true
        })
        if (result.exceptionDetails) {
            throw new Error(result.exceptionDetails.exception?.description || '页面脚本执行失败')
        }
        return result.result?.value
    }

    close() {
        this.socket.close()
    }
}

async function waitFor(client, expression, label, timeoutMs = 12000) {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
        if (await client.evaluate(`Boolean(${expression})`)) return
        await delay(100)
    }
    throw new Error(`等待界面状态超时: ${label}`)
}

async function clickByAria(client, label) {
    const clicked = await client.evaluate(`(() => {
        const element = [...document.querySelectorAll('button[aria-label]')]
            .find(item => item.getAttribute('aria-label') === ${JSON.stringify(label)})
        if (!element) return false
        element.click()
        return true
    })()`)
    if (!clicked) throw new Error(`找不到按钮: ${label}`)
}

async function screenshot(client, name) {
    const result = await client.send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: false,
        fromSurface: true
    })
    await writeFile(path.join(artifactDir, name), Buffer.from(result.data, 'base64'))
}

let client
try {
    const pages = await waitForJson(`http://127.0.0.1:${port}/json/list`)
    const target = pages.find(item => item.type === 'page')
    if (!target?.webSocketDebuggerUrl) throw new Error('未找到可调试页面')
    client = new CdpClient(target.webSocketDebuggerUrl)
    await client.connect()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Log.enable')
    await client.send('Network.enable')
    await client.send('Page.navigate', { url })
    await waitFor(client, "document.readyState === 'complete'", '欢迎页加载')
    await waitFor(client, "document.querySelector('.welcome, .ide-shell-layout')", 'EasyCode 根界面')

    // Startup may briefly render the welcome page while the most recent
    // project is being restored.  Give that transaction priority instead of
    // racing it with a synthetic click on another recent project.
    const restoreDeadline = Date.now() + 8000
    while (Date.now() < restoreDeadline) {
        if (await client.evaluate("Boolean(document.querySelector('.ide-shell-layout'))")) break
        const busy = await client.evaluate("Boolean(document.querySelector('.welcome .el-button.is-loading'))")
        const recentReady = await client.evaluate("Boolean(document.querySelector('.welcome .recent-item'))")
        if (!busy && recentReady) break
        await delay(100)
    }
    const alreadyOpen = await client.evaluate("Boolean(document.querySelector('.ide-shell-layout'))")
    if (!alreadyOpen) {
        const opened = await client.evaluate(`(() => {
            const rows = [...document.querySelectorAll('.recent-item')]
            const row = rows.find(item => item.querySelector('.recent-name')?.textContent?.trim() === ${JSON.stringify(projectName)})
            const button = row?.querySelector('.recent-open')
            if (!button || button.disabled) return false
            button.click()
            return true
        })()`)
        if (!opened) throw new Error(`最近项目中未找到可打开的 ${projectName}`)
        await waitFor(client, "document.querySelector('.ide-shell-layout')", `${projectName} 工作区`, 20000)
    }

    await delay(800)
    await screenshot(client, '01-workflow.png')

    await clickByAria(client, '函数库')
    await waitFor(client, "document.querySelector('.function-panel')", '函数库面板')
    await waitFor(client, "document.querySelector('.status-right span:last-child')?.textContent?.includes('函数')", '函数画布模式')
    const functionOpened = await client.evaluate(`(() => {
        const button = document.querySelector('.function-row')
        if (!button) return false
        button.click()
        return true
    })()`)
    if (functionOpened) await delay(350)
    await screenshot(client, '02-function.png')

    await clickByAria(client, '页面地图')
    await waitFor(client, "document.querySelector('.page-map-panel')", '页面地图面板')
    await waitFor(client, "document.querySelector('.status-right span:last-child')?.textContent?.includes('页面地图')", '页面地图画布模式')
    await delay(300)
    await screenshot(client, '03-page-map.png')

    await clickByAria(client, '主流程大纲')
    await waitFor(client, "document.querySelector('.outline-panel')", '主流程面板')
    await waitFor(client, "document.querySelector('.status-right span:last-child')?.textContent?.includes('主流程')", '主流程画布模式')
    await delay(300)

    const audit = await client.evaluate(`(() => {
        const overflow = [...document.querySelectorAll('body *')]
            .filter(element => {
                const style = getComputedStyle(element)
                if (style.position === 'fixed') return false
                // Canvas ports deliberately extend beyond their cards and the
                // collapsed dock keeps a 5px hover affordance. These are not
                // content clipping defects.
                if (element.matches('.canvas-node-card, .node-handle, .fixed-dock-right')) return false
                return element.scrollWidth > element.clientWidth + 2
                    && style.overflowX === 'visible'
            })
            .slice(0, 30)
            .map(element => ({
                tag: element.tagName.toLowerCase(),
                className: String(element.className || '').slice(0, 140),
                clientWidth: element.clientWidth,
                scrollWidth: element.scrollWidth
            }))
        const unlabeledIconButtons = [...document.querySelectorAll('button')]
            .filter(button => !button.textContent.trim() && !button.getAttribute('aria-label') && !button.title)
            .map(button => String(button.className || ''))
        return {
            title: document.title,
            project: document.querySelector('.project-location')?.textContent?.trim() || '',
            canvasMode: document.querySelector('.status-right span:last-child')?.textContent?.trim() || '',
            nodeCount: document.querySelectorAll('.canvas-node-card').length,
            overflow,
            unlabeledIconButtons,
            bodySize: { width: document.body.clientWidth, height: document.body.clientHeight }
        }
    })()`)

    const severeEvents = client.events.filter(event => {
        if (event.method === 'Runtime.exceptionThrown') return true
        if (event.method === 'Log.entryAdded') return ['error', 'warning'].includes(event.params?.entry?.level)
        if (event.method === 'Network.loadingFailed') return !event.params?.canceled
        return false
    }).map(event => ({ method: event.method, params: event.params }))

    const report = {
        ok: severeEvents.length === 0 && audit.overflow.length === 0 && audit.unlabeledIconButtons.length === 0,
        projectName,
        url,
        audit,
        severeEvents
    }
    await writeFile(path.join(artifactDir, 'report.json'), JSON.stringify(report, null, 2), 'utf8')
    console.log(JSON.stringify(report, null, 2))
    if (!report.ok) process.exitCode = 2
} catch (error) {
    const diagnosticEvents = (client?.events || []).filter(event => (
        event.method === 'Runtime.exceptionThrown'
        || event.method === 'Log.entryAdded'
        || event.method === 'Network.loadingFailed'
        || (event.method === 'Network.responseReceived' && Number(event.params?.response?.status || 0) >= 400)
    ))
    const diagnostic = {
        error: error?.stack || String(error),
        eventCount: client?.events?.length || 0,
        events: diagnosticEvents.slice(-100)
    }
    if (client) {
        try {
            diagnostic.page = await client.evaluate(`({
                text: document.body?.innerText?.slice(0, 8000) || '',
                project: document.querySelector('.project-location')?.textContent?.trim() || '',
                mode: document.querySelector('.status-right')?.textContent?.trim() || '',
                messages: [...document.querySelectorAll('.el-message')].map(item => item.textContent.trim())
            })`)
            await screenshot(client, '99-failure.png')
        } catch (diagnosticError) {
            diagnostic.diagnosticError = diagnosticError?.stack || String(diagnosticError)
        }
    }
    await writeFile(path.join(artifactDir, 'failure.json'), JSON.stringify(diagnostic, null, 2), 'utf8')
    console.error(JSON.stringify(diagnostic, null, 2))
    process.exitCode = 1
} finally {
    client?.close()
    browser.kill()
}
