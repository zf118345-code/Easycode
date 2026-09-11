export type PlatformId = 'windows' | 'android_adb' | 'android_local'
/** Platform selected for one concrete check/run. `no_target` is not a target definition. */
export type ExecutionPlatformId = PlatformId | 'no_target'

export interface WorkspaceIdentity {
    workspace_id: string
    generation: number
    project_id: string
    project_name: string
    project_path: string
    read_only: boolean
}

export interface ParameterDefinition {
    parameter_id: string
    name: string
    /** Business-facing field name published by vNext contracts. */
    display_name?: string
    value_type: string
    required: boolean
    default: unknown
    description: string
    constraints?: {
        min?: number
        max?: number
        step?: number
        choices?: Array<unknown | { label: string; value: unknown; platforms?: PlatformId[] }>
        [key: string]: unknown
    }
    ui?: ParameterUiContract
}

export interface ParameterChoiceOption {
    label: string
    value: unknown
    disabled?: boolean
}

export type ParameterControlType =
    | 'text'
    | 'number'
    | 'toggle'
    | 'select'
    | 'slider-number'
    | 'duration'
    | 'time'
    | 'color'
    | 'coordinate'
    | 'region'
    | 'resource'
    | 'control-selector'
    | 'gesture-path'
    | 'file'
    | 'directory'
    | 'control-reference'
    | 'instance'
    | 'target'
    | 'application'
    | 'instance-multi-select'
    | 'key-chord'
    | 'json'
    | 'list'
    | 'key-value'
    | 'expression'
export type ParameterEditorStrategy =
    | 'scalar'
    | 'reference'
    | 'capture'
    | 'inline_record'
    | 'row_list'
    | 'focused'
export interface ParameterUiAction {
    id: 'choose-resource' | 'capture-image' | 'pick-point' | 'pick-region' | 'pick-color' | 'capture-control' | 'capture-path' | string
    capture_kind?: 'point' | 'region' | 'image' | 'color' | 'control' | 'path'
    platforms?: PlatformId[]
    /** Optional presentation/capture hints published by the function contract. */
    default_category?: AssetCategoryId
    title?: string
    max_rects?: number
    min_points?: number
    max_points?: number
    result_reference_type?: string
}
export interface ParameterUiContract {
    control: ParameterControlType
    editor_strategy?: ParameterEditorStrategy
    type_hint?: 'hidden' | 'label' | 'suffix'
    action_placement?: 'adjacent'
    actions?: ParameterUiAction[]
    unit?: string
    placeholder?: string
    help?: string
    importance?: 'primary' | 'advanced' | 'contextual' | 'internal'
    effective_default_label?: string
    visible_when?: {
        parameter_id?: string
        field_id?: string
        operator?: 'equals' | 'not_equals' | 'greater_than' | 'truthy'
        value?: unknown
    }
    player_supported?: boolean
    [key: string]: unknown
}

export interface FunctionDefinition {
    function_id: string
    namespace: string
    name: string
    qualified_name: string
    label: string
    category: string
    parameters: ParameterDefinition[]
    return_type: string
    description: string
    platforms: PlatformId[]
    capabilities: string[]
    opcode: string
    scope?: 'platform' | 'project' | 'shared' | string
    source_kind?: 'native' | 'easy' | 'python' | string
    source_path?: string
    editable?: boolean
    deletable?: boolean
    version?: string
}

export interface RuntimeEvent {
    sequence: number
    timestamp: string
    level: 'info' | 'warning' | 'error'
    category: string
    message: string
    instruction_id: string
}

export interface RuntimeValueEntry {
    id: string
    display_name: string
    value_type: string
    kind: 'parameter' | 'result' | 'local' | 'loop' | 'error' | 'message' | 'project' | string
    value: unknown
}

export interface RuntimeSession {
    execution_id: string
    status: 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
    started_at: string
    finished_at: string
    error: string
    events: RuntimeEvent[]
    event_cursor?: number
    oldest_event_sequence?: number
    events_truncated?: boolean
    event_log_available?: boolean
    worker?: { pid: number; started: boolean; isolated: boolean }
    current_instruction_id: string
    current_source: {
        function_id?: string
        statement_id?: string
        value_id?: string
        [key: string]: unknown
    }
    variables: Record<string, unknown>
    project_variables?: Record<string, unknown>
    value_entries?: {
        local: RuntimeValueEntry[]
        project: RuntimeValueEntry[]
    }
    breakpoints: string[]
    diagnostic_available: boolean
    failure_frame_available: boolean
    recording?: PlayerRecordingStatus
}

export interface DebugSettings {
    schema_version: 2
    breakpoints: Record<string, string[]>
}

