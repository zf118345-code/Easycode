import { defineStore } from 'pinia'
import {
    fileNodeToFlat,
    flatNodeToFile,
    fileEdgeToFlat,
    flatEdgeToFile,
    topologyFlatToFile,
    pruneTopologyEdgesForNode
} from '@/utils/topologyModel'

// topology.json 文件结构为任务组形式 {tasks: [{..., nodes: [...]}], edges: [...]}
// 本 store 内部使用扁平结构（type/page_id/features/exits 位于顶层，连线用 source/target），
// 组件（TopologyCanvas/InspectorPanel 等）零改动；折叠/展开转换集中在 topologyModel.js。

export const useTopologyStore = defineStore('topology', {
    state: () => ({
        // 内部扁平结构（组件消费）：nodes 为扁平拓扑节点，edges 用 source/target
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
            if (topo && Array.isArray(topo.tasks)) {
                // 新结构：任务组 -> 展开为扁平节点
                const nodes = []
                for (const task of topo.tasks) {
                    for (const n of (task.nodes || [])) nodes.push(fileNodeToFlat(n))
                }
                this.topologyBlueprint = {
                    nodes,
                    edges: (topo.edges || []).map(fileEdgeToFlat)
                }
            } else if (topo && Array.isArray(topo.nodes)) {
                // 兼容旧内存合并视图 {nodes, edges}
                this.topologyBlueprint = {
                    nodes: topo.nodes.map(n => ({ ...n })),
                    edges: (topo.edges || []).map(e => ({ ...e }))
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
            // 输出 topology.json 文件结构 {tasks, edges}
            return topologyFlatToFile(this.topologyBlueprint)
        },

        async saveTopologyToBlueprint() {
            const { useProjectStore } = await import('./projectStore')
            const projectStore = useProjectStore()
            projectStore.blueprint.topology = this.syncTopologyToBlueprint()
            projectStore.saveTopologyDebounced()
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
        },

        removeTopologyEdgeByRoute(source, sourcePort) {
            // 按 源节点+端口 断开连线（拉线空放断线）
            if (!source) return false
            const before = (this.topologyBlueprint.edges || []).length
            this.topologyBlueprint.edges = (this.topologyBlueprint.edges || []).filter(e =>
                !(e.source === source && (e.source_port || 'exit') === (sourcePort || 'exit'))
            )
            if (this.topologyBlueprint.edges.length !== before) {
                this.saveTopologyToBlueprint()
                return true
            }
            return false
        },

        pruneEdgesForNode(nodeId, exitsLength) {
            // D3：exits 删除后修剪索引越界的 exit 连线
            const pruned = pruneTopologyEdgesForNode(this.topologyBlueprint.edges, nodeId, exitsLength)
            if (pruned.length !== (this.topologyBlueprint.edges || []).length) {
                this.topologyBlueprint.edges = pruned
                this.saveTopologyToBlueprint()
            }
        }
    }
})
