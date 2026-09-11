import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'
import {
    VNextButton,
    VNextDialog,
    VNextFormRow,
    VNextFormSection,
    VNextIconButton,
    VNextSelect,
    VNextSwitch,
    VNextTextField,
    VNextTextarea,
} from '../components/ui'

describe('shared UI primitives', () => {
    it('owns button state, loading, labels and icon geometry', async () => {
        const button = mount(VNextButton, { props: { loading: true, tone: 'primary', appearance: 'solid' }, slots: { default: '保存' } })
        expect(button.get('button').attributes('disabled')).toBeDefined()
        expect(button.get('button').attributes('aria-busy')).toBe('true')
        expect(button.text()).toContain('保存')

        const icon = mount(VNextIconButton, { props: { label: '刷新', pressed: true }, slots: { default: () => h('svg') } })
        expect(icon.get('button').attributes('aria-label')).toBe('刷新')
        expect(icon.get('button').attributes('aria-pressed')).toBe('true')
    })

    it('emits typed field edits without owning domain persistence', async () => {
        const input = mount(VNextTextField, { props: { modelValue: '旧值' } })
        await input.get('input').setValue('新值')
        expect(input.emitted('update:modelValue')?.[0]).toEqual(['新值'])

        const select = mount(VNextSelect, { props: { modelValue: 'a' }, slots: { default: '<option value="a">A</option><option value="b">B</option>' } })
        await select.get('select').setValue('b')
        expect(select.emitted('update:modelValue')?.[0]).toEqual(['b'])

        const textarea = mount(VNextTextarea, { props: { modelValue: '说明' } })
        await textarea.get('textarea').setValue('新说明')
        expect(textarea.emitted('update:modelValue')?.[0]).toEqual(['新说明'])

        const toggle = mount(VNextSwitch, { props: { modelValue: false, label: '启用计划' } })
        await toggle.get('button').trigger('click')
        expect(toggle.emitted('update:modelValue')?.[0]).toEqual([true])
    })

    it('keeps field help and errors in one shared form row', () => {
        const row = mount(VNextFormRow, { props: { label: '名称', required: true, error: '不能为空' }, slots: { default: () => h('input', { id: 'name' }) } })
        expect(row.text()).toContain('名称 *')
        expect(row.get('[role="alert"]').text()).toBe('不能为空')

        const section = mount(VNextFormSection, { props: { title: '高级参数', description: '只在需要时调整' }, slots: { default: '字段' } })
        expect(section.text()).toContain('高级参数')
        expect(section.text()).toContain('只在需要时调整')
    })

    it('traps dialog semantics and returns close through one event', async () => {
        const dialog = mount(VNextDialog, { attachTo: document.body, props: { open: true, title: '编辑内容' }, slots: { default: '正文' } })
        expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
        ;(document.body.querySelector('button[aria-label="关闭"]') as HTMLButtonElement).click()
        await dialog.vm.$nextTick()
        expect(dialog.emitted('close')).toHaveLength(1)
        dialog.unmount()
    })
})
