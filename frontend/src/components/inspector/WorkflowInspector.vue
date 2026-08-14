<!-- frontend/src/components/inspector/WorkflowInspector.vue -->
<template>
    <div class="workflow-inspector-embedded">
        <!-- 1. 单节点面板 -->
        <NodeInspectorPanel
v-if="targetType === 'node' && currentNode"
                            :node="currentNode"
                            @save="triggerSave" />

        <!-- 2. 多选批量编辑面板 -->
        <BatchInspectorPanel
v-else-if="targetType === 'batch' && selectedNodes.length > 1"
                             :nodes="selectedNodes"
                             @save="triggerSave" />

        <!-- 3. 任务组配置面板 -->
        <GroupInspectorPanel
v-else-if="targetType === 'group' && targetData"
                             :group="targetData"
                             @save="triggerSave" />

        <!-- 4. 空状态提示 -->
        <div v-else class="inspector-empty-tip">
            <span>👆 请在画布中点击节点或任务组以查看/编辑属性</span>
        </div>
    </div>
</template>

<script setup>
    import { ref, computed, watch } from 'vue'
    import { useMainStore } from '@/stores'
    import { blueprintApi } from '@/api/blueprintApi'
    import NodeInspectorPanel from './panels/NodeInspectorPanel.vue'
    import BatchInspectorPanel from './panels/BatchInspectorPanel.vue'
    import GroupInspectorPanel from './panels/GroupInspectorPanel.vue'

    const store = useMainStore()
    const currentNode = ref(null)
    const targetType = ref('node')
    const targetData = ref(null)

    const selectedNodes = computed(() => {
        const ids = store.selectedNodeIds || []
        const tasks = store.blueprint?.tasks || []
        let list = []
        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                if (ids.includes(n.node_id)) list.push(n)
            })
        })
        return list
    })

    watch(() => [store.selectedNodeIds, store.selectedGroupId], () => {
        const nodeIds = store.selectedNodeIds || []
        const tasks = store.blueprint?.tasks || []

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
        } else if (store.selectedGroupId) {
            targetType.value = 'group'
            const t = tasks.find((task, idx) => `group_${task.task_id || idx}` === store.selectedGroupId)
            if (t) {
                targetData.value = {
                    groupId: store.selectedGroupId,
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
                const tasks = store.blueprint?.tasks || []
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
            } else if (targetType.value === 'group' && targetData.value) {
                targetData.value.loopCount = Number(targetData.value.loopCount) || 1
                targetData.value.loopInterval = Number(targetData.value.loopInterval) || 0
                const groupTask = store.blueprint?.tasks?.find(t => t.task_id === targetData.value.taskId || `group_${t.task_id}` === targetData.value.groupId)
                if (groupTask) {
                    groupTask.task_name = targetData.value.groupName
                    groupTask.loop_count = targetData.value.loopCount
                    groupTask.loop_interval = targetData.value.loopInterval
                }
            }
            await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
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