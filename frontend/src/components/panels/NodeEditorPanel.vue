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

            // 动态增强参数定义
            const allParams = computed(() => {
                const _depNodes = store.nodes.length
                const _depVersion = store.taskNodesVersion

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
                                                nextTick(() => {
                                                    store.loadTaskNodes(targetTask)
                                                })
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

            const getNextNodeId = (currentNodes, currentNodeId) => {
                if (!currentNodes || !currentNodes.length) return ''
                const currentIndex = currentNodes.findIndex(n => n.node_id === currentNodeId)
                if (currentIndex !== -1 && currentIndex + 1 < currentNodes.length) {
                    return currentNodes[currentIndex + 1].node_id
                }
                return currentNodes[0].node_id
            }

            // ⭐ 核心路由分发函数（修复入口）
            const handleParamUpdate = (paramName, value) => {
                if (paramName === 'on_success' || paramName === 'on_failure') {
                    // 当更新跳转配置时，对比新旧对象，分析是哪一个子属性发生了变化
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
                        // 其他子属性兜底更新
                        node.params[paramName] = value
                    }
                } else {
                    // 普通参数正常更新
                    updateParam(paramName, value)
                }
            }

            const updateParam = (paramName, value) => {
                const node = store.selectedNode
                if (!node) return
                node.params[paramName] = value
            }

            // ⭐ 智能化逻辑干事核心函数
            const updateJumpParam = async (jumpKey, subKey, value) => {
                const node = store.selectedNode
                if (!node) return

                if (!node.params[jumpKey]) {
                    node.params[jumpKey] = { jump_type: 'next', target_task: '', target_node: '' }
                }

                const jumpObj = { ...node.params[jumpKey] }
                console.group(`🚀 [智能更新执行] ${jumpKey}.${subKey} => ${value}`)

                jumpObj[subKey] = value
                const currentNodes = store.nodes || []

                // 1. 切换跳转类型
                if (subKey === 'jump_type') {
                    if (value === 'next' || value === 'end') {
                        jumpObj.target_task = ''
                        jumpObj.target_node = ''
                    }
                    if (value === 'node') {
                        jumpObj.target_task = ''
                        jumpObj.target_node = getNextNodeId(currentNodes, node.node_id)
                    }
                    if (value === 'task') {
                        if (!jumpObj.target_task) {
                            jumpObj.target_task = store.currentTaskId
                        }
                        jumpObj.target_node = getNextNodeId(currentNodes, node.node_id)
                        if (jumpObj.target_task !== store.currentTaskId) {
                            await store.loadTaskNodes(jumpObj.target_task)
                        }
                    }
                }

                // 2. 切换目标任务
                if (subKey === 'target_task' && value) {
                    let targetNodes = []
                    if (value === store.currentTaskId) {
                        targetNodes = currentNodes
                    } else {
                        await store.loadTaskNodes(value)
                        targetNodes = store.taskNodesCache?.[value] || []
                    }

                    const oldTargetNode = jumpObj.target_node
                    const exists = targetNodes.some(n => n.node_id === oldTargetNode)

                    if (!exists) {
                        // 旧节点在新的任务中不存在 -> 自动重置为新任务的第一个节点！
                        const newFirstNodeId = targetNodes.length > 0 ? targetNodes[0].node_id : ''
                        console.log(`🎯 [旧节点不在新任务中，自动校正 target_node] =>`, newFirstNodeId)
                        jumpObj.target_node = newFirstNodeId
                    } else {
                        console.log(`✅ 旧节点在新任务中依然有效，保留:`, oldTargetNode)
                    }
                }

                // 深度克隆赋值，强行通知 Vue 响应式依赖
                node.params[jumpKey] = JSON.parse(JSON.stringify(jumpObj))
                console.log(`干事后结果:`, node.params[jumpKey])
                console.groupEnd()
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

            return {
                store,
                allParams,
                nodeTypeLabel,
                handleParamUpdate,
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