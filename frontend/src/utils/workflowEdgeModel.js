// frontend/src/utils/workflowEdgeModel.js
// 统一连线实体模型：workflow.json 与 topology.json 的 edges 完全同构
//   { edge_id, source_node, target_node, source_port, source_port_id, canvas }
// source_port 一律用标准名：success / failure / branch_N / exit_N
// 提供派生、建边、断边、删节点的纯函数，供 CanvasView 渲染与 CanvasPage 事件处理共用。

/**
 * 在图适配列表中查找节点，返回 { task, node }。
 * task 只是 CanvasView 的内部图容器名，不对应旧版任务组语义。
 */
export function findNodeInTasks(tasks, nodeId) {
    for (const task of tasks || []) {
        const found = (task.nodes || []).find(n => n.node_id === nodeId)
        if (found) return { task, node: found }
    }
    return null
}

/**
 * 查找节点所属的当前图容器
 */
export function findTaskByNodeId(tasks, nodeId) {
    return (tasks || []).find(t => (t.nodes || []).some(n => n.node_id === nodeId)) || null
}

export function normalizePort(portType) {
    return typeof portType === 'string' ? portType : ''
}

/**
 * 从实体 edges 派生画布扁平连线（统一结构，供渲染/端口连接集合使用）
 * @returns {Array<{sourceNodeId, targetNodeId, sourcePort, edgeId, edgeIdBase, isFailFlag, extra}>}
 */
export function deriveEdges(edges) {
    return (edges || []).map(e => {
        const port = e.source_port
        return {
            sourceNodeId: e.source_node,
            targetNodeId: e.target_node,
            sourcePort: port,
            edgeId: e.edge_id,
            edgeIdBase: e.edge_id,
            isFailFlag: port === 'failure',
            extra: {
                sourcePort: port,
                sourcePortId: e.source_port_id,
                routing: e.routing ? JSON.parse(JSON.stringify(e.routing)) : undefined,
                candIndex: typeof port === 'string' && port.startsWith('branch_')
                    ? (parseInt(port.split('_')[1], 10) || 0)
                    : undefined
            }
        }
    })
}

/**
 * 解析出口端口序号：exit_N → N；非出口端口返回 null
 */
export function parseExitPortIndex(port) {
    if (typeof port !== 'string') return null
    const m = port.match(/^exit_(\d+)$/)
    return m ? parseInt(m[1], 10) : null
}

/**
 * 出口边重编号：某节点的 exit 边按序号升序重新分配连续 exit_0..N-1
 * （断连中间出口后，后续出口上移补位，与画布端口“第二个移到第一个位置”联动）
 * @returns {boolean} 是否发生了重编号
 */
export function renumberExitEdges(edges, sourceNodeId) {
    if (!sourceNodeId) return false
    const exits = []
    for (let i = 0; i < (edges || []).length; i++) {
        const e = edges[i]
        const idx = parseExitPortIndex(e?.source_port)
        if (e.source_node === sourceNodeId && idx !== null) {
            exits.push({ e, idx })
        }
    }
    if (exits.length === 0) return false
    exits.sort((a, b) => a.idx - b.idx)
    let changed = false
    exits.forEach((x, newIdx) => {
        const want = `exit_${newIdx}`
        if (x.e.source_port !== want) {
            x.e.source_port = want
            if (x.e.edge_id) {
                x.e.edge_id = `e_${x.e.source_node}_${want}_${x.e.target_node}`
            }
            changed = true
        }
    })
    return changed
}

/**
 * 应用连线（实体边）：同源同端口覆盖旧连线，其余原样保留。
 * v3 的每张画布是独立图，跨图复用只能通过调用函数节点表达。
 * @param {Array} edges 实体边数组（原样修改）
 * @param {{source, target, source_port, canvas?}} payload source_port 为画布端口名
 * @returns {boolean}
 */
