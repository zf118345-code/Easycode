// frontend/src/utils/topologyModel.js
// 拓扑数据纯模型：topology.json 文件结构（任务组 {tasks, edges}）与内部扁平结构（{nodes, edges}）的转换
// 供 topologyStore / CanvasView / InspectorPanel 共用。

export function defaultTopologyTask() {
    return {
        task_id: 'task_topology',
        task_name: '页面拓扑组',
        loop_count: 1,
        loop_interval: 0,
        nodes: []
    }
}

// 文件节点（页面数据存于 params）-> 内部扁平节点（组件消费）
export function fileNodeToFlat(n) {
    const params = n.params || {}
    return {
        node_id: n.node_id,
        node_name: n.node_name || '',
        type: n.node_type || n.type || 'page_state',
        page_id: params.page_id ?? n.page_id ?? '',
        features: params.features ?? n.features ?? [],
        feature_mode: params.feature_mode ?? n.feature_mode ?? 'and',
        exits: params.exits ?? n.exits ?? [],
        label: n.label ?? '',
        condition: n.condition ?? null,
        position: n.position || null,
        params: n.params || {}
    }
}

// 内部扁平节点 -> 文件节点
export function flatNodeToFile(n) {
    return {
        node_id: n.node_id,
        node_name: n.node_name || '',
        node_type: n.type || 'page_state',
        params: {
            ...(n.params || {}),
            page_id: n.page_id ?? '',
            features: n.features ?? [],
            feature_mode: n.feature_mode ?? 'and',
            exits: n.exits ?? []
        },
        delay_before: n.delay_before ?? 0,
        loop_count: n.loop_count ?? 1,
        enabled: n.enabled ?? true,
        position: n.position || null,
        label: n.label ?? '',
        condition: n.condition ?? null
    }
}

// 文件连线（source_node/target_node）-> 内部连线（source/target）
export function fileEdgeToFlat(e) {
    return {
        edge_id: e.edge_id,
        source: e.source_node ?? e.source ?? '',
        target: e.target_node ?? e.target ?? '',
        source_port: e.source_port || 'exit',
        source_exit: e.source_exit || 'default',
        label: e.label || '',
        condition: e.condition || null,
        action: e.action || ''
    }
}

// 内部连线 -> 文件连线
export function flatEdgeToFile(e) {
    return {
        edge_id: e.edge_id,
        source_node: e.source ?? e.source_node,
        target_node: e.target ?? e.target_node,
        source_port: e.source_port || 'exit',
        canvas: 'topology',
        source_exit: e.source_exit || 'default',
        label: e.label || '',
        condition: e.condition || null,
        action: e.action || ''
    }
}

/**
 * topology.json 文件结构 {tasks, edges} -> 扁平结构 {nodes, edges}
 */
export function topologyFileToFlat(topo) {
    const nodes = []
    const tasks = topo?.tasks || []
    for (const task of tasks) {
        for (const n of (task.nodes || [])) {
            if (n && n.node_id) nodes.push(fileNodeToFlat(n))
        }
    }
    return {
        nodes,
        edges: (topo?.edges || []).map(fileEdgeToFlat)
    }
}

/**
 * 扁平结构 {nodes, edges} -> topology.json 文件结构 {tasks, edges}
 */
export function topologyFlatToFile(flat) {
    const task = defaultTopologyTask()
    task.nodes = (flat?.nodes || []).map(flatNodeToFile)
    return {
        tasks: [task],
        edges: (flat?.edges || []).map(flatEdgeToFile)
    }
}

/**
 * 修剪某节点的越界 exit 连线（D3：exits 删除后，索引越界的 exit_N 连线自动移除）
 * @param {Array} edges      内部扁平连线列表
 * @param {string} nodeId    源节点 id
 * @param {number} exitsLength 当前 exits 数量
 * @returns {Array} 修剪后的连线列表
 */
export function pruneTopologyEdgesForNode(edges, nodeId, exitsLength) {
    const limit = Math.max(0, exitsLength || 0)
    return (edges || []).filter(e => {
        if (e.source !== nodeId) return true
        const port = e.source_port || ''
        if (port === 'exit') return limit > 0
        const m = port.match(/^exit_(\d+)$/)
        if (!m) return true
        return parseInt(m[1], 10) < limit
    })
}
