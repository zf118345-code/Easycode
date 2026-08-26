import { defineStore } from 'pinia'
import debounce from 'lodash-es/debounce'
import { blueprintApi } from '@/api/blueprintApi'
import { projectWorkspaceApi } from '@/api/projectWorkspaceApi'
import { setWorkspaceIdentity } from '@/api/workspaceIdentity'
import { logger } from '@/utils/logger'
import { reconcileGraphIntegrity, reconcileStablePortRoutes } from '@/utils/workflowEdgeModel'
import {
    collectFunctionReferences,
    createMainGraph,
    createPageMap,
    getFunction,
    getGraph,
    MAIN_GRAPH_ID,
} from '@/utils/flowModel'

export const DEFAULT_UI_STATE = {
    leftPanelExpanded: true,
    leftPanelWidth: 260,
    rightPanelExpanded: true,
    rightPanelWidth: 320,
    bottomPanelExpanded: false,
    bottomPanelHeight: 200,
    minimapExpanded: true
}

const PROJECT_SCHEMA_VERSION = 3
const saveQueues = new WeakMap()
const saveCoordinators = new WeakMap()

function clone(value) {
    return JSON.parse(JSON.stringify(value))
}

function enqueueProjectWrite(store, writer) {
    const coordinator = saveCoordinators.get(store) || { tail: Promise.resolve() }
    saveCoordinators.set(store, coordinator)
    const operation = coordinator.tail.catch(() => undefined).then(writer)
    // Keep the shared tail fulfilled so one failed document domain does not
    // permanently block later retries, while the caller still receives the
    // original rejection and updates the corresponding save error state.
    coordinator.tail = operation.catch(() => undefined)
    return operation
}

function createQueue(store, queueName, runner) {
    let inflight = Promise.resolve()
    let scheduledVersion = 0
    let pending = false

    const setPending = value => {
        if (pending === value) return
        pending = value
        store._savePendingCount = Math.max(0, Number(store._savePendingCount || 0) + (value ? 1 : -1))
    }

    const setQueueError = error => {
        const errors = { ...(store._saveErrors || {}) }
        if (error) errors[queueName] = error?.message || String(error)
        else delete errors[queueName]
        store._saveErrors = errors
        const first = Object.values(errors)[0]
        store._lastSaveError = first ? new Error(first) : null
    }

    const queued = debounce(({ snapshotFactory, version }) => {
        // Chain every write. A slow previous request must never finish after a
        // newer snapshot and overwrite it on disk.
        inflight = inflight.catch(() => undefined).then(async () => {
            // Snapshot creation is deliberately inside the debounced write.
            // Large graphs must not be reconciled, cloned and stringified once
            // per keystroke when only the final state will be persisted.
            const snapshot = snapshotFactory()
            if (!snapshot) return
            await enqueueProjectWrite(store, () => runner(snapshot))
            setQueueError(null)
            store._lastSavedAt = Date.now()
        }).catch((error) => {
            setQueueError(error)
            throw error
        }).finally(() => {
            if (version === scheduledVersion) setPending(false)
        })
        inflight.catch((error) => logger.error('Store', '自动保存失败', error))
        return inflight
    }, 400)
    return {
        schedule(snapshotFactory) {
            if (typeof snapshotFactory !== 'function') return
            setPending(true)
            scheduledVersion += 1
            queued({ snapshotFactory, version: scheduledVersion })
        },
        async flush() {
            const flushed = queued.flush()
            if (flushed) await flushed
            await inflight
        },
        cancel() {
            queued.cancel()
            scheduledVersion += 1
            setPending(false)
        },
        isPending() { return pending }
    }
}

function queuesFor(store) {
    if (!saveQueues.has(store)) {
        saveQueues.set(store, {
            meta: createQueue(store, 'meta', snapshot => blueprintApi.saveBlueprint(
                snapshot.path, snapshot.data, snapshot.identity
            )),
            workflow: createQueue(store, 'workflow', snapshot => blueprintApi.saveWorkflow(
                snapshot.path, snapshot.data, snapshot.identity
            )),
            topology: createQueue(store, 'topology', snapshot => blueprintApi.saveTopology(
                snapshot.path, snapshot.data, snapshot.identity
            )),
            blueprint: createQueue(store, 'blueprint', snapshot => blueprintApi.saveBlueprint(
                snapshot.path, snapshot.data, snapshot.identity
            ))
        })
    }
    return saveQueues.get(store)
}

