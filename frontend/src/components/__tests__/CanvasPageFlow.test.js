import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import CanvasPage from '@/components/CanvasPage.vue'
import { blueprintApi } from '@/api/blueprintApi'
import { useProjectStore } from '@/stores/projectStore'
import { useUiStore } from '@/stores/uiStore'
import { useIdeStore } from '@/stores'

vi.mock('@/api/blueprintApi', () => ({
    blueprintApi: {
        saveWorkflow: vi.fn(),
        saveTopology: vi.fn(),
        saveBlueprint: vi.fn(),
    },
}))

const CanvasViewStub = {
    name: 'CanvasView',
    template: '<div class="canvas-view-stub" />',
    methods: {
        getViewportCenter() { return { x: 100, y: 120 } },
    },
}

function mountCanvas() {
    return mount(CanvasPage, {
        global: {
            stubs: {
                CanvasView: CanvasViewStub,
                'el-dialog': true,
                'el-form': true,
                'el-form-item': true,
                'el-radio-group': true,
                'el-radio-button': true,
                'el-alert': true,
                'el-button': true,
            },
        },
    })
}

function mountInteractiveCanvas() {
    return mount(CanvasPage, {
        attachTo: document.body,
        global: {
            stubs: {
                CanvasNodeCard: true,
                CanvasEdgeLayer: true,
                'el-dialog': true,
                'el-form': true,
                'el-form-item': true,
                'el-radio-group': true,
                'el-radio-button': true,
                'el-alert': true,
                'el-button': true,
            },
        },
    })
}

function activateProject() {
    const project = useProjectStore()
    project.currentProjectPath = 'D:/test/canvas-project'
    project.workspaceId = 'workspace-test'
    project.workspaceGeneration = 3
    project.blueprint = {
        schema_version: 3,
        project_id: 'project_test',
        revision: 0,
        project_name: '画布测试',
        variables: {},
        ui_state: {},
        settings: {},
        main_graph: { graph_id: 'main', nodes: [], edges: [] },
        functions: [],
        function_folders: [],
        page_map: { schema_version: 3, nodes: [], edges: [] },
    }
    return project
}

