// frontend/src/components/panels/__tests__/VariableInspectorPanel.test.js
// 变量监控面板：未运行时展示项目全局变量；暂停时展示运行时快照 + 上一节点值 + 变化高亮
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VariableInspectorPanel from '../VariableInspectorPanel.vue'
import { useProjectStore, useExecutionStore, useMainStore } from '@/stores'

function mountPanel() {
    return mount(VariableInspectorPanel, {
        attachTo: document.body,
        global: { stubs: { 'el-input': true } }
    })
}

describe('VariableInspectorPanel 变量监控', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        setActivePinia(createPinia())
        const project = useProjectStore()
        project.blueprint = { variables: { coin: 5, name: 'alice' } }
    })

    it('未运行时展示项目全局变量（当前值=初始值，上一节点值=—）', () => {
        const wrapper = mountPanel()
        const text = wrapper.text()
        expect(text).toContain('2 个变量')
        expect(text).toContain('coin')
        expect(text).toContain('5')
        expect(text).toContain('alice')
    })

    it('暂停时展示运行时快照 + 上一节点值 + 变化行高亮', () => {
        const exec = useExecutionStore()
        exec.executionState = 'paused'
        exec.executionCurrentVariables = { coin: 9 }
        exec.executionPrevVariables = { coin: 5 }

        const wrapper = mountPanel()
        const text = wrapper.text()
        expect(text).toContain('9')    // 运行时当前值优先
        expect(text).toContain('5')    // 上一节点值
        expect(wrapper.find('.var-row.is-changed').exists()).toBe(true)
        // 未变化的全局变量仍在列表中
        expect(text).toContain('alice')
    })

    it('运行中保留实时快照（prev 无对比）', () => {
        const exec = useExecutionStore()
        exec.executionState = 'running'
        exec.executionCurrentVariables = { coin: 7 }
        exec.executionPrevVariables = {}

        const wrapper = mountPanel()
        expect(wrapper.text()).toContain('7')
    })

    it('mainStore 代理正确转发变量快照（回归：代理缺失导致面板永远为空）', () => {
        const exec = useExecutionStore()
        exec.executionCurrentVariables = { a: 1 }
        exec.executionPrevVariables = { a: 0 }
        const main = useMainStore()
        expect(main.executionCurrentVariables).toEqual({ a: 1 })
        expect(main.executionPrevVariables).toEqual({ a: 0 })
    })
})
