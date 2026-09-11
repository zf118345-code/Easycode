import { describe, expect, it } from 'vitest'
import { expressionSegments, isInlineExpressionValueType, parseExpressionDraft, preserveExpressionValueIds } from '../expressionComposer'
import type { ProgramValueCatalogDto } from '../serverTypes'
import type { AvailableProgramValue } from '../types'

const values: AvailableProgramValue[] = [
    { source: 'local', id: 'symbol_stamina', display_name: '当前体力', value_type: 'int64' },
    { source: 'project', id: 'variable_minimum', display_name: '最低体力', value_type: 'int64' },
    { source: 'project', id: 'variable_ready', display_name: '队伍已准备', value_type: 'bool' },
    { source: 'project', id: 'variable_levels', display_name: '副本等级', value_type: 'list<int64>' },
    { source: 'local', id: 'symbol_click_point', display_name: '登录按钮中心', value_type: 'point' },
    { source: 'local', id: 'symbol_read_file', display_name: '账号文件', value_type: 'file_ref<read>' },
    { source: 'local', id: 'symbol_optional_match', display_name: '出战匹配', value_type: 'optional<image_match>' },
    { source: 'local', id: 'symbol_status', display_name: '状态文字', value_type: 'string' },
    { source: 'local', id: 'symbol_task_map', display_name: '任务配置', value_type: 'map<string,bool>' },
]

describe('inline expression field selection', () => {
    it('keeps stable image resources in the direct resource picker', () => {
        expect(isInlineExpressionValueType('asset_ref<image>')).toBe(false)
        expect(isInlineExpressionValueType('optional<asset_ref<image>>')).toBe(false)
        expect(isInlineExpressionValueType('string')).toBe(true)
    })
})

const intCatalog: ProgramValueCatalogDto = {
    schema_version: 1, registry_version: 1, registry_hash: 'test', revision: 'r', expected_type: 'int64',
    sources: [], members: [], record: null,
    operations: [{
        candidate_id: 'add-int', operation_id: 'core.number_add.v1', display_name: '相加', category: '数值',
        description: '把两个数相加', result_type: 'int64', inputs: [
            { input_id: 'core.number_add.v1.input.left', display_name: '左侧', value_type: 'int64', choices: [] },
            { input_id: 'core.number_add.v1.input.right', display_name: '右侧', value_type: 'int64', choices: [] },
        ],
    }],
}

const listCatalog: ProgramValueCatalogDto = {
    schema_version: 1, registry_version: 1, registry_hash: 'test', revision: 'r', expected_type: 'list<int64>',
    sources: [], members: [], record: null,
    operations: [{
        candidate_id: 'filter-list', operation_id: 'core.list_filter.v1', display_name: '筛选列表', category: '列表',
        syntax_name: '列表.筛选', description: '逐项判断', result_type: 'list<int64>', inputs: [
            { input_id: 'core.list_filter.v1.input.list', display_name: '列表', value_type: 'list<int64>', choices: [] },
            { input_id: 'core.list_filter.v1.input.predicate', display_name: '保留条件', value_type: 'list_selector<int64,bool>', choices: [] },
        ],
    }],
}

const imageValues: AvailableProgramValue[] = [
    { source: 'local', id: 'symbol_image_match', display_name: '图像测试', value_type: 'optional<image_match>' },
]

const imageTextCatalog: ProgramValueCatalogDto = {
    schema_version: 1, registry_version: 1, registry_hash: 'test', revision: 'r', expected_type: 'string',
    sources: [], record: null, operations: [],
    members: [{
        candidate_id: 'image-similarity', source: 'local', source_id: 'symbol_image_match',
        source_display_name: '图像测试', source_value_type: 'optional<image_match>', result_type: 'percentage',
        path: [{ field_id: 'image_match.field.similarity', display_name: '相似度', result_type: 'percentage' }],
    }],
}

