export type TriggerType = 'once' | 'daily' | 'interval'

export interface ScheduleEntry {
    entry_id?: string
    order?: number
    enabled: boolean
    host_id: string
    instance_id: string
    product_id: string
    profile_id: string
    start_offset_seconds: number
    start_deadline_seconds: number | null
    validated_summary?: Record<string, string | number | boolean | null>
}

export interface SchedulePlan {
    schedule_id?: string
    revision?: number
    name: string
    enabled: boolean
    timezone_id: string
    trigger: Record<string, string | number>
    misfire_policy: 'skip' | 'catch_up_once'
    max_lateness_seconds: number
    overlap_policy: 'skip' | 'queue_once'
    dispatch_mode: 'simultaneous' | 'staggered'
    entries: ScheduleEntry[]
    created_by?: string
    created_at?: string
    updated_at?: string
    next_due_at?: string | null
    last_processed_due_at?: string | null
    deleted_at?: string | null
}

export interface ScheduleBatch {
    batch_id?: string
    revision?: number
    name: string
    dispatch_mode: 'simultaneous' | 'staggered'
    entries: ScheduleEntry[]
    created_at?: string
    updated_at?: string
}

export interface HubProfile {
    profile_id: string
    name: string
    target_id: string | null
    revision: number
    recording_enabled: boolean
    created_at: string
    updated_at: string
}

export interface HubInstance {
    instance_id: string
    installation_id: string
    product_id: string
    display_name: string
    data_root: string
    revision: number
    enabled: boolean
    status?: 'ready' | 'blocked'
    profiles?: HubProfile[]
    error_id?: string
    error_message?: string
    installation?: Record<string, unknown>
}

export interface HubInstallation {
    installation_id: string
    product_id: string
    release_id: string
    display_name: string
    root_path: string
    revision: number
    enabled: boolean
    signing_key_id: string
    updated_at: string
    instances: HubInstance[]
}

export interface HubStatus {
    available: boolean
    ready: boolean
    host_id: string
    owner_scope: string
    checked_at: string
    installations: HubInstallation[]
    active_run_count: number
    interactive_session: Record<string, unknown>
    wake_agent: { available?: boolean; installed?: boolean; state?: string }
    remote_dispatch: { available: boolean; state: string; error_id: string; listener?: LanStatus; authorized_peer_count?: number }
    android_system_scheduler: { available: boolean; state: string; error_id: string }
    registry_error?: { error_id: string; message: string } | null
}

export interface LanPermissions {
    messages: boolean
    status: boolean
    remote_start: boolean
    allowed_products: string[]
    allowed_instances: string[]
}

export interface LanPeer {
    host_id: string
    device_name: string
    platform: string
    public_key: string
    fingerprint: string
    addresses: string[]
    port: number
    permissions: LanPermissions
    remote_permissions: LanPermissions
    connection_state: 'online' | 'offline' | 'unknown'
    created_at: string
    updated_at: string
    last_connected_at: string | null
    last_error_id: string
    revoked: boolean
}

export interface LanRemoteInstance {
    host_id: string
    project_namespace: string
    instance_id: string
    display_name: string
    product_id: string
    profiles: HubProfile[]
    status: string
    observed_at: string
}

export interface LanPairingPending {
    pending_id: string
    host_id: string
    device_name: string
    platform: string
    fingerprint: string
    status: 'pending' | 'confirmed'
    created_at: string
}

export interface LanPairingSession {
    session_id: string
    created_at: string
    expires_at: string
    used: boolean
    cancelled: boolean
    addresses: string[]
    port: number
    pending: LanPairingPending[]
}

export interface LanStatus {
    available: boolean
    running: boolean
    identity: { host_id: string; device_name: string; platform: string; public_key: string; fingerprint: string }
    addresses: string[]
    port: number
    permissions: string[]
    paired_devices: LanPeer[]
    remote_instances: LanRemoteInstance[]
    pairing_sessions: LanPairingSession[]
    cloud_relay: { available: false; state: string }
}

export interface LanPairingOffer {
    version: number
    kind: 'easycode_pairing'
    session_id: string
    code: string
    addresses: string[]
    port: number
    host_id: string
    device_name: string
    fingerprint: string
    expires_at: string
    qr_payload: string
}

export interface LanDiagnostic {
    sequence: number
    recorded_at: string
    level: string
    event_type: string
    peer_host_id: string
    request_id: string
    correlation_id: string
    error_id: string
    details: Record<string, string | number | boolean | null>
}

export interface ScheduleOccurrence {
    occurrence_id: string
    schedule_id: string
    schedule_revision: number
    scheduled_at: string
    discovered_at: string
    trigger_source: string
    entries: ScheduleEntry[]
    status: string
    reason_code: string | null
    created_at: string
    updated_at: string
}

export interface ScheduleDispatch {
    dispatch_id: string
    occurrence_id: string
    schedule_id: string
    entry_id: string
    instance_id: string
    product_id: string
    profile_id: string
    status: string
    run_id: string | null
    error_id: string | null
    error_message: string | null
    not_before_at: string
    deadline_at: string | null
    created_at: string
    updated_at: string
}

export interface ScheduleDiagnostic {
    sequence: number
    recorded_at: string
    level: string
    event_type: string
    schedule_id: string | null
    occurrence_id: string | null
    dispatch_id: string | null
    run_id: string | null
    error_id: string | null
    details: Record<string, string | number | boolean | null>
}
