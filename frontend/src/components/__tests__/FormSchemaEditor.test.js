// frontend/src/components/__tests__/FormSchemaEditor.test.js
// ⚡ 打包页新增能力回归：运行入口配置（entry）与一键上下文配置组
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import FormSchemaEditor from '@/components/schema/FormSchemaEditor.vue'
import { exporterApi } from '@/api/exporterApi'
import { useProjectStore } from '@/stores/projectStore'

vi.mock('@/api/exporterApi', () => ({
    exporterApi: {
        getFormSchema: vi.fn(),
        saveFormSchema: vi.fn()
    }
}))
vi.mock('@/api/client', () => ({ default: { post: vi.fn() } }))

function makeStore() {
    setActivePinia(createPinia())
    const store = useProjectStore()
    store.currentProjectPath = 'D:/test/proj'
    store.blueprint = {
        variables: { numrun: 0, isnew: false },
        main_graph: { graph_id: 'main', nodes: [{ node_id: 'n1', node_name: '日志A' }, { node_id: 'n2', node_name: '点击B' }], edges: [], blocks: [] },
        functions: [], function_folders: [],
        page_map: { nodes: [{
            node_id: 'page_login', node_name: '登录页', node_type: 'page_state',
            params: { page_id: 'page_login_stable', features: [{ condition_type: 'image_exists', image_source: 'asset://login' }] }
        }], edges: [], blocks: [] }
    }
    return store
}

async function mountEditor() {
    const wrapper = mount(FormSchemaEditor, {
        props: { modelValue: false },
        global: { stubs: { teleport: true } }
    })
    await wrapper.setProps({ modelValue: true })  // 触发 watch 加载
    await flushPromises()
    await wrapper.vm.$nextTick()
    return wrapper
}

describe('FormSchemaEditor 打包页增强', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        makeStore()
        exporterApi.getFormSchema.mockResolvedValue({ form_title: '测试面板', groups: [] })
    })

    it('Player 入口只能选择主流程节点，保存时写入稳定入口', async () => {
        const wrapper = await mountEditor()
        const vm = wrapper.vm

        expect(vm.entryTaskId).toBe('main')
        expect(vm.entryNodes.map(n => n.node_id)).toEqual(['n1', 'n2'])
        vm.entryNodeId = 'n2'
        await vm.$nextTick()

        await vm.handleSaveSchema()
        await flushPromises()
        const saved = exporterApi.saveFormSchema.mock.calls[0][1]
        expect(saved.entry).toEqual({ task_id: 'main', node_id: 'n2', node_name: '点击B' })

        // 清除入口
        vm.clearEntry()
        await vm.handleSaveSchema()
        await flushPromises()
        const saved2 = exporterApi.saveFormSchema.mock.calls[1][1]
        expect(saved2.entry).toBeNull()
    })

    it('一键添加上下文配置：生成「窗口与裁剪」分组（8 个 $ctx 字段）', async () => {
        const wrapper = await mountEditor()
        wrapper.vm.addContextFields()
        await wrapper.vm.$nextTick()

        const group = wrapper.vm.localSchema.groups.find(g => g.group_title === '窗口与裁剪')
        expect(group).toBeTruthy()
        expect(group.fields).toHaveLength(8)
        expect(group.fields[0].target).toBe('$ctx.window_title')
        expect(group.fields[0].provider).toBe('sys.window_list')
        expect(group.fields[1].target).toBe('$ctx.is_emulator')
        expect(group.fields.find(f => f.target === '$ctx.target_content_width').default).toBe(1280)

        // 重复添加覆盖更新而非追加
        wrapper.vm.addContextFields()
        const groups = wrapper.vm.localSchema.groups.filter(g => g.group_title === '窗口与裁剪')
        expect(groups).toHaveLength(1)
    })

    it('打开时回显已保存的 entry 配置', async () => {
        exporterApi.getFormSchema.mockResolvedValue({
            form_title: '测试面板',
            groups: [],
            entry: { task_id: 'main', node_id: 'n1', node_name: '日志A' }
        })
        const wrapper = await mountEditor()
        expect(wrapper.vm.entryTaskId).toBe('main')
        expect(wrapper.vm.entryNodeId).toBe('n1')
        expect(wrapper.vm.localSchema.entry).toEqual({ task_id: 'main', node_id: 'n1', node_name: '日志A' })
    })

    it('可将页面特征中的嵌套图片暴露为 Player 截图字段', async () => {
        const wrapper = await mountEditor()
        const target = '$node.page_login.params.features.0.image_source'
        const option = wrapper.vm.nodeBindingOptions.find(item => item.target === target)
        expect(option).toBeTruthy()
        expect(option.label).toContain('features / #1 / image_source')

        const field = { target, ui_type: 'str', default: '' }
        wrapper.vm.onTargetChange(field)
        expect(field.ui_type).toBe('image_asset')
        expect(field.default).toBe('asset://login')
    })
})
