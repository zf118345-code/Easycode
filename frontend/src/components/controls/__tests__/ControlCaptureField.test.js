// frontend/src/components/controls/__tests__/ControlCaptureField.test.js
// 控件信息字段（只读 textarea 展示捕获全部信息 + 捕获控件/重置控件按钮）：
// 1. 只读展示当前控件完整信息（名称/类型/自动化ID/坐标等分行）
// 2. 「捕获控件」→ 注册填充回调 + 启动捕获模式
// 3. 捕获回调 → 回填名称 + 写回 by/control_info 到 context
// 4. 「重置控件」→ 清空 + emit capture-reset
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ControlCaptureField from '../ControlCaptureField.vue'
import { useUiStore } from '@/stores'
import { uiControlApi } from '@/api/uiControlApi'

vi.mock('@/api/uiControlApi', () => ({
    uiControlApi: {
        modeControl: vi.fn(() => Promise.resolve({ ok: true })),
        mode: vi.fn(() => Promise.resolve({ success: true, active: false }))
    }
}))

function mountField(props = {}) {
    return mount(ControlCaptureField, {
        props: {
            config: { type: 'capture_str', label: '控件信息' },
            modelValue: '',
            context: {},
            ...props
        },
        global: {
            stubs: { 'el-input': true }
        }
    })
}

function findBtn(wrapper, text) {
    return wrapper.findAll('button').find(b => b.text().includes(text))
}

describe('ControlCaptureField 控件信息字段', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
    })

    it('只读展示当前控件完整信息（分行）', () => {
        const wrapper = mountField({
            modelValue: '确定',
            context: {
                control_info: {
                    name: '确定', control_type: 'button', automation_id: 'btn_1',
                    class_name: 'Button', window_title: '主窗口', rect: [10, 20, 30, 40]
                }
            }
        })
        const input = wrapper.findComponent({ name: 'ElInput' })
        expect(input.exists()).toBe(true)
        // stub 组件不声明 props，传入值以 kebab-case attr 透传
        const shown = input.attributes('model-value') || input.props('modelValue') || ''
        expect(shown).toContain('控件名称：确定')
        expect(shown).toContain('控件类型：button')
        expect(shown).toContain('自动化ID：btn_1')
        expect(shown).toContain('窗口标题：主窗口')
        expect(shown).toContain('坐标：[10, 20, 30, 40]')
        expect(input.attributes('readonly') !== undefined || input.props('readonly') === true).toBe(true)
        wrapper.unmount()
    })

    it('无 control_info 时兜底显示控件名称', () => {
        const wrapper = mountField({ modelValue: '开始游戏', context: {} })
        const input = wrapper.findComponent({ name: 'ElInput' })
        const shown = input.attributes('model-value') || input.props('modelValue') || ''
        expect(shown).toBe('控件名称：开始游戏')
        wrapper.unmount()
    })

    it('「捕获控件」按钮：注册填充回调 + 启动捕获模式', async () => {
        const uiStore = useUiStore()
        const wrapper = mountField()
        await findBtn(wrapper, '捕获控件').trigger('click')

        expect(uiControlApi.modeControl).toHaveBeenCalledWith('start')
        expect(uiStore.captureFillHandler).toBeTypeOf('function')
        wrapper.unmount()
    })

    it('捕获回调：回填名称 + 写回 by/control_info 到 context', async () => {
        const uiStore = useUiStore()
        const context = {}
        const wrapper = mountField({ context })
        await findBtn(wrapper, '捕获控件').trigger('click')

        // 模拟 Ctrl+Shift+Enter 捕获成功 → 全局链路调用填充回调
        uiStore.captureFillHandler({
            name: '关闭按钮', control_type: 'button', automation_id: 'close_1',
            rect: [0, 0, 100, 40], window_title: '主窗口'
        })
        await wrapper.vm.$nextTick()

        const updates = wrapper.emitted('update:modelValue')
        expect(updates.at(-1)[0]).toBe('关闭按钮')
        expect(context.by).toBe('uia_name')
        expect(context.control_info.name).toBe('关闭按钮')
        expect(context.control_info.control_type).toBe('button')
        expect(context.control_info.window_title).toBe('主窗口')
        wrapper.unmount()
    })

    it('「重置控件」：清空名称 + emit capture-reset', async () => {
        const wrapper = mountField({ modelValue: '开始游戏' })
        await findBtn(wrapper, '重置控件').trigger('click')

        expect(wrapper.emitted('update:modelValue').at(-1)[0]).toBe('')
        expect(wrapper.emitted('capture-reset')).toBeTruthy()
        wrapper.unmount()
    })

    it('组件卸载时清空填充回调（防悬挂）', async () => {
        const uiStore = useUiStore()
        const wrapper = mountField()
        await findBtn(wrapper, '捕获控件').trigger('click')
        expect(uiStore.captureFillHandler).toBeTypeOf('function')

        wrapper.unmount()
        expect(uiStore.captureFillHandler).toBeNull()
    })
})
