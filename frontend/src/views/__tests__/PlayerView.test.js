import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import PlayerView from '@/views/PlayerView.vue'
import client from '@/api/client'

vi.mock('@/api/client', () => ({
    default: {
        get: vi.fn(), post: vi.fn(), delete: vi.fn()
    }
}))

let eventSource
class FakeEventSource {
    constructor(url) { this.url = url; this.onmessage = null; this.onerror = null; eventSource = this }
    close() {}
}
globalThis.EventSource = FakeEventSource

const initPayload = {
    form_schema: { schema_version: 3, form_title: '交付脚本', entry: { node_name: '开始' }, groups: [] },
    user_config: { vars: {}, ctx: {}, overrides: {} },
    runtime_status: { state: 'ready', message: '脚本资源已就绪', can_resume: false },
    environment: { status: 'pass', counts: { pass: 4, warning: 0, error: 0 }, checks: [] }
}

const mountPlayer = async () => {
    const wrapper = shallowMount(PlayerView)
    await flushPromises()
    return wrapper
}

describe('PlayerView 运维交互', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        Object.defineProperty(window, 'chrome', { configurable: true, writable: true, value: undefined })
        eventSource = null
        localStorage.clear()
        client.get.mockImplementation((url) => {
            if (url === '/api/player/init') return Promise.resolve(initPayload)
            if (url === '/api/player/profiles') return Promise.resolve({ profiles: [] })
            if (url === '/api/player/environment') return Promise.resolve(initPayload.environment)
            if (url === '/api/player/status') return Promise.resolve({ state: 'ready', message: '就绪' })
            return Promise.resolve({})
        })
        client.post.mockImplementation((url) => {
            if (url === '/api/player/run') return Promise.resolve({ execution_id: 'exec-1', status: 'started' })
            return Promise.resolve({ status: 'success' })
        })
        client.delete.mockResolvedValue({ status: 'success' })
    })

    it('初始化后显示状态，并能创建独立实例和执行环境自检', async () => {
        const wrapper = await mountPlayer()
        expect(wrapper.text()).toContain('就绪')
        expect(wrapper.text()).toContain('运行入口：开始')

        await wrapper.find('[title="新增并行实例"]').trigger('click')
        expect(wrapper.text()).toContain('实例 2')

        const checkButton = wrapper.findAll('el-button').find(button => button.text().includes('环境自检'))
        await checkButton.trigger('click')
        await flushPromises()
        expect(client.get).toHaveBeenCalledWith('/api/player/environment', expect.objectContaining({ params: expect.any(Object) }))
        wrapper.unmount()
    })

    it('运行请求携带实例 ID，并消费 SSE 终态', async () => {
        const wrapper = await mountPlayer()
        const runButton = wrapper.findAll('el-button').find(button => button.text().includes('开始运行自动化'))
        await runButton.trigger('click')
        await flushPromises()

        expect(client.post).toHaveBeenCalledWith('/api/player/run', { instance_id: 'instance-1', resume: false })
        expect(eventSource.url).toContain('exec-1')
        eventSource.onmessage({ data: JSON.stringify({ status: { status: 'success', message: '执行完成' }, logs: [] }) })
        await wrapper.vm.$nextTick()
        expect(wrapper.text()).toContain('已完成')
        wrapper.unmount()
    })

    it('原生 WebView2 消息桥优先处理窗口操作和标题栏拖动', async () => {
        const postMessage = vi.fn()
        const addEventListener = vi.fn()
        const removeEventListener = vi.fn()
        Object.defineProperty(window, 'chrome', {
            configurable: true,
            writable: true,
            value: { webview: { postMessage, addEventListener, removeEventListener } }
        })

        const wrapper = await mountPlayer()
        await wrapper.find('[title="最大化/还原"]').trigger('click')
        await wrapper.find('.title-area').trigger('pointerdown', { button: 0 })

        expect(postMessage).toHaveBeenCalledWith({ event: 'window-command', version: 1, command: 'maximize' })
        expect(postMessage).toHaveBeenCalledWith({ event: 'window-command', version: 1, command: 'drag' })
        wrapper.unmount()
        expect(removeEventListener).toHaveBeenCalledWith('message', expect.any(Function))
    })
})
