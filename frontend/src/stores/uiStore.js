import { defineStore } from 'pinia'
import { useProjectStore } from './projectStore'
import { useTopologyStore } from './topologyStore'

export const useUiStore = defineStore('ui', {
    state: () => ({
        selectedNodeId: null,
        selectedNodeIds: [],
        selectedGroupId: null,
        canvasMode: 'workflow'
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
        }
    }
})
