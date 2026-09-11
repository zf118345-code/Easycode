import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramExpressionInput from '../ProgramExpressionInput.vue'
import type { ProgramValueCatalogDto } from '../serverTypes'

const intCatalog: ProgramValueCatalogDto = {
    schema_version: 1, registry_version: 4, registry_hash: 'sha256:test', revision: 'r', expected_type: 'int64',
    sources: [], members: [], record: null,
    operations: [{
        candidate_id: 'add', operation_id: 'core.number_add.v1', display_name: '相加', category: '数值',
        syntax_name: '数值.相加', description: '把两个数相加', result_type: 'int64', inputs: [
            { input_id: 'core.number_add.v1.input.left', display_name: '左侧', value_type: 'int64', choices: [] },
            { input_id: 'core.number_add.v1.input.right', display_name: '右侧', value_type: 'int64', choices: [] },
        ],
    }],
}
const boolCatalog: ProgramValueCatalogDto = {
    ...intCatalog, expected_type: 'bool', operations: [],
}
const discoveryIntCatalog: ProgramValueCatalogDto = {
    ...intCatalog,
    schema_version: 2,
    discovery: {
        namespaces: [
            { name: '文本', description: '组合、整理、查找和提取文字', keywords: ['字符串'], operation_count: 1, compatible_count: 0 },
            { name: '数值', description: '计算、取整、转换和限制数字', keywords: ['数字'], operation_count: 1, compatible_count: 1 },
        ],
        operations: [
            {
                operation_id: 'core.number_add.v1', display_name: '相加', namespace: '数值', group: '计算与变换',
                description: '把两个数相加', syntax_name: '数值.相加', aliases: ['加法'], keywords: ['合计'],
                input_labels: ['左侧', '右侧'], example: '数值.相加(1, 2)', result_type_hints: ['int64'], compatible: true, disabled_reason: '',
            },
            {
                operation_id: 'core.text_replace.v1', display_name: '替换文本', namespace: '文本', group: '修改副本',
                description: '替换文本中的指定内容', syntax_name: '文本.替换', aliases: ['替换'], keywords: ['字符串'],
                input_labels: ['文本', '查找内容', '替换为'], example: '文本.替换("旧", "旧", "新")', result_type_hints: ['string'], compatible: false,
                disabled_reason: '这个操作的结果类型不能填入当前字段',
            },
        ],
        literals: [{ label: '整数', insert_text: '0', description: '直接输入整数，例如 18 或 -3' }],
        operators: [{ label: '相加', insert_text: ' + ', description: '在当前数值后相加' }],
        triggers: [{ keys: 'Ctrl+Space', description: '打开当前字段的全部可用写法' }],
    },
}
const boolConversionCatalog: ProgramValueCatalogDto = {
    ...boolCatalog,
    schema_version: 2,
    discovery: {
        namespaces: [
            { name: '类型', description: '在明确且安全的类型之间转换', keywords: ['转换'], operation_count: 1, compatible_count: 0 },
        ],
        operations: [{
            operation_id: 'core.text_to_int.v1', display_name: '文本转整数', namespace: '类型', group: '类型转换',
            description: '严格解析整数；无法解析时返回无结果', syntax_name: '类型.文本转整数', aliases: ['转整数'], keywords: ['解析'],
            input_labels: ['文本'], example: '类型.文本转整数("3")', result_type_hints: ['optional<int64>'], compatible: false,
            disabled_reason: '这个操作的结果类型不能填入当前字段',
        }],
        literals: [], operators: [], triggers: [],
    },
}
const optionalIntCatalog: ProgramValueCatalogDto = {
    ...intCatalog,
    expected_type: 'optional<int64>',
    operations: [{
        candidate_id: 'text-to-int', operation_id: 'core.text_to_int.v1', display_name: '文本转整数', category: '类型',
        syntax_name: '类型.文本转整数', description: '严格解析整数；无法解析时返回无结果', result_type: 'optional<int64>',
        inputs: [{ input_id: 'core.text_to_int.v1.input.text', display_name: '文本', value_type: 'string', choices: [] }],
    }],
}

