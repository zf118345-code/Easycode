import { VNextApiError } from './api'
import type {
    HubInstallation,
    HubInstance,
    HubStatus,
    LanDiagnostic,
    LanPairingOffer,
    LanPermissions,
    LanStatus,
    ScheduleBatch,
    ScheduleDiagnostic,
    ScheduleDispatch,
    ScheduleOccurrence,
    SchedulePlan,
} from './scheduleTypes'

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(url, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
        const detail = payload?.detail && typeof payload.detail === 'object' ? payload.detail : {}
        throw new VNextApiError(
            String(detail.message || payload?.message || `请求失败 (${response.status})`),
            response.status,
            String(detail.error_id || ''),
            String(detail.code || ''),
            Boolean(detail.recovery?.retryable),
            String(detail.recovery?.action || ''),
            Array.isArray(detail.diagnostics) ? detail.diagnostics : [],
        )
    }
    return payload as T
}

export const scheduleApi = {
    hubStatus: () => request<HubStatus>('/api/vnext/player-hub'),
    installations: () => request<HubInstallation[]>('/api/vnext/player-hub/installations'),
    registerInstallation: (distribution_root: string, instance_name: string) =>
        request<HubInstallation>('/api/vnext/player-hub/installations', {
            method: 'POST', body: JSON.stringify({ distribution_root, instance_name }),
        }),
    instances: () => request<HubInstance[]>('/api/vnext/player-hub/instances'),
    createInstance: (installation_id: string, name: string) =>
        request<HubInstance>('/api/vnext/player-hub/instances', {
            method: 'POST', body: JSON.stringify({ installation_id, name }),
        }),
    openInstance: (instance_id: string) => request<{ ok: true; process_id: number }>(
        `/api/vnext/player-hub/instances/${encodeURIComponent(instance_id)}/open`,
        { method: 'POST' },
    ),
    openConsole: (product_id = '') => request<{ ok: true; process_id: number }>(
        `/api/vnext/player-hub/console/open${product_id ? `?product_id=${encodeURIComponent(product_id)}` : ''}`,
        { method: 'POST' },
    ),
    bindRelease: (instance_id: string, installation_id: string, expected_revision: number) =>
        request<HubInstance>(`/api/vnext/player-hub/instances/${encodeURIComponent(instance_id)}/release`, {
            method: 'PUT', body: JSON.stringify({ installation_id, expected_revision }),
        }),
    batches: () => request<ScheduleBatch[]>('/api/vnext/player-hub/batches'),
    saveBatch: (batch: ScheduleBatch) => batch.batch_id
        ? request<ScheduleBatch>(`/api/vnext/player-hub/batches/${encodeURIComponent(batch.batch_id)}`, {
            method: 'PUT', body: JSON.stringify(batchPayload(batch, true)),
        })
        : request<ScheduleBatch>('/api/vnext/player-hub/batches', {
            method: 'POST', body: JSON.stringify(batchPayload(batch, false)),
        }),
    deleteBatch: (batch_id: string, revision: number) => request<{ ok: true }>(
        `/api/vnext/player-hub/batches/${encodeURIComponent(batch_id)}?expected_revision=${revision}`,
        { method: 'DELETE' },
    ),
    plans: () => request<SchedulePlan[]>('/api/vnext/schedules'),
    savePlan: (plan: SchedulePlan) => plan.schedule_id
        ? request<SchedulePlan>(`/api/vnext/schedules/${encodeURIComponent(plan.schedule_id)}`, {
            method: 'PUT', body: JSON.stringify(planPayload(plan, true)),
        })
        : request<SchedulePlan>('/api/vnext/schedules', {
            method: 'POST', body: JSON.stringify(planPayload(plan, false)),
        }),
    deletePlan: (schedule_id: string, revision: number) => request<{ ok: true }>(
        `/api/vnext/schedules/${encodeURIComponent(schedule_id)}?expected_revision=${revision}`,
        { method: 'DELETE' },
    ),
    occurrences: () => request<ScheduleOccurrence[]>('/api/vnext/schedules/occurrences?limit=500'),
    dispatches: (occurrence_id = '') => request<ScheduleDispatch[]>(
        `/api/vnext/schedules/dispatches?limit=1000${occurrence_id ? `&occurrence_id=${encodeURIComponent(occurrence_id)}` : ''}`,
    ),
    diagnostics: () => request<ScheduleDiagnostic[]>('/api/vnext/schedules/diagnostics?limit=1000'),
    installAgent: () => request<{ ok: true }>('/api/vnext/player-hub/agent/install', { method: 'POST' }),
    uninstallAgent: () => request<{ ok: true }>('/api/vnext/player-hub/agent', { method: 'DELETE' }),
    checkNow: () => request('/api/vnext/player-hub/tick', { method: 'POST' }),
    lanStatus: () => request<LanStatus>('/api/vnext/player-hub/lan'),
    startLan: () => request<LanStatus>('/api/vnext/player-hub/lan/listener', { method: 'POST' }),
    stopLan: () => request<{ ok: true; state: string }>('/api/vnext/player-hub/lan/listener', { method: 'DELETE' }),
    discoverLan: (port?: number) => request<Record<string, unknown>[]>('/api/vnext/player-hub/lan/discovery', {
        method: 'POST', body: JSON.stringify({ timeout_seconds: 1, ...(port ? { port } : {}) }),
    }),
    createPairingSession: () => request<LanPairingOffer>('/api/vnext/player-hub/lan/pairing-sessions', {
        method: 'POST', body: JSON.stringify({ ttl_ms: 300_000 }),
    }),
    beginPairing: (payload: {
        address?: string
        port?: number
        code?: string
        session_id?: string
        qr_payload?: string
        permissions: LanPermissions
    }) => request<Record<string, unknown>>('/api/vnext/player-hub/lan/pairing/begin', {
        method: 'POST', body: JSON.stringify(payload),
    }),
    completePairing: (pairing: Record<string, unknown>, expected_fingerprint: string) =>
        request('/api/vnext/player-hub/lan/pairing/complete', {
            method: 'POST', body: JSON.stringify({ pairing, expected_fingerprint }),
        }),
    confirmPairing: (pending_id: string, permissions: LanPermissions) =>
        request(`/api/vnext/player-hub/lan/pairing-pending/${encodeURIComponent(pending_id)}/confirm`, {
            method: 'POST', body: JSON.stringify({ permissions }),
        }),
    setLanPermissions: (host_id: string, permissions: LanPermissions) =>
        request(`/api/vnext/player-hub/lan/peers/${encodeURIComponent(host_id)}/permissions`, {
            method: 'PATCH', body: JSON.stringify(permissions),
        }),
    revokeLanPeer: (host_id: string) => request(
        `/api/vnext/player-hub/lan/peers/${encodeURIComponent(host_id)}`,
        { method: 'DELETE' },
    ),
    refreshLanPeer: (host_id: string) => request(
        `/api/vnext/player-hub/lan/peers/${encodeURIComponent(host_id)}/refresh`,
        { method: 'POST' },
    ),
    lanDiagnostics: () => request<LanDiagnostic[]>('/api/vnext/player-hub/lan/diagnostics?limit=500'),
}

