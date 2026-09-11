import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProgramApiError } from '../api'
import type { AvailableFunctionContractDto, ProgramSnapshotDto, ProgramSummaryDto } from '../serverTypes'

const apiMocks = vi.hoisted(() => ({
    listAvailableFunctions: vi.fn(),
    listPrograms: vi.fn(),
    createProgram: vi.fn(),
    renameProgram: vi.fn(),
    deleteProgram: vi.fn(),
    getProgram: vi.fn(),
    applyCommand: vi.fn(),
    applyCommands: vi.fn(),
    extractStatements: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    compile: vi.fn(),
    run: vi.fn(),
}))

vi.mock('../api', async () => {
    const actual = await vi.importActual<typeof import('../api')>('../api')
    return { ...actual, programApi: apiMocks }
})

import { useProgramStore } from '../store'

const workspace = {
    workspace_id: 'workspace-store',
    generation: 3,
    project_id: 'project-store',
    project_name: 'Store test',
    project_path: 'D:/Projects/Store',
    read_only: false,
}

function contract(): AvailableFunctionContractDto {
    return {
        function_id: 'official.wait.duration',
        namespace: '等待',
        name: '持续',
        qualified_name: '等待.持续',
        summary: '等待{duration}',
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
        implementation_state: 'available',
        standard_definition_id: '',
        contract_version: '1.0.0',
        schema_version: 1,
        contract_fingerprint: 'fingerprint',
    }
}

function snapshot(revisionCharacter = 'a', milliseconds = 1000): ProgramSnapshotDto {
    return {
        revision: `sha256:${revisionCharacter.repeat(64)}`,
        diagnostics: [],
        can_undo: revisionCharacter !== 'a',
        can_redo: false,
        document: {
            schema_version: 1,
            document_id: 'doc-main',
            function: {
                function_id: 'func-main',
                display_name: '主程序',
                parameters: [],
                return_type: 'null',
                statements: [{
                    statement_id: 'stmt-wait',
                    kind: 'call',
                    function_id: 'official.wait.duration',
                    arguments: {
                        'official.wait.duration.parameter.duration': {
                            value_id: 'value-duration',
                            kind: 'duration',
                            milliseconds,
                        },
                    },
                    result_binding: null,
                    step_label: null,
                }],
            },
        },
    }
}

function twoWaitSnapshot(revisionCharacter = 'a'): ProgramSnapshotDto {
    const result = snapshot(revisionCharacter)
    result.document.function.statements.push({
        statement_id: 'stmt-wait-2', kind: 'call', function_id: 'official.wait.duration',
        arguments: {
            'official.wait.duration.parameter.duration': {
                value_id: 'value-duration-2', kind: 'duration', milliseconds: 2000,
            },
        },
        result_binding: null, step_label: null,
    })
    return result
}

function secondarySnapshot(revisionCharacter = 'c'): ProgramSnapshotDto {
    const result = snapshot(revisionCharacter)
    result.document.document_id = 'doc-secondary'
    result.document.function.function_id = 'func-secondary'
    result.document.function.display_name = '辅助流程'
    result.document.function.statements = [{
        statement_id: 'stmt-secondary',
        kind: 'call',
        function_id: 'official.wait.duration',
        arguments: {
            'official.wait.duration.parameter.duration': {
                value_id: 'value-secondary-duration', kind: 'duration', milliseconds: 500,
            },
        },
        result_binding: null,
        step_label: null,
    }]
    return result
}

const summary: ProgramSummaryDto = {
    document_id: 'doc-main',
    function_id: 'func-main',
    display_name: '主程序',
    statement_count: 1,
    revision: `sha256:${'a'.repeat(64)}`,
    parameters: [],
    return_type: 'null',
    contract_version: '1.0.0',
    contract_fingerprint: 'fingerprint-main',
}

