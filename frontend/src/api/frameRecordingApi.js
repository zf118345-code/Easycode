import client from './client'

export const frameRecordingApi = {
    start: (projectPath, options = undefined) => client.post('/api/frame-recording/start', {
        project_path: projectPath,
        ...(options ? { options } : {})
    }),
    stop: (reason = 'api') => client.post('/api/frame-recording/stop', { reason }),
    getStatus: () => client.get('/api/frame-recording/status'),
    mark: (label = '手动标记') => client.post('/api/frame-recording/mark', { label }),
    listSessions: projectPath => client.get('/api/frame-recording/sessions', { params: { project_path: projectPath } }),
    listFrames: (projectPath, sessionId, offset = 0, limit = 200) => client.get(
        `/api/frame-recording/sessions/${encodeURIComponent(sessionId)}/frames`,
        { params: { project_path: projectPath, offset, limit } }
    ),
    getFrameImage: (projectPath, sessionId, frameIndex) => client.get(
        `/api/frame-recording/sessions/${encodeURIComponent(sessionId)}/frames/${frameIndex}/image`,
        { params: { project_path: projectPath }, responseType: 'blob' }
    ),
    getFrameThumbnail: (projectPath, sessionId, frameIndex) => client.get(
        `/api/frame-recording/sessions/${encodeURIComponent(sessionId)}/frames/${frameIndex}/image`,
        { params: { project_path: projectPath, thumbnail: true }, responseType: 'blob' }
    ),
    analyzeFrame: (projectPath, sessionId, frameIndex, diagnostics = false) => client.post('/api/frame-recording/analyze', {
        project_path: projectPath,
        session_id: sessionId,
        frame_index: frameIndex,
        diagnostics
    }),
    analyzeSession: (projectPath, sessionId, options = {}) => client.post('/api/frame-recording/analyze-session', {
        project_path: projectPath,
        session_id: sessionId,
        ...options
    })
}
