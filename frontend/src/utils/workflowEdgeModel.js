// frontend/src/utils/workflowEdgeModel.js
// 统一连线实体模型：workflow.json 与 topology.json 的 edges 完全同构
//   { edge_id, source_node, target_node, source_port, target_task?, return_on_complete?, canvas }
// source_port 一律用标准名：success / failure / branch_N / exit_N / exit
// 提供派生、建边、断边、删节点的纯函数，供 CanvasView 渲染与 CanvasPage 事件处理共用。

/**
 * 在任务组列表中查找节点，返回 { task, node }
 */
export function findNodeInTasks(tasks, nodeId) {
    for (const task of tasks || []) {
        const found = (task.nodes || []).find(n => n.node_id === nodeId)
        if (found) return { task, node: found }
    }
    return null
}

/**
 * 查找节点所属任务组
 */
export function findTaskByNodeId(tasks, nodeId) {
    return (tasks || []).find(t => (t.nodes || []).some(n => n.node_id === nodeId)) || null
}

/**
 * 画布端口名 → 标准存储名（succ→success、fail→failure，其余原样）
 */
export function normalizePort(portType) {
    if (portType === 'succ') return 'success'
    if (portType === 'fail') return 'failure'
    return portType || 'success'
}

/**
 * 从实体 edges 派生画布扁平连线（统一结构，供渲染/端口连接集合使用）
 * @returns {Array<{sourceNodeId, targetNodeId, legacyPort, edgeId, edgeIdBase, isFailFlag, extra}>}
 */
export function deriveEdges(edges) {
    return (edges || []).map(e => {
        const port = e.source_port || 'success'
        return {
            sourceNodeId: e.source_node,
            targetNodeId: e.target_node,
            legacyPort: port,
            edgeId: e.edge_id,
            edgeIdBase: e.edge_id || `e_${e.source_node}_${port}_${e.target_node}`,
            isFailFlag: port === 'failure' || port === 'fail',
            extra: {
                sourcePort: port,
                candIndex: typeof port === 'string' && port.startsWith('branch_')
                    ? (parseInt(port.split('_')[1], 10) || 0)
                    : undefined
            }
        }
    })
}

/**
 * 应用连线（实体边）：同源同端口覆盖旧连线，其余原样保留
 * @param {Array} edges 实体边数组（原样修改）
 * @param {{source, target, source_port, canvas?}} payload source_port 为画布端口名
 * @returns {boolean}
 */
export function applyEdge(edges, { source, target, source_port, canvas = 'workflow' }) {
    if (!source || !target || source === target) return false
    const port = normalizePort(source_port)
    const next = (edges || []).filter(e => !(e.source_node === source && e.source_port === port))
    next.push({
        edge_id: `e_${source}_${port}_${target}`,
        source_node: source,
        target_node: target,
        source_port: port,
        canvas
    })
    edges.length = 0
    edges.push(...next)
    return true
}

/**
 * 断开连线：按 edge 描述（edge_id 优先，回退 sourceNodeId + legacyPort）
 * @returns {boolean} 是否确实断开了连线
 */
export function removeEdge(edges, edge) {
    if (!edge) return false
    let idx = -1
    if (edge.edgeId || edge.edgeIdBase) {
        idx = (edges || []).findIndex(e => e.edge_id === (edge.edgeId || edge.edgeIdBase))
    }
    if (idx === -1 && edge.sourceNodeId) {
        idx = (edges || []).findIndex(e =>
            e.source_node === edge.sourceNodeId && e.source_port === normalizePort(edge.legacyPort)
        )
    }
    if (idx === -1) return false
    edges.splice(idx, 1)
    return true
}

/**
 * 断开指定节点的指定端口连线（拉线空放断线）
 * @returns {boolean} 是否确实断开了连线
 */
export function disconnectPort(edges, nodeId, portType) {
    if (!nodeId) return false
    const port = normalizePort(portType)
    const idx = (edges || []).findIndex(e => e.source_node === nodeId && e.source_port === port)
    if (idx === -1) return false
    edges.splice(idx, 1)
    return true
}

/**
 * 删除节点：从所有任务组移除（清空组剔除），并清理所有关联边（源或目标）
 * @param {Array} tasks 任务组数组（返回新数组）
 * @param {Array} edges 实体边数组（原样修改）
 * @returns {Array} 新的任务组数组
 */
export function removeNode(tasks, edges, nodeId) {
    if (!nodeId) return tasks || []
    const next = (tasks || []).map(t => ({
        ...t,
        nodes: (t.nodes || []).filter(n => n.node_id !== nodeId)
    }))
    const filtered = next.filter(t => (t.nodes || []).length > 0)
    for (let i = (edges || []).length - 1; i >= 0; i--) {
        const e = edges[i]
        if (e.source_node === nodeId || e.target_node === nodeId) {
            edges.splice(i, 1)
        }
    }
    return filtered
}
