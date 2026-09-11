import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import VNextOverflowTabs from '../components/ui/VNextOverflowTabs.vue'

const items = [
    { id: 'one', label: '任务设置' },
    { id: 'two', label: '目标与资源' },
    { id: 'three', label: '高级运行参数' },
    { id: 'four', label: '问题诊断' },
]

describe('VNextOverflowTabs', () => {
    it('宽度不足时保留当前页并把其余页面放入更多菜单', async () => {
        const wrapper = mount(VNextOverflowTabs, { props: { items, modelValue: 'three' } })
        Object.defineProperty(wrapper.element, 'clientWidth', { configurable: true, value: 230 })
        await wrapper.setProps({ modelValue: 'one' })
        await wrapper.setProps({ modelValue: 'three' })
        await flushPromises()

        expect(wrapper.find('details').exists()).toBe(true)
        expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('高级运行参数')
        await wrapper.get('summary').trigger('click')
        const hidden = wrapper.findAll('[role="menuitemradio"]')
        expect(hidden.length).toBeGreaterThan(0)
        await hidden[0].trigger('click')
        expect(wrapper.emitted('update:modelValue')).toBeTruthy()
        wrapper.unmount()
    })

    it('方向键按照完整页面顺序切换', async () => {
        const wrapper = mount(VNextOverflowTabs, { props: { items, modelValue: 'one' } })
        await flushPromises()
        await wrapper.get('[role="tab"]').trigger('keydown', { key: 'ArrowRight' })
        expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['two'])
        wrapper.unmount()
    })
})
