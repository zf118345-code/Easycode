import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import VNextConfirmDialog from '../components/VNextConfirmDialog.vue'


describe('VNextConfirmDialog', () => {
    afterEach(() => {
        document.body.innerHTML = ''
    })

    it('在 EasyCode 内完成确认并提供明确的无障碍关系', async () => {
        const wrapper = mount(VNextConfirmDialog, {
            attachTo: document.body,
            props: {
                open: true,
                title: '重置测试分组码？',
                message: '重置会改变后续稳定灰度分组。',
                confirmLabel: '重置分组码',
                tone: 'warning',
            },
        })

        const dialog = document.body.querySelector<HTMLElement>('[role="alertdialog"]')
        expect(dialog).not.toBeNull()
        expect(dialog?.getAttribute('aria-modal')).toBe('true')
        expect(document.body.textContent).toContain('重置测试分组码？')
        expect(document.body.textContent).toContain('重置分组码')

        const confirm = Array.from(document.body.querySelectorAll('button')).find(
            (button) => button.textContent?.includes('重置分组码'),
        ) as HTMLButtonElement
        confirm.click()
        expect(wrapper.emitted('confirm')).toHaveLength(1)
        wrapper.unmount()
    })

    it('Escape 只取消当前决定并归还焦点', async () => {
        const trigger = document.createElement('button')
        document.body.appendChild(trigger)
        trigger.focus()
        const wrapper = mount(VNextConfirmDialog, {
            attachTo: document.body,
            props: { open: true, title: '确认操作', message: '是否继续？' },
        })

        const dialog = document.body.querySelector<HTMLElement>('[role="alertdialog"]')!
        dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
        expect(wrapper.emitted('cancel')).toHaveLength(1)
        await wrapper.setProps({ open: false })
        expect(document.activeElement).toBe(trigger)
        wrapper.unmount()
    })

    it('破坏性决定可禁止遮罩误关闭，但显式取消仍然有效', async () => {
        const wrapper = mount(VNextConfirmDialog, {
            attachTo: document.body,
            props: {
                open: true,
                title: '确认删除',
                message: '删除后无法恢复。',
                dismissOnBackdrop: false,
            },
        })

        const backdrop = document.body.querySelector<HTMLElement>('.decision-backdrop')!
        backdrop.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
        expect(wrapper.emitted('cancel')).toBeUndefined()

        const cancel = Array.from(document.body.querySelectorAll('button')).find(
            (button) => button.textContent?.includes('取消'),
        ) as HTMLButtonElement
        cancel.click()
        expect(wrapper.emitted('cancel')).toHaveLength(1)
        wrapper.unmount()
    })
})
