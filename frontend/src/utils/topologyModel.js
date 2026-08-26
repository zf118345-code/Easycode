// frontend/src/utils/topologyModel.js
// 页面地图使用一张项目级扁平画布；页面数据内嵌于节点 params。

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
        const m = port.match(/^exit_(\d+)$/)
        if (!m) return true
        return parseInt(m[1], 10) < limit
    })
}
