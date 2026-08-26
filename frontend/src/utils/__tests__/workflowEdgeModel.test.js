import { describe, it, expect } from 'vitest'
import {
    deriveEdges,
    applyEdge,
    removeEdge,
    disconnectPort,
    removeNode,
    normalizePort,
    findNodeInTasks,
    findTaskByNodeId,
    findEdgeAtPort,
    reconcileStablePortRoutes,
    reconcileGraphIntegrity,
    reconcileTaskNames,
    removeTask
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
            { edge_id: 'e1', source_node: 'n1', target_node: 'n2', source_port: 'success', source_port_id: 'success', canvas: 'workflow' },
            { edge_id: 'e2', source_node: 'n1', target_node: 'n3', source_port: 'failure', source_port_id: 'failure', canvas: 'workflow' },
            { edge_id: 'e3', source_node: 'n2', target_node: 'n3', source_port: 'branch_0', source_port_id: 'cand_1', canvas: 'workflow' },
            { edge_id: 'e4', source_node: 'p1', target_node: 'p2', source_port: 'exit_1', source_port_id: 'exit_1', canvas: 'topology' }
        ]
        const derived = deriveEdges(edges)
        expect(derived).toHaveLength(4)
        const succ = derived.find(e => e.sourcePort === 'success')
        expect(succ.sourceNodeId).toBe('n1')
        expect(succ.targetNodeId).toBe('n2')
        expect(succ.edgeId).toBe('e1')
        expect(succ.isFailFlag).toBe(false)
        const fail = derived.find(e => e.sourcePort === 'failure')
        expect(fail.isFailFlag).toBe(true)
        const branch = derived.find(e => e.sourcePort === 'branch_0')
        expect(branch.extra.candIndex).toBe(0)
        expect(derived.find(e => e.sourcePort === 'exit_1')).toBeTruthy()
    })

    it('normalizePort 保持新版端口名', () => {
        expect(normalizePort('success')).toBe('success')
        expect(normalizePort('failure')).toBe('failure')
        expect(normalizePort('branch_0')).toBe('branch_0')
        expect(normalizePort('exit_2')).toBe('exit_2')
        expect(normalizePort(undefined)).toBe('')
    })

    it('applyEdge 添加实体边并同源同端口覆盖', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'n1', target: 'n4', source_port: 'success', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('success')
        expect(edges[0].target_node).toBe('n4')
        expect(edges[0].canvas).toBe('workflow')

        // 同源同端口覆盖
        expect(applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'success', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].target_node).toBe('n3')

        // 不同端口追加
        expect(applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'failure', canvas: 'workflow' })).toBe(true)
        expect(edges).toHaveLength(2)
    })

    it('applyEdge 拒绝自连与无效源', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'n1', target: 'n1', source_port: 'success' })).toBe(false)
        expect(applyEdge(edges, { source: '', target: 'n2', source_port: 'success' })).toBe(false)
        expect(edges).toHaveLength(0)
    })

    it('稳定端口 ID 在分支重排后仍只覆盖自身连线', () => {
        const edges = [
            { edge_id: 'ea', source_node: 'n2', target_node: 'na', source_port: 'branch_0', source_port_id: 'cand_a' },
            { edge_id: 'eb', source_node: 'n2', target_node: 'nb', source_port: 'branch_1', source_port_id: 'cand_b' }
        ]
        // UI 重排后 cand_b 显示在 branch_0；重新连接它不能误删 cand_a。
        applyEdge(edges, {
            source: 'n2', target: 'nc', source_port: 'branch_0', source_port_id: 'cand_b'
        })
        expect(edges).toHaveLength(2)
        expect(edges.find(e => e.source_port_id === 'cand_a')?.target_node).toBe('na')
        expect(findEdgeAtPort(edges, 'n2', 'branch_0', 'cand_b')?.target_node).toBe('nc')
    })

    it('保存前按稳定 ID 重排端口并清理已删除分支的孤儿边', () => {
        const tasks = [{ task_id: 't1', nodes: [{
            node_id: 'branch', node_type: 'branch',
            params: { candidates: [{ candidate_id: 'cand_b' }, { candidate_id: 'cand_a' }] }
        }] }]
        const edges = [
            { edge_id: 'ea', source_node: 'branch', target_node: 'na', source_port: 'branch_0', source_port_id: 'cand_a' },
            { edge_id: 'eb', source_node: 'branch', target_node: 'nb', source_port: 'branch_1', source_port_id: 'cand_b' },
            { edge_id: 'gone', source_node: 'branch', target_node: 'nx', source_port: 'branch_2', source_port_id: 'cand_deleted' }
        ]
        expect(reconcileStablePortRoutes(tasks, edges)).toBe(true)
        expect(edges).toHaveLength(2)
        expect(edges.find(e => e.source_port_id === 'cand_b')?.source_port).toBe('branch_0')
        expect(edges.find(e => e.source_port_id === 'cand_a')?.source_port).toBe('branch_1')
    })

    it('removeEdge 只按 edge_id 断开', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'success' })
        applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'failure' })

        expect(removeEdge(edges, { edgeId: edges[0].edge_id })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(removeEdge(edges, { edgeId: edges[0].edge_id })).toBe(true)
        expect(edges).toHaveLength(0)
        expect(removeEdge(edges, { edgeId: 'missing' })).toBe(false)
    })

    it('disconnectPort 拉线空放断线', () => {
        const edges = []
        applyEdge(edges, { source: 'n2', target: 'n3', source_port: 'branch_1', source_port_id: 'cand_1' })
        expect(disconnectPort(edges, 'n2', 'branch_1')).toBe(true)
        expect(edges).toHaveLength(0)
        expect(disconnectPort(edges, 'n2', 'branch_1')).toBe(false)
    })

    it('removeNode 删除节点并清理关联边，同时保留可继续编辑的空流程', () => {
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
        expect(next2).toHaveLength(2)
        expect(edges).toHaveLength(0)
        expect(findTaskByNodeId(next2, 'n4')).toBeNull()
    })

    it('保存前删除孤儿边、消除重复名称并剥离旧跨任务字段', () => {
        const tasks = makeTasks()
        tasks[1].task_name = '组一'
        const edges = [
            { edge_id: 'cross', source_node: 'n1', target_node: 'n4', source_port: 'success', source_port_id: 'success' },
            { edge_id: 'orphan', source_node: 'n1', target_node: 'missing', source_port: 'failure', source_port_id: 'failure' }
        ]
        const report = reconcileGraphIntegrity(tasks, edges)
        expect(report.changed).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].target_task).toBeUndefined()
        expect(tasks.map(task => task.task_name)).toEqual(['组一', '组一'])
    })

    it('组名补位使用最小可用编号，删除任务组级联清除全部入边和出边', () => {
        const tasks = makeTasks()
        tasks.push({ task_id: 't3', task_name: '组一2', nodes: [{ node_id: 'n5' }] })
        tasks.push({ task_id: 't4', task_name: '组一', nodes: [{ node_id: 'n6' }] })
        expect(reconcileTaskNames(tasks)).toBe(1)
        expect(tasks[3].task_name).toBe('组一1')
        const edges = [
            { edge_id: 'in', source_node: 'n1', target_node: 'n4', source_port: 'success' },
            { edge_id: 'out', source_node: 'n4', target_node: 'n5', source_port: 'success' },
            { edge_id: 'keep', source_node: 'n5', target_node: 'n6', source_port: 'success' }
        ]
        const next = removeTask(tasks, edges, 't2')
        expect(next.some(task => task.task_id === 't2')).toBe(false)
        expect(edges.map(edge => edge.edge_id)).toEqual(['keep'])
    })
})