function entryPayload(entry: ScheduleBatch['entries'][number]) {
    return {
        ...(entry.entry_id ? { entry_id: entry.entry_id } : {}),
        enabled: entry.enabled,
        host_id: entry.host_id,
        instance_id: entry.instance_id,
        product_id: entry.product_id,
        profile_id: entry.profile_id,
        start_offset_seconds: entry.start_offset_seconds || 0,
        start_deadline_seconds: entry.start_deadline_seconds,
    }
}

function batchPayload(batch: ScheduleBatch, update: boolean) {
    return {
        ...(batch.batch_id ? { batch_id: batch.batch_id } : {}),
        ...(update ? { expected_revision: batch.revision } : {}),
        name: batch.name,
        dispatch_mode: batch.dispatch_mode,
        entries: batch.entries.map(entryPayload),
    }
}

function planPayload(plan: SchedulePlan, update: boolean) {
    return {
        ...(plan.schedule_id ? { schedule_id: plan.schedule_id } : {}),
        ...(update ? { expected_revision: plan.revision } : {}),
        name: plan.name,
        enabled: plan.enabled,
        timezone_id: plan.timezone_id,
        trigger: plan.trigger,
        misfire_policy: plan.misfire_policy,
        max_lateness_seconds: plan.max_lateness_seconds,
        overlap_policy: plan.overlap_policy,
        dispatch_mode: plan.dispatch_mode,
        entries: plan.entries.map(entryPayload),
    }
}
