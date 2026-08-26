import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import CanvasPage from '@/components/CanvasPage.vue'
import InspectorPanel from '@/components/inspector/InspectorPanel.vue'
import FunctionLibraryPanel from '../FunctionLibraryPanel.vue'
import { useProjectStore, useUiStore } from '@/stores'

vi.mock('@/api/blueprintApi', () => ({
    blueprintApi: {
        saveWorkflow: vi.fn().mockResolvedValue({ status: 'success' }),
        saveTopology: vi.fn().mockResolvedValue({ status: 'success' }),
        saveBlueprint: vi.fn().mockResolvedValue({ status: 'success' })
    }
}))

const functionDefinition = () => ({
    function_id: 'function_login',
    name: '登录函数',
    description: '完成登录并返回结果',
    folder_id: null,
    parameters: [],
    local_variables: [],
    outputs: [],
    outcomes: [
        { outcome_id: 'outcome_success', name: '成功', color: 'success' },
        { outcome_id: 'system_exception', name: '异常', color: 'danger', immutable: true }
    ],
    test_cases: [],
    graph: {
        graph_id: 'function_login',
        entry_node_id: 'function_entry',
        nodes: [{ node_id: 'function_entry', node_name: '函数入口', node_type: 'function_entry', params: {} }],
        edges: []
    }
})

function activateProject() {
    const project = useProjectStore()
    project.currentProjectName = '函数工作区测试'
    project.currentTaskId = 'main'
    project.blueprint = {
        schema_version: 3,
        project_name: '函数工作区测试',
        variables: {}, ui_state: {}, settings: {},
        main_graph: { graph_id: 'main', nodes: [], edges: [] },
        functions: [functionDefinition()],
        function_folders: [],
        page_map: { schema_version: 3, nodes: [], edges: [] }
    }
    return project
}

describe('函数库、画布与检查器联动', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        globalThis.ResizeObserver = class ResizeObserver { observe() {} disconnect() {} }
        activateProject()
    })

    it('进入函数入口先展示空工作区，不误挂载主流程画布', () => {
        useUiStore().enterFunctionLibrary()
        const wrapper = mount(CanvasPage, { global: { stubs: { CanvasView: { template: '<div class="canvas-view-stub" />' } } } })
        expect(wrapper.find('.function-workspace-empty').text()).toContain('选择一个函数开始编辑')
        expect(wrapper.find('.canvas-view-stub').exists()).toBe(false)
        wrapper.unmount()
    })

    it('单击函数列表立即打开对应函数画布并展开右侧检查器', async () => {
        const project = useProjectStore()
        const ui = useUiStore()
        ui.enterFunctionLibrary()
        const wrapper = mount(FunctionLibraryPanel)

        await wrapper.find('.function-row').trigger('click')
        await flushPromises()

        expect(project.currentTaskId).toBe('function_login')
        expect(ui.canvasMode).toBe('function')
        expect(ui.functionWorkspaceEmpty).toBe(false)
        expect(project.blueprint.ui_state.rightPanelExpanded).toBe(true)
        expect(ui.focusTarget).toEqual(expect.objectContaining({ type: 'graph', id: 'function_login' }))
        wrapper.unmount()
    })

    it('函数未选节点时显示函数检查器，选中节点后节点检查器优先', async () => {
        const project = useProjectStore()
        const ui = useUiStore()
        project.currentTaskId = 'function_login'
        ui.showFunctionGraph()
        const wrapper = mount(InspectorPanel, {
            global: {
                stubs: {
                    FunctionInspectorPanel: { template: '<div class="function-inspector-stub" />' },
                    NodeInspectorPanel: { template: '<div class="node-inspector-stub" />' },
                    BatchInspectorPanel: { template: '<div class="batch-inspector-stub" />' }
                }
            }
        })

        expect(wrapper.find('.function-inspector-stub').exists()).toBe(true)
        ui.selectNode('function_entry')
        await flushPromises()
        expect(wrapper.find('.node-inspector-stub').exists()).toBe(true)
        expect(wrapper.find('.function-inspector-stub').exists()).toBe(false)
        wrapper.unmount()
    })
})