export type PlayerRecordingStrategy = 'all_frames' | 'changed_frames' | 'diagnostic'

export interface PlayerRecordingSettings {
    enabled: boolean
    strategy: PlayerRecordingStrategy
    target_fps: number
    max_duration_ms: number
    max_session_bytes: number
    min_free_bytes: number
    confirmed_profile_revision?: number | null
}

export interface PlayerRecordingStatus {
    active: boolean
    status: string
    recording_session_id?: string
    strategy?: PlayerRecordingStrategy
    terminal_reason?: string
    last_error?: string
    frame_count?: number
    capture_count?: number
    dropped_frame_count?: number
    disk_bytes?: number
    queue_depth?: number
    queue_capacity?: number
    target_id?: string
    requested_enabled?: boolean
    reason?: string
}

export interface PlayerRecordingSessionSummary {
    session_id: string
    started_at?: string
    stopped_at?: string
    status?: string
    terminal_reason?: string
    strategy?: PlayerRecordingStrategy
    target_title?: string
    frame_count?: number
    capture_count?: number
    dropped_frame_count?: number
    disk_bytes?: number
    final?: boolean
    issue_count?: number
}

export interface PlayerRecordingFrame {
    frame_id: string
    sequence: number
    captured_at?: string
    width?: number
    height?: number
    bytes?: number
}

export interface PlayerRecordingSessionDetail extends PlayerRecordingSessionSummary {
    session?: PlayerRecordingSessionSummary
    frames: PlayerRecordingFrame[]
    frame_total?: number
    segments?: Record<string, unknown>[]
    drops?: Record<string, unknown>[]
    terminal?: Record<string, unknown> | null
}

export type AndroidScheduleTrigger =
    | { kind: 'one_time'; at: string }
    | { kind: 'daily'; local_time: string; timezone_id: string }
    | { kind: 'interval'; anchor_time: string; interval_ms: number }

export interface AndroidPlayerSchedule {
    schedule_id: string
    revision: number
    name: string
    enabled: boolean
    profile_id: string
    profile_name: string
    profile_revision_at_save: number
    trigger: AndroidScheduleTrigger
    misfire_policy: 'skip' | 'run_once'
    max_lateness_ms: number
    overlap_policy: 'skip' | 'queue_once'
    next_trigger_at: string
    pending_once?: boolean
}

export interface AndroidScheduleOccurrence {
    occurrence_id: string
    dispatch_id: string
    schedule_id: string
    scheduled_at: string
    discovered_at: string
    profile_name: string
    status: string
    reason?: string
    message?: string
    run_id?: string
    finished_at?: string
}

export interface TargetIdentity {
    target_id: string
    name: string
}

export type WindowsWorkArea =
    | { mode: 'client' }
    | { mode: 'window' }
    | { mode: 'desktop' }
    | { mode: 'region'; region: [number, number, number, number] }

export interface CapturedWindowBinding {
    binding_version: 1
    binding_id: string
    title: string
    class_name: string
    executable_name: string
    hwnd: number
    process_id: number
    process_started_at_ms: number
    captured_at: string
}

export interface WindowsTargetDefinition extends TargetIdentity {
    type: 'windows'
    window_title: string
    window_match: 'contains' | 'exact' | 'regex'
    work_area: WindowsWorkArea
    allow_physical_fallback: boolean
    window_binding?: CapturedWindowBinding
}

export interface AndroidAdbTargetDefinition extends TargetIdentity {
    type: 'android_adb'
    device_serial: string
}

export interface AdbDeviceCandidate {
    serial: string
    state: string
    selectable: boolean
    model: string
    product: string
    transport_id: string
    display_name: string
}

export interface AdbDeviceCandidateResult {
    available: boolean
    code: string
    message: string
    candidates: AdbDeviceCandidate[]
}

export interface AndroidLocalTargetDefinition extends TargetIdentity {
    type: 'android_local'
}

export type TargetDefinition =
    | WindowsTargetDefinition
    | AndroidAdbTargetDefinition
    | AndroidLocalTargetDefinition

export interface TargetConfiguration {
    schema_version: 1
    targets: TargetDefinition[]
    default_target_id: string | null
    revision: string
}

export interface TargetReferenceDefinition {
    kind: string
    path?: string
    function_id?: string
    function_name?: string
    statement_id?: string
    value_id?: string
    variable_id?: string
    variable_name?: string
    asset_id?: string
    control_id?: string
    profile_id?: string
    field?: string
    field_path?: string
    location?: string
}

export type AssetCategoryId = 'image' | 'ocr' | 'page'

export interface AssetCategory {
    id: AssetCategoryId
    label: string
    folders: string[]
}

