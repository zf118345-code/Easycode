import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'

/* eslint-disable vue/one-component-per-file -- the fixture exercises the composable as a rendered modal */

const DialogFixture = defineComponent({
    setup() {
        const open = ref(false)
        const dialog = ref<HTMLElement | null>(null)
        useDialogFocusReturn(open, dialog)
        return () => h('main', [
            h('button', { class: 'trigger', onClick: () => { open.value = true } }, '打开'),
            open.value ? h('section', {
                ref: dialog,
                role: 'dialog',
                tabindex: -1,
                onKeydown: trapDialogFocus,
            }, [
                h('button', { class: 'cancel', 'data-dialog-initial-focus': '', onClick: () => { open.value = false } }, '取消'),
                h('button', { class: 'confirm' }, '确认'),
            ]) : null,
        ])
    },
})

describe('dialogFocus', () => {
    it('focuses the safe action, traps Tab and restores the opening control', async () => {
        const wrapper = mount(DialogFixture, { attachTo: document.body })
        const trigger = wrapper.get('.trigger')
        ;(trigger.element as HTMLElement).focus()
        await trigger.trigger('click')
        await flushPromises()
        expect(document.activeElement).toBe(wrapper.get('.cancel').element)

        ;(wrapper.get('.confirm').element as HTMLElement).focus()
        await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Tab' })
        expect(document.activeElement).toBe(wrapper.get('.cancel').element)

        await wrapper.get('.cancel').trigger('click')
        await flushPromises()
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })
})
