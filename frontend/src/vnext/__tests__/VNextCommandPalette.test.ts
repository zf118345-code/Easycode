import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VNextCommandPalette from '../components/VNextCommandPalette.vue'

describe('VNextCommandPalette', () => {
    beforeEach(() => {
        vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => window.setTimeout(callback, 0))
        HTMLElement.prototype.scrollIntoView = vi.fn()
    })
    afterEach(() => { vi.unstubAllGlobals() })

    it('搜索可用命令并用 Enter 执行', async () => {
        const wrapper = mount(VNextCommandPalette, {
            attachTo: document.body,
            props: { shortcuts: { 'help.command_palette': 'Ctrl+Shift+P' }, enabled: () => true, disabledReason: () => '' },
        })
        const input = wrapper.get('input[aria-label="搜索命令"]')
        expect(document.activeElement).toBe(input.element)
        await input.setValue('项目变量')
        expect(wrapper.get('.command-results').text()).toContain('项目变量')
        await input.trigger('keydown', { key: 'Enter' })
        expect(wrapper.emitted('command')?.[0]).toEqual(['view.variables'])
        wrapper.unmount()
    })

    it('保留禁用命令及原因但不会执行，并允许 Escape 退出', async () => {
        const wrapper = mount(VNextCommandPalette, {
            props: { shortcuts: {}, enabled: id => id !== 'run.stop', disabledReason: () => '当前没有运行任务' },
        })
        await wrapper.get('input[aria-label="搜索命令"]').setValue('停止')
        const disabled = wrapper.get('.command-results button')
        expect(disabled.attributes('disabled')).toBeDefined()
        expect(disabled.text()).toContain('当前没有运行任务')
        await disabled.trigger('click')
        expect(wrapper.emitted('command')).toBeUndefined()
        await wrapper.get('.command-palette').trigger('keydown', { key: 'Escape' })
        expect(wrapper.emitted('cancel')).toHaveLength(1)
    })
})
