import { describe, expect, it } from 'vitest'
import {
    availableFunctionsToUiContracts,
    programSnapshotToUiDocument,
    uiStructureCommandToServerCommand,
    uiValueUpdateToServerCommand,
} from '../adapter'
import { choiceOptions, controlForParameter } from '../controlContract'
import type { AvailableFunctionContractDto, ProgramSnapshotDto } from '../serverTypes'

function waitContract(state: 'available' | 'planned' = 'available'): AvailableFunctionContractDto {
    return {
        function_id: 'official.wait.duration',
        namespace: '等待',
        name: '持续',
        qualified_name: '等待.持续',
        summary: '等待{duration}',
        statement_summary: {
            schema_version: 1,
            parts: [
                { kind: 'text', text: '等待' },
                {
                    kind: 'parameter', parameter_id: 'official.wait.duration.parameter.duration',
                    parameter_name: 'duration', role: 'qualifier', presentation: 'auto',
                },
            ],
        },
        layer: 'atomic',
        parameters: [{
            parameter_id: 'official.wait.duration.parameter.duration',
            name: 'duration',
            display_name: '时长',
            value_type: 'duration',
            required: true,
            has_default: true,
            default: { kind: 'duration', milliseconds: 1000 },
            control: 'duration',
            constraints: {},
            description: '',
        }],
        return_type: 'unit',
        opcode: 'wait.duration',
        host_requirements: ['windows', 'android'],
        target_kinds: [],
        target_capabilities: [],
        permissions: [],
        side_effects: [],
        errors: [],
        normal_empty: false,
        network_level: 'none',
        dangerous: false,
        implementation_state: state,
        standard_definition_id: '',
        contract_version: '1.0.0',
        schema_version: 1,
        contract_fingerprint: 'fingerprint',
    }
}

function snapshot(): ProgramSnapshotDto {
    return {
        revision: `sha256:${'a'.repeat(64)}`,
        diagnostics: [],
        document: {
            schema_version: 1,
            document_id: 'doc_main',
            function: {
                function_id: 'func_main',
                display_name: '主程序',
                parameters: [],
                return_type: 'null',
                statements: [{
                    statement_id: 'stmt_wait',
                    kind: 'call',
                    function_id: 'official.wait.duration',
                    arguments: {
                        'official.wait.duration.parameter.duration': {
                            value_id: 'value_duration',
                            kind: 'duration',
                            milliseconds: 2000,
                        },
                    },
                    result_binding: null,
                    step_label: null,
                }],
            },
        },
    }
}

