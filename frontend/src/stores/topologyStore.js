import { defineStore } from 'pinia'

export const useTopologyStore = defineStore('topology', {
    state: () => ({
        topologyBlueprint: { nodes: [], edges: [] },
        selectedTopologyNodeId: null
    }),

    getters: {
        topologyNodes: (state) => state.topologyBlueprint.nodes || [],
        topologyEdges: (state) => state.topologyBlueprint.edges || [],
        currentTopologyNode: (state) => {
            const nodes = state.topologyBlueprint.nodes || []
            return nodes.find(n => n.node_id === state.selectedTopologyNodeId) || null
        }
    },

    actions: {
        async loadTopologyFromBlueprint(blueprint) {
            // 兼容：未显式传 blueprint 时，自动从 projectStore 取，避免组件挂载时传空导致数据被清
            let bp = blueprint
            if (!bp) {
                const { useProjectStore } = await import('./projectStore')
                bp = useProjectStore().blueprint
            }
            const topo = bp?.topology
            if (topo && Array.isArray(topo.nodes) && Array.isArray(topo.edges)) {
                this.topologyBlueprint = {
                    nodes: JSON.parse(JSON.stringify(topo.nodes)),
                    edges: JSON.parse(JSON.stringify(topo.edges))
                }
            } else if ((this.topologyBlueprint?.nodes || []).length === 0) {
                // 只在真的没有数据时才初始化为空；有本地数据则保留（防止覆盖刚新增但尚未保存的节点）
                this.topologyBlueprint = { nodes: [], edges: [] }
            }
            this.selectedTopologyNodeId = null
        },

        selectTopologyNode(nodeId) {
            this.selectedTopologyNodeId = nodeId || null
        },

        syncTopologyToBlueprint() {
            return {
                nodes: JSON.parse(JSON.stringify(this.topologyBlueprint.nodes || [])),
                edges: JSON.parse(JSON.stringify(this.topologyBlueprint.edges || []))
            }
        },

        async saveTopologyToBlueprint() {
            const snapshot = this.syncTopologyToBlueprint()
            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()
            projectStore.blueprint.topology = snapshot
            projectStore.saveBlueprintDebounced()
        },

        addTopologyNode(nodeData) {
            if (!nodeData || !nodeData.node_id) return
            const exists = (this.topologyBlueprint.nodes || []).some(n => n.node_id === nodeData.node_id)
            if (exists) return
            const node = {
                node_id: nodeData.node_id,
                node_name: nodeData.node_name || nodeData.label || '页面状态',
                type: nodeData.type || 'page_state',
                page_id: nodeData.page_id || '',
                label: nodeData.label || '',
                position: nodeData.position || { x: 0, y: 0 },
                features: nodeData.features || [],
                feature_mode: nodeData.feature_mode || 'and',
                exits: nodeData.exits || [],
                params: nodeData.params || {},
                condition: nodeData.condition || null
            }
            this.topologyBlueprint.nodes.push(node)
            this.saveTopologyToBlueprint()
        },

        updateTopologyNode(nodeId, data) {
            if (!nodeId || !data) return
            const node = (this.topologyBlueprint.nodes || []).find(n => n.node_id === nodeId)
            if (!node) return
            Object.assign(node, data)
            this.saveTopologyToBlueprint()
        },

        removeTopologyNode(nodeId) {
            if (!nodeId) return
            this.topologyBlueprint.nodes = (this.topologyBlueprint.nodes || []).filter(n => n.node_id !== nodeId)
            this.topologyBlueprint.edges = (this.topologyBlueprint.edges || []).filter(e => {
                return e.source !== nodeId && e.target !== nodeId
            })
            if (this.selectedTopologyNodeId === nodeId) {
                this.selectedTopologyNodeId = null
            }
            this.saveTopologyToBlueprint()
        },

        addTopologyEdge(edgeData) {
            if (!edgeData) return
            const edgeId = edgeData.edge_id || `edge_${Date.now()}`
            const exists = (this.topologyBlueprint.edges || []).some(e => e.edge_id === edgeId)
            if (exists) return
            const dupRoute = (this.topologyBlueprint.edges || []).some(e =>
                e.source === edgeData.source &&
                e.target === edgeData.target &&
                (e.source_port || 'exit') === (edgeData.source_port || 'exit'))
            if (dupRoute) return
            const edge = {
                edge_id: edgeId,
                source: edgeData.source,
                target: edgeData.target,
                source_exit: edgeData.source_exit || 'default',
                source_port: edgeData.source_port || 'exit',
                label: edgeData.label || '',
                condition: edgeData.condition || null,
                action: edgeData.action || ''
            }
            this.topologyBlueprint.edges.push(edge)
            this.saveTopologyToBlueprint()
        },

        removeTopologyEdge(edgeId) {
            if (!edgeId) return
            this.topologyBlueprint.edges = (this.topologyBlueprint.edges || []).filter(e => e.edge_id !== edgeId)
            this.saveTopologyToBlueprint()
        }
    }
})
