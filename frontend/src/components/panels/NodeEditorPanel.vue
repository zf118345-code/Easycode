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
                                       @update="(val) => handleParamUpdate(paramName, val)" />
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
    import { computed, watch, nextTick, ref } from 'vue'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { ElMessage } from 'element-plus'
    import { logger } from '@/utils/logger'
    import axios from 'axios'

    export default {
        name: 'NodeEditorPanel',
        components: { ParamRenderer },
        setup() {
            const store = useMainStore()
            const originalRecordedRegion = ref(null)

            let isSyncingRecorded = false

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

            const allParams = computed(() => {
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

                                    let nodes = []
                                    if (jumpType === 'node') {
                                        nodes = store.nodes || []
                                    } else if (jumpType === 'task') {
                                        if (targetTask === currentTaskId) {
                                            nodes = store.nodes || []
                                        } else if (targetTask) {
                                            const cached = store.taskNodesCache?.[targetTask]
                                            if (cached && cached.length) {
                                                nodes = cached
                                            } else {
                                                nextTick(() => { store.loadTaskNodes(targetTask) })
                                                return []
                                            }
                                        } else {
                                            return []
                                        }
                                    } else {
                                        return []
                                    }

                                    return nodes.map((n, index) => ({
                                        value: n.node_id,
                                        label: `${index + 1}. ${n.node_name || n.node_id}`
                                    }))
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

            const handleParamUpdate = (paramName, value) => {
                if (paramName === 'on_success' || paramName === 'on_failure') {
                    const node = store.selectedNode
                    if (!node) return
                    const oldObj = node.params[paramName] || {}
                    const newObj = value || {}

                    if (oldObj.jump_type !== newObj.jump_type) {
                        updateJumpParam(paramName, 'jump_type', newObj.jump_type)
                    } else if (oldObj.target_task !== newObj.target_task) {
                        updateJumpParam(paramName, 'target_task', newObj.target_task)
                    } else if (oldObj.target_node !== newObj.target_node) {
                        updateJumpParam(paramName, 'target_node', newObj.target_node)
                    } else {
                        node.params[paramName] = value
                    }
                } else {
                    updateParam(paramName, value)
                }
            }

            const updateParam = (paramName, value) => {
                const node = store.selectedNode
                if (!node) return

                if (paramName === 'region_value' && node.params.region_type === 'recorded' && !isSyncingRecorded) {
                    if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
                        node.params.region_type = 'custom'
                        ElMessage.info('检测到坐标手动微调，已自动切换为【自定义区域】模式')
                    }
                }

                node.params[paramName] = value

                if (paramName === 'region_type' && value === 'recorded') {
                    syncRecordedRegion()
                }

                if (paramName === 'image_source' && node.params.region_type === 'recorded') {
                    syncRecordedRegion()
                }
            }

            const syncRecordedRegion = async () => {
                const node = store.selectedNode
                if (!node || !store.currentProjectPath) return

                const rawTemplateName = node.params.image_source
                if (!rawTemplateName) {
                    ElMessage.warning('请先选择模板图片')
                    return
                }

                isSyncingRecorded = true

                try {
                    const res = await axios.get('/api/regions', {
                        params: { project_path: store.currentProjectPath }
                    })
                    const regions = res.data || {}

                    const cleanName = rawTemplateName.replace(/\.png$/i, '')
                    const fileNameOnly = cleanName.split(/[\\/]/).pop()

                    const rect = regions[rawTemplateName] ||
                        regions[cleanName] ||
                        regions[fileNameOnly] ||
                        regions[`${fileNameOnly}.png`]

                    if (rect && Array.isArray(rect) && rect.length === 4) {
                        node.params.region_value = [...rect]
                        originalRecordedRegion.value = [...rect]
                        logger.info('NodeEditor', `✅ 成功回填录入坐标: [${rect}]`)
                    } else {
                        node.params.region_value = [0, 0, 0, 0]
                        originalRecordedRegion.value = [0, 0, 0, 0]
                        ElMessage.warning(`未在 regions.json 中查找到图片 [${fileNameOnly}] 的坐标`)
                    }
                } catch (err) {
                    logger.error('NodeEditor', '获取区域配置失败:', err)
                } finally {
                    setTimeout(() => { isSyncingRecorded = false }, 300)
                }
            }

            // ⭐ 核心优化：智能计算默认选中节点与目标任务联动逻辑
            const updateJumpParam = async (jumpKey, subKey, value) => {
                const node = store.selectedNode
                if (!node) return

                if (!node.params[jumpKey]) {
                    node.params[jumpKey] = { jump_type: 'next', target_task: '', target_node: '' }
                }

                const jumpObj = { ...node.params[jumpKey] }
                jumpObj[subKey] = value

                // 1. 当切换【跳转类型 (jump_type)】时
                if (subKey === 'jump_type') {
                    if (value === 'next' || value === 'end') {
                        jumpObj.target_task = ''
                        jumpObj.target_node = ''
                    }
                    // 切换为跳转节点 (node) 时：默认选中物理下一个节点，没有则是空
                    else if (value === 'node') {
                        jumpObj.target_task = ''
                        const currentNodes = store.nodes || []
                        const currentIndex = currentNodes.findIndex(n => n.node_id === node.node_id)

                        if (currentIndex !== -1 && currentIndex + 1 < currentNodes.length) {
                            jumpObj.target_node = currentNodes[currentIndex + 1].node_id
                        } else {
                            jumpObj.target_node = ''
                        }
                    }
                    // 切换为跳转任务 (task) 时：默认选中当前任务，并联动该任务的第一个节点
                    else if (value === 'task') {
                        const targetTaskId = store.currentTaskId || ''
                        jumpObj.target_task = targetTaskId

                        if (targetTaskId) {
                            const taskNodes = await store.loadTaskNodes(targetTaskId)
                            jumpObj.target_node = (taskNodes && taskNodes.length > 0) ? taskNodes[0].node_id : ''
                        } else {
                            jumpObj.target_node = ''
                        }
                    }
                }

                // 2. 当切换【目标任务 (target_task)】时：强行重置 target_node，清除旧任务的脏节点 ID，默认选中新任务的第一个节点
                if (subKey === 'target_task' && jumpObj.jump_type === 'task') {
                    if (value) {
                        const taskNodes = await store.loadTaskNodes(value)
                        jumpObj.target_node = (taskNodes && taskNodes.length > 0) ? taskNodes[0].node_id : ''
                    } else {
                        jumpObj.target_node = ''
                    }
                }

                node.params[jumpKey] = JSON.parse(JSON.stringify(jumpObj))
            }

            watch(
                () => store.selectedNodeId,
                () => {
                    const node = store.selectedNode
                    if (node && node.params?.region_type === 'recorded') {
                        syncRecordedRegion()
                    }
                },
                { immediate: true }
            )

            const saveNode = async () => {
                try {
                    await store.saveCurrentTask(true)
                    ElMessage.success('参数已保存')
                } catch (err) {
                    ElMessage.error('保存失败')
                }
            }

            return {
                store,
                allParams,
                nodeTypeLabel,
                handleParamUpdate,
                updateParam,
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