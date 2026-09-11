import type { TargetDefinition, WorkspaceIdentity } from './types'

export type RecordingStrategy = 'all_frames' | 'changed_frames' | 'diagnostic'

export interface RecordingState {
    active: boolean
    status: string
    recording_session_id?: string
    session_id: string
    strategy: RecordingStrategy | string
    frame_count: number
    capture_count: number
    dropped_frame_count: number
    policy_skipped_frame_count: number
    disk_bytes: number
    elapsed_ms: number
    terminal_reason: string
    last_error: string
    target_id: string
    target_title: string
    owned_by_current_workspace?: boolean
}

export interface RecordingStartOptions {
    target_id: string
    target_fps: number
    queue_capacity: number
    recording_mode: RecordingStrategy
    change_threshold: number
    max_duration_ms: number
    max_session_bytes: number
    min_free_bytes: number
    diagnostic_pre_frames: number
    diagnostic_post_frames: number
}

export interface ReplaySessionSummary {
    session_id: string
    recording_format: number
    project_name: string
    started_at: string
    stopped_at: string
    status: string
    terminal_reason: string
    strategy: RecordingStrategy | string
    target_id: string
    target_kind: string
    target_title: string
    frame_count: number
    capture_count: number
    segment_count: number
    marker_count: number
    drop_event_count: number
    dropped_frame_count: number
    policy_skipped_frame_count: number
    total_bytes: number
    locked: boolean
    final: boolean
    recovered: boolean
    integrity: string
    issue_count: number
}

export interface ReplaySegment {
    event: 'opened' | 'closed'
    recording_segment_id: string
    opened_at?: string
    closed_at?: string
    start_capture_sequence?: number
    end_capture_sequence?: number
    target_id?: string
    target_kind?: string
    target_title?: string
    space_version?: string
    orientation?: string
    width?: number
    height?: number
    dpi?: number
    reason?: string
}

export interface ReplayMarker {
    kind: string
    marker_id: string
    label: string
    capture_sequence: number
    nearest_frame_id?: string
    marked_at: string
    recording_segment_id?: string
}

export interface ReplayDrop {
    kind: 'backpressure' | 'policy_filtered' | string
    drop_id: string
    reason: string
    start_capture_sequence: number
    end_capture_sequence: number
    count: number
    started_at: string
    ended_at: string
    recording_segment_id?: string
}

export interface ReplayFrame {
    kind?: 'frame'
    frame_id: string
    sequence: number
    capture_sequence: number
    captured_at: string
    timestamp_ns: number
    width: number
    height: number
    orientation: string
    dpi: number
    target_id: string
    target_kind: string
    target_title: string
    recording_segment_id: string
    space_version: string
    screen_region: number[]
    change_score: number
    bytes: number
    sha256: string
    file: string
}

export type ReplayTimelineItem =
    | (ReplayFrame & { kind: 'frame'; sort_sequence: number })
    | (ReplayMarker & { kind: 'marker'; sort_sequence: number })
    | (ReplayDrop & { kind: 'drop'; sort_sequence: number })

export interface ReplaySessionDetail extends ReplaySessionSummary {
    segments: ReplaySegment[]
    markers: ReplayMarker[]
    drops: ReplayDrop[]
    terminal: Record<string, unknown> | null
    issues: Array<Record<string, unknown>>
}

export interface ReplayAnalysisCatalogItem {
    analysis_id: string
    function_id: 'official.image.find' | 'official.image.find_all' | 'official.text.recognize'
    owner_function_id: string
    statement_id: string
    display_name: string
    side_effect_free: true
    implementation: 'official_dedicated_adapter'
}

export interface ReplayAnalysisCatalogResult {
    available: boolean
    unavailable_reason: string
    diagnostics: Array<Record<string, unknown>>
    analyses: ReplayAnalysisCatalogItem[]
}

export interface ReplayAnalysisReport {
    analysis_report_format: number
    analysis_run_id: string
    recording_session_id: string
    analysis_input_bundle_id: string
    input_content_digest: string
    created_at: string
    scope: string
    previous_analysis_run_id?: string | null
    reproducibility: string
    result: Record<string, unknown>
    immutable: true
}

export interface ReplayVerification {
    session_id: string
    ok: boolean
    integrity: string
    verified_frame_count: number
    frame_count: number
    issues: Array<Record<string, unknown>>
}

export interface ReplayComparison {
    session_id: string
    left_frame_index: number
    right_frame_index: number
    width: number
    height: number
    identical: boolean
    difference_box: number[] | null
    changed_pixel_ratio: number
    mean_channel_difference: number
}

export interface ReplayExportResult {
    export_id: string
    mode: 'default' | 'reproducible'
    bytes: number
    sha256: string
    privacy: Record<string, unknown>
}

export interface ReplayWorkspaceContext {
    workspace: WorkspaceIdentity
    targets: TargetDefinition[]
}
