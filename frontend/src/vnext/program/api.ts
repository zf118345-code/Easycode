import type { ExecutionPlatformId, WorkspaceIdentity } from '../types'
import type {
    AvailableFunctionContractDto,
    ProgramApiErrorDetail,
    ProgramCompileResponse,
    ProgramDeleteResponseDto,
    ProgramExtractResponseDto,
    ProgramHistoryDto,
    ProgramRunRequest,
    ProgramRunResponse,
    ProgramServerCommand,
    ProgramSnapshotDto,
    ProgramSummaryDto,
    ProgramValueCatalogDto,
    ProjectVariableReferenceDto,
    ProjectVariableSnapshotDto,
    ServerProgramValueNode,
} from './serverTypes'

interface RequestOptions extends RequestInit {
    timeoutMs?: number
}

interface RetainedRunKey {
    key: string
    expires_at: number
}

const RUN_KEY_TTL_MS = 5 * 60_000
const retainedRunKeys = new Map<string, RetainedRunKey>()

export class ProgramApiError extends Error {
    readonly status: number
    readonly code: string
    readonly requestId: string
    readonly retryable: boolean
    readonly recoveryAction: string
    readonly recoveryMessage: string
    readonly diagnostics: Array<Record<string, unknown>>

    constructor(
        message: string,
        options: {
            status?: number
            code?: string
            requestId?: string
            retryable?: boolean
            recoveryAction?: string
            recoveryMessage?: string
            diagnostics?: Array<Record<string, unknown>>
        } = {},
    ) {
        super(message)
        this.name = 'ProgramApiError'
        this.status = options.status || 0
        this.code = options.code || ''
        this.requestId = options.requestId || ''
        this.retryable = Boolean(options.retryable)
        this.recoveryAction = options.recoveryAction || 'none'
        this.recoveryMessage = options.recoveryMessage || ''
        this.diagnostics = options.diagnostics || []
    }
}

function workspaceHeaders(workspace: WorkspaceIdentity): Record<string, string> {
    return {
        'X-Workspace-ID': workspace.workspace_id,
        'X-Workspace-Generation': String(workspace.generation),
    }
}

function newRunKey(functionId: string): string {
    const suffix = globalThis.crypto?.randomUUID?.()
        || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
    return `program-run-${functionId.replace(/[^A-Za-z0-9_.:-]/g, '-').slice(0, 80)}-${suffix}`
}

function runSignature(
    workspace: WorkspaceIdentity,
    functionId: string,
    payload: ProgramRunRequest,
): string {
    return JSON.stringify([
        workspace.workspace_id,
        workspace.generation,
        functionId,
        payload.target_platform || null,
        payload.target_id || null,
        payload.debug || {},
    ])
}

function retainedRunKey(signature: string, functionId: string): string {
    const now = Date.now()
    for (const [key, entry] of retainedRunKeys) {
        if (entry.expires_at <= now) retainedRunKeys.delete(key)
    }
    const retained = retainedRunKeys.get(signature)
    if (retained) return retained.key
    while (retainedRunKeys.size >= 64) {
        const oldest = retainedRunKeys.keys().next().value
        if (!oldest) break
        retainedRunKeys.delete(oldest)
    }
    const key = newRunKey(functionId)
    retainedRunKeys.set(signature, { key, expires_at: now + RUN_KEY_TTL_MS })
    return key
}

function apiErrorFromPayload(status: number, payload: unknown): ProgramApiError {
    const envelope = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {}
    const rawDetail = envelope.detail
    const detail = rawDetail && typeof rawDetail === 'object'
        ? rawDetail as ProgramApiErrorDetail
        : null
    const message = detail?.message
        || (typeof rawDetail === 'string' ? rawDetail : '')
        || (typeof envelope.message === 'string' ? envelope.message : '')
        || `请求失败 (${status})`
    return new ProgramApiError(message, {
        status,
        code: detail?.code || (typeof envelope.code === 'string' ? envelope.code : ''),
        requestId: detail?.request_id || (typeof envelope.request_id === 'string' ? envelope.request_id : ''),
        retryable: detail?.recovery?.retryable,
        recoveryAction: detail?.recovery?.action,
        recoveryMessage: detail?.recovery?.message,
        diagnostics: (detail?.diagnostics || []) as Array<Record<string, unknown>>,
    })
}