const imageTextCatalog: ProgramValueCatalogDto = {
    ...intCatalog,
    expected_type: 'string',
    operations: [],
    sources: [{
        source: 'local', source_id: 'symbol_image_match', display_name: '图像测试',
        value_type: 'optional<image_match>', narrowed_type: 'image_match',
    }],
    members: [{
        candidate_id: 'image-similarity', source: 'local', source_id: 'symbol_image_match',
        source_display_name: '图像测试', source_value_type: 'optional<image_match>', result_type: 'percentage',
        path: [{ field_id: 'image_match.field.similarity', display_name: '相似度', result_type: 'percentage' }],
    }],
}
const imageRecordCatalog: ProgramValueCatalogDto = {
    ...intCatalog,
    expected_type: 'image_match',
    operations: [], members: [], sources: imageTextCatalog.sources,
    record: {
        type_id: 'image_match', display_name: '图像匹配结果',
        fields: [
            { field_id: 'image_match.field.region', display_name: '匹配区域', value_type: 'rect', description: '', choices: [] },
            { field_id: 'image_match.field.center', display_name: '中心', value_type: 'point', description: '', choices: [] },
            { field_id: 'image_match.field.similarity', display_name: '相似度', value_type: 'percentage', description: '', choices: [] },
        ],
    },
}
const ocrTextCatalog: ProgramValueCatalogDto = {
    ...intCatalog,
    expected_type: 'string', operations: [],
    sources: [{ source: 'local', source_id: 'symbol_ocr', display_name: '识字结果', value_type: 'ocr_result', narrowed_type: '' }],
    members: [
        {
            candidate_id: 'ocr-text', source: 'local', source_id: 'symbol_ocr', source_display_name: '识字结果',
            source_value_type: 'ocr_result', result_type: 'string',
            path: [{ field_id: 'ocr_result.field.text', display_name: '全文', result_type: 'string' }],
        },
        {
            candidate_id: 'ocr-frame-width', source: 'local', source_id: 'symbol_ocr', source_display_name: '识字结果',
            source_value_type: 'ocr_result', result_type: 'int64',
            path: [
                { field_id: 'ocr_result.field.source_frame', display_name: '来源画面', result_type: 'frame_ref' },
                { field_id: 'frame_ref.field.width', display_name: '宽度', result_type: 'int64' },
            ],
        },
    ],
}
const ocrRecordCatalog: ProgramValueCatalogDto = {
    ...intCatalog, expected_type: 'ocr_result', operations: [], members: [], sources: ocrTextCatalog.sources,
    record: {
        type_id: 'ocr_result', display_name: '文字识别结果', fields: [
            { field_id: 'ocr_result.field.text', display_name: '全文', value_type: 'string', description: '', choices: [] },
            { field_id: 'ocr_result.field.source_frame', display_name: '来源画面', value_type: 'frame_ref', description: '', choices: [] },
        ],
    },
}
const frameRecordCatalog: ProgramValueCatalogDto = {
    ...intCatalog, expected_type: 'frame_ref', operations: [], members: [], sources: ocrTextCatalog.sources,
    record: {
        type_id: 'frame_ref', display_name: '画面引用', fields: [
            { field_id: 'frame_ref.field.width', display_name: '宽度', value_type: 'int64', description: '', choices: [] },
            { field_id: 'frame_ref.field.height', display_name: '高度', value_type: 'int64', description: '', choices: [] },
        ],
    },
}

