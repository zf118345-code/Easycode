// frontend/src/api/executionApi.js
// 执行引擎 + 调试控制接口
import client from './client'

export const executionApi = {
    // ===== 执行基础控制 =====
    status: (executionId) => client.get(`/api/execution/${executionId}`),
    stop: (executionId) => client.post(`/api/execution/${executionId}/stop`),

    // ===== 调试控制（Pause / Resume / Step / State / Variables） =====
    pause: (executionId) => client.post(`/api/execution/${executionId}/pause`),
    resume: (executionId) => client.post(`/api/execution/${executionId}/resume`),
    step: (executionId, kind = 'over') => client.post(
        `/api/execution/${executionId}/step`, { step: kind }
    ),
    getDebugState: (executionId) => client.get(`/api/execution/${executionId}/debug`),
    getVariables: (executionId, level = 0) => client.get(
        `/api/execution/${executionId}/variables`, { params: { level } }
    ),

    // ===== 断点动态下发 =====
    setBreakpoints: (executionId, nodeIds) => client.post(
        `/api/execution/${executionId}/breakpoints`, { breakpoints: nodeIds || [] }
    ),
    addBreakpoint: (executionId, nodeId) => client.post(
        `/api/execution/${executionId}/breakpoints/add`, { node_id: nodeId }
    ),
    removeBreakpoint: (executionId, nodeId) => client.post(
        `/api/execution/${executionId}/breakpoints/remove`, { node_id: nodeId }
    )
}