async function request<T>(url: string, init: RequestOptions = {}): Promise<T> {
    const { timeoutMs = 30_000, ...requestInit } = init
    const controller = new AbortController()
    let timedOut = false
    const abortFromCaller = () => controller.abort(init.signal?.reason)
    if (init.signal?.aborted) abortFromCaller()
    else init.signal?.addEventListener('abort', abortFromCaller, { once: true })
    const timeout = timeoutMs > 0
        ? globalThis.setTimeout(() => {
            timedOut = true
            controller.abort()
        }, timeoutMs)
        : null

    try {
        const response = await fetch(url, {
            ...requestInit,
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                ...(requestInit.headers || {}),
            },
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw apiErrorFromPayload(response.status, payload)
        return payload as T
    } catch (error) {
        if (error instanceof ProgramApiError) throw error
        if (timedOut) {
            throw new ProgramApiError('请求超时。请确认 EasyCode 后端仍在运行，然后重试。', {
                status: 408,
                code: 'request_timeout',
                retryable: true,
                recoveryAction: 'retry',
            })
        }
        if ((error as { name?: string } | null)?.name === 'AbortError') {
            throw new ProgramApiError('请求已取消。', { status: 499, code: 'request_cancelled' })
        }
        throw new ProgramApiError('无法连接 EasyCode 后端。请确认服务仍在运行。', {
            status: 503,
            code: 'service_unavailable',
            retryable: true,
            recoveryAction: 'retry',
        })
    } finally {
        if (timeout !== null) globalThis.clearTimeout(timeout)
        init.signal?.removeEventListener('abort', abortFromCaller)
    }
}

export const programApi = {
    startOperationRecording(workspace: WorkspaceIdentity, payload: {
        function_id: string; expected_revision: string; target_id: string; location: Record<string, unknown>
    }): Promise<Record<string, unknown>> {
        return request('/api/vnext/operation-recording/start', {
            method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify(payload),
        })
    },

    stopOperationRecording(workspace: WorkspaceIdentity, sessionId: string): Promise<Record<string, unknown>> {
        return request(`/api/vnext/operation-recording/${encodeURIComponent(sessionId)}/stop`, {
            method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify({ reason: 'user' }),
        })
    },

    commitOperationRecording(workspace: WorkspaceIdentity, sessionId: string, reviewEvents: Record<string, unknown>[]): Promise<{ program: ProgramSnapshotDto; inserted_command_count: number }> {
        return request(`/api/vnext/operation-recording/${encodeURIComponent(sessionId)}/commit`, {
            method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify({ review_events: reviewEvents }),
        })
    },

    cancelOperationRecording(workspace: WorkspaceIdentity, sessionId: string): Promise<Record<string, unknown>> {
        return request(`/api/vnext/operation-recording/${encodeURIComponent(sessionId)}`, {
            method: 'DELETE', headers: workspaceHeaders(workspace),
        })
    },

    getTriggers(workspace: WorkspaceIdentity): Promise<{ schema_version: number; revision: string; triggers: Array<Record<string, unknown>> }> {
        return request('/api/vnext/triggers', { headers: workspaceHeaders(workspace) })
    },

    saveTrigger(workspace: WorkspaceIdentity, expectedRevision: string, trigger: Record<string, unknown>): Promise<{ schema_version: number; revision: string; triggers: Array<Record<string, unknown>> }> {
        return request('/api/vnext/triggers', {
            method: 'PUT', headers: workspaceHeaders(workspace), body: JSON.stringify({ expected_revision: expectedRevision, trigger }),
        })
    },

    deleteTrigger(workspace: WorkspaceIdentity, triggerId: string, expectedRevision: string): Promise<{ schema_version: number; revision: string; triggers: Array<Record<string, unknown>> }> {
        return request(`/api/vnext/triggers/${encodeURIComponent(triggerId)}`, {
            method: 'DELETE', headers: workspaceHeaders(workspace), body: JSON.stringify({ expected_revision: expectedRevision }),
        })
    },
    async listAvailableFunctions(): Promise<AvailableFunctionContractDto[]> {
        const response = await request<{ functions: AvailableFunctionContractDto[] }>('/api/vnext/functions')
        // Defense in depth: the IDE must not advertise planned contracts even
        // if a future backend accidentally returns the complete registry.
        return response.functions.filter((item) => item.implementation_state === 'available')
    },

    async listPrograms(workspace: WorkspaceIdentity): Promise<ProgramSummaryDto[]> {
        const response = await request<{ programs: ProgramSummaryDto[] }>('/api/vnext/programs', {
            headers: workspaceHeaders(workspace),
        })
        return response.programs
    },

    createProgram(workspace: WorkspaceIdentity, displayName: string): Promise<ProgramSnapshotDto> {
        return request('/api/vnext/programs', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ display_name: displayName }),
        })
    },

    getProgram(workspace: WorkspaceIdentity, functionId: string): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}`, {
            headers: workspaceHeaders(workspace),
        })
    },

    getProgramHistory(workspace: WorkspaceIdentity, functionId: string): Promise<ProgramHistoryDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/history`, {
            headers: workspaceHeaders(workspace),
        })
    },

    restoreProgramHistory(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
        historyId: string,
    ): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/history/restore`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, history_id: historyId }),
        })
    },

    renameProgram(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
        displayName: string,
    ): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}`, {
            method: 'PATCH',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, display_name: displayName }),
        })
    },

    deleteProgram(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
    ): Promise<ProgramDeleteResponseDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}`, {
            method: 'DELETE',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision }),
        })
    },

    getProjectVariables(workspace: WorkspaceIdentity): Promise<ProjectVariableSnapshotDto> {
        return request('/api/vnext/project-variables', { headers: workspaceHeaders(workspace) })
    },

    createProjectVariable(
        workspace: WorkspaceIdentity,
        expectedRevision: string,
        payload: {
            display_name: string; value_type: string; default_value: ServerProgramValueNode
            description?: string; constraints?: Record<string, unknown>
        },
    ): Promise<ProjectVariableSnapshotDto> {
        return request('/api/vnext/project-variables', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, ...payload }),
        })
    },

    updateProjectVariable(
        workspace: WorkspaceIdentity,
        variableId: string,
        expectedRevision: string,
        changes: {
            display_name?: string; value_type?: string; default_value?: ServerProgramValueNode
            description?: string; constraints?: Record<string, unknown>
        },
    ): Promise<ProjectVariableSnapshotDto> {
        return request(`/api/vnext/project-variables/${encodeURIComponent(variableId)}`, {
            method: 'PATCH',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, ...changes }),
        })
    },

    deleteProjectVariable(
        workspace: WorkspaceIdentity,
        variableId: string,
        expectedRevision: string,
    ): Promise<ProjectVariableSnapshotDto> {
        return request(`/api/vnext/project-variables/${encodeURIComponent(variableId)}`, {
            method: 'DELETE',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision }),
        })
    },

    async getProjectVariableReferences(
        workspace: WorkspaceIdentity,
        variableId: string,
    ): Promise<ProjectVariableReferenceDto[]> {
        const response = await request<{ references: ProjectVariableReferenceDto[] }>(
            `/api/vnext/project-variables/${encodeURIComponent(variableId)}/references`,
            { headers: workspaceHeaders(workspace) },
        )
        return response.references
    },

    applyCommand(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
        command: ProgramServerCommand,
    ): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/commands`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, command }),
        })
    },

    applyCommands(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
        commands: ProgramServerCommand[],
    ): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/commands/batch`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision, commands }),
        })
    },

    extractStatements(
        workspace: WorkspaceIdentity,
        functionId: string,
        expectedRevision: string,
        statementIds: string[],
        displayName: string,
    ): Promise<ProgramExtractResponseDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/extract`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({
                expected_revision: expectedRevision,
                statement_ids: statementIds,
                display_name: displayName,
            }),
        })
    },

    getValueCatalog(
        workspace: WorkspaceIdentity,
        functionId: string,
        statementId: string,
        expectedType: string,
        scopeBindings: Array<{ symbol_id: string; display_name: string; value_type: string }> = [],
    ): Promise<ProgramValueCatalogDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/value-catalog`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({
                statement_id: statementId,
                expected_type: expectedType,
                scope_bindings: scopeBindings.map(({ symbol_id, display_name, value_type }) => ({
                    symbol_id, display_name, value_type,
                })),
            }),
        })
    },

    undo(workspace: WorkspaceIdentity, functionId: string, expectedRevision: string): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/undo`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision }),
        })
    },

    redo(workspace: WorkspaceIdentity, functionId: string, expectedRevision: string): Promise<ProgramSnapshotDto> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/redo`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ expected_revision: expectedRevision }),
        })
    },

    compile(
        workspace: WorkspaceIdentity,
        functionId: string,
        targetPlatform?: ExecutionPlatformId,
    ): Promise<ProgramCompileResponse> {
        return request(`/api/vnext/programs/${encodeURIComponent(functionId)}/compile`, {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ target_platform: targetPlatform || null }),
        })
    },

    async run(
        workspace: WorkspaceIdentity,
        functionId: string,
        payload: ProgramRunRequest = {},
    ): Promise<ProgramRunResponse> {
        const signature = runSignature(workspace, functionId, payload)
        const idempotencyKey = retainedRunKey(signature, functionId)
        try {
            const result = await request<ProgramRunResponse>(`/api/vnext/programs/${encodeURIComponent(functionId)}/run`, {
                method: 'POST',
                headers: {
                    ...workspaceHeaders(workspace),
                    'Idempotency-Key': idempotencyKey,
                },
                body: JSON.stringify({
                    target_platform: payload.target_platform || null,
                    target_id: payload.target_id || null,
                    debug: payload.debug || {},
                }),
                timeoutMs: 60_000,
            })
            retainedRunKeys.delete(signature)
            return result
        } catch (error) {
            const uncertain = error instanceof ProgramApiError
                && (error.status === 408 || error.status >= 500)
            if (!uncertain) retainedRunKeys.delete(signature)
            throw error
        }
    },
}
