// frontend/src/utils/topologyModel.js
// 拓扑节点/连线统一实体模型：画布直接读写 topology.json 文件形态（任务组 {tasks, edges}，
// 页面数据内嵌于 params），与 workflow.json 完全同构，不再需要扁平转换层。

export function defaultTopologyTask() {
    return {
        task_id: 'task_topology',
        task_name: '页面拓扑组',
        loop_count: 1,
        loop_interval: 0,
        nodes: []
    }
}

/**
 * 修剪某节点的越界 exit 连线（D3：exits 删除后，索引越界的 exit_N 连线自动移除）
 * @param {Array} edges      实体连线列表（source_node/target_node 键）
 * @param {string} nodeId    源节点 id
 * @param {number} exitsLength 当前 exits 数量
 * @returns {Array} 修剪后的连线列表
 */
export function pruneTopologyEdgesForNode(edges, nodeId, exitsLength) {
    const limit = Math.max(0, exitsLength || 0)
    return (edges || []).filter(e => {
        if (e.source_node !== nodeId) return true
        const port = e.source_port || ''
        if (port === 'exit') return limit > 0
        const m = port.match(/^exit_(\d+)$/)
        if (!m) return true
        return parseInt(m[1], 10) < limit
    })
}
