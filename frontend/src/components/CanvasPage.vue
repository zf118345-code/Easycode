<!-- frontend/src/components/CanvasPage.vue
  唯一画布页面（业务流程与页面拓扑完全共用一个页面/一套逻辑）：
  - 画布渲染/交互（节点卡片、连线、端口、拖拽、碰撞、组、断点、缩放、快捷键）全部复用 CanvasView
  - 「模式」只存在于数据读写层：canvasMode 决定读取哪个 JSON（workflow.json / topology.json）
    与显示哪些节点类型（nodeRegistry 白名单）；两数据源结构完全同构（{tasks, edges}）
-->
<template>
    <CanvasView
        :mode="canvasMode"
        :tasks="canvasData.tasks"
        :edges="canvasData.edges"
        :available-node-types="availableNodeTypes"
        :has-groups="true"
        :has-breakpoints="true"
        :on-save="handleSave"
        :on-delete="handleDelete"
        :on-select-all="handleSelectAll"
        :on-undo="activeUndoRedo.undo"
        :on-redo="activeUndoRedo.redo"
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
    import { createCanvasUndoRedo } from '@/composables/useUndoRedo'
    import { getNodeTypesForMode } from '@/config/nodeRegistry'
    import {
        applyEdge,
        removeEdge,
        disconnectPort,
        removeNode
    } from '@/utils/workflowEdgeModel'
    import CanvasView from '@/components/canvas/CanvasView.vue'

    const store = useMainStore()
    const uiStore = useUiStore()

    const canvasMode = computed(() => store.canvasMode || 'workflow')
    const isTopology = computed(() => canvasMode.value === 'topology')

    // 节点可用类型：modes/label 来自后端 /api/params 配置（单一数据源），前端表兜底
    const availableNodeTypes = computed(() => getNodeTypesForMode(canvasMode.value, store.paramsDefinitions))

    // ===== 当前数据源（唯一模式判断点 1：读取哪个 JSON） =====
    const canvasData = computed(() => (
        isTopology.value ? store.topologyData : store.workflowData
    ))

    const canvasName = computed(() => (isTopology.value ? 'topology' : 'workflow'))

    // 撤销重做：快照结构同构 {tasks, edges}，仅数据键不同，各持一个实例避免跨 Tab 撤销
    const workflowUndoRedo = createCanvasUndoRedo('workflow')
    const topologyUndoRedo = createCanvasUndoRedo('topology')
    const activeUndoRedo = computed(() => (isTopology.value ? topologyUndoRedo : workflowUndoRedo))

    // ===== 保存路由（唯一模式判断点 2：写入哪个 JSON） =====
    async function saveCanvas() {
        if (isTopology.value) {
            await store.saveTopologyData()
        } else {
            await store.saveWorkflowImmediately()
        }
    }

    // ===== 节点/组结构更新（两 Tab 同一套逻辑，操作当前数据源） =====

    async function handleUpdateTasks(tasks) {
        activeUndoRedo.value.commit()
        if (isTopology.value) {
            store.blueprint.topology = {
                tasks: JSON.parse(JSON.stringify(tasks || [])),
                edges: store.blueprint.topology?.edges || []
            }
        } else {
            store.blueprint.tasks = JSON.parse(JSON.stringify(tasks || []))
        }
        await saveCanvas()
    }

    async function handleAddEdge(payload) {
        activeUndoRedo.value.commit()
        const edges = canvasData.value.edges
        applyEdge(edges, { ...payload, canvas: canvasName.value })
        await saveCanvas()
    }

    async function handleRemoveEdge(edge) {
        if (!edge || !edge.sourceNodeId) return
        activeUndoRedo.value.commit()
        const edges = canvasData.value.edges
        const removed = removeEdge(edges, edge) || disconnectPort(edges, edge.sourceNodeId, edge.legacyPort)
        if (removed) {
            await saveCanvas()
        }
    }

    async function handleCreateNode(payload) {
        activeUndoRedo.value.commit()
        const tasks = canvasData.value.tasks
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

        const chineseLabel = (availableNodeTypes.value[payload.type] || payload.type).replace(/^[^\u4e00-\u9fa5]+/, '').trim()
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
            applyEdge(canvasData.value.edges, {
                source: payload.sourceNodeId,
                target: payload.nodeId,
                source_port: payload.portType,
                canvas: canvasName.value
            })
        }

        targetTask.nodes.push(newNode)
        await saveCanvas()
    }

    async function handleDeleteNode(payload) {
        activeUndoRedo.value.commit()
        const tasks = canvasData.value.tasks
        const edges = canvasData.value.edges
        const nextTasks = removeNode(tasks, edges, payload?.nodeId)
        if (isTopology.value) {
            store.blueprint.topology = { tasks: nextTasks, edges }
        } else {
            store.blueprint.tasks = nextTasks
        }
        uiStore.clearSelection()
        await saveCanvas()
    }

    // ===== 任务组（两 Tab 统一支持：直接操作当前数据源的 tasks，不走后端任务 CRUD） =====

    async function handleCreateGroup(payload) {
        activeUndoRedo.value.commit()
        const tasks = canvasData.value.tasks
        tasks.push({
            task_id: `task_${Date.now()}`,
            task_name: payload.name || '新建组',
            loop_count: 1,
            loop_interval: 0,
            nodes: []
        })
        await saveCanvas()
        ElMessage.success(`任务组 [${payload.name}] 创建成功`)
    }

    async function handleDeleteGroup(payload) {
        activeUndoRedo.value.commit()
        const tasks = canvasData.value.tasks
        const nextTasks = tasks.filter(t => t.task_id !== payload.taskId)
        if (isTopology.value) {
            store.blueprint.topology = { tasks: nextTasks, edges: canvasData.value.edges }
        } else {
            store.blueprint.tasks = nextTasks
        }
        await saveCanvas()
        ElMessage.success('任务组已删除')
    }

    // ===== 通用操作（两 Tab 共用） =====

    async function handleSave() {
        await store.saveBlueprintImmediately()
        ElMessage.success('蓝图已保存')
    }

    function handleDelete() {
        const ids = uiStore.selectedNodeIds || []
        if (!ids.length) {
            ElMessage.warning('请先选中要删除的节点')
            return
        }
        const tasks = canvasData.value.tasks
        const edges = canvasData.value.edges
        let nextTasks = tasks
        for (const id of [...ids]) {
            nextTasks = removeNode(nextTasks, edges, id)
        }
        if (isTopology.value) {
            store.blueprint.topology = { tasks: nextTasks, edges }
        } else {
            store.blueprint.tasks = nextTasks
        }
        activeUndoRedo.value.commit()
        uiStore.clearSelection()
        saveCanvas()
    }

    function handleSelectAll() {
        const allIds = (canvasData.value.tasks || []).flatMap(t => (t.nodes || []).map(n => n.node_id))
        if (!allIds.length) return
        // 已全选 -> 取消全选
        if (uiStore.selectedNodeIds.length === allIds.length &&
            allIds.every(id => uiStore.selectedNodeIds.includes(id))) {
            uiStore.selectNodes([])
            return
        }
        uiStore.selectNodes(allIds)
    }

    onMounted(async () => {
        if (store.currentProjectPath) {
            await store.loadProjectData()
        }
    })
</script>
