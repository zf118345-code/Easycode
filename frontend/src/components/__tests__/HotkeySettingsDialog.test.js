// frontend/src/components/__tests__/HotkeySettingsDialog.test.js
// 全局快捷键设置弹窗：
// 1. 加载并展示快捷键列表
// 2. 点击「修改」进入录制，按键组合 → 预览
// 3. 保存调用 putHotkeys，冲突提示
// 4. 保存成功更新状态
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import HotkeySettingsDialog from '../HotkeySettingsDialog.vue'

vi.mock('@/api/uiControlApi', () => ({
    uiControlApi: {
        getHotkeys: vi.fn(() => Promise.resolve({
            success: true,
            hotkeys: { enter_capture: 'ctrl+shift+c', copy_generate: 'ctrl+shift+enter', exit_mode: 'esc' }
        })),
        putHotkeys: vi.fn(() => Promise.resolve({ ok: true, hotkeys: {} }))
    }
}))

import { uiControlApi } from '@/api/uiControlApi'

const DialogStub = { template: '<div class="stub-dialog"><slot /><slot name="footer" /></div>' }
const ButtonStub = { template: '<button class="stub-btn" @click="$emit(\'click\')"><slot /></button>' }

function mountDialog() {
    return mount(HotkeySettingsDialog, {
        props: { modelValue: true },
        global: { stubs: { 'el-dialog': DialogStub, 'el-button': ButtonStub } }
    })
}

async function settle() {
    await flushPromises()
    await nextTick()
    await nextTick()
}

describe('HotkeySettingsDialog 快捷键设置', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        vi.clearAllMocks()
    })
    afterEach(() => {
        document.body.innerHTML = ''
    })

    it('加载并展示快捷键条目（进入/生成/退出 + 悬停识别说明）', async () => {
        const wrapper = mountDialog()
        await settle()
        const text = wrapper.text()
        expect(text).toContain('进入控件捕获模式')
        expect(text).toContain('复制选择器 + 生成控件节点')
        expect(text).toContain('退出捕获模式')
        expect(text).toContain('鼠标悬停目标 250ms 自动识别（无需快捷键）')
        expect(text).toContain('ctrl')
        expect(wrapper.findAll('.hk-table .hk-row').length).toBe(4) // 表头 + 3 项
        wrapper.unmount()
    })

    it('点击修改进入录制，按住组合键预览', async () => {
        const wrapper = mountDialog()
        await settle()

        // 第一行的「修改」按钮
        const modifyBtn = wrapper.findAll('.c-action .stub-btn').find(b => b.text().includes('修改'))
        await modifyBtn.trigger('click')
        await nextTick()
        expect(wrapper.text()).toContain('请按下组合键…')

        // 模拟按下 ctrl+shift+x
        const ev = new KeyboardEvent('keydown', { key: 'x', ctrlKey: true, shiftKey: true, bubbles: true })
        window.dispatchEvent(ev)
        await nextTick()
        const text = wrapper.text()
        expect(text).toContain('ctrl')
        expect(text).toContain('shift')
        expect(text).toContain('x')
        wrapper.unmount()
    })

    it('保存调用 putHotkeys 且冲突时提示', async () => {
        uiControlApi.putHotkeys.mockResolvedValue({ ok: false, message: '组合键已被其他软件占用: ctrl+shift+x' })
        const wrapper = mountDialog()
        await settle()

        const modifyBtn = wrapper.findAll('.c-action .stub-btn').find(b => b.text().includes('修改'))
        await modifyBtn.trigger('click')
        await nextTick()
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'x', ctrlKey: true, shiftKey: true, bubbles: true }))
        await nextTick()

        const applyBtn = wrapper.findAll('.c-action .stub-btn').find(b => b.text().includes('应用'))
        await applyBtn.trigger('click')
        await flushPromises()

        expect(uiControlApi.putHotkeys).toHaveBeenCalledWith({ enter_capture: 'ctrl+shift+x' })
        expect(wrapper.text()).toContain('占用')
        wrapper.unmount()
    })

    it('保存成功更新显示', async () => {
        uiControlApi.putHotkeys.mockResolvedValue({ ok: true, hotkeys: {} })
        const wrapper = mountDialog()
        await settle()

        const modifyBtn = wrapper.findAll('.c-action .stub-btn').find(b => b.text().includes('修改'))
        await modifyBtn.trigger('click')
        await nextTick()
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r', altKey: true, bubbles: true }))
        await nextTick()
        const applyBtn = wrapper.findAll('.c-action .stub-btn').find(b => b.text().includes('应用'))
        await applyBtn.trigger('click')
        await flushPromises()

        expect(wrapper.text()).toContain('已保存并注册成功')
        wrapper.unmount()
    })
})
