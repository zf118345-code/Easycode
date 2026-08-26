import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/blueprintApi', () => ({
    blueprintApi: {
        getParams: vi.fn().mockResolvedValue({}),
        getBlueprint: vi.fn(),
        getWorkflow: vi.fn(),
        getTopology: vi.fn(),
        saveBlueprint: vi.fn().mockResolvedValue({ status: 'success' }),
        saveWorkflow: vi.fn().mockResolvedValue({ status: 'success' }),
        saveTopology: vi.fn().mockResolvedValue({ status: 'success' })
    }
}))

import InspectorPanel from '../InspectorPanel.vue'
import { blueprintApi } from '@/api/blueprintApi'
import { useIdeStore, useProjectStore, useUiStore } from '@/stores'

const NodeEditorStub = {
    name: 'NodeInspectorPanel',
    props: { node: { type: Object, required: true } },
    template: '<input data-testid="node-name" :value="node.node_name" @input="node.node_name = $event.target.value" />'
}

describe('InspectorPanel 自动保存', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
    })

    it('输入后立即写回平面页面地图，并在切换画布前排空保存队列', async () => {
        const project = useProjectStore()
        project._applyWorkspace({
            workspace_id: 'workspace_demo',
            generation: 1,
            project_id: 'project_demo',
            project_name: 'demo',
            project_path: 'D:/projects/demo',
            revision: 0,
            read_only: false
        })
        project.blueprint = {
            schema_version: 3,
            project_id: 'project_demo',
            project_name: 'demo',
            variables: {},
            ui_state: {},
            settings: {},
            main_graph: { graph_id: 'main', nodes: [], edges: [] },
            functions: [],
            function_folders: [],
            page_map: {
                schema_version: 3,
                nodes: [{
                        node_id: 'page_1',
                        node_name: '旧名称',
                        node_type: 'page_state',
                        delay_before: 0,
                        loop_count: 1,
                        params: {}
                    }],
                edges: []
            }
        }
        const ui = useUiStore()
        ui.canvasMode = 'topology'
        ui.selectNode('page_1')

        const wrapper = mount(InspectorPanel, {
            global: {
                stubs: {
                    NodeInspectorPanel: NodeEditorStub,
                    BatchInspectorPanel: true,
                    GroupInspectorPanel: true,
                    MousePointerClick: true
                }
            }
        })
        await flushPromises()

        await wrapper.get('[data-testid="node-name"]').setValue('新页面名称')
        expect(project.blueprint.page_map.nodes[0].node_name).toBe('新页面名称')
        expect(project.hasPendingSaves()).toBe(true)

        await useIdeStore().setCanvasMode('workflow')

        expect(blueprintApi.saveTopology).toHaveBeenCalledWith(
            'D:/projects/demo',
            expect.objectContaining({
                nodes: [expect.objectContaining({ node_name: '新页面名称' })]
            }),
            { workspaceId: 'workspace_demo', generation: 1 }
        )
        expect(ui.canvasMode).toBe('workflow')
        project.cancelPendingSaves()
        wrapper.unmount()
    })
})
