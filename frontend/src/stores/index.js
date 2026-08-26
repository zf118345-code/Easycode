// stores/index.js - Store 统一出口与 IDE 门面。
// 领域状态由 4 个独立 Store 持有，useIdeStore 仅为组件提供统一访问入口。
export { useProjectStore } from './projectStore'
export { useUiStore } from './uiStore'
export { useExecutionStore } from './executionStore'
export { useContextStore } from './contextStore'
export { DEFAULT_UI_STATE } from './projectStore'

import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'
import { useUiStore } from './uiStore'
import { useExecutionStore } from './executionStore'
import { useContextStore } from './contextStore'

export const useIdeStore = defineStore('ide', {
    state: () => ({}),
    getters: {
        // ===== 子 Store 引用（架构层） =====
        projectStore() { return useProjectStore() },
        uiStore() { return useUiStore() },
        executionStore() { return useExecutionStore() },
        contextStore() { return useContextStore() },

        // ===== projectStore =====
        currentProjectPath() { return useProjectStore().currentProjectPath },
        taskNodesVersion() { return useProjectStore().taskNodesVersion },
        currentProjectName() { return useProjectStore().currentProjectName },
        currentProjectId() { return useProjectStore().currentProjectId },
        projectReadOnly() { return useProjectStore().readOnly },
        recentProjects() { return useProjectStore().recentProjects },
        blueprint() { return useProjectStore().blueprint },
        paramsDefinitions() { return useProjectStore().paramsDefinitions },
        currentTaskId() { return useProjectStore().currentTaskId },
        tasks() { return useProjectStore().tasks },
        currentTask() { return useProjectStore().currentTask },
        currentTaskData() { return useProjectStore().currentTaskData },
        nodes() { return useProjectStore().nodes },
        params() { return useProjectStore().params },
        uiState() { return useProjectStore().uiState },
        workflowData() { return useProjectStore().workflowData },
        topologyData() { return useProjectStore().topologyData },
        minimapExpanded() { return useProjectStore().uiState.minimapExpanded },

        // ===== uiStore 关键字段代理 =====
        selectedNodeId() { return useUiStore().selectedNodeId },
        selectedNodeIds() { return useUiStore().selectedNodeIds },
        primaryNodeId() { return useUiStore().primaryNodeId },
        selectionAnchorId() { return useUiStore().selectionAnchorId },
        selectedEdgeIds() { return useUiStore().selectedEdgeIds },
        selectedGroupId() { return useUiStore().selectedGroupId },
        selectedNode() { return useUiStore().selectedNode },
        canvasMode() { return useUiStore().canvasMode },
        batchMode() { return useUiStore().batchMode },
        breakpoints() { return useUiStore().breakpoints },
        hasBreakpoints() { return useUiStore().hasBreakpoints },
        focusTarget() { return useUiStore().focusTarget },

        // ===== executionStore 关键字段代理 =====
        executionLogs() { return useExecutionStore().executionLogs },
        currentExecutionId() { return useExecutionStore().currentExecutionId },
        executionState() { return useExecutionStore().executionState },
        executionPaused() { return useExecutionStore().executionPaused },
        executionVariables() { return useExecutionStore().executionVariables },
        executionCallstack() { return useExecutionStore().executionCallstack },
        executionCurrentVariables() { return useExecutionStore().executionCurrentVariables },
        executionPrevVariables() { return useExecutionStore().executionPrevVariables },
        previousActiveNodeId() { return useExecutionStore().previousActiveNodeId },
        currentActiveNodeId() { return useExecutionStore().currentActiveNodeId },
        isRunning() { return useExecutionStore().isRunning },
        isPaused() { return useExecutionStore().isPaused },

        // ===== contextStore 关键字段代理 =====
        currentContext() { return useContextStore().currentContext }
    },
    actions: {
        // ===== projectStore 关键方法代理 =====
        async loadParams() { return useProjectStore().loadParams() },
        async loadProjectByPath(path, options) { return useProjectStore().loadProjectByPath(path, options) },
        async loadProjectData() { return useProjectStore().loadProjectData() },
        updateUiState(keyOrObject, value) { return useProjectStore().updateUiState(keyOrObject, value) },
        toggleMinimap() { return useProjectStore().toggleMinimap() },
        toggleLogPanel() { return useProjectStore().toggleLogPanel() },
        async loadTasks() { return useProjectStore().loadTasks() },
        async loadTaskData(taskId) { return useProjectStore().loadTaskData(taskId) },
        async saveProjectMeta() { return useProjectStore().saveProjectMeta() },
        saveProjectMetaDebounced() { return useProjectStore().saveProjectMetaDebounced() },
        async saveWorkflowImmediately() { return useProjectStore().saveWorkflowImmediately() },
        saveWorkflowDebounced() { return useProjectStore().saveWorkflowDebounced() },
        async saveTopologyData() { return useProjectStore().saveTopologyData() },
        saveTopologyDebounced() { return useProjectStore().saveTopologyDebounced() },
        saveBlueprintDebounced() { return useProjectStore().saveBlueprintDebounced() },
        async saveBlueprintImmediately() { return useProjectStore().saveBlueprintImmediately() },
        async flushPendingSaves() { return useProjectStore().flushPendingSaves() },
        async saveCurrentTask() { return useProjectStore().saveCurrentTask() },
        async loadTaskNodes(taskId) { return useProjectStore().loadTaskNodes(taskId) },
        async createFunction(name, folderId) { return useProjectStore().createFunction(name, folderId) },
        async saveFunctionData(functionData) { return useProjectStore().saveFunctionData(functionData) },
        async deleteFunction(functionId) { return useProjectStore().deleteFunction(functionId) },

        // ===== uiStore 关键方法代理 =====
        async setCanvasMode(mode) {
            // 切换前排空所有自动保存队列，保证属性面板最后一次输入和
            // 画布结构已经持久化后再改变数据源。
            const projectStore = useProjectStore()
            const uiStore = useUiStore()
            await projectStore.flushPendingSaves()
            // 结构操作通常即时保存，但如果之前一次请求因图引用不完整而
            // 失败，队列中不会留下任务。切换前再对当前内存图做一次完整
            // 规范化与权威保存；失败时绝不改变 canvasMode。
            if (projectStore.currentProjectPath && !projectStore.readOnly) {
                if (uiStore.canvasMode === 'topology') await projectStore.saveTopologyData()
                else await projectStore.saveWorkflowImmediately()
            }
            return uiStore.setCanvasMode(mode)
        },
        selectNode(nodeId) { return useUiStore().selectNode(nodeId) },
        selectNodes(nodeIds, options) { return useUiStore().selectNodes(nodeIds, options) },
        selectPath(nodeIds, edgeIds, anchorId, primaryId) { return useUiStore().selectPath(nodeIds, edgeIds, anchorId, primaryId) },
        selectEdge(edgeId, additive) { return useUiStore().selectEdge(edgeId, additive) },
        clearEdgeSelection() { return useUiStore().clearEdgeSelection() },
        clearSelection() { return useUiStore().clearSelection() },
        setSelectedGroup(groupId) { return useUiStore().setSelectedGroup(groupId) },
        toggleBatchMode() { return useUiStore().toggleBatchMode() },
        enterBatchMode() { return useUiStore().enterBatchMode() },
        exitBatchMode() { return useUiStore().exitBatchMode() },
        toggleNodeSelection(nodeId) { return useUiStore().toggleNodeSelection(nodeId) },
        selectAllNodes() { return useUiStore().selectAllNodes() },
        async batchDeleteNodes() { return useUiStore().batchDeleteNodes() },
        async batchSetDelay(delayMs) { return useUiStore().batchSetDelay(delayMs) },
        toggleBreakpoint(nodeId) { return useUiStore().toggleBreakpoint(nodeId) },
        addBreakpoint(nodeId) { return useUiStore().addBreakpoint(nodeId) },
        removeBreakpoint(nodeId) { return useUiStore().removeBreakpoint(nodeId) },
        clearBreakpoints() { return useUiStore().clearBreakpoints() },
        hasBreakpoint(nodeId) { return useUiStore().hasBreakpoint(nodeId) },
        getBreakpointList() { return useUiStore().getBreakpointList() },
        setFocusTarget(target) { return useUiStore().setFocusTarget(target) },

        // ===== executionStore 关键方法代理 =====
        async runTask(taskId, startNodeId) { return useExecutionStore().runTask(taskId, startNodeId) },
        async stopExecution() { return useExecutionStore().stopExecution() },
        async pauseExecution() { return useExecutionStore().pauseExecution() },
        async resumeExecution() { return useExecutionStore().resumeExecution() },
        async stepOverExecution() { return useExecutionStore().stepOverExecution() },
        async stepIntoExecution() { return useExecutionStore().stepIntoExecution() },
        async stepOutExecution() { return useExecutionStore().stepOutExecution() },
        async pollDebugState() { return useExecutionStore().pollDebugState() },
        async getExecutionVariables(level) { return useExecutionStore().getExecutionVariables(level) },
        startDebugPolling() { return useExecutionStore().startDebugPolling() },
        stopDebugPolling() { return useExecutionStore().stopDebugPolling() },

        // ===== contextStore 关键方法代理 =====
        async loadContext() { return useContextStore().loadContext() },
        async setCurrentContext(ctx) { return useContextStore().setCurrentContext(ctx) }
    }
})
