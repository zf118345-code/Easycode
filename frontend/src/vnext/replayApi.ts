import { VNextApiError } from './api'
import type { WorkspaceIdentity } from './types'
import type {
    RecordingStartOptions,
    RecordingState,
    ReplayAnalysisCatalogResult,
    ReplayAnalysisReport,
    ReplayComparison,
    ReplayExportResult,
    ReplaySessionDetail,
    ReplaySessionSummary,
    ReplayTimelineItem,
    ReplayVerification,
} from './replayTypes'

function headers(workspace: WorkspaceIdentity): Record<string, string> {
    return {
        'Content-Type': 'application/json',
        'X-Workspace-Id': workspace.workspace_id,
        'X-Workspace-Generation': String(workspace.generation),
    }
}

async function request<T>(workspace: WorkspaceIdentity, url: string, init: RequestInit = {}): Promise<T> {
    let response: Response
    try {
        response = await fetch(url, { ...init, headers: { ...headers(workspace), ...(init.headers || {}) } })
    } catch (error) {
        if ((error as { name?: string } | null)?.name === 'AbortError') throw error
        throw new VNextApiError('无法连接 EasyCode 后端。请确认应用服务仍在运行。', 503)
    }
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
        const detail = payload?.detail
        const message = typeof detail === 'string'
            ? detail
            : String(detail?.message || payload?.message || `请求失败 (${response.status})`)
        throw new VNextApiError(message, response.status, String(detail?.error_id || ''), String(detail?.code || ''))
    }
    return payload as T
}

async function blob(workspace: WorkspaceIdentity, url: string, signal?: AbortSignal): Promise<Blob> {
    let response: Response
    try {
        response = await fetch(url, { headers: headers(workspace), signal })
    } catch (error) {
        if ((error as { name?: string } | null)?.name === 'AbortError') throw error
        throw new VNextApiError('无法加载录制画面。', 503)
    }
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        const detail = payload?.detail
        throw new VNextApiError(
            typeof detail === 'string' ? detail : String(detail?.message || `请求失败 (${response.status})`),
            response.status,
        )
    }
    return response.blob()
}

export const replayApi = {
    sessions: async (workspace: WorkspaceIdentity) =>
        (await request<{ sessions: ReplaySessionSummary[] }>(workspace, '/api/vnext/replay/sessions')).sessions,
    session: (workspace: WorkspaceIdentity, sessionId: string) =>
        request<ReplaySessionDetail>(workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}`),
    timeline: (workspace: WorkspaceIdentity, sessionId: string, offset = 0, limit = 2000) =>
        request<{ total: number; offset: number; limit: number; items: ReplayTimelineItem[]; issues: Array<Record<string, unknown>> }>(
            workspace,
            `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/timeline?offset=${offset}&limit=${limit}`,
        ),
    frames: (workspace: WorkspaceIdentity, sessionId: string, offset = 0, limit = 200) =>
        request<{ total: number; offset: number; limit: number; frames: import('./replayTypes').ReplayFrame[]; issues: Array<Record<string, unknown>> }>(
            workspace,
            `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/frames?offset=${offset}&limit=${limit}`,
        ),
    status: (workspace: WorkspaceIdentity) =>
        request<RecordingState>(workspace, '/api/vnext/recording/status'),
    start: (workspace: WorkspaceIdentity, options: RecordingStartOptions) =>
        request<RecordingState>(workspace, '/api/vnext/recording/start', { method: 'POST', body: JSON.stringify(options) }),
    stop: (workspace: WorkspaceIdentity, reason: 'user_stopped' | 'user_cancelled' = 'user_stopped') =>
        request<RecordingState>(workspace, '/api/vnext/recording/stop', { method: 'POST', body: JSON.stringify({ reason }) }),
    mark: (workspace: WorkspaceIdentity, label: string) =>
        request<Record<string, unknown>>(workspace, '/api/vnext/recording/mark', {
            method: 'POST', body: JSON.stringify({ label }),
        }),
    frameBlob: (workspace: WorkspaceIdentity, sessionId: string, frameIndex: number, signal?: AbortSignal) =>
        blob(workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/frames/${frameIndex}/image`, signal),
    thumbnailBlob: (workspace: WorkspaceIdentity, sessionId: string, frameIndex: number, signal?: AbortSignal) =>
        blob(workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/frames/${frameIndex}/image?thumbnail=true`, signal),
    verify: (workspace: WorkspaceIdentity, sessionId: string) =>
        request<ReplayVerification>(workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/verify`, { method: 'POST' }),
    catalog: (workspace: WorkspaceIdentity) =>
        request<ReplayAnalysisCatalogResult>(workspace, '/api/vnext/replay/analysis-catalog'),
    analyzeFrame: (
        workspace: WorkspaceIdentity, sessionId: string, frameIndex: number, analysisIds: string[],
    ) => request<Record<string, unknown>>(workspace, '/api/vnext/replay/analyze-frame', {
        method: 'POST', body: JSON.stringify({ session_id: sessionId, frame_index: frameIndex, analysis_ids: analysisIds }),
    }),
    analyzeSession: (workspace: WorkspaceIdentity, sessionId: string, analysisIds: string[]) =>
        request<Record<string, unknown>>(workspace, '/api/vnext/replay/analyze-session', {
            method: 'POST',
            body: JSON.stringify({
                session_id: sessionId, changes_only: false, step: 1, max_frames: 1000, analysis_ids: analysisIds,
            }),
        }),
    reports: async (workspace: WorkspaceIdentity, sessionId: string) =>
        (await request<{ reports: ReplayAnalysisReport[] }>(
            workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/analyses`,
        )).reports,
    deleteReport: (workspace: WorkspaceIdentity, sessionId: string, analysisRunId: string) =>
        request<Record<string, unknown>>(
            workspace,
            `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/analyses/${encodeURIComponent(analysisRunId)}`,
            { method: 'DELETE' },
        ),
    compare: (workspace: WorkspaceIdentity, sessionId: string, left: number, right: number) =>
        request<ReplayComparison>(workspace, '/api/vnext/replay/compare', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId, left_frame_index: left, right_frame_index: right }),
        }),
    comparisonBlob: (
        workspace: WorkspaceIdentity, sessionId: string, left: number, right: number, signal?: AbortSignal,
    ) => blob(
        workspace,
        `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/comparison.png?left_frame_index=${left}&right_frame_index=${right}`,
        signal,
    ),
    createExport: (
        workspace: WorkspaceIdentity,
        sessionId: string,
        mode: 'default' | 'reproducible',
        analysisRunIds: string[],
        includeCategories: string[],
        frameIndices: number[] = [],
    ) => request<ReplayExportResult>(workspace, '/api/vnext/replay/export', {
        method: 'POST',
        body: JSON.stringify({
            session_id: sessionId,
            mode,
            analysis_run_ids: analysisRunIds,
            include_categories: includeCategories,
            frame_indices: frameIndices,
        }),
    }),
    exportBlob: (workspace: WorkspaceIdentity, sessionId: string, exportId: string) =>
        blob(workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}/exports/${encodeURIComponent(exportId)}`),
    deleteSession: (workspace: WorkspaceIdentity, sessionId: string) =>
        request<Record<string, unknown>>(
            workspace, `/api/vnext/replay/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' },
        ),
}
