import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { ParameterControlType, ParameterUiAction } from '../../types'
import VNextValueControl from '../../components/VNextValueControl.vue'
import ProgramParameterControl from '../ProgramParameterControl.vue'
import type { ProgramValueCatalogDto } from '../serverTypes'
import type { ProgramParameterContract, ProgramValueNode, RecordValueNode } from '../types'

function parameter(overrides: Partial<ProgramParameterContract> = {}): ProgramParameterContract {
    return {
        parameter_id: 'parameter_value',
        display_name: '值',
        value_type: 'string',
        required: false,
        allowed_sources: ['fixed'],
        ui: { control: 'expression' },
        ...overrides,
    }
}

function literal(valueId: string, value: string | number | boolean | null, valueType = 'string'): ProgramValueNode {
    return { value_id: valueId, kind: 'literal', value_type: valueType, value }
}

function catalog(record: NonNullable<ProgramValueCatalogDto['record']>): ProgramValueCatalogDto {
    return {
        schema_version: 2,
        registry_version: 1,
        registry_hash: 'sha256:parameter-control-test',
        revision: 'revision-1',
        expected_type: record.type_id,
        operations: [],
        members: [],
        sources: [],
        record,
    }
}

const ocrCatalog = catalog({
    type_id: 'ocr_preprocess',
    display_name: 'OCR 预处理',
    authoring_mode: 'constructible',
    editor_strategy: 'inline_record',
    fields: [
        { field_id: 'ocr_preprocess.field.grayscale', display_name: '灰度化', value_type: 'bool', description: '', choices: [], required: false, has_default: true, default: false, ui: { control: 'toggle' } },
        { field_id: 'ocr_preprocess.field.binary', display_name: '二值化', value_type: 'bool', description: '', choices: [], required: false, has_default: true, default: false, ui: { control: 'toggle' } },
        {
            field_id: 'ocr_preprocess.field.threshold', display_name: '阈值', value_type: 'int64', description: '', choices: [],
            required: false, has_default: true, default: 127, constraints: { minimum: 0, maximum: 255 },
            ui: {
                control: 'slider-number', placeholder: '0–255', help: '仅在开启二值化时生效。',
                visible_when: { field_id: 'ocr_preprocess.field.binary', operator: 'equals', value: true },
            },
        },
        { field_id: 'ocr_preprocess.field.invert', display_name: '反色', value_type: 'bool', description: '', choices: [], required: false, has_default: true, default: false, ui: { control: 'toggle' } },
    ],
})

function ocrValue(binary: boolean): RecordValueNode {
    return {
        value_id: 'value_preprocess',
        kind: 'record',
        value_type: 'ocr_preprocess',
        record_type: 'ocr_preprocess',
        record_name: 'OCR 预处理',
        field_names: {
            'ocr_preprocess.field.grayscale': '灰度化',
            'ocr_preprocess.field.binary': '二值化',
            'ocr_preprocess.field.threshold': '阈值',
            'ocr_preprocess.field.invert': '反色',
        },
        fields: {
            'ocr_preprocess.field.grayscale': literal('value_grayscale', false, 'bool'),
            'ocr_preprocess.field.binary': literal('value_binary', binary, 'bool'),
            'ocr_preprocess.field.threshold': literal('value_threshold', 127, 'int64'),
            'ocr_preprocess.field.invert': literal('value_invert', false, 'bool'),
        },
    }
}

function mountParameter(
    controlParameter: ProgramParameterContract,
    value: ProgramValueNode,
    extra: Record<string, unknown> = {},
) {
    return mount(ProgramParameterControl, {
        props: {
            statementId: 'statement-1',
            parameter: controlParameter,
            value,
            valueEditorAvailable: true,
            ...extra,
        },
    })
}

