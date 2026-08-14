<!-- frontend/src/components/canvas/CanvasView.vue
  统一画布组件（Step 3）：workflow 与 topology 两种模式共享全部交互。
  数据只读（props.tasks / props.edges），所有数据变更通过 emit 事件回传包装器执行；
  交互状态（选中/断点/运行高亮/聚焦）经 useMainStore 读取。
-->
<template>
    <div
        ref="containerRef"
        class="custom-canvas-container"
        @mousedown="onCanvasMouseDown"
        @wheel.prevent="onCanvasWheel"
        @contextmenu="onContextMenu">
        <!-- 视口变换层（网格由统一世界图层矢量绘制，不再用 CSS 背景） -->
        <div class="canvas-viewport" :style="viewportStyle">
            <!-- SVG 世界图层（矢量网格 + 连线，共享子组件） -->
            <CanvasEdgeLayer
                :edges="computedEdges"
                :drawing-connection="drawingConnection"
                :viewport="viewport"
                :container-size="containerSize"
                @edge-click="onEdgeClick" />

            <!-- 任务组包围框（仅 workflow） -->
            <div
                v-for="group in dynamicGroups"
                :key="group.groupId"
                :data-group-id="group.groupId"
                :class="['canvas-group-box', { 'is-focused': activeFocusedGroupId === group.groupId }]"
                :style="{
                    left: group.box.x + 'px',
                    top: group.box.y + 'px',
                    width: group.box.w + 'px',
                    height: group.box.h + 'px'
                }">
                <div
                    class="group-title-badge"
                    :data-group-id="group.groupId"
                    @mousedown.stop="startGroupDrag($event, group.groupId)"
                    @dblclick.stop="openGroupInspector($event, group)">
                    <div class="group-name-text">📁 {{ group.groupName }}</div>
                    <div class="group-sub-info">
                        <span>间隔: {{ group.loopInterval || 0 }}s</span>
                        <span>循环: {{ group.loopCount }}次</span>
                    </div>
                </div>
            </div>

            <!-- 节点拖拽预览框 -->
            <div
                v-if="draggingNodeId && dragPreviewBox.visible"
                class="node-drag-preview-box"
                :class="{ 'is-danger': dragPreviewBox.hasCollision }"
                :style="{
                    left: dragPreviewBox.x + 'px',
                    top: dragPreviewBox.y + 'px',
                    width: dragPreviewBox.w + 'px',
                    height: dragPreviewBox.h + 'px'
                }">
                <div class="preview-inner-tag">
                    {{ dragPreviewBox.hasCollision ? '⚠️ 将自动推挤周围节点' : '✔️ 空间充足' }}
                </div>
            </div>

            <!-- 节点卡片层（共享子组件） -->
            <CanvasNodeCard
                v-for="node in renderNodes"
                :key="node.node_id"
                :node="node"
                :selected="node.selected"
                :is-active-debug="hasBreakpoints && store.currentActiveNodeId === node.node_id"
                :has-breakpoint="hasBreakpoints ? uiStore.hasBreakpoint(node.node_id) : false"
                :current-project-path="store.currentProjectPath"
                :blueprint-version="store.blueprint?.version || 0"
                :mode="mode"
                @node-mousedown="onNodeMouseDown"
                @node-mouseup="onNodeMouseUpCard"
                @node-dblclick="onNodeDoubleClick"
                @node-contextmenu="openNodeContextMenu"
                @toggle-breakpoint="handleToggleBreakpoint"
                @start-connection="startConnection"
                @image-loaded="(data) => onImageLoaded(data)" />
        </div>

        <!-- 全景缩略图导航面板（两模式共用） -->
        <div class="minimap-container" v-show="store.uiState.minimapExpanded">
            <canvas ref="minimapCanvasRef" width="150" height="110" @click="onMinimapClick" />
        </div>

        <!-- 框选 UI -->
        <div v-if="selectionBox.visible" class="selection-box" :style="selectionBoxStyle" />

        <!-- 缩放工具栏（两模式共用） -->
        <div class="canvas-toolbar">
            <button class="toolbar-btn" @click="zoomIn" title="放大">
                <Plus :size="16" />
            </button>
            <button class="toolbar-btn" @click="zoomOut" title="缩小">
                <Minus :size="16" />
            </button>
            <button class="toolbar-btn" @click="resetView" title="重置视图">
                <Maximize :size="16" />
            </button>
            <span class="zoom-display">{{ Math.round(viewport.zoom * 100) }}%</span>
        </div>

        <!-- 右键菜单 + Spawn 菜单（共享子组件） -->
        <CanvasContextMenu
            :spawn-menu="spawnMenu"
            :context-menu="customContextMenu"
            :menu-z-index="menuZIndex"
            :available-node-types="availableNodeTypes"
            :has-breakpoint="hasBreakpoints && customContextMenu.targetId ? uiStore.hasBreakpoint(customContextMenu.targetId) : false"
            :is-paused="store.isPaused"
            :show-debug-items="hasBreakpoints"
            :has-groups="hasGroups"
            @create-and-connect="createAndConnectNode"
            @run-from-node="handleRunFromNode"
            @toggle-breakpoint="handleToggleBreakpoint"
            @add-breakpoint-and-run="handleAddBreakpointAndRun"
            @resume-execution="store.resumeExecution"
            @step-over="store.stepOverExecution"
            @step-into="store.stepIntoExecution"
            @delete-node="handleDeleteNode"
            @delete-group="handleDeleteGroup"
            @canvas-new-node="handleCanvasNewNode"
            @canvas-new-group="handleCanvasNewGroup" />
    </div>
</template>

