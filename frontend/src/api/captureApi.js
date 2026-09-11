import client from './client'

export const captureApi = {
    registerSession: payload => client.post('/api/capture/session/register', payload),
    unregisterSession: sessionId => client.post('/api/capture/session/unregister', { session_id: sessionId }),
    trigger: (payload = {}) => client.post('/api/capture/trigger', payload),
    prewarm: () => client.post('/api/capture/prewarm'),
    replay: (recordingSessionId, frameIndex, sessionId = '') => client.post('/api/capture/replay', {
        recording_session_id: recordingSessionId,
        frame_index: frameIndex,
        session_id: sessionId
    }),
    createSnapshot: (projectPath, sessionId) => client.post('/api/capture/snapshot', {
        project_path: projectPath,
        session_id: sessionId
    }),
    getSnapshot: (snapshotId, includeImage = true) => client.get(
        `/api/capture/snapshot/${encodeURIComponent(snapshotId)}`,
        { params: { include_image: includeImage } }
    ),
    close: snapshotId => client.post('/api/capture/close', { snapshot_id: snapshotId }),
    listDirectories: projectPath => client.get('/api/capture/directories', { params: { project_path: projectPath } }),
    saveAssets: payload => client.post('/api/capture/assets', payload),
    undoAssets: transactionId => client.post('/api/capture/assets/undo', { transaction_id: transactionId }),
    // 后端超时会投递同 operation_id 的补偿回滚；客户端略晚超时，避免
    // 浏览器先放弃请求而后端仍在等待确认。
    requestAction: payload => client.post('/api/capture/action', payload, { timeout: 45000 }),
    acknowledgeAction: (requestId, result) => client.post('/api/capture/action/ack', {
        request_id: requestId,
        result
    })
}
