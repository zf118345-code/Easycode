// frontend/src/layouts/__tests__/IdeLayoutCapture.test.js
// 捕获结果处理链路（回归：handleCaptureNodeRequested 曾因缺失 useUiStore 导入而静默崩溃）：
// 1. 有填充回调（节点表单「捕获控件」）→ 回填 + 退出捕获模式（一次性填充语义）
// 2. 无填充回调（顶部「控件捕获模式」）→ 生成新节点（连续捕获，模式不退出由后端保证）
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IdeLayout from '../IdeLayout.vue'
import { useProjectStore, useUiStore } from '@/stores'
import { uiControlApi } from '@/api/uiControlApi'

vi.mock('@/api/uiControlApi', () => ({
    uiControlApi: {
        modeControl: vi.fn(() => Promise.resolve({ ok: true })),
        mode: vi.fn(() => Promise.resolve({ success: true, active: false }))
    }
}))

// jsdom 无 EventSource：以桩替代并捕获实例，测试经真实 onmessage 链路驱动
// （SSE 事件 → IdeLayout → captureEvent prop → 面板 watch → emit node-requested → 处理）
let esInstance = null
class FakeEventSource {
    constructor() { esInstance = this; this.onopen = null; this.onerror = null; this.onmessage = null }
    close() {}
}
globalThis.EventSource = globalThis.EventSource || FakeEventSource

function pushSSE(payload) {
    esInstance.onmessage({ data: JSON.stringify(payload) })
}

const createControlNodeFromCaptureSpy = vi.fn()

function mountLayout() {
    return mount(IdeLayout, {
        global: {
            stubs: {
                TopMenuBar: true,
                DebugToolbar: true,
                ActivityBar: true,
                ToolWindow: true,
                // 可被 ref 调用的画布桩：暴露 createControlNodeFromCapture 供断言
                CanvasPage: { template: '<div />', methods: { createControlNodeFromCapture: createControlNodeFromCaptureSpy } },
                PanelSettingsDialog: true,
                FormSchemaEditor: true,
                HotkeySettingsDialog: true,
                ScreenshotTool: true,
                'el-tooltip': { template: '<span><slot /></span>' }
            }
        }
    })
}

describe('IdeLayout 捕获结果处理链路', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
    })

    it('copy 事件：有填充回调 → 回填当前编辑目标 + 退出捕获模式', async () => {
        const uiStore = useUiStore()
        const fillHandler = vi.fn()
        uiStore.setCaptureFillHandler(fillHandler)

        const wrapper = mountLayout()
        expect(esInstance).toBeTruthy()
        vi.clearAllMocks()  // 清掉挂载期面板自身 stopAll 的调用，只看 copy 链路

        pushSSE({ event: 'copy', info: { name: '开始游戏', control_type: 'button' }, selector: 'name="开始游戏"' })
        await wrapper.vm.$nextTick()
        await wrapper.vm.$nextTick()

        expect(fillHandler).toHaveBeenCalledWith({ name: '开始游戏', control_type: 'button' })
        expect(uiControlApi.modeControl).toHaveBeenCalledWith('stop')  // ⚡ 一次性填充完成即退出模式
        expect(createControlNodeFromCaptureSpy).not.toHaveBeenCalled()  // 有回调时不再生成新节点
        expect(uiStore.captureFillHandler).toBeNull()  // 用完即清（再次点击「捕获控件」重新注册）
        const tool = wrapper.findComponent({ name: 'ControlCaptureTool' })
        expect(tool.props('modelValue')).toBe(false)  // ⚡ 填充完成面板一并收起
        wrapper.unmount()
    })

    it('copy 事件：无填充回调 → 画布生成新节点，模式保持激活（连续捕获）', async () => {
        useProjectStore().currentProjectPath = 'D:/test/project'  // 生成新节点需要已打开项目

        const wrapper = mountLayout()
        vi.clearAllMocks()

        pushSSE({ event: 'copy', info: { name: '确定', control_type: 'button' } })
        await wrapper.vm.$nextTick()
        await wrapper.vm.$nextTick()

        expect(createControlNodeFromCaptureSpy).toHaveBeenCalledWith({ name: '确定', control_type: 'button' })
        expect(uiControlApi.modeControl).not.toHaveBeenCalled()  // 全局模式不退出（由后端保持激活）
        wrapper.unmount()
    })
})
