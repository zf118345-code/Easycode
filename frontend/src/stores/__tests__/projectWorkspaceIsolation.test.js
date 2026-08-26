import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const calls = []

vi.mock('@/api/blueprintApi', () => ({
    blueprintApi: {
        getParams: vi.fn().mockResolvedValue({}),
        getBlueprint: vi.fn(),
        getWorkflow: vi.fn(),
        getTopology: vi.fn(),
        saveBlueprint: vi.fn(async (path, data, identity) => {
            calls.push(['saveBlueprint', path, identity, data])
            return { status: 'success' }
        }),
        saveWorkflow: vi.fn(async (path, data, identity) => {
            calls.push(['saveWorkflow', path, identity, data])
            return { status: 'success' }
        }),
        saveTopology: vi.fn().mockResolvedValue({ status: 'success' })
    }
}))

vi.mock('@/api/projectWorkspaceApi', () => ({
    projectWorkspaceApi: {
        open: vi.fn(),
        close: vi.fn().mockResolvedValue({ closed: true }),
        recent: vi.fn().mockResolvedValue({ projects: [] }),
        acknowledge: vi.fn().mockResolvedValue({ acknowledged: true }),
        changes: vi.fn().mockResolvedValue({ changed: false, paths: [] })
    }
}))

vi.mock('@/stores/contextStore', () => ({
    useContextStore: () => ({ loadContext: vi.fn().mockResolvedValue({}) })
}))

vi.mock('@/stores/uiStore', () => ({
    useUiStore: () => ({ _restoreBreakpoints: vi.fn() })
}))

import { blueprintApi } from '@/api/blueprintApi'
import { projectWorkspaceApi } from '@/api/projectWorkspaceApi'
import { useProjectStore } from '@/stores/projectStore'

const identity = (name, generation) => ({
    workspace_id: `workspace_${name}`,
    generation,
    project_id: `project_${name}`,
    project_name: name,
    project_path: `D:/${name}`,
    revision: 0,
    read_only: false
})

const blueprint = (name = 'A') => ({
    schema_version: 3,
    project_id: `project_${name}`,
    revision: 0,
    project_name: name,
    variables: {}, ui_state: {}, settings: {},
    main_graph: { graph_id: 'main', nodes: [], edges: [] },
    functions: [], function_folders: [],
    page_map: { schema_version: 3, nodes: [], edges: [] }
})

