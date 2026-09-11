import { afterEach, describe, expect, it, vi } from 'vitest'
import { programApi } from '../api'

const workspace = {
    workspace_id: 'workspace-6',
    generation: 8,
    project_id: 'project-6',
    project_name: 'Format 6',
    project_path: 'D:/Projects/Format6',
    read_only: false,
}

function response(payload: unknown, status = 200): Response {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: vi.fn().mockResolvedValue(payload),
    } as unknown as Response
}

describe('Program Service API adapter', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    it('sends workspace identity and exposes only available function contracts', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(response({ functions: [
                { function_id: 'available', implementation_state: 'available' },
                { function_id: 'planned', implementation_state: 'planned' },
            ] }))
            .mockResolvedValueOnce(response({ programs: [] }))
        vi.stubGlobal('fetch', fetchMock)

        expect((await programApi.listAvailableFunctions()).map((item) => item.function_id)).toEqual(['available'])
        await programApi.listPrograms(workspace)

        expect(fetchMock.mock.calls[1][0]).toBe('/api/vnext/programs')
        expect(fetchMock.mock.calls[1][1].headers).toMatchObject({
            'X-Workspace-ID': 'workspace-6',
            'X-Workspace-Generation': '8',
        })
    })

    it('preserves the structured revision conflict recovery contract', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
            detail: {
                code: 'program_revision_conflict',
                message: 'ProgramDocument 已被其他操作修改，当前命令未执行',
                request_id: 'request-7',
                recovery: { retryable: false, action: 'reload_workspace', message: '重新加载' },
                diagnostics: [{ expected_revision: 'old', actual_revision: 'new' }],
            },
        }, 409)))

        const promise = programApi.applyCommand(workspace, 'func-main', `sha256:${'a'.repeat(64)}`, {
            kind: 'delete_statement',
            statement_id: 'stmt-1',
        })

        await expect(promise).rejects.toMatchObject({
            status: 409,
            code: 'program_revision_conflict',
            requestId: 'request-7',
            recoveryAction: 'reload_workspace',
            diagnostics: [{ expected_revision: 'old', actual_revision: 'new' }],
        })
    })

    it('reuses the run idempotency key only after an uncertain transport failure', async () => {
        const session = {
            execution_id: 'run-1',
            status: 'queued',
            started_at: '',
            finished_at: '',
            error: '',
            events: [],
            current_instruction_id: '',
            current_source: {},
            variables: {},
            breakpoints: [],
            diagnostic_available: false,
            failure_frame_available: false,
        }
        const fetchMock = vi.fn()
            .mockRejectedValueOnce(new TypeError('connection reset'))
            .mockResolvedValueOnce(response(session))
            .mockResolvedValueOnce(response({ ...session, execution_id: 'run-2' }))
        vi.stubGlobal('fetch', fetchMock)
        const payload = { target_platform: 'windows' as const, target_id: 'target-main' }

        await expect(programApi.run(workspace, 'func-main', payload)).rejects.toMatchObject({ status: 503 })
        await programApi.run(workspace, 'func-main', payload)
        await programApi.run(workspace, 'func-main', payload)

        const first = (fetchMock.mock.calls[0][1].headers as Record<string, string>)['Idempotency-Key']
        const retry = (fetchMock.mock.calls[1][1].headers as Record<string, string>)['Idempotency-Key']
        const nextRun = (fetchMock.mock.calls[2][1].headers as Record<string, string>)['Idempotency-Key']
        expect(retry).toBe(first)
        expect(nextRun).not.toBe(first)
    })

    it('preserves explicit no_target for project checks instead of converting it to an unrestricted null', async () => {
        const fetchMock = vi.fn().mockResolvedValue(response({ valid: false, ecir: null, diagnostics: [] }))
        vi.stubGlobal('fetch', fetchMock)

        await programApi.compile(workspace, 'func-main', 'no_target')

        expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ target_platform: 'no_target' })
    })

    it('uses revisioned lifecycle and project-variable endpoints without client-side overwrite fallbacks', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(response({ document: {}, revision: 'program-b', diagnostics: [] }))
            .mockResolvedValueOnce(response({ deleted_function_id: 'func-helper', programs: [] }))
            .mockResolvedValueOnce(response({ schema_version: 1, variables: [], revision: 'variables-a' }))
            .mockResolvedValueOnce(response({ schema_version: 1, variables: [], revision: 'variables-b' }))
        vi.stubGlobal('fetch', fetchMock)

        await programApi.renameProgram(workspace, 'func-helper', 'program-a', '领取奖励')
        await programApi.deleteProgram(workspace, 'func-helper', 'program-b')
        await programApi.getProjectVariables(workspace)
        await programApi.createProjectVariable(workspace, 'variables-a', {
            display_name: '启用副本', value_type: 'list<string>',
            default_value: { value_id: 'value-list', kind: 'list', item_type: 'string', items: [] },
        })

        expect(fetchMock.mock.calls[0][0]).toBe('/api/vnext/programs/func-helper')
        expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ expected_revision: 'program-a', display_name: '领取奖励' })
        expect(fetchMock.mock.calls[1][1].method).toBe('DELETE')
        expect(fetchMock.mock.calls[2][0]).toBe('/api/vnext/project-variables')
        expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
            expected_revision: 'variables-a', display_name: '启用副本',
            default_value: { value_id: 'value-list', kind: 'list' },
        })
        expect(fetchMock.mock.calls[3][1].headers).toMatchObject({
            'X-Workspace-ID': 'workspace-6', 'X-Workspace-Generation': '8',
        })
    })

    it('sends stable scoped bindings when resolving a nested selector catalog', async () => {
        const fetchMock = vi.fn().mockResolvedValue(response({
            schema_version: 1, registry_version: 4, registry_hash: 'sha256:test',
            revision: 'sha256:revision', expected_type: 'int64',
            sources: [], members: [], operations: [], record: null,
        }))
        vi.stubGlobal('fetch', fetchMock)
        await programApi.getValueCatalog(
            workspace, 'function-main', 'statement-main', 'int64',
            [{ symbol_id: 'selector-item', display_name: '当前项', value_type: 'int64' }],
        )
        expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
            statement_id: 'statement-main', expected_type: 'int64',
            scope_bindings: [{
                symbol_id: 'selector-item', display_name: '当前项', value_type: 'int64',
            }],
        })
    })
})