describe('format-6 program Pinia store', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        Object.values(apiMocks).forEach((mock) => mock.mockReset())
        apiMocks.listAvailableFunctions.mockResolvedValue([contract()])
        apiMocks.listPrograms.mockResolvedValue([summary])
        apiMocks.getProgram.mockResolvedValue(snapshot())
    })

    it('keeps the server snapshot authoritative and sends stable parameter commands', async () => {
        const store = useProgramStore()
        await store.connect(workspace)
        store.setSelectedStatementIds(['stmt-wait'])
        apiMocks.applyCommand.mockResolvedValueOnce({
            ...snapshot('b', 2500),
            selected_statement_id: 'stmt-wait',
        })

        await store.applyUiCommand({
            document_id: 'doc-main',
            base_revision: `sha256:${'a'.repeat(64)}`,
            command: {
                kind: 'update_value',
                statement_id: 'stmt-wait',
                parameter_id: 'official.wait.duration.parameter.duration',
                value_id: 'value-duration',
                next: { kind: 'literal', value_type: 'duration', value: { milliseconds: 2500 } },
            },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace,
            'func-main',
            `sha256:${'a'.repeat(64)}`,
            {
                kind: 'update_argument',
                statement_id: 'stmt-wait',
                parameter_id: 'official.wait.duration.parameter.duration',
                value: { value_id: 'value-duration', kind: 'duration', milliseconds: 2500 },
            },
        )
        expect(store.serverSnapshot?.revision).toBe(`sha256:${'b'.repeat(64)}`)
        expect(store.document?.function.statements[0]).toMatchObject({ summary: '等待2500 毫秒' })
        expect(store.selectedStatementIds).toEqual(['stmt-wait'])
    })

    it('does not retry or overwrite a revision conflict and reloads only on explicit request', async () => {
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockRejectedValueOnce(new ProgramApiError('文档已修改', {
            status: 409,
            code: 'program_revision_conflict',
            recoveryAction: 'reload_workspace',
            diagnostics: [{
                function_id: 'func-main',
                expected_revision: `sha256:${'a'.repeat(64)}`,
                actual_revision: `sha256:${'c'.repeat(64)}`,
            }],
        }))

        await expect(store.applyUiCommand({
            document_id: 'doc-main',
            base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'delete_statements', statement_ids: ['stmt-wait'] },
        })).rejects.toThrow('文档已修改')

        expect(apiMocks.applyCommand).toHaveBeenCalledTimes(1)
        expect(apiMocks.getProgram).toHaveBeenCalledTimes(1)
        expect(store.status).toBe('conflict')
        expect(store.conflict).toMatchObject({ function_id: 'func-main' })
        expect(store.serverSnapshot?.revision).toBe(`sha256:${'a'.repeat(64)}`)

        apiMocks.getProgram.mockResolvedValueOnce(snapshot('c', 3000))
        await store.reloadConflict()
        expect(apiMocks.getProgram).toHaveBeenCalledTimes(2)
        expect(store.status).toBe('ready')
        expect(store.serverSnapshot?.revision).toBe(`sha256:${'c'.repeat(64)}`)
    })

    it('routes structure edits through the same revision and snapshot transaction', async () => {
        const structured = snapshot()
        structured.document.function.statements = [{
            statement_id: 'stmt_if', kind: 'if', step_label: null,
            condition: { value_id: 'value_condition', kind: 'bool', value: false },
            then_statements: [], additional_branches: [], otherwise_statements: [],
        }]
        apiMocks.getProgram.mockResolvedValueOnce(structured)
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({
            ...structured,
            revision: `sha256:${'b'.repeat(64)}`,
            document: {
                ...structured.document,
                function: {
                    ...structured.document.function,
                    statements: [{
                        ...structured.document.function.statements[0],
                        condition: { value_id: 'value_condition', kind: 'bool', value: true },
                    }],
                },
            },
        })

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: `sha256:${'a'.repeat(64)}`,
            command: {
                kind: 'update_if_condition', statement_id: 'stmt_if', branch_id: null,
                condition: { value_id: 'value_condition', kind: 'literal', value_type: 'bool', value: true },
            },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'update_if_condition', statement_id: 'stmt_if', branch_id: null,
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
        })
        expect(store.serverSnapshot?.revision).toBe(`sha256:${'b'.repeat(64)}`)
        expect(store.document?.function.statements[0]).toMatchObject({ kind: 'if', condition: { value: true } })
    })

    it('refuses to insert catalog entries that the backend has not made available', async () => {
        const store = useProgramStore()
        await store.connect(workspace)

        await expect(store.insertFunction('official.image.find')).rejects.toThrow('尚未由后端确认可运行')
        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
    })

    it('inserts a catalog-backed project function but rejects direct self-calls', async () => {
        const store = useProgramStore()
        apiMocks.listPrograms.mockResolvedValueOnce([summary, {
            ...summary,
            document_id: 'doc-helper',
            function_id: 'func-helper',
            display_name: '领取奖励',
            contract_fingerprint: 'fingerprint-helper',
        }])
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce(snapshot('b'))

        await store.insertFunction('func-helper')
        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace,
            'func-main',
            `sha256:${'a'.repeat(64)}`,
            expect.objectContaining({ kind: 'insert_call', function_id: 'func-helper' }),
        )
        await expect(store.insertFunction('func-main')).rejects.toThrow('不能直接调用自身')
    })

    it('preserves additional-branch ownership when moving nested statements', async () => {
        const nested = snapshot()
        nested.document.function.statements = [{
            statement_id: 'stmt_if',
            kind: 'if',
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
            then_statements: [],
            additional_branches: [{
                branch_id: 'branch_retry',
                condition: { value_id: 'value_retry', kind: 'bool', value: false },
                statements: [
                    { statement_id: 'stmt_a', kind: 'return', value: null, step_label: null },
                    { statement_id: 'stmt_b', kind: 'return', value: null, step_label: null },
                ],
            }],
            otherwise_statements: [],
            step_label: null,
        }]
        apiMocks.getProgram.mockResolvedValueOnce(nested)
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...nested, revision: `sha256:${'b'.repeat(64)}` })

        await store.applyUiCommand({
            document_id: 'doc-main',
            base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'move_statements', statement_ids: ['stmt_b'], direction: 'up' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'move_statements',
            statement_ids: ['stmt_b'],
            location: {
                parent_statement_id: 'stmt_if',
                block: 'additional_branch',
                clause_id: 'branch_retry',
                before_statement_id: 'stmt_a',
            },
        })
    })

    it('moves a statement into and out of a structural block without changing its identity', async () => {
        const root = snapshot()
        root.document.function.statements = [{
            statement_id: 'stmt_if', kind: 'if', step_label: null,
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
            then_statements: [], additional_branches: [], otherwise_statements: [],
        }, { statement_id: 'stmt_log', kind: 'return', value: null, step_label: null }]
        apiMocks.getProgram.mockResolvedValueOnce(root)
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...root, revision: `sha256:${'b'.repeat(64)}` })

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'change_statement_nesting', statement_ids: ['stmt_log'], direction: 'in' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'move_statements', statement_ids: ['stmt_log'],
            location: { parent_statement_id: 'stmt_if', block: 'then', clause_id: null, before_statement_id: null },
        })

        const nested = snapshot()
        nested.document.function.statements = [{
            statement_id: 'stmt_if', kind: 'if', step_label: null,
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
            then_statements: [{ statement_id: 'stmt_log', kind: 'return', value: null, step_label: null }],
            additional_branches: [], otherwise_statements: [],
        }, { statement_id: 'stmt_after', kind: 'return', value: null, step_label: null }]
        apiMocks.getProgram.mockResolvedValueOnce(nested)
        await store.loadProgram('func-main')
        apiMocks.applyCommand.mockResolvedValueOnce({ ...nested, revision: `sha256:${'b'.repeat(64)}` })

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'change_statement_nesting', statement_ids: ['stmt_log'], direction: 'out' },
        })

        expect(apiMocks.applyCommand).toHaveBeenLastCalledWith(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'move_statements', statement_ids: ['stmt_log'],
            location: { parent_statement_id: null, block: 'root', before_statement_id: 'stmt_after' },
        })
    })

    it('extracts selected statements through the transactional service and registers the new function', async () => {
        const store = useProgramStore()
        await store.connect(workspace)
        const extractedSummary: ProgramSummaryDto = {
            ...summary,
            document_id: 'doc-extracted',
            function_id: 'func-extracted',
            display_name: '等待片段',
            revision: `sha256:${'c'.repeat(64)}`,
        }
        const sourceAfterExtraction = snapshot('b')
        sourceAfterExtraction.document.function.statements = [{
            statement_id: 'stmt-extracted-call', kind: 'call', function_id: 'func-extracted',
            arguments: {}, result_binding: null, step_label: null,
        }]
        apiMocks.extractStatements.mockResolvedValueOnce({
            ...sourceAfterExtraction,
            selected_statement_id: 'stmt-extracted-call',
            extracted_program: extractedSummary,
        })

        await store.extractStatements(['stmt-wait'], '等待片段')

        expect(apiMocks.extractStatements).toHaveBeenCalledWith(
            workspace, 'func-main', `sha256:${'a'.repeat(64)}`, ['stmt-wait'], '等待片段',
        )
        expect(store.programs.some((item) => item.function_id === 'func-extracted')).toBe(true)
        expect(store.document?.function.statements[0]).toMatchObject({
            kind: 'call', display_name: '等待片段',
        })
    })

    it('creates every exposed structure through a real Program Service command', async () => {
        apiMocks.listPrograms.mockResolvedValueOnce([summary, {
            ...summary,
            document_id: 'doc-handler',
            function_id: 'func-handler',
            display_name: '处理消息',
        }])
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValue(snapshot('b'))

        for (const kind of ['assignment', 'if', 'loop', 'try', 'target_scope', 'listen', 'return'] as const) {
            await store.insertStructure(kind, { target_id: 'target-main', handler_function_id: 'func-handler' })
        }

        const commands = apiMocks.applyCommand.mock.calls.map((call) => call[3])
        expect(commands.map((command) => command.kind)).toEqual([
            'insert_assignment', 'insert_if', 'insert_loop', 'insert_try', 'insert_target_scope', 'insert_listen', 'insert_return',
        ])
        expect(commands[2]).toMatchObject({ kind: 'insert_loop', mode: 'repeat', source: { kind: 'int64', value: 1 } })
        expect(commands[4]).toMatchObject({ kind: 'insert_target_scope', target: { kind: 'target_ref', target_id: 'target-main' } })
        expect(commands[5]).toMatchObject({ kind: 'insert_listen', handler_function_id: 'func-handler', event_source: { name: { kind: 'string', value: '消息' } } })
    })

    it('creates an existing-variable assignment atomically with a type-correct editable value', async () => {
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce(snapshot('b'))

        await store.insertStructure('assignment', {
            assignment_target: {
                kind: 'project_variable', variable_id: 'variable_energy', display_name: '当前体力', value_type: 'int64',
            },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace, 'func-main', `sha256:${'a'.repeat(64)}`,
            {
                kind: 'insert_assignment',
                target: {
                    kind: 'project_variable', variable_id: 'variable_energy', display_name: '当前体力', value_type: 'int64',
                },
                value: expect.objectContaining({ kind: 'int64', value: 0 }),
                location: { parent_statement_id: null, block: 'root', before_statement_id: null },
            },
        )
    })

    it('inserts into a selected empty block using its clause identity', async () => {
        const nested = snapshot()
        nested.document.function.statements = [{
            statement_id: 'stmt_if', kind: 'if', step_label: null,
            condition: { value_id: 'value_condition', kind: 'bool', value: true },
            then_statements: [], additional_branches: [], otherwise_statements: [],
        }]
        apiMocks.getProgram.mockResolvedValueOnce(nested)
        const store = useProgramStore()
        await store.connect(workspace)
        store.setInsertionTarget({ key: 'stmt_if:otherwise', parent_statement_id: 'stmt_if', block: 'otherwise', label: '否则' })
        apiMocks.applyCommand.mockResolvedValueOnce({ ...nested, revision: `sha256:${'b'.repeat(64)}` })

        await store.insertFunction('official.wait.duration')

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'insert_call',
            function_id: 'official.wait.duration',
            location: { parent_statement_id: 'stmt_if', block: 'otherwise', before_statement_id: null },
        })
    })

    it('renames a project function with its own revision and refreshes the authoritative snapshot', async () => {
        const renamed = snapshot('b')
        renamed.document.function.display_name = '每日任务'
        apiMocks.renameProgram.mockResolvedValueOnce(renamed)
        const store = useProgramStore()
        await store.connect(workspace)

        await store.renameProgram('func-main', ' 每日任务 ')

        expect(apiMocks.renameProgram).toHaveBeenCalledWith(
            workspace, 'func-main', `sha256:${'a'.repeat(64)}`, '每日任务',
        )
        expect(store.document?.function.display_name).toBe('每日任务')
        expect(store.programs[0].revision).toBe(`sha256:${'b'.repeat(64)}`)
    })

    it('keeps a referenced function and records the exact blocker instead of force deleting', async () => {
        apiMocks.deleteProgram.mockRejectedValueOnce(new ProgramApiError('项目函数仍被调用', {
            status: 409,
            code: 'program_referenced',
            diagnostics: [{
                kind: 'call', function_id: 'func-other', function_name: '自动领奖', statement_id: 'stmt-call',
            }],
        }))
        const store = useProgramStore()
        await store.connect(workspace)

        await expect(store.deleteProgram('func-main')).rejects.toThrow('项目函数仍被调用')
        expect(store.programs).toHaveLength(1)
        expect(store.lifecycleBlocker).toMatchObject({
            function_id: 'func-main', code: 'program_referenced',
            references: [{ function_id: 'func-other', statement_id: 'stmt-call' }],
        })
    })

    it('submits retry review without exposing or calculating the fingerprint in the client', async () => {
        const structured = snapshot()
        structured.document.function.statements = [{
            statement_id: 'stmt_try', kind: 'try', step_label: null, body: [], catches: [], finally_statements: [],
            retry_policy: {
                max_retries: { value_id: 'value_retries', kind: 'int64', value: 2 },
                interval: { value_id: 'value_interval', kind: 'duration', milliseconds: 500 },
                transient_only: true,
                author_review_fingerprint: null,
            },
        }]
        apiMocks.getProgram.mockResolvedValueOnce(structured)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...structured, revision: `sha256:${'b'.repeat(64)}` })
        const store = useProgramStore()
        await store.connect(workspace)

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'review_retry_risk', statement_id: 'stmt_try' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace, 'func-main', `sha256:${'a'.repeat(64)}`,
            { kind: 'review_retry_risk', statement_id: 'stmt_try' },
        )
    })

    it('delegates call-result condition creation as one atomic Program Service command', async () => {
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...snapshot(), revision: `sha256:${'b'.repeat(64)}` })

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: `sha256:${'a'.repeat(64)}`,
            command: { kind: 'insert_if_from_call_result', statement_id: 'stmt-wait' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace, 'func-main', `sha256:${'a'.repeat(64)}`,
            { kind: 'insert_if_from_call_result', statement_id: 'stmt-wait' },
        )
    })

    it('inserts a callable result guard as one server-side edit', async () => {
        apiMocks.listAvailableFunctions.mockResolvedValueOnce([{
            ...contract(),
            function_id: 'official.file.exists',
            return_type: 'bool',
        }])
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...snapshot(), revision: `sha256:${'c'.repeat(64)}` })

        await store.insertFunctionAndIf('official.file.exists')

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace,
            'func-main',
            `sha256:${'a'.repeat(64)}`,
            {
                kind: 'insert_call_and_if',
                function_id: 'official.file.exists',
                location: { parent_statement_id: null, block: 'root', before_statement_id: null },
            },
        )
    })

    it('inserts execute-until as one bounded structural transaction', async () => {
        apiMocks.listAvailableFunctions.mockResolvedValueOnce([{
            ...contract(),
            function_id: 'official.image.find',
            return_type: 'optional<image_match>',
        }])
        const store = useProgramStore()
        await store.connect(workspace)
        apiMocks.applyCommand.mockResolvedValueOnce({ ...snapshot(), revision: `sha256:${'d'.repeat(64)}` })

        await store.insertExecuteUntil('official.image.find')

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace,
            'func-main',
            `sha256:${'a'.repeat(64)}`,
            {
                kind: 'insert_execute_until',
                condition_function_id: 'official.image.find',
                max_attempts: 20,
                location: { parent_statement_id: null, block: 'root', before_statement_id: null },
            },
        )
    })

    it('copies without mutating and pastes a structural snapshot after the current anchor', async () => {
        const original = twoWaitSnapshot()
        apiMocks.getProgram.mockResolvedValueOnce(original)
        const store = useProgramStore()
        await store.connect(workspace)
        store.setSelectedStatementIds(['stmt-wait'])

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: original.revision,
            command: { kind: 'copy_statements', statement_ids: ['stmt-wait'] },
        })

        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
        expect(store.serverSnapshot?.revision).toBe(original.revision)
        expect(store.statementClipboardCount).toBe(1)
        expect(store.canPasteStatements).toBe(true)

        store.setSelectedStatementIds(['stmt-wait-2'])
        const pasted = twoWaitSnapshot('b')
        pasted.document.function.statements.push({
            statement_id: 'stmt-wait-copy',
            kind: 'call',
            function_id: 'official.wait.duration',
            arguments: {
                'official.wait.duration.parameter.duration': {
                    value_id: 'value-duration-copy', kind: 'duration', milliseconds: 1000,
                },
            },
            result_binding: null,
            step_label: null,
        })
        apiMocks.applyCommand.mockResolvedValueOnce(pasted)
        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: original.revision,
            command: { kind: 'paste_statements' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace, 'func-main', original.revision,
            expect.objectContaining({
                kind: 'paste_statements',
                location: { parent_statement_id: null, block: 'root', before_statement_id: null },
            }),
        )
        expect(store.selectedStatementIds).toEqual(['stmt-wait-copy'])
        expect(store.statementClipboardCount).toBe(1)
    })

    it('keeps a copy across project functions and pastes it atomically into the destination', async () => {
        const source = twoWaitSnapshot()
        const destination = secondarySnapshot()
        apiMocks.listPrograms.mockResolvedValueOnce([
            summary,
            {
                ...summary,
                document_id: 'doc-secondary',
                function_id: 'func-secondary',
                display_name: '辅助流程',
                revision: destination.revision,
            },
        ])
        apiMocks.getProgram.mockResolvedValueOnce(source).mockResolvedValueOnce(destination)
        const store = useProgramStore()
        await store.connect(workspace)

        await store.applyUiCommand({
            document_id: source.document.document_id,
            base_revision: source.revision,
            command: { kind: 'copy_statements', statement_ids: ['stmt-wait'] },
        })
        await store.loadProgram('func-secondary')

        expect(store.statementClipboardCount).toBe(1)
        expect(store.canPasteStatements).toBe(true)
        store.setSelectedStatementIds(['stmt-secondary'])
        const pasted = secondarySnapshot('d')
        pasted.document.function.statements.push({
            statement_id: 'stmt-cross-function-copy',
            kind: 'call',
            function_id: 'official.wait.duration',
            arguments: {
                'official.wait.duration.parameter.duration': {
                    value_id: 'value-cross-function-copy', kind: 'duration', milliseconds: 1000,
                },
            },
            result_binding: null,
            step_label: null,
        })
        apiMocks.applyCommand.mockResolvedValueOnce(pasted)

        await store.applyUiCommand({
            document_id: destination.document.document_id,
            base_revision: destination.revision,
            command: { kind: 'paste_statements' },
        })

        expect(apiMocks.applyCommand).toHaveBeenCalledOnce()
        expect(apiMocks.applyCommand).toHaveBeenCalledWith(
            workspace,
            'func-secondary',
            destination.revision,
            expect.objectContaining({
                kind: 'paste_statements',
                statements: [expect.objectContaining({ statement_id: 'stmt-wait' })],
                location: { parent_statement_id: null, block: 'root', before_statement_id: null },
            }),
        )
        expect(store.selectedStatementIds).toEqual(['stmt-cross-function-copy'])
        expect(store.statementClipboardCount).toBe(1)
    })

    it('cancels a deferred cut on function switch but preserves a rejected cross-function copy', async () => {
        const source = twoWaitSnapshot()
        const destination = secondarySnapshot()
        apiMocks.getProgram.mockResolvedValueOnce(source).mockResolvedValueOnce(destination)
        const store = useProgramStore()
        await store.connect(workspace)

        await store.applyUiCommand({
            document_id: source.document.document_id,
            base_revision: source.revision,
            command: { kind: 'cut_statements', statement_ids: ['stmt-wait'] },
        })
        await store.loadProgram('func-secondary')
        expect(store.statementClipboardCount).toBe(0)
        expect(store.canPasteStatements).toBe(false)

        apiMocks.getProgram.mockResolvedValueOnce(source).mockResolvedValueOnce(destination)
        await store.loadProgram('func-main')
        await store.applyUiCommand({
            document_id: source.document.document_id,
            base_revision: source.revision,
            command: { kind: 'copy_statements', statement_ids: ['stmt-wait'] },
        })
        await store.loadProgram('func-secondary')
        apiMocks.applyCommand.mockRejectedValueOnce(new ProgramApiError('局部变量引用不存在或不在当前作用域', {
            status: 400,
            code: 'program_command_invalid',
        }))

        await expect(store.applyUiCommand({
            document_id: destination.document.document_id,
            base_revision: destination.revision,
            command: { kind: 'paste_statements' },
        })).rejects.toThrow('请同时复制所依赖的局部语句')
        expect(store.statementClipboardCount).toBe(1)
        expect(store.canPasteStatements).toBe(true)
    })

    it('clears the structural clipboard when the workspace project changes', async () => {
        const source = twoWaitSnapshot()
        apiMocks.getProgram.mockResolvedValueOnce(source)
        const store = useProgramStore()
        await store.connect(workspace)
        await store.applyUiCommand({
            document_id: source.document.document_id,
            base_revision: source.revision,
            command: { kind: 'copy_statements', statement_ids: ['stmt-wait'] },
        })
        expect(store.statementClipboardCount).toBe(1)

        const nextWorkspace = {
            ...workspace,
            workspace_id: 'workspace-other-project',
            generation: workspace.generation + 1,
            project_id: 'project-other',
            project_path: 'D:/Other',
        }
        apiMocks.getProgram.mockResolvedValueOnce(snapshot())
        await store.connect(nextWorkspace)

        expect(store.statementClipboardCount).toBe(0)
        expect(store.canPasteStatements).toBe(false)
    })

    it('keeps cut deferred and treats a paste inside the cut range as a no-op', async () => {
        const original = twoWaitSnapshot()
        apiMocks.getProgram.mockResolvedValueOnce(original)
        const store = useProgramStore()
        await store.connect(workspace)
        store.setSelectedStatementIds(['stmt-wait', 'stmt-wait-2'])

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: original.revision,
            command: { kind: 'cut_statements', statement_ids: ['stmt-wait', 'stmt-wait-2'] },
        })
        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
        expect(store.pendingCutStatementIds).toEqual(['stmt-wait', 'stmt-wait-2'])

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: original.revision,
            command: { kind: 'paste_statements' },
        })
        expect(apiMocks.applyCommand).not.toHaveBeenCalled()
        expect(store.pendingCutStatementIds).toEqual([])
        expect(store.selectedStatementIds).toEqual(['stmt-wait', 'stmt-wait-2'])
    })

    it('updates one shared parameter through a single atomic command bundle', async () => {
        const original = twoWaitSnapshot()
        apiMocks.getProgram.mockResolvedValueOnce(original)
        apiMocks.applyCommands.mockResolvedValueOnce(twoWaitSnapshot('b'))
        const store = useProgramStore()
        await store.connect(workspace)

        await store.applyUiCommand({
            document_id: 'doc-main', base_revision: original.revision,
            command: {
                kind: 'batch_update_values',
                statement_ids: ['stmt-wait', 'stmt-wait-2'],
                parameter_id: 'official.wait.duration.parameter.duration',
                next: { kind: 'literal', value_type: 'duration', value: { milliseconds: 3000 } },
            },
        })

        expect(apiMocks.applyCommands).toHaveBeenCalledOnce()
        expect(apiMocks.applyCommands).toHaveBeenCalledWith(
            workspace, 'func-main', original.revision, [
                expect.objectContaining({
                    kind: 'update_argument', statement_id: 'stmt-wait',
                    value: { value_id: 'value-duration', kind: 'duration', milliseconds: 3000 },
                }),
                expect.objectContaining({
                    kind: 'update_argument', statement_id: 'stmt-wait-2',
                    value: { value_id: 'value-duration-2', kind: 'duration', milliseconds: 3000 },
                }),
            ],
        )
        expect(store.selectedStatementIds).toEqual(['stmt-wait', 'stmt-wait-2'])
    })
})
