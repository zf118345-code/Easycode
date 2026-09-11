import type {
    AssetCategory,
    AssetDefinition,
    AssetReferenceDefinition,
    AuthorUpdateConfiguration,
    FunctionDefinition,
    PlayerBindingContract,
    PlayerBindingSources,
    PlayerControlDestination,
    PlayerDangerousOperationConfirmation,
    PlayerDangerousOperationRequirement,
    PlayerEnvironmentCheck,
    PlayerFormDefinition,
    PlayerProfile,
    PlayerRecordingSettings,
    PlayerRecordingStatus,
    PlayerRuntimeBootstrap,
    PlayerUpdatesResponse,
    UpdatePreferences,
    PlayerTerminalActionsResponse,
    RuntimeSession,
    TargetDefinition,
    TargetConfiguration,
    AdbDeviceCandidateResult,
    DebugSettings,
    TargetReferenceDefinition,
    WorkspaceIdentity,
} from './types'

interface WorkspaceOpenResult {
    workspace: WorkspaceIdentity | null
    inspection: Record<string, unknown>
    targets?: TargetDefinition[]
    default_target_id?: string | null
    revision?: string
}

export interface PlayerRuntimeRunPayload {
    target_id?: string | null
    player_values?: Record<string, unknown>
    action_control_id?: string
    profile_id?: string
    profile_revision?: number
    message_instance_id?: string
    dangerous_confirmations?: PlayerDangerousOperationConfirmation[]
}

export interface IdeViewState {
    schema_version: 1
    active_view: 'program' | 'resources' | 'variables' | 'targets' | 'replay' | 'extensions' | 'schedules' | 'player'
    active_function_id: string
    collapsed_statement_ids: Record<string, string[]>
    scroll_offsets: Record<string, number>
    panel_sizes: Record<string, number>
}

export interface IdeSettings {
    schema_version: 1
    shortcuts: Record<string, string>
    defaults: Record<string, string>
}

interface RequestOptions extends RequestInit {
    timeoutMs?: number
}

interface IdempotencyEntry {
    key: string
    expiresAt: number
}

const IDEMPOTENCY_TTL_MS = 5 * 60_000
const idempotencyRetryKeys = new Map<string, IdempotencyEntry>()
const idempotencyPending = new Map<string, Promise<unknown>>()

function compactFingerprint(value: string): string {
    let left = 0x811c9dc5
    let right = 0x9e3779b9
    for (let index = 0; index < value.length; index += 1) {
        const code = value.charCodeAt(index)
        left = Math.imul(left ^ code, 0x01000193)
        right = Math.imul(right ^ code, 0x85ebca6b)
    }
    return `${value.length.toString(36)}-${(left >>> 0).toString(36)}-${(right >>> 0).toString(36)}`
}

function newIdempotencyKey(operation: string): string {
    const suffix = globalThis.crypto?.randomUUID?.()
        || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
    return `ide-${operation.replace(/[^A-Za-z0-9_.:-]+/g, '-').slice(0, 80)}-${suffix}`
}

function pruneIdempotencyKeys(now: number) {
    idempotencyRetryKeys.forEach((entry, signature) => {
        if (entry.expiresAt <= now) idempotencyRetryKeys.delete(signature)
    })
    while (idempotencyRetryKeys.size > 128) {
        const oldest = idempotencyRetryKeys.keys().next().value
        if (!oldest) break
        idempotencyRetryKeys.delete(oldest)
    }
}

export class VNextApiError extends Error {
    readonly status: number
    readonly errorId: string
    readonly code: string
    readonly retryable: boolean
    readonly recoveryAction: string
    readonly diagnostics: Array<Record<string, unknown>>

    constructor(
        message: string,
        status = 0,
        errorId = '',
        code = '',
        retryable = false,
        recoveryAction = '',
        diagnostics: Array<Record<string, unknown>> = [],
    ) {
        super(message)
        this.name = 'VNextApiError'
        this.status = status
        this.errorId = errorId
        this.code = code
        this.retryable = retryable
        this.recoveryAction = recoveryAction
        this.diagnostics = diagnostics
    }
}

