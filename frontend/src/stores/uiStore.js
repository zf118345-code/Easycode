import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'

function activeGraph(projectStore, canvasMode) {
    if (canvasMode === 'topology') return projectStore.blueprint?.page_map || null
    if (canvasMode === 'function') return projectStore.currentFunction?.graph || null
    return projectStore.blueprint?.main_graph || null
}

export const useUiStore = defineStore('ui', {
    state: () => ({
        // selectedNodeId is retained as a compatibility alias for the
        // primary/inspected node. selectedNodeIds is the only collection
        // used by the canvas, explorer and inspector.
        selectedNodeId: null,
        selectedNodeIds: [],
        primaryNodeId: null,
        selectionAnchorId: null,
        selectedEdgeIds: [],
        canvasMode: 'workflow',
        // 函数入口是一个真实的库工作区。进入后先展示空状态，只有从
        // 左侧选择具体函数才挂载对应画布，避免误把主流程当成函数编辑。
        functionWorkspaceEmpty: false,
        // ===== 断点（调试会话级断点 node_id 集合） =====
        breakpoints: new Set(),
        // ===== 画布镜头聚焦（跨组件通信：ProjectExplorer → WorkflowCanvas） =====
        focusTarget: null,  // { type: 'node' | 'group', id, timestamp }
        // ===== 控件捕获填充（节点表单/条件对话框「捕获控件」按钮注册的填充回调） =====
        captureFillHandler: null,  // (info) => void，Ctrl+Shift+Enter 捕获成功后调用
        // 属性面板的一次性原生截图回填。它不持久化，只在当前编辑会话内存活。
        fieldCaptureRequestId: null,
        fieldCaptureHandler: null,
        fieldCaptureCancelHandler: null,
        // ===== 属性检查器外部刷新（捕获填充后强制检查器重新同步当前节点） =====
        inspectorSyncTick: 0
    }),

    getters: {
        selectedNode() {
            const projectStore = useProjectStore()
            const selectedNodeId = this.selectedNodeId
            if (this.canvasMode === 'topology') {
                return (projectStore.blueprint?.page_map?.nodes || []).find(node => node.node_id === selectedNodeId) || null
            }
            const graph = this.canvasMode === 'function'
                ? projectStore.currentFunction?.graph
                : projectStore.blueprint?.main_graph
            return (graph?.nodes || []).find(node => node.node_id === selectedNodeId) || null
        },
        hasBreakpoints(state) {
            return state.breakpoints.size > 0
        }
    },

    actions: {
        setCanvasMode(mode) {
            if (!['workflow', 'function', 'topology'].includes(mode)) return
            if (this.canvasMode === mode) return
            this.canvasMode = mode
            if (mode !== 'function') this.functionWorkspaceEmpty = false
            // 切换 Tab 时清空选中状态（同一套选中状态，两 Tab 共用）
            this.selectedNodeId = null
            this.selectedNodeIds = []
            this.primaryNodeId = null
            this.selectionAnchorId = null
            this.selectedEdgeIds = []
            useProjectStore().updateUiState('canvasMode', mode)
        },

        enterFunctionLibrary() {
            this.canvasMode = 'function'
            this.functionWorkspaceEmpty = true
            this.clearSelection()
            this.focusTarget = null
            useProjectStore().updateUiState('canvasMode', 'function')
        },

        showFunctionGraph() {
            this.canvasMode = 'function'
            this.functionWorkspaceEmpty = false
            this.clearSelection()
            useProjectStore().updateUiState('canvasMode', 'function')
        },

        selectNode(nodeId) {
            this.selectedNodeId = nodeId || null
            this.selectedNodeIds = nodeId ? [nodeId] : []
            this.primaryNodeId = nodeId || null
            this.selectionAnchorId = nodeId || null
            this.selectedEdgeIds = []
        },

        selectNodes(nodeIds, options = {}) {
            const uniqueIds = Array.from(new Set((Array.isArray(nodeIds) ? nodeIds : []).filter(Boolean)))
            this.selectedNodeIds = uniqueIds
            const requestedPrimary = options.primaryId
            this.primaryNodeId = uniqueIds.includes(requestedPrimary)
                ? requestedPrimary
                : (uniqueIds[0] || null)
            this.selectedNodeId = this.primaryNodeId
            if (options.preserveAnchor !== true) {
                const requestedAnchor = options.anchorId
                this.selectionAnchorId = uniqueIds.includes(requestedAnchor)
                    ? requestedAnchor
                    : this.primaryNodeId
            }
            this.selectedEdgeIds = Array.from(new Set((options.edgeIds || []).filter(Boolean)))
        },

        selectPath(nodeIds, edgeIds = [], anchorId = null, primaryId = null) {
            this.selectNodes(nodeIds, {
                edgeIds,
                anchorId: anchorId || nodeIds?.[0] || null,
                primaryId: primaryId || nodeIds?.at?.(-1) || null
            })
        },

        selectEdge(edgeId, additive = false) {
            if (!edgeId) return
            this.selectedEdgeIds = additive
                ? Array.from(new Set([...this.selectedEdgeIds, edgeId]))
                : [edgeId]
        },

        clearEdgeSelection() {
            this.selectedEdgeIds = []
        },

        clearSelection() {
            this.selectedNodeId = null
            this.selectedNodeIds = []
            this.primaryNodeId = null
            this.selectionAnchorId = null
            this.selectedEdgeIds = []
        },

        // ===== 单节点多选切换（Ctrl + 点 或 复选框） =====
        toggleNodeSelection(nodeId) {
            if (!nodeId) return
            const idx = this.selectedNodeIds.indexOf(nodeId)
            if (idx >= 0) {
                this.selectedNodeIds = this.selectedNodeIds.filter(id => id !== nodeId)
            } else {
                this.selectedNodeIds = [...this.selectedNodeIds, nodeId]
            }
            this.primaryNodeId = this.selectedNodeIds.includes(nodeId)
                ? nodeId
                : (this.selectedNodeIds.at(-1) || null)
            this.selectedNodeId = this.primaryNodeId
            this.selectionAnchorId = this.primaryNodeId
            this.selectedEdgeIds = []
        },

        // ===== 全选当前任务的节点 =====
        selectAllNodes() {
            const projectStore = useProjectStore()
            const nodes = activeGraph(projectStore, this.canvasMode)?.nodes || []
            const allIds = nodes.map(n => n.node_id)
            // 已全选 -> 取消全选
            if (allIds.length > 0 && this.selectedNodeIds.length === allIds.length &&
                allIds.every(id => this.selectedNodeIds.includes(id))) {
                this.selectedNodeIds = []
                this.selectedNodeId = null
                return
            }
            this.selectNodes(allIds)
        },

        // ===== 批量删除选中节点 =====
        async batchDeleteNodes() {
            if (!this.selectedNodeIds.length) return
            const projectStore = useProjectStore()
            const idsToDelete = new Set(this.selectedNodeIds)
            const isTopology = this.canvasMode === 'topology'
            const graph = activeGraph(projectStore, this.canvasMode)
            if (!graph) return
            const fixedIds = new Set((graph.nodes || []).filter(node => node.fixed).map(node => node.node_id))
            const removable = new Set([...idsToDelete].filter(id => !fixedIds.has(id)))
            graph.nodes = (graph.nodes || []).filter(node => !removable.has(node.node_id))
            const nextEdges = (graph.edges || []).filter(edge =>
                !removable.has(edge.source_node) && !removable.has(edge.target_node)
            )
            graph.edges = nextEdges
            if (isTopology) await projectStore.saveTopologyData()
            else await projectStore.saveWorkflowImmediately()
            this.clearSelection()
        },

        // ===== 批量设置节点延迟 =====
        async batchSetDelay(delayMs) {
            if (!this.selectedNodeIds.length) return
            const projectStore = useProjectStore()
            const graph = activeGraph(projectStore, this.canvasMode)
            if (!graph) return
            const nodes = graph.nodes || []
            const ids = new Set(this.selectedNodeIds)
            for (const n of nodes) {
                if (ids.has(n.node_id)) {
                    n.delay_before = Number(delayMs) || 0
                }
            }
            if (this.canvasMode === 'topology') projectStore.saveTopologyDebounced()
            else projectStore.saveWorkflowDebounced()
        },

        // ===== 断点管理（持久化到 project.json ui_state，刷新后保留） =====
        _persistBreakpoints() {
            useProjectStore().updateUiState('breakpoints', Array.from(this.breakpoints))
        },
        async _syncBreakpointsToSession() {
            // 运行中/已暂停会话的断点即时同步（覆盖式下发），失败静默（会话可能已结束/网络异常）
            try {
                const { useExecutionStore } = await import('./executionStore')
                const { executionApi } = await import('../api/executionApi')
                const execStore = useExecutionStore()
                const sessionId = execStore.currentExecutionId
                if (!sessionId) return
                if (execStore.executionState !== 'running' && execStore.executionState !== 'paused') return
                await executionApi.setBreakpoints(sessionId, this.getBreakpointList())
            } catch { /* 静默 */ }
        },
        _restoreBreakpoints() {
            const saved = useProjectStore().blueprint?.ui_state?.breakpoints
            if (Array.isArray(saved)) {
                this.breakpoints = new Set(saved)
            }
        },
        toggleBreakpoint(nodeId) {
            if (!nodeId) return false
            if (this.breakpoints.has(nodeId)) {
                this.breakpoints.delete(nodeId)
            } else {
                this.breakpoints.add(nodeId)
            }
            this._persistBreakpoints()
            this._syncBreakpointsToSession()
            return this.breakpoints.has(nodeId)
        },
        addBreakpoint(nodeId) {
            if (nodeId) {
                this.breakpoints.add(nodeId)
                this._persistBreakpoints()
                this._syncBreakpointsToSession()
            }
        },
        enableBreakpoint(nodeId) {
            // 语义化别名：设置节点断点（不存在则添加，已存在保持）
            if (nodeId) {
                this.breakpoints.add(nodeId)
                this._persistBreakpoints()
                this._syncBreakpointsToSession()
            }
        },
        disableBreakpoint(nodeId) {
            if (nodeId) {
                this.breakpoints.delete(nodeId)
                this._persistBreakpoints()
                this._syncBreakpointsToSession()
            }
        },
        removeBreakpoint(nodeId) {
            if (nodeId) {
                this.breakpoints.delete(nodeId)
                this._persistBreakpoints()
                this._syncBreakpointsToSession()
            }
        },
        clearBreakpoints() {
            this.breakpoints.clear()
            this._persistBreakpoints()
            this._syncBreakpointsToSession()
        },
        hasBreakpoint(nodeId) {
            return nodeId ? this.breakpoints.has(nodeId) : false
        },
        getBreakpointList() {
            return Array.from(this.breakpoints)
        },

        // ===== 画布镜头聚焦 =====
        setFocusTarget(target) {
            this.focusTarget = target || null
        },

        // ===== 控件捕获填充 =====
        setCaptureFillHandler(handler) {
            this.captureFillHandler = typeof handler === 'function' ? handler : null
        },
        clearCaptureFillHandler() {
            this.captureFillHandler = null
        },
        setFieldCaptureHandler(requestId, handler, cancelHandler = null) {
            this.fieldCaptureRequestId = requestId || null
            this.fieldCaptureHandler = typeof handler === 'function' ? handler : null
            this.fieldCaptureCancelHandler = typeof cancelHandler === 'function' ? cancelHandler : null
        },
        async completeFieldCapture(payload) {
            if (!payload || payload.field_request_id !== this.fieldCaptureRequestId || !this.fieldCaptureHandler) {
                throw new Error('属性捕获请求已失效，请重新点击捕获')
            }
            const handler = this.fieldCaptureHandler
            this.clearFieldCaptureHandler()
            return await handler(payload)
        },
        cancelFieldCapture(requestId = null) {
            if (requestId && requestId !== this.fieldCaptureRequestId) return false
            const cancel = this.fieldCaptureCancelHandler
            this.clearFieldCaptureHandler()
            if (cancel) cancel()
            return true
        },
        clearFieldCaptureHandler() {
            this.fieldCaptureRequestId = null
            this.fieldCaptureHandler = null
            this.fieldCaptureCancelHandler = null
        },
        bumpInspectorSync() {
            this.inspectorSyncTick += 1
        }
    }
})
