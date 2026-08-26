import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import FunctionContractSection from '../FunctionContractSection.vue'

function mountSection(items) {
    return mount(FunctionContractSection, {
        props: {
            title: '形参',
            prefix: '$param.',
            idField: 'parameter_id',
            items
        }
    })
}

describe('FunctionContractSection', () => {
    it('以完整深色表单结构编辑函数契约并发出稳定事件', async () => {
        const item = {
            parameter_id: 'parameter_1', name: 'count', type: 'number',
            required: false, default_value: 1, description: ''
        }
        const wrapper = mountSection([item])
        const inputs = wrapper.findAll('input')
        await inputs[0].setValue('total')
        await inputs[0].trigger('change')
        await wrapper.get('select').setValue('string')
        await wrapper.get('select').trigger('change')
        await wrapper.get('input[type="checkbox"]').setValue(true)

        expect(wrapper.emitted('rename')?.[0]?.[0]).toMatchObject({
            item, previousName: 'count', nextName: 'total'
        })
        expect(item.type).toBe('string')
        expect(item.required).toBe(true)
        expect(wrapper.emitted('change')?.length).toBeGreaterThanOrEqual(2)
    })

    it('复制按钮使用可直接粘贴的局部变量表达式', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: { writeText }
        })
        const wrapper = mountSection([{
            parameter_id: 'parameter_1', name: 'count', type: 'number', required: true
        }])
        await wrapper.get('button[aria-label="复制 $param.count"]').trigger('click')
        expect(writeText).toHaveBeenCalledWith('$param.count')
    })
})
