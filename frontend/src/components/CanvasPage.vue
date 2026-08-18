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
    import { buildNodeDefaultParams, NODE_DEFAULTS } from '@/utils/nodeDefaults'
    import { buildControlParamsFromInfo, buildControlNodeName } from '@/utils/captureNode'
    import {
        NODE_WIDTH, NODE_MIN_HEIGHT, computeCanvasNodeHeight,
        computeGroupBox, findFreePosition, isColliding
    } from '@/utils/canvasShared'
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
        let isNewGroup = false   // ⚡ 本次是否新建组（组级避让只作用于新组，不惊动已有组）

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
            isNewGroup = true
            tasks.push(targetTask)
        }

        if (!targetTask.nodes) targetTask.nodes = []

        const chineseLabel = (availableNodeTypes.value[payload.type] || payload.type).replace(/^[^\u4e00-\u9fa5]+/, '').trim()
        const sameTypeCount = targetTask.nodes.filter(n => n.node_type === payload.type).length + 1
        const newNode = {
            node_id: payload.nodeId,
            node_name: payload.nodeName || `${chineseLabel}_${sameTypeCount}`,
            node_type: payload.type,
            // 复制粘贴：沿用源节点参数；新建：从后端 schema default 填充（集中默认值，见 utils/nodeDefaults.js）
            params: payload.params
                ? JSON.parse(JSON.stringify(payload.params))
                : buildNodeDefaultParams(payload.type, store.paramsDefinitions),
            delay_before: payload.delayBefore ?? NODE_DEFAULTS.delayBefore,
            loop_count: payload.loopCount ?? NODE_DEFAULTS.loopCount,
            position: payload.position || { x: 0, y: 0 }
        }

        // 页面状态节点：自动生成内部页面标识（表单隐藏，标题即页面名）
        if (payload.type === 'page_state' && !newNode.params.page_id) {
            newNode.params.page_id = `page_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
        }

        // ⚡ 新建避让：新节点被身边节点/组挤开，不再重叠（所有创建入口统一经过此处）
        const newNodeSize = {
            w: NODE_WIDTH,
            h: computeCanvasNodeHeight(newNode.params ? Object.keys(newNode.params).length : 0, 0)
        }
        // 1) 节点级避让：避开同组已有节点（把新节点推到无碰撞位置，旧布局不动）
        const sameGroupNodes = (targetTask.nodes || []).map(n => ({
            position: n.position, size: { w: NODE_WIDTH, h: NODE_MIN_HEIGHT }
        }))
        const freePos = findFreePosition(sameGroupNodes, newNode.position, newNodeSize)
        newNode.position = { x: freePos.x, y: freePos.y }
        // 2) 组级避让：新建组若与已有组重叠，整体平移新组（组内所有成员同偏移）——只作用于新组
        if (isNewGroup) {
            const groupBoxes = new Map()  // task_id -> box（只算一次）
            const boxOf = (task) => {
                if (!groupBoxes.has(task.task_id)) {
                    groupBoxes.set(task.task_id, computeGroupBox(task.nodes || []))
                }
                return groupBoxes.get(task.task_id)
            }
            const newGroupBox = computeGroupBox([...targetTask.nodes, newNode])
            let shiftX = 0, shiftY = 0
            let guard = 0
            while (guard < 100) {
                const cand = {
                    position: { x: newGroupBox.x + shiftX, y: newGroupBox.y + shiftY },
                    size: { w: newGroupBox.w, h: newGroupBox.h }
                }
                const overlaps = tasks.some(t => {
                    if (t.task_id === targetTask.task_id) return false
                    const b = boxOf(t)
                    return isColliding(cand, { position: { x: b.x, y: b.y }, size: { w: b.w, h: b.h } })
                })
                if (!overlaps) break
                shiftX += 40
                shiftY += 40
                guard += 1
            }
            if (shiftX || shiftY) {
                for (const n of targetTask.nodes) {
                    n.position = { x: (n.position.x || 0) + shiftX, y: (n.position.y || 0) + shiftY }
                }
                newNode.position = { x: (newNode.position.x || 0) + shiftX, y: (newNode.position.y || 0) + shiftY }
            }
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

    // ===== 控件捕获模式：一键生成控件节点（由 IdeLayout 经 ref 调用） =====
    async function createControlNodeFromCapture(info) {
        if (!info || typeof info !== 'object') return
        // 查找参数自动填充（纯函数，逻辑与测试见 utils/captureNode.js）
        const { by, target } = buildControlParamsFromInfo(info)
        if (!target) {
            ElMessage.warning('未捕获到有效控件信息')
            return
        }

        const nodeId = `node_${Date.now()}${Math.random().toString(36).slice(2, 5)}`
        const params = {
            ...buildNodeDefaultParams('control', store.paramsDefinitions),
            by,
            target,
            // ⚡ 捕获的完整定位信息一并存入节点隐藏字段（表单只展示控件名称）：
            // 窗口标题用于查找作用域，control_info 供主选择器未命中时兜底重查
            window_title: String(info?.window_title || ''),
            index: info?.index ?? 0,
            control_info: info || null
        }
        const nodeName = buildControlNodeName(info)
        let position = null
        let sourceNodeId = null

        // 选中单个节点 → 在其 success 线后新建（与粘贴逻辑一致）
        const selectedIds = uiStore.selectedNodeIds?.length ? uiStore.selectedNodeIds
            : (uiStore.selectedNodeId ? [uiStore.selectedNodeId] : [])
        if (selectedIds.length === 1) {
            const tasks = canvasData.value.tasks
            for (const t of tasks) {
                const found = (t.nodes || []).find(n => n.node_id === selectedIds[0])
                if (found) {
                    sourceNodeId = found.node_id
                    const w = found.w || 180
                    position = {
                        x: Math.round((found.position.x + w + 40) / 20) * 20,
                        y: found.position.y
                    }
                    break
                }
            }
        }
        if (!position) {
            position = { x: 0, y: 0 }
        }

        await handleCreateNode({
            nodeId,
            type: 'control',
            nodeName,
            params,
            position,
            sourceNodeId,
            portType: 'succ',
        })
        uiStore.selectNodes([nodeId])
        ElMessage.success(`已生成控件节点 [${nodeName}]（${by} = ${target}）`)
    }

    defineExpose({ createControlNodeFromCapture })
</script>