describe('ProgramExpressionInput', () => {
    it('shows examples that match a duration field instead of generic text operations', () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '超时', expectedType: 'duration', helpOpen: true,
                value: { value_id: 'value_timeout', kind: 'literal', value_type: 'duration', value: 10_000 },
            },
        })

        const help = wrapper.get('.expression-help').text()
        expect(help).toContain('500 毫秒')
        expect(help).toContain('2 秒')
        expect(help).not.toContain('公告内容')
    })

    it('keeps one stable input surface and uses keyboard commit/cancel without action buttons', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => intCatalog,
            },
        })

        expect(wrapper.get('.expression-surface').text()).toContain('18')
        await wrapper.get('.expression-surface').trigger('click')
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        expect(wrapper.find('.expression-tools').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('取消')
        expect(wrapper.text()).not.toContain('确定')
        expect(wrapper.text()).not.toContain('更多操作')

        await editor.setValue('20')
        await editor.trigger('keydown.esc')
        expect(wrapper.emitted('replace')).toBeUndefined()
        expect(wrapper.get('.expression-surface').text()).toContain('18')

        await wrapper.get('.expression-surface').trigger('click')
        await wrapper.get('.expression-editor').setValue('20')
        await wrapper.get('.expression-editor').trigger('keydown.enter')
        await flushPromises()
        expect(wrapper.emitted('replace')?.[0]?.[0]).toMatchObject({
            value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 20,
        })
    })

    it('edits an effective default as an empty field so the format placeholder remains visible', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '时区', expectedType: 'optional<timezone>',
                placeholder: '例如：GMT+8；留空使用设备时区',
                effectiveDefaultLabel: '当前设备时区（如 Asia/Shanghai）',
                value: { value_id: 'value_timezone', kind: 'literal', value_type: 'optional<timezone>', value: null },
            },
        })

        expect(wrapper.get('.expression-default').text()).toBe('当前设备时区（如 Asia/Shanghai）')
        expect(wrapper.get('.expression-surface').attributes('aria-label')).toBe('时区：当前设备时区（如 Asia/Shanghai）')
        await wrapper.get('.expression-surface').trigger('click')
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        expect(editor.element.value).toBe('')
        expect(editor.attributes('placeholder')).toContain('GMT+8')
    })

    it('commits an emptied optional reference as the effective automatic default', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '使用画面', expectedType: 'optional<frame_ref>',
                effectiveDefaultLabel: '自动获取最新画面',
                value: {
                    value_id: 'value_frame', kind: 'symbol_ref', value_type: 'optional<frame_ref>',
                    symbol_id: 'symbol_old_frame', display_name: '旧画面',
                },
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('')
        await editor.trigger('keydown.enter')

        expect(wrapper.emitted('replace')?.[0]?.[0]).toEqual({
            value_id: 'value_frame', kind: 'literal', value_type: 'optional<frame_ref>', value: null,
        })
        expect(wrapper.find('.expression-error').exists()).toBe(false)
    })

    it('offers contextual operation completion and commits a typed operation tree', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => intCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('数值.')
        await editor.trigger('input')
        expect(wrapper.get('.operation-suggestion').text()).toContain('数值.相加')
        await wrapper.get('.operation-suggestion').trigger('click')
        expect((editor.element as HTMLInputElement).value).toBe('数值.相加()')

        await editor.setValue('数值.相加(18, 3)')
        await editor.trigger('keydown.enter')
        await flushPromises()
        expect(wrapper.emitted('replace')?.[0]?.[0]).toMatchObject({
            value_id: 'value_level', kind: 'computed', operation_id: 'core.number_add.v1',
        })
    })

    it('opens the registry discovery directory with Ctrl+Space and explains incompatible syntax', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => discoveryIntCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.trigger('keydown', { key: ' ', code: 'Space', ctrlKey: true })
        await flushPromises()

        expect(wrapper.get('.value-suggestions').text()).toContain('整数可用写法')
        expect(wrapper.get('.value-suggestions').text()).toContain('@ 变量或结果')
        expect(wrapper.get('.value-suggestions').text()).toContain('文本.')
        expect(wrapper.get('.value-suggestions').text()).toContain('数值.')

        const textNamespace = wrapper.findAll('.namespace-suggestion').find((item) => item.text().includes('文本.'))
        await textNamespace?.trigger('click')
        await flushPromises()
        expect((editor.element as HTMLInputElement).value).toBe('文本.')
        const incompatible = wrapper.get<HTMLButtonElement>('.operation-suggestion')
        expect(incompatible.element.disabled).toBe(true)
        expect(incompatible.text()).toContain('不能填入当前字段')
        expect(incompatible.text()).toContain('文本')
    })

    it('lets a boolean condition insert a typed intermediate result before the comparison is complete', async () => {
        const requested: string[] = []
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '判断条件', expectedType: 'bool',
                value: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
                availableValues: [{ source: 'local', id: 'symbol_count_text', display_name: '次数文本', value_type: 'string' }],
                resolveCatalog: async (type: string) => {
                    requested.push(type)
                    if (type === 'optional<int64>') return optionalIntCatalog
                    return boolConversionCatalog
                },
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        await editor.setValue('类型.')
        await editor.trigger('input')

        const conversion = wrapper.get<HTMLButtonElement>('.operation-suggestion')
        expect(conversion.element.disabled).toBe(false)
        expect(conversion.text()).toContain('再继续比较')
        expect(wrapper.find('.expression-error').exists()).toBe(false)

        await conversion.trigger('click')
        await flushPromises()
        expect(requested).toContain('optional<int64>')
        expect(editor.element.value).toBe('类型.文本转整数()')

        await editor.setValue('类型.文本转整数([局部 · 次数文本]) == 3')
        await editor.trigger('keydown.enter')
        await flushPromises()
        expect(wrapper.emitted('replace')?.[0]?.[0]).toMatchObject({
            kind: 'compare', operator: 'eq',
            left: { kind: 'computed', operation_id: 'core.text_to_int.v1', value_type: 'optional<int64>' },
            right: { kind: 'literal', value: 3, value_type: 'optional<int64>' },
        })
    })

    it('commits a text-to-integer comparison fed by an OCR result member', async () => {
        const ocrWinTextCatalog: ProgramValueCatalogDto = {
            ...ocrTextCatalog,
            sources: [{ source: 'local', source_id: 'symbol_wins', display_name: '获胜次数', value_type: 'ocr_result', narrowed_type: '' }],
            members: ocrTextCatalog.members.map((member) => ({
                ...member,
                source_id: 'symbol_wins',
                source_display_name: '获胜次数',
            })),
        }
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '判断条件', expectedType: 'bool',
                value: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
                availableValues: [{ source: 'local', id: 'symbol_wins', display_name: '获胜次数', value_type: 'ocr_result' }],
                resolveCatalog: async (type: string) => {
                    if (type === 'optional<int64>') return optionalIntCatalog
                    if (type === 'string') return ocrWinTextCatalog
                    if (type === 'ocr_result') return ocrRecordCatalog
                    return boolConversionCatalog
                },
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        await editor.setValue('类型.文本转整数([局部 · 获胜次数].全文)==3')
        await editor.trigger('keydown.enter')
        await flushPromises()

        expect(wrapper.find('.expression-error').exists()).toBe(false)
        expect(wrapper.emitted('replace')?.[0]?.[0]).toMatchObject({
            kind: 'compare', operator: 'eq',
            left: {
                kind: 'computed', operation_id: 'core.text_to_int.v1',
                inputs: {
                    'core.text_to_int.v1.input.text': {
                        kind: 'member_access', field_id: 'ocr_result.field.text',
                        source: { kind: 'symbol_ref', symbol_id: 'symbol_wins', value_type: 'ocr_result' },
                    },
                },
            },
            right: { kind: 'literal', value: 3, value_type: 'optional<int64>' },
        })
    })

    it('discovers namespaces by familiar words and offers operators after a complete value', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => discoveryIntCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')

        await editor.setValue('数字')
        await editor.trigger('input')
        expect(wrapper.get('.namespace-suggestion').text()).toContain('数值.')

        await editor.setValue('18')
        editor.element.setSelectionRange(2, 2)
        await editor.trigger('keyup')
        expect(wrapper.get('.suggestion-heading').text()).toContain('继续计算或判断')
        expect(wrapper.get('.discovery-suggestion').text()).toContain('相加')
    })

    it('shows the active operation parameter and its legal literals inside the same input', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => discoveryIntCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('数值.相加(')
        await editor.trigger('input')
        await flushPromises()

        expect(wrapper.get('.suggestion-heading').text()).toContain('数值.相加 · 左侧')
        const zero = wrapper.findAll('.discovery-suggestion').find((item) => item.text().includes('整数'))
        expect(zero?.text()).toContain('0')
        await zero?.trigger('click')
        expect((editor.element as HTMLInputElement).value).toBe('数值.相加(0')
    })

    it('keeps invalid text in the editor with a local explanation instead of overwriting the value', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => intCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await wrapper.get('.expression-editor').setValue('十八岁')
        await wrapper.get('.expression-editor').trigger('keydown.enter')
        await flushPromises()

        expect(wrapper.find('.expression-editor').exists()).toBe(true)
        expect(wrapper.get('[role="alert"]').text()).toContain('需要整数')
        expect(wrapper.emitted('replace')).toBeUndefined()
    })

    it('loads only the current value catalog when editing begins', async () => {
        let calls = 0
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => { calls += 1; return intCatalog },
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        expect(calls).toBe(1)
    })

    it('shows only value roots for @ and reveals fields after the selected value plus dot', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '内容', expectedType: 'string',
                value: { value_id: 'value_log', kind: 'literal', value_type: 'string', value: '' },
                availableValues: [{
                    source: 'local', id: 'symbol_image_match', display_name: '图像测试', value_type: 'optional<image_match>',
                }],
                resolveCatalog: async (type: string) => type === 'image_match' ? imageRecordCatalog : imageTextCatalog,
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('相似度为 @图像测试')
        await editor.trigger('input')

        expect(wrapper.get('.suggestion-heading').text()).toContain('选择已有值')
        expect(wrapper.find('.member-suggestion').exists()).toBe(false)
        await wrapper.get('.value-suggestion').trigger('click')
        expect((editor.element as HTMLInputElement).value).toBe('相似度为 [局部 · 图像测试]')

        await editor.setValue('相似度为 [局部 · 图像测试].')
        await editor.trigger('input')
        await flushPromises()
        expect(wrapper.get('.suggestion-heading').text()).toContain('图像测试的字段')
        expect(wrapper.findAll('.member-suggestion').map((item) => item.text())).toEqual([
            '字段匹配区域区域', '字段中心坐标', '字段相似度百分比',
        ])
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[0].element.disabled).toBe(true)
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[1].element.disabled).toBe(true)
        await wrapper.findAll('.member-suggestion')[2].trigger('click')
        expect((editor.element as HTMLInputElement).value).toBe('相似度为 [局部 · 图像测试].相似度')
    })

    it('allows strict optional member access and explains its fail-fast semantics', async () => {
        const optionalCatalog: ProgramValueCatalogDto = {
            ...imageTextCatalog,
            members: imageTextCatalog.members,
            sources: imageTextCatalog.sources.map((source) => ({ ...source, narrowed_type: '' })),
        }
        const optionalRecord = { ...imageRecordCatalog, sources: optionalCatalog.sources }
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '内容', expectedType: 'string',
                value: { value_id: 'value_log_optional', kind: 'literal', value_type: 'string', value: '' },
                availableValues: [{
                    source: 'local', id: 'symbol_image_match', display_name: '图像测试', value_type: 'optional<image_match>',
                }],
                resolveCatalog: async (type: string) => type === 'image_match' ? optionalRecord : optionalCatalog,
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('[局部 · 图像测试].')
        await editor.trigger('input')
        await flushPromises()

        expect(wrapper.get('.member-guard-note').text()).toContain('本次运行会停在使用它的语句')
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')).toHaveLength(3)
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[0].element.disabled).toBe(true)
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[1].element.disabled).toBe(true)
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[2].element.disabled).toBe(false)

        await editor.setValue('[局部 · 图像测试].相似度')
        await editor.trigger('keydown.enter')
        await flushPromises()
        expect(wrapper.find('[role="alert"]').exists()).toBe(false)
        expect(wrapper.emitted('replace')).toHaveLength(1)
    })

    it('keeps an incomplete draft neutral until explicit commit and ignores IME Enter', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '判断条件', expectedType: 'bool', invalid: true,
                value: { value_id: 'value_condition_draft', kind: 'literal', value_type: 'bool', value: false },
                resolveCatalog: async () => boolConversionCatalog,
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        expect(wrapper.classes()).not.toContain('has-error')
        expect(editor.attributes('aria-invalid')).toBeUndefined()

        await editor.setValue('类型.')
        await editor.trigger('input')
        expect(wrapper.find('[role="alert"]').exists()).toBe(false)
        expect(wrapper.classes()).not.toContain('has-error')

        await editor.trigger('compositionstart')
        await editor.trigger('keydown', { key: 'Enter', isComposing: true })
        expect(wrapper.emitted('replace')).toBeUndefined()
        expect(wrapper.find('.expression-editor').exists()).toBe(true)
        await editor.trigger('compositionend')

        await editor.trigger('keydown', { key: 'Enter' })
        await flushPromises()
        expect(wrapper.get('[role="alert"]').text()).toBeTruthy()
        expect(editor.element.value).toBe('类型.')
    })

    it('navigates nested records one level at a time instead of flattening their paths', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '内容', expectedType: 'string',
                value: { value_id: 'value_log_ocr', kind: 'literal', value_type: 'string', value: '' },
                availableValues: [{ source: 'local', id: 'symbol_ocr', display_name: '识字结果', value_type: 'ocr_result' }],
                resolveCatalog: async (type: string) => {
                    if (type === 'ocr_result') return ocrRecordCatalog
                    if (type === 'frame_ref') return frameRecordCatalog
                    return ocrTextCatalog
                },
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get('.expression-editor')
        await editor.setValue('[局部 · 识字结果].')
        await editor.trigger('input')
        await flushPromises()
        const firstLevel = wrapper.findAll('.member-suggestion')
        expect(firstLevel.map((item) => item.text())).toEqual([
            '字段全文文本', '字段来源画面画面 · 可继续选择',
        ])

        await firstLevel[1].trigger('click')
        await flushPromises()
        expect((editor.element as HTMLInputElement).value).toBe('[局部 · 识字结果].来源画面.')
        expect(wrapper.findAll('.member-suggestion').map((item) => item.text())).toEqual([
            '字段宽度整数', '字段高度整数',
        ])
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[0].element.disabled).toBe(false)
        expect(wrapper.findAll<HTMLButtonElement>('.member-suggestion')[1].element.disabled).toBe(true)
    })

    it('loads the inferred numeric catalog only when a pasted condition needs arithmetic', async () => {
        const requested: string[] = []
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '判断条件', expectedType: 'bool',
                value: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
                resolveCatalog: async (type: string) => {
                    requested.push(type)
                    return type === 'bool' ? boolCatalog : intCatalog
                },
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        expect(requested).toEqual(['bool'])
        await wrapper.get('.expression-editor').setValue('1 + 2 > 2')
        await wrapper.get('.expression-editor').trigger('keydown.enter')
        await flushPromises()

        expect(requested).toEqual(['bool', 'int64'])
        expect(wrapper.emitted('replace')?.[0]?.[0]).toMatchObject({
            value_id: 'value_condition', kind: 'compare', operator: 'gt',
            left: { kind: 'computed', operation_id: 'core.number_add.v1' },
        })
    })

    it('supports keyboard traversal and selection in operation completion', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            attachTo: document.body,
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => intCatalog,
            },
        })
        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        const editor = wrapper.get<HTMLInputElement>('.expression-editor')
        await editor.setValue('数值.')
        await editor.trigger('input')
        await editor.trigger('keydown', { key: 'ArrowDown' })
        await wrapper.vm.$nextTick()
        expect(document.activeElement).toBe(wrapper.get('.operation-suggestion').element)

        await wrapper.get('.operation-suggestion').trigger('keydown', { key: 'Escape' })
        expect(document.activeElement).toBe(editor.element)
        expect(wrapper.find('.operation-suggestion').exists()).toBe(false)

        await editor.trigger('input')
        await editor.trigger('keydown', { key: 'ArrowDown' })
        await wrapper.get('.operation-suggestion').trigger('click')
        expect(editor.element.value).toBe('数值.相加()')
        wrapper.unmount()
    })

    it('never carries an uncommitted draft into a different stable value slot', async () => {
        const wrapper = mount(ProgramExpressionInput, {
            props: {
                label: '当前等级', expectedType: 'int64',
                value: { value_id: 'value_a', kind: 'literal', value_type: 'int64', value: 18 },
                resolveCatalog: async () => intCatalog,
            },
        })

        await wrapper.get('.expression-surface').trigger('click')
        await flushPromises()
        await wrapper.get<HTMLInputElement>('.expression-editor').setValue('999')
        await wrapper.setProps({
            value: { value_id: 'value_b', kind: 'literal', value_type: 'int64', value: 20 },
        })
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.expression-editor').exists()).toBe(false)
        expect(wrapper.get('.expression-surface').text()).toContain('20')
        expect(wrapper.get('.expression-surface').text()).not.toContain('999')
    })
})
