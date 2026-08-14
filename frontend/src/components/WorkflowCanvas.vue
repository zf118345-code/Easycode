<!-- frontend/src/components/WorkflowCanvas.vue
  流程画布薄包装（Step 3）：数据来自 projectStore.workflowData，事件处理 mutate store 并保存，
  撤销重做基于 workflowData 快照。
-->
<template>
    <CanvasView
        mode="workflow"
        :tasks="workflowData.tasks"
        :edges="workflowData.edges"
        :available-node-types="availableNodeTypes"
        :has-groups="true"
        :has-breakpoints="true"
        :on-save="handleSave"
        :on-delete="handleDelete"
        :on-select-all="handleSelectAll"
        :on-undo="undoRedo.undo"
        :on-redo="undoRedo.redo"
        @update-tasks="handleUpdateTasks"
        @add-edge="handleAddEdge"
        @remove-edge="handleRemoveEdge"
        @create-node="handleCreateNode"
        @delete-node="handleDeleteNode"
        @create-group="handleCreateGroup"
        @delete-group="handleDeleteGroup" />
</template>

<script setup>
    import { computed, onMounted } from 'vue'
    import { useMainStore, useUiStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { blueprintApi } from '@/api/blueprintApi'
    import { createCanvasUndoRedo } from '@/composables/useUndoRedo'
    import {
        applyWorkflowEdge,
        removeWorkflowEdge,
        disconnectWorkflowPort,
        removeWorkflowNode
    } from '@/utils/workflowEdgeModel'
    import CanvasView from '@/components/canvas/CanvasView.vue'

    const store = useMainStore()
    const uiStore = useUiStore()

    const availableNodeTypes = {
        click: '鼠标点击',
        wait: '等待',
        image_recognition: '图像识别',
        ocr_recognition: '文字识别 (OCR)',
        branch: '分支选择',
        logic_check: '逻辑判断',
        variable_op: '变量操作',
        log: '日志输出',
        script_call: '调用脚本',
        smart_jump: '智能跳转'
    }

    const workflowData = computed(() => store.workflowData)

    const undoRedo = createCanvasUndoRedo('workflow')

    async function handleUpdateTasks(tasks) {
        undoRedo.commit()
        store.blueprint.tasks = JSON.parse(JSON.stringify(tasks || []))
        await store.saveWorkflowImmediately()
    }

    async function handleAddEdge(payload) {
        undoRedo.commit()
        applyWorkflowEdge(store.blueprint.tasks, payload)
        await store.saveWorkflowImmediately()
    }

    async function handleRemoveEdge(edge) {
        if (!edge || !edge.sourceNodeId) return
        undoRedo.commit()
        const removed = removeWorkflowEdge(store.blueprint.tasks, edge) ||
            disconnectWorkflowPort(store.blueprint.tasks, edge.sourceNodeId, edge.legacyPort)
        if (removed) {
            await store.saveWorkflowImmediately()
        }
    }

    async function handleCreateNode(payload) {
        undoRedo.commit()
        const tasks = store.blueprint.tasks || []
        let targetTask = null
        let sourceNodeObj = null

        if (payload.sourceNodeId) {
            for (const t of tasks) {
                const found = (t.nodes || []).find(n => n.node_id === payload.sourceNodeId)
                if (found) { targetTask = t; sourceNodeObj = found; break }
            }
        } else if (payload.groupId) {
            targetTask = tasks.find(t => t.task_id === payload.groupId)
        }

        if (!targetTask) {
            const newTaskId = `task_${Date.now()}`
            targetTask = {
                task_id: newTaskId,
                task_name: '新建组',
                loop_count: 1,
                loop_interval: 0,
                nodes: []
            }
            tasks.push(targetTask)
        }

        if (!targetTask.nodes) targetTask.nodes = []

        const chineseLabel = (availableNodeTypes[payload.type] || payload.type).replace(/^[^\u4e00-\u9fa5]+/, '').trim()
        const sameTypeCount = targetTask.nodes.filter(n => n.node_type === payload.type).length + 1
        const newNode = {
            node_id: payload.nodeId,
            node_name: `${chineseLabel}_${sameTypeCount}`,
            node_type: payload.type,
            params: {},
            delay_before: 200,
            loop_count: 1,
            position: payload.position || { x: 0, y: 0 }
        }

        if (sourceNodeObj) {
            applyWorkflowEdge(tasks, { source: payload.sourceNodeId, target: payload.nodeId, source_port: payload.portType })
        }

        targetTask.nodes.push(newNode)
        store.blueprint.tasks = tasks
        await store.saveWorkflowImmediately()
    }

    async function handleDeleteNode(payload) {
        undoRedo.commit()
        store.blueprint.tasks = removeWorkflowNode(store.blueprint.tasks, payload?.nodeId)
        await store.saveWorkflowImmediately()
    }

    async function handleCreateGroup(payload) {
        await blueprintApi.createTask(store.currentProjectPath, { task_name: payload.name, nodes: [] })
        await store.loadProjectData()
    }

    async function handleDeleteGroup(payload) {
        await blueprintApi.deleteTask(payload.taskId, store.currentProjectPath)
        await store.loadProjectData()
    }

    async function handleSave() {
        await store.saveBlueprintImmediately()
        ElMessage.success('蓝图已保存')
    }

    function handleDelete() {
        uiStore.batchDeleteNodes()
    }

    function handleSelectAll() {
        uiStore.selectAllNodes()
    }

    onMounted(async () => {
        if (store.currentProjectPath) {
            await store.loadProjectData()
        }
    })
</script>
