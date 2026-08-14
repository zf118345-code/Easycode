// frontend/src/utils/workflowEdgeModel.js
// 工作流连线纯模型：连线存于节点 params（on_success / on_failure / candidates[i].on_success）
// 提供派生、建边、断边、删节点的纯函数，供 CanvasView 渲染与 WorkflowCanvas 包装器事件处理共用。

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
 * 从节点 params 派生连线列表（与 WorkflowCanvas 渲染语义一致）
 * @returns {Array<{sourceNodeId, targetNodeId, legacyPort, edgeIdBase, isFailFlag, extra}>}
 */
export function deriveWorkflowEdges(tasks) {
    const edges = []
    const allNodes = []
    ;(tasks || []).forEach(t => (t.nodes || []).forEach(n => allNodes.push(n)))

    for (const node of allNodes) {
        // 1. 成功出口（含 branch 节点：Step 4 起所有节点均有 success 端口）
        if (node.params?.on_success?.target_node) {
            const target = allNodes.find(n => n.node_id === node.params.on_success.target_node)
            if (target) {
                edges.push({
                    sourceNodeId: node.node_id,
                    targetNodeId: target.node_id,
                    legacyPort: 'succ',
                    edgeIdBase: `e_${node.node_id}_succ_${target.node_id}`,
                    isFailFlag: false,
                    extra: {}
                })
            }
        }

        // 2. branch 节点多路行级分支出口
        if (node.node_type === 'branch' && Array.isArray(node.params?.candidates)) {
            node.params.candidates.forEach((cand, cIdx) => {
                if (cand?.on_success?.target_node) {
                    const target = allNodes.find(n => n.node_id === cand.on_success.target_node)
                    if (target) {
                        edges.push({
                            sourceNodeId: node.node_id,
                            targetNodeId: target.node_id,
                            legacyPort: `branch_${cIdx}`,
                            edgeIdBase: `e_${node.node_id}_branch_${cIdx}_${target.node_id}`,
                            isFailFlag: false,
                            extra: { candIndex: cIdx }
                        })
                    }
                }
            })
        }

        // 3. 失败 / Else 兜底出口
        if (node.params?.on_failure?.target_node) {
            const target = allNodes.find(n => n.node_id === node.params.on_failure.target_node)
            if (target) {
                edges.push({
                    sourceNodeId: node.node_id,
                    targetNodeId: target.node_id,
                    legacyPort: 'fail',
                    edgeIdBase: `e_${node.node_id}_fail_${target.node_id}`,
                    isFailFlag: true,
                    extra: {}
                })
            }
        }
    }
    return edges
}

/**
 * 应用连线：按端口写入源节点 params
 * @returns {boolean} 是否写入成功
 */
export function applyWorkflowEdge(tasks, { source, target, source_port }) {
    if (!source || !target || source === target) return false
    const hit = findNodeInTasks(tasks, source)
    if (!hit) return false
    const sourceNode = hit.node
    if (!sourceNode.params) sourceNode.params = {}

    const targetTask = findTaskByNodeId(tasks, target)
    const connectionData = { target_task: targetTask ? targetTask.task_id : '', target_node: target }

    if (typeof source_port === 'string' && source_port.startsWith('branch_')) {
        const cIdx = parseInt(source_port.split('_')[1], 10) || 0
        if (!sourceNode.params.candidates) sourceNode.params.candidates = []
        if (!sourceNode.params.candidates[cIdx]) return false
        sourceNode.params.candidates[cIdx].on_success = { ...connectionData }
    } else if (source_port === 'fail' || source_port === 'failure') {
        sourceNode.params.on_failure = { ...connectionData }
    } else {
        sourceNode.params.on_success = { ...connectionData }
    }
    return true
}

/**
 * 断开连线（按 edge 描述定位：sourceNodeId + legacyPort，branch 需 candIndex）
 * @returns {boolean} 是否确实断开了连线
 */
export function removeWorkflowEdge(tasks, edge) {
    if (!edge || !edge.sourceNodeId) return false
    const hit = findNodeInTasks(tasks, edge.sourceNodeId)
    if (!hit || !hit.node.params) return false
    const params = hit.node.params
    const legacyPort = edge.legacyPort || edge.typeFlag

    if (legacyPort === 'succ') {
        if (params.on_success?.target_node) { params.on_success = {}; return true }
    } else if (legacyPort === 'fail') {
        if (params.on_failure?.target_node) { params.on_failure = {}; return true }
    } else if (typeof legacyPort === 'string' && legacyPort.startsWith('branch_')) {
        const cIdx = edge.candIndex ?? parseInt(legacyPort.split('_')[1], 10)
        if (params.candidates?.[cIdx]?.on_success?.target_node) {
            params.candidates[cIdx].on_success = {}
            return true
        }
    }
    return false
}

/**
 * 断开指定节点的指定端口连线（拉线空放断线）
 * @returns {boolean} 是否确实断开了连线
 */
export function disconnectWorkflowPort(tasks, nodeId, portType) {
    if (!nodeId) return false
    const hit = findNodeInTasks(tasks, nodeId)
    if (!hit || !hit.node.params) return false
    const params = hit.node.params

    if (typeof portType === 'string' && portType.startsWith('branch_')) {
        const cIdx = parseInt(portType.split('_')[1], 10) || 0
        if (params.candidates?.[cIdx]?.on_success?.target_node) {
            params.candidates[cIdx].on_success = {}
            return true
        }
    } else if (portType === 'fail' && params.on_failure?.target_node) {
        params.on_failure = {}
        return true
    } else if (portType === 'succ' && params.on_success?.target_node) {
        params.on_success = {}
        return true
    }
    return false
}

/**
 * 删除节点（从所有任务组移除，并清理空任务组）
 * @returns {Array} 新的任务组数组
 */
export function removeWorkflowNode(tasks, nodeId) {
    if (!nodeId) return tasks || []
    const next = (tasks || []).map(t => ({
        ...t,
        nodes: (t.nodes || []).filter(n => n.node_id !== nodeId)
    }))
    return next.filter(t => (t.nodes || []).length > 0)
}