export function applyEdge(edges, { source, target, source_port, source_port_id = '', canvas = 'workflow' }) {
    if (!source || !target || source === target || !source_port) return false
    const port = normalizePort(source_port)
    const stablePortId = source_port_id || (port === 'success' || port === 'failure' ? port : '')
    if (!stablePortId) return false
    const next = (edges || []).filter(e => {
        if (e.source_node !== source) return true
        return e.source_port_id !== stablePortId
    })
    next.push({
        edge_id: `e_${source}_${port}_${target}`,
        source_node: source,
        target_node: target,
        source_port: port,
        source_port_id: stablePortId,
        canvas
    })
    edges.length = 0
    edges.push(...next)
    return true
}

/** Find the current edge occupying a semantic/stable source port. */
export function findEdgeAtPort(edges, source, sourcePort, sourcePortId = '') {
    const port = normalizePort(sourcePort)
    const stable = sourcePortId || (port === 'success' || port === 'failure' ? port : '')
    if (!stable) return null
    const sourceEdges = (edges || []).filter(edge => edge.source_node === source)
    return sourceEdges.find(edge => edge.source_port_id === stable) || null
}

/**
 * 断开连线：按 edge_id 删除。
 * 断开拓扑出口边后，同源节点的其余出口边自动重编号补位
 * @returns {boolean} 是否确实断开了连线
 */
export function removeEdge(edges, edge) {
    if (!edge) return false
    let idx = -1
    if (edge.edgeId || edge.edgeIdBase) {
        idx = (edges || []).findIndex(e => e.edge_id === (edge.edgeId || edge.edgeIdBase))
    }
    if (idx === -1) return false
    const removed = edges[idx]
    edges.splice(idx, 1)
    if (parseExitPortIndex(removed?.source_port) !== null) {
        renumberExitEdges(edges, removed.source_node)
    }
    return true
}

/**
 * 断开指定节点的指定端口连线（拉线空放断线）
 * 断开拓扑出口边后，同源节点的其余出口边自动重编号补位
 * @returns {boolean} 是否确实断开了连线
 */
export function disconnectPort(edges, nodeId, portType) {
    if (!nodeId) return false
    const port = normalizePort(portType)
    const idx = (edges || []).findIndex(e => e.source_node === nodeId && e.source_port === port)
    if (idx === -1) return false
    edges.splice(idx, 1)
    if (parseExitPortIndex(port) !== null) {
        renumberExitEdges(edges, nodeId)
    }
    return true
}

/**
 * Reconcile persisted branch wires with the current candidate order.
 * Candidate identity is stable; branch_N is only its current visual/runtime slot.
 * Deleted candidates therefore lose their orphaned wire instead of silently
 * donating it to whichever candidate moved into the same row.
 */
export function reconcileStablePortRoutes(tasks, edges) {
    const branchMaps = new Map()
    let changed = false
    for (const task of tasks || []) {
        for (const node of task.nodes || []) {
            if (node.node_type !== 'branch') continue
            const candidates = node.params?.candidates || []
            const semantic = new Map()
            candidates.forEach((candidate, index) => {
                semantic.set(candidate.candidate_id, `branch_${index}`)
            })
            branchMaps.set(node.node_id, { semantic, candidates })
        }
    }

    for (let index = (edges || []).length - 1; index >= 0; index--) {
        const edge = edges[index]
        const model = branchMaps.get(edge.source_node)
        if (!model || !String(edge.source_port || '').startsWith('branch_')) continue
        const stable = edge.source_port_id
        if (!model.semantic.has(stable)) {
            edges.splice(index, 1)
            changed = true
            continue
        }
        const currentPort = model.semantic.get(stable)
        if (edge.source_port !== currentPort) {
            edge.source_port = currentPort
            edge.edge_id = `e_${edge.source_node}_${currentPort}_${edge.target_node}`
            changed = true
        }
    }
    return changed
}

/**
 * 保证流程名称全局唯一，重复名称自动追加最小可用序号。
 */
export function reconcileTaskNames(tasks, fallbackName = '新建流程') {
    const used = new Set()
    let changedCount = 0
    for (const task of tasks || []) {
        const raw = String(task?.task_name || '').trim() || fallbackName
        const base = raw.slice(0, 64)
        let name = base
        let suffix = 1
        while (used.has(name)) {
            const suffixText = String(suffix)
            name = `${base.slice(0, Math.max(1, 64 - suffixText.length))}${suffixText}`
            suffix += 1
        }
        used.add(name)
        if (task.task_name !== name) {
            task.task_name = name
            changedCount += 1
        }
    }
    return changedCount
}

