// stores/index.js - 向后兼容的重导出
// 大 Store 已拆分为 4 个独立 Store（拓扑数据已收编进 projectStore.blueprint.topology），此处保持旧 API 兼容
export { useProjectStore } from './projectStore'
export { useUiStore } from './uiStore'
export { useExecutionStore } from './executionStore'
export { useContextStore } from './contextStore'
export { DEFAULT_UI_STATE } from './projectStore'

// 向后兼容：useMainStore 代理到各子 Store
import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'
import { useUiStore } from './uiStore'
import { useExecutionStore } from './executionStore'
import { useContextStore } from './contextStore'

export const useMainStore = defineStore('main', {
    state: () => ({}),
    getters: {
        // ===== 子 Store 引用（架构层） =====
        projectStore() { return useProjectStore() },
        uiStore() { return useUiStore() },
        executionStore() { return useExecutionStore() },
        contextStore() { return useContextStore() },

        // ===== projectStore 关键字段代理（向后兼容） =====
        currentProjectPath() { return useProjectStore().currentProjectPath },
        currentProjectName() { return useProjectStore().currentProjectName },
        recentProjects() { return useProjectStore().recentProjects },
        blueprint() { return useProjectStore().blueprint },
        paramsDefinitions() { return useProjectStore().paramsDefinitions },
        currentTaskId() { return useProjectStore().currentTaskId },
        tasks() { return useProjectStore().tasks },
        currentTask() { return useProjectStore().currentTask },
        nodes() { return useProjectStore().nodes },
        params() { return useProjectStore().params },
        uiState() { return useProjectStore().uiState },
        workflowData() { return useProjectStore().workflowData },
        topologyData() { return useProjectStore().topologyData },

        // ===== uiStore 关键字段代理 =====
        selectedNodeId() { return useUiStore().selectedNodeId },
        selectedNodeIds() { return useUiStore().selectedNodeIds },
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
        currentActiveNodeId() { return useExecutionStore().currentActiveNodeId },
        isRunning() { return useExecutionStore().isRunning },
        isPaused() { return useExecutionStore().isPaused },

        // ===== contextStore 关键字段代理 =====
        currentContext() { return useContextStore().currentContext }
    },
    actions: {
        // ===== projectStore 关键方法代理 =====
        async loadParams() { return useProjectStore().loadParams() },
        async loadProjectByPath(path) { return useProjectStore().loadProjectByPath(path) },
        async loadProjectData() { return useProjectStore().loadProjectData() },
        updateUiState(keyOrObject, value) { return useProjectStore().updateUiState(keyOrObject, value) },
        toggleMinimap() { return useProjectStore().toggleMinimap() },
        toggleLogPanel() { return useProjectStore().toggleLogPanel() },
        async loadTasks() { return useProjectStore().loadTasks() },
        async saveProjectMeta() { return useProjectStore().saveProjectMeta() },
        saveProjectMetaDebounced() { return useProjectStore().saveProjectMetaDebounced() },
        async saveWorkflowImmediately() { return useProjectStore().saveWorkflowImmediately() },
        async saveTopologyData() { return useProjectStore().saveTopologyData() },
        saveTopologyDebounced() { return useProjectStore().saveTopologyDebounced() },
        saveBlueprintDebounced() { return useProjectStore().saveBlueprintDebounced() },
        async saveBlueprintImmediately() { return useProjectStore().saveBlueprintImmediately() },
        async saveCurrentTask() { return useProjectStore().saveCurrentTask() },
        async loadTaskNodes(taskId) { return useProjectStore().loadTaskNodes(taskId) },
        async createNewTask(taskName) { return useProjectStore().createNewTask(taskName) },

        // ===== uiStore 关键方法代理 =====
        setCanvasMode(mode) { return useUiStore().setCanvasMode(mode) },
        selectNode(nodeId) { return useUiStore().selectNode(nodeId) },
        selectNodes(nodeIds) { return useUiStore().selectNodes(nodeIds) },
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
        startDebugPolling(intervalMs) { return useExecutionStore().startDebugPolling(intervalMs) },
        stopDebugPolling() { return useExecutionStore().stopDebugPolling() },

        // ===== contextStore 关键方法代理 =====
        async loadContext() { return useContextStore().loadContext() },
        async setCurrentContext(ctx) { return useContextStore().setCurrentContext(ctx) }
    }
})
