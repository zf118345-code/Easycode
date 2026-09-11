import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VNextAppContextMenu from '../VNextAppContextMenu.vue'

describe('VNextAppContextMenu', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
    })

    it('suppresses the browser menu on blank surfaces without inventing actions', async () => {
        const wrapper = mount(VNextAppContextMenu, { attachTo: document.body })
        const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true })
        document.body.dispatchEvent(event)

        expect(event.defaultPrevented).toBe(true)
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('offers text editing actions for editable controls', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText, readText: vi.fn().mockResolvedValue('新值') } })
        const input = document.createElement('input')
        input.value = '原始文本'
        document.body.appendChild(input)
        input.setSelectionRange(0, 2)
        const wrapper = mount(VNextAppContextMenu, { attachTo: document.body })

        input.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 20, clientY: 20 }))
        await wrapper.vm.$nextTick()
        expect(wrapper.get('[role="menu"]').text()).toContain('复制')
        await wrapper.get('button[role="menuitem"]').trigger('click')
        expect(writeText).toHaveBeenCalledWith('原始')

        wrapper.unmount()
        input.remove()
    })
})