describe('ProgramParameterControl', () => {
    it('keeps only compact toggles beside their labels and gives ordinary controls a full-width row', () => {
        const textField = mountParameter(parameter(), literal('value_text', '你好'))
        expect(textField.get('.vnext-control-field').classes()).toContain('is-stacked')

        const toggleField = mountParameter(parameter({
            display_name: '启用', value_type: 'bool', ui: { control: 'toggle' },
        }), literal('value_enabled', true, 'bool'))
        expect(toggleField.get('.vnext-control-field').classes()).not.toContain('is-stacked')
    })

    it('renders an unset color as the shared RGBA control and exposes the typed capture action', async () => {
        const wrapper = mountParameter(parameter({
            parameter_id: 'color', display_name: '颜色', value_type: 'color', required: true,
            ui: {
                control: 'color',
                actions: [{ id: 'pick-color', capture_kind: 'color', platforms: ['windows'] }],
            },
        }), { value_id: 'value_color', kind: 'unset', value_type: 'color' })

        expect(wrapper.find('.expression-surface').exists()).toBe(false)
        expect(wrapper.get<HTMLInputElement>('.color-hex').element.value).toBe('')
        await wrapper.get('button[aria-label="从目标画面取色"]').trigger('click')
        expect(wrapper.emitted('capture')?.[0]?.[0]).toMatchObject({
            statement_id: 'statement-1', parameter_id: 'color', value_id: 'value_color',
            action: { id: 'pick-color', capture_kind: 'color' },
        })
    })

    it('renders inline OCR preprocessing directly and reveals the bounded threshold only for binary mode', async () => {
        const resolveCatalog = vi.fn(async () => ocrCatalog)
        const controlParameter = parameter({
            parameter_id: 'preprocess',
            display_name: '预处理',
            value_type: 'ocr_preprocess',
            ui: { control: 'key-value', editor_strategy: 'inline_record' },
        })
        const wrapper = mountParameter(controlParameter, ocrValue(false), { resolveCatalog })
        await flushPromises()

        expect(resolveCatalog).toHaveBeenCalledWith('ocr_preprocess')
        expect(wrapper.find('.inline-record').exists()).toBe(true)
        expect(wrapper.find('.structured-summary-control').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('编辑内容')
        expect(wrapper.text()).not.toMatch(/字段\s*\d+/)
        expect(wrapper.get('[data-record-field-id="ocr_preprocess.field.grayscale"]').classes()).toContain('is-compact')
        expect(wrapper.find('[data-record-field-id="ocr_preprocess.field.threshold"]').exists()).toBe(false)

        await wrapper.setProps({ value: ocrValue(true) })
        await flushPromises()

        const threshold = wrapper.get('[data-record-field-id="ocr_preprocess.field.threshold"]')
        expect(threshold.classes()).not.toContain('is-compact')
        const slider = threshold.get('input[type="range"]')
        const number = threshold.get('input[type="number"]')
        expect(slider.attributes()).toMatchObject({ min: '0', max: '255' })
        expect(number.attributes()).toMatchObject({ min: '0', max: '255' })
    })

    it.each(['focused', 'row_list'] as const)('keeps %s values on a passive summary with an adjacent field action', (editorStrategy) => {
        const value: ProgramValueNode = editorStrategy === 'row_list'
            ? { value_id: 'value_rows', kind: 'list', value_type: 'list<string>', item_type: 'string', items: [literal('value_row', '第一项')] }
            : { value_id: 'value_json', kind: 'json', value_type: 'json_value', payload: { enabled: true } }
        const wrapper = mountParameter(parameter({
            value_type: value.value_type,
            ui: { control: editorStrategy === 'row_list' ? 'list' : 'json', editor_strategy: editorStrategy },
        }), value)

        const surface = wrapper.get<HTMLElement>('[data-control-surface]')
        const action = wrapper.get<HTMLButtonElement>('.app-field-action')
        expect(surface.element.tagName).toBe('DIV')
        expect(surface.find('button').exists()).toBe(false)
        expect(surface.element.contains(action.element)).toBe(false)
        expect(surface.element.parentElement).toBe(action.element.parentElement)
    })

    it('edits a condition completely in place without a duplicate modal action', () => {
        const condition: ProgramValueNode = {
            value_id: 'value_condition',
            kind: 'compare',
            value_type: 'bool',
            operator: 'gt',
            left: literal('value_left', 2, 'int64'),
            right: literal('value_right', 1, 'int64'),
        }
        const wrapper = mountParameter(parameter({
            parameter_id: 'condition',
            display_name: '判断条件',
            value_type: 'bool',
        }), condition)

        expect(wrapper.find('.structured-summary-control').exists()).toBe(false)
        expect(wrapper.get('.expression-surface').text()).toContain('2大于1')
        expect(wrapper.find('[data-parameter-action-id="open-condition-builder"]').exists()).toBe(false)
        expect(wrapper.emitted('openValueEditor')).toBeUndefined()
    })

    it('propagates disabled state to inputs, selects, toggles, expression surfaces, and field actions', () => {
        const input = mount(VNextValueControl, { props: { controlType: 'number', modelValue: 3, disabled: true } })
        const select = mount(VNextValueControl, { props: { controlType: 'select', modelValue: 'a', disabled: true, options: [{ label: 'A', value: 'a' }] } })
        const toggle = mount(VNextValueControl, { props: { controlType: 'toggle', modelValue: true, disabled: true } })
        expect(input.get<HTMLInputElement>('input').element.disabled).toBe(true)
        expect(select.get<HTMLSelectElement>('select').element.disabled).toBe(true)
        expect(toggle.get<HTMLInputElement>('input[type="checkbox"]').element.disabled).toBe(true)

        const action: ParameterUiAction = { id: 'capture-image', capture_kind: 'image' }
        const parameterWrapper = mountParameter(parameter({ ui: { control: 'expression', actions: [action] } }), literal('value_text', '内容'), { disabled: true })
        expect(parameterWrapper.get<HTMLButtonElement>('.expression-surface').element.disabled).toBe(true)
        expect(parameterWrapper.get<HTMLButtonElement>('.app-field-action').element.disabled).toBe(true)
    })

    it('does not keep a value-type annotation on the resting expression surface', () => {
        const wrapper = mountParameter(parameter({ display_name: '消息', value_type: 'string' }), literal('value_message', '欢迎回来'))

        expect(wrapper.get('.expression-surface').text()).toBe('欢迎回来')
        expect(wrapper.find('.app-control-adornment').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('文本')
    })

    it('keeps unimplemented author file pickers out of the inspector while preserving typed reference input', async () => {
        const wrapper = mountParameter(parameter({
            parameter_id: 'file',
            display_name: '文件',
            value_type: 'file_ref<read>',
            required: true,
            ui: {
                control: 'file',
                editor_strategy: 'reference',
                actions: [{ id: 'choose-file-read', platforms: ['windows'] }],
                placeholder: '输入 @ 选择已有文件',
            },
        }), { value_id: 'value_file', kind: 'unset', value_type: 'file_ref<read>' })

        expect(wrapper.find('[data-parameter-action-id="choose-file-read"]').exists()).toBe(false)
        expect(wrapper.get('.expression-surface').text()).toContain('输入 @ 选择已有文件')
        await wrapper.get('.expression-surface').trigger('click')
        expect(wrapper.get<HTMLInputElement>('.expression-editor').attributes('placeholder')).toBe('输入 @ 选择已有文件')
    })

    it('connects help and errors to the invalid control with aria-describedby', async () => {
        const wrapper = mountParameter(parameter({
            parameter_id: 'mode',
            display_name: '运行模式',
            value_type: 'enum<run_mode>',
            required: true,
            description: '选择本次运行采用的模式。',
            constraints: { choices: [{ label: '稳健', value: 'safe' }] },
            ui: { control: 'select' },
        }), { value_id: 'value_mode', kind: 'unset', value_type: 'enum<run_mode>' }, { diagnostics: ['当前模式不可用'] })

        const control = wrapper.get('select')
        expect(control.attributes('aria-invalid')).toBe('true')
        const initialIds = (control.attributes('aria-describedby') || '').split(' ').filter(Boolean)
        expect(initialIds).toHaveLength(1)
        expect(wrapper.get(`#${initialIds[0]}`).text()).toContain('当前模式不可用')

        await wrapper.get('.expression-help-trigger').trigger('click')
        const describedIds = (control.attributes('aria-describedby') || '').split(' ').filter(Boolean)
        expect(describedIds).toHaveLength(2)
        expect(describedIds.every((id) => wrapper.find(`#${id}`).exists())).toBe(true)
        expect(wrapper.get('.parameter-help').text()).toContain('选择本次运行采用的模式')
        expect(wrapper.get('.parameter-error').text()).toContain('请完成必填项')
    })

    it('hides saved-value diagnostics while the user is composing a replacement draft', async () => {
        const wrapper = mountParameter(
            parameter({ display_name: '判断条件', value_type: 'bool', required: true }),
            literal('value_condition', false, 'bool'),
            { diagnostics: ['旧值不符合条件要求'] },
        )

        expect(wrapper.get('.parameter-error').text()).toContain('旧值不符合条件要求')
        await wrapper.get('.expression-surface').trigger('click')
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        await editor.setValue('类型.')
        await editor.trigger('input')

        expect(wrapper.find('.parameter-error').exists()).toBe(false)
        expect(editor.attributes('aria-invalid')).toBeUndefined()
    })

    it('keeps every supported Control type on a rendered authoring surface', () => {
        const controls: ParameterControlType[] = [
            'text', 'number', 'toggle', 'select', 'slider-number', 'duration', 'time', 'color', 'coordinate', 'region',
            'resource', 'control-selector', 'gesture-path', 'file', 'directory', 'control-reference', 'instance',
            'target', 'application', 'instance-multi-select', 'key-chord', 'json', 'list', 'key-value', 'expression',
        ]

        for (const control of controls) {
            const valueType = control === 'expression' ? 'string' : `test_${control}`
            const value = literal(`value_${control}`, control === 'toggle' ? false : control === 'number' || control === 'slider-number' ? 1 : null, valueType)
            const wrapper = mountParameter(parameter({
                parameter_id: `parameter_${control}`,
                display_name: control,
                value_type: valueType,
                constraints: control === 'select' ? { choices: [{ label: '选项', value: 'option' }] } : {},
                ui: { control, editor_strategy: 'scalar' },
            }), value)

            expect(wrapper.find('.program-parameter').exists(), control).toBe(true)
            expect(wrapper.find('[data-control-surface], input, select, textarea').exists(), control).toBe(true)
            wrapper.unmount()
        }
    })
})
