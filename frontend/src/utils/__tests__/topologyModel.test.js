import { describe, it, expect } from 'vitest'
import {
    defaultTopologyTask,
    fileNodeToFlat,
    flatNodeToFile,
    fileEdgeToFlat,
    flatEdgeToFile,
    topologyFileToFlat,
    topologyFlatToFile,
    pruneTopologyEdgesForNode
} from '../topologyModel'

const FILE_NODE = {
    node_id: 'topo_1',
    node_name: '登录页',
    node_type: 'page_state',
    params: {
        page_id: 'login_page',
        features: [{ feature_type: 'image_exists', params: { image_source: 'login_btn' } }],
        feature_mode: 'and',
        exits: [{ exit_action: '点击登录', target_page_id: 'main_page' }]
    },
    delay_before: 0,
    loop_count: 1,
    enabled: true,
    position: { x: 100, y: 200 },
    label: '',
    condition: null
}

const FILE_EDGE = {
    edge_id: 'te1',
    source_node: 'topo_1',
    target_node: 'topo_2',
    source_port: 'exit_0',
    canvas: 'topology',
    label: '',
    condition: null,
    action: ''
}

describe('topologyModel', () => {
    it('fileNodeToFlat 把 params 内页面数据提升到顶层', () => {
        const flat = fileNodeToFlat(FILE_NODE)
        expect(flat.node_id).toBe('topo_1')
        expect(flat.type).toBe('page_state')
        expect(flat.page_id).toBe('login_page')
        expect(flat.features).toEqual(FILE_NODE.params.features)
        expect(flat.exits).toEqual(FILE_NODE.params.exits)
        expect(flat.feature_mode).toBe('and')
        expect(flat.position).toEqual({ x: 100, y: 200 })
    })

    it('flatNodeToFile 把顶层页面数据折叠回 params（原 params 值优先）', () => {
        const flat = fileNodeToFlat(FILE_NODE)
        const file = flatNodeToFile(flat)
        expect(file.node_type).toBe('page_state')
        expect(file.params.page_id).toBe('login_page')
        expect(file.params.features).toEqual(FILE_NODE.params.features)
        expect(file.params.exits).toEqual(FILE_NODE.params.exits)
        expect(file.position).toEqual({ x: 100, y: 200 })
    })

    it('fileEdgeToFlat / flatEdgeToFile 键名映射往返', () => {
        const flat = fileEdgeToFlat(FILE_EDGE)
        expect(flat.source).toBe('topo_1')
        expect(flat.target).toBe('topo_2')
        expect(flat.source_port).toBe('exit_0')

        const file = flatEdgeToFile(flat)
        expect(file.source_node).toBe('topo_1')
        expect(file.target_node).toBe('topo_2')
        expect(file.canvas).toBe('topology')
    })

    it('topologyFileToFlat 展开任务组为扁平节点', () => {
        const topo = { tasks: [{ ...defaultTopologyTask(), nodes: [FILE_NODE, { ...FILE_NODE, node_id: 'topo_2' }] }], edges: [FILE_EDGE] }
        const flat = topologyFileToFlat(topo)
        expect(flat.nodes).toHaveLength(2)
        expect(flat.nodes[0].node_id).toBe('topo_1')
        expect(flat.edges[0].source).toBe('topo_1')
    })

    it('topologyFlatToFile 打包回任务组结构并往返一致', () => {
        const flat = { nodes: [fileNodeToFlat(FILE_NODE)], edges: [fileEdgeToFlat(FILE_EDGE)] }
        const file = topologyFlatToFile(flat)
        expect(file.tasks).toHaveLength(1)
        expect(file.tasks[0].task_id).toBe('task_topology')
        expect(file.tasks[0].nodes[0].node_id).toBe('topo_1')
        expect(file.edges[0].source_node).toBe('topo_1')

        const roundtrip = topologyFileToFlat(file)
        expect(roundtrip.nodes[0].page_id).toBe('login_page')
        expect(roundtrip.edges[0].source).toBe('topo_1')
    })

    it('pruneTopologyEdgesForNode 清除索引越界的 exit 连线，保留合法连线', () => {
        const edges = [
            { edge_id: 'e1', source: 'topo_1', target: 'x', source_port: 'exit_0' },
            { edge_id: 'e2', source: 'topo_1', target: 'y', source_port: 'exit_2' },
            { edge_id: 'e3', source: 'topo_1', target: 'z', source_port: 'success' },
            { edge_id: 'e4', source: 'other', target: 'x', source_port: 'exit_5' },
            { edge_id: 'e5', source: 'topo_1', target: 'w', source_port: 'exit' }
        ]
        const pruned = pruneTopologyEdgesForNode(edges, 'topo_1', 2)
        const ids = pruned.map(e => e.edge_id)
        expect(ids).toContain('e1')   // exit_0 合法
        expect(ids).not.toContain('e2') // exit_2 越界
        expect(ids).toContain('e3')   // success 不受影响
        expect(ids).toContain('e4')   // 其他节点的连线不受影响
        expect(ids).toContain('e5')   // exit（视为 exit_0）在 limit>0 时保留
    })

    it('pruneTopologyEdgesForNode exits 清空时移除全部 exit 连线', () => {
        const edges = [
            { edge_id: 'e1', source: 'topo_1', target: 'x', source_port: 'exit_0' },
            { edge_id: 'e2', source: 'topo_1', target: 'y', source_port: 'exit' }
        ]
        const pruned = pruneTopologyEdgesForNode(edges, 'topo_1', 0)
        expect(pruned).toHaveLength(0)
    })
})
