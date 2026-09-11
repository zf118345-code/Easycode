import type {
    PlayerControlDestination,
    AndroidPlayerSchedule,
    AndroidScheduleOccurrence,
    PlayerDangerousOperationConfirmation,
    PlayerDangerousOperationRequirement,
    PlayerEnvironmentCheck,
    PlayerProfile,
    PlayerRecordingSettings,
    PlayerRecordingFrame,
    PlayerRecordingSessionDetail,
    PlayerRecordingSessionSummary,
    PlayerRecordingStatus,
    PlayerRuntimeBootstrap,
    PlayerTerminalActionsResponse,
    PlayerUpdatesResponse,
    PlayerLanStatus,
    PlayerLanPairingSession,
    PlayerLanPermissions,
    PlayerMessageInstance,
    PlayerMessageStatus,
    RuntimeSession,
    UpdatePreferences,
} from './types'

export interface PlayerRuntimeRunPayload {
    target_id?: string | null
    player_values?: Record<string, unknown>
    action_control_id?: string
    profile_id?: string
    profile_revision?: number
    message_instance_id?: string
    dangerous_confirmations?: PlayerDangerousOperationConfirmation[]
}

interface RequestOptions extends RequestInit { timeoutMs?: number }
interface IdempotencyEntry { key: string; expiresAt: number }

const IDEMPOTENCY_TTL_MS = 5 * 60_000
const retryKeys = new Map<string, IdempotencyEntry>()
const pendingRequests = new Map<string, Promise<unknown>>()

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
    return `player-${operation.replace(/[^A-Za-z0-9_.:-]+/g, '-').slice(0, 80)}-${suffix}`
}

export class PlayerApiError extends Error {
    constructor(
        message: string,
        readonly status = 0,
        readonly requestId = '',
        readonly code = '',
        readonly retryable = false,
        readonly recoveryAction = '',
    ) {
        super(message)
        this.name = 'PlayerApiError'
    }
}

