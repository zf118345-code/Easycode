<template>
    <div class="node-editor-panel">
        <div v-if="store.selectedNode" class="editor-form">
            <div class="node-title">
                <span class="node-type-badge">{{ nodeTypeLabel }}</span>
                <span class="node-name">{{ store.selectedNode.node_name }}</span>
            </div>

            <el-divider content-position="left">参数配置</el-divider>
            <div class="params-container">
                <template v-for="(config, paramName) in allParams" :key="paramName">
                    <div class="param-item">
                        <ParamRenderer :key="paramName + store.currentTaskId"
                                       :config="config"
                                       :value="store.selectedNode.params[paramName]"
                                       :label="config.label || paramName"
                                       :context="store.selectedNode.params"
                                       @update="(val) => updateParam(paramName, val)" />
                    </div>
                </template>
            </div>

            <div class="save-actions">
                <el-button type="primary" size="small" @click="saveNode">保存参数</el-button>
            </div>
        </div>
        <div v-else class="empty">请从节点列表中选择一个节点</div>
    </div>
</template>

<script>
    import { useMainStore } from '@/stores'
    import { computed, watch, onBeforeUnmount, nextTick } from 'vue'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { ElMessage } from 'element-plus'

    const JUDGMENT_NODE_TYPES = ['image_recognition', 'branch']

    export default {
        name: 'NodeEditorPanel',
        components: { ParamRenderer },
        setup() {
            const store = useMainStore()

            const paramDefs = computed(() => {
                const node = store.selectedNode
                if (!node) return {}
                return store.params[node.node_type]?.params || {}
            })

            const nodeTypeLabel = computed(() => {
                const node = store.selectedNode
                if (!node) return ''
                return store.params[node.node_type]?.label || node.node_type
            })

            // 增强参数定义
            const allParams = computed(() => {
                // ===== 强制依赖 =====
                const _depNodes = store.nodes.length
                const _depVersion = store.taskNodesVersion

                console.log('🔄 [allParams] 重新计算，taskNodesVersion:', _depVersion, 'nodes.length:', _depNodes)

                const defs = paramDefs.value
                const result = {}
                for (const [key, config] of Object.entries(defs)) {
                    if (key === 'on_success' || key === 'on_failure') {
                        const sub = { ...config.sub }
                        if (sub.target_task) {
                            sub.target_task = {
                                ...sub.target_task,
                                options: (context, currentValue) => {
                                    const tasks = store.tasks || []
                                    console.log(`📋 [target_task] options 被调用，当前任务列表:`, tasks.map(t => t.task_name))
                                    return tasks.map(t => ({
                                        value: t.task_id,
                                        label: t.task_name || t.task_id
                                    }))
                                }
                            }
                        }
                        if (sub.target_node) {
                            sub.target_node = {
                                ...sub.target_node,
                                options: (context, currentValue) => {
                                    const jumpType = context?.jump_type || ''
                                    const targetTask = context?.target_task || ''
                                    const currentTaskId = store.currentTaskId
                                    console.log(`🔍 [target_node] options 被调用:`, {
                                        jumpType,
                                        targetTask,
                                        currentTaskId,
                                        context
                                    })

                                    let nodes = []
                                    if (jumpType === 'node') {
                                        nodes = store.nodes || []
                                        console.log(`📦 [target_node] 节点模式，使用 store.nodes (${nodes.length}个)`)
                                    } else if (jumpType === 'task') {
                                        if (targetTask === currentTaskId) {
                                            nodes = store.nodes || []
                                            console.log(`📦 [target_node] 任务模式且是当前任务，使用 store.nodes (${nodes.length}个)`)
                                        } else if (targetTask) {
                                            const cached = store.taskNodesCache?.[targetTask]
                                            if (cached && cached.length) {
                                                nodes = cached
                                                console.log(`📦 [target_node] 任务模式且是其他任务，从缓存读取 ${targetTask} (${nodes.length}个)`)
                                            } else {
                                                console.log(`⏳ [target_node] 缓存为空，触发加载任务 ${targetTask}`)
                                                nextTick(() => {
                                                    store.loadTaskNodes(targetTask)
                                                })
                                                return []
                                            }
                                        } else {
                                            console.log(`⚠️ [target_node] 任务模式但 target_task 为空`)
                                            return []
                                        }
                                    } else {
                                        console.log(`⚠️ [target_node] 未知 jumpType:`, jumpType)
                                        return []
                                    }

                                    const result = nodes.map((n, index) => ({
                                        value: n.node_id,
                                        label: `${index + 1}. ${n.node_name || n.node_id}`
                                    }))
                                    console.log(`✅ [target_node] 返回 ${result.length} 个选项`)
                                    return result
                                }
                            }
                        }
                        result[key] = { ...config, sub }
                    } else {
                        result[key] = config
                    }
                }
                return result
            })

            const updateParam = (paramName, value) => {
                const node = store.selectedNode
                if (!node) return
                console.log(`✏️ [updateParam] ${paramName} =`, value)
                node.params[paramName] = value
            }

            const updateJumpParam = async (jumpKey, subKey, value) => {
                const node = store.selectedNode
                if (!node) return
                if (!node.params[jumpKey]) {
                    node.params[jumpKey] = { jump_type: 'next', target_task: '', target_node: '' }
                }
                console.log(`🔄 [updateJumpParam] ${jumpKey}.${subKey} = ${value}`)
                node.params[jumpKey][subKey] = value

                if (subKey === 'jump_type') {
                    if (value === 'next' || value === 'end') {
                        node.params[jumpKey].target_task = ''
                        node.params[jumpKey].target_node = ''
                        console.log(`🧹 [updateJumpParam] 清空 target_task 和 target_node`)
                    }
                    if (value === 'node') {
                        node.params[jumpKey].target_task = ''
                        const currentNodes = store.nodes || []
                        if (currentNodes.length && !node.params[jumpKey].target_node) {
                            node.params[jumpKey].target_node = currentNodes[0].node_id
                            console.log(`👉 [updateJumpParam] node模式，自动选中第一个节点: ${currentNodes[0].node_name}`)
                        }
                    }
                    if (value === 'task') {
                        node.params[jumpKey].target_node = ''
                        const tasks = store.tasks || []
                        if (tasks.length && !node.params[jumpKey].target_task) {
                            node.params[jumpKey].target_task = tasks[0].task_id
                            console.log(`👉 [updateJumpParam] task模式，自动选中第一个任务: ${tasks[0].task_name}`)
                            await store.loadTaskNodes(tasks[0].task_id)
                            const nodes = store.taskNodesCache?.[tasks[0].task_id] || []
                            if (nodes.length) {
                                node.params[jumpKey].target_node = nodes[0].node_id
                                console.log(`👉 [updateJumpParam] task模式，自动选中第一个节点: ${nodes[0].node_name}`)
                            }
                        }
                    }
                }

                if (subKey === 'target_task' && value) {
                    node.params[jumpKey].target_node = ''
                    console.log(`🔄 [updateJumpParam] target_task 变化，清空 target_node`)
                    await store.loadTaskNodes(value)
                    const nodes = store.taskNodesCache?.[value] || []
                    if (nodes.length) {
                        node.params[jumpKey].target_node = nodes[0].node_id
                        console.log(`👉 [updateJumpParam] target_task 变化，自动选中第一个节点: ${nodes[0].node_name}`)
                    }
                }

                console.log(`📊 [updateJumpParam] 当前 ${jumpKey}:`, JSON.stringify(node.params[jumpKey]))
            }

            const saveNode = async () => {
                try {
                    await store.saveCurrentTask(true)
                    ElMessage.success('参数已保存')
                } catch (err) {
                    console.error('保存失败', err)
                    ElMessage.error('保存失败')
                }
            }

            // ===== 使用 watch 监听任务切换 =====
            watch(
                () => store.currentTaskId,
                async (newTaskId, oldTaskId) => {
                    console.log(`🔍 [watch currentTaskId] 从 ${oldTaskId} 切换到 ${newTaskId}`)

                    // 只有真正切换且 newTaskId 存在时才执行
                    if (newTaskId && oldTaskId && newTaskId !== oldTaskId) {
                        const node = store.selectedNode
                        if (node) {
                            console.log(`📌 [watch] 当前节点: ${node.node_name} (${node.node_id})`)
                            for (const jumpKey of ['on_success', 'on_failure']) {
                                const jumpData = node.params[jumpKey]
                                if (!jumpData) continue
                                console.log(`📌 [watch] ${jumpKey} 当前值:`, JSON.stringify(jumpData))

                                if (jumpData.jump_type === 'task') {
                                    if (jumpData.target_node) {
                                        console.log(`🧹 [watch] task模式，清空 target_node (旧值: ${jumpData.target_node})`)
                                        // 使用 nextTick 确保响应式更新完成
                                        await nextTick()
                                        node.params[jumpKey] = {
                                            ...jumpData,
                                            target_node: ''
                                        }
                                        console.log(`📊 [watch] 清空后值:`, JSON.stringify(node.params[jumpKey]))
                                    }
                                } else if (jumpData.jump_type === 'node') {
                                    const currentNodes = store.nodes || []
                                    if (currentNodes.length && !jumpData.target_node) {
                                        jumpData.target_node = currentNodes[0].node_id
                                        console.log(`👉 [watch] node模式，自动选中第一个节点: ${currentNodes[0].node_name}`)
                                    }
                                }
                            }
                        } else {
                            console.log(`⚠️ [watch] 没有选中的节点`)
                        }
                    } else {
                        console.log(`ℹ️ [watch] 无需清空 (newTaskId=${newTaskId}, oldTaskId=${oldTaskId})`)
                    }
                },
                { immediate: true }
            )

            // ===== 监听 region_type 变化 =====
            const unwatchRegionType = watch(
                () => store.selectedNode?.params?.region_type,
                async (newVal, oldVal) => {
                    const node = store.selectedNode
                    if (!node) return
                    if (newVal === 'recorded' && newVal !== oldVal) {
                        const templateName = node.params.image_source
                        if (!templateName) {
                            ElMessage.warning('请先选择模板图片')
                            return
                        }
                        try {
                            const regions = await store.getRegions()
                            if (regions[templateName]) {
                                node.params.region_value = regions[templateName]
                                node._originalRegionValue = [...regions[templateName]]
                            } else {
                                node.params.region_value = [0, 0, 0, 0]
                                node._originalRegionValue = [0, 0, 0, 0]
                                ElMessage.warning('未找到该图片的区域配置，将使用全屏匹配')
                            }
                        } catch (err) {
                            console.error('加载区域配置失败', err)
                        }
                    }
                }
            )

            const unwatchImageSource = watch(
                () => store.selectedNode?.params?.image_source,
                (newVal, oldVal) => {
                    if (newVal && newVal !== oldVal) {
                        const node = store.selectedNode
                        if (node?.params?.region_type === 'recorded') {
                            const currentType = node.params.region_type
                            node.params.region_type = 'fullwindow'
                            setTimeout(() => {
                                node.params.region_type = currentType
                            }, 50)
                        }
                    }
                }
            )

            const unwatchRegionValue = watch(
                () => store.selectedNode?.params?.region_value,
                (newVal, oldVal) => {
                    const node = store.selectedNode
                    if (!node) return
                    if (node.params.region_type === 'recorded' && node._originalRegionValue) {
                        if (JSON.stringify(newVal) !== JSON.stringify(node._originalRegionValue)) {
                            node.params.region_type = 'custom'
                            ElMessage.info('已切换到自定义模式')
                        }
                    }
                },
                { deep: true }
            )

            onBeforeUnmount(() => {
                unwatchRegionType()
                unwatchImageSource()
                unwatchRegionValue()
            })

            return {
                store,
                allParams,
                nodeTypeLabel,
                updateParam,
                updateJumpParam,
                saveNode
            }
        }
    }
</script>

<style scoped>
    .node-editor-panel {
        height: 100%;
        padding: 16px;
        overflow-y: auto;
    }

    .node-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
    }

    .node-type-badge {
        background: #409EFF;
        color: white;
        padding: 2px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }

    .node-name {
        color: #cfd3e6;
        font-size: 18px;
        font-weight: 600;
    }

    .params-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .param-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .jump-section {
        border-top: 1px solid #3d3d5a;
        padding-top: 12px;
        margin-top: 8px;
    }

    .jump-config {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding-left: 12px;
    }

    .save-actions {
        margin-top: 20px;
        display: flex;
        justify-content: flex-end;
    }

    .empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #8a8fa8;
    }
</style>