describe('项目切换与延迟保存隔离', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        calls.length = 0
        setActivePinia(createPinia())
    })

    it('绕过正式切换流程改变工作区身份时，延迟保存拒绝跨项目写入', async () => {
        vi.useFakeTimers()
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 1))
        store.blueprint = blueprint('A')

        store.saveWorkflowDebounced()
        store._applyWorkspace(identity('B', 2))
        store.blueprint.main_graph.nodes.push({ node_id: 'b_local', node_type: 'log', params: {} })
        vi.advanceTimersByTime(450)
        await store.flushPendingSaves()

        expect(blueprintApi.saveWorkflow).not.toHaveBeenCalled()
        vi.useRealTimers()
    })

    it('连续编辑只在防抖结束时生成一次完整工作流快照', async () => {
        vi.useFakeTimers()
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 3))
        store.blueprint = blueprint('A')
        store.blueprint.main_graph.nodes = [{ node_id: 'node_a', node_name: 'first', node_type: 'log', params: {} }]
        const snapshotSpy = vi.spyOn(store, '_workflowSnapshot')

        store.saveWorkflowDebounced()
        store.blueprint.main_graph.nodes[0].node_name = 'second'
        store.saveWorkflowDebounced()
        store.blueprint.main_graph.nodes[0].node_name = 'final'
        store.saveWorkflowDebounced()

        expect(snapshotSpy).not.toHaveBeenCalled()
        await vi.advanceTimersByTimeAsync(450)
        await store.flushPendingSaves()
        expect(snapshotSpy).toHaveBeenCalledTimes(1)
        expect(blueprintApi.saveWorkflow.mock.calls.at(-1)[1].main_graph.nodes[0].node_name).toBe('final')
        vi.useRealTimers()
    })

    it('正式切换前先冲刷 A 的保存队列，再加载 B', async () => {
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 4))
        store.blueprint.project_name = 'A edited'
        store.saveProjectMetaDebounced()

        projectWorkspaceApi.open.mockImplementation(async () => {
            calls.push(['open', 'D:/B'])
            return { workspace: identity('B', 5), inspection: { status: 'valid' } }
        })
        blueprintApi.getBlueprint.mockResolvedValue({
            schema_version: 3, project_id: 'project_B', revision: 0,
            project_name: 'B', variables: {}, ui_state: {}, settings: {}
        })
        blueprintApi.getWorkflow.mockResolvedValue({ schema_version: 3, main_graph: blueprint('B').main_graph, functions: [], function_folders: [] })
        blueprintApi.getTopology.mockResolvedValue({ schema_version: 3, nodes: [], edges: [] })

        await store.loadProjectByPath('D:/B')

        expect(calls[0][0]).toBe('saveBlueprint')
        expect(calls[0][1]).toBe('D:/A')
        expect(calls[0][2]).toEqual({ workspaceId: 'workspace_A', generation: 4 })
        expect(calls[1]).toEqual(['open', 'D:/B'])
        expect(store.currentProjectPath).toBe('D:/B')
    })

    it('慢保存严格串行，旧快照不会在新快照之后落盘', async () => {
        vi.useFakeTimers()
        let releaseFirst
        blueprintApi.saveWorkflow
            .mockImplementationOnce(() => new Promise(resolve => { releaseFirst = resolve }))
            .mockResolvedValueOnce({ status: 'success' })

        const store = useProjectStore()
        store._applyWorkspace(identity('A', 8))
        store.blueprint = blueprint('A')
        store.blueprint.main_graph.nodes = [{ node_id: 'node_a', node_name: 'first', node_type: 'log', params: {} }]
        store.saveWorkflowDebounced()
        await vi.advanceTimersByTimeAsync(450)
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(1)
        expect(store.saveState).toBe('saving')

        store.blueprint.main_graph.nodes[0].node_name = 'second'
        store.saveWorkflowDebounced()
        await vi.advanceTimersByTimeAsync(450)
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(1)

        releaseFirst({ status: 'success' })
        await store.flushPendingSaves()
        expect(blueprintApi.saveWorkflow).toHaveBeenCalledTimes(2)
        expect(blueprintApi.saveWorkflow.mock.calls[1][1].main_graph.nodes[0].node_name).toBe('second')
        expect(store.saveState).toBe('saved')
        vi.useRealTimers()
    })

    it('元数据、工作流与完整保存共享一条写入队列，不会跨文档并发覆盖', async () => {
        vi.useFakeTimers()
        let releaseMeta
        blueprintApi.saveBlueprint
            .mockImplementationOnce(() => new Promise(resolve => { releaseMeta = resolve }))
            .mockResolvedValueOnce({ status: 'success' })

        const store = useProjectStore()
        store._applyWorkspace(identity('A', 12))
        store.blueprint = blueprint('A')
        store.saveProjectMetaDebounced()
        await vi.advanceTimersByTimeAsync(450)
        expect(blueprintApi.saveBlueprint).toHaveBeenCalledTimes(1)

        store.blueprint.main_graph.nodes.push({ node_id: 'after_meta', node_name: 'newer', node_type: 'log', params: {} })
        const fullSave = store.saveBlueprintImmediately()
        await Promise.resolve()
        expect(blueprintApi.saveBlueprint).toHaveBeenCalledTimes(1)

        releaseMeta({ status: 'success' })
        await fullSave
        expect(blueprintApi.saveBlueprint).toHaveBeenCalledTimes(2)
        expect(blueprintApi.saveBlueprint.mock.calls[1][1].main_graph.nodes[0].node_id).toBe('after_meta')
        vi.useRealTimers()
    })

    it('立即重试成功后清除同一文档域的旧保存错误', async () => {
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 9))
        store.blueprint = blueprint('A')
        store._saveErrors = { workflow: '磁盘暂时不可写' }
        store._lastSaveError = new Error('磁盘暂时不可写')

        await store.saveWorkflowImmediately()

        expect(store.saveState).toBe('saved')
        expect(store._lastSaveError).toBeNull()
        expect(store._lastSavedAt).toBeGreaterThan(0)
    })

    it('全量保存成功会恢复所有文档域的错误状态', async () => {
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 10))
        store.blueprint = blueprint('A')
        store._saveErrors = { meta: 'meta failed', topology: 'topology failed' }
        store._lastSaveError = new Error('meta failed')

        await store.saveBlueprintImmediately()

        expect(store._saveErrors).toEqual({})
        expect(store.saveState).toBe('saved')
    })

    it('立即保存再次失败时保留可重试错误并恢复计数', async () => {
        blueprintApi.saveWorkflow.mockRejectedValueOnce(new Error('磁盘空间不足'))
        const store = useProjectStore()
        store._applyWorkspace(identity('A', 11))
        store.blueprint = blueprint('A')

        await expect(store.saveWorkflowImmediately()).rejects.toThrow('磁盘空间不足')

        expect(store.saveState).toBe('error')
        expect(store._savePendingCount).toBe(0)
        expect(store._lastSaveError?.message).toBe('磁盘空间不足')
    })
})
