import { describe, expect, it } from 'vitest'
import { directProgramValue, isConditionValueDestination, programValueEditorTitle, replaceDirectProgramValue } from '../valueEditing'
import type { ProgramStatement, ProgramValueNode } from '../types'

const listValue: ProgramValueNode = { value_id: 'value_list', kind: 'list', value_type: 'list<string>', item_type: 'string', items: [] }
const nextList: ProgramValueNode = {
    ...listValue,
    items: [{ value_id: 'value_item', kind: 'literal', value_type: 'string', value: '副本' }],
}

describe('focused value destinations', () => {
    it('names the value editor with both the owning statement and field', () => {
        const statement: ProgramStatement = {
            statement_id: 'statement_call', kind: 'call', function_id: 'function_test', display_name: '图像.查找',
            summary: '查找登录按钮', arguments: { image: listValue },
        }
        expect(programValueEditorTitle(statement, 'image', {
            function_test: {
                function_id: 'function_test', display_name: '图像.查找', return_type: 'void',
                parameters: [{ parameter_id: 'image', display_name: '图片', value_type: 'asset_ref<image>', required: true }],
            },
        })).toBe('查找登录按钮 · 图片')
    })

    it('targets a call argument by statement, parameter and value identity', () => {
        const statement: ProgramStatement = {
            statement_id: 'statement_call', kind: 'call', function_id: 'function_test', display_name: '测试',
            arguments: { items: listValue },
        }
        expect(directProgramValue(statement, 'items', 'value_list')).toBe(listValue)
        expect(replaceDirectProgramValue(statement, 'items', 'value_list', nextList)).toMatchObject({
            kind: 'update_value', statement_id: 'statement_call', parameter_id: 'items', value_id: 'value_list',
            next: { value_id: 'value_list', items: [{ value_id: 'value_item' }] },
        })
        expect(replaceDirectProgramValue(statement, 'other', 'value_list', nextList)).toBeNull()
    })

    it('uses field-specific commands for conditions and listener handler arguments', () => {
        const conditional: ProgramStatement = {
            statement_id: 'statement_if', kind: 'if', condition: listValue,
            then_body: [], additional_branches: [{ branch_id: 'branch_1', condition: listValue, statements: [] }], else_body: [],
        }
        expect(replaceDirectProgramValue(conditional, 'if.branch.branch_1', 'value_list', nextList)).toMatchObject({
            kind: 'update_if_condition', statement_id: 'statement_if', branch_id: 'branch_1', condition: nextList,
        })

        const listener: ProgramStatement = {
            statement_id: 'statement_listen', kind: 'listen',
            event_source: { kind: 'message', name: { value_id: 'value_name', kind: 'literal', value_type: 'string', value: 'invite' } },
            receive_binding: { symbol_id: 'symbol_message', display_name: '邀请', value_type: 'message' },
            handler_function_id: 'function_handler', handler_display_name: '处理邀请', condition: null,
            handler_arguments: { tasks: listValue },
        }
        const command = replaceDirectProgramValue(listener, 'tasks', 'value_list', nextList)
        expect(command).toMatchObject({ kind: 'update_listen', statement_id: 'statement_listen', handler_arguments: { tasks: nextList } })
    })

    it('rejects a replacement whose stable root identity changed', () => {
        const statement: ProgramStatement = {
            statement_id: 'statement_assignment', kind: 'assignment',
            target: { kind: 'local', symbol_id: 'symbol_items', display_name: '项目', value_type: 'list<string>', declare: true },
            value: listValue,
        }
        expect(replaceDirectProgramValue(statement, 'assignment.value', 'value_list', { ...nextList, value_id: 'other' })).toBeNull()
    })

    it('offers the condition builder only for actual control-flow condition slots', () => {
        const conditional: ProgramStatement = {
            statement_id: 'statement_if', kind: 'if', condition: listValue,
            then_body: [], additional_branches: [], else_body: [],
        }
        const loop: ProgramStatement = {
            statement_id: 'statement_loop', kind: 'loop', mode: 'repeat', source: listValue,
            body: [], item_binding: null, index_binding: null, key_binding: null, value_binding: null,
        }
        expect(isConditionValueDestination(conditional, 'if.condition')).toBe(true)
        expect(isConditionValueDestination(conditional, 'assignment.value')).toBe(false)
        expect(isConditionValueDestination(loop, 'loop.source')).toBe(false)
        expect(isConditionValueDestination({ ...loop, mode: 'while' }, 'loop.source')).toBe(true)
    })
})
