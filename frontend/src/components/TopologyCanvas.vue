<!-- frontend/src/components/TopologyCanvas.vue
  拓扑画布薄包装（Step 3）：数据来自 projectStore.topologyData（文件结构），
  事件处理经 topologyStore mutate + 防抖保存，撤销重做基于扁平拓扑数据快照。
-->
<template>
    <CanvasView
        mode="topology"
        :tasks="topologyData.tasks"
        :edges="topologyData.edges"
        :available-node-types="availableNodeTypes"
        :has-groups="false"
        :has-breakpoints="false"
        :on-save="handleSave"
        :on-delete="handleDelete"
        :on-select-all="handleSelectAll"
        :on-undo="undoRedo.undo"
        :on-redo="undoRedo.redo"
        @update-node-positions="handleNodePositions"
        @add-edge="handleAddEdge"
        @remove-edge="handleRemoveEdge"
        @create-node="handleCreateNode"
        @delete-node="handleDeleteNode" />
</template>

<script setup>
    import { computed, onMounted } from 'vue'
    import { useMainStore, useTopologyStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { createCanvasUndoRedo } from '@/composables/useUndoRedo'
    import CanvasView from '@/components/canvas/CanvasView.vue'

    const store = useMainStore()
    const topoStore = useTopologyStore()

    const availableNodeTypes = {
        page_state: '页面状态',
        smart_jump: '智能跳转',
        click: '点击动作',
        wait: '等待动作',
        image_recognition: '图像识别',
        ocr_recognition: 'OCR 识别'
    }

    const topologyData = computed(() => store.topologyData)

    const undoRedo = createCanvasUndoRedo('topology')

    // ===== 事件处理（mutate topologyStore + 防抖保存） =====

    function handleNodePositions(positions) {
        if (!positions || !positions.length) return
        undoRedo.commit()
        for (const p of positions) {
            if (p.node_id && p.position) {
                topoStore.updateTopologyNode(p.node_id, { position: p.position })
            }
        }
    }

    function handleAddEdge(payload) {
        undoRedo.commit()
        topoStore.addTopologyEdge({
            source: payload.source,
            target: payload.target,
            source_port: payload.source_port === 'succ' ? 'success' : payload.source_port === 'fail' ? 'failure' : payload.source_port,
            edge_id: `e_${payload.source}_${payload.source_port}_${payload.target}`
        })
    }

    function handleRemoveEdge(edge) {
        if (!edge) return
        undoRedo.commit()
        if (edge.edge_id) {
            topoStore.removeTopologyEdge(edge.edge_id)
        } else if (edge.sourceNodeId) {
            topoStore.removeTopologyEdgeByRoute(edge.sourceNodeId, edge.legacyPort)
        }
    }

    function handleCreateNode(payload) {
        undoRedo.commit()
        topoStore.addTopologyNode({
            node_id: payload.nodeId,
            type: payload.type,
            node_name: availableNodeTypes[payload.type] || payload.type,
            position: payload.position || { x: 0, y: 0 }
        })
        if (payload.sourceNodeId) {
            topoStore.addTopologyEdge({
                source: payload.sourceNodeId,
                target: payload.nodeId,
                source_port: payload.portType === 'succ' ? 'success' : payload.portType === 'fail' ? 'failure' : payload.portType,
                edge_id: `e_${payload.sourceNodeId}_${payload.portType}_${payload.nodeId}`
            })
        }
    }

    function handleDeleteNode(payload) {
        undoRedo.commit()
        topoStore.removeTopologyNode(payload?.nodeId)
    }

    async function handleSave() {
        await store.saveBlueprintImmediately()
        ElMessage.success('蓝图已保存')
    }

    function handleDelete() {
        // 拓扑模式：删除当前选中的拓扑节点
        if (topoStore.selectedTopologyNodeId) {
            undoRedo.commit()
            topoStore.removeTopologyNode(topoStore.selectedTopologyNodeId)
        } else {
            ElMessage.warning('请先选中要删除的节点')
        }
    }

    function handleSelectAll() {
        // 拓扑模式暂不支持多选：选中第一个节点
        const first = (topoStore.topologyNodes || [])[0]
        if (first) {
            topoStore.selectTopologyNode(first.node_id)
            ElMessage.info('拓扑模式暂不支持多选，已选中第一个节点')
        }
    }

    onMounted(() => {
        if (!topoStore.topologyNodes.length) {
            topoStore.loadTopologyFromBlueprint()
        }
    })
</script>
