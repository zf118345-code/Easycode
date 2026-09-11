export interface PlayerConsoleExecution {
    execution_id: string
    status: 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
    error?: string
    events?: Array<{ sequence?: number; timestamp?: string; category?: string; message?: string }>
}

export interface PlayerConsoleSession {
    instance_id: string
    instance_name: string
    product_id: string
    process_id: number
    port: number
    status: string
    frame_url: string
    execution: PlayerConsoleExecution | null
    error_id?: string
    error_message?: string
}

export interface PlayerConsoleInstallation {
    installation_id: string
    product_id: string
    display_name: string
    release_id: string
    enabled: boolean
}

export interface PlayerConsoleInstance {
    instance_id: string
    installation_id: string
    product_id: string
    display_name: string
    revision: number
    enabled: boolean
    status: string
    error_message?: string
    installation?: PlayerConsoleInstallation
    console: PlayerConsoleSession
}

export interface PlayerConsoleBootstrap {
    schema_version: 1
    installations: PlayerConsoleInstallation[]
    instances: PlayerConsoleInstance[]
}

export interface PlayerConsoleCloseStatus {
    schema_version: 1
    active_count: number
    active_instances: Array<{ instance_id: string; instance_name: string; status: string }>
    ready?: boolean
    requires_confirmation?: boolean
    stopped_instance_count?: number
}

function messageFrom(payload: unknown, fallback: string): string {
    if (!payload || typeof payload !== 'object') return fallback
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object') {
        return String((detail as { message?: unknown }).message || fallback)
    }
    return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(path, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) throw new Error(messageFrom(payload, `请求失败 (${response.status})`))
    return payload as T
}

async function downloadZip(path: string): Promise<Blob> {
    const response = await fetch(path)
    if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new Error(messageFrom(payload, `诊断包生成失败 (${response.status})`))
    }
    const contentType = String(response.headers.get('content-type') || '').toLocaleLowerCase()
    const blob = await response.blob()
    const signature = new Uint8Array(await blob.slice(0, 2).arrayBuffer())
    if (!contentType.includes('application/zip') || blob.size < 22 || signature[0] !== 0x50 || signature[1] !== 0x4b) {
        throw new Error('诊断服务没有返回有效 ZIP，请刷新实例后重试')
    }
    return blob
}

export const playerConsoleApi = {
    bootstrap: () => request<PlayerConsoleBootstrap>('/api/vnext/player-console'),
    closeStatus: () => request<PlayerConsoleCloseStatus>('/api/vnext/player-console/lifecycle/close-status'),
    prepareClose: (stop_active: boolean) => request<PlayerConsoleCloseStatus>(
        '/api/vnext/player-console/lifecycle/prepare-close',
        { method: 'POST', body: JSON.stringify({ stop_active }) },
    ),
    createInstance: (installation_id: string) => request<{ instance: PlayerConsoleInstance }>(
        '/api/vnext/player-console/instances',
        { method: 'POST', body: JSON.stringify({ installation_id }) },
    ),
    deleteInstance: (instance_id: string, expected_revision: number) => request<{ ok: boolean; instance_id: string; recovery_path?: string; retained_path?: string }>(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}`,
        { method: 'DELETE', body: JSON.stringify({ expected_revision }) },
    ),
    connect: (instance_id: string) => request<PlayerConsoleSession>(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}/connect`,
        { method: 'POST' },
    ),
    state: (instance_id: string) => request<PlayerConsoleSession>(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}/state`,
    ),
    downloadDiagnostics: (instance_id: string) => downloadZip(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}/diagnostics`,
    ),
    control: (instance_id: string, action: 'pause' | 'resume' | 'stop') => request(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}/${action}`,
        { method: 'POST' },
    ),
    restart: (instance_id: string) => request<PlayerConsoleSession>(
        `/api/vnext/player-console/instances/${encodeURIComponent(instance_id)}/restart`,
        { method: 'POST' },
    ),
}
