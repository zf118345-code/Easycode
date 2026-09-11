import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    bootstrap: vi.fn(), createInstance: vi.fn(), connect: vi.fn(), state: vi.fn(),
    control: vi.fn(), restart: vi.fn(), deleteInstance: vi.fn(),
    closeStatus: vi.fn(), prepareClose: vi.fn(), downloadDiagnostics: vi.fn(),
}))
vi.mock('../playerConsoleApi', () => ({ playerConsoleApi: api }))

import VNextPlayerConsoleApp from '../VNextPlayerConsoleApp.vue'

const instance = (id: string, name: string) => ({
    instance_id: id, installation_id: 'install_1', product_id: 'product_1',
    display_name: name, revision: 1, enabled: true, status: 'ready',
    installation: { installation_id: 'install_1', product_id: 'product_1', display_name: '超能世界', release_id: 'r1', enabled: true },
    console: { instance_id: id, instance_name: name, product_id: 'product_1', process_id: 0, port: 0, status: 'stopped', frame_url: '', execution: null },
})
const session = (id: string, name: string, status = 'ready') => ({
    instance_id: id, instance_name: name, product_id: 'product_1', process_id: id === 'a' ? 101 : 102,
    port: id === 'a' ? 40101 : 40102, status, frame_url: `http://127.0.0.1:40${id === 'a' ? '101' : '102'}/player.html?embedded=1`,
    execution: status === 'running' ? { execution_id: 'run_a', status: 'running' } : null,
})

