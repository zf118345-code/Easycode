import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProjectVariableSnapshotDto } from '../program/serverTypes'

const apiMocks = vi.hoisted(() => ({
    getProjectVariables: vi.fn(), createProjectVariable: vi.fn(), updateProjectVariable: vi.fn(),
    deleteProjectVariable: vi.fn(), getProjectVariableReferences: vi.fn(),
}))
vi.mock('../program/api', async () => {
    const actual = await vi.importActual<typeof import('../program/api')>('../program/api')
    return { ...actual, programApi: apiMocks }
})

import VNextProjectVariableWorkspace from '../components/VNextProjectVariableWorkspace.vue'
import { useProjectVariableStore } from '../program/projectVariableStore'

const workspace = {
    workspace_id: 'workspace-ui', generation: 2, project_id: 'project-ui', project_name: 'UI',
    project_path: 'D:/Projects/UI', read_only: false,
}
function snapshot(revision = 'revision-a', displayName = '副本列表'): ProjectVariableSnapshotDto {
    return {
        schema_version: 1, revision, selected_variable_id: 'variable-list',
        variables: [{
            variable_id: 'variable-list', display_name: displayName, value_type: 'list<string>',
            default_value: { value_id: 'value-list', kind: 'list', item_type: 'string', items: [] },
            description: '', constraints: {},
        }],
    }
}

describe('VNextProjectVariableWorkspace', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        Object.values(apiMocks).forEach((mock) => mock.mockReset())
        apiMocks.getProjectVariables.mockResolvedValue(snapshot())
    })

    it('edits the selected variable through the revisioned store and keeps list defaults in the shared Control', async () => {
        const store = useProjectVariableStore()
        await store.connect(workspace)
        apiMocks.updateProjectVariable.mockResolvedValueOnce(snapshot('revision-b', '每日副本'))
        const wrapper = mount(VNextProjectVariableWorkspace)

        expect(wrapper.text()).toContain('每次运行的初始值')
        expect(wrapper.find('.structured-summary-control').exists()).toBe(true)
        expect(wrapper.find('.structured-summary-control [data-control-surface] button').exists()).toBe(false)
        expect(wrapper.find('.structured-summary-control > .app-field-action').exists()).toBe(true)
        expect(wrapper.findAll('.variable-inspector .field.app-form-row').length).toBeGreaterThanOrEqual(4)
        expect(wrapper.findAll('.constraint-field.app-form-row')).toHaveLength(2)
        expect(wrapper.get('.variable-inspector .field.app-form-row input').classes()).toContain('app-form-control')
        expect(wrapper.get('.advanced-variable-settings').attributes('open')).toBeUndefined()
        expect(wrapper.get('.advanced-variable-settings summary').text()).toContain('可选')
        expect(wrapper.find('textarea[placeholder="只在需要解释用途时填写"]').exists()).toBe(true)
        const nameInput = wrapper.findAll('.form-section .field input')[0]
        await nameInput.setValue('每日副本')
        await nameInput.trigger('change')
        await flushPromises()

        expect(apiMocks.updateProjectVariable).toHaveBeenCalledWith(
            workspace, 'variable-list', 'revision-a', { display_name: '每日副本' },
        )
        expect(store.revision).toBe('revision-b')
    })

    it('uses the same compact rows inside the create transaction without adding an intermediate form', async () => {
        const store = useProjectVariableStore()
        await store.connect(workspace)
        const wrapper = mount(VNextProjectVariableWorkspace)

        await wrapper.get('.variable-sidebar header button').trigger('click')
        const dialog = wrapper.get('.variable-dialog[role="dialog"]')
        expect(dialog.findAll('.field.app-form-row')).toHaveLength(2)
        expect(dialog.findAll('.field.app-form-row .app-form-control')).toHaveLength(2)
        expect(dialog.find('.program-parameter').exists()).toBe(true)
    })

    it('lists blocking references and lets the user jump to the stable statement', async () => {
        const store = useProjectVariableStore()
        await store.connect(workspace)
        apiMocks.getProjectVariableReferences.mockResolvedValueOnce([{
            kind: 'program_value', function_id: 'func-main', function_name: '主程序', statement_id: 'stmt-loop', value_id: 'value-source',
        }])
        const wrapper = mount(VNextProjectVariableWorkspace)

        await wrapper.get('.danger-button').trigger('click')
        await flushPromises()
        expect(wrapper.text()).toContain('项目变量仍在使用')
        await wrapper.get('.reference-list button').trigger('click')
        expect(wrapper.emitted('openReference')?.[0]?.[0]).toMatchObject({ function_id: 'func-main', statement_id: 'stmt-loop' })
        expect(apiMocks.deleteProjectVariable).not.toHaveBeenCalled()
    })
})
