import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProjectExplorerPanel from '../ProjectExplorerPanel.vue'
import { useProjectStore, useUiStore } from '@/stores'

const node = (id, x, y, name = id) => ({
    node_id: id, node_name: name, node_type: 'wait', params: {},
    position: { x, y }, size: { w: 160, h: 96 }
})

function mountPanel() {
    const project = useProjectStore()
    project.currentProjectPath = 'D:/Projects/V3Outline'
    project.currentProjectName = 'V3Outline'
    project.currentTaskId = 'main'
    project.blueprint = {
        schema_version: 3,
        main_graph: {
            graph_id: 'main',
            nodes: [node('inside', 120, 140, '区块内节点'), node('partial', 430, 140, '跨边界节点'), node('loose', 700, 140, '自由节点')],
            edges: [],
            blocks: [{ block_id: 'block_a', name: '登录阶段', x: 80, y: 80, width: 400, height: 260, color: 'slate' }]
        },
        functions: [], function_folders: [],
        page_map: { schema_version: 3, nodes: [], edges: [], blocks: [] },
        variables: {}, ui_state: {}, settings: {}
    }
    vi.spyOn(project, 'saveWorkflowImmediately').mockResolvedValue({ status: 'success' })
    useUiStore().canvasMode = 'workflow'
    return mount(ProjectExplorerPanel, { attachTo: document.body })
}

describe('ProjectExplorerPanel v3 主流程大纲', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        setActivePinia(createPinia())
    })

    it('按几何完整包含关系展示区块成员，其余节点保持无区块', () => {
        const wrapper = mountPanel()
        const section = wrapper.find('.block-section')
        expect(section.text()).toContain('登录阶段')
        expect(section.text()).toContain('区块内节点')
        expect(section.text()).not.toContain('跨边界节点')
        expect(wrapper.find('.loose-section').text()).toContain('跨边界节点')
        expect(wrapper.find('.loose-section').text()).toContain('自由节点')
        wrapper.unmount()
    })

    it('点击区块只选择完整位于区块内的节点', async () => {
        const wrapper = mountPanel()
        await wrapper.find('.block-row').trigger('click')
        await flushPromises()
        expect(useUiStore().selectedNodeIds).toEqual(['inside'])
        wrapper.unmount()
    })

    it('新建区块自动避让并使用不重复名称，不会为普通节点强制建区块', async () => {
        const wrapper = mountPanel()
        await wrapper.find('.icon-button').trigger('click')
        await flushPromises()
        const graph = useProjectStore().blueprint.main_graph
        expect(graph.blocks).toHaveLength(2)
        expect(graph.blocks[1].name).toBe('新区块')
        expect(graph.blocks[1]).toEqual(expect.objectContaining({ width: 400, height: 260 }))
        expect(graph.nodes).toHaveLength(3)
        expect(useProjectStore().saveWorkflowImmediately).toHaveBeenCalled()
        wrapper.unmount()
    })

    it('大纲单选与 Ctrl 增减多选和画布选择状态一致', async () => {
        const wrapper = mountPanel()
        const looseRows = wrapper.findAll('.loose-section .node-row')
        await looseRows[0].trigger('click')
        await looseRows[1].trigger('click', { ctrlKey: true })
        await flushPromises()
        expect(new Set(useUiStore().selectedNodeIds)).toEqual(new Set(['partial', 'loose']))
        wrapper.unmount()
    })
})