export interface AssetCaptureProvenance {
    platform: string
    target_id: string
    work_area: [number, number, number, number] | null
    captured_at: string
    host: string
    selection_rect: [number, number, number, number] | null
    reference_size: [number, number] | null
    coordinate_space: string
}

export interface AssetDefinition {
    asset_id: string
    display_name: string
    category: AssetCategoryId
    folder: string
    path: string
    extension: string
    mime_type: string
    size_bytes: number
    width: number | null
    height: number | null
    sha256: string
    source: string
    created_at: string
    updated_at: string
    aliases: string[]
    /** Diagnostic provenance only; runtime search regions remain call-site data. */
    capture: AssetCaptureProvenance | null
}

export interface AssetReferenceDefinition {
    kind: string
    path: string
    document_id?: string
    function_id?: string
    statement_id?: string
    parameter_id?: string
    value_id?: string
    field_path?: string
    preview?: string
    line?: number
}

export type PlayerControlType = ParameterControlType | 'button'
export type PlayerBinding =
    | { kind: 'project_variable'; variable_id: string }
    | { kind: 'function_parameter'; function_id: string; parameter_id: string }
    | { kind: 'statement_parameter'; function_id: string; statement_id: string; parameter_id: string }
    | { kind: 'function_action'; function_id: string }
    | { kind: 'setting'; target_id: string; setting_id: string }
export interface PlayerTargetSettingDefinition {
    setting_id: string
    type: ParameterControlType
    label: string
    value_type: string
    constraints: Record<string, unknown>
    target_types: TargetDefinition['type'][]
    options?: Array<{ label: string; value: unknown }>
    type_fingerprint: string
}
export interface PlayerBindingContract {
    schema_version: 3
    type_fingerprint_contract: string
    binding_kinds: Array<{ kind: PlayerBinding['kind']; required_fields: string[] }>
    unsupported: Array<{ kind: string; error_code: string; reason: string }>
    target_settings: PlayerTargetSettingDefinition[]
}
export interface PlayerControlOption {
    label: string
    value: unknown
    fixed_value?: boolean
    fixed_reason?: string
}
export interface PlayerBindingSourceDefinition {
    source_id: string
    kind: PlayerBinding['kind']
    label: string
    path: Array<{ id: string; label: string }>
    binding: PlayerBinding
    required: boolean
    value_type?: string
    type_fingerprint?: string
    constraints?: Record<string, unknown>
    recommended_control: PlayerControlType
    options?: PlayerControlOption[]
    platforms: PlatformId[]
    parameter_ui?: ParameterUiContract
    default?: unknown
}
export interface PlayerBindingSources {
    schema_version: 3
    available: boolean
    unavailable_reason: string
    diagnostics: Array<Record<string, unknown>>
    sources: PlayerBindingSourceDefinition[]
}
export interface PlayerControlDefinition {
    control_id: string
    type: PlayerControlType
    label: string
    help: string
    default?: unknown
    options: PlayerControlOption[]
    required: boolean
    binding: PlayerBinding
    layout: { span: number }
    parameter_ui?: ParameterUiContract
    constraints?: ParameterDefinition['constraints']
    platforms?: PlatformId[]
    source_type?: string
    type_fingerprint?: string
    terminal_actions?: Array<{ action_id: ParameterUiAction['id']; platforms: PlatformId[] }>
    override?: { active: boolean; asset_id: string; file_name: string }
}
export interface PlayerPageDefinition {
    page_id: string
    title: string
    controls: PlayerControlDefinition[]
}
export interface PlayerFormDefinition {
    schema_version: 3
    title: string
    icon_asset_id?: string
    features?: {
        recording: boolean
    }
    pages: PlayerPageDefinition[]
}

export interface PlayerRuntimeBootstrap {
    available: boolean
    bundle?: { project_id: string; release_id: string; name: string; created_at: string }
    form?: PlayerFormDefinition
    targets?: TargetDefinition[]
    default_target_id?: string | null
    assets?: { categories: AssetCategory[]; assets: AssetDefinition[] }
    updates?: PlayerUpdatesResponse
    host_feedback?: {
        ok: boolean
        message: string
        control_id?: string
    }
}

export type UpdateLifecycleState =
    | 'disabled' | 'idle' | 'checking' | 'available' | 'downloading' | 'staged'
    | 'waiting_safe_point' | 'awaiting_platform_install' | 'applying' | 'verifying'
    | 'complete' | 'failed' | 'rolled_back'

export interface UpdatePreferences {
    automatic_check: boolean
    automatic_download: boolean
    automatic_apply: boolean
}

