import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ProgramValueReferencePicker from '../ProgramValueReferencePicker.vue'
import referencePickerSource from '../ProgramValueReferencePicker.vue?raw'
import ProgramValueTreeField from '../ProgramValueTreeField.vue'
import type { AvailableProgramValue, ProgramValueNode } from '../types'

const values: AvailableProgramValue[] = [
    { source: 'local', id: 'symbol_room', display_name: '当前房间码', value_type: 'string' },
    { source: 'project', id: 'variable_room', display_name: '默认房间码', value_type: 'string' },
    { source: 'project', id: 'variable_count', display_name: '重试次数', value_type: 'int64' },
]

describe('ProgramValueReferencePicker', () => {
    it('separates local and project values and filters by name or type', async () => {
        const wrapper = mount(ProgramValueReferencePicker, {
            props: { values, currentKey: 'local:symbol_room' },
        })

        expect(wrapper.get('.reference-trigger').text()).toContain('局部')
        expect(wrapper.get('.reference-trigger').text()).toContain('当前房间码')
        await wrapper.get('.reference-trigger').trigger('click')
        expect(wrapper.findAll('.reference-group > strong').map((item) => item.text())).toEqual(['局部', '项目'])

        await wrapper.get('input[type="search"]').setValue('默认')
        expect(wrapper.findAll('[role="option"]')).toHaveLength(1)
        expect(wrapper.get('[role="option"]').text()).toContain('默认房间码')
        await wrapper.get('[role="option"]').trigger('click')

        expect(wrapper.emitted('select')?.[0]).toEqual([values[1]])
        expect(wrapper.find('.reference-panel').exists()).toBe(false)
    })

    it('supports type search without exposing stable ids as visual noise', async () => {
        const wrapper = mount(ProgramValueReferencePicker, { props: { values } })
        await wrapper.get('.reference-trigger').trigger('click')
        await wrapper.get('input[type="search"]').setValue('int64')
        expect(wrapper.get('[role="option"]').text()).toContain('重试次数')
        expect(wrapper.text()).not.toContain('variable_count')
    })

    it('opens directly into its 32px search path without another step', async () => {
        const wrapper = mount(ProgramValueReferencePicker, {
            props: { values },
            attachTo: document.body,
        })
        await wrapper.get('.reference-trigger').trigger('click')
        await wrapper.vm.$nextTick()

        expect(document.activeElement).toBe(wrapper.get('.search-field input').element)
        expect(referencePickerSource).toContain('.reference-trigger { width: 100%; min-height: var(--app-control-default)')
        expect(referencePickerSource).toContain('.search-field { min-height: var(--app-control-default)')
        wrapper.unmount()
    })
})

describe('ProgramValueTreeField references', () => {
    it('uses the same searchable picker for a nested structured value', async () => {
        const value: ProgramValueNode = {
            value_id: 'value_nested',
            kind: 'literal',
            value_type: 'string',
            value: '',
        }
        const wrapper = mount(ProgramValueTreeField, {
            props: { label: '房间码', value, availableValues: values },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await wrapper.get('.expression-editor').setValue('@')
        const projectOption = wrapper.findAll('.value-suggestion').find((item) => item.text().includes('默认房间码'))
        expect(projectOption).toBeTruthy()
        await projectOption!.trigger('click')
        await wrapper.get('.expression-editor').trigger('keydown.enter')

        expect(wrapper.emitted('replace')?.at(-1)?.[0]).toMatchObject({
            value_id: 'value_nested',
            kind: 'project_variable_ref',
            variable_id: 'variable_room',
            display_name: '默认房间码',
            value_type: 'string',
        })
    })
})