describe('VNextPlayerConsoleApp', () => {
    const nativePostMessage = vi.fn()
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
        api.bootstrap.mockResolvedValue({
            schema_version: 1,
            installations: [{ installation_id: 'install_1', product_id: 'product_1', display_name: '超能世界', release_id: 'r1', enabled: true }],
            instances: [instance('a', '账号 A'), instance('b', '账号 B')],
        })
        api.connect.mockImplementation((id: string) => Promise.resolve(session(id, id === 'a' ? '账号 A' : '账号 B', id === 'a' ? 'running' : 'ready')))
        api.state.mockImplementation((id: string) => Promise.resolve(session(id, id === 'a' ? '账号 A' : '账号 B')))
        api.control.mockResolvedValue({ ok: true })
        api.deleteInstance.mockResolvedValue({ ok: true })
        api.closeStatus.mockResolvedValue({ schema_version: 1, active_count: 0, active_instances: [] })
        api.prepareClose.mockResolvedValue({ schema_version: 1, ready: true, active_count: 0, active_instances: [], stopped_instance_count: 2 })
        api.downloadDiagnostics.mockResolvedValue(new Blob(['PK valid support archive'], { type: 'application/zip' }))
        ;(window as any).chrome = { webview: { postMessage: nativePostMessage, addEventListener: vi.fn(), removeEventListener: vi.fn() } }
    })
    afterEach(() => {
        vi.useRealTimers()
        delete (window as any).chrome
    })

    it('在同一窗口切换隔离实例且保留先前 iframe', async () => {
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()
        expect(api.connect).toHaveBeenCalledWith('a')
        expect(wrapper.findAll('iframe')).toHaveLength(1)

        await wrapper.findAll('.instance-row > button')[1].trigger('click')
        await flushPromises()
        expect(api.connect).toHaveBeenCalledWith('b')
        expect(wrapper.findAll('iframe')).toHaveLength(2)
        expect(wrapper.findAll('iframe')[0].attributes('style')).toContain('display: none')
        expect(wrapper.findAll('iframe')[1].attributes('style') || '').not.toContain('display: none')
        wrapper.unmount()
    })

    it('列表控制只操作当前实例运行', async () => {
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()
        await wrapper.get('[aria-label="暂停当前任务"]').trigger('click')
        await flushPromises()
        expect(api.control).toHaveBeenCalledWith('a', 'pause')
        wrapper.unmount()
    })

    it('每个实例行直接展示运行管理并且不再提供独立窗口入口', async () => {
        api.connect.mockImplementation((id: string) => Promise.resolve(session(id, id === 'a' ? '账号 A' : '账号 B', 'ready')))
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()

        expect(wrapper.findAll('[aria-label="运行此实例"]')).toHaveLength(2)
        expect(wrapper.findAll('.instance-actions [aria-label="刷新实例"]')).toHaveLength(2)
        expect(wrapper.findAll('[aria-label="删除实例"]')).toHaveLength(2)
        expect(wrapper.find('[aria-label="改用独立窗口打开"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('实例后端状态异常时仍保留轻量诊断入口', async () => {
        api.connect.mockResolvedValue({
            ...session('a', '账号 A', 'unreachable'),
            frame_url: '',
            error_id: 'schedule.instance_worker_unreachable',
            error_message: '实例工作进程已失去连接，可以原位重启。',
        })
        const writeText = vi.fn().mockResolvedValue(undefined)
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()

        expect(wrapper.get('[aria-label="复制诊断摘要"]').text()).toBe('复制摘要')
        expect(wrapper.get('[aria-label="导出最近诊断包"]').text()).toBe('诊断包')
        await wrapper.get('[aria-label="复制诊断摘要"]').trigger('click')
        await flushPromises()
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining('schedule.instance_worker_unreachable'))
        expect(wrapper.text()).toContain('诊断摘要已复制')
        wrapper.unmount()
    })

    it('诊断接口失败时不会把空响应误报为已生成', async () => {
        api.connect.mockResolvedValue({
            ...session('a', '账号 A', 'unreachable'),
            frame_url: '',
            error_id: 'schedule.instance_worker_unreachable',
            error_message: '实例工作进程已失去连接，可以原位重启。',
        })
        api.downloadDiagnostics.mockRejectedValue(new Error('诊断服务没有返回有效 ZIP，请刷新实例后重试'))
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()

        await wrapper.get('[aria-label="导出最近诊断包"]').trigger('click')
        await flushPromises()

        expect(wrapper.text()).toContain('诊断服务没有返回有效 ZIP')
        expect(wrapper.text()).not.toContain('诊断包已生成')
        wrapper.unmount()
    })

    it('顶部加号直接创建唯一实例，不出现名称录入中间态', async () => {
        api.createInstance.mockResolvedValue({ instance: instance('c', '实例 3') })
        const wrapper = mount(VNextPlayerConsoleApp)
        await flushPromises()

        expect(wrapper.find('.create-instance').exists()).toBe(false)
        await wrapper.get('[aria-label="为当前产品新建实例"]').trigger('click')
        await flushPromises()

        expect(api.createInstance).toHaveBeenCalledWith('install_1')
        expect(api.connect).toHaveBeenCalledWith('c')
        expect(wrapper.find('input[placeholder="实例名称"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('空闲实例经过共享确认框删除并选择相邻实例', async () => {
        api.connect.mockImplementation((id: string) => Promise.resolve(session(id, id === 'a' ? '账号 A' : '账号 B', 'ready')))
        const wrapper = mount(VNextPlayerConsoleApp, { attachTo: document.body })
        await flushPromises()

        await wrapper.get('[aria-label="删除实例"]').trigger('click')
        await flushPromises()
        expect(document.body.textContent).toContain('本机配置和日志会移入可恢复目录')
        ;(document.querySelector('[role="alertdialog"] .vnext-button.is-solid') as HTMLButtonElement).click()
        await flushPromises()

        expect(api.deleteInstance).toHaveBeenCalledWith('a', 1)
        wrapper.unmount()
    })

    it('关闭时按真实活动实例确认，取消保留现场，确认后停止全部实例', async () => {
        api.closeStatus.mockResolvedValue({
            schema_version: 1,
            active_count: 2,
            active_instances: [
                { instance_id: 'a', instance_name: '账号 A', status: 'running' },
                { instance_id: 'b', instance_name: '账号 B', status: 'paused' },
            ],
        })
        api.prepareClose.mockResolvedValue({ schema_version: 1, ready: true, active_count: 2, active_instances: [], stopped_instance_count: 2 })
        const wrapper = mount(VNextPlayerConsoleApp, { attachTo: document.body })
        await flushPromises()

        await wrapper.get('[aria-label="关闭窗口"]').trigger('click')
        await flushPromises()
        expect(document.body.textContent).toContain('当前有 2 个 Player 实例仍在运行')
        ;(document.querySelector('[role="alertdialog"] .vnext-button:not(.is-solid)') as HTMLButtonElement).click()
        await flushPromises()
        expect(nativePostMessage).toHaveBeenCalledWith({ event: 'window-command', version: 1, command: 'close-cancelled' })

        await wrapper.get('[aria-label="关闭窗口"]').trigger('click')
        await flushPromises()
        ;(document.querySelector('[role="alertdialog"] .vnext-button.is-solid') as HTMLButtonElement).click()
        await flushPromises()
        expect(api.prepareClose).toHaveBeenCalledWith(true)
        expect(nativePostMessage).toHaveBeenCalledWith({ event: 'window-command', version: 1, command: 'close-confirmed' })
        wrapper.unmount()
    })
})
