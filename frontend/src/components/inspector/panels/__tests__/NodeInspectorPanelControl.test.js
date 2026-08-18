// frontend/src/components/inspector/panels/__tests__/NodeInspectorPanelControl.test.js
// C 环节：NodeInspectorPanel 遍历渲染 control 节点 schema
//   - 每个参数（action/by/target/window_title/index/text_input/save_to_var/timeout）都渲染出对应 ParamRenderer
//   - config 透传正确（type/label/default）
//   - on_success/on_failure 不渲染（网关排除）
//   - 参数更新 → emit save
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import NodeInspectorPanel from '../NodeInspectorPanel.vue'
import { useProjectStore } from '@/stores'
import { CONTROL_SCHEMA } from '@/testFixtures/controlSchema'
import { buildNodeDefaultParams } from '@/utils/nodeDefaults'

globalThis.ResizeObserver = globalThis.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} }

// ParamRenderer stub：渲染 label|type 供遍历断言，支持 update 事件回传
const ParamRendererStub = {
    name: 'ParamRenderer',
    props: ['config', 'value', 'label', 'context'],
    emits: ['update', 'autoChangeType'],
    template: '<div class="pr-stub">{{ label }}|{{ config.type }}|{{ JSON.stringify(config) }}</div>'
}

function makeNode() {
    const params = buildNodeDefaultParams('control', { control: CONTROL_SCHEMA })
    return {
        node_id: 'ctrl_1',
        node_name: '我的控件节点',
        node_type: 'control',
        params: { ...params, target: '开始游戏' },
        delay_before: 200,
        loop_count: 1
    }
}

function mountPanel(node = makeNode()) {
    return mount(NodeInspectorPanel, {
        props: { node },
        attachTo: document.body,
        global: {
            stubs: {
                ParamRenderer: ParamRendererStub,
                'el-dialog': true,
                'el-tooltip': true
            }
        }
    })
}

describe('NodeInspectorPanel × control 节点', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        setActivePinia(createPinia())
        useProjectStore().paramsDefinitions = { control: CONTROL_SCHEMA }
    })

    it('遍历渲染全部 8 个参数（含 visible_if 依赖的 text_input/save_to_var）', () => {
        const wrapper = mountPanel()
        const stubs = wrapper.findAll('.pr-stub').map(w => w.text())
        expect(stubs).toHaveLength(8)
        for (const label of ['操作方式', '查找方式', '控件标识', '目标窗口标题', '匹配序号', '输入内容', '保存结果到变量', '查找超时时长']) {
            expect(stubs.some(t => t.startsWith(label))).toBe(true)
        }
        wrapper.unmount()
    })

    it('on_success/on_failure 不进入渲染列表（网关排除）', () => {
        const node = makeNode()
        node.params.on_success = { target_node: 'n2' }
        node.params.on_failure = { target_node: 'n3' }
        const wrapper = mountPanel(node)
        const texts = wrapper.findAll('.pr-stub').map(w => w.text()).join('|')
        expect(texts).not.toContain('on_success')
        expect(texts).not.toContain('on_failure')
        wrapper.unmount()
    })

    it('config 透传：by 的 options 含 7 项且 default=uia_name；timeout default=3000', () => {
        const wrapper = mountPanel()
        const byStub = wrapper.findAll('.pr-stub').find(w => w.text().startsWith('查找方式'))
        const byConfig = JSON.parse(byStub.text().split('|')[2])
        expect(byConfig.options).toHaveLength(7)
        expect(byConfig.default).toBe('uia_name')
        expect(byConfig.options[0].value).toBe('uia_name')

        const timeoutStub = wrapper.findAll('.pr-stub').find(w => w.text().startsWith('查找超时时长'))
        expect(JSON.parse(timeoutStub.text().split('|')[2]).default).toBe(3000)
        wrapper.unmount()
    })

    it('stub 更新参数 → handleParamUpdate 写回 node.params 并 emit save', async () => {
        const node = makeNode()
        const wrapper = mountPanel(node)
        const targetStub = wrapper.findAllComponents(ParamRendererStub)
            .find(w => w.text().startsWith('控件标识'))
        targetStub.vm.$emit('update', '关闭按钮')

        expect(node.params.target).toBe('关闭按钮')
        expect(wrapper.emitted('save')).toBeTruthy()
        wrapper.unmount()
    })
})
