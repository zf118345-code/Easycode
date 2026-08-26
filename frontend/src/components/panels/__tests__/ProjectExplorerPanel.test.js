import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProjectExplorerPanel from '../ProjectExplorerPanel.vue'
import { useProjectStore, useUiStore } from '@/stores'

const node = (id, name = id) => ({
    node_id: id, node_name: name, node_type: 'wait', params: {},
    position: { x: 80, y: 80 }, size: { w: 160, h: 96 }
})

function edge(id, source, target) {
    return { edge_id: id, source_node: source, target_node: target, source_port: 'success', source_port_id: 'success' }
}

function mountPanel() {
    const project = useProjectStore()
    project.currentProjectPath = 'D:/Projects/V3Outline'
    project.currentProjectName = 'V3Outline'
    project.currentTaskId = 'main'
    project.blueprint = {
        schema_version: 3,
        main_graph: {
            graph_id: 'main',
            nodes: [node('start', '开始节点'), node('middle', '处理中间页'), node('finish', '完成节点')],
            edges: [edge('e1', 'start', 'middle'), edge('e2', 'middle', 'finish')]
        },
        functions: [], function_folders: [],
        page_map: { schema_version: 3, nodes: [], edges: [] },
        variables: {}, ui_state: {}, settings: {}
    }
    vi.spyOn(project, 'saveWorkflowImmediately').mockResolvedValue({ status: 'success' })
    useUiStore().canvasMode = 'workflow'
    return mount(ProjectExplorerPanel, { attachTo: document.body })
}

describe('ProjectExplorerPanel 主流程大纲', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        setActivePinia(createPinia())
    })

    it('以扁平列表展示主流程全部节点，不再出现区块入口', () => {
        const wrapper = mountPanel()
        expect(wrapper.findAll('.node-row')).toHaveLength(3)
        expect(wrapper.text()).toContain('开始节点')
        expect(wrapper.text()).toContain('处理中间页')
        expect(wrapper.text()).not.toContain('V3Outline')
        expect(wrapper.find('.node-row small').text()).toBe('等待')
        expect(wrapper.text()).not.toContain('区块')
        wrapper.unmount()
    })

    it('单击与 Ctrl 单击同步画布多选状态', async () => {
        const wrapper = mountPanel()
        const rows = wrapper.findAll('.node-row')
        await rows[0].trigger('click')
        await rows[2].trigger('click', { ctrlKey: true })
        await flushPromises()
        expect(new Set(useUiStore().selectedNodeIds)).toEqual(new Set(['start', 'finish']))
        wrapper.unmount()
    })

    it('Shift 单击选中两个节点之间的路径节点和连线', async () => {
        const wrapper = mountPanel()
        const rows = wrapper.findAll('.node-row')
        await rows[0].trigger('click')
        await rows[2].trigger('click', { shiftKey: true })
        await flushPromises()
        expect(useUiStore().selectedNodeIds).toEqual(['start', 'middle', 'finish'])
        expect(useUiStore().selectedEdgeIds).toEqual(['e1', 'e2'])
        wrapper.unmount()
    })

    it('搜索只保留名称或类型匹配的节点', async () => {
        const wrapper = mountPanel()
        await wrapper.find('.outline-search input').setValue('完成')
        expect(wrapper.findAll('.node-row')).toHaveLength(1)
        expect(wrapper.find('.node-row').text()).toContain('完成节点')
        await wrapper.find('.outline-search input').setValue('等待')
        expect(wrapper.findAll('.node-row')).toHaveLength(3)
        wrapper.unmount()
    })
})