async function request<T>(url: string, init: RequestOptions = {}): Promise<T> {
    const { timeoutMs = 30_000, ...requestInit } = init
    const controller = new AbortController()
    let timedOut = false
    const onCallerAbort = () => controller.abort(init.signal?.reason)
    if (init.signal?.aborted) onCallerAbort()
    else init.signal?.addEventListener('abort', onCallerAbort, { once: true })
    const timeout =
        timeoutMs > 0
            ? globalThis.setTimeout(() => {
                  timedOut = true
                  controller.abort()
              }, timeoutMs)
            : null

    try {
        const response = await fetch(url, {
            ...requestInit,
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json', ...(requestInit.headers || {}) },
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) {
            const detailObject = payload?.detail && typeof payload.detail === 'object' ? payload.detail : null
            const detail = typeof payload?.detail === 'string' ? payload.detail : detailObject?.message
            const errorId = String(detailObject?.error_id || payload?.error_id || '')
            const code = String(detailObject?.code || payload?.code || '')
            const retryable = Boolean(detailObject?.recovery?.retryable)
            const recoveryAction = String(detailObject?.recovery?.action || '')
            const message = detail || payload?.message || `请求失败 (${response.status})`
            const requestId = String(detailObject?.request_id || errorId)
            const diagnostics = Array.isArray(detailObject?.diagnostics)
                ? detailObject.diagnostics.filter(
                    (item: unknown): item is Record<string, unknown> => Boolean(item) && typeof item === 'object',
                )
                : []
            throw new VNextApiError(
                requestId ? `${message}（请求编号：${requestId}）` : message,
                response.status,
                requestId,
                code,
                retryable,
                recoveryAction,
                diagnostics,
            )
        }
        return payload as T
    } catch (error) {
        if (error instanceof VNextApiError) throw error
        if (timedOut) throw new VNextApiError('请求超时。请确认 EasyCode 后端仍在运行，然后重试。', 408)
        if ((error as { name?: string } | null)?.name === 'AbortError') {
            throw new VNextApiError('请求已取消。', 499)
        }
        if (error instanceof TypeError) {
            throw new VNextApiError('无法连接 EasyCode 后端。请确认应用服务仍在运行。', 503)
        }
        throw error
    } finally {
        if (timeout !== null) globalThis.clearTimeout(timeout)
        init.signal?.removeEventListener('abort', onCallerAbort)
    }
}

async function idempotentRequest<T>(operation: string, url: string, init: RequestOptions): Promise<T> {
    const method = String(init.method || 'POST').toUpperCase()
    const body = typeof init.body === 'string' ? init.body : ''
    const signature = `${operation}:${method}:${compactFingerprint(body)}`
    const currentPending = idempotencyPending.get(signature)
    if (currentPending) return currentPending as Promise<T>

    const now = Date.now()
    pruneIdempotencyKeys(now)
    let entry = idempotencyRetryKeys.get(signature)
    if (!entry || entry.expiresAt <= now) {
        entry = { key: newIdempotencyKey(operation), expiresAt: now + IDEMPOTENCY_TTL_MS }
        idempotencyRetryKeys.set(signature, entry)
    }

    const pending = request<T>(url, {
        ...init,
        headers: { ...(init.headers || {}), 'Idempotency-Key': entry.key },
    }).then(result => {
        idempotencyRetryKeys.delete(signature)
        return result
    }).catch(error => {
        const uncertain = error instanceof VNextApiError
            && (error.retryable || [408, 499, 503, 504].includes(error.status))
        if (!uncertain) idempotencyRetryKeys.delete(signature)
        throw error
    }).finally(() => {
        idempotencyPending.delete(signature)
    })
    idempotencyPending.set(signature, pending)
    return pending
}

function workspaceHeaders(workspace: WorkspaceIdentity): Record<string, string> {
    return {
        'X-Workspace-Id': workspace.workspace_id,
        'X-Workspace-Generation': String(workspace.generation),
    }
}

export function mergeRuntimeSession(current: RuntimeSession | null, next: RuntimeSession): RuntimeSession {
    if (!current || current.execution_id !== next.execution_id) return next
    const merged = new Map(current.events.map((event) => [event.sequence, event]))
    next.events.forEach((event) => merged.set(event.sequence, event))
    const events = [...merged.values()].sort((left, right) => left.sequence - right.sequence).slice(-2000)
    return { ...current, ...next, events }
}

export const vnextApi = {
    ideSettings: () => request<IdeSettings>('/api/vnext/ide-settings'),
    saveIdeSettings: (shortcuts: Record<string, string>) => request<IdeSettings>('/api/vnext/ide-settings', {
        method: 'PUT', body: JSON.stringify({ shortcuts }),
    }),
    chooseFolder: () =>
        request<{ path: string }>('/api/vnext/workspaces/choose-folder', {
            method: 'POST',
            body: JSON.stringify({ title: '选择 EasyCode vNext 项目文件夹' }),
            timeoutMs: 0,
        }),
    chooseFile: (title = '选择文件', extensions: string[] = []) =>
        request<{ path: string }>('/api/vnext/workspaces/choose-file', {
            method: 'POST',
            body: JSON.stringify({ title, extensions }),
            timeoutMs: 0,
        }),
    inspect: (path: string) =>
        request<Record<string, unknown>>('/api/vnext/workspaces/inspect', {
            method: 'POST',
            body: JSON.stringify({ path }),
        }),
    open: (path: string, options: { initialize?: boolean; projectName?: string } = {}) =>
        request<WorkspaceOpenResult>('/api/vnext/workspaces/open', {
            method: 'POST',
            body: JSON.stringify({
                path,
                initialize: Boolean(options.initialize),
                project_name: options.projectName || '',
            }),
        }),
    recoverProgram: (payload: {
        path: string; function_id: string; history_id: string; expected_revision: string
    }) => request<{ function_id: string; revision: string; inspection: Record<string, unknown> }>(
        '/api/vnext/workspaces/recover-program', {
            method: 'POST',
            body: JSON.stringify(payload),
        },
    ),
    active: () =>
        request<{
            workspace: WorkspaceIdentity | null
            targets: TargetDefinition[]
            default_target_id: string | null
            revision: string
        }>('/api/vnext/workspaces/active'),
    debugSettings: (workspace: WorkspaceIdentity) =>
        request<DebugSettings>('/api/vnext/debug-settings', {
            headers: workspaceHeaders(workspace),
        }),
    saveDebugSettings: (workspace: WorkspaceIdentity, breakpoints: Record<string, string[]>) =>
        request<DebugSettings>('/api/vnext/debug-settings', {
            method: 'PUT',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ breakpoints }),
        }),
    viewState: (workspace: WorkspaceIdentity) => request<IdeViewState>('/api/vnext/view-state', {
        headers: workspaceHeaders(workspace),
    }),
    saveViewState: (workspace: WorkspaceIdentity, value: Omit<IdeViewState, 'schema_version'>) =>
        request<IdeViewState>('/api/vnext/view-state', {
            method: 'PUT', headers: workspaceHeaders(workspace), body: JSON.stringify(value),
        }),
    functions: () => request<{ functions: FunctionDefinition[] }>('/api/vnext/functions'),
    previewVision: (workspace: WorkspaceIdentity, payload: {
        target_id: string
        function_id: 'official.image.find' | 'official.image.find_all' | 'official.image.wait_visible' | 'official.image.wait_hidden' | 'official.image.click_once' | 'official.image.click_until_hidden' | 'official.image.click_position_until_visible' | 'official.image.click_position_until_hidden' | 'official.text.recognize' | 'official.text.match' | 'official.text.wait_visible'
        region?: number[] | null
        image_asset_id?: string
        similarity?: number
        language?: string
        preprocess?: Record<string, unknown>
        expected_text?: string
        match_mode?: string
    }) => request<{
        kind: 'image' | 'ocr'
        preview_data_url: string
        matched: boolean | null
        similarity: number | null
        threshold: number | null
        text: string
        line_count: number
        target_id: string
        captured_at: string
        requested_region: number[]
        actual_region: number[]
        region_clipped: boolean
        region_empty: boolean
    }>('/api/vnext/vision/preview', {
        method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify(payload), timeoutMs: 60_000,
    }),
    controlCaptureMode: (workspace: WorkspaceIdentity, action: 'start' | 'stop') =>
        request<Record<string, unknown>>('/api/vnext/capture/control', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ action }),
        }),
    resolveControlCapture: (workspace: WorkspaceIdentity, targetId: string, point: [number, number], referenceSize: [number, number]) =>
        request<{ candidates: Array<{ label: string; role: string; frame_rect: [number, number, number, number]; selector: Record<string, unknown> }> }>('/api/vnext/capture/control/resolve', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ target_id: targetId, point, reference_size: referenceSize }),
        }),
    resolveWindowCapture: (
        workspace: WorkspaceIdentity,
        sessionId: string,
        snapshotId: string,
        point: [number, number],
        referenceSize: [number, number],
    ) => request<{
        ok: boolean
        binding: import('./types').CapturedWindowBinding
        title: string
        application: string
        window_rect: number[]
    }>('/api/vnext/targets/windows/capture/resolve', {
        method: 'POST',
        headers: workspaceHeaders(workspace),
        body: JSON.stringify({ session_id: sessionId, snapshot_id: snapshotId, point, reference_size: referenceSize }),
    }),
    testWindowsTarget: (workspace: WorkspaceIdentity, target: import('./types').WindowsTargetDefinition) => request<{
        ok: boolean
        title: string
        application: string
        window_rect: number[]
        binding_method: string
        message: string
    }>('/api/vnext/targets/windows/test', {
        method: 'POST',
        headers: workspaceHeaders(workspace),
        body: JSON.stringify({ target }),
    }),
    targets: (workspace: WorkspaceIdentity) =>
        request<TargetConfiguration>('/api/vnext/targets', {
            headers: workspaceHeaders(workspace),
        }),
    adbCandidates: (workspace: WorkspaceIdentity) =>
        request<AdbDeviceCandidateResult>('/api/vnext/targets/adb-candidates', {
            headers: workspaceHeaders(workspace),
        }),
    targetReferences: (workspace: WorkspaceIdentity, targetId: string) =>
        request<{ target_id: string; references: TargetReferenceDefinition[] }>(
            `/api/vnext/targets/${encodeURIComponent(targetId)}/references`,
            { headers: workspaceHeaders(workspace) },
        ),
    saveTargets: (
        workspace: WorkspaceIdentity,
        expectedRevision: string,
        targets: TargetDefinition[],
        defaultTargetId: string | null,
    ) =>
        request<TargetConfiguration>('/api/vnext/targets', {
            method: 'PUT',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({
                expected_revision: expectedRevision,
                targets,
                default_target_id: defaultTargetId,
            }),
        }),
    assets: (workspace: WorkspaceIdentity) =>
        request<{ categories: AssetCategory[]; assets: AssetDefinition[] }>('/api/vnext/assets', {
            headers: workspaceHeaders(workspace),
        }),
    importAsset: (
        workspace: WorkspaceIdentity,
        payload: {
            category: string
            folder: string
            file_name: string
            display_name: string
            content_base64: string
            source?: string
            capture?: Record<string, unknown>
        }
    ) =>
        request<{ asset: AssetDefinition; duplicate_of: AssetDefinition | null }>('/api/vnext/assets', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify(payload),
        }),
    createAssetFolder: (workspace: WorkspaceIdentity, category: string, folder: string) =>
        request<{ created: boolean; path: string }>('/api/vnext/asset-folders', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ category, folder }),
        }),
    moveAssetFolder: (workspace: WorkspaceIdentity, sourcePath: string, targetParent: string, name: string) =>
        request<{ status: string; new_path: string }>('/api/vnext/asset-folders/move', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify({ source_path: sourcePath, target_parent: targetParent, name }),
        }),
    deleteAssetFolder: (workspace: WorkspaceIdentity, path: string, force = false) =>
        request<{ deleted: boolean; blocked?: boolean; requires_confirmation?: boolean; asset_count?: number; references?: AssetReferenceDefinition[] }>(
            `/api/vnext/asset-folders/${encodeURIComponent(path)}?force=${force ? 'true' : 'false'}`,
            {
                method: 'DELETE',
                headers: workspaceHeaders(workspace),
            }
        ),
    updateAsset: (
        workspace: WorkspaceIdentity,
        assetId: string,
        payload: Partial<Pick<AssetDefinition, 'display_name' | 'category' | 'folder'>>
    ) =>
        request<{ asset: AssetDefinition }>(`/api/vnext/assets/${encodeURIComponent(assetId)}`, {
            method: 'PATCH',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify(payload),
        }),
    replaceAsset: (
        workspace: WorkspaceIdentity,
        assetId: string,
        payload: { file_name: string; content_base64: string }
    ) =>
        request<{ asset: AssetDefinition }>(`/api/vnext/assets/${encodeURIComponent(assetId)}/content`, {
            method: 'PUT',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify(payload),
        }),
    assetReferences: (workspace: WorkspaceIdentity, assetId: string) =>
        request<{ references: AssetReferenceDefinition[] }>(
            `/api/vnext/assets/${encodeURIComponent(assetId)}/references`,
            {
                headers: workspaceHeaders(workspace),
            }
        ),
    deleteAsset: (workspace: WorkspaceIdentity, assetId: string, force = false, replacementAssetId = '') =>
        request<{
            deleted: boolean
            blocked?: boolean
            requires_confirmation?: boolean
            reason?: string
            message?: string
            references?: AssetReferenceDefinition[]
        }>(
            `/api/vnext/assets/${encodeURIComponent(assetId)}?force=${force ? 'true' : 'false'}&replacement_asset_id=${encodeURIComponent(replacementAssetId)}`,
            {
                method: 'DELETE',
                headers: workspaceHeaders(workspace),
            }
        ),
    assetContent: async (workspace: WorkspaceIdentity, assetId: string) => {
        const response = await fetch(`/api/vnext/assets/${encodeURIComponent(assetId)}/content`, {
            headers: workspaceHeaders(workspace),
        })
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}))
            const detail = payload?.detail
            const message = typeof detail === 'string'
                ? detail
                : detail && typeof detail === 'object' && typeof detail.message === 'string'
                    ? detail.message
                    : '资源预览加载失败'
            throw new VNextApiError(message, response.status, String(detail?.error_id || ''))
        }
        return response.blob()
    },
    playerForm: (workspace: WorkspaceIdentity) =>
        request<PlayerFormDefinition>('/api/vnext/player/form', { headers: workspaceHeaders(workspace) }),
    playerBindingContract: () => request<PlayerBindingContract>('/api/vnext/player/binding-contract'),
    playerBindingSources: (workspace: WorkspaceIdentity) =>
        request<PlayerBindingSources>('/api/vnext/player/binding-sources', {
            headers: workspaceHeaders(workspace),
        }),
    playerPreviewRun: (
        workspace: WorkspaceIdentity,
        payload: { target_id?: string | null; player_values?: Record<string, unknown>; action_control_id?: string },
    ) => idempotentRequest<RuntimeSession>(
        `player-preview:${workspace.workspace_id}:${workspace.generation}`,
        '/api/vnext/player/preview-run',
        { method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify(payload) },
    ),
    savePlayerForm: (workspace: WorkspaceIdentity, form: PlayerFormDefinition) =>
        idempotentRequest<PlayerFormDefinition>(`player-form:${workspace.workspace_id}:${workspace.generation}`, '/api/vnext/player/form', {
            method: 'PUT',
            headers: workspaceHeaders(workspace),
            body: JSON.stringify(form),
        }),
    playerPublishReport: (workspace: WorkspaceIdentity) =>
        request<{ valid: boolean; errors: Array<{ message: string; code?: string }>; warnings: Array<{ message: string; code?: string }>; source_included: boolean; required_capabilities: string[]; supported_platforms: string[]; android_build_declared: boolean; minimum_android_api: number; android_api_requirements: Array<{ display_name: string; minimum_android_api: number; statement_ids?: string[] }> }>(
            '/api/vnext/player/publish-report',
            { headers: workspaceHeaders(workspace) }
        ),
    updateConfiguration: (workspace: WorkspaceIdentity) =>
        request<{ configuration: AuthorUpdateConfiguration; enabled: boolean }>(
            '/api/vnext/updates/configuration',
            { headers: workspaceHeaders(workspace) },
        ),
    saveUpdateConfiguration: (workspace: WorkspaceIdentity, configuration: AuthorUpdateConfiguration) =>
        request<{ saved: boolean; configuration: AuthorUpdateConfiguration }>(
            '/api/vnext/updates/configuration',
            {
                method: 'PUT',
                headers: workspaceHeaders(workspace),
                body: JSON.stringify(configuration),
            },
        ),
    initializeUpdateRepository: (
        workspace: WorkspaceIdentity,
        payload: { domain: 'player_application' | 'project_content'; repository_root: string },
    ) => request<Record<string, unknown>>('/api/vnext/updates/repository/initialize', {
        method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify(payload), timeoutMs: 120_000,
    }),
    publishProjectContentUpdate: (
        workspace: WorkspaceIdentity,
        payload: { repository_root: string; platform: 'windows' | 'android'; architecture: string; display_version: string; notes: string },
    ) => request<Record<string, unknown>>('/api/vnext/updates/releases/project-content', {
        method: 'POST', headers: workspaceHeaders(workspace), body: JSON.stringify(payload), timeoutMs: 600_000,
    }),
    setUpdateRollout: (
        workspace: WorkspaceIdentity,
        payload: {
            domain: 'player_application' | 'project_content'; repository_root: string; release_id: string
            channel: 'test' | 'stable'; percent_bps: number; whitelist_codes: string[]
            whitelist_hashes: string[]; paused: boolean; rollout_id: string
        },
    ) => request<Record<string, unknown>>('/api/vnext/updates/rollout', {
        method: 'PUT', headers: workspaceHeaders(workspace), body: JSON.stringify(payload),
    }),
    setRequiredUpdatePolicy: (
        workspace: WorkspaceIdentity,
        payload: {
            domain: 'player_application' | 'project_content'; repository_root: string; release_id: string
            effective_at: string; grace_deadline: string; reason: string; platform_targets: string[]
        },
    ) => request<Record<string, unknown>>('/api/vnext/updates/required-policy', {
        method: 'PUT', headers: workspaceHeaders(workspace), body: JSON.stringify(payload),
    }),
    revokeRequiredUpdatePolicy: (
        workspace: WorkspaceIdentity,
        domain: 'player_application' | 'project_content',
        repositoryRoot: string,
    ) => request<Record<string, unknown>>('/api/vnext/updates/required-policy/revoke', {
        method: 'POST', headers: workspaceHeaders(workspace),
        body: JSON.stringify({ domain, repository_root: repositoryRoot }),
    }),
    publishPlayer: (workspace: WorkspaceIdentity) =>
        idempotentRequest<{ created: boolean; path: string; size: number; release_id: string; signature: { algorithm: string; key_id: string; public_key: string; integrity_sha256: string } }>(`player-publish:${workspace.workspace_id}:${workspace.generation}`, '/api/vnext/player/publish', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            timeoutMs: 120_000,
        }),
    playerPackageReadiness: (workspace: WorkspaceIdentity) =>
        request<{ ready: boolean; missing: string[] }>('/api/vnext/player/package-readiness', {
            headers: workspaceHeaders(workspace),
        }),
    packagePlayer: (workspace: WorkspaceIdentity) =>
        idempotentRequest<{ created: boolean; path: string; executable: string; release_id?: string; signature?: { key_id?: string } }>(`player-package:${workspace.workspace_id}:${workspace.generation}`, '/api/vnext/player/package', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            timeoutMs: 600_000,
        }),
    packageAndroidPlayer: (workspace: WorkspaceIdentity) =>
        idempotentRequest<{ apk_path: string; evidence_path: string; min_sdk: number; release_id?: string; signature?: { key_id?: string } }>(`player-android-package:${workspace.workspace_id}:${workspace.generation}`, '/api/vnext/player/android-package', {
            method: 'POST',
            headers: workspaceHeaders(workspace),
            timeoutMs: 1_800_000,
        }),
    playerRuntimeBootstrap: () => request<PlayerRuntimeBootstrap>('/api/vnext/player/runtime/bootstrap'),
    playerUpdateStatus: () => request<PlayerUpdatesResponse>('/api/vnext/player/runtime/updates'),
    playerUpdateCheck: (domain: 'player_application' | 'project_content', policyOnly = false) =>
        request<Record<string, unknown>>('/api/vnext/player/runtime/updates/check', {
            method: 'POST', body: JSON.stringify({ domain, policy_only: policyOnly }), timeoutMs: 120_000,
        }),
    playerUpdateDownload: (domain: 'player_application' | 'project_content') =>
        request<Record<string, unknown>>('/api/vnext/player/runtime/updates/download', {
            method: 'POST', body: JSON.stringify({ domain }), timeoutMs: 600_000,
        }),
    playerUpdateApply: (domain: 'player_application' | 'project_content') =>
        request<Record<string, unknown>>('/api/vnext/player/runtime/updates/apply', {
            method: 'POST', body: JSON.stringify({ domain }), timeoutMs: 600_000,
        }),
    savePlayerUpdatePreferences: (
        domain: 'player_application' | 'project_content', preferences: UpdatePreferences,
    ) => request<Record<string, unknown>>('/api/vnext/player/runtime/updates/preferences', {
        method: 'PUT', body: JSON.stringify({ domain, preferences }),
    }),
    playerUpdateGroupCode: (domain: 'player_application' | 'project_content') =>
        request<{ domain: string; group_code: string }>(`/api/vnext/player/runtime/updates/${domain}/group-code`),
    resetPlayerUpdateGroup: (domain: 'player_application' | 'project_content') =>
        request<{ domain: string; group_code: string }>('/api/vnext/player/runtime/updates/reset-group', {
            method: 'POST', body: JSON.stringify({ domain }),
        }),
    markPlayerUpdateSafePoint: (runningOrPaused: boolean, uncommittedDraft: boolean) =>
        request<PlayerUpdatesResponse>('/api/vnext/player/runtime/updates/safe-point', {
            method: 'PUT', body: JSON.stringify({ running_or_paused: runningOrPaused, uncommitted_draft: uncommittedDraft }),
        }),
    playerRuntimeRun: (payload: PlayerRuntimeRunPayload) =>
        idempotentRequest<RuntimeSession>('player-runtime-run', '/api/vnext/player/runtime/run', {
            method: 'POST',
            body: JSON.stringify(payload),
        }),
    playerRuntimeDangerousOperations: (payload: PlayerRuntimeRunPayload) =>
        request<{ operations: PlayerDangerousOperationRequirement[] }>(
            '/api/vnext/player/runtime/dangerous-operations',
            { method: 'POST', body: JSON.stringify(payload) },
        ),
    playerRuntimePreflight: (targetId?: string | null, profileId?: string | null, profileRevision?: number | null) => {
        const query = new URLSearchParams()
        if (targetId) query.set('target_id', targetId)
        if (profileId) query.set('profile_id', profileId)
        if (profileRevision != null) query.set('profile_revision', String(profileRevision))
        return request<PlayerEnvironmentCheck>(
            `/api/vnext/player/runtime/preflight${query.size ? `?${query.toString()}` : ''}`
        )
    },
    playerRuntimeProfiles: () => request<{ profiles: PlayerProfile[] }>('/api/vnext/player/runtime/profiles'),
    savePlayerRuntimeProfile: (payload: {
        profile_id?: string
        name: string
        target_id?: string | null
        values: Record<string, unknown>
        expected_revision?: number
        recording?: Omit<PlayerRecordingSettings, 'confirmed_profile_revision'> & {
            confirm_current_revision: boolean
        }
    }) =>
        request<{ saved: boolean; profile: PlayerProfile }>('/api/vnext/player/runtime/profiles', {
            method: 'PUT',
            body: JSON.stringify(payload),
        }),
    deletePlayerRuntimeProfile: (profileId: string) =>
        request<{ deleted: boolean; profile_id: string }>(
            `/api/vnext/player/runtime/profiles/${encodeURIComponent(profileId)}`,
            { method: 'DELETE' }
        ),
    playerRuntimeRecordingStatus: () =>
        request<PlayerRecordingStatus>('/api/vnext/player/runtime/recording'),
    stopPlayerRuntimeRecording: () =>
        request<PlayerRecordingStatus>('/api/vnext/player/runtime/recording/stop', { method: 'POST' }),
    playerRuntimeActions: (profileId: string, profileRevision: number | null, targetId: string | null) => {
        const query = new URLSearchParams()
        if (profileId) query.set('profile_id', profileId)
        if (profileRevision) query.set('profile_revision', String(profileRevision))
        if (targetId) query.set('target_id', targetId)
        return request<PlayerTerminalActionsResponse>(`/api/vnext/player/runtime/actions?${query.toString()}`)
    },
    startPlayerControlCapture: (destination: PlayerControlDestination, origin = '') =>
        request<{ ok: boolean; capture_id: string; state: string; destination: PlayerControlDestination; snapshot_id?: string }>('/api/vnext/player/runtime/capture/start', {
            method: 'POST',
            body: JSON.stringify({ destination, origin }),
        }),
    confirmPlayerControlCapture: (captureId: string, destination: PlayerControlDestination, result: Record<string, unknown>) =>
        request<{ ok: boolean; profile: PlayerProfile; value: unknown }>('/api/vnext/player/runtime/capture/confirm', {
            method: 'POST',
            body: JSON.stringify({ capture_id: captureId, destination, result }),
            timeoutMs: 45_000,
        }),
    cancelPlayerControlCapture: (captureId: string, destination: PlayerControlDestination) =>
        request<{ ok: boolean; cancelled: boolean }>('/api/vnext/player/runtime/capture/cancel', {
            method: 'POST',
            body: JSON.stringify({ capture_id: captureId, destination }),
        }),
    restorePlayerProfileImage: (destination: PlayerControlDestination) =>
        request<{ ok: boolean; profile: PlayerProfile; value: unknown }>('/api/vnext/player/runtime/images/restore', {
            method: 'POST',
            body: JSON.stringify({ destination }),
        }),
    runStatus: (executionId: string, afterSequence = 0) =>
        request<RuntimeSession>(
            `/api/vnext/runs/${encodeURIComponent(executionId)}${afterSequence > 0 ? `?after_sequence=${afterSequence}` : ''}`
        ),
    activeRuns: (workspace: WorkspaceIdentity) =>
        request<{ runs: RuntimeSession[] }>('/api/vnext/runs/active', {
            headers: workspaceHeaders(workspace),
        }),
    cancelRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}`, { method: 'DELETE' }),
    pauseRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}/pause`, { method: 'POST' }),
    resumeRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}/resume`, { method: 'POST' }),
    stepRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}/step`, { method: 'POST' }),
}
