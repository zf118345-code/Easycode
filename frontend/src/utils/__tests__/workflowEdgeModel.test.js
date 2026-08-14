import { describe, it, expect } from 'vitest'
import {
    deriveWorkflowEdges,
    applyWorkflowEdge,
    removeWorkflowEdge,
    disconnectWorkflowPort,
    removeWorkflowNode,
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
                {
                    node_id: 'n2',
                    node_name: '分支',
                    node_type: 'branch',
                    params: { candidates: [{ on_success: {} }, { on_success: {} }] },
                    position: { x: 200, y: 0 }
                },
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

describe('workflowEdgeModel', () => {
    it('deriveWorkflowEdges 从 params 派生三类连线', () => {
        const tasks = makeTasks()
        tasks[0].nodes[0].params.on_success = { target_node: 'n2' }
        tasks[0].nodes[0].params.on_failure = { target_node: 'n3' }
        tasks[0].nodes[1].params.candidates[0].on_success = { target_node: 'n3' }

        const edges = deriveWorkflowEdges(tasks)
        expect(edges).toHaveLength(3)
        const succ = edges.find(e => e.legacyPort === 'succ')
        expect(succ.sourceNodeId).toBe('n1')
        expect(succ.targetNodeId).toBe('n2')
        const fail = edges.find(e => e.legacyPort === 'fail')
        expect(fail.isFailFlag).toBe(true)
        const branch = edges.find(e => e.legacyPort === 'branch_0')
        expect(branch.extra.candIndex).toBe(0)
    })

    it('deriveWorkflowEdges 忽略目标不存在的连线', () => {
        const tasks = makeTasks()
        tasks[0].nodes[0].params.on_success = { target_node: 'ghost' }
        expect(deriveWorkflowEdges(tasks)).toHaveLength(0)
    })

    it('deriveWorkflowEdges 派生 branch 节点的 success 连线（Step 4）', () => {
        const tasks = makeTasks()
        tasks[0].nodes[1].params.on_success = { target_node: 'n3' }
        const edges = deriveWorkflowEdges(tasks)
        const succ = edges.find(e => e.legacyPort === 'succ' && e.sourceNodeId === 'n2')
        expect(succ).toBeTruthy()
        expect(succ.targetNodeId).toBe('n3')
    })

    it('applyWorkflowEdge 写入 success/failure/branch 端口', () => {
        const tasks = makeTasks()
        expect(applyWorkflowEdge(tasks, { source: 'n1', target: 'n4', source_port: 'succ' })).toBe(true)
        expect(tasks[0].nodes[0].params.on_success).toEqual({ target_task: 't2', target_node: 'n4' })

        expect(applyWorkflowEdge(tasks, { source: 'n1', target: 'n3', source_port: 'fail' })).toBe(true)
        expect(tasks[0].nodes[0].params.on_failure).toEqual({ target_task: 't1', target_node: 'n3' })

        expect(applyWorkflowEdge(tasks, { source: 'n2', target: 'n3', source_port: 'branch_0' })).toBe(true)
        expect(tasks[0].nodes[1].params.candidates[0].on_success.target_node).toBe('n3')
    })

    it('applyWorkflowEdge 拒绝自连/无效源/无效分支索引', () => {
        const tasks = makeTasks()
        expect(applyWorkflowEdge(tasks, { source: 'n1', target: 'n1', source_port: 'succ' })).toBe(false)
        expect(applyWorkflowEdge(tasks, { source: 'ghost', target: 'n2', source_port: 'succ' })).toBe(false)
        // branch_5 不存在
        expect(applyWorkflowEdge(tasks, { source: 'n2', target: 'n3', source_port: 'branch_5' })).toBe(false)
    })

    it('removeWorkflowEdge / disconnectWorkflowPort 断开连线', () => {
        const tasks = makeTasks()
        applyWorkflowEdge(tasks, { source: 'n1', target: 'n2', source_port: 'succ' })
        expect(removeWorkflowEdge(tasks, { sourceNodeId: 'n1', legacyPort: 'succ' })).toBe(true)
        expect(tasks[0].nodes[0].params.on_success).toEqual({})

        applyWorkflowEdge(tasks, { source: 'n2', target: 'n3', source_port: 'branch_1' })
        expect(disconnectWorkflowPort(tasks, 'n2', 'branch_1')).toBe(true)
        expect(tasks[0].nodes[1].params.candidates[1].on_success).toEqual({})
    })

    it('removeWorkflowNode 删除节点并清理空任务组', () => {
        const tasks = makeTasks()
        const next = removeWorkflowNode(tasks, 'n4')
        expect(next).toHaveLength(1)
        expect(findNodeInTasks(next, 'n4')).toBeNull()

        const next2 = removeWorkflowNode(next, 'n1')
        expect(findTaskByNodeId(next2, 'n1')).toBeNull()
    })
})
