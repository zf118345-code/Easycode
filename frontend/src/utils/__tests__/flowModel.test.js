import { describe, expect, it } from 'vitest'
import {
    MAIN_GRAPH_ID,
    SYSTEM_EXCEPTION_OUTCOME_ID,
    collectFunctionReferences,
    createFunctionDefinition,
    createMainGraph,
    createPageMap,
    getGraph,
} from '@/utils/flowModel'

describe('v3 画布与函数模型', () => {
    it('为主流程和页面地图创建唯一的扁平画布', () => {
        expect(createMainGraph()).toEqual({ graph_id: MAIN_GRAPH_ID, nodes: [], edges: [] })
        expect(createPageMap()).toEqual({ schema_version: 3, nodes: [], edges: [] })
    })

    it('新函数拥有独立画布、固定入口、显式返回与系统异常出口', () => {
        const fn = createFunctionDefinition('登录')
        expect(fn.name).toBe('登录')
        expect(fn.graph.graph_id).toBe(fn.function_id)
        expect(fn.graph.nodes.map(node => node.node_type)).toEqual(['function_entry', 'function_return'])
        expect(fn.graph.nodes[0].fixed).toBe(true)
        expect(fn.outcomes.some(item => item.outcome_id === SYSTEM_EXCEPTION_OUTCOME_ID && item.immutable)).toBe(true)
    })

    it('按画布 ID 读取主流程、函数与页面地图', () => {
        const fn = createFunctionDefinition('识别页面')
        const blueprint = { main_graph: createMainGraph(), functions: [fn], page_map: createPageMap() }
        expect(getGraph(blueprint, MAIN_GRAPH_ID)).toBe(blueprint.main_graph)
        expect(getGraph(blueprint, fn.function_id)).toBe(fn.graph)
        expect(getGraph(blueprint, MAIN_GRAPH_ID, 'topology')).toBe(blueprint.page_map)
    })

    it('删除函数前能找出主流程和其他函数中的实时调用', () => {
        const fn = createFunctionDefinition('子函数')
        const caller = createFunctionDefinition('调用者')
        caller.graph.nodes.push({ node_id: 'call_b', node_type: 'call_function', params: { function_id: fn.function_id } })
        const blueprint = {
            main_graph: { ...createMainGraph(), nodes: [{ node_id: 'call_a', node_type: 'call_function', params: { function_id: fn.function_id } }] },
            functions: [fn, caller],
        }
        expect(collectFunctionReferences(blueprint, fn.function_id)).toEqual([
            { ownerGraphId: MAIN_GRAPH_ID, nodeId: 'call_a', targetFunctionId: fn.function_id },
            { ownerGraphId: caller.function_id, nodeId: 'call_b', targetFunctionId: fn.function_id },
        ])
    })
})
