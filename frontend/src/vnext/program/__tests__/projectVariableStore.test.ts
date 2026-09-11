import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProgramApiError } from '../api'
import type { ProjectVariableSnapshotDto } from '../serverTypes'

const apiMocks = vi.hoisted(() => ({
    getProjectVariables: vi.fn(),
    createProjectVariable: vi.fn(),
    updateProjectVariable: vi.fn(),
    deleteProjectVariable: vi.fn(),
    getProjectVariableReferences: vi.fn(),
}))

vi.mock('../api', async () => {
    const actual = await vi.importActual<typeof import('../api')>('../api')
    return { ...actual, programApi: apiMocks }
})

import { useProjectVariableStore } from '../projectVariableStore'

const workspace = {
    workspace_id: 'workspace-variables', generation: 4, project_id: 'project-variables',
    project_name: 'Variables', project_path: 'D:/Projects/Variables', read_only: false,
}

function snapshot(revision = 'revision-a', displayName = '启用副本'): ProjectVariableSnapshotDto {
    return {
        schema_version: 1,
        revision,
        selected_variable_id: 'variable-dungeons',
        variables: [{
            variable_id: 'variable-dungeons',
            display_name: displayName,
            value_type: 'list<string>',
            default_value: {
                value_id: 'value-dungeons', kind: 'list', item_type: 'string',
                items: [{ value_id: 'value-dungeon-1', kind: 'string', value: '经验副本' }],
            },
            description: '本次运行要完成的副本',
            constraints: { min_items: 1, unique_items: true },
        }],
    }
}

describe('format-6 project variable store', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        Object.values(apiMocks).forEach((mock) => mock.mockReset())
        apiMocks.getProjectVariables.mockResolvedValue(snapshot())
    })

    it('projects typed defaults and exposes only the user-facing project variable catalog', async () => {
        const store = useProjectVariableStore()
        await store.connect(workspace)

        expect(store.selectedVariable).toMatchObject({
            variable_id: 'variable-dungeons', display_name: '启用副本',
            default_value: { kind: 'list', value_id: 'value-dungeons' },
        })
        expect(store.availableValues).toEqual([{
            source: 'project', id: 'variable-dungeons', display_name: '启用副本', value_type: 'list<string>',
        }])
    })

    it('clears the previous project catalog before a new workspace snapshot arrives', async () => {
        const store = useProjectVariableStore()
        await store.connect(workspace)

        let resolveNext!: (value: ProjectVariableSnapshotDto) => void
        apiMocks.getProjectVariables.mockReturnValueOnce(new Promise((resolve) => { resolveNext = resolve }))
        const nextWorkspace = { ...workspace, workspace_id: 'workspace-next', generation: 1 }
        const pending = store.connect(nextWorkspace)

        expect(store.status).toBe('loading')
        expect(store.variables).toEqual([])
        expect(store.availableValues).toEqual([])
        expect(store.selectedVariableId).toBe('')

        resolveNext({ ...snapshot('revision-next', '下一项目变量'), selected_variable_id: 'variable-dungeons' })
        await pending
        expect(store.availableValues[0]?.display_name).toBe('下一项目变量')
    })

    it('serializes a typed default and advances only from the returned revision', async () => {
        apiMocks.updateProjectVariable.mockResolvedValue(snapshot('revision-b', '要打的副本'))
        const store = useProjectVariableStore()
        await store.connect(workspace)

        await store.updateVariable('variable-dungeons', {
            display_name: ' 要打的副本 ',
            default_value: {
                value_id: 'value-dungeons', kind: 'list', value_type: 'list<string>', item_type: 'string',
                items: [{ value_id: 'value-dungeon-1', kind: 'literal', value_type: 'string', value: '经验副本' }],
            },
        })

        expect(apiMocks.updateProjectVariable).toHaveBeenCalledWith(
            workspace,
            'variable-dungeons',
            'revision-a',
            {
                display_name: '要打的副本',
                default_value: {
                    value_id: 'value-dungeons', kind: 'list', item_type: 'string',
                    items: [{ value_id: 'value-dungeon-1', kind: 'string', value: '经验副本' }],
                },
            },
        )
        expect(store.revision).toBe('revision-b')
    })

    it('does not retry a variable revision conflict and requires explicit reload', async () => {
        apiMocks.updateProjectVariable.mockRejectedValue(new ProgramApiError('项目变量已变化', {
            status: 409,
            code: 'project_variable_revision_conflict',
            diagnostics: [{ expected_revision: 'revision-a', actual_revision: 'revision-c' }],
        }))
        const store = useProjectVariableStore()
        await store.connect(workspace)

        await expect(store.updateVariable('variable-dungeons', { description: '新的说明' })).rejects.toThrow('项目变量已变化')
        expect(apiMocks.updateProjectVariable).toHaveBeenCalledTimes(1)
        expect(store.status).toBe('conflict')
        expect(store.conflict).toMatchObject({ expected_revision: 'revision-a', actual_revision: 'revision-c' })

        apiMocks.getProjectVariables.mockResolvedValueOnce(snapshot('revision-c'))
        await store.reload()
        expect(store.status).toBe('ready')
        expect(store.revision).toBe('revision-c')
    })

    it('keeps referenced variables and exposes stable locations instead of force deleting', async () => {
        apiMocks.deleteProjectVariable.mockRejectedValue(new ProgramApiError('项目变量仍被引用', {
            status: 409,
            code: 'project_variable_referenced',
            diagnostics: [{
                kind: 'program_value', function_id: 'func-main', function_name: '主程序',
                statement_id: 'stmt-if', value_id: 'value-condition', field: 'condition',
            }],
        }))
        const store = useProjectVariableStore()
        await store.connect(workspace)

        await expect(store.deleteVariable('variable-dungeons')).rejects.toThrow('项目变量仍被引用')
        expect(store.variables).toHaveLength(1)
        expect(store.blockedReferences).toEqual([{
            kind: 'program_value', function_id: 'func-main', function_name: '主程序',
            statement_id: 'stmt-if', value_id: 'value-condition', field: 'condition',
        }])
    })
})
