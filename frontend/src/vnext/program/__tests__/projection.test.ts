import { describe, expect, it } from 'vitest'
import { availableValuesAtInsertion, availableValuesAtStatement, conditionSummary, projectStatements, statementSummary, valueSummary, visibleStatementRows } from '../projection'
import type { ProgramDocument, ProgramStatement, ProgramValueNode } from '../types'

function literal(valueId: string, value: string | number | boolean | null, valueType = 'string'): ProgramValueNode {
    return { value_id: valueId, value_type: valueType, kind: 'literal', value }
}
function call(statementId: string, displayName: string): ProgramStatement {
    return { statement_id: statementId, kind: 'call', function_id: `builtin.${statementId}`, display_name: displayName, arguments: {} }
}

describe('ProgramDocument projection', () => {
    it('projects every format-6 statement kind without exposing internal identifiers', () => {
        const statements: ProgramStatement[] = [
            call('stmt_call', '等待 2 秒'),
            {
                statement_id: 'stmt_assignment', kind: 'assignment',
                target: { kind: 'local', symbol_id: 'symbol_count', display_name: '重试次数', value_type: 'int64', declare: true },
                value: literal('value_count', 2, 'int64'),
            },
            {
                statement_id: 'stmt_if', kind: 'if', condition: literal('value_condition', true, 'bool'),
                then_body: [call('stmt_then', '输出日志「成功」')],
                additional_branches: [{ branch_id: 'branch_retry', condition: literal('value_retry', false, 'bool'), statements: [] }],
                else_body: [{ statement_id: 'stmt_else_return', kind: 'return', value: literal('value_return', '失败') }],
            },
            {
                statement_id: 'stmt_loop', kind: 'loop', mode: 'for_each',
                source: { value_id: 'value_list', value_type: 'list<string>', kind: 'list', item_type: 'string', items: [literal('value_a', '副本一'), literal('value_b', '副本二')] },
                item_binding: { symbol_id: 'symbol_item', display_name: '当前副本', value_type: 'string' }, body: [call('stmt_loop_call', '执行当前副本')],
            },
            {
                statement_id: 'stmt_try', kind: 'try', body: [call('stmt_try_body', '发送请求')],
                catches: [{ catch_id: 'catch_network', error_ids: ['网络错误'], error_binding: null, statements: [call('stmt_catch', '记录失败')] }],
                finally_body: [call('stmt_finally', '释放资源')],
                retry_policy: {
                    max_retries: literal('value_retries', 2, 'int64'),
                    interval: { value_id: 'value_interval', value_type: 'duration', kind: 'literal', value: { milliseconds: 500 } },
                    transient_only: true,
                },
            },
            {
                statement_id: 'stmt_target', kind: 'target_scope',
                target: { value_id: 'value_target', value_type: 'target_ref', kind: 'target_ref', target_id: 'target_adb', display_name: '雷电模拟器' },
                body: [call('stmt_target_body', '点击屏幕')],
            },
            {
                statement_id: 'stmt_listen', kind: 'listen',
                event_source: { kind: 'message', name: literal('value_source', '组队邀请'), sender: null },
                receive_binding: { symbol_id: 'symbol_message', display_name: '邀请消息', value_type: 'message' },
                condition: literal('value_listen_condition', true, 'bool'),
                handler_function_id: 'function_join', handler_display_name: '加入房间', handler_arguments: {},
            },
        ]

        const rows = projectStatements(statements)
        const summaries = visibleStatementRows(rows).map((row) => row.summary)

        expect(summaries).toContain('等待 2 秒')
        expect(summaries).toContain('设置重试次数为 2')
        expect(summaries).toContain('如果 始终满足')
        expect(summaries).toContain('逐项处理 列表 · 2 项 → 当前副本')
        expect(summaries).toContain('尝试（失败后重试 2 次，每隔 500 毫秒）')
        expect(summaries).toContain('在雷电模拟器中执行')
        expect(summaries).toContain('收到组队邀请时，加入房间')
        expect(rows.filter((row) => row.row_kind === 'branch').map((row) => row.label)).toEqual([
            '那么', '否则如果 永不满足', '否则', '网络错误时', '最后',
        ])
        expect(rows.find((row) => row.key === 'branch_retry')).toMatchObject({ row_kind: 'branch', empty: true })
        expect(summaries.join(' ')).not.toContain('stmt_')
        expect(summaries.join(' ')).not.toContain('value_')
    })

    it('collapses all child blocks without changing the owner statement', () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if', condition: literal('value_condition', true, 'bool'),
            then_body: [call('stmt_child', '子语句')], additional_branches: [], else_body: [],
        }
        const rows = projectStatements([conditional], new Set(['stmt_if']))
        expect(visibleStatementRows(rows).map((row) => row.statement.statement_id)).toEqual(['stmt_if'])
        expect(statementSummary(conditional)).toBe('如果 始终满足')
    })

    it('presents an empty else as an optional action instead of an existing branch', () => {
        const conditional: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if', condition: literal('value_condition', true, 'bool'),
            then_body: [], additional_branches: [], else_body: [],
        }
        const branches = projectStatements([conditional]).filter((row) => row.row_kind === 'branch')
        expect(branches).toMatchObject([
            { block: 'then', label: '那么', action: false, empty: true },
            { block: 'otherwise', label: '添加“否则”分支', action: true, empty: false },
        ])
    })

    it('summarizes recursive values without dumping storage JSON', () => {
        const condition: ProgramValueNode = {
            value_id: 'value_all', value_type: 'bool', kind: 'condition_group', operator: 'all',
            conditions: [{
                value_id: 'value_compare', value_type: 'bool', kind: 'compare', operator: 'gte',
                left: literal('value_level', 15, 'int64'), right: literal('value_required', 10, 'int64'),
            }],
        }
        expect(valueSummary(condition)).toBe('同时满足 1 个条件')
        expect(conditionSummary(literal('value_true', true, 'bool'))).toBe('始终满足')
        expect(conditionSummary(literal('value_false', false, 'bool'))).toBe('永不满足')
        expect(valueSummary({ value_id: 'value_unset', value_type: 'asset_ref<image>', kind: 'unset' })).toBe('待配置')
    })

    it('projects application and control records as user-facing semantic values', () => {
        expect(valueSummary({
            value_id: 'value_app', value_type: 'application_ref', kind: 'record', record_type: 'application_ref',
            fields: {
                'application_ref.field.platform': literal('value_platform', 'android_adb'),
                'application_ref.field.package': literal('value_package', 'com.android.settings'),
                'application_ref.field.activity': literal('value_activity', '.Settings'),
            },
        })).toBe('Android 应用「com.android.settings/.Settings」')
        expect(valueSummary({
            value_id: 'value_control', value_type: 'control_selector', kind: 'record', record_type: 'control_selector',
            fields: { 'control_selector.field.name': literal('value_name', '确认按钮') },
        })).toBe('控件「确认按钮」')
    })

    it('projects visual values as short workflow language', () => {
        expect(valueSummary({
            value_id: 'value_color', value_type: 'color', kind: 'record', record_type: 'color',
            fields: {
                'color.field.red': literal('value_red', 32, 'int64'),
                'color.field.green': literal('value_green', 96, 'int64'),
                'color.field.blue': literal('value_blue', 160, 'int64'),
            },
        })).toBe('RGB (32, 96, 160)')
        expect(valueSummary({
            value_id: 'value_size', value_type: 'size', kind: 'record', record_type: 'size',
            fields: {
                width: literal('value_width', 1280, 'int64'),
                height: literal('value_height', 720, 'int64'),
            },
        })).toBe('尺寸 1280 × 720')
        expect(valueSummary({
            value_id: 'value_path', value_type: 'gesture_path', kind: 'literal',
            value: [[0, 0], [10, 20], [30, 40]],
        })).toBe('路径 · 3 个点')
    })

    it('offers only values visible before the selected statement in its lexical block', () => {
        const document: ProgramDocument = {
            schema_version: 6, document_id: 'doc_scope', revision: 'rev_scope',
            function: {
                function_id: 'func_scope', display_name: '作用域测试', return_type: 'void',
                parameters: [{ symbol_id: 'symbol_parameter', display_name: '输入', value_type: 'string' }],
                statements: [
                    {
                        statement_id: 'stmt_assignment', kind: 'assignment',
                        target: { kind: 'local', symbol_id: 'symbol_before', display_name: '前置值', value_type: 'string', declare: true },
                        value: literal('value_before', 'A'),
                    },
                    {
                        statement_id: 'stmt_loop', kind: 'loop', mode: 'for_each',
                        source: { value_id: 'value_list', value_type: 'list<string>', kind: 'list', item_type: 'string', items: [] },
                        item_binding: { symbol_id: 'symbol_item', display_name: '当前项', value_type: 'string' },
                        body: [call('stmt_inside', '循环内')],
                    },
                    call('stmt_after', '循环后'),
                ],
            },
        }

        expect(availableValuesAtStatement(document, 'stmt_inside').map((item) => item.id)).toEqual([
            'symbol_parameter', 'symbol_before', 'symbol_item',
        ])
        expect(availableValuesAtStatement(document, 'stmt_after').map((item) => item.id)).toEqual([
            'symbol_parameter', 'symbol_before',
        ])
        expect(availableValuesAtInsertion(document, 'stmt_assignment').map((item) => item.id)).toEqual([
            'symbol_parameter', 'symbol_before',
        ])
        expect(availableValuesAtInsertion(document, undefined, {
            key: 'stmt_loop:body', parent_statement_id: 'stmt_loop', block: 'body', label: '循环内容',
        }).map((item) => item.id)).toEqual([
            'symbol_parameter', 'symbol_before', 'symbol_item',
        ])
        expect(availableValuesAtInsertion(document).map((item) => item.id)).toEqual([
            'symbol_parameter', 'symbol_before',
        ])
    })
})
