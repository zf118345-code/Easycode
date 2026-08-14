import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'
import { useTopologyStore } from './topologyStore'

export const useUiStore = defineStore('ui', {
    state: () => ({
        selectedNodeId: null,
        selectedNodeIds: [],
        selectedGroupId: null,
        canvasMode: 'workflow',
        // ===== 节点列表批量操作模式 =====
        batchMode: false,
        // ===== 断点（调试会话级断点 node_id 集合） =====
        breakpoints: new Set(),
        // ===== 画布镜头聚焦（跨组件通信：ProjectExplorer → WorkflowCanvas） =====
        focusTarget: null  // { type: 'node' | 'group', id, timestamp }
    }),

    getters: {
        selectedNode() {
            const projectStore = useProjectStore()
            const selectedNodeId = this.selectedNodeId
            for (const task of (projectStore.blueprint.tasks || [])) {
                const node = (task.nodes || []).find(n => n.node_id === selectedNodeId)
                if (node) return node
            }
            return null
        },
        hasBreakpoints(state) {
            return state.breakpoints.size > 0
        }
    },

    actions: {
        setCanvasMode(mode) {
            if (mode !== 'workflow' && mode !== 'topology') return
            if (this.canvasMode === mode) return
            this.canvasMode = mode
            if (mode === 'topology') {
                useTopologyStore().selectedTopologyNodeId = null
            }
            useProjectStore().updateUiState('canvasMode', mode)
        },

        selectNode(nodeId) {
            this.selectedNodeId = nodeId || null
            this.selectedNodeIds = nodeId ? [nodeId] : []
        },

        selectNodes(nodeIds) {
            this.selectedNodeIds = Array.isArray(nodeIds) ? [...nodeIds] : []
            this.selectedNodeId = this.selectedNodeIds[0] || null
        },

        clearSelection() {
            this.selectedNodeId = null
            this.selectedNodeIds = []
        },

        setSelectedGroup(groupId) {
            this.selectedGroupId = groupId || null
        },

        // ===== 批量模式 =====
        toggleBatchMode() {
            this.batchMode = !this.batchMode
            if (!this.batchMode) {
                this.selectedNodeIds = []
            }
        },
        enterBatchMode() {
            this.batchMode = true
        },
        exitBatchMode() {
            this.batchMode = false
            this.selectedNodeIds = []
        },

        // ===== 单节点多选切换（Ctrl + 点 或 复选框） =====
        toggleNodeSelection(nodeId) {
            if (!nodeId) return
            const idx = this.selectedNodeIds.indexOf(nodeId)
            if (idx >= 0) {
                this.selectedNodeIds.splice(idx, 1)
            } else {
                this.selectedNodeIds.push(nodeId)
            }
            if (this.selectedNodeIds.length === 1) {
                this.selectedNodeId = this.selectedNodeIds[0]
            } else if (!this.selectedNodeIds.includes(this.selectedNodeId || '')) {
                this.selectedNodeId = this.selectedNodeIds[0] || null
            }
        },

        // ===== 全选当前任务的节点 =====
        selectAllNodes() {
            const projectStore = useProjectStore()
            const nodes = projectStore.nodes || []
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
            const task = projectStore.currentTask
            if (!task || !task.nodes) return
            const idsToDelete = new Set(this.selectedNodeIds)
            task.nodes = task.nodes.filter(n => !idsToDelete.has(n.node_id))
            // 同时移除相关的边
            if (projectStore.blueprint.edges) {
                projectStore.blueprint.edges = projectStore.blueprint.edges.filter(
                    e => !idsToDelete.has(e.source_node) && !idsToDelete.has(e.target_node)
                )
            }
            this.clearSelection()
            await projectStore.saveBlueprintDebounced()
        },

        // ===== 批量设置节点延迟 =====
        async batchSetDelay(delayMs) {
            if (!this.selectedNodeIds.length) return
            const projectStore = useProjectStore()
            const nodes = projectStore.nodes || []
            const ids = new Set(this.selectedNodeIds)
            for (const n of nodes) {
                if (ids.has(n.node_id)) {
                    n.delay_before = Number(delayMs) || 0
                }
            }
            await projectStore.saveBlueprintDebounced()
        },

        // ===== 断点管理 =====
        toggleBreakpoint(nodeId) {
            if (!nodeId) return false
            if (this.breakpoints.has(nodeId)) {
                this.breakpoints.delete(nodeId)
                return false
            } else {
                this.breakpoints.add(nodeId)
                return true
            }
        },
        addBreakpoint(nodeId) {
            if (nodeId) this.breakpoints.add(nodeId)
        },
        enableBreakpoint(nodeId) {
            // 语义化别名：设置节点断点（不存在则添加，已存在保持）
            if (nodeId) this.breakpoints.add(nodeId)
        },
        disableBreakpoint(nodeId) {
            if (nodeId) this.breakpoints.delete(nodeId)
        },
        removeBreakpoint(nodeId) {
            if (nodeId) this.breakpoints.delete(nodeId)
        },
        clearBreakpoints() {
            this.breakpoints.clear()
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
        }
    }
})