describe('workflowEdgeModel 拓扑出口边（exit_N）', () => {
    it('applyEdge 拓扑出口边创建（无标签字段，线上文字已移除）', () => {
        const edges = []
        expect(applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', source_port_id: 'port_a', canvas: 'topology' })).toBe(true)
        expect(edges[0].source_port).toBe('exit_0')
        expect(edges[0].label).toBeUndefined()
        expect(applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_2', source_port_id: 'port_b', canvas: 'topology' })).toBe(true)
        expect(edges[1].source_port).toBe('exit_2')
    })

    it('applyEdge workflow 边不生成标签', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'success', canvas: 'workflow' })
        expect(edges[0].label).toBeUndefined()
    })

    it('removeEdge 断连中间出口后，同源出口边重编号补位（exit_1→exit_0）', () => {
        const edges = []
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', source_port_id: 'port_a', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_1', source_port_id: 'port_b', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p4', source_port: 'exit_2', source_port_id: 'port_c', canvas: 'topology' })
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
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', source_port_id: 'port_a', canvas: 'topology' })
        applyEdge(edges, { source: 'p1', target: 'p3', source_port: 'exit_1', source_port_id: 'port_b', canvas: 'topology' })
        expect(disconnectPort(edges, 'p1', 'exit_0')).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('exit_0')
        expect(edges[0].target_node).toBe('p3')
    })

    it('断连非出口边不触发重编号', () => {
        const edges = []
        applyEdge(edges, { source: 'n1', target: 'n2', source_port: 'success' })
        applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'failure' })
        expect(removeEdge(edges, { edgeId: edges[0].edge_id })).toBe(true)
        expect(edges).toHaveLength(1)
        expect(edges[0].source_port).toBe('failure')
    })

    it('单条出口边删除后无需重编号', () => {
        const edges = []
        applyEdge(edges, { source: 'p1', target: 'p2', source_port: 'exit_0', source_port_id: 'port_a', canvas: 'topology' })
        expect(removeEdge(edges, { edgeId: edges[0].edge_id })).toBe(true)
        expect(edges).toHaveLength(0)
    })
})

describe('applyEdge 严格单画布连线', () => {
    it('不会再持久化旧 target_task 字段', () => {
        const tasks = [
            { task_id: 't1', nodes: [{ node_id: 'n1' }] },
            { task_id: 't2', nodes: [{ node_id: 'n2' }, { node_id: 'n3' }] }
        ]
        const edges = []
        // 跨组：n1(t1) -> n3(t2)
        expect(applyEdge(edges, { source: 'n1', target: 'n3', source_port: 'success', tasks })).toBe(true)
        expect(edges[0].target_task).toBeUndefined()
        // 同组：n2(t2) -> n3(t2)
        expect(applyEdge(edges, { source: 'n2', target: 'n3', source_port: 'success', tasks })).toBe(true)
        expect(edges[1].target_task).toBeUndefined()
        // 单画布边不再保存任务归属信息。
        expect(applyEdge(edges, { source: 'n1', target: 'nX', source_port: 'failure', tasks })).toBe(true)
        expect(edges[2].target_task).toBeUndefined()
        expect(applyEdge(edges, { source: 'n2', target: 'n3', source_port: 'failure' })).toBe(true)
        expect(edges[3].target_task).toBeUndefined()
    })
})