export interface PlayerUpdateDomainStatus {
    enabled: boolean
    state: UpdateLifecycleState
    current_release_id: string
    current_release_sequence: number
    selected_release?: { release_id: string; release_sequence: number; display_version: string; notes?: string } | null
    selected_artifact?: { artifact_id: string; length: number; platform: string; architecture: string } | null
    download_path?: string
    staged_slot?: string
    last_error?: { code: string; message: string } | null
    last_checked_at?: string
    platform_message?: string
    automatic_checks: boolean
    required_policy_capability: boolean
    can_start_task: boolean
    policy_block?: { code: string; message: string; target_release_id: string; grace_deadline: string } | null
    preferences: UpdatePreferences
}

export interface PlayerUpdatesResponse {
    enabled: boolean
    domains: Partial<Record<'player_application' | 'project_content', PlayerUpdateDomainStatus>>
    telemetry?: false
    task_execution_requires_network?: false
}

export interface PlayerLanPermissions {
    messages: boolean
    status: boolean
    remote_start: boolean
    allowed_products?: string[]
    allowed_instances?: string[]
}

export interface PlayerLanPeer {
    host_id: string
    device_name: string
    platform: string
    fingerprint: string
    permissions: PlayerLanPermissions
    remote_permissions: PlayerLanPermissions
    addresses: string[]
    port: number
    last_connected_at?: string
    last_error_id?: string
}

export interface PlayerLanPairingSession {
    session_id: string
    code?: string
    qr_payload?: string
    short_fingerprint?: string
    addresses: string[]
    port: number
    expires_at: string
    pending?: Array<{ pending_id: string; host_id: string; device_name: string; platform: string; fingerprint: string; status: string }>
}

export interface PlayerLanStatus {
    available: boolean
    running: boolean
    identity: { host_id: string; device_name: string; platform: string; fingerprint: string }
    addresses: string[]
    port: number
    paired_devices: PlayerLanPeer[]
    remote_instances: Array<{ host_id: string; instance_id: string; display_name: string; project_namespace: string; status?: string }>
    pairing_sessions: PlayerLanPairingSession[]
}

export interface PlayerMessageInstance {
    project_namespace: string
    host_id: string
    instance_id: string
    display_name: string
    reference: Record<string, unknown>
}

export interface PlayerMessageStatus {
    instance: PlayerMessageInstance
    batches: Array<{ batch_id: string; name: string; created_at_ms: number; expires_at_ms: number }>
    copies: Array<{ message_id: string; batch_id: string; recipient_display_name: string; status: string; transport_kind: string; transport_error?: string; created_at: string; expires_at: string }>
}

export interface AuthorUpdateDomainConfiguration {
    enabled: boolean
    product_id: string
    provider: 'easycode_hosted' | 'self_hosted'
    feed_base_url: string
    channel: 'test' | 'stable'
    required_policy_capability: boolean
    initial_preferences: UpdatePreferences
    pinned_root: Record<string, unknown> | null
}

export interface AuthorUpdateConfiguration {
    schema_version: 1
    domains: {
        player_application: AuthorUpdateDomainConfiguration
        project_content: AuthorUpdateDomainConfiguration
    }
}

export interface PlayerDangerousOperationRequirement {
    confirmation_id: string
    statement_id: string
    function_id: 'official.directory.delete_tree'
    display_name: string
    display_path: string
    authorization_root_id: string
    execution_config_revision: string
    contract_fingerprint: string
}

export interface PlayerDangerousOperationConfirmation {
    confirmation_id: string
    confirmed: true
}

export interface PlayerEnvironmentCheck {
    ready: boolean
    target_id: string | null
    checked_at: string
    duration_ms?: number
    checks: Array<{ id: string; status: 'pass' | 'warning' | 'fail'; message: string; size?: number[] }>
}

export interface PlayerProfile {
    profile_id: string
    name: string
    target_id: string | null
    values: Record<string, unknown>
    revision: number
    image_overrides: Record<string, { file: string; file_name: string; sha256: string }>
    recording: PlayerRecordingSettings
    created_at: string
    updated_at: string
}

export interface PlayerControlDestination {
    product_id: string
    release_id: string
    profile_id: string
    control_id: string
    action_id: ParameterUiAction['id']
    profile_revision: number
    /** Empty only for host-local file/directory selection in a no-target profile. */
    target_id: string
}

export interface PlayerTerminalActionAvailability {
    control_id: string
    action_id: ParameterUiAction['id']
    platform: PlatformId
    capability: string
    enabled: boolean
    disabled_reason: string
    destination: PlayerControlDestination
}

export interface PlayerTerminalActionsResponse {
    platform: PlatformId | null
    profile_id: string | null
    profile_revision: number | null
    blocked_reason: string
    actions: PlayerTerminalActionAvailability[]
}