describe('format-6 ProgramDocument projection adapter', () => {
    it('uses native date, datetime and time controls for canonical temporal types', () => {
        for (const valueType of ['date', 'datetime', 'time']) {
            expect(controlForParameter({
                parameter_id: `temporal_${valueType}`,
                display_name: valueType,
                value_type: valueType,
                required: true,
            })).toBe('time')
        }
    })

    it('filters enum choices by the active target and preserves an incompatible current value as disabled', () => {
        const parameter = {
            parameter_id: 'button', display_name: '按键', value_type: 'enum<pointer_button>',
            required: false,
            constraints: { choices: [
                { label: '主按键', value: 'primary' },
                { label: '右键', value: 'secondary', platforms: ['windows' as const] },
            ] },
        }

        expect(choiceOptions(parameter, 'android_adb')).toEqual([
            { label: '主按键', value: 'primary' },
        ])
        expect(choiceOptions(parameter, 'android_adb', 'secondary')).toEqual([
            { label: '主按键', value: 'primary' },
            { label: '右键（当前目标不可用）', value: 'secondary', disabled: true },
        ])
    })

    it('projects contract choices as fixed selects instead of value-source modes', () => {
        const contract = waitContract()
        contract.parameters[0] = {
            ...contract.parameters[0],
            value_type: 'enum<wait_mode>',
            control: 'select',
            default: 'normal',
            constraints: { choices: [{ label: '普通', value: 'normal' }, { label: '严格', value: 'strict' }] },
        }

        const projected = availableFunctionsToUiContracts([contract])[contract.function_id].parameters[0]

        expect(projected.allowed_sources).toEqual(['fixed'])
        expect(projected.ui?.control).toBe('select')
        expect(projected.constraints?.choices).toHaveLength(2)
    })

    it('projects server facts without leaking them back as an editable second model', () => {
        const source = snapshot()
        const projected = programSnapshotToUiDocument(source, [waitContract()])

        expect(projected).toMatchObject({
            schema_version: 1,
            document_id: 'doc_main',
            revision: source.revision,
            function: { function_id: 'func_main', display_name: '主程序' },
        })
        expect(projected.function.statements[0]).toMatchObject({
            statement_id: 'stmt_wait',
            display_name: '等待.持续',
            summary: '等待2 秒',
            summary_parts: [
                { text: '等待' },
                { text: '2 秒', dynamic: true },
            ],
            arguments: {
                'official.wait.duration.parameter.duration': {
                    value_id: 'value_duration',
                    kind: 'literal',
                    value: { milliseconds: 2000 },
                },
            },
        })
        expect(source.document.function.statements[0]).toMatchObject({
            kind: 'call',
            arguments: {
                'official.wait.duration.parameter.duration': { kind: 'duration', milliseconds: 2000 },
            },
        })
    })

    it('converts one UI field edit to stable statement, parameter and value identifiers', () => {
        expect(uiValueUpdateToServerCommand({
            statement_id: 'stmt_wait',
            parameter_id: 'official.wait.duration.parameter.duration',
            value_id: 'value_duration',
            next: { kind: 'literal', value_type: 'duration', value: { milliseconds: 3500 } },
        })).toEqual({
            kind: 'update_argument',
            statement_id: 'stmt_wait',
            parameter_id: 'official.wait.duration.parameter.duration',
            value: { value_id: 'value_duration', kind: 'duration', milliseconds: 3500 },
        })
    })

    it('serializes percentage parameters as finite float values', () => {
        expect(uiValueUpdateToServerCommand({
            statement_id: 'stmt_find',
            parameter_id: 'official.image.find.parameter.similarity',
            value_id: 'value_similarity',
            next: { kind: 'literal', value_type: 'percentage', value: 0.9 },
        })).toEqual({
            kind: 'update_argument',
            statement_id: 'stmt_find',
            parameter_id: 'official.image.find.parameter.similarity',
            value: { value_id: 'value_similarity', kind: 'float64', value: 0.9 },
        })
    })

    it('converts field-specific structure edits without degrading them to arbitrary patches', () => {
        expect(uiStructureCommandToServerCommand({
            kind: 'update_loop',
            statement_id: 'stmt_loop',
            mode: 'for_each',
            source: { value_id: 'value_source', kind: 'list', value_type: 'list<string>', item_type: 'string', items: [] },
            item_binding: { symbol_id: 'symbol_item', display_name: '当前项', value_type: 'string' },
            index_binding: { symbol_id: 'symbol_index', display_name: '当前序号', value_type: 'int64' },
            key_binding: null,
            value_binding: null,
        })).toEqual({
            kind: 'update_loop',
            statement_id: 'stmt_loop',
            mode: 'for_each',
            source: { value_id: 'value_source', kind: 'list', item_type: 'string', items: [] },
            item_binding: { symbol_id: 'symbol_item', display_name: '当前项', value_type: 'string' },
            index_binding: { symbol_id: 'symbol_index', display_name: '当前序号', value_type: 'int64' },
            key_binding: null,
            value_binding: null,
        })

        expect(uiStructureCommandToServerCommand({
            kind: 'update_if_condition', statement_id: 'stmt_if', branch_id: 'branch_retry',
            condition: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
        })).toEqual({
            kind: 'update_if_condition', statement_id: 'stmt_if', branch_id: 'branch_retry',
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
        })

        expect(uiStructureCommandToServerCommand({
            kind: 'add_if_branch', statement_id: 'stmt_if',
            condition: { value_id: 'value_branch', kind: 'unset', value_type: 'bool' },
        })).toEqual({
            kind: 'add_if_branch', statement_id: 'stmt_if',
            condition: { value_id: 'value_branch', kind: 'unset', expected_type: 'bool' },
        })
        expect(uiStructureCommandToServerCommand({
            kind: 'remove_if_branch', statement_id: 'stmt_if', branch_id: 'branch_retry',
        })).toEqual({ kind: 'remove_if_branch', statement_id: 'stmt_if', branch_id: 'branch_retry' })

        expect(uiStructureCommandToServerCommand({
            kind: 'update_assignment_target', statement_id: 'stmt_assignment',
            target: { kind: 'local', symbol_id: 'symbol_value', display_name: '是否完成', value_type: 'bool', declare: true },
            value: { value_id: 'value_assignment', kind: 'literal', value_type: 'bool', value: false },
        })).toEqual({
            kind: 'update_assignment_target', statement_id: 'stmt_assignment',
            target: { kind: 'local', symbol_id: 'symbol_value', display_name: '是否完成', value_type: 'bool', declare: true },
            value: { value_id: 'value_assignment', kind: 'bool', value: false },
        })
    })

    it('filters planned contracts and does not promise unavailable functions', () => {
        const contracts = availableFunctionsToUiContracts([waitContract(), {
            ...waitContract('planned'),
            function_id: 'official.wait.until',
            qualified_name: '等待.直到',
        }])

        expect(Object.keys(contracts)).toEqual(['official.wait.duration'])
        expect(contracts['official.wait.duration'].parameters[0]).toMatchObject({
            parameter_id: 'official.wait.duration.parameter.duration',
            default_value: { milliseconds: 1000 },
            allowed_sources: ['fixed', 'reference', 'computed'],
            ui: { control: 'duration' },
        })
        expect(contracts['official.wait.duration'].parameters[0].ui?.actions).toBeUndefined()
    })

    it('projects recursive values and every structured statement family', () => {
        const source: ProgramSnapshotDto = {
            revision: `sha256:${'b'.repeat(64)}`,
            diagnostics: [],
            document: {
                schema_version: 1,
                document_id: 'doc_rich',
                function: {
                    function_id: 'func_rich', display_name: '完整结构', parameters: [], return_type: 'record.result',
                    statements: [
                        {
                            statement_id: 'stmt_assignment', kind: 'assignment', step_label: null,
                            target: { kind: 'local', symbol_id: 'symbol_items', display_name: '任务列表', value_type: 'list<string>', declare: true },
                            value: { value_id: 'value_list', kind: 'list', item_type: 'string', items: [{ value_id: 'value_item', kind: 'string', value: '副本一' }] },
                        },
                        {
                            statement_id: 'stmt_if', kind: 'if', step_label: null,
                            condition: {
                                value_id: 'value_all', kind: 'condition_group', operator: 'all', conditions: [{
                                    value_id: 'value_compare', kind: 'compare', operator: 'gte',
                                    left: { value_id: 'value_member', kind: 'member_access', field_id: 'level', result_type: 'int64', source: { value_id: 'value_result_ref', kind: 'symbol_ref', symbol_id: 'symbol_items', value_type: 'record' } },
                                    right: { value_id: 'value_operation', kind: 'operation', operation_id: 'math.minimum', result_type: 'int64', inputs: { left: { value_id: 'value_ten', kind: 'int64', value: 10 } } },
                                }],
                            },
                            then_statements: [],
                            additional_branches: [{ branch_id: 'branch_other', condition: { value_id: 'value_not', kind: 'not', condition: { value_id: 'value_false', kind: 'bool', value: false } }, statements: [] }],
                            otherwise_statements: [],
                        },
                        {
                            statement_id: 'stmt_loop', kind: 'loop', mode: 'for_each_map', step_label: null,
                            source: { value_id: 'value_map', kind: 'map', key_type: 'string', entry_value_type: 'json_value', duplicate_policy: 'error', entries: [{ key: { value_id: 'value_key', kind: 'string', value: '配置' }, value: { value_id: 'value_json', kind: 'json', payload: { enabled: true } } }] },
                            body: [], item_binding: null, index_binding: null,
                            key_binding: { symbol_id: 'symbol_key', display_name: '键', value_type: 'string' },
                            value_binding: { symbol_id: 'symbol_value', display_name: '值', value_type: 'json_value' },
                        },
                        {
                            statement_id: 'stmt_return', kind: 'return', step_label: null,
                            value: { value_id: 'value_record', kind: 'record', record_type: 'record.result', fields: { ok: { value_id: 'value_ok', kind: 'bool', value: true } } },
                        },
                        {
                            statement_id: 'stmt_try', kind: 'try', step_label: null, body: [], catches: [{ catch_id: 'catch_any', error_ids: [], error_binding: null, statements: [] }], finally_statements: [], retry_policy: null,
                        },
                        {
                            statement_id: 'stmt_target', kind: 'target_scope', step_label: null,
                            target: { value_id: 'value_target', kind: 'target_ref', target_id: 'target_windows' }, body: [],
                        },
                        {
                            statement_id: 'stmt_listen', kind: 'listen', step_label: null,
                            event_source: { kind: 'message', name: { value_id: 'value_name', kind: 'string', value: '组队邀请' }, sender: null },
                            receive_binding: { symbol_id: 'symbol_message', display_name: '邀请', value_type: 'message' },
                            condition: null, handler_function_id: 'func_handle', handler_arguments: {},
                        },
                    ],
                },
            },
        }

        const projected = programSnapshotToUiDocument(source, [], {
            fieldNames: { level: '等级' }, operationNames: { 'math.minimum': '较小值' }, functionNames: { func_handle: '处理组队邀请' },
        })

        expect(projected.function.statements.map((statement) => statement.kind)).toEqual([
            'assignment', 'if', 'loop', 'return', 'try', 'target_scope', 'listen',
        ])
        expect(projected.function.statements[0]).toMatchObject({ kind: 'assignment', value: { kind: 'list', items: [{ kind: 'literal', value: '副本一' }] } })
        expect(projected.function.statements[1]).toMatchObject({ kind: 'if', condition: { kind: 'condition_group', conditions: [{ kind: 'compare', left: { kind: 'member_access', field_name: '等级' }, right: { kind: 'computed', operation_name: '较小值' } }] } })
        expect(projected.function.statements[2]).toMatchObject({ kind: 'loop', source: { kind: 'map', entries: [{ value: { kind: 'json', payload: { enabled: true } } }] } })
        expect(projected.function.statements[3]).toMatchObject({ kind: 'return', value: { kind: 'record', fields: { ok: { kind: 'literal', value: true } } } })
        expect(projected.function.statements[6]).toMatchObject({ kind: 'listen', handler_display_name: '处理组队邀请' })
    })

    it('projects capture actions only when the server explicitly publishes them', () => {
        const withAction = waitContract()
        withAction.parameters[0].ui = {
            control: 'duration',
            actions: [{ id: 'pick-point', capture_kind: 'point', platforms: ['windows'] }],
        }
        const contracts = availableFunctionsToUiContracts([withAction])
        expect(contracts[withAction.function_id].parameters[0].ui?.actions).toEqual(withAction.parameters[0].ui.actions)
    })

    it('uses snapshot presentation metadata instead of leaking stable operation IDs', () => {
        const operationId = 'core.number_max.v1'
        const source: ProgramSnapshotDto = {
            revision: `sha256:${'c'.repeat(64)}`,
            diagnostics: [],
            presentations: {
                operations: {
                    [operationId]: {
                        display_name: '取较大值',
                        syntax_name: '数值.取较大值',
                        input_labels: {
                            [`${operationId}.input.left`]: '左侧',
                            [`${operationId}.input.right`]: '右侧',
                        },
                    },
                },
            },
            document: {
                schema_version: 1,
                document_id: 'doc_operation_presentation',
                function: {
                    function_id: 'func_operation_presentation', display_name: '中文投影', parameters: [], return_type: 'null',
                    statements: [{
                        statement_id: 'stmt_assignment', kind: 'assignment', step_label: null,
                        target: { kind: 'local', symbol_id: 'symbol_value', display_name: '结果', value_type: 'int64', declare: true },
                        value: {
                            value_id: 'value_operation', kind: 'operation', operation_id: operationId, result_type: 'int64',
                            inputs: {
                                [`${operationId}.input.left`]: { value_id: 'value_left', kind: 'int64', value: 18 },
                                [`${operationId}.input.right`]: { value_id: 'value_right', kind: 'int64', value: 3 },
                            },
                        },
                    }],
                },
            },
        }

        const projected = programSnapshotToUiDocument(source, [])
        expect(projected.function.statements[0]).toMatchObject({
            kind: 'assignment',
            value: {
                kind: 'computed',
                operation_id: operationId,
                operation_name: '数值.取较大值',
                operation_input_names: {
                    [`${operationId}.input.left`]: '左侧',
                    [`${operationId}.input.right`]: '右侧',
                },
            },
        })
        expect(JSON.stringify(projected)).not.toContain('operation_name":"core.')
    })

    it('projects record and member labels from the same snapshot presentation contract', () => {
        const source = snapshot()
        source.presentations = {
            operations: {},
            record_types: { image_match: '图像匹配结果' },
            fields: { 'image_match.field.center': '中心' },
        }
        source.document.function.statements = [{
            statement_id: 'stmt_member', kind: 'assignment', step_label: null,
            target: { kind: 'local', symbol_id: 'symbol_center', display_name: '登录位置', value_type: 'point', declare: true },
            value: {
                value_id: 'value_member', kind: 'member_access', field_id: 'image_match.field.center', result_type: 'point',
                source: {
                    value_id: 'value_record', kind: 'record', record_type: 'image_match',
                    fields: {
                        'image_match.field.center': { value_id: 'value_point', kind: 'point', x: 120, y: 80 },
                    },
                },
            },
        }]

        const projected = programSnapshotToUiDocument(source, [])
        expect(projected.function.statements[0]).toMatchObject({
            kind: 'assignment',
            value: {
                kind: 'member_access', field_name: '中心',
                source: {
                    kind: 'record', record_name: '图像匹配结果',
                    field_names: { 'image_match.field.center': '中心' },
                },
            },
        })
        expect(JSON.stringify(projected)).not.toContain('field_name":"image_match.field.center')
    })
})
