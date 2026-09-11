import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramJsonValueField from '../ProgramJsonValueField.vue'
import jsonValueFieldSource from '../ProgramJsonValueField.vue?raw'

describe('ProgramJsonValueField compact layout', () => {
    it('keeps an atomic type and its 32px value Control on one row', () => {
        const wrapper = mount(ProgramJsonValueField, { props: { modelValue: '文本值' } })

        expect(wrapper.get('header').classes()).toContain('atomic-header')
        expect(wrapper.get('header > input').attributes('aria-label')).toBe('文本值')
        expect(wrapper.find('.json-children').exists()).toBe(false)
        expect(jsonValueFieldSource).toContain("select, input[type='text'], input[type='number'] { min-width: 0; min-height: var(--app-control-default)")
        expect(jsonValueFieldSource).toContain('header.atomic-header { display: grid; grid-template-columns: minmax(88px, auto) minmax(0, 1fr)')
        expect(jsonValueFieldSource).toContain('@container (max-width: 320px)')
    })

    it('keeps object keys beside their action and preserves destructive type confirmation', async () => {
        const wrapper = mount(ProgramJsonValueField, {
            props: { modelValue: { account: 'alice' } },
        })

        expect(wrapper.get('.child-heading input').attributes('value')).toBe('account')
        expect(wrapper.get('.child-heading button').text()).toContain('删除')
        await wrapper.get('header select').setValue('array')
        expect(wrapper.get('.kind-change-confirm').text()).toContain('切换类型会清空当前内容')
        expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    })
})