function emptyBlueprint() {
    return {
        schema_version: PROJECT_SCHEMA_VERSION,
        project_id: '',
        revision: 0,
        project_name: '',
        main_graph: createMainGraph(),
        functions: [],
        function_folders: [],
        variables: {},
        ui_state: { ...DEFAULT_UI_STATE },
        page_map: createPageMap(),
        settings: {}
    }
}

export const useProjectStore = defineStore('project', {
    state: () => ({
        currentProjectPath: null,
        currentProjectName: '',
        currentProjectId: '',
        workspaceId: '',
        workspaceGeneration: 0,
        readOnly: false,
        workspaceBusy: false,
        blueprint: emptyBlueprint(),
        paramsDefinitions: {},
        currentTaskId: MAIN_GRAPH_ID,
        recentProjects: [],
        taskNodesVersion: 0,
        assetPreviewVersion: 0,
        _lastSaveError: null,
        _saveErrors: {},
        _savePendingCount: 0,
        _lastSavedAt: 0
    }),

    getters: {
        tasks: state => [
            { task_id: MAIN_GRAPH_ID, task_name: '主流程', role: 'main', ...(state.blueprint.main_graph || createMainGraph()) },
            ...(state.blueprint.functions || []).map(item => ({ task_id: item.function_id, task_name: item.name, role: 'function', ...item.graph }))
        ],
        mainFlow: state => ({ task_id: MAIN_GRAPH_ID, task_name: '主流程', role: 'main', ...(state.blueprint.main_graph || createMainGraph()) }),
        functions: state => state.blueprint.functions || [],
        currentFunction: state => getFunction(state.blueprint.functions, state.currentTaskId),
        currentTaskData: state => getGraph(state.blueprint, state.currentTaskId),
        currentTask: state => getGraph(state.blueprint, state.currentTaskId),
        nodes: state => getGraph(state.blueprint, state.currentTaskId)?.nodes || [],
        params: state => state.paramsDefinitions,
        uiState: state => ({ ...DEFAULT_UI_STATE, ...(state.blueprint?.ui_state || {}) }),
        workflowData: state => ({
            main_graph: state.blueprint.main_graph || createMainGraph(),
            functions: state.blueprint.functions || [],
            function_folders: state.blueprint.function_folders || []
        }),
        topologyData: state => state.blueprint.page_map || createPageMap(),
        workspaceIdentity: state => state.workspaceId ? ({
            workspaceId: state.workspaceId,
            generation: state.workspaceGeneration
        }) : null,
        saveState: state => Object.keys(state._saveErrors || {}).length
            ? 'error'
            : (state._savePendingCount > 0 ? 'saving' : 'saved')
    },

    actions: {
        async loadParams() {
            try {
                this.paramsDefinitions = await blueprintApi.getParams()
            } catch (error) {
                logger.error('Store', '加载节点参数定义失败', error)
            }
        },

        async loadRecentProjects() {
            const result = await projectWorkspaceApi.recent()
            this.recentProjects = result?.projects || []
            return this.recentProjects
        },

        async inspectProject(path) { return await projectWorkspaceApi.inspect(path) },

        async chooseProjectFolder() {
            const result = await projectWorkspaceApi.chooseFolder()
            return result?.path || ''
        },

        _sessionSnapshot() {
            if (!this.workspaceId || !this.currentProjectPath) return null
            return {
                path: this.currentProjectPath,
                identity: { workspaceId: this.workspaceId, generation: this.workspaceGeneration }
            }
        },

        _scheduleDeferredSave(queueName, snapshotFactory) {
            if (!this.currentProjectPath || this.readOnly) return
            const scheduledSession = this._sessionSnapshot()
            if (!scheduledSession) return
            queuesFor(this)[queueName].schedule(() => {
                const currentSession = this._sessionSnapshot()
                // Public project switching flushes before changing identity. This
                // guard prevents an internal or failed switch from ever writing
                // data from project B with project A's credentials (or vice versa).
                if (
                    !currentSession
                    || currentSession.path !== scheduledSession.path
                    || currentSession.identity.workspaceId !== scheduledSession.identity.workspaceId
                    || currentSession.identity.generation !== scheduledSession.identity.generation
                ) return null
                return snapshotFactory()
            })
        },

        _applyWorkspace(workspace) {
            this.currentProjectPath = workspace.project_path
            this.currentProjectName = workspace.project_name
            this.currentProjectId = workspace.project_id
            this.workspaceId = workspace.workspace_id
            this.workspaceGeneration = Number(workspace.generation)
            this.readOnly = Boolean(workspace.read_only)
            setWorkspaceIdentity(workspace)
        },

        async loadProjectByPath(path, options = {}) {
            if (!path?.trim()) throw new Error('项目路径不能为空')
            if (this.workspaceBusy) throw new Error('项目正在切换，请稍候')
            this.workspaceBusy = true
            const previous = {
                path: this.currentProjectPath,
                name: this.currentProjectName,
                id: this.currentProjectId,
                readOnly: this.readOnly,
                blueprint: this.blueprint,
                taskId: this.currentTaskId
            }
            try {
                await this.flushPendingSaves()
                this.cancelPendingSaves()
                const result = await projectWorkspaceApi.open({
                    path: path.trim(),
                    initialize: Boolean(options.initialize),
                    confirm_nonempty: Boolean(options.confirmNonempty),
                    project_name: options.projectName || '',
                    allow_read_only: true
                })
                if (!result?.workspace) return result
                this._applyWorkspace(result.workspace)
                const data = await this._fetchProjectData(result.workspace.project_path, result.workspace.project_name)
                this._applyProjectData(data)
                await this.loadRecentProjects()
                const { useContextStore } = await import('./contextStore')
                await useContextStore().loadContext()
                return result
            } catch (error) {
                if (previous.path) {
                    try {
                        const rollback = await projectWorkspaceApi.open({ path: previous.path, allow_read_only: true })
                        if (rollback?.workspace) this._applyWorkspace(rollback.workspace)
                    } catch (rollbackError) {
                        logger.error('Store', '回滚旧项目失败', rollbackError)
                    }
                } else {
                    try { await projectWorkspaceApi.close() } catch {}
                    setWorkspaceIdentity(null)
                    this.workspaceId = ''
                    this.workspaceGeneration = 0
                }
                this.currentProjectPath = previous.path
                this.currentProjectName = previous.name
                this.currentProjectId = previous.id
                this.readOnly = previous.readOnly
                this.blueprint = previous.blueprint
                this.currentTaskId = previous.taskId
                logger.error('Store', '打开项目失败', error)
                throw error
            } finally {
                this.workspaceBusy = false
            }
        },

        async restoreLastProject() {
            const recent = await this.loadRecentProjects()
            const candidate = recent.find(item => !item.missing)
            if (!candidate) return null
            return await this.loadProjectByPath(candidate.path)
        },

        async closeProject() {
            if (this.workspaceBusy) throw new Error('项目正在切换，请稍候')
            this.workspaceBusy = true
            try {
                await this.flushPendingSaves()
                this.cancelPendingSaves()
                await projectWorkspaceApi.close()
                this._resetProjectState()
            } finally {
                this.workspaceBusy = false
            }
        },

        async removeRecentProject(path) {
            const result = await projectWorkspaceApi.removeRecent(path)
            this.recentProjects = result?.projects || []
        },

        _resetProjectState() {
            setWorkspaceIdentity(null)
            this.currentProjectPath = null
            this.currentProjectName = ''
            this.currentProjectId = ''
            this.workspaceId = ''
            this.workspaceGeneration = 0
            this.readOnly = false
            this.currentTaskId = MAIN_GRAPH_ID
            this.blueprint = emptyBlueprint()
            this._lastSaveError = null
            this._saveErrors = {}
            this._savePendingCount = 0
            this._lastSavedAt = 0
            this.taskNodesVersion++
            this.assetPreviewVersion++
        },

        invalidateAssetPreviews() {
            this.assetPreviewVersion++
        },

        async loadProjectData() {
            if (!this.currentProjectPath) return null
            const data = await this._fetchProjectData(this.currentProjectPath, this.currentProjectName)
            this._applyProjectData(data)
            return data
        },

        async _fetchProjectData(path, fallbackName = '') {
            const [meta, workflow, topology] = await Promise.all([
                blueprintApi.getBlueprint(path),
                blueprintApi.getWorkflow(path),
                blueprintApi.getTopology(path)
            ])
            if (!meta || !workflow || !workflow.main_graph || !Array.isArray(workflow.functions) || !Array.isArray(workflow.function_folders)) {
                throw new Error('项目数据结构无效：workflow.json 必须包含 main_graph、functions 与 function_folders')
            }
            if (!topology || !Array.isArray(topology.nodes) || !Array.isArray(topology.edges)) {
                throw new Error('项目数据结构无效：topology.json 必须包含 nodes 与 edges 数组')
            }
            if ([meta, workflow, topology].some(document => document.schema_version !== PROJECT_SCHEMA_VERSION)) {
                throw new Error(`项目格式版本不匹配：当前只支持 schema_version ${PROJECT_SCHEMA_VERSION}`)
            }
            return {
                schema_version: PROJECT_SCHEMA_VERSION,
                project_id: meta.project_id,
                revision: meta.revision,
                project_name: meta.project_name || fallbackName,
                variables: meta.variables && typeof meta.variables === 'object' ? meta.variables : {},
                ui_state: meta.ui_state ? { ...DEFAULT_UI_STATE, ...meta.ui_state } : { ...DEFAULT_UI_STATE },
                settings: meta.settings && typeof meta.settings === 'object' ? meta.settings : {},
                main_graph: workflow.main_graph,
                functions: workflow.functions,
                function_folders: workflow.function_folders,
                page_map: topology
            }
        },

        _applyProjectData(data) {
            this.blueprint = data
            const graphs = [
                { id: MAIN_GRAPH_ID, graph: this.blueprint.main_graph },
                ...(this.blueprint.functions || []).map(item => ({ id: item.function_id, graph: item.graph })),
                { id: 'page_map', graph: this.blueprint.page_map }
            ]
            for (const { id, graph } of graphs) {
                if (!graph) continue
                graph.nodes = Array.isArray(graph.nodes) ? graph.nodes : []
                graph.edges = Array.isArray(graph.edges) ? graph.edges : []
                const graphTask = { task_id: id, nodes: graph.nodes }
                reconcileStablePortRoutes([graphTask], graph.edges)
                reconcileGraphIntegrity([graphTask], graph.edges)
            }
            this.currentProjectName = data.project_name || this.currentProjectName
            this.currentProjectId = data.project_id || this.currentProjectId
            const graphIds = new Set([MAIN_GRAPH_ID, ...(data.functions || []).map(item => item.function_id)])
            if (!graphIds.has(this.currentTaskId)) this.currentTaskId = MAIN_GRAPH_ID
            this.taskNodesVersion++
            import('./uiStore').then(({ useUiStore }) => useUiStore()._restoreBreakpoints())
        },

        updateUiState(keyOrObject, value) {
            if (!this.blueprint.ui_state) this.blueprint.ui_state = { ...DEFAULT_UI_STATE }
            if (typeof keyOrObject === 'object') Object.assign(this.blueprint.ui_state, keyOrObject)
            else if (typeof keyOrObject === 'string') this.blueprint.ui_state[keyOrObject] = value
            this.saveProjectMetaDebounced()
        },

        toggleMinimap() { this.updateUiState('minimapExpanded', !this.uiState.minimapExpanded) },
        toggleLogPanel() { this.updateUiState('bottomPanelExpanded', !this.uiState.bottomPanelExpanded) },
        async loadTasks() { await this.loadProjectData(); return this.tasks },

        async loadTaskData(taskId) {
            if (!taskId || (taskId !== MAIN_GRAPH_ID && !getFunction(this.blueprint.functions, taskId))) {
                throw new Error(`画布不存在: ${taskId || '(空)'}`)
            }
            this.currentTaskId = taskId
            this.taskNodesVersion++
            return this.currentTaskData
        },

        _metaSnapshot() {
            const session = this._sessionSnapshot()
            if (!session) return null
            return { ...session, data: clone({
                project_name: this.blueprint.project_name,
                variables: this.blueprint.variables || {},
                ui_state: this.blueprint.ui_state || {},
                settings: this.blueprint.settings || {}
            }) }
        },

        _workflowSnapshot() {
            const session = this._sessionSnapshot()
            if (!session) return null
            const graphs = [
                { id: MAIN_GRAPH_ID, graph: this.blueprint.main_graph },
                ...(this.blueprint.functions || []).map(item => ({ id: item.function_id, graph: item.graph }))
            ]
            for (const { id, graph } of graphs) {
                const graphTask = { task_id: id, nodes: graph?.nodes || [] }
                reconcileStablePortRoutes([graphTask], graph?.edges || [])
                reconcileGraphIntegrity([graphTask], graph?.edges || [])
            }
            return { ...session, data: clone({
                main_graph: this.blueprint.main_graph,
                functions: this.blueprint.functions || [],
                function_folders: this.blueprint.function_folders || []
            }) }
        },

        _topologySnapshot() {
            const session = this._sessionSnapshot()
            if (!session) return null
            const pageMap = this.blueprint.page_map || createPageMap()
            const pageTask = { task_id: 'page_map', nodes: pageMap.nodes || [] }
            reconcileStablePortRoutes([pageTask], pageMap.edges || [])
            reconcileGraphIntegrity([pageTask], pageMap.edges || [])
            return { ...session, data: clone(pageMap) }
        },

        _blueprintSnapshot() {
            const session = this._sessionSnapshot()
            if (!session) return null
            const workflow = this._workflowSnapshot()?.data || {}
            const pageMap = this._topologySnapshot()?.data || createPageMap()
            return { ...session, data: clone({
                project_name: this.blueprint.project_name,
                variables: this.blueprint.variables || {},
                ui_state: this.blueprint.ui_state || {},
                settings: this.blueprint.settings || {},
                main_graph: workflow.main_graph,
                functions: workflow.functions,
                function_folders: workflow.function_folders,
                page_map: pageMap
            }) }
        },

        _assertWritable() {
            if (this.readOnly) throw new Error('项目以只读方式打开，不能修改或运行')
        },

        _clearSaveErrors(queueNames) {
            const names = new Set(Array.isArray(queueNames) ? queueNames : [queueNames])
            const errors = { ...(this._saveErrors || {}) }
            names.forEach(name => delete errors[name])
            this._saveErrors = errors
            const first = Object.values(errors)[0]
            this._lastSaveError = first ? new Error(first) : null
        },

        _recordImmediateSaveError(queueName, error) {
            const errors = { ...(this._saveErrors || {}) }
            errors[queueName] = error?.message || String(error)
            this._saveErrors = errors
            this._lastSaveError = new Error(errors[queueName])
        },

        async _runImmediateSave(queueNames, writer) {
            const names = Array.isArray(queueNames) ? queueNames : [queueNames]
            const errorKey = names.length === 1 ? names[0] : 'blueprint'
            // A deliberate retry must be allowed to recover from a previous
            // transient error.  Keep errors from unrelated document domains.
            this._clearSaveErrors(names)
            this._savePendingCount += 1
            try {
                const result = await enqueueProjectWrite(this, writer)
                this._clearSaveErrors(names)
                this._lastSavedAt = Date.now()
                return result
            } catch (error) {
                this._recordImmediateSaveError(errorKey, error)
                throw error
            } finally {
                this._savePendingCount = Math.max(0, this._savePendingCount - 1)
            }
        },

        async saveProjectMeta(snapshot = null) {
            if (!this.currentProjectPath) return
            this._assertWritable()
            const value = snapshot || this._metaSnapshot()
            if (value) return await this._runImmediateSave('meta', () => (
                blueprintApi.saveBlueprint(value.path, value.data, value.identity)
            ))
        },
        async saveWorkflowImmediately(snapshot = null) {
            if (!this.currentProjectPath) return
            this._assertWritable()
            const value = snapshot || this._workflowSnapshot()
            if (value) return await this._runImmediateSave('workflow', () => (
                blueprintApi.saveWorkflow(value.path, value.data, value.identity)
            ))
        },
        async saveTopologyData(snapshot = null) {
            if (!this.currentProjectPath) return
            this._assertWritable()
            const value = snapshot || this._topologySnapshot()
            if (value) return await this._runImmediateSave('topology', () => (
                blueprintApi.saveTopology(value.path, value.data, value.identity)
            ))
        },
        async saveBlueprintImmediately(snapshot = null) {
            if (!this.currentProjectPath) return
            this._assertWritable()
            const value = snapshot || this._blueprintSnapshot()
            if (value) return await this._runImmediateSave(
                ['meta', 'workflow', 'topology', 'blueprint'],
                () => blueprintApi.saveBlueprint(value.path, value.data, value.identity)
            )
        },

        saveProjectMetaDebounced() {
            this._scheduleDeferredSave('meta', () => this._metaSnapshot())
        },
        saveWorkflowDebounced() {
            this._scheduleDeferredSave('workflow', () => this._workflowSnapshot())
        },
        saveTopologyDebounced() {
            this._scheduleDeferredSave('topology', () => this._topologySnapshot())
        },
        saveBlueprintDebounced() {
            this._scheduleDeferredSave('blueprint', () => this._blueprintSnapshot())
        },

        async flushPendingSaves() {
            const queues = queuesFor(this)
            await Promise.all([queues.meta.flush(), queues.workflow.flush(), queues.topology.flush(), queues.blueprint.flush()])
            if (this._lastSaveError) throw this._lastSaveError
        },
        hasPendingSaves() {
            return Object.values(queuesFor(this)).some(queue => queue.isPending())
        },
        cancelPendingSaves() {
            const queues = queuesFor(this)
            queues.meta.cancel(); queues.workflow.cancel(); queues.topology.cancel(); queues.blueprint.cancel()
        },

        async reloadAfterResourceMutation() {
            this.cancelPendingSaves()
            const result = await this.loadProjectData()
            await projectWorkspaceApi.acknowledge()
            return result
        },

        async checkExternalChanges() {
            if (!this.workspaceId || this.workspaceBusy) return { changed: false, paths: [] }
            return await projectWorkspaceApi.changes()
        },

        async reloadExternalChanges() {
            this.cancelPendingSaves()
            const result = await this.loadProjectData()
            await projectWorkspaceApi.acknowledge()
            return result
        },

        async reopenAfterExternalIdentityChange() {
            const path = this.currentProjectPath
            if (!path) return null
            this.cancelPendingSaves()
            await projectWorkspaceApi.close()
            this._resetProjectState()
            return await this.loadProjectByPath(path)
        },

        async keepLocalAfterExternalChange() {
            await projectWorkspaceApi.acknowledge()
            await this.flushPendingSaves()
        },

        async saveFunctionData(functionData) {
            if (!this.currentProjectPath || !functionData?.function_id) return
            this._assertWritable()
            await blueprintApi.saveFunction(functionData.function_id, this.currentProjectPath, functionData)
        },
        async deleteFunction(functionId) {
            if (!this.currentProjectPath || !functionId) return
            this._assertWritable()
            const references = collectFunctionReferences(this.blueprint, functionId)
            if (references.length) throw new Error(`该函数仍被 ${references.length} 个调用函数节点使用`)
            await blueprintApi.deleteFunction(functionId, this.currentProjectPath)
            this.blueprint.functions = (this.blueprint.functions || []).filter(item => item.function_id !== functionId)
            if (this.currentTaskId === functionId) this.currentTaskId = MAIN_GRAPH_ID
        },
        async saveCurrentTask() { await this.saveBlueprintImmediately() },
        async loadTaskNodes(taskId) {
            return getGraph(this.blueprint, taskId)?.nodes || []
        },
        async createFunction(name = '新建函数', folderId = null) {
            if (!this.currentProjectPath) return
            this._assertWritable()
            const result = await blueprintApi.createFunction(this.currentProjectPath, name, folderId)
            await this.loadProjectData()
            return result
        },
        async duplicateFunction(functionId) {
            const result = await blueprintApi.duplicateFunction(functionId, this.currentProjectPath)
            await this.loadProjectData()
            return result
        }
    }
})
