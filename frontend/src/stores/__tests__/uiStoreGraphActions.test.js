import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/projectStore'
import { useUiStore } from '@/stores/uiStore'
import { createFunctionDefinition, createMainGraph, createPageMap } from '@/utils/flowModel'

describe('uiStore 当前画布批量操作', () => {
    let projectStore
    let uiStore
    let fn

    beforeEach(() => {
        setActivePinia(createPinia())
        projectStore = useProjectStore()
        uiStore = useUiStore()
        fn = createFunctionDefinition('测试函数')
        projectStore.blueprint = {
            main_graph: createMainGraph(),
            functions: [fn],
            page_map: createPageMap(),
            variables: {}, ui_state: {}, settings: {}
        }
        projectStore.blueprint.main_graph.nodes = [{ node_id: 'shared', delay_before: 1 }]
        projectStore.blueprint.page_map.nodes = [{ node_id: 'page', delay_before: 2 }]
        fn.graph.nodes.push({ node_id: 'fn-node', delay_before: 3 })
        vi.spyOn(projectStore, 'saveTopologyDebounced').mockImplementation(() => undefined)
        vi.spyOn(projectStore, 'saveWorkflowDebounced').mockImplementation(() => undefined)
    })

    it('拓扑模式只修改页面节点并保存 topology.json', async () => {
        uiStore.canvasMode = 'topology'
        uiStore.selectNodes(['page'])
        await uiStore.batchSetDelay(80)

        expect(projectStore.blueprint.page_map.nodes[0].delay_before).toBe(80)
        expect(projectStore.blueprint.main_graph.nodes[0].delay_before).toBe(1)
        expect(projectStore.saveTopologyDebounced).toHaveBeenCalledOnce()
        expect(projectStore.saveWorkflowDebounced).not.toHaveBeenCalled()
    })

    it('函数模式的全选和批量修改都限定在当前函数', async () => {
        projectStore.currentTaskId = fn.function_id
        uiStore.canvasMode = 'function'
        uiStore.selectAllNodes()
        expect(uiStore.selectedNodeIds).toEqual(expect.arrayContaining(fn.graph.nodes.map(node => node.node_id)))
        expect(uiStore.selectedNodeIds).not.toContain('shared')

        uiStore.selectNodes(['fn-node'])
        await uiStore.batchSetDelay(120)
        expect(fn.graph.nodes.find(node => node.node_id === 'fn-node').delay_before).toBe(120)
        expect(projectStore.blueprint.main_graph.nodes[0].delay_before).toBe(1)
        expect(projectStore.saveWorkflowDebounced).toHaveBeenCalledOnce()
    })
})
