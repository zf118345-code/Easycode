import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VNextShortcutSettingsDialog from '../VNextShortcutSettingsDialog.vue'
import shortcutDialogSource from '../VNextShortcutSettingsDialog.vue?raw'

const shortcuts = {
    'edit.undo': 'Ctrl+Z',
    'edit.redo': 'Ctrl+Y',
    'edit.find': 'Ctrl+F',
    'edit.duplicate_statement': 'Ctrl+D',
    'edit.delete_statement': 'Delete',
    'edit.extract_function': 'Ctrl+Shift+E',
    'run.start_or_resume': 'F5',
    'run.step': 'F10',
    'run.toggle_breakpoint': 'F9',
    'view.toggle_problems': 'Ctrl+Shift+M',
    'view.toggle_log': 'Ctrl+J',
}

describe('VNextShortcutSettingsDialog', () => {
    it('keeps search, recorder, and row action on the shared 32px control line', () => {
        const wrapper = mount(VNextShortcutSettingsDialog, { props: { shortcuts, defaults: shortcuts } })
        expect(shortcutDialogSource).toContain('<VNextTextField v-model="query"')
        expect(shortcutDialogSource).toContain('.shortcut-tools > :first-child { min-width: 0; flex: 1; }')
        expect(shortcutDialogSource).toContain('.shortcut-recorder { height: var(--app-control-default)')
        expect(shortcutDialogSource).toContain('.shortcut-clear { min-height: var(--app-control-default)')
        expect(wrapper.get('.shortcut-row').findAll('button')).toHaveLength(2)
        wrapper.unmount()
    })

    it('records a shortcut and emits the complete settings', async () => {
        const wrapper = mount(VNextShortcutSettingsDialog, { props: { shortcuts, defaults: shortcuts } })
        const recorders = wrapper.findAll('.shortcut-recorder')
        await recorders[0].trigger('click')
        await recorders[0].trigger('keydown', { key: 'U', ctrlKey: true, altKey: true })
        await wrapper.get('.vnext-button.is-primary').trigger('click')
        expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({ 'edit.undo': 'Ctrl+Alt+U' })
    })

    it('shows a conflict and blocks save when two commands share a shortcut', async () => {
        const wrapper = mount(VNextShortcutSettingsDialog, { props: { shortcuts, defaults: shortcuts } })
        const recorders = wrapper.findAll('.shortcut-recorder')
        await recorders[1].trigger('click')
        await recorders[1].trigger('keydown', { key: 'z', ctrlKey: true })
        expect(wrapper.get('[role="alert"]').text()).toContain('同时分配给了两个命令')
        expect(wrapper.get('.vnext-button.is-primary').attributes('disabled')).toBeDefined()
    })
})