describe('structured expression composer', () => {
    it('turns qualified variable text and arithmetic into stable typed nodes', () => {
        const result = parseExpressionDraft('[项目 · 最低体力] + 3', 'int64', 'value_root', values, [intCatalog])
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            value_id: 'value_root', kind: 'computed', operation_id: 'core.number_add.v1', operation_name: '数值.相加',
            operation_input_names: {
                'core.number_add.v1.input.left': '左侧',
                'core.number_add.v1.input.right': '右侧',
            },
            inputs: {
                'core.number_add.v1.input.left': { kind: 'project_variable_ref', variable_id: 'variable_minimum' },
                'core.number_add.v1.input.right': { kind: 'literal', value: 3 },
            },
        })
    })

    it('builds readable comparisons and logical groups without saving formula text', () => {
        const result = parseExpressionDraft(
            '[局部 · 当前体力] 大于等于 [项目 · 最低体力] 且 [项目 · 队伍已准备]',
            'bool', 'value_condition', values, [intCatalog],
        )
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({ kind: 'condition_group', operator: 'all' })
        if (!result.value) throw new Error('expected value')
        expect(JSON.stringify(result.value)).not.toContain('大于等于')
        expect(expressionSegments(result.value).map((item) => item.text).join(' ')).toContain('当前体力')
    })

    it('normalizes safe condition shorthand to explicit typed boolean trees', () => {
        expect(parseExpressionDraft('@出战匹配', 'bool', 'condition_optional', values).value).toMatchObject({
            value_id: 'condition_optional', kind: 'computed', value_type: 'bool', operation_id: 'core.optional_has_value.v1',
            inputs: { 'core.optional_has_value.v1.input.value': { kind: 'symbol_ref', symbol_id: 'symbol_optional_match' } },
        })
        expect(parseExpressionDraft('@当前体力', 'bool', 'condition_number', values).value).toMatchObject({
            value_id: 'condition_number', kind: 'compare', operator: 'ne', right: { kind: 'literal', value: 0 },
        })
        expect(parseExpressionDraft('@状态文字', 'bool', 'condition_text', values).value).toMatchObject({
            value_id: 'condition_text', kind: 'compare', operator: 'ne', right: { kind: 'literal', value: '' },
        })
        expect(parseExpressionDraft('@副本等级', 'bool', 'condition_list', values).value).toMatchObject({
            value_id: 'condition_list', kind: 'not', condition: { kind: 'computed', operation_id: 'core.list_is_empty.v1' },
        })
        expect(parseExpressionDraft('@任务配置', 'bool', 'condition_map', values).value).toMatchObject({
            value_id: 'condition_map', kind: 'not',
            condition: {
                kind: 'computed', operation_id: 'core.list_is_empty.v1',
                inputs: { 'core.list_is_empty.v1.input.list': { kind: 'computed', operation_id: 'core.map_keys.v1' } },
            },
        })
    })

    it('does not guess truthiness for coordinates or other reference objects', () => {
        const result = parseExpressionDraft('@登录按钮中心', 'bool', 'condition_point', values)
        expect(result.value).toBeNull()
        expect(result.error).toContain('没有默认的条件含义')
    })

    it.each([
        ['大于', 'gt'],
        ['小于', 'lt'],
        ['大于等于', 'gte'],
        ['小于等于', 'lte'],
        ['等于', 'eq'],
        ['不等于', 'ne'],
    ] as const)('accepts the Chinese comparison operator %s', (label, operator) => {
        const result = parseExpressionDraft(
            `[局部 · 当前体力] ${label} 0`,
            'bool', 'value_condition', values, [intCatalog],
        )
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({ kind: 'compare', operator })
    })

    it('does not silently bind an unknown or ambiguous reference', () => {
        const ambiguous = [...values, { source: 'local' as const, id: 'symbol_minimum', display_name: '最低体力', value_type: 'int64' }]
        const result = parseExpressionDraft('@最低体力', 'int64', 'value_root', ambiguous, [intCatalog])
        expect(result.value).toBeNull()
        expect(result.error).toContain('多个同名值')
    })

    it('preserves stable IDs for existing structural slots after an edit', () => {
        const before = parseExpressionDraft('[项目 · 最低体力] + 3', 'int64', 'value_root', values, [intCatalog]).value
        const after = parseExpressionDraft('[项目 · 最低体力] + 5', 'int64', 'temporary_root', values, [intCatalog]).value
        if (!before || !after || before.kind !== 'computed' || after.kind !== 'computed') throw new Error('expected computed values')
        before.inputs['core.number_add.v1.input.left'].value_id = 'stable_left'
        before.inputs['core.number_add.v1.input.right'].value_id = 'stable_right'

        const reconciled = preserveExpressionValueIds(before, after)

        expect(reconciled.value_id).toBe('value_root')
        expect(reconciled).toMatchObject({
            inputs: {
                'core.number_add.v1.input.left': { value_id: 'stable_left' },
                'core.number_add.v1.input.right': { value_id: 'stable_right', value: 5 },
            },
        })
    })

    it('parses duration and temporal literals without falling back to formula text', () => {
        expect(parseExpressionDraft('2 秒', 'duration', 'duration_value', values).value).toMatchObject({
            kind: 'literal', value_type: 'duration', value: 2_000,
        })
        expect(parseExpressionDraft('2026-09-02', 'date', 'date_value', values).value).toMatchObject({
            kind: 'literal', value_type: 'date', value: '2026-09-02',
        })
        expect(parseExpressionDraft('18:30', 'time', 'time_value', values).value).toMatchObject({
            kind: 'literal', value_type: 'time', value: '18:30',
        })
        expect(parseExpressionDraft('无结果', 'optional<string>', 'optional_value', values).value).toMatchObject({
            kind: 'literal', value_type: 'optional<string>', value: null,
        })
    })

    it('parses a hex color into the canonical RGBA record without saving display text', () => {
        const result = parseExpressionDraft('#616264', 'color', 'color_value', values)
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            value_id: 'color_value', kind: 'record', value_type: 'color', record_type: 'color',
            fields: {
                'color.field.red': { kind: 'literal', value: 97 },
                'color.field.green': { kind: 'literal', value: 98 },
                'color.field.blue': { kind: 'literal', value: 100 },
                'color.field.alpha': { kind: 'literal', value: 255 },
            },
        })
        expect(parseExpressionDraft('#61GG64', 'color', 'bad_color', values).error).toContain('#RRGGBB')
    })

    it('uses the same field for direct coordinates, regions, and compatible references', () => {
        expect(parseExpressionDraft('坐标(480, 320)', 'point', 'point_value', values).value).toMatchObject({
            value_id: 'point_value', kind: 'literal', value_type: 'point', value: [480, 320],
        })
        expect(parseExpressionDraft('区域(100, 80, 640, 360)', 'rect', 'rect_value', values).value).toMatchObject({
            value_id: 'rect_value', kind: 'literal', value_type: 'rect', value: [100, 80, 640, 360],
        })
        expect(parseExpressionDraft('@登录按钮中心', 'point', 'point_reference', values).value).toMatchObject({
            value_id: 'point_reference', kind: 'symbol_ref', symbol_id: 'symbol_click_point', value_type: 'point',
        })
        expect(parseExpressionDraft('@账号文件', 'file_ref<read>', 'file_reference', values).value).toMatchObject({
            value_id: 'file_reference', kind: 'symbol_ref', symbol_id: 'symbol_read_file', value_type: 'file_ref<read>',
        })
    })

    it('uses the same input for open text/value slots without mistaking ordinary punctuation for arithmetic', () => {
        expect(parseExpressionDraft('自动领取已开启', 'any', 'value_log', values).value).toMatchObject({
            value_id: 'value_log', kind: 'literal', value_type: 'string', value: '自动领取已开启',
        })
        expect(parseExpressionDraft('https://example.test/a+b', 'any', 'value_url', values).value).toMatchObject({
            kind: 'literal', value_type: 'string', value: 'https://example.test/a+b',
        })
        expect(parseExpressionDraft('[局部 · 当前体力]', 'message_value', 'value_message', values).value).toMatchObject({
            kind: 'symbol_ref', symbol_id: 'symbol_stamina', value_type: 'int64',
        })
        expect(parseExpressionDraft('[局部 · 当前体力] + 3', 'message_value', 'value_math', values, [intCatalog]).value).toMatchObject({
            kind: 'computed', value_type: 'int64', operation_id: 'core.number_add.v1',
        })
    })

    it('lowers mixed text and variables to typed operations instead of saving formula text', () => {
        const result = parseExpressionDraft(
            '当前体力为 [局部 · 当前体力]，最低要求 [项目 · 最低体力]',
            'string', 'value_log', values,
        )
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            value_id: 'value_log', kind: 'computed', value_type: 'string', operation_id: 'core.text_concat.v1',
        })
        expect(JSON.stringify(result.value)).not.toContain('当前体力为 [局部')
        expect(result.value && expressionSegments(result.value).map((item) => item.text).join('')).toBe(
            '当前体力为 局部 · 当前体力，最低要求 项目 · 最低体力',
        )
    })

    it('embeds a printable field from a structured image result in ordinary text', () => {
        const result = parseExpressionDraft(
            '图像相似度为 [局部 · 图像测试].相似度',
            'string', 'value_log', imageValues, [imageTextCatalog],
        )

        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            kind: 'computed', operation_id: 'core.text_concat.v1',
            inputs: {
                'core.text_concat.v1.input.right': {
                    kind: 'computed', operation_id: 'core.value_to_text.v1',
                    inputs: {
                        'core.value_to_text.v1.input.value': {
                            kind: 'member_access', field_id: 'image_match.field.similarity', value_type: 'percentage',
                        },
                    },
                },
            },
        })
    })

    it('explains that a structured image result needs a concrete field', () => {
        const result = parseExpressionDraft(
            '当前值为 [局部 · 图像测试]',
            'string', 'value_log', imageValues, [imageTextCatalog],
        )

        expect(result.value).toBeNull()
        expect(result.error).toContain('结构化结果')
        expect(result.error).toContain('请选择具体字段')
    })

    it('accepts a numeric variable with a duration unit', () => {
        const result = parseExpressionDraft('[局部 · 当前体力] 秒', 'duration', 'value_wait', values)
        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            value_id: 'value_wait', kind: 'computed', value_type: 'duration',
            operation_id: 'core.duration_from_seconds.v1',
            inputs: {
                'core.duration_from_seconds.v1.input.amount': {
                    kind: 'symbol_ref', symbol_id: 'symbol_stamina', value_type: 'int64',
                },
            },
        })
    })

    it('parses a collection selector from the same formula syntax and keeps it typed', () => {
        const result = parseExpressionDraft(
            '列表.筛选(@副本等级, 每项 => @当前项 >= 15)',
            'list<int64>', 'value_filtered', values, [listCatalog],
        )

        expect(result.error).toBe('')
        expect(result.value).toMatchObject({
            value_id: 'value_filtered', kind: 'computed', operation_id: 'core.list_filter.v1',
            inputs: {
                'core.list_filter.v1.input.list': { kind: 'project_variable_ref', variable_id: 'variable_levels' },
                'core.list_filter.v1.input.predicate': {
                    kind: 'selector', result_type: 'bool',
                    expression: { kind: 'compare', operator: 'gte' },
                },
            },
        })
        expect(result.value && expressionSegments(result.value).map((item) => item.text).join(' ')).toContain('每项 =>')
        expect(JSON.stringify(result.value)).not.toContain('每项 =>')
    })

    it('preserves selector bindings and remaps their references when editing the formula', () => {
        const before = parseExpressionDraft(
            '列表.筛选(@副本等级, 每项 => @当前项 >= 15)',
            'list<int64>', 'value_filtered', values, [listCatalog],
        ).value
        const after = parseExpressionDraft(
            '列表.筛选(@副本等级, 每项 => @当前项 >= 20)',
            'list<int64>', 'temporary_root', values, [listCatalog],
        ).value
        if (before?.kind !== 'computed' || after?.kind !== 'computed') throw new Error('expected computed list')
        const beforeSelector = before.inputs['core.list_filter.v1.input.predicate']
        if (beforeSelector?.kind !== 'selector') throw new Error('expected selector')
        beforeSelector.bindings[0]!.symbol_id = 'stable_item'

        const reconciled = preserveExpressionValueIds(before, after)
        if (reconciled.kind !== 'computed') throw new Error('expected reconciled operation')
        const selector = reconciled.inputs['core.list_filter.v1.input.predicate']
        if (selector?.kind !== 'selector' || selector.expression.kind !== 'compare') throw new Error('expected reconciled selector')
        expect(selector.bindings[0]?.symbol_id).toBe('stable_item')
        expect(selector.expression.left).toMatchObject({ kind: 'symbol_ref', symbol_id: 'stable_item' })
        expect(selector.expression.right).toMatchObject({ value: 20 })
    })
})