/**
 * 保存前统一修复图引用：
 * - 删除目标/来源节点已经不存在的孤儿边；
 * - 补齐稳定端口标识，并保证一个语义端口只有一条出边；
 *
 * 返回修复统计，调用方可用于日志或测试。函数原地修改 tasks/edges。
 */
export function reconcileGraphIntegrity(tasks, edges) {
    const taskList = Array.isArray(tasks) ? tasks : []
    const edgeList = Array.isArray(edges) ? edges : []
    const report = {
        changed: false,
        removedEdges: 0,
        updatedEdges: 0,
        renamedTasks: 0
    }

    const nodeTasks = new Map()
    for (const [taskIndex, task] of taskList.entries()) {
        const taskId = task.task_id || `__graph_${taskIndex}`
        for (const node of task.nodes || []) {
            if (node?.node_id) nodeTasks.set(node.node_id, taskId)
        }
    }

    const seenEdgeIds = new Set()
    const seenPorts = new Set()
    const kept = []
    // 从后向前：如果历史数据里一个端口意外保留多条边，以最后一次操作为准。
    for (let index = edgeList.length - 1; index >= 0; index -= 1) {
        const edge = edgeList[index]
        const sourceTask = nodeTasks.get(edge?.source_node)
        const targetTask = nodeTasks.get(edge?.target_node)
        if (!sourceTask || !targetTask) {
            report.changed = true
            report.removedEdges += 1
            continue
        }

        let edgeChanged = false
        if (!edge.source_port_id && edge.source_port) {
            edge.source_port_id = edge.source_port
            edgeChanged = true
        }
        if (!edge.edge_id && edge.source_port) {
            edge.edge_id = `e_${edge.source_node}_${edge.source_port}_${edge.target_node}`
            edgeChanged = true
        }
        if ('target_task' in edge || 'return_on_complete' in edge) {
            delete edge.target_task
            delete edge.return_on_complete
            edgeChanged = true
        }

        const edgeId = String(edge.edge_id || '')
        const portKey = `${edge.source_node}|${edge.source_port_id || edge.source_port || ''}`
        if (!edgeId || !edge.source_port || !edge.source_port_id || seenEdgeIds.has(edgeId) || seenPorts.has(portKey)) {
            report.changed = true
            report.removedEdges += 1
            continue
        }
        seenEdgeIds.add(edgeId)
        seenPorts.add(portKey)
        if (edgeChanged) {
            report.changed = true
            report.updatedEdges += 1
        }
        kept.push(edge)
    }
    kept.reverse()
    if (kept.length !== edgeList.length || kept.some((edge, index) => edge !== edgeList[index])) {
        edgeList.splice(0, edgeList.length, ...kept)
    }
    return report
}

/** 删除整个流程，并级联清理流程内节点关联的全部入边和出边。 */
export function removeTask(tasks, edges, taskId) {
    const nodeIds = new Set(
        (tasks || []).find(task => task.task_id === taskId)?.nodes?.map(node => node.node_id) || []
    )
    for (let index = (edges || []).length - 1; index >= 0; index -= 1) {
        const edge = edges[index]
        if (nodeIds.has(edge.source_node) || nodeIds.has(edge.target_node)) edges.splice(index, 1)
    }
    return (tasks || []).filter(task => task.task_id !== taskId)
}

/**
 * 删除节点：从所有流程移除，但保留空流程，并清理所有关联边（源或目标）。
 * @param {Array} tasks 流程数组（返回新数组）
 * @param {Array} edges 实体边数组（原样修改）
 * @returns {Array} 新的内部运行图适配数组
 */
export function removeNode(tasks, edges, nodeId) {
    if (!nodeId) return tasks || []
    const next = (tasks || []).map(t => ({
        ...t,
        nodes: (t.nodes || []).filter(n => n.node_id !== nodeId)
    }))
    for (let i = (edges || []).length - 1; i >= 0; i--) {
        const e = edges[i]
        if (e.source_node === nodeId || e.target_node === nodeId) {
            edges.splice(i, 1)
        }
    }
    return next
}
