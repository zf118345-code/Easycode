import { describe, it, expect } from 'vitest'
import {
    deriveEdges,
    applyEdge,
    removeEdge,
    disconnectPort,
    removeNode,
    normalizePort,
    findNodeInTasks,
    findTaskByNodeId
} from '../workflowEdgeModel'

function makeTasks() {
    return [
        {
            task_id: 't1',
            task_name: '组一',
            nodes: [
                { node_id: 'n1', node_name: '点击', node_type: 'click', params: {}, position: { x: 0, y: 0 } },
                { node_id: 'n2', node_name: '分支', node_type: 'branch', params: {}, position: { x: 200, y: 0 } },
                { node_id: 'n3', node_name: '日志', node_type: 'log', params: {}, position: { x: 400, y: 0 } }
            ]
        },
        {
            task_id: 't2',
            task_name: '组二',
            nodes: [{ node_id: 'n4', node_name: '等待', node_type: 'wait', params: {}, position: { x: 0, y: 200 } }]
        }
    ]
}

describe('workflowEdgeModel（统一实体边）', () => {
    it('deriveEdges 从实体边派生统一扁平结构（标准端口名）', () => {
        const edges = [
            { edge_id: 'e1', source_node: 'n1', target_node: 'n2', source_port: 'success', canvas: 'workflow' },
            { edge_id: 'e2', source_node: 'n1', target_node: 'n3', source_port: 'failure', canvas: 'workflow' },
            { edge_id: 'e3', source_node: 'n2', target_node: 'n3', source_port: 'branch_0', canvas: 'workflow' },
            { edge_id: 'e4', source_node: 'p1', target_node: 'p2', source_port: 'exit_1', canvas: 'topology' }
        ]
        const derived = deriveEdges(edges)
        expect(derived).toHaveLength(4)
        const succ = derived.find(e => e.legacyPort === 'success')
        expect(succ.sourceNodeId).toBe('n1')
        expect(succ.targetNodeId).toBe('n2')
        expect(succ.edgeId).toBe('e1')
        expect(succ.isFailFlag).toBe(false)
        const fail = derived.find(e => e.legacyPort === 'failure')
        expect(fail.isFailFlag).toBe(true)
        const branch = derived.find(e => e.legacyPort === 'branch_0')
        expect(branch.extra.candIndex).toBe(0)
        expect(derived.find(e => e.legacyPort === 'exit_1')).toBeTruthy()
    })

    it('normalizePort 画布端口名 → 标准名', () => {
        expect(normalizePort('succ')).toBe('success')
        expect(normalizePort('fail')).toBe('failure')
        expect(normalizePort('branch_0')).toBe('branch_0')
        expect(normalizePort('exit_2')).toBe('exit_2')
        expect(normalizePort(undefined)).toBe('success')
    })

    it('applyEdge 添加实体边并同源同端口覆盖', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'n1', target: 'n4', source_port: 'succ', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('success')
        expect(edges[0].target_node).toBe('n4')
        expect(edges[0].canvas).toBe('workflow')

        // 同源同端口覆盖
        expect(applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'succ', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].target_node).toBe('n3')

        // 不同端口追加
        expect(applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'fail', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(2)
    })

    it('applyEdge 拒绝自连与无效源', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'n1', target: 'n1', source_port: 'succ' })).toBe(false)
        expect(applyEdge(edges, { source: '', target: 'n2', source_port: 'succ' })).toBe(false)
        expect(edges).toHaveLength(0)
    })

    it('removeEdge 按 edge_id / 源+端口断开', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'succ' })
        applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'fail' })

        expect(removeEdge(edges, { edgeId: edges[0].edge_id })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(removeEdge(edges, { sourceNodeId: 'n1', legacyPort: 'fail' })).toBe(true)
        expect(edges).toHaveLength(0)
        expect(removeEdge(edges, { sourceNodeId: 'n1', legacyPort: 'success' })).toBe(false)
    })

    it('disconnectPort 拉线空放断线', () => {
        const edges = []
        applyEdge(edges, { source: 'n2', target: 'n3', source_port: 'branch_1' })
        expect(disconnectPort(edges, 'n2', 'branch_1')).toBe(true)
        expect(edges).toHaveLength(0)
        expect(disconnectPort(edges, 'n2', 'branch_1')).toBe(false)
    })

    it('removeNode 删除节点并清理关联边与空任务组', () => {
        const tasks = makeTasks()
        const edges = [
            { edge_id: 'e1', source_node: 'n1', target_node: 'n2', source_port: 'success' },
            { edge_id: 'e2', source_node: 'n2', target_node: 'n3', source_port: 'success' },
            { edge_id: 'e3', source_node: 'n3', target_node: 'n4', source_port: 'success' }
        ]
        const next = removeNode(tasks, edges, 'n2')
        expect(next).toHaveLength(2)
        expect(findNodeInTasks(next, 'n2')).toBeNull()
        // 关联边（源或目标）全部清理
        expect(edges.map(e => e.edge_id)).toEqual(['e3'])

        const next2 = removeNode(next, edges, 'n4')
        expect(next2).toHaveLength(1)
        expect(edges).toHaveLength(0)
        expect(findTaskByNodeId(next2, 'n4')).toBeNull()
    })
})

describe('workflowEdgeModel 拓扑出口边（exit_N）', () => {
    it('applyEdge 拓扑出口边创建（无标签字段，线上文字已移除）', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', canvas: 'topology' })).toBe(true)
        expect(edges[0].source_port).toBe('exit_0')
        expect(edges[0].label).toBeUndefined()
        expect(applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_2', canvas: 'topology' })).toBe(true)
        expect(edges[1].source_port).toBe('exit_2')
    })

    it('applyEdge workflow 边不生成标签', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'succ', canvas: 'workflow' })
        expect(edges[0].label).toBeUndefined()
    })

    it('removeEdge 断连中间出口后，同源出口边重编号补位（exit_1→exit_0）', () => {
        const edges = []
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_1', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p4', source_port: 'exit_2', canvas: 'topology' })
        const first = edges.find(e => e.source_port === 'exit_0')

        expect(removeEdge(edges, { edgeId: first.edge_id })).toBe(true)
        expect(edges).toHaveLength(2)
        expect(edges.map(e => e.source_port)).toEqual(['exit_0', 'exit_1'])
        // 重编号后 edge_id 同步更新
        const shifted = edges.find(e => e.source_port === 'exit_0')
        expect(shifted.target_node).toBe('p3')
        expect(shifted.edge_id).toBe('e_p1_exit_0_p3')
        const shifted2 = edges.find(e => e.source_port === 'exit_1')
        expect(shifted2.target_node).toBe('p4')
    })

    it('disconnectPort 断开拓扑出口边后同样重编号', () => {
        const edges = []
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_1', canvas: 'topology' })
        expect(disconnectPort(edges, 'p1', 'exit_0')).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('exit_0')
        expect(edges[0].target_node).toBe('p3')
    })

    it('断连非出口边不触发重编号', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'succ' })
        applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'fail' })
        expect(removeEdge(edges, { sourceNodeId: 'n1', legacyPort: 'succ' })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('failure')
    })

    it('单条出口边删除后无需重编号', () => {
        const edges = []
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', canvas: 'topology' })
        expect(removeEdge(edges, { sourceNodeId: 'p1', legacyPort: 'exit_0' })).toBe(true)
        expect(edges).toHaveLength(0)
    })
})
