<!-- frontend/src/components/inspector/InspectorPanel.vue
  统一属性检查器：workflow 与 topology 共用一套逻辑。
  监听 uiStore 选中状态，从「当前画布数据源」（blueprint.workflow / blueprint.topology）读取节点编辑，
  保存时写回同一数据源（两数据源结构同构，节点页面数据内嵌 params）。
-->
<template>
    <div class="workflow-inspector-embedded">
        <NodeInspectorPanel
            v-if="targetType === 'node' && currentNode"
            :node="currentNode"
            @save="triggerSave" />

        <BatchInspectorPanel
            v-else-if="targetType === 'batch' && selectedNodes.length > 1"
            :nodes="selectedNodes"
            @save="triggerSave" />

        <GroupInspectorPanel
            v-else-if="targetType === 'group' && targetData"
            :group="targetData"
            mode="workflow"
            @save="triggerSave" />

        <div v-else class="inspector-empty-tip">
            <span><MousePointerClick :size="14" style="vertical-align: middle;" /> 请在画布中点击节点或任务组以查看/编辑属性</span>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch } from 'vue'
    import { useMainStore, useUiStore } from '@/stores'
    import { MousePointerClick } from 'lucide-vue-next'
    import { pruneTopologyEdgesForNode } from '@/utils/topologyModel'
    import NodeInspectorPanel from './panels/NodeInspectorPanel.vue'
    import BatchInspectorPanel from './panels/BatchInspectorPanel.vue'
    import GroupInspectorPanel from './panels/GroupInspectorPanel.vue'

    const store = useMainStore()
    const uiStore = useUiStore()

    const isTopology = computed(() => store.canvasMode === 'topology')

    // 当前画布数据源（两 Tab 同构 {tasks, edges}）
    const canvasData = computed(() => (
        isTopology.value
            ? { tasks: store.blueprint?.topology?.tasks || [], edges: store.blueprint?.topology?.edges || [] }
            : { tasks: store.blueprint?.tasks || [], edges: store.blueprint?.edges || [] }
    ))

    const currentNode = ref(null)
    const targetType = ref('node')
    const targetData = ref(null)

    const selectedNodes = computed(() => {
        const ids = uiStore.selectedNodeIds || []
        const tasks = canvasData.value.tasks || []
        let list = []
        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                if (ids.includes(n.node_id)) list.push(n)
            })
        })
        return list
    })

    watch(() => [uiStore.selectedNodeIds, uiStore.selectedGroupId], () => {
        const nodeIds = uiStore.selectedNodeIds || []
        const tasks = canvasData.value.tasks || []

        if (nodeIds.length > 1) {
            targetType.value = 'batch'
            targetData.value = null
            currentNode.value = null
        } else if (nodeIds.length === 1) {
            targetType.value = 'node'
            let foundNode = null
            for (const task of tasks) {
                const n = (task.nodes || []).find(item => item.node_id === nodeIds[0])
                if (n) { foundNode = n; break }
            }
            if (foundNode) {
                const nodeCopy = JSON.parse(JSON.stringify(foundNode))
                if (!nodeCopy.params) nodeCopy.params = {}
                currentNode.value = nodeCopy
            }
        } else if (uiStore.selectedGroupId) {
            targetType.value = 'group'
            const t = tasks.find((task, idx) => `group_${task.task_id || idx}` === uiStore.selectedGroupId)
            if (t) {
                targetData.value = {
                    groupId: uiStore.selectedGroupId,
                    taskId: t.task_id,
                    groupName: t.task_name,
                    loopCount: t.loop_count || 1,
                    loopInterval: t.loop_interval || 0
                }
                currentNode.value = null
            }
        } else {
            targetType.value = 'node'
            currentNode.value = null
            targetData.value = null
        }
    }, { immediate: true, deep: true })

    const triggerSave = async () => {
        try {
            if (targetType.value === 'node' && currentNode.value) {
                const tasks = canvasData.value.tasks || []
                for (const task of tasks) {
                    if (task.nodes) {
                        const idx = task.nodes.findIndex(n => n.node_id === currentNode.value.node_id)
                        if (idx > -1) {
                            currentNode.value.loop_count = Number(currentNode.value.loop_count) || 1
                            currentNode.value.delay_before = Number(currentNode.value.delay_before) || 0
                            task.nodes[idx] = JSON.parse(JSON.stringify(currentNode.value))
                            break
                        }
                    }
                }
                // 页面状态节点：exits 删除后修剪索引越界的 exit 连线
                if (isTopology.value && currentNode.value.node_type === 'page_state') {
                    const exitsLength = (currentNode.value.params?.exits || []).length
                    const edges = canvasData.value.edges || []
                    const pruned = pruneTopologyEdgesForNode(edges, currentNode.value.node_id, exitsLength)
                    if (pruned.length !== edges.length) {
                        if (isTopology.value) {
                            store.blueprint.topology = { ...store.blueprint.topology, edges: pruned }
                        } else {
                            store.blueprint.edges = pruned
                        }
                    }
                }
            } else if (targetType.value === 'group' && targetData.value) {
                targetData.value.loopCount = Number(targetData.value.loopCount) || 1
                targetData.value.loopInterval = Number(targetData.value.loopInterval) || 0
                const groupTask = (canvasData.value.tasks || []).find(t =>
                    t.task_id === targetData.value.taskId || `group_${t.task_id}` === targetData.value.groupId)
                if (groupTask) {
                    groupTask.task_name = targetData.value.groupName
                    groupTask.loop_count = targetData.value.loopCount
                    groupTask.loop_interval = targetData.value.loopInterval
                }
            }
            if (isTopology.value) {
                await store.saveTopologyData()
            } else {
                await store.saveWorkflowImmediately()
            }
        } catch (err) {
            console.error('保存节点配置失败:', err)
        }
    }
</script>

<style scoped>
    .workflow-inspector-embedded {
        width: 100%;
        height: 100%;
        background: rgba(38, 40, 61, 0.95);
        display: flex;
        flex-direction: column;
        user-select: none;
        overflow: hidden;
        box-sizing: border-box;
    }

    .inspector-empty-tip {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        text-align: center;
        font-size: 12px;
        color: var(--el-text-color-placeholder);
    }
</style>
