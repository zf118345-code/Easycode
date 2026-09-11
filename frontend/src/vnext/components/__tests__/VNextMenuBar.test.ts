import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VNextMenuBar from '../VNextMenuBar.vue'

describe('VNextMenuBar', () => {
    it('shows real commands with their shortcut and emits a selected command', async () => {
        const wrapper = mount(VNextMenuBar, {
            props: {
                shortcuts: { 'edit.find': 'Ctrl+F' },
                enabled: () => true,
                disabledReason: () => '',
            },
        })
        await wrapper.findAll('.app-menu-trigger')[1].trigger('click')
        expect(wrapper.text()).toContain('Ctrl+F')
        const find = wrapper.findAll('[role="menuitem"]').find(item => item.text().includes('查找当前函数'))
        await find?.trigger('click')
        expect(wrapper.emitted('command')).toEqual([['edit.find']])
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    })

    it('keeps unavailable commands disabled with an explanatory title', async () => {
        const wrapper = mount(VNextMenuBar, {
            props: {
                shortcuts: {},
                enabled: commandId => commandId !== 'run.step',
                disabledReason: () => '请先暂停运行',
            },
        })
        await wrapper.findAll('.app-menu-trigger')[3].trigger('click')
        const step = wrapper.findAll('[role="menuitem"]').find(item => item.text().includes('单步执行'))
        expect(step?.attributes('disabled')).toBeDefined()
        expect(step?.attributes('title')).toBe('请先暂停运行')
    })

    it('opens and traverses enabled commands with standard menu keys', async () => {
        const wrapper = mount(VNextMenuBar, {
            attachTo: document.body,
            props: {
                shortcuts: {},
                enabled: commandId => commandId !== 'edit.undo',
                disabledReason: () => '不可用',
            },
        })
        const editTrigger = wrapper.findAll<HTMLButtonElement>('.app-menu-trigger')[1]
        editTrigger.element.focus()
        await editTrigger.trigger('keydown', { key: 'ArrowDown' })
        await wrapper.vm.$nextTick()
        const items = wrapper.findAll<HTMLButtonElement>('[role="menuitem"]')
        expect(document.activeElement).toBe(items.find(item => !item.element.disabled)?.element)

        await wrapper.find(':focus').trigger('keydown', { key: 'End' })
        expect(document.activeElement).toBe(items.filter(item => !item.element.disabled).at(-1)?.element)

        await wrapper.find(':focus').trigger('keydown', { key: 'ArrowRight' })
        await wrapper.vm.$nextTick()
        expect(wrapper.findAll('.app-menu-trigger')[2].attributes('aria-expanded')).toBe('true')
        expect((document.activeElement as HTMLElement)?.getAttribute('role')).toBe('menuitem')

        await wrapper.find(':focus').trigger('keydown', { key: 'Escape' })
        await wrapper.vm.$nextTick()
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        expect(document.activeElement).toBe(wrapper.findAll('.app-menu-trigger')[2].element)
        wrapper.unmount()
    })

    it('cycles top-level menus horizontally without opening a closed menu', async () => {
        const wrapper = mount(VNextMenuBar, {
            attachTo: document.body,
            props: { shortcuts: {}, enabled: () => true, disabledReason: () => '' },
        })
        const triggers = wrapper.findAll<HTMLButtonElement>('.app-menu-trigger')
        triggers[0].element.focus()
        await triggers[0].trigger('keydown', { key: 'ArrowLeft' })
        expect(document.activeElement).toBe(triggers.at(-1)?.element)
        expect(wrapper.find('[role="menu"]').exists()).toBe(false)
        wrapper.unmount()
    })

    it('keeps every command available through the compact menu and restores focus on Escape', async () => {
        const wrapper = mount(VNextMenuBar, {
            attachTo: document.body,
            props: {
                shortcuts: { 'run.start_or_resume': 'F5' },
                enabled: () => true,
                disabledReason: () => '',
            },
        })
        const trigger = wrapper.find<HTMLButtonElement>('.app-menu-compact-trigger')
        trigger.element.focus()
        await trigger.trigger('keydown', { key: 'ArrowDown' })
        await wrapper.vm.$nextTick()

        expect(wrapper.find('#app-menu-compact').exists()).toBe(true)
        expect(wrapper.text()).toContain('项目')
        expect(wrapper.text()).toContain('编辑')
        expect(wrapper.text()).toContain('运行')
        expect(wrapper.text()).toContain('F5')
        expect((document.activeElement as HTMLElement)?.getAttribute('role')).toBe('menuitem')

        await wrapper.find(':focus').trigger('keydown', { key: 'Escape' })
        await wrapper.vm.$nextTick()
        expect(wrapper.find('#app-menu-compact').exists()).toBe(false)
        expect(document.activeElement).toBe(trigger.element)
        wrapper.unmount()
    })
})
