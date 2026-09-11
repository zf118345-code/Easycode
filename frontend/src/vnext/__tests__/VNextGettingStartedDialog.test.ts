import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VNextGettingStartedDialog from '../components/VNextGettingStartedDialog.vue'

describe('VNextGettingStartedDialog', () => {
    it('说明完整主流程并只通过真实工作区命令跳转', async () => {
        const wrapper = mount(VNextGettingStartedDialog)
        expect(wrapper.text()).toContain('连接运行目标')
        expect(wrapper.text()).toContain('采集可复用素材')
        expect(wrapper.text()).toContain('按顺序搭建流程')
        expect(wrapper.text()).toContain('交付与排查')

        await wrapper.get('button').trigger('keydown', { key: 'Tab' })
        const targets = wrapper.findAll('button').find(button => button.text().includes('打开运行目标'))
        await targets!.trigger('click')
        expect(wrapper.emitted('command')?.[0]).toEqual(['view.targets'])
    })

    it('支持 Escape 关闭', async () => {
        const wrapper = mount(VNextGettingStartedDialog)
        await wrapper.get('.help-dialog').trigger('keydown', { key: 'Escape' })
        expect(wrapper.emitted('close')).toHaveLength(1)
    })
})