<script setup>
    import { ref, computed, onMounted, onUnmounted, reactive, nextTick, watch } from 'vue'
    import { useMainStore, useUiStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { Plus, Minus, Maximize } from 'lucide-vue-next'
    import { computeEdgePath, getSimpleOrthoPath } from '@/utils/canvasRouter'
    import {
        normalizePortType, normalizeNodeList,
        getPortPosition, getArrowDirection
    } from '@/utils/nodeModel'
    import { NODE_WIDTH, computeCanvasNodeHeight } from '@/utils/canvasShared'
    import { getNextZIndex } from '@/utils/zIndexManager'
    import { deriveWorkflowEdges } from '@/utils/workflowEdgeModel'
    import { topologyFileToFlat } from '@/utils/topologyModel'

    import { useCanvasKeyboard } from '@/composables/useCanvasKeyboard'
    import { useViewport } from '@/composables/useViewport'
    import { useNodeDrag } from '@/composables/useNodeDrag'
    import { useConnection } from '@/composables/useConnection'
    import { useContextMenu } from '@/composables/useContextMenu'
    import { useCanvasSharedStyle } from '@/composables/useCanvasSharedStyle'

    import CanvasNodeCard from '@/components/canvas/CanvasNodeCard.vue'
    import CanvasEdgeLayer from '@/components/canvas/CanvasEdgeLayer.vue'
    import CanvasContextMenu from '@/components/canvas/CanvasContextMenu.vue'

    useCanvasSharedStyle()

    const props = defineProps({
        mode: { type: String, default: 'workflow' },   // 'workflow' | 'topology'
        tasks: { type: Array, default: () => [] },
        edges: { type: Array, default: () => [] },
        availableNodeTypes: { type: Object, default: () => ({}) },
        hasGroups: { type: Boolean, default: false },
        hasBreakpoints: { type: Boolean, default: false },
        // 快捷键回调（由包装器注入）
        onSave: { type: Function, default: null },
        onDelete: { type: Function, default: null },
        onSelectAll: { type: Function, default: null },
        onUndo: { type: Function, default: null },
        onRedo: { type: Function, default: null }
    })

    const emit = defineEmits([
        'update-tasks',            // (tasks) 节点/组拖拽结算后的完整任务组数组
        'update-node-positions',   // ([{node_id, position}]) 拓扑节点拖拽结算
        'add-edge',                // ({source, target, source_port})
        'remove-edge',             // ({sourceNodeId, legacyPort, candIndex, edge_id, targetNodeId})
        'create-node',             // ({nodeId, type, position, groupId, sourceNodeId, portType})
        'delete-node',             // ({nodeId, taskId})
        'create-group',            // ({name})
        'delete-group'             // ({taskId})
    ])

    const store = useMainStore()
    const uiStore = useUiStore()

    const containerRef = ref(null)
    const minimapCanvasRef = ref(null)

    // 容器尺寸（供世界图层按可见区域计算 SVG 盒与网格范围）
    const containerSize = reactive({ width: 0, height: 0 })
    let containerResizeObserver = null

    // 网格常量
    const GRID_SIZE = 20
    const NODE_GRID_W = 8

    // ===== 快捷键：Ctrl+S / Ctrl+A（Delete 由 globalKeydownHandler 统一处理以优先删边） =====
    useCanvasKeyboard({
        onSave: props.onSave || (async () => { await store.saveBlueprintImmediately(); ElMessage.success('蓝图已保存') }),
        onDelete: () => {},
        onSelectAll: props.onSelectAll || (() => uiStore.selectAllNodes())
    })

    // ===== 视口 / 拖拽 / 连线 / 菜单 =====
    const { viewport, isPanning, panStart, viewportStyle, onCanvasWheel: viewportWheel, zoomIn, zoomOut, resetView } = useViewport()

    const dragComposable = useNodeDrag({
        viewport,
        getRenderNodes: () => renderNodes.value,
        getDynamicGroups: () => dynamicGroups.value,
        GRID_SIZE,
        NODE_GRID_W
    })
    const {
        draggingNodeId, hasMoved, isCtrlHeldRef, dragPreviewBox,
        localDraftPositions, draggedSourceGroupSnapshot, ghostPlaceholder,
        selectionBox, resolveCollisionsAndPushOthers, calculateOverlapRatio,
        resolveGroupCollisionsAndPushOthers
    } = dragComposable

    const { drawingConnection } = useConnection()
    const { customContextMenu, spawnMenu } = useContextMenu()

    const menuZIndex = ref(3000)
    const dynamicImageHeights = reactive({})
    const tallImageFlags = reactive({})
    const selectedEdgeId = ref(null)
    const localSelectedNodeIds = ref([])

    // 拖拽辅助状态
    const dragStartMouse = ref({ x: 0, y: 0 })
    const nodeInitialPos = ref({ x: 0, y: 0 })

    // 拖拽结算期间用本地克隆覆盖数据源（保持 dynamicGroups 等 computed 响应式重算），
    // 包装器完成保存后 props 更新、override 自动清空
    const localTasksOverride = ref(null)
    const dataTasks = computed(() => localTasksOverride.value || props.tasks)
    watch(() => props.tasks, () => { localTasksOverride.value = null })

    const isTopology = computed(() => props.mode === 'topology')

    const getNodeShortLabel = (nodeType) => {
        const label = props.availableNodeTypes[nodeType] || nodeType
        return label.replace(/^[^\u4e00-\u9fa5]+/, '').trim()
    }

    const selectionBoxStyle = computed(() => {
        if (!containerRef.value) return {}
        const rect = containerRef.value.getBoundingClientRect()
        const startX = selectionBox.value.startX - rect.left
        const startY = selectionBox.value.startY - rect.top
        const endX = selectionBox.value.endX - rect.left
        const endY = selectionBox.value.endY - rect.top
        return {
            left: Math.min(startX, endX) + 'px',
            top: Math.min(startY, endY) + 'px',
            width: Math.abs(endX - startX) + 'px',
            height: Math.abs(endY - startY) + 'px'
        }
    })

    const activeFocusedGroupId = computed(() => {
        if (draggingNodeId.value) {
            const tasks = dataTasks.value || []
            for (let i = 0; i < tasks.length; i++) {
                if ((tasks[i].nodes || []).some(n => n.node_id === draggingNodeId.value)) {
                    return `group_${tasks[i].task_id || i}`
                }
            }
        }
        if (localSelectedNodeIds.value.length > 0) {
            const firstSelId = localSelectedNodeIds.value[0]
            const tasks = dataTasks.value || []
            for (let i = 0; i < tasks.length; i++) {
                if ((tasks[i].nodes || []).some(n => n.node_id === firstSelId)) {
                    return `group_${tasks[i].task_id || i}`
                }
            }
        }
        return null
    })

    // ===== 拓扑扁平节点（供渲染/命中检测） =====
    const flatTopologyNodes = computed(() => topologyFileToFlat({ tasks: dataTasks.value, edges: props.edges }).nodes)
    const flatTopologyEdges = computed(() => topologyFileToFlat({ tasks: dataTasks.value, edges: props.edges }).edges)

    // ===== 已连线端口集合（从原始数据派生，避免与 renderNodes 循环依赖） =====
    const connectedWorkflowPorts = computed(() => {
        const map = {}
        for (const edge of deriveWorkflowEdges(dataTasks.value)) {
            const ports = map[edge.sourceNodeId] || (map[edge.sourceNodeId] = new Set())
            ports.add(edge.legacyPort)
        }
        return map
    })

    const connectedTopologyPorts = computed(() => {
        const map = {}
        for (const edge of flatTopologyEdges.value) {
            const ports = map[edge.source] || (map[edge.source] = new Set())
            ports.add(edge.source_port || 'exit')
        }
        return map
    })

    const FAILURE_PORT_TYPES = ['image_recognition', 'ocr_recognition', 'branch', 'logic_check']

    // 为节点构建端口模型（定义存在 ∪ 已连线；含 success/failure/dynamic 可见性与 connected 状态）
    function buildNodePorts(node) {
        const connectedSet = isTopology.value
            ? connectedTopologyPorts.value[node.node_id]
            : connectedWorkflowPorts.value[node.node_id]
        const has = (p) => (connectedSet ? connectedSet.has(p) : false)
        const nodeType = isTopology.value ? (node.type || node.node_type) : node.node_type

        let definedDynamic = []
        if (!isTopology.value && nodeType === 'branch') {
            definedDynamic = (node.params?.candidates || []).map((c, i) => ({
                name: `branch_${i}`,
                label: `分支 ${i + 1}`
            }))
        } else if (isTopology.value && nodeType === 'page_state') {
            definedDynamic = (node.exits || []).map((ex, i) => ({
                name: `exit_${i}`,
                label: ex?.label || ex?.exit_action || `出口 ${i + 1}`
            }))
        }

        const definedNames = definedDynamic.map(d => d.name)
        const connectedDynamic = []
        for (const p of connectedSet || []) {
            const name = p === 'exit' ? 'exit_0' : p
            const isDynamic = p === 'exit' || p.startsWith('branch_') || p.startsWith('exit_')
            if (isDynamic && !definedNames.includes(name)) {
                connectedDynamic.push({ name, label: name === 'exit_0' ? '出口 1' : name })
            }
        }
        const dynamic = [...definedDynamic, ...connectedDynamic].sort((a, b) => {
            const ai = parseInt(a.name.split('_')[1], 10) || 0
            const bi = parseInt(b.name.split('_')[1], 10) || 0
            return ai - bi
        })

        return {
            success: { visible: true, connected: has('succ') || has('success') },
            failure: {
                visible: FAILURE_PORT_TYPES.includes(nodeType) || has('fail') || has('failure'),
                connected: has('fail') || has('failure')
            },
            dynamic: dynamic.map(d => ({
                ...d,
                connected: has(d.name) || (d.name === 'exit_0' && has('exit'))
            }))
        }
    }

    // 拓扑内容区高度（Step 4 网格化）：基础 2 格，page_state 按 page_id/features/exits 各 +1 格
    const computeTopologyContentHeight = (node) => {
        let h = 40
        if ((node.type || node.node_type) === 'page_state') {
            if (node.page_id) h += 20
            if (node.features?.length) h += 20
            if (node.exits?.length) h += 20
        }
        return h
    }

    const renderNodes = computed(() => {
        if (isTopology.value) {
            const raw = flatTopologyNodes.value.map(n => {
                const ports = buildNodePorts(n)
                const rawPos = localDraftPositions[n.node_id] || n.position || { x: 0, y: 0 }
                const gridX = Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE
                const gridY = Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
                const w = NODE_WIDTH
                const h = computeCanvasNodeHeight(computeTopologyContentHeight(n), ports.dynamic.length)
                return {
                    ...n,
                    node_type: n.type,
                    node_name: n.node_name || n.label || n.page_id || '未命名',
                    position: { x: gridX, y: gridY },
                    w,
                    h,
                    size: { w, h },
                    ports,
                    selected: localSelectedNodeIds.value.includes(n.node_id)
                }
            })
            return normalizeNodeList(raw)
        }

        // workflow：遍历任务组展开节点
        const tasks = dataTasks.value || []
        let allNodesList = []
        tasks.forEach((task) => {
            const rawNodes = task.nodes || []
            rawNodes.forEach((node, nIndex) => {
                const ports = buildNodePorts(node)
                const rawPos = localDraftPositions[node.node_id] || node.position || { x: 60 + (nIndex % 3) * 200, y: 60 + Math.floor(nIndex / 3) * 120 }
                const gridX = Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE
                const gridY = Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
                const isSel = localSelectedNodeIds.value.includes(node.node_id)

                let contentHeightPx = 40
                if (node.node_type === 'image_recognition') {
                    contentHeightPx = Math.max(80, dynamicImageHeights[node.node_id] || 80)
                } else if (node.node_type === 'ocr_recognition') {
                    contentHeightPx = 60
                } else if (node.node_type === 'branch') {
                    const candCount = node.params?.candidates?.length || 0
                    contentHeightPx = Math.max(candCount * 24 + 12, 40)
                }

                const finalHeight = computeCanvasNodeHeight(contentHeightPx, ports.dynamic.length)
                const w = NODE_GRID_W * GRID_SIZE
                allNodesList.push({
                    ...node,
                    position: { x: gridX, y: gridY },
                    w,
                    h: finalHeight,
                    size: { w, h: finalHeight },
                    ports,
                    selected: isSel
                })
            })
        })
        return allNodesList
    })

    const onImageLoaded = (data) => {
        const { nodeId, width: naturalW, height: naturalH, cardInnerWidth } = data
        const ratio = naturalH / naturalW
        if (ratio > 1) {
            tallImageFlags[nodeId] = true
            dynamicImageHeights[nodeId] = cardInnerWidth
        } else {
            tallImageFlags[nodeId] = false
            dynamicImageHeights[nodeId] = Math.round(cardInnerWidth * ratio)
        }
    }

    const fitViewToNodes = () => {
        nextTick(() => {
            const allNodes = renderNodes.value
            if (allNodes.length === 0 || !containerRef.value) return

            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
            allNodes.forEach(n => {
                const pos = n.position || { x: 0, y: 0 }
                const w = n.w || (NODE_GRID_W * GRID_SIZE)
                const h = n.h || 120
                minX = Math.min(minX, pos.x)
                minY = Math.min(minY, pos.y)
                maxX = Math.max(maxX, pos.x + w)
                maxY = Math.max(maxY, pos.y + h)
            })

            const centerX = (minX + maxX) / 2
            const centerY = (minY + maxY) / 2

            const containerW = containerRef.value.clientWidth
            const containerH = containerRef.value.clientHeight

            viewport.value.x = containerW / 2 - centerX * viewport.value.zoom
            viewport.value.y = containerH / 2 - centerY * viewport.value.zoom

            drawMinimap()
        })
    }

    const dynamicGroups = computed(() => {
        if (isTopology.value || !props.hasGroups) return []
        const tasks = dataTasks.value || []
        let groups = []
        const PADDING_GRIDS = 3
        const PADDING_PX = PADDING_GRIDS * GRID_SIZE

        const allRenderedNodes = renderNodes.value

        tasks.forEach((task, tIndex) => {
            const groupId = `group_${task.task_id || tIndex}`
            const groupName = task.task_name || `任务组 ${tIndex + 1}`

            const taskNodeIds = (task.nodes || []).map(n => n.node_id)
            const groupNodes = allRenderedNodes.filter(n => {
                if (!taskNodeIds.includes(n.node_id)) return false
                if (n.node_id === draggingNodeId.value && isCtrlHeldRef.value) {
                    return false
                }
                return true
            })

            let effectiveNodes = [...groupNodes]
            if (ghostPlaceholder.value && draggingNodeId.value && isCtrlHeldRef.value) {
                const isNodeInThisGroup = taskNodeIds.includes(draggingNodeId.value)
                if (isNodeInThisGroup) {
                    effectiveNodes.push(ghostPlaceholder.value)
                }
            }

            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity

            if (effectiveNodes.length > 0) {
                effectiveNodes.forEach((node) => {
                    minX = Math.min(minX, node.position.x)
                    minY = Math.min(minY, node.position.y)
                    maxX = Math.max(maxX, node.position.x + node.w)
                    maxY = Math.max(maxY, node.position.y + node.h)
                })

                const rawBoxX = minX - PADDING_PX
                const rawBoxY = minY - PADDING_PX - 24
                const rawBoxW = (maxX - minX) + PADDING_PX * 2
                const rawBoxH = (maxY - minY) + PADDING_PX * 2 + 24

                const boxX = Math.round(rawBoxX / GRID_SIZE) * GRID_SIZE
                const boxY = Math.round(rawBoxY / GRID_SIZE) * GRID_SIZE
                const boxW = Math.max(Math.round(rawBoxW / GRID_SIZE) * GRID_SIZE, 220)
                const boxH = Math.max(Math.round(rawBoxH / GRID_SIZE) * GRID_SIZE, 120)

                groups.push({
                    groupId,
                    groupName,
                    taskId: task.task_id,
                    loopCount: task.loop_count || 1,
                    loopInterval: task.loop_interval || 0,
                    box: { x: boxX, y: boxY, w: boxW, h: boxH }
                })
            } else {
                groups.push({
                    groupId,
                    groupName,
                    taskId: task.task_id,
                    loopCount: task.loop_count || 1,
                    loopInterval: task.loop_interval || 0,
                    box: { x: 60, y: 60, w: 240, h: 140 }
                })
            }
        })
        return groups
    })

    const onContextMenu = (e) => {
        e.preventDefault()
        menuZIndex.value = getNextZIndex(e)
        customContextMenu.visible = false

        const nodeCard = e.target.closest('.canvas-node-card')
        if (nodeCard) {
            const nodeId = nodeCard.getAttribute('data-node-id')
            const nodeObj = renderNodes.value.find(n => n.node_id === nodeId)
            if (nodeObj) {
                customContextMenu.visible = true
                customContextMenu.x = e.clientX
                customContextMenu.y = e.clientY
                customContextMenu.targetType = 'node'
                customContextMenu.targetId = nodeObj.node_id
                customContextMenu.targetName = nodeObj.node_name
                customContextMenu.clientX = e.clientX
                customContextMenu.clientY = e.clientY
                return
            }
        }

        if (props.hasGroups) {
            const groupBox = e.target.closest('.canvas-group-box') || e.target.closest('.group-title-badge')
            if (groupBox) {
                const groupId = groupBox.getAttribute('data-group-id')
                const groupObj = dynamicGroups.value.find(g => g.groupId === groupId)
                if (groupObj) {
                    customContextMenu.visible = true
                    customContextMenu.x = e.clientX
                    customContextMenu.y = e.clientY
                    customContextMenu.targetType = 'group'
                    customContextMenu.targetId = groupObj.taskId
                    customContextMenu.targetName = groupObj.groupName
                    customContextMenu.clientX = e.clientX
                    customContextMenu.clientY = e.clientY
                    return
                }
            }
        }

        if (!containerRef.value) return
        const rect = containerRef.value.getBoundingClientRect()
        const clientX = e.clientX - rect.left
        const clientY = e.clientY - rect.top
        const worldX = (clientX - viewport.value.x) / viewport.value.zoom
        const worldY = (clientY - viewport.value.y) / viewport.value.zoom

        let hitGroup = null
        if (props.hasGroups) {
            for (const g of dynamicGroups.value) {
                const box = g.box
                if (worldX >= box.x && worldX <= box.x + box.w && worldY >= box.y && worldY <= box.y + box.h) {
                    hitGroup = g
                    break
                }
            }
        }

        customContextMenu.visible = true
        customContextMenu.x = e.clientX
        customContextMenu.y = e.clientY
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY

        if (hitGroup) {
            customContextMenu.targetType = 'canvas_in_group'
            customContextMenu.targetId = hitGroup.taskId
            customContextMenu.targetName = hitGroup.groupName
        } else {
            customContextMenu.targetType = 'canvas_public'
            customContextMenu.targetId = null
            customContextMenu.targetName = ''
        }
    }

    // ===== 调试相关（仅 workflow） =====
    const findTargetTaskId = (nodeId) => {
        const tasks = dataTasks.value || []
        for (const task of tasks) {
            if ((task.nodes || []).some(n => n.node_id === nodeId)) {
                return task.task_id
            }
        }
        return null
    }

    const handleRunFromNode = async () => {
        if (isTopology.value) return
        const nodeId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!nodeId) return

        const targetTaskId = findTargetTaskId(nodeId)
        if (!targetTaskId) {
            ElMessage.error('未找到该节点所属的任务组')
            return
        }

        try {
            ElMessage.info('正在从当前节点启动任务...')
            const result = await store.runTask(targetTaskId, nodeId)
            if (result && result.status === 'started') {
                ElMessage.success('任务已成功从当前节点启动！')
            } else {
                ElMessage.error('执行失败')
            }
        } catch (err) {
            ElMessage.error('执行请求失败: ' + err.message)
        }
    }

    function openNodeContextMenu(e, node) {
        customContextMenu.visible = true
        customContextMenu.targetType = 'node'
        customContextMenu.targetId = node.node_id
        customContextMenu.targetName = node.node_name
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY
        const rect = containerRef.value?.getBoundingClientRect?.()
        customContextMenu.x = rect ? (e.clientX - rect.left) + 8 : e.offsetX
        customContextMenu.y = rect ? (e.clientY - rect.top) + 8 : e.offsetY
        menuZIndex.value = getNextZIndex()
        spawnMenu.value.visible = false
    }

    function handleToggleBreakpoint(nodeId) {
        if (!props.hasBreakpoints || !nodeId) return
        const added = uiStore.toggleBreakpoint(nodeId)
        customContextMenu.visible = false
        ElMessage.info(
            added ? `🔴 已设置断点：${nodeId}` : `⚪ 已移除断点：${nodeId}`
        )
    }

    async function handleAddBreakpointAndRun(nodeId) {
        if (!props.hasBreakpoints || !nodeId) return
        uiStore.enableBreakpoint(nodeId)
        customContextMenu.visible = false

        const targetTaskId = findTargetTaskId(nodeId)
        if (!targetTaskId) {
            ElMessage.error('未找到该节点所属任务组')
            return
        }
        try {
            const result = await store.runTask(targetTaskId)
            if (result?.status === 'started') {
                ElMessage.success('任务已启动，将在设置的断点处暂停')
            } else {
                ElMessage.error('启动失败')
            }
        } catch (err) {
            ElMessage.error('启动失败：' + err.message)
        }
    }

    const handleDeleteNode = () => {
        const nodeId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!nodeId) return

        const taskId = findTargetTaskId(nodeId)
        emit('delete-node', { nodeId, taskId })
        if (isTopology.value) {
            store.selectTopologyNode(null)
        } else {
            store.clearSelection()
        }
        localSelectedNodeIds.value = []
        ElMessage.success('节点已删除')
    }

    const handleDeleteGroup = () => {
        if (isTopology.value) return
        const taskId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!taskId) return
        emit('delete-group', { taskId })
        ElMessage.success('任务组已删除')
    }

    const handleCanvasNewNode = () => {
        customContextMenu.visible = false
        spawnMenu.value = {
            visible: true,
            x: customContextMenu.x,
            y: customContextMenu.y,
            sourceNodeId: null,
            portType: 'succ',
            clientX: customContextMenu.clientX,
            clientY: customContextMenu.clientY
        }
    }

    const handleCanvasNewGroup = async () => {
        if (isTopology.value) {
            // 拓扑模式无任务组：退化为新建节点
            handleCanvasNewNode()
            return
        }
        customContextMenu.visible = false
        try {
            const { value: groupName } = await ElMessageBox.prompt('请输入新任务组名称', '新建任务组', {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                inputPattern: /\S+/,
                inputErrorMessage: '任务组名称不能为空'
            })

            if (groupName) {
                emit('create-group', { name: groupName.trim() })
                ElMessage.success(`任务组 [${groupName}] 创建成功`)
            }
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error(err.message || '创建任务组失败')
            }
        }
    }

    // ===== 连线计算 =====
    const computedEdges = computed(() => {
        const allNodes = renderNodes.value
        const activeDraggingId = draggingNodeId.value
        const isActuallyMoving = hasMoved.value

        let edges = []
        const routerNodes = normalizeNodeList(allNodes)

        const pushEdge = ({ sourceNode, targetNode, legacyPort, edgeIdBase, isFailFlag, extra = {}, edgeId, candIndex }) => {
            const standardPort = normalizePortType(legacyPort)
            const isThisEdgeDragging = activeDraggingId && isActuallyMoving &&
                (sourceNode.node_id === activeDraggingId || targetNode.node_id === activeDraggingId)

            let path = ''
            let arrowDir = 'down'
            let startPt = null
            let endPt = null
            let rawPixelPoints = []

            if (isThisEdgeDragging) {
                // 拖拽中：使用简单正交折线 + 圆角，避免每帧 BFS 开销
                const sPt = getPortPosition(sourceNode, legacyPort)
                const ePt = getPortPosition(targetNode, 'entry')
                startPt = sPt
                endPt = ePt
                path = getSimpleOrthoPath(sPt, ePt, standardPort)
                rawPixelPoints = [sPt, ePt]
                arrowDir = getArrowDirection(rawPixelPoints)
            } else {
                // 静态：canvasRouter BFS 寻路
                try {
                    const result = computeEdgePath(sourceNode, targetNode, routerNodes, standardPort, {})
                    path = result.pathD
                    arrowDir = result.arrowDir
                    rawPixelPoints = result.points || []
                    if (rawPixelPoints.length) {
                        startPt = rawPixelPoints[0]
                        endPt = rawPixelPoints[rawPixelPoints.length - 1]
                    }
                } catch (e) {
                    console.warn('[CanvasView] computeEdgePath 失败，使用兜底路径:', e)
                    const sPt = getPortPosition(sourceNode, legacyPort)
                    const ePt = getPortPosition(targetNode, 'entry')
                    startPt = sPt
                    endPt = ePt
                    path = getSimpleOrthoPath(sPt, ePt, standardPort)
                    rawPixelPoints = [sPt, ePt]
                    arrowDir = getArrowDirection(rawPixelPoints)
                }
            }

            const isFail = !!isFailFlag
            const markerPrefix = isFail ? 'fail' : 'succ'

            edges.push({
                id: edgeIdBase,
                sourceNodeId: sourceNode.node_id,
                targetNodeId: targetNode.node_id,
                typeFlag: legacyPort === 'succ' ? 'succ' : (legacyPort === 'fail' ? 'fail' : 'branch'),
                legacyPort,
                candIndex: candIndex ?? extra?.candIndex,
                edgeId,
                ...extra,
                path,
                isFail,
                markerUrl: `url(#arrow-${markerPrefix}-${arrowDir})`,
                selected: selectedEdgeId.value === edgeIdBase,
                labelX: startPt && endPt ? (startPt.x + endPt.x) / 2 : 0,
                labelY: startPt && endPt ? (startPt.y + endPt.y) / 2 - 10 : 0,
                rawPixelPoints
            })
        }

        if (isTopology.value) {
            // topology：实体连线列表（source_node/target_node 已归一化为 source/target）
            const flatEdges = flatTopologyEdges.value
            const parallelCount = {}
            const parallelIndex = {}
            flatEdges.forEach(edge => {
                const key = `${edge.source}-${edge.target}`
                parallelCount[key] = (parallelCount[key] || 0) + 1
            })
            for (const edge of flatEdges) {
                const sourceNode = allNodes.find(n => n.node_id === edge.source)
                const targetNode = allNodes.find(n => n.node_id === edge.target)
                if (!sourceNode || !targetNode) continue

                const sourcePort = edge.source_port || 'exit'
                const key = `${edge.source}-${edge.target}`
                parallelIndex[key] = (parallelIndex[key] || 0) + 1
                const offsetIndex = parallelIndex[key] - 1
                const totalParallel = parallelCount[key]

                pushEdge({
                    sourceNode,
                    targetNode,
                    legacyPort: sourcePort,
                    edgeIdBase: edge.edge_id || `e_${edge.source}_${edge.target}_${parallelIndex[key]}`,
                    isFailFlag: sourcePort === 'failure' || sourcePort === 'fail',
                    edgeId: edge.edge_id,
                    extra: {
                        sourcePort,
                        parallel: { offsetIndex, totalParallel }
                    }
                })
            }
        } else {
            // workflow：从节点 params 派生连线
            deriveWorkflowEdges(dataTasks.value).forEach(derived => {
                const sourceNode = allNodes.find(n => n.node_id === derived.sourceNodeId)
                const targetNode = allNodes.find(n => n.node_id === derived.targetNodeId)
                if (sourceNode && targetNode) {
                    pushEdge({
                        sourceNode,
                        targetNode,
                        legacyPort: derived.legacyPort,
                        edgeIdBase: derived.edgeIdBase,
                        isFailFlag: derived.isFailFlag,
                        extra: derived.extra
                    })
                }
            })
        }

        // 用户实时拉线预览（Step 4 网格化端口：按端口方向绘制预览路径）
        if (drawingConnection.value.active) {
            const sourceNode = allNodes.find(n => n.node_id === drawingConnection.value.sourceNodeId)
            if (sourceNode) {
                const portType = drawingConnection.value.portType
                const startPt = getPortPosition(sourceNode, portType)
                const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }

                const pathStr = getSimpleOrthoPath(startPt, mousePt, portType)
                const arrowDir = getArrowDirection([startPt, mousePt])
                const markerPrefix = portType === 'fail' ? 'fail' : 'succ'
                drawingConnection.value.previewMarkerUrl = `url(#arrow-${markerPrefix}-${arrowDir})`

                edges.push({
                    id: 'temp_drawing',
                    path: pathStr,
                    label: '',
                    isFail: portType === 'fail',
                    markerUrl: drawingConnection.value.previewMarkerUrl,
                    selected: false,
                    labelX: 0,
                    labelY: 0,
                    gridPoints: [],
                    rawPixelPoints: [startPt, mousePt]
                })
            }
        }

        return edges
    })

    // ===== 小地图 =====
    const drawMinimap = () => {
        const canvas = minimapCanvasRef.value
        if (!canvas || !containerRef.value) return
        const ctx = canvas.getContext('2d')
        const mapW = canvas.width
        const mapH = canvas.height

        ctx.clearRect(0, 0, mapW, mapH)
        ctx.fillStyle = '#1e1f29'
        ctx.fillRect(0, 0, mapW, mapH)

        const nodes = renderNodes.value
        const groups = dynamicGroups.value
        if (!nodes.length && !groups.length) return

        let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
        nodes.forEach(n => {
            minX = Math.min(minX, n.position.x - 200)
            minY = Math.min(minY, n.position.y - 200)
            maxX = Math.max(maxX, n.position.x + n.w + 200)
            maxY = Math.max(maxY, n.position.y + n.h + 200)
        })

        const worldW = maxX - minX
        const worldH = maxY - minY
        const scaleX = mapW / worldW
        const scaleY = mapH / worldH
        const mapScale = Math.min(scaleX, scaleY)

        const toMapCoord = (wx, wy) => ({
            x: (wx - minX) * mapScale + (mapW - worldW * mapScale) / 2,
            y: (wy - minY) * mapScale + (mapH - worldH * mapScale) / 2
        })

        ctx.strokeStyle = '#4ed19c33'
        ctx.lineWidth = 1
        groups.forEach(g => {
            const p = toMapCoord(g.box.x, g.box.y)
            ctx.strokeRect(p.x, p.y, g.box.w * mapScale, g.box.h * mapScale)
        })

        nodes.forEach(n => {
            const p = toMapCoord(n.position.x, n.position.y)
            ctx.fillStyle = n.selected ? '#409EFF' : '#4ed19c'
            ctx.fillRect(p.x, p.y, Math.max(4, n.w * mapScale), Math.max(3, n.h * mapScale))
        })

        const containerW = containerRef.value.clientWidth
        const containerH = containerRef.value.clientHeight
        const viewLeft = -viewport.value.x / viewport.value.zoom
        const viewTop = -viewport.value.y / viewport.value.zoom
        const viewW = containerW / viewport.value.zoom
        const viewH = containerH / viewport.value.zoom

        const vpCoord = toMapCoord(viewLeft, viewTop)
        ctx.strokeStyle = '#409EFF'
        ctx.lineWidth = 1.5
        ctx.strokeRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
        ctx.fillStyle = 'rgba(64, 158, 255, 0.1)'
        ctx.fillRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
    }

    const onMinimapClick = (e) => {
        const canvas = minimapCanvasRef.value
        if (!canvas || !containerRef.value) return
        const rect = canvas.getBoundingClientRect()
        const clickX = e.clientX - rect.left
        const clickY = e.clientY - rect.top

        const nodes = renderNodes.value
        let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
        nodes.forEach(n => {
            minX = Math.min(minX, n.position.x - 200)
            minY = Math.min(minY, n.position.y - 200)
            maxX = Math.max(maxX, n.position.x + n.w + 200)
            maxY = Math.max(maxY, n.position.y + n.h + 200)
        })

        const worldW = maxX - minX
        const worldH = maxY - minY
        const mapScale = Math.min(canvas.width / worldW, canvas.height / worldH)

        const targetWorldX = (clickX - (canvas.width - worldW * mapScale) / 2) / mapScale + minX
        const targetWorldY = (clickY - (canvas.height - worldH * mapScale) / 2) / mapScale + minY

        const containerW = containerRef.value.clientWidth
        const containerH = containerRef.value.clientHeight

        viewport.value.x = -(targetWorldX - containerW / (2 * viewport.value.zoom)) * viewport.value.zoom
        viewport.value.y = -(targetWorldY - containerH / (2 * viewport.value.zoom)) * viewport.value.zoom
        drawMinimap()
    }

    watch([renderNodes, dynamicGroups, viewport], () => {
        nextTick(drawMinimap)
    }, { deep: true })

    watch(() => store.uiState.minimapExpanded, (val) => {
        if (val) {
            nextTick(drawMinimap)
        }
    })

    // ===== 鼠标事件 =====
    const onCanvasMouseDown = (e) => {
        // 工具栏/菜单内点击不触发画布平移
        if (e.target.closest('.canvas-toolbar') || e.target.closest('.canvas-context-menu') || e.target.closest('.spawn-menu')) return
        customContextMenu.visible = false

        const isBlankArea = e.target === containerRef.value ||
            e.target.classList.contains('canvas-viewport') ||
            e.target.tagName === 'svg' ||
            e.target.classList.contains('canvas-edges-layer')

        if (isBlankArea) {
            if (e.shiftKey && e.button === 0) {
                spawnMenu.value = {
                    visible: true,
                    x: e.clientX,
                    y: e.clientY,
                    sourceNodeId: null,
                    portType: 'succ',
                    clientX: e.clientX,
                    clientY: e.clientY
                }
                e.stopPropagation()
                return
            }

            localSelectedNodeIds.value = []
            if (isTopology.value) {
                store.selectTopologyNode(null)
            } else {
                store.clearSelection()
                store.setSelectedGroup(null)
            }
            selectedEdgeId.value = null
        }

        if (e.altKey) {
            selectionBox.value = { visible: true, startX: e.clientX, startY: e.clientY, endX: e.clientX, endY: e.clientY }
        } else {
            isPanning.value = true
            panStart.value = { x: e.clientX - viewport.value.x, y: e.clientY - viewport.value.y }
        }
        spawnMenu.value.visible = false
    }

    const onNodeMouseDown = (e, node) => {
        isCtrlHeldRef.value = e.ctrlKey

        draggedSourceGroupSnapshot.value = null
        ghostPlaceholder.value = null

        ghostPlaceholder.value = {
            node_id: `ghost_${node.node_id}`,
            position: { ...node.position },
            w: NODE_GRID_W * GRID_SIZE,
            h: node.h || 120
        }

        if (props.hasGroups) {
            const tasks = dataTasks.value || []
            tasks.forEach((t, tIdx) => {
                const found = (t.nodes || []).find(n => n.node_id === node.node_id)
                if (found) {
                    const groupInfo = dynamicGroups.value[tIdx]
                    if (groupInfo && groupInfo.box) {
                        draggedSourceGroupSnapshot.value = { ...groupInfo.box }
                    }
                }
            })
        }

        if (!isTopology.value && e.ctrlKey) {
            if (localSelectedNodeIds.value.includes(node.node_id)) {
                localSelectedNodeIds.value = localSelectedNodeIds.value.filter(id => id !== node.node_id)
            } else {
                localSelectedNodeIds.value.push(node.node_id)
            }
        } else {
            localSelectedNodeIds.value = [node.node_id]
        }

        if (isTopology.value) {
            store.selectTopologyNode(node.node_id)
        } else {
            store.selectNodes([...localSelectedNodeIds.value])
            store.setSelectedGroup(null)
        }

        draggingNodeId.value = node.node_id
        dragStartMouse.value = { x: e.clientX, y: e.clientY }
        nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
        hasMoved.value = false
        e.stopPropagation()
    }

    const onGlobalMouseMove = (e) => {
        isCtrlHeldRef.value = e.ctrlKey

        if (isPanning.value) {
            viewport.value.x = e.clientX - panStart.value.x
            viewport.value.y = e.clientY - panStart.value.y
        } else if (selectionBox.value.visible) {
            selectionBox.value.endX = e.clientX
            selectionBox.value.endY = e.clientY
        } else if (draggingNodeId.value) {
            const dist = Math.hypot(e.clientX - dragStartMouse.value.x, e.clientY - dragStartMouse.value.y)
            if (dist > 6) {
                hasMoved.value = true
            }

            if (hasMoved.value) {
                const dx = (e.clientX - dragStartMouse.value.x) / viewport.value.zoom
                const dy = (e.clientY - dragStartMouse.value.y) / viewport.value.zoom

                const rawX = nodeInitialPos.value.x + dx
                const rawY = nodeInitialPos.value.y + dy

                localDraftPositions[draggingNodeId.value] = { x: rawX, y: rawY }

                const MIN_GAP = 2 * GRID_SIZE

                const currentDraggingNode = renderNodes.value.find(n => n.node_id === draggingNodeId.value)
                const nodeW = currentDraggingNode?.w || (NODE_GRID_W * GRID_SIZE)
                const nodeH = currentDraggingNode?.h || 120

                const previewX = rawX - MIN_GAP
                const previewY = rawY - MIN_GAP
                const previewW = nodeW + MIN_GAP * 2
                const previewH = nodeH + MIN_GAP * 2

                let isColliding = false
                const currentBox = {
                    minX: rawX,
                    maxX: rawX + nodeW,
                    minY: rawY,
                    maxY: rawY + nodeH
                }

                for (const otherNode of renderNodes.value) {
                    if (otherNode.node_id === draggingNodeId.value) continue
                    const otherPos = localDraftPositions[otherNode.node_id] || otherNode.position || { x: 0, y: 0 }
                    const otherSize = { w: otherNode.w || nodeW, h: otherNode.h || 120 }

                    const expandedOtherBox = {
                        minX: otherPos.x - MIN_GAP,
                        maxX: otherPos.x + otherSize.w + MIN_GAP,
                        minY: otherPos.y - MIN_GAP,
                        maxY: otherPos.y + otherSize.h + MIN_GAP
                    }

                    const isIntersect = !(
                        currentBox.maxX <= expandedOtherBox.minX ||
                        currentBox.minX >= expandedOtherBox.maxX ||
                        currentBox.maxY <= expandedOtherBox.minY ||
                        currentBox.minY >= expandedOtherBox.maxY
                    )

                    if (isIntersect) {
                        isColliding = true
                        break
                    }
                }

                dragPreviewBox.value = {
                    visible: true,
                    x: previewX,
                    y: previewY,
                    w: previewW,
                    h: previewH,
                    hasCollision: isColliding
                }
            }
        } else if (drawingConnection.value.active && containerRef.value) {
            const rect = containerRef.value.getBoundingClientRect()
            const clientX = e.clientX - rect.left
            const clientY = e.clientY - rect.top
            const rawX = (clientX - viewport.value.x) / viewport.value.zoom
            const rawY = (clientY - viewport.value.y) / viewport.value.zoom
            drawingConnection.value.currentX = Math.round(rawX / GRID_SIZE) * GRID_SIZE
            drawingConnection.value.currentY = Math.round(rawY / GRID_SIZE) * GRID_SIZE
        }
    }

    const settleTopologyDrag = (nodeId, finalPos, currentNodeSize) => {
        // 拓扑模式：节点级碰撞推挤（在扁平克隆上计算，避免污染 props）
        const flatClone = JSON.parse(JSON.stringify(flatTopologyNodes.value))
        const enriched = flatClone.map(n => {
            const ports = buildNodePorts(n)
            return {
                ...n,
                w: NODE_WIDTH,
                h: computeCanvasNodeHeight(computeTopologyContentHeight(n), ports.dynamic.length)
            }
        })
        resolveCollisionsAndPushOthers(nodeId, finalPos, enriched, currentNodeSize)

        const moved = []
        for (const n of enriched) {
            if (localDraftPositions[n.node_id]) {
                moved.push({ node_id: n.node_id, position: { ...localDraftPositions[n.node_id] } })
            }
        }
        for (const key of Object.keys(localDraftPositions)) {
            delete localDraftPositions[key]
        }
        if (moved.length) {
            emit('update-node-positions', moved)
        }
        ElMessage.success('节点排版更新成功')
    }

    const settleWorkflowDrag = async (nodeId, isCtrlHeld) => {
        const rawPos = localDraftPositions[nodeId] || nodeInitialPos.value
        const finalPos = {
            x: Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE,
            y: Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
        }

        // 在深拷贝上计算（localTasksOverride 让 dynamicGroups 等 computed 随克隆重算）
        const tasks = JSON.parse(JSON.stringify(dataTasks.value))
        localTasksOverride.value = tasks

        const targetNodeObj = renderNodes.value.find(n => n.node_id === nodeId)
        const currentNodeSize = { w: targetNodeObj?.w || (NODE_GRID_W * GRID_SIZE), h: targetNodeObj?.h || 120 }

        let targetTaskIndex = -1
        let isCreatingNewGroup = false

        if (isCtrlHeld && draggedSourceGroupSnapshot.value) {
            const nodeRectBeforePush = { x: finalPos.x, y: finalPos.y, w: currentNodeSize.w, h: currentNodeSize.h }
            const overlapWithSnapshot = calculateOverlapRatio(nodeRectBeforePush, draggedSourceGroupSnapshot.value)

            if (overlapWithSnapshot === 0) {
                dynamicGroups.value.forEach((g, gIdx) => {
                    let currentSourceTIdx = -1
                    tasks.forEach((t, tI) => {
                        if ((t.nodes || []).some(n => n.node_id === nodeId)) currentSourceTIdx = tI
                    })
                    if (gIdx === currentSourceTIdx) return

                    const ratio = calculateOverlapRatio(nodeRectBeforePush, g.box)
                    if (ratio >= 1.0) {
                        targetTaskIndex = gIdx
                    }
                })

                if (targetTaskIndex === -1) {
                    isCreatingNewGroup = true
                }
            }
        }

        const safePos = resolveCollisionsAndPushOthers(nodeId, finalPos, renderNodes.value, currentNodeSize)

        let sourceTaskIndex = -1
        let sourceNodeObj = null
        tasks.forEach((t, tIdx) => {
            const found = (t.nodes || []).find(n => n.node_id === nodeId)
            if (found) {
                sourceTaskIndex = tIdx
                sourceNodeObj = found
            }
        })

        if (sourceTaskIndex !== -1 && isCtrlHeld && draggedSourceGroupSnapshot.value) {
            const originalTask = tasks[sourceTaskIndex]
            const nodeRectAfterPush = { x: safePos.x, y: safePos.y, w: currentNodeSize.w, h: currentNodeSize.h }
            const overlapWithSnapshot = calculateOverlapRatio(nodeRectAfterPush, draggedSourceGroupSnapshot.value)

            if (overlapWithSnapshot === 0) {
                originalTask.nodes = (originalTask.nodes || []).filter(n => n.node_id !== nodeId)
                sourceNodeObj.position = safePos

                if (targetTaskIndex !== -1) {
                    const targetTask = tasks[targetTaskIndex]
                    if (!targetTask.nodes) targetTask.nodes = []
                    targetTask.nodes.push(sourceNodeObj)
                    ElMessage.success(`节点已被纳入组 [${targetTask.task_name}]`)
                } else if (isCreatingNewGroup) {
                    const newTaskId = `task_${Date.now()}`
                    const newTask = {
                        task_id: newTaskId,
                        task_name: '新建组',
                        loop_count: 1,
                        loop_interval: 0,
                        nodes: [sourceNodeObj]
                    }
                    tasks.push(newTask)
                    ElMessage.success('节点已成功脱离，并自动创建放入【新建组】')
                }
            } else {
                sourceNodeObj.position = safePos
            }
        } else {
            for (const task of tasks) {
                const found = (task.nodes || []).find(n => n.node_id === nodeId)
                if (found) {
                    found.position = safePos
                    break
                }
            }
        }

        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                if (localDraftPositions[n.node_id]) {
                    n.position = localDraftPositions[n.node_id]
                    delete localDraftPositions[n.node_id]
                }
            })
        })

        await nextTick()
        const currentGroupsForCheck = dynamicGroups.value.map(g => ({
            taskId: g.taskId,
            box: { x: g.box.x, y: g.box.y, w: g.box.w, h: g.box.h }
        }))

        let globalAdjustedBoxes = {}
        let activeTaskObj = tasks[sourceTaskIndex] || tasks[tasks.length - 1]
        if (activeTaskObj) {
            const activeGroupId = activeTaskObj.task_id
            const activeGroupInfo = currentGroupsForCheck.find(x => x.taskId === activeGroupId)

            if (activeGroupInfo) {
                const others = currentGroupsForCheck.filter(x => x.taskId !== activeGroupId)
                globalAdjustedBoxes = resolveGroupCollisionsAndPushOthers(activeGroupId, activeGroupInfo.box, others)
            }
        }

        tasks.forEach(t => {
            const newBox = globalAdjustedBoxes[t.task_id]
            const oldGroup = currentGroupsForCheck.find(x => x.taskId === t.task_id)
            if (newBox && oldGroup && oldGroup.box) {
                const shiftX = (Number(newBox.x) || 0) - (Number(oldGroup.box.x) || 0)
                const shiftY = (Number(newBox.y) || 0) - (Number(oldGroup.box.y) || 0)

                if (shiftX !== 0 || shiftY !== 0) {
                    (t.nodes || []).forEach(n => {
                        n.position.x = Math.round((n.position.x + shiftX) / GRID_SIZE) * GRID_SIZE
                        n.position.y = Math.round((n.position.y + shiftY) / GRID_SIZE) * GRID_SIZE
                    })
                }
            }
        })

        const finalTasks = tasks.filter(t => (t.nodes || []).length > 0)
        emit('update-tasks', finalTasks)

        draggedSourceGroupSnapshot.value = null
        ghostPlaceholder.value = null
        delete localDraftPositions[nodeId]

        ElMessage.success('节点排版及组归属更新成功')
    }

    const onGlobalMouseUp = async (e) => {
        isPanning.value = false

        if (selectionBox.value.visible) {
            selectionBox.value.visible = false
        }

        dragPreviewBox.value.visible = false

        const wasDrawing = drawingConnection.value.active
        const sourceId = drawingConnection.value.sourceNodeId
        const portType = drawingConnection.value.portType
        drawingConnection.value.active = false

        if (draggingNodeId.value) {
            const nodeId = draggingNodeId.value
            const isCtrlHeld = isCtrlHeldRef.value || e.ctrlKey
            draggingNodeId.value = false
            isCtrlHeldRef.value = false

            if (hasMoved.value) {
                const rawPos = localDraftPositions[nodeId] || nodeInitialPos.value
                const finalPos = {
                    x: Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE,
                    y: Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
                }
                const targetNodeObj = renderNodes.value.find(n => n.node_id === nodeId)
                const currentNodeSize = { w: targetNodeObj?.w || (NODE_GRID_W * GRID_SIZE), h: targetNodeObj?.h || 120 }

                if (isTopology.value) {
                    settleTopologyDrag(nodeId, finalPos, currentNodeSize)
                } else {
                    await settleWorkflowDrag(nodeId, isCtrlHeld)
                }
            }
            hasMoved.value = false
        }

        // 拖拽空放断开原有连线 / 弹 spawn 菜单
        if (wasDrawing) {
            const hasExisting = isTopology.value
                ? flatTopologyEdges.value.some(ed => ed.source === sourceId && (ed.source_port || 'exit') === (portType || 'exit'))
                : deriveWorkflowEdges(dataTasks.value).some(ed => ed.sourceNodeId === sourceId && ed.legacyPort === portType)

            if (hasExisting) {
                emit('remove-edge', { sourceNodeId: sourceId, legacyPort: portType })
                ElMessage.success('已成功断开连线')
                return
            }

            spawnMenu.value = {
                visible: true,
                x: e.clientX,
                y: e.clientY,
                sourceNodeId: sourceId,
                portType,
                clientX: e.clientX,
                clientY: e.clientY
            }
        }
    }

    const onCanvasWheel = (e) => {
        viewportWheel(e)
        drawMinimap()
    }

    watch(() => store.focusTarget, (target) => {
        if (!target || !containerRef.value) return
        const containerW = containerRef.value.clientWidth
        const containerH = containerRef.value.clientHeight
        let targetX = 0
        let targetY = 0

        if (target.type === 'node') {
            const node = renderNodes.value.find(n => n.node_id === target.id)
            if (node) {
                targetX = node.position.x + node.w / 2
                targetY = node.position.y + node.h / 2
            }
        } else if (target.type === 'group') {
            const group = dynamicGroups.value.find(g => g.groupId === target.id || g.taskId === target.id)
            if (group) {
                targetX = group.box.x + group.box.w / 2
                targetY = group.box.y + group.box.h / 2
            }
        }

        if (targetX !== 0 || targetY !== 0) {
            viewport.value.x = containerW / 2 - targetX * viewport.value.zoom
            viewport.value.y = containerH / 2 - targetY * viewport.value.zoom
            if (typeof drawMinimap === 'function') drawMinimap()
        }
    }, { deep: true })

    // ===== 拉线落点建立连线 =====
    const onNodeMouseUpCard = (e, targetNode) => {
        if (drawingConnection.value.active) {
            const sourceId = drawingConnection.value.sourceNodeId
            const portType = drawingConnection.value.portType

            drawingConnection.value.active = false

            if (sourceId && sourceId !== targetNode.node_id) {
                emit('add-edge', { source: sourceId, target: targetNode.node_id, source_port: portType })
                ElMessage.success(`连线指向 ➔ [${targetNode.node_name}]`)
            }
            e.stopPropagation()
        }
    }

    const onNodeDoubleClick = (e, node) => {
        if (isTopology.value) {
            store.selectTopologyNode(node.node_id)
        } else {
            store.selectNode(node.node_id)
            store.setSelectedGroup(null)
        }
        localSelectedNodeIds.value = [node.node_id]
        e.stopPropagation()
    }

    const openGroupInspector = (e, group) => {
        if (isTopology.value) return
        store.setSelectedGroup(group.groupId)
        store.clearSelection()
        localSelectedNodeIds.value = []
        e.stopPropagation()
    }

    const startGroupDrag = (e, groupId) => {
        if (isTopology.value) return
        e.stopPropagation()
        const startX = e.clientX
        const startY = e.clientY
        let hasGroupMoved = false

        const tasks = JSON.parse(JSON.stringify(dataTasks.value))
        localTasksOverride.value = tasks
        const taskIndex = tasks.findIndex((t, idx) => `group_${t.task_id || idx}` === groupId)
        if (taskIndex === -1) return

        const activeTask = tasks[taskIndex]
        const taskNodes = activeTask.nodes || []

        const initialNodePositions = {}
        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                initialNodePositions[n.node_id] = { x: n.position?.x || 0, y: n.position?.y || 0 }
            })
        })

        const currentGroupInfo = dynamicGroups.value.find(g => g.groupId === groupId)
        if (!currentGroupInfo) return
        const initialBox = { ...currentGroupInfo.box }

        const onMouseMove = (moveEvent) => {
            const dist = Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY)
            if (dist > 6) {
                hasGroupMoved = true
            }

            if (hasGroupMoved) {
                const dx = (moveEvent.clientX - startX) / viewport.value.zoom
                const dy = (moveEvent.clientY - startY) / viewport.value.zoom

                taskNodes.forEach((n) => {
                    localDraftPositions[n.node_id] = {
                        x: initialNodePositions[n.node_id].x + dx,
                        y: initialNodePositions[n.node_id].y + dy
                    }
                })
            }
        }

        const onMouseUp = async () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', onMouseUp)

            if (!hasGroupMoved) {
                localTasksOverride.value = null
                return
            }

            const finalDraftNode = taskNodes[0] ? (localDraftPositions[taskNodes[0].node_id] || taskNodes[0].position) : { x: 0, y: 0 }
            const initDraftNode = taskNodes[0] ? initialNodePositions[taskNodes[0].node_id] : { x: 0, y: 0 }
            const groupDx = (finalDraftNode.x - initDraftNode.x)
            const groupDy = (finalDraftNode.y - initDraftNode.y)

            const rawFinalBox = {
                x: initialBox.x + groupDx,
                y: initialBox.y + groupDy,
                w: initialBox.w,
                h: initialBox.h
            }
            const snappedFinalBox = {
                x: Math.round(rawFinalBox.x / GRID_SIZE) * GRID_SIZE,
                y: Math.round(rawFinalBox.y / GRID_SIZE) * GRID_SIZE,
                w: rawFinalBox.w,
                h: rawFinalBox.h
            }

            const allOtherGroups = dynamicGroups.value.map(g => ({
                taskId: g.taskId,
                box: g.box
            }))

            const adjustedBoxes = resolveGroupCollisionsAndPushOthers(activeTask.task_id, snappedFinalBox, allOtherGroups)

            tasks.forEach(t => {
                const targetBox = adjustedBoxes[t.task_id]
                const origGroup = dynamicGroups.value.find(g => g.taskId === t.task_id)
                if (targetBox && origGroup && origGroup.box) {
                    let taskDeltaX = 0
                    let taskDeltaY = 0

                    if (t.task_id === activeTask.task_id) {
                        taskDeltaX = targetBox.x - initialBox.x
                        taskDeltaY = targetBox.y - initialBox.y
                    } else {
                        const origBox = origGroup.box
                        taskDeltaX = targetBox.x - origBox.x
                        taskDeltaY = targetBox.y - origBox.y
                    }

                    (t.nodes || []).forEach(n => {
                        const initPos = initialNodePositions[n.node_id]
                        if (initPos) {
                            const finalX = Math.round((initPos.x + taskDeltaX) / GRID_SIZE) * GRID_SIZE
                            const finalY = Math.round((initPos.y + taskDeltaY) / GRID_SIZE) * GRID_SIZE
                            n.position = { x: finalX, y: finalY }
                        }
                    })
                }
                (t.nodes || []).forEach(n => {
                    delete localDraftPositions[n.node_id]
                })
            })

            const finalTasks = tasks.filter(t => (t.nodes || []).length > 0)
            emit('update-tasks', finalTasks)
            ElMessage.success('任务组移动及互斥排版保存成功')
        }

        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', onMouseUp)
    }

    const startConnection = (e, nodeId, portType) => {
        if (!containerRef.value) return
        const rect = containerRef.value.getBoundingClientRect()
        const clientX = e.clientX - rect.left
        const clientY = e.clientY - rect.top

        const sourceNode = renderNodes.value.find(n => n.node_id === nodeId)
        const sourcePt = sourceNode ? getPortPosition(sourceNode, portType) : null

        drawingConnection.value = {
            active: true,
            sourceNodeId: nodeId,
            portType,
            sourceX: sourcePt?.x ?? 0,
            sourceY: sourcePt?.y ?? 0,
            currentX: (clientX - viewport.value.x) / viewport.value.zoom,
            currentY: (clientY - viewport.value.y) / viewport.value.zoom,
            previewMarkerUrl: 'url(#arrow-preview)'
        }
        e.stopPropagation()
    }

    const onEdgeClick = (edge) => {
        selectedEdgeId.value = edge.id
        ElMessage.info('已选中连线')
    }

    // ===== 快捷键删除选中连线（Delete/Backspace 优先删边，否则回退批量删除节点） =====
    const checkInputFocus = () => {
        const el = document.activeElement
        if (!el) return false
        const tag = el.tagName?.toLowerCase()
        return tag === 'input' || tag === 'textarea' || el.isContentEditable || el.classList.contains('el-input__inner')
    }

    const globalKeydownHandler = (e) => {
        if (e.key === 'Control') {
            isCtrlHeldRef.value = true
        }

        if ((e.key === 'Delete' || e.key === 'Backspace') && !checkInputFocus()) {
            if (selectedEdgeId.value) {
                const edge = computedEdges.value.find(item => item.id === selectedEdgeId.value)
                if (edge) {
                    emit('remove-edge', {
                        sourceNodeId: edge.sourceNodeId,
                        targetNodeId: edge.targetNodeId,
                        legacyPort: edge.legacyPort,
                        candIndex: edge.candIndex,
                        edge_id: edge.edgeId
                    })
                    selectedEdgeId.value = null
                    ElMessage.success('已成功断开连线')
                    return
                }
            }
            if (props.onDelete) {
                props.onDelete()
            }
        }
    }

    const globalKeyupHandler = (e) => {
        if (e.key === 'Control') {
            isCtrlHeldRef.value = false
        }
    }

    const createAndConnectNode = (nodeType) => {
        if (!nodeType) return
        const sourceId = spawnMenu.value.sourceNodeId
        const portType = spawnMenu.value.portType

        const targetClientX = spawnMenu.value.clientX || customContextMenu.clientX || window.innerWidth / 2
        const targetClientY = spawnMenu.value.clientY || customContextMenu.clientY || window.innerHeight / 2

        spawnMenu.value.visible = false
        customContextMenu.visible = false

        if (!containerRef.value) return
        const rect = containerRef.value.getBoundingClientRect()

        const spawnX = targetClientX - rect.left
        const spawnY = targetClientY - rect.top

        const rawSpawnX = (spawnX - viewport.value.x) / viewport.value.zoom - (NODE_GRID_W * GRID_SIZE) / 2
        const rawSpawnY = (spawnY - viewport.value.y) / viewport.value.zoom - 40

        const position = {
            x: Math.round(rawSpawnX / GRID_SIZE) * GRID_SIZE,
            y: Math.round(rawSpawnY / GRID_SIZE) * GRID_SIZE
        }

        const nodeId = isTopology.value ? `topo_${Date.now()}` : `node_${Date.now()}`
        const groupId = customContextMenu.targetType === 'canvas_in_group' ? customContextMenu.targetId : null

        emit('create-node', { nodeId, type: nodeType, position, groupId, sourceNodeId: sourceId, portType })

        localSelectedNodeIds.value = [nodeId]
        if (isTopology.value) {
            store.selectTopologyNode(nodeId)
        } else {
            store.selectNode(nodeId)
        }

        const chineseLabel = getNodeShortLabel(nodeType)
        ElMessage.success(`成功创建节点: [${chineseLabel}]`)
    }

    // ===== Undo/Redo 快捷键 =====
    function _onUndoHotkey(e) {
        const ctrl = e.ctrlKey || e.metaKey
        if (!ctrl) return
        if (e.key === 'z' && !e.shiftKey) {
            e.preventDefault(); e.stopPropagation()
            if (props.onUndo) props.onUndo()
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
            e.preventDefault(); e.stopPropagation()
            if (props.onRedo) props.onRedo()
        }
    }

    onMounted(() => {
        window.addEventListener('mousemove', onGlobalMouseMove)
        window.addEventListener('mouseup', onGlobalMouseUp)
        window.addEventListener('keydown', globalKeydownHandler)
        window.addEventListener('keyup', globalKeyupHandler)
        window.addEventListener('keydown', _onUndoHotkey, true)

        // 跟踪容器尺寸变化（世界图层按可见区域重算 SVG 盒与网格）
        if (containerRef.value) {
            const updateContainerSize = () => {
                containerSize.width = containerRef.value?.clientWidth || 0
                containerSize.height = containerRef.value?.clientHeight || 0
            }
            updateContainerSize()
            containerResizeObserver = new ResizeObserver(updateContainerSize)
            containerResizeObserver.observe(containerRef.value)
        }

        fitViewToNodes()
        nextTick(drawMinimap)
    })

    onUnmounted(() => {
        window.removeEventListener('mousemove', onGlobalMouseMove)
        window.removeEventListener('mouseup', onGlobalMouseUp)
        window.removeEventListener('keydown', globalKeydownHandler)
        window.removeEventListener('keyup', globalKeyupHandler)
        window.removeEventListener('keydown', _onUndoHotkey, true)
        containerResizeObserver?.disconnect()
    })
</script>
