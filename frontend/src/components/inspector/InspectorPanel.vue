<template>
    <div class="workflow-inspector-embedded">
        <NodeInspectorPanel v-if="targetType === 'node' && currentNode" :node="currentNode" @save="commitActiveDraft" />
        <BatchInspectorPanel v-else-if="targetType === 'batch' && selectedNodes.length > 1" :nodes="selectedNodes" @save="saveCurrentGraph" />
        <div v-else class="inspector-empty-tip">
            <MousePointerClick :size="16" />
            <span>选择一个节点查看属性；区块名称和范围直接在画布中编辑。</span>
        </div>
    </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { MousePointerClick } from 'lucide-vue-next'
import { useIdeStore, useUiStore } from '@/stores'
import BatchInspectorPanel from './panels/BatchInspectorPanel.vue'
import NodeInspectorPanel from './panels/NodeInspectorPanel.vue'

const store = useIdeStore()
const uiStore = useUiStore()
const currentNode = ref(null)
const currentGraphMode = ref('workflow')
const targetType = ref('none')
let hydratingDraft = false
const clone = value => JSON.parse(JSON.stringify(value))

const workflowGraphs = computed(() => [
    store.blueprint?.main_graph,
    ...(store.blueprint?.functions || []).map(item => item.graph)
].filter(Boolean))
const graphsForMode = mode => mode === 'topology' ? [store.blueprint?.page_map].filter(Boolean) : workflowGraphs.value
const activeGraph = computed(() => {
    if (store.canvasMode === 'topology') return store.blueprint?.page_map || null
    if (store.currentTaskId === 'main') return store.blueprint?.main_graph || null
    return (store.blueprint?.functions || []).find(item => item.function_id === store.currentTaskId)?.graph || store.blueprint?.main_graph || null
})
const selectedNodes = computed(() => {
    const ids = new Set(uiStore.selectedNodeIds || [])
    return (activeGraph.value?.nodes || []).filter(node => ids.has(node.node_id))
})

const saveCurrentGraph = () => store.canvasMode === 'topology' ? store.saveTopologyDebounced() : store.saveWorkflowDebounced()

function commitNodeDraft(draft = currentNode.value) {
    if (hydratingDraft || !draft?.node_id) return false
    for (const graph of graphsForMode(currentGraphMode.value)) {
        const index = (graph.nodes || []).findIndex(node => node.node_id === draft.node_id)
        if (index < 0) continue
        const next = clone(draft)
        next.loop_count = Math.max(1, Number(next.loop_count) || 1)
        next.delay_before = Math.max(0, Number(next.delay_before) || 0)
        graph.nodes.splice(index, 1, next)
        currentGraphMode.value === 'topology' ? store.saveTopologyDebounced() : store.saveWorkflowDebounced()
        return true
    }
    return false
}
const commitActiveDraft = () => targetType.value === 'node' && currentNode.value ? commitNodeDraft() : undefined

watch(() => [store.canvasMode, store.currentTaskId, [...(uiStore.selectedNodeIds || [])], uiStore.inspectorSyncTick], () => {
    commitActiveDraft()
    hydratingDraft = true
    const ids = uiStore.selectedNodeIds || []
    currentNode.value = null
    if (ids.length > 1) {
        targetType.value = 'batch'
    } else if (ids.length === 1) {
        const found = (activeGraph.value?.nodes || []).find(node => node.node_id === ids[0])
        if (found) {
            currentNode.value = clone(found)
            currentNode.value.params ||= {}
            currentGraphMode.value = store.canvasMode
            targetType.value = 'node'
        } else targetType.value = 'none'
    } else targetType.value = 'none'
    hydratingDraft = false
}, { immediate: true, deep: false, flush: 'sync' })

watch(currentNode, value => {
    if (!hydratingDraft && targetType.value === 'node' && value) commitNodeDraft(value)
}, { deep: true, flush: 'sync' })

onBeforeUnmount(commitActiveDraft)
</script>

<style scoped>
.workflow-inspector-embedded{width:100%;height:100%;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box;background:var(--app-panel-bg);user-select:none}.inspector-empty-tip{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:24px;text-align:center;font-size:11px;line-height:1.55;color:var(--el-text-color-placeholder)}
</style>
