import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VNextPaneResizer from '../VNextPaneResizer.vue'

describe('VNextPaneResizer', () => {
    it('supports keyboard resizing and restoring the safe default', async () => {
        const wrapper = mount(VNextPaneResizer, {
            props: {
                modelValue: 280,
                orientation: 'vertical' as const,
                min: 220,
                max: 460,
                defaultValue: 280,
                label: '调整函数库宽度',
                'onUpdate:modelValue': (value: number) => wrapper.setProps({ modelValue: value }),
            },
        })

        const separator = wrapper.get('[role="separator"]')
        expect(separator.attributes('aria-valuenow')).toBe('280')

        await separator.trigger('keydown', { key: 'ArrowRight' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([296])
        expect(wrapper.emitted('commit')?.at(-1)).toEqual([296])

        await wrapper.setProps({ modelValue: 420 })
        await separator.trigger('keydown', { key: 'Home' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([280])
        expect(wrapper.emitted('commit')?.at(-1)).toEqual([280])
    })

    it('grows a bottom panel upward and clamps its maximum', async () => {
        const wrapper = mount(VNextPaneResizer, {
            props: {
                modelValue: 550,
                orientation: 'horizontal' as const,
                min: 150,
                max: 560,
                defaultValue: 270,
                label: '调整底部面板高度',
                reverse: true,
                'onUpdate:modelValue': (value: number) => wrapper.setProps({ modelValue: value }),
            },
        })

        await wrapper.get('[role="separator"]').trigger('keydown', { key: 'ArrowUp' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([560])
    })

    it('reverses keyboard semantics for a right panel', async () => {
        const wrapper = mount(VNextPaneResizer, {
            props: {
                modelValue: 340,
                orientation: 'vertical' as const,
                min: 280,
                max: 560,
                defaultValue: 340,
                label: '调整右侧检查器宽度',
                reverse: true,
                'onUpdate:modelValue': (value: number) => wrapper.setProps({ modelValue: value }),
            },
        })

        await wrapper.get('[role="separator"]').trigger('keydown', { key: 'ArrowRight' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([324])
        await wrapper.get('[role="separator"]').trigger('keydown', { key: 'ArrowLeft' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([340])
    })
})