async function request<T>(url: string, init: RequestOptions = {}): Promise<T> {
    const androidBridge = typeof window !== 'undefined' ? window.EasyCodeAndroid : undefined
    if (androidBridge) {
        let envelope: {
            ok?: boolean
            status?: number
            payload?: T
            error?: { message?: string; request_id?: string; code?: string; retryable?: boolean; recovery_action?: string }
        }
        try {
            envelope = JSON.parse(androidBridge.request(JSON.stringify({
                schema_version: 1,
                method: String(init.method || 'GET').toUpperCase(),
                url,
                body: typeof init.body === 'string' && init.body ? JSON.parse(init.body) : null,
            })))
        } catch (error) {
            throw new PlayerApiError(
                error instanceof Error ? `Android Player 宿主返回了无效结果：${error.message}` : 'Android Player 宿主返回了无效结果',
                500,
                '',
                'android.host.invalid_response',
            )
        }
        if (!envelope.ok) {
            const detail = envelope.error || {}
            throw new PlayerApiError(
                detail.request_id ? `${detail.message || 'Android Player 操作失败'}（请求编号：${detail.request_id}）` : detail.message || 'Android Player 操作失败',
                Number(envelope.status || 500),
                String(detail.request_id || ''),
                String(detail.code || ''),
                Boolean(detail.retryable),
                String(detail.recovery_action || ''),
            )
        }
        return envelope.payload as T
    }
    const { timeoutMs = 30_000, ...requestInit } = init
    const controller = new AbortController()
    let timedOut = false
    const callerAbort = () => controller.abort(init.signal?.reason)
    if (init.signal?.aborted) callerAbort()
    else init.signal?.addEventListener('abort', callerAbort, { once: true })
    const timeout = timeoutMs > 0
        ? globalThis.setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
        : null
    try {
        const response = await fetch(url, {
            ...requestInit,
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json', ...(requestInit.headers || {}) },
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) {
            const detail = payload?.detail && typeof payload.detail === 'object' ? payload.detail : null
            const message = typeof payload?.detail === 'string'
                ? payload.detail
                : detail?.message || payload?.message || `请求失败 (${response.status})`
            const requestId = String(detail?.request_id || '')
            throw new PlayerApiError(
                requestId ? `${message}（请求编号：${requestId}）` : message,
                response.status,
                requestId,
                String(detail?.code || ''),
                Boolean(detail?.recovery?.retryable),
                String(detail?.recovery?.action || ''),
            )
        }
        return payload as T
    } catch (error) {
        if (error instanceof PlayerApiError) throw error
        if (timedOut) throw new PlayerApiError('请求超时。请确认 Player 服务仍在运行。', 408)
        if ((error as { name?: string } | null)?.name === 'AbortError') {
            throw new PlayerApiError('请求已取消。', 499)
        }
        if (error instanceof TypeError) throw new PlayerApiError('无法连接 Player 服务。', 503)
        throw error
    } finally {
        if (timeout !== null) globalThis.clearTimeout(timeout)
        init.signal?.removeEventListener('abort', callerAbort)
    }
}

async function idempotentRequest<T>(operation: string, url: string, init: RequestOptions): Promise<T> {
    const body = typeof init.body === 'string' ? init.body : ''
    const signature = `${operation}:${String(init.method || 'POST').toUpperCase()}:${compactFingerprint(body)}`
    const pending = pendingRequests.get(signature)
    if (pending) return pending as Promise<T>
    const now = Date.now()
    retryKeys.forEach((entry, key) => { if (entry.expiresAt <= now) retryKeys.delete(key) })
    let entry = retryKeys.get(signature)
    if (!entry) {
        entry = { key: newIdempotencyKey(operation), expiresAt: now + IDEMPOTENCY_TTL_MS }
        retryKeys.set(signature, entry)
    }
    const promise = request<T>(url, {
        ...init,
        headers: { ...(init.headers || {}), 'Idempotency-Key': entry.key },
    }).then(result => {
        retryKeys.delete(signature)
        return result
    }).catch(error => {
        if (!(error instanceof PlayerApiError)
            || (!error.retryable && ![408, 499, 503, 504].includes(error.status))) {
            retryKeys.delete(signature)
        }
        throw error
    }).finally(() => pendingRequests.delete(signature))
    pendingRequests.set(signature, promise)
    return promise
}

export function mergeRuntimeSession(current: RuntimeSession | null, next: RuntimeSession): RuntimeSession {
    if (!current || current.execution_id !== next.execution_id) return next
    const merged = new Map(current.events.map(event => [event.sequence, event]))
    next.events.forEach(event => merged.set(event.sequence, event))
    const events = [...merged.values()].sort((left, right) => left.sequence - right.sequence).slice(-2000)
    return { ...current, ...next, events }
}

export const vnextApi = {
    playerRuntimeBootstrap: () => request<PlayerRuntimeBootstrap>('/api/vnext/player/runtime/bootstrap'),
    playerRuntimeRun: (payload: PlayerRuntimeRunPayload) =>
        idempotentRequest<RuntimeSession>('runtime-run', '/api/vnext/player/runtime/run', {
            method: 'POST', body: JSON.stringify(payload),
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
            `/api/vnext/player/runtime/preflight${query.size ? `?${query.toString()}` : ''}`,
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
    }) => request<{ saved: boolean; profile: PlayerProfile }>('/api/vnext/player/runtime/profiles', {
        method: 'PUT', body: JSON.stringify(payload),
    }),
    deletePlayerRuntimeProfile: (profileId: string) =>
        request<{ deleted: boolean; profile_id: string }>(
            `/api/vnext/player/runtime/profiles/${encodeURIComponent(profileId)}`,
            { method: 'DELETE' },
        ),
    playerRuntimeRecordingStatus: () => request<PlayerRecordingStatus>('/api/vnext/player/runtime/recording'),
    stopPlayerRuntimeRecording: () =>
        request<PlayerRecordingStatus>('/api/vnext/player/runtime/recording/stop', { method: 'POST' }),
    playerRuntimeRecordingSessions: () =>
        request<{ sessions: PlayerRecordingSessionSummary[] }>('/api/vnext/player/runtime/recordings'),
    playerRuntimeRecordingSession: (sessionId: string) =>
        request<PlayerRecordingSessionDetail>(`/api/vnext/player/runtime/recordings/${encodeURIComponent(sessionId)}`),
    playerRuntimeRecordingFrame: (sessionId: string, sequence: number) =>
        request<{ frame: PlayerRecordingFrame; mime_type: string; data_base64: string }>(
            `/api/vnext/player/runtime/recordings/${encodeURIComponent(sessionId)}/frames/${sequence}`,
        ),
    deletePlayerRuntimeRecordingSession: (sessionId: string) =>
        request<{ deleted: boolean; session_id: string; released_bytes?: number }>(
            `/api/vnext/player/runtime/recordings/${encodeURIComponent(sessionId)}`,
            { method: 'DELETE' },
        ),
    createPlayerRuntimeRecordingExport: (sessionId: string) =>
        request<{ accepted?: boolean; state?: string; export_id?: string; mode?: string }>(
            `/api/vnext/player/runtime/recordings/${encodeURIComponent(sessionId)}/export`,
            { method: 'POST' },
        ),
    playerRuntimeRecordingExportBlob: async (sessionId: string, exportId: string) => {
        const response = await fetch(
            `/api/vnext/player/runtime/recordings/${encodeURIComponent(sessionId)}/exports/${encodeURIComponent(exportId)}`,
        )
        if (!response.ok) throw new PlayerApiError('录制导出下载失败', response.status)
        return response.blob()
    },
    playerRuntimeSchedules: () => request<{ schema_version: number; schedules: AndroidPlayerSchedule[]; occurrences: AndroidScheduleOccurrence[] }>(
        '/api/vnext/player/runtime/schedules',
    ),
    savePlayerRuntimeSchedule: (payload: Record<string, unknown>) => request<AndroidPlayerSchedule>(
        '/api/vnext/player/runtime/schedules', { method: 'PUT', body: JSON.stringify(payload) },
    ),
    deletePlayerRuntimeSchedule: (scheduleId: string) => request<{ deleted: boolean; schedule_id: string }>(
        `/api/vnext/player/runtime/schedules/${encodeURIComponent(scheduleId)}`, { method: 'DELETE' },
    ),
    runPlayerRuntimeScheduleNow: (scheduleId: string) => request<{ accepted: boolean; schedule_id: string }>(
        `/api/vnext/player/runtime/schedules/${encodeURIComponent(scheduleId)}/run`, { method: 'POST' },
    ),
    playerRuntimeLan: () => request<PlayerLanStatus>('/api/vnext/player/runtime/lan'),
    startPlayerRuntimeLan: () => request<PlayerLanStatus>('/api/vnext/player/runtime/lan/listener', { method: 'POST' }),
    stopPlayerRuntimeLan: () => request<{ ok: boolean; state: string }>('/api/vnext/player/runtime/lan/listener', { method: 'DELETE' }),
    createPlayerRuntimePairingSession: () => request<PlayerLanPairingSession>('/api/vnext/player/runtime/lan/pairing-sessions', { method: 'POST', body: JSON.stringify({ ttl_ms: 300_000 }) }),
    beginPlayerRuntimePairing: (payload: { address: string; port: number; code: string; session_id: string; permissions: PlayerLanPermissions }) =>
        request<Record<string, unknown>>('/api/vnext/player/runtime/lan/pairing/begin', { method: 'POST', body: JSON.stringify(payload), timeoutMs: 20_000 }),
    completePlayerRuntimePairing: (pairing: Record<string, unknown>, expectedFingerprint = '') =>
        request<Record<string, unknown>>('/api/vnext/player/runtime/lan/pairing/complete', { method: 'POST', body: JSON.stringify({ pairing, expected_fingerprint: expectedFingerprint }), timeoutMs: 20_000 }),
    confirmPlayerRuntimePairing: (pendingId: string, permissions: PlayerLanPermissions) =>
        request<Record<string, unknown>>(`/api/vnext/player/runtime/lan/pairing-pending/${encodeURIComponent(pendingId)}/confirm`, { method: 'POST', body: JSON.stringify({ permissions }) }),
    setPlayerRuntimeLanPermissions: (hostId: string, permissions: PlayerLanPermissions) =>
        request<Record<string, unknown>>(`/api/vnext/player/runtime/lan/peers/${encodeURIComponent(hostId)}/permissions`, { method: 'PATCH', body: JSON.stringify(permissions) }),
    revokePlayerRuntimeLanPeer: (hostId: string) =>
        request<Record<string, unknown>>(`/api/vnext/player/runtime/lan/peers/${encodeURIComponent(hostId)}`, { method: 'DELETE' }),
    refreshPlayerRuntimeLanPeer: (hostId: string) =>
        request<Record<string, unknown>>(`/api/vnext/player/runtime/lan/peers/${encodeURIComponent(hostId)}/refresh`, { method: 'POST', timeoutMs: 20_000 }),
    playerRuntimeMessageInstance: () => request<PlayerMessageInstance>('/api/vnext/player/runtime/messages/instance'),
    renamePlayerRuntimeMessageInstance: (displayName: string) => request<PlayerMessageInstance>('/api/vnext/player/runtime/messages/instance', { method: 'PATCH', body: JSON.stringify({ display_name: displayName }) }),
    playerRuntimeMessages: () => request<PlayerMessageStatus>('/api/vnext/player/runtime/messages'),
    flushPlayerRuntimeMessages: () => request<Record<string, unknown>>('/api/vnext/player/runtime/messages/flush', { method: 'POST', timeoutMs: 20_000 }),
    playerRuntimeActions: (profileId: string, profileRevision: number | null, targetId: string | null) => {
        const query = new URLSearchParams()
        if (profileId) query.set('profile_id', profileId)
        if (profileRevision) query.set('profile_revision', String(profileRevision))
        if (targetId) query.set('target_id', targetId)
        return request<PlayerTerminalActionsResponse>(`/api/vnext/player/runtime/actions?${query.toString()}`)
    },
    startPlayerControlCapture: (destination: PlayerControlDestination, origin = '') =>
        request<{
            ok: boolean
            capture_id: string
            state: string
            destination: PlayerControlDestination
            snapshot_id?: string
            cancelled?: boolean
            candidate?: { candidate_id: string; kind: 'file' | 'directory'; display_name: string; access: string[] }
        }>(
            '/api/vnext/player/runtime/capture/start',
            { method: 'POST', body: JSON.stringify({ destination, origin }) },
        ),
    confirmPlayerControlCapture: (
        captureId: string,
        destination: PlayerControlDestination,
        result: Record<string, unknown>,
    ) => request<{ ok: boolean; profile: PlayerProfile; value: unknown }>(
        '/api/vnext/player/runtime/capture/confirm',
        { method: 'POST', body: JSON.stringify({ capture_id: captureId, destination, result }), timeoutMs: 45_000 },
    ),
    cancelPlayerControlCapture: (captureId: string, destination: PlayerControlDestination) =>
        request<{ ok: boolean; cancelled: boolean }>('/api/vnext/player/runtime/capture/cancel', {
            method: 'POST', body: JSON.stringify({ capture_id: captureId, destination }),
        }),
    restorePlayerProfileImage: (destination: PlayerControlDestination) =>
        request<{ ok: boolean; profile: PlayerProfile; value: unknown }>('/api/vnext/player/runtime/images/restore', {
            method: 'POST', body: JSON.stringify({ destination }),
        }),
    runStatus: (executionId: string, afterSequence = 0) => request<RuntimeSession>(
        `/api/vnext/runs/${encodeURIComponent(executionId)}${afterSequence > 0 ? `?after_sequence=${afterSequence}` : ''}`,
    ),
    cancelRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}`, { method: 'DELETE' }),
    pauseRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}/pause`, { method: 'POST' }),
    resumeRun: (executionId: string) =>
        request<RuntimeSession>(`/api/vnext/runs/${encodeURIComponent(executionId)}/resume`, { method: 'POST' }),
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
        domain: 'player_application' | 'project_content',
        preferences: UpdatePreferences,
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
            method: 'PUT',
            body: JSON.stringify({ running_or_paused: runningOrPaused, uncommitted_draft: uncommittedDraft }),
        }),
    acknowledgeCaptureAction: (requestId: string, result: Record<string, unknown>) =>
        request<{ ok: boolean }>('/api/capture/action/ack', {
            method: 'POST', body: JSON.stringify({ request_id: requestId, result }),
        }),
}
