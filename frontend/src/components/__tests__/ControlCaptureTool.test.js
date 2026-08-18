// frontend/src/components/__tests__/ControlCaptureTool.test.js
// 控件捕获模式（零轮询事件驱动版）：
// 1. 展示未激活状态与快捷键说明（打开时一次性读取）
// 2. 进入/退出按钮调用 modeControl（一次性请求）
// 3. SSE 捕获事件（props.captureEvent）驱动面板：select/wheel 更新、clear 清空、copy 生成节点、mode 切换状态
// 4. backendConnected=false 时明示后端连接中断
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ControlCaptureTool from '../ControlCaptureTool.vue'

vi.mock('@/api/uiControlApi', () => ({
    uiControlApi: {
        mode: vi.fn(() => Promise.resolve({ success: true, active: false, hotkey_ok: true })),
        modeControl: vi.fn(() => Promise.resolve({ ok: true, active: true })),
        getHotkeys: vi.fn(() => Promise.resolve({
            success: true,
            hotkeys: { enter_capture: 'ctrl+shift+c', copy_generate: 'ctrl+shift+enter', exit_mode: 'esc' }
        }))
    }
}))

import { uiControlApi } from '@/api/uiControlApi'

const DialogStub = { template: '<div class="stub-dialog"><slot /><slot name="footer" /></div>' }
const ButtonStub = { template: '<button class="stub-btn" @click="$emit(\'click\')"><slot /></button>' }

function mountTool(props = {}) {
    return mount(ControlCaptureTool, {
        props: { modelValue: true, captureEvent: null, backendConnected: true, ...props },
        global: { stubs: { 'el-dialog': DialogStub, 'el-button': ButtonStub } }
    })
}

async function settle() {
    await flushPromises()
    await nextTick()
    await nextTick()
}

describe('ControlCaptureTool 控件捕获模式（零轮询事件驱动）', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        vi.clearAllMocks()
        // clearAllMocks 不清除 mockResolvedValue 实现，显式重置默认行为
        uiControlApi.mode.mockResolvedValue({ success: true, active: false, hotkey_ok: true })
    })
    afterEach(() => {
        document.body.innerHTML = ''
    })

    it('展示未激活状态与快捷键说明（打开时一次性读取配置）', async () => {
        const wrapper = mountTool()
        await settle()

        const text = wrapper.text()
        expect(text).toContain('未激活')
        expect(text.toUpperCase()).toContain('CTRL+SHIFT+C')
        expect(text.toUpperCase()).toContain('CTRL+SHIFT')   // 识别 = Ctrl+Shift+左键（固定组合）
        expect(text.toUpperCase()).toContain('ESC')
        expect(uiControlApi.getHotkeys).toHaveBeenCalled()
        wrapper.unmount()
    })

    it('打开时一次性获取模式状态（非轮询）', async () => {
        uiControlApi.mode.mockResolvedValue({ success: true, active: true, hotkey_ok: true })
        const wrapper = mountTool()
        await settle()
        expect(wrapper.text()).toContain('捕获模式运行中')
        expect(uiControlApi.mode).toHaveBeenCalledTimes(1)
        wrapper.unmount()
    })

    it('进入模式按钮调用 modeControl(start) 且状态更新', async () => {
        const wrapper = mountTool()
        await settle()

        const enterBtn = wrapper.findAll('.stub-btn').find(b => b.text().includes('进入捕获模式'))
        expect(enterBtn).toBeTruthy()
        await enterBtn.trigger('click')
        await settle()

        expect(uiControlApi.modeControl).toHaveBeenCalledWith('start')
        expect(wrapper.text()).toContain('捕获模式运行中')
        wrapper.unmount()
    })

    it('SSE select 事件 → 面板展示选中控件', async () => {
        const wrapper = mountTool()
        await settle()
        expect(wrapper.text()).not.toContain('确定')

        await wrapper.setProps({ captureEvent: { event: 'select', info: { name: '确定', control_type: 'button', rect: [0, 0, 10, 10] }, selector: 'name="确定"' } })
        await nextTick()

        expect(wrapper.text()).toContain('确定')
        expect(wrapper.text()).toContain('name="确定"')
        wrapper.unmount()
    })

    it('SSE wheel 事件 → 面板更新为新层级控件', async () => {
        const wrapper = mountTool()
        await wrapper.setProps({ captureEvent: { event: 'select', info: { name: '确定', control_type: 'button' }, selector: 'name="确定"' } })
        await nextTick()
        expect(wrapper.text()).toContain('确定')

        await wrapper.setProps({ captureEvent: { event: 'wheel', info: { name: '窗口', control_type: 'window' }, selector: 'name="窗口"' } })
        await nextTick()
        expect(wrapper.text()).toContain('窗口')
        expect(wrapper.text()).not.toContain('确定')
        wrapper.unmount()
    })

    it('SSE clear 事件 → 清空面板', async () => {
        const wrapper = mountTool()
        await wrapper.setProps({ captureEvent: { event: 'select', info: { name: '确定', control_type: 'button' }, selector: 'name="确定"' } })
        await nextTick()
        expect(wrapper.text()).toContain('确定')

        await wrapper.setProps({ captureEvent: { event: 'clear' } })
        await nextTick()
        expect(wrapper.text()).not.toContain('确定')
        wrapper.unmount()
    })

    it('SSE copy 事件 → emit node-requested（生成控件节点）', async () => {
        const wrapper = mountTool()
        await wrapper.setProps({ captureEvent: { event: 'copy', info: { name: '开始游戏', control_type: 'button' }, selector: 'name="开始游戏"' } })
        await nextTick()

        const emitted = wrapper.emitted('node-requested')
        expect(emitted && emitted.length).toBe(1)
        expect(emitted[0][0].name).toBe('开始游戏')
        expect(wrapper.text()).toContain('最近捕获')
        wrapper.unmount()
    })

    it('SSE mode 事件 → 状态切换', async () => {
        const wrapper = mountTool()
        await wrapper.setProps({ captureEvent: { event: 'mode', active: true } })
        await nextTick()
        expect(wrapper.text()).toContain('捕获模式运行中')

        await wrapper.setProps({ captureEvent: { event: 'mode', active: false } })
        await nextTick()
        expect(wrapper.text()).toContain('未激活')
        wrapper.unmount()
    })

    it('backendConnected=false → 明示后端连接中断（模态已失效）', async () => {
        const wrapper = mountTool({ captureEvent: { event: 'mode', active: true } })
        await nextTick()
        expect(wrapper.text()).toContain('捕获模式运行中')

        await wrapper.setProps({ backendConnected: false })
        await nextTick()
        expect(wrapper.text()).toContain('后端连接中断')
        expect(wrapper.text()).not.toContain('捕获模式运行中')
        wrapper.unmount()
    })

    it('关闭时退出模式（若激活）', async () => {
        uiControlApi.mode.mockResolvedValue({ success: true, active: true, hotkey_ok: true })
        const wrapper = mountTool()
        await settle()
        expect(uiControlApi.modeControl).not.toHaveBeenCalled()

        await wrapper.setProps({ modelValue: false })
        await settle()
        expect(uiControlApi.modeControl).toHaveBeenCalledWith('stop')
        wrapper.unmount()
    })
})
