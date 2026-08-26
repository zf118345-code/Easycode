import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import GlobalSearchDialog from '@/components/GlobalSearchDialog.vue'
import { useIdeStore, useProjectStore, useUiStore } from '@/stores'

vi.mock('element-plus', () => ({
    ElMessage: { error: vi.fn() }
}))

const DialogStub = {
    props: ['modelValue'],
    emits: ['update:modelValue', 'opened'],
    template: '<section><slot /></section>'
}

const InputStub = {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    methods: { focus() {} },
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
}

function mountDialog() {
    return mount(GlobalSearchDialog, {
        props: { modelValue: true },
        global: { stubs: { 'el-dialog': DialogStub, 'el-input': InputStub } }
    })
}

describe('GlobalSearchDialog', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        const project = useProjectStore()
        project.blueprint.main_graph.nodes = [
            { node_id: 'node-a', node_name: '登录按钮', node_type: 'click', params: {} },
            { node_id: 'node-b', node_name: '等待页面', node_type: 'wait', params: {} }
        ]
    })

    it('支持上下键循环选择并用 Enter 打开当前结果', async () => {
        const wrapper = mountDialog()
        wrapper.vm.query = 'node'
        await wrapper.vm.$nextTick()

        expect(wrapper.vm.results).toHaveLength(2)
        wrapper.vm.setActiveResult(0)
        wrapper.vm.moveActiveResult(-1)
        expect(wrapper.vm.activeResultIndex).toBe(1)

        await wrapper.vm.activateCurrentResult()
        await flushPromises()

        expect(useUiStore().selectedNodeIds).toEqual(['node-b'])
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
    })

    it('导航保存失败时保留弹窗并给出明确错误', async () => {
        const wrapper = mountDialog()
        const ide = useIdeStore()
        vi.spyOn(ide, 'navigateToGraph').mockRejectedValueOnce(new Error('拓扑保存失败'))
        const pageMap = wrapper.vm.results.find(item => item.kind === 'page_map')

        await wrapper.vm.activate(pageMap)

        expect(ElMessage.error).toHaveBeenCalledWith('拓扑保存失败')
        expect(wrapper.props('modelValue')).toBe(true)
        expect(wrapper.vm.activating).toBe(false)
    })
})
