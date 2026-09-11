import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramStructureInspector from '../ProgramStructureInspector.vue'
import type { ProgramFunctionContract, ProgramStatement } from '../types'

describe('ProgramStructureInspector', () => {
    it('edits a new if directly as a typed condition instead of reducing it to a boolean toggle', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
            then_body: [], additional_branches: [], else_body: [],
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement } })
        expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
        expect(wrapper.text()).toContain('判断条件')
        expect(wrapper.get('.expression-surface').text()).toContain('开启')

        await wrapper.get('.expression-surface').trigger('click')
        const input = wrapper.get('.expression-editor')
        await input.setValue('18 >= 3')
        await input.trigger('keydown.enter')
        expect(wrapper.emitted('command')?.[0]?.[0]).toMatchObject({
            kind: 'update_if_condition', statement_id: 'stmt_if',
            condition: { value_id: 'value_condition', kind: 'compare', operator: 'gte' },
        })
    })

    it('adds ordered else-if branches and only removes an empty branch', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_if', kind: 'if',
            condition: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
            then_body: [],
            additional_branches: [{
                branch_id: 'branch_empty',
                condition: { value_id: 'value_else_if', kind: 'literal', value_type: 'bool', value: false },
                statements: [],
            }],
            else_body: [],
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement } })

        await wrapper.get('.condition-branch-actions button').trigger('click')
        expect(wrapper.emitted('command')?.[0]?.[0]).toMatchObject({
            kind: 'add_if_branch', statement_id: 'stmt_if', condition: { kind: 'unset', value_type: 'bool' },
        })

        await wrapper.get('.remove-branch-button').trigger('click')
        expect(wrapper.emitted('command')?.[1]?.[0]).toEqual({
            kind: 'remove_if_branch', statement_id: 'stmt_if', branch_id: 'branch_empty',
        })
        expect(wrapper.get('.condition-branch-actions button').attributes('title')).toBe('按顺序判断，并只执行第一个满足条件的分支')
        expect(wrapper.text()).not.toContain('只执行第一个满足条件的分支')

        await wrapper.setProps({
            statement: {
                ...statement,
                additional_branches: [{ ...statement.additional_branches[0]!, statements: [{
                    statement_id: 'stmt_child', kind: 'break',
                }] }],
            },
        })
        expect(wrapper.get('.remove-branch-button').attributes('disabled')).toBeDefined()
    })

    it('switches loop mode as one valid field-specific command and preserves the source root ID', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_loop', kind: 'loop', mode: 'repeat',
            source: { value_id: 'value_count', kind: 'literal', value_type: 'int64', value: 3 },
            body: [], item_binding: null, index_binding: null, key_binding: null, value_binding: null,
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement } })

        await wrapper.get('select').setValue('for_each')
        const command = wrapper.emitted('command')?.[0]?.[0] as Record<string, unknown>
        expect(command).toMatchObject({
            kind: 'update_loop', statement_id: 'stmt_loop', mode: 'for_each',
            source: { value_id: 'value_count', kind: 'list', value_type: 'list<any>' },
            item_binding: { display_name: '当前项', value_type: 'any' },
            key_binding: null, value_binding: null,
        })
    })

    it('changes a target scope through the shared select Control with a typed target reference', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_target', kind: 'target_scope',
            target: { value_id: 'value_target', kind: 'target_ref', value_type: 'target_ref', target_id: 'target_a' },
            body: [],
        }
        const wrapper = mount(ProgramStructureInspector, {
            props: {
                statement,
                targetOptions: [{ label: '窗口 A', value: 'target_a' }, { label: '模拟器 B', value: 'target_b' }],
            },
        })

        expect((wrapper.get('.program-parameter select').element as HTMLSelectElement).value).toBe('target_a')
        expect(wrapper.get('.program-parameter').classes()).toContain('is-stacked')
        await wrapper.get('.program-parameter select').setValue('target_b')
        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            kind: 'update_target_scope', statement_id: 'stmt_target',
            target: { value_id: 'value_target', kind: 'target_ref', value_type: 'target_ref', target_id: 'target_b' },
        })
    })

    it('initializes handler arguments when changing a listener handler', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_listen', kind: 'listen',
            event_source: { kind: 'message', name: { value_id: 'value_name', kind: 'literal', value_type: 'string', value: '邀请' }, sender: null },
            receive_binding: { symbol_id: 'symbol_message', display_name: '消息', value_type: 'message' },
            condition: null, handler_function_id: 'func_old', handler_display_name: '旧处理', handler_arguments: {},
        }
        const contracts: Record<string, ProgramFunctionContract> = {
            func_old: { function_id: 'func_old', display_name: '旧处理', parameters: [], return_type: 'void' },
            func_new: {
                function_id: 'func_new', display_name: '处理邀请', return_type: 'void',
                parameters: [{ parameter_id: 'room_code', display_name: '房间码', value_type: 'string', required: true }],
            },
        }
        const wrapper = mount(ProgramStructureInspector, {
            props: { statement, functionContracts: contracts, projectFunctionIds: ['func_old', 'func_new'] },
        })

        await wrapper.get('.structure-section select').setValue('func_new')
        const command = wrapper.emitted('command')?.[0]?.[0] as Record<string, unknown>
        expect(command).toMatchObject({
            kind: 'update_listen', statement_id: 'stmt_listen', handler_function_id: 'func_new',
            receive_binding: { symbol_id: 'symbol_message' },
            handler_arguments: { room_code: { kind: 'unset', value_type: 'string' } },
        })
    })

    it('renames a local assignment target without replacing its stable symbol ID', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_assignment', kind: 'assignment',
            target: { kind: 'local', symbol_id: 'symbol_result', display_name: '结果', value_type: 'string', declare: true },
            value: { value_id: 'value_text', kind: 'literal', value_type: 'string', value: '完成' },
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement } })
        await wrapper.get('.field-label input').setValue('执行结果')
        await wrapper.get('.field-label input').trigger('change')

        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            kind: 'update_assignment_target', statement_id: 'stmt_assignment',
            target: { kind: 'local', symbol_id: 'symbol_result', display_name: '执行结果', value_type: 'string', declare: true },
        })
    })

    it('shows the local variable type and changes target plus value atomically', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_assignment', kind: 'assignment',
            target: { kind: 'local', symbol_id: 'symbol_level', display_name: '当前等级', value_type: 'int64', declare: true },
            value: { value_id: 'value_level', kind: 'literal', value_type: 'int64', value: 18 },
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement } })

        expect(wrapper.text()).toContain('变量类型')
        expect(wrapper.text()).toContain('整数')
        const typeSelect = wrapper.findAll('.field-label select').find((select) => (select.element as HTMLSelectElement).value === 'int64')
        if (!typeSelect) throw new Error('expected variable type select')
        expect(typeSelect.findAll('option').map((option) => option.attributes('value'))).toEqual(expect.arrayContaining([
            'list<string>', 'list<int64>', 'map<string,string>', 'map<string,any>',
        ]))
        await typeSelect.setValue('bool')

        expect(wrapper.emitted('command')?.at(-1)?.[0]).toMatchObject({
            kind: 'update_assignment_target', statement_id: 'stmt_assignment',
            target: { kind: 'local', symbol_id: 'symbol_level', display_name: '当前等级', value_type: 'bool' },
            value: { value_id: 'value_level', kind: 'literal', value_type: 'bool', value: false },
        })

        await typeSelect.setValue('list<string>')
        expect(wrapper.emitted('command')?.at(-1)?.[0]).toMatchObject({
            kind: 'update_assignment_target', statement_id: 'stmt_assignment',
            target: { kind: 'local', symbol_id: 'symbol_level', value_type: 'list<string>' },
            value: { value_id: 'value_level', kind: 'list', value_type: 'list<string>', item_type: 'string', items: [] },
        })
    })

    it('shows retry review only when the server diagnostic requires it and never exposes a fingerprint field', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_try', kind: 'try', body: [], catches: [], finally_body: [],
            retry_policy: {
                max_retries: { value_id: 'value_retries', kind: 'literal', value_type: 'int64', value: 2 },
                interval: { value_id: 'value_interval', kind: 'literal', value_type: 'duration', value: { milliseconds: 500 } },
                transient_only: true,
                author_review_fingerprint: null,
            },
        }
        const wrapper = mount(ProgramStructureInspector, { props: { statement, reviewRetryRequired: false } })
        expect(wrapper.find('.retry-review').exists()).toBe(false)

        await wrapper.setProps({ reviewRetryRequired: true })
        expect(wrapper.text()).not.toContain('fingerprint')
        await wrapper.get('.retry-review button').trigger('click')
        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            kind: 'review_retry_risk', statement_id: 'stmt_try',
        })
    })
})