describe('CanvasPage 捕获到持久化全流程', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
        globalThis.ResizeObserver = class ResizeObserver {
            observe() {}
            disconnect() {}
        }
        HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
            clearRect: vi.fn(),
            fillRect: vi.fn(),
            strokeRect: vi.fn(),
            fillStyle: '',
            strokeStyle: '',
            lineWidth: 1,
        }))
        blueprintApi.saveWorkflow.mockResolvedValue({ status: 'success' })
        blueprintApi.saveTopology.mockResolvedValue({ status: 'success' })
    })

    it('连续捕获点击和图像节点，直接写入主流程、连线并逐次保存 workflow', async () => {
        const wrapper = mountCanvas()
        await flushPromises()
        const project = activateProject()
        await nextTick()

        const first = await wrapper.vm.executeCaptureCommand({
            snapshot_id: 'snapshot-1',
            capture_chain_id: 'chain-1',
            capture_context: {
                anchorKind: 'project',
                groupId: 'task_main',
                viewportCenter: { x: 100, y: 120 },
            },
            kind: 'click',
            point: [75, 90],
            reference_size: [960, 540],
            operation_id: 'operation-1',
        })
        const second = await wrapper.vm.executeCaptureCommand({
            snapshot_id: 'snapshot-1',
            capture_chain_id: 'chain-1',
            kind: 'image',
            rects: [[10, 20, 30, 40]],
            asset_refs: ['asset://asset_button'],
            reference_size: [960, 540],
            operation_id: 'operation-2',
        })

        expect(first.ok).toBe(true)
        expect(second.ok).toBe(true)
        expect(project.blueprint.main_graph.nodes.map(node => node.node_type)).toEqual([
            'click', 'image_recognition',
        ])
        expect(project.blueprint.main_graph.nodes[0].params.position).toEqual([75, 90])
        expect(project.blueprint.main_graph.nodes[1].params).toEqual(expect.objectContaining({
            image_source: 'asset://asset_button',
            region_type: 'recorded',
            region_value: [10, 20, 30, 40],
            region_reference_size: [960, 540],
        }))
        expect(project.blueprint.main_graph.edges).toHaveLength(1)
        expect(project.blueprint.main_graph.edges[0]).toEqual(expect.objectContaining({
            source_node: first.nodeId,
            target_node: second.nodeId,
        }))
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(2)
    })

    it('拓扑多框捕获只生成一个页面节点，并保存稳定 page_id 与 AND 特征', async () => {
        const wrapper = mountCanvas()
        await flushPromises()
        const project = activateProject()
        useUiStore().setCanvasMode('topology')

        const result = await wrapper.vm.executeCaptureCommand({
            snapshot_id: 'snapshot-page',
            capture_chain_id: 'chain-page',
            capture_context: {
                anchorKind: 'new_collection',
                viewportCenter: { x: 180, y: 200 },
            },
            kind: 'page',
            rects: [[1, 2, 30, 40], [50, 60, 70, 80]],
            asset_refs: ['asset://asset_a', 'asset://asset_b'],
            reference_size: [960, 540],
            operation_id: 'operation-page',
        })

        expect(result.ok).toBe(true)
        const nodes = project.blueprint.page_map.nodes
        expect(nodes).toHaveLength(1)
        expect(nodes[0].node_type).toBe('page_state')
        expect(nodes[0].node_name).toBe('页面节点')
        expect(nodes[0].params.page_id).toMatch(/^page_/)
        expect(nodes[0].params.feature_mode).toBe('and')
        expect(nodes[0].params.features).toHaveLength(2)
        expect(nodes[0].params.features.every(item => item.condition_type === 'image_exists')).toBe(true)
        expect(blueprintApi.saveTopology).toHaveBeenCalledTimes(1)
    })

    it('从空出口拖到空白处新建节点时，同一次操作生成节点和连线', async () => {
        const wrapper = mountCanvas()
        await flushPromises()
        const project = activateProject()
        project.blueprint.main_graph = {
            graph_id: 'main', nodes: [{
                node_id: 'node_a', node_name: '起点', node_type: 'log', params: {}, position: { x: 0, y: 0 }
            }], edges: []
        }

        wrapper.findComponent(CanvasViewStub).vm.$emit('create-node', {
            nodeId: 'node_b',
            type: 'wait',
            position: { x: 240, y: 0 },
            sourceNodeId: 'node_a',
            portType: 'success',
            sourcePortId: 'success'
        })
        await flushPromises()

        expect(project.blueprint.main_graph.nodes.map(node => node.node_id)).toEqual(['node_a', 'node_b'])
        expect(project.blueprint.main_graph.edges).toEqual([expect.objectContaining({
            source_node: 'node_a',
            target_node: 'node_b',
            source_port: 'success',
            source_port_id: 'success'
        })])
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(1)
        const ui = useUiStore()
        expect(ui.selectedNodeIds).toEqual(['node_b'])
        expect(ui.focusTarget).toEqual(expect.objectContaining({ type: 'node', id: 'node_b' }))
    })

    it('从画布工具栏打开节点菜单，点击类型后创建并持久化节点', async () => {
        const project = activateProject()
        const wrapper = mountInteractiveCanvas()
        await flushPromises()

        const canvas = wrapper.find('.custom-canvas-container')
        Object.defineProperty(canvas.element, 'getBoundingClientRect', {
            configurable: true,
            value: () => ({ left: 0, top: 0, width: 960, height: 540, right: 960, bottom: 540 }),
        })

        await wrapper.find('button[title="新建节点"]').trigger('click')
        await nextTick()
        expect(wrapper.find('.spawn-menu').exists()).toBe(true)

        const waitItem = wrapper.findAll('.spawn-menu-item').find(item => item.text().includes('等待'))
        expect(waitItem).toBeTruthy()
        await waitItem.trigger('click')
        await flushPromises()

        expect(project.blueprint.main_graph.nodes).toHaveLength(1)
        expect(project.blueprint.main_graph.nodes[0]).toEqual(expect.objectContaining({
            node_type: 'wait',
            node_name: '等待节点',
        }))
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(1)
        expect(wrapper.find('.spawn-menu').exists()).toBe(false)
        wrapper.unmount()
    })

    it('切换画布前权威保存当前拓扑，保存失败时保持当前模式和内存数据', async () => {
        const project = activateProject()
        const ui = useUiStore()
        const ide = useIdeStore()
        ui.setCanvasMode('topology')
        project.blueprint.page_map.nodes = [{
                node_id: 'page_a', node_name: '页面A', node_type: 'page_state',
                params: { page_id: 'page_a', features: [] }
            }]

        blueprintApi.saveTopology.mockRejectedValueOnce(new Error('disk busy'))
        await expect(ide.setCanvasMode('workflow')).rejects.toThrow('disk busy')
        expect(ui.canvasMode).toBe('topology')
        expect(project.blueprint.page_map.nodes[0].node_name).toBe('页面A')

        blueprintApi.saveTopology.mockResolvedValueOnce({ status: 'success' })
        await ide.setCanvasMode('workflow')
        expect(ui.canvasMode).toBe('workflow')
        expect(blueprintApi.saveTopology).toHaveBeenLastCalledWith(
            'D:/test/canvas-project',
            expect.objectContaining({ nodes: [expect.objectContaining({ node_id: 'page_a' })] }),
            { workspaceId: 'workspace-test', generation: 3 }
        )
    })

    it('从空函数工作区打开函数时，通过同一导航屏障保存旧画布并展示目标函数', async () => {
        const project = activateProject()
        const ui = useUiStore()
        const ide = useIdeStore()
        project.blueprint.functions = [{
            function_id: 'fn_target',
            name: '目标函数',
            graph: { graph_id: 'fn_target', nodes: [], edges: [] },
            parameters: [], outputs: [], local_variables: [], outcomes: [],
        }]
        ui.enterFunctionLibrary()

        await ide.navigateToGraph('function', 'fn_target')

        expect(project.currentTaskId).toBe('fn_target')
        expect(ui.canvasMode).toBe('function')
        expect(ui.functionWorkspaceEmpty).toBe(false)
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(1)
    })

    it('导航前保存失败时不改变当前任务、模式或函数空工作区状态', async () => {
        const project = activateProject()
        const ui = useUiStore()
        const ide = useIdeStore()
        project.blueprint.functions = [{
            function_id: 'fn_target',
            name: '目标函数',
            graph: { graph_id: 'fn_target', nodes: [], edges: [] },
            parameters: [], outputs: [], local_variables: [], outcomes: [],
        }]
        ui.setCanvasMode('topology')
        blueprintApi.saveTopology.mockRejectedValueOnce(new Error('topology locked'))

        await expect(ide.navigateToGraph('function', 'fn_target')).rejects.toThrow('topology locked')

        expect(project.currentTaskId).toBe('main')
        expect(ui.canvasMode).toBe('topology')
        expect(ui.functionWorkspaceEmpty).toBe(false)
    })
})
