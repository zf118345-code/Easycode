import { describe, it, expect } from 'vitest'
import { pruneTopologyEdgesForNode } from '../topologyModel'

describe('topologyModel（统一实体模型）', () => {
    it('pruneTopologyEdgesForNode 清除索引越界的 exit 连线，保留合法连线（实体键 source_node）', () => {
        const edges = [
            { edge_id: 'e1', source_node: 'topo_1', target_node: 'x', source_port: 'exit_0' },
            { edge_id: 'e2', source_node: 'topo_1', target_node: 'y', source_port: 'exit_2' },
            { edge_id: 'e3', source_node: 'topo_1', target_node: 'z', source_port: 'success' },
            { edge_id: 'e4', source_node: 'other', target_node: 'x', source_port: 'exit_5' }
        ]
        const pruned = pruneTopologyEdgesForNode(edges, 'topo_1', 2)
        const ids = pruned.map(e => e.edge_id)
        expect(ids).toContain('e1')   // exit_0 合法
        expect(ids).not.toContain('e2') // exit_2 越界
        expect(ids).toContain('e3')   // success 不受影响
        expect(ids).toContain('e4')   // 其他节点的连线不受影响
    })

    it('pruneTopologyEdgesForNode exits 清空时移除全部 exit 连线', () => {
        const edges = [
            { edge_id: 'e1', source_node: 'topo_1', target_node: 'x', source_port: 'exit_0' }
        ]
        const pruned = pruneTopologyEdgesForNode(edges, 'topo_1', 0)
        expect(pruned).toHaveLength(0)
    })
})
