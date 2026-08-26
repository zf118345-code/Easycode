<!-- frontend/src/components/canvas/CanvasView.vue
  统一画布组件（Step 3）：workflow 与 topology 两种模式共享全部交互。
  数据只读（props.tasks / props.edges），所有数据变更通过 emit 事件回传包装器执行；
    交互状态（选中/断点/运行高亮/聚焦）经 useIdeStore 读取。
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
                :edges="visibleComputedEdges"
                :drawing-connection="drawingConnection"
                :viewport="viewport"
                :container-size="containerSize"
                :hovered-port="hoveredPort"
                :editing-edge-id="editingEdgeId"
                @edge-click="onEdgeClick"
                @edge-hover="onEdgeHover"
                @edge-double-click="addWaypointFromEdgeEvent"
                @edge-contextmenu="openEdgeContextMenu"
                @waypoint-focus="focusWaypoint"
                @waypoint-mousedown="startWaypointDrag" />

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
                    <AlertTriangle v-if="dragPreviewBox.hasCollision" :size="13" />
                    <CheckCircle2 v-else :size="13" />
                    {{ dragPreviewBox.hasCollision ? '将自动推挤周围节点' : '空间充足' }}
                </div>
            </div>

            <!-- 节点卡片层（共享子组件） -->
            <CanvasNodeCard
                v-for="node in visibleRenderNodes"
                :key="node.node_id"
                :node="node"
                :selected="node.selected"
                :is-active-debug="store.currentActiveNodeId === node.node_id"
                :has-breakpoint="hasBreakpoints ? uiStore.hasBreakpoint(node.node_id) : false"
                :current-project-path="store.currentProjectPath"
                :asset-revision="store.assetPreviewVersion"
                :mode="mode"
                :hovered-port="hoveredPort"
                @node-mousedown="onNodeMouseDown"
                @node-mouseup="onNodeMouseUpCard"
                @node-dblclick="onNodeDoubleClick"
                @node-contextmenu="openNodeContextMenu"
                @toggle-breakpoint="handleToggleBreakpoint"
                @start-connection="startConnection"
                @row-hover="onRowHover"
                @node-hover="onNodeHover"
                @image-loaded="(data) => onImageLoaded(data)" />
        </div>

        <!-- 全景缩略图导航面板（两模式共用） -->
        <div class="minimap-container" v-show="store.uiState.minimapExpanded" title="全景导航：点击缩略图定位">
            <canvas ref="minimapCanvasRef" width="150" height="110" aria-label="画布全景导航" @click="onMinimapClick" />
        </div>

        <!-- 框选 UI -->
        <div v-if="selectionBox.visible" class="selection-box" :style="selectionBoxStyle" />

        <!-- 缩放工具栏（两模式共用） -->
        <div class="canvas-toolbar">
            <button class="toolbar-btn" type="button" aria-label="放大画布" @click="zoomIn" title="放大">
                <Plus :size="16" />
            </button>
            <button class="toolbar-btn" type="button" aria-label="缩小画布" @click="zoomOut" title="缩小">
                <Minus :size="16" />
            </button>
            <button class="toolbar-btn" type="button" aria-label="重置画布视图" @click="resetView" title="重置视图">
                <Maximize :size="16" />
            </button>
            <span class="toolbar-separator" aria-hidden="true" />
            <button class="toolbar-btn" type="button" aria-label="新建节点" @click="createNodeAtViewportCenter" title="新建节点">
                <CirclePlus :size="16" />
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
            :session-active="store.isRunning || store.isPaused"
            :show-debug-items="hasBreakpoints"
            :has-clipboard="hasSnapshotContent(clipboardSubgraph)"
            :run-disabled="!canRunSelected"
            @create-and-connect="createAndConnectNode"
            @run-from-node="handleRunFromNode"
            @toggle-breakpoint="handleToggleBreakpoint"
            @resume-execution="store.resumeExecution"
            @step-over="store.stepOverExecution"
            @stop-execution="store.stopExecution"
            @delete-node="handleDeleteNode"
            @add-waypoint="addWaypointFromContextMenu"
            @reset-edge-routing="resetSelectedEdgeRouting"
            @canvas-new-node="handleCanvasNewNode"
            @copy-node="handleCopyNode"
            @paste-node="handlePasteNode"
            @dismiss="dismissCanvasMenus" />
    </div>
</template>

<script setup>
    import { ref, computed, onMounted, onUnmounted, reactive, nextTick, watch } from 'vue'
    import { useIdeStore, useUiStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { Plus, Minus, Maximize, AlertTriangle, CheckCircle2, CirclePlus } from 'lucide-vue-next'
    import {
        computeEdgePath,
        getSimpleOrthoPath,
        getSimpleOrthoPoints,
        registerRouteUsage
    } from '@/utils/canvasRouter'
    import {
        normalizePortType, normalizeNodeList,
        getPortPosition, getArrowDirection
    } from '@/utils/nodeModel'
    import { NODE_WIDTH, computeCanvasNodeHeight, filterEdgesToViewport, filterNodesToViewport } from '@/utils/canvasShared'
    import { getNodeContentSpec, estimateNodeContentHeight } from '@/config/nodeRegistry'
    import { getNextZIndex } from '@/utils/zIndexManager'
    import { deriveEdges } from '@/utils/workflowEdgeModel'
    import { buildNodePorts, getPrimarySourcePort, getSourcePortDescriptors } from '@/utils/portModel'
    import { useRunFromSelection } from '@/composables/useRunFromSelection'
    import { buildSubgraphSnapshot, findSelectionPath, hasSnapshotContent } from '@/utils/graphSelection'
    import {
        applyEdgeVisualStates,
        applyLineJumps,
        applyMicroLanes,
        findNearestFreeWaypoint,
        normalizeEdgeRouting
    } from '@/utils/edgePresentation'
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
        hasBreakpoints: { type: Boolean, default: false },
        // 快捷键回调（由包装器注入）
        onSave: { type: Function, default: null },
        onDelete: { type: Function, default: null },
        onSelectAll: { type: Function, default: null },
        onUndo: { type: Function, default: null },
        onRedo: { type: Function, default: null }
    })

    const emit = defineEmits([
        'update-tasks',            // (tasks) 节点拖拽结算后的完整流程数组（两 Tab 同构）
        'update-geometry',
        'add-edge',                // ({source, target, source_port})
        'remove-edge',             // ({sourceNodeId, sourcePort, candIndex, edge_id, targetNodeId})
        'update-edge-routing',     // ({edgeId, routing}) editor-only waypoints
        'create-node',             // ({nodeId, type, position, groupId, sourceNodeId, portType, params?, nodeName?})
        'paste-subgraph',          // ({snapshot, position, groupId, sourceNodeId, sourcePort, sourcePortId})
        'delete-node'              // ({nodeId, taskId})
    ])

    const store = useIdeStore()
    const uiStore = useUiStore()
    const { canRun: canRunSelected, runSelectedNode } = useRunFromSelection()

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
        onDelete: false,
        onSelectAll: props.onSelectAll || (() => uiStore.selectAllNodes())
    })

    // ===== 视口 / 拖拽 / 连线 / 菜单 =====
    const { viewport, isPanning, panStart, viewportStyle, onCanvasWheel: viewportWheel, zoomIn, zoomOut, resetView } = useViewport()

    const dragComposable = useNodeDrag({
        viewport,
        getRenderNodes: () => renderNodes.value,
        GRID_SIZE,
        NODE_GRID_W
    })
    const {
        draggingNodeId, hasMoved, isCtrlHeldRef, dragPreviewBox,
        localDraftPositions, selectionBox, resolveCollisionsAndPushOthers
    } = dragComposable

    const { drawingConnection } = useConnection()
    const { customContextMenu, spawnMenu } = useContextMenu()
    const dismissCanvasMenus = () => {
        customContextMenu.visible = false
        spawnMenu.value.visible = false
    }

    const menuZIndex = ref(3000)
    const dynamicImageHeights = reactive({})
    const tallImageFlags = reactive({})
    const selectedEdgeId = computed({
        get: () => store.selectedEdgeIds?.[0] || null,
        set: value => value ? store.selectEdge(value) : store.clearEdgeSelection()
    })
    const hoveredPort = ref('')   // 行 ↔ 端口 ↔ 连线 悬停联动（存端口名，如 branch_1 / exit_0）
    const hoveredNodeId = ref('')
    const hoveredEdgeId = ref('')
    const editingEdgeId = ref('')
    const waypointDrafts = reactive({})
    const waypointDrag = reactive({ active: false, edgeId: '', waypointId: '', index: -1 })
    const selectedWaypoint = reactive({ edgeId: '', waypointId: '' })
    const localSelectedNodeIds = computed(() => store.selectedNodeIds || [])
    // 边路径缓存：key = 两端点(id/坐标/高度)+端口+选项+障碍签名（排除被拖节点）
    const routeCache = new Map()

    // ===== 选中状态（三种画布共用 uiStore 同一套选中） =====
    const clearSelection = () => {
        store.clearSelection()
    }

    // 拖拽辅助状态
    const dragStartMouse = ref({ x: 0, y: 0 })
    const nodeInitialPos = ref({ x: 0, y: 0 })
    const dragInitialPositions = ref(new Map())

    // 拖拽结算期间用本地克隆覆盖数据源；包装器保存后 props 更新并清空 override。
    const localTasksOverride = ref(null)
    const dataTasks = computed(() => localTasksOverride.value || props.tasks)
    watch(() => props.tasks, () => { localTasksOverride.value = null })

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

    // ===== 统一扁平图适配（主流程、函数、页面地图共用渲染/交互层） =====

    // CanvasPage 将当前唯一活动图包装为单元素 tasks，供既有渲染层消费。
    const flatNodes = computed(() => {
        const tasks = dataTasks.value || []
        const list = []
        tasks.forEach((task) => {
            (task.nodes || []).forEach((node, nIndex) => {
                list.push({
                    ...node,
                    _taskId: task.task_id,
                    _fallbackPos: { x: 60 + (nIndex % 3) * 200, y: 60 + Math.floor(nIndex / 3) * 120 }
                })
            })
        })
        return list
    })

    // 扁平边：统一结构 { sourceNodeId, targetNodeId, sourcePort, isFailFlag, edgeId?, extra }
    const flatEdges = computed(() => deriveEdges(props.edges))
    const selectedNodeIdSet = computed(() => new Set(localSelectedNodeIds.value))

    const FAILURE_PORT_TYPES = ['image_recognition', 'ocr_recognition', 'branch', 'logic_check']

    // 行/端口悬停联动：候选行、出口行、端口悬停时高亮对应端口与其出边（EdgeLayer 消费 hoveredPort）
    const onRowHover = (portName) => {
        hoveredPort.value = portName || ''
    }
    const onNodeHover = nodeId => {
        hoveredNodeId.value = nodeId || ''
    }
    const onEdgeHover = edge => {
        hoveredEdgeId.value = edge?.id || ''
    }

    // 内容区高度（注册表驱动，两模式同一套估算；图片节点用加载后的实际宽高比二次修正；
    // page_state 出口行数由动态端口推导（bound + pending 虚线占位））
    const resolveContentHeight = (node, dynamicCount) => {
        const nodeType = node.type || node.node_type
        const spec = getNodeContentSpec(nodeType)
        if (!spec) return 0
        if (spec.kind === 'image') {
            return Math.max(spec.minHeight, dynamicImageHeights[node.node_id] || 0)
        }
        return estimateNodeContentHeight(node, dynamicCount)
    }

    // 拖动一个节点会逐帧更新 localDraftPositions。缓存未变化节点的渲染
    // 对象，避免 Vue 同时重渲染画布上其他图片、端口和内容卡片。
    const renderNodeCache = new Map()

    // 渲染节点（两模式单一实现：统一遍历扁平节点流，尺寸/端口/选中逻辑完全共用）
    const renderNodes = computed(() => {
        const functionsById = new Map(
            (store.blueprint?.functions || []).map(item => [item.function_id, item])
        )
        const liveIds = new Set()
        const raw = flatNodes.value.map(n => {
            liveIds.add(n.node_id)
            const targetFunction = (n.node_type || n.type) === 'call_function'
                ? functionsById.get(n.params?.function_id)
                : null
            const rawPos = localDraftPositions[n.node_id] || n.position || n._fallbackPos || { x: 0, y: 0 }
            const selected = selectedNodeIdSet.value.has(n.node_id)
            const previous = renderNodeCache.get(n.node_id)
            const cacheState = {
                source: n,
                params: n.params,
                positionSource: rawPos,
                positionX: rawPos.x,
                positionY: rawPos.y,
                edges: props.edges,
                edgeCount: props.edges.length,
                selected,
                nodeName: n.node_name,
                nodeType: n.node_type || n.type,
                delay: n.delay_before,
                loop: n.loop_count,
                enabled: n.enabled,
                functionOutcomes: targetFunction?.outcomes,
                functionOutcomeCount: targetFunction?.outcomes?.length || 0,
                imageHeight: dynamicImageHeights[n.node_id],
                tallImage: tallImageFlags[n.node_id]
            }
            if (
                previous
                && Object.keys(cacheState).every(key => previous.state[key] === cacheState[key])
            ) return previous.node

            const portNode = targetFunction ? { ...n, _functionOutcomes: targetFunction.outcomes || [] } : n
            const ports = buildNodePorts(portNode, props.edges, FAILURE_PORT_TYPES)
            const gridX = Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE
            const gridY = Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
            const w = NODE_WIDTH
            const h = computeCanvasNodeHeight(resolveContentHeight(n, ports.dynamic.length), ports.dynamic.length)
            const rendered = {
                ...portNode,
                node_type: n.node_type || n.type,
                node_name: n.node_name || n.label || n.page_id || '未命名',
                position: { x: gridX, y: gridY },
                w,
                h,
                size: { w, h },
                ports,
                selected
            }
            renderNodeCache.set(n.node_id, { state: cacheState, node: rendered })
            return rendered
        })
        for (const nodeId of renderNodeCache.keys()) {
            if (!liveIds.has(nodeId)) renderNodeCache.delete(nodeId)
        }
        return raw
    })

    const renderNodeById = computed(() => new Map(renderNodes.value.map(node => [node.node_id, node])))
    const visibleRenderNodes = computed(() => {
        // Keep full geometry for routing/minimap, but mount only nearby cards.
        return filterNodesToViewport(
            renderNodes.value,
            viewport.value,
            containerSize,
            selectedNodeIdSet.value,
            draggingNodeId.value
        )
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

            scheduleMinimapDraw()
        })
    }

    const clientToWorld = (clientX, clientY) => {
        const rect = containerRef.value?.getBoundingClientRect?.() || { left: 0, top: 0 }
        return {
            x: (clientX - rect.left - viewport.value.x) / viewport.value.zoom,
            y: (clientY - rect.top - viewport.value.y) / viewport.value.zoom
        }
    }

    const onContextMenu = (e) => {
        e.preventDefault()
        menuZIndex.value = getNextZIndex()  // ⚡ 不传事件对象（此前被当作 offset 拼接成字符串）
        customContextMenu.visible = false

        const nodeCard = e.target.closest('.canvas-node-card')
        if (nodeCard) {
            const nodeId = nodeCard.getAttribute('data-node-id')
            const nodeObj = renderNodes.value.find(n => n.node_id === nodeId)
            if (nodeObj) {
                if (!localSelectedNodeIds.value.includes(nodeObj.node_id)) {
                    store.selectNode(nodeObj.node_id)
                }
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

        customContextMenu.visible = true
        customContextMenu.x = e.clientX
        customContextMenu.y = e.clientY
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY
        customContextMenu.targetType = 'canvas_public'
        customContextMenu.targetId = null
        customContextMenu.targetName = ''
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
        customContextMenu.visible = false
        await runSelectedNode()
    }

    function openNodeContextMenu(e, node) {
        if (!localSelectedNodeIds.value.includes(node.node_id)) {
            store.selectNode(node.node_id)
        }
        customContextMenu.visible = true
        customContextMenu.targetType = 'node'
        customContextMenu.targetId = node.node_id
        customContextMenu.targetName = node.node_name
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY
        customContextMenu.x = e.clientX + 8
        customContextMenu.y = e.clientY + 8
        menuZIndex.value = getNextZIndex()
        spawnMenu.value.visible = false
    }

    function handleToggleBreakpoint(nodeId) {
        if (!props.hasBreakpoints || !nodeId) return
        const added = uiStore.toggleBreakpoint(nodeId)
        customContextMenu.visible = false
        ElMessage.info(
            added ? `已设置断点：${nodeId}` : `已移除断点：${nodeId}`
        )
    }

    const handleDeleteNode = () => {
        const nodeId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!nodeId) return

        const taskId = findTargetTaskId(nodeId)
        emit('delete-node', { nodeId, taskId })
    }

    const handleCanvasNewNode = () => {
        customContextMenu.visible = false
        spawnMenu.value = {
            visible: true,
            x: customContextMenu.x,
            y: customContextMenu.y,
            sourceNodeId: null,
            portType: 'success',
            clientX: customContextMenu.clientX,
            clientY: customContextMenu.clientY
        }
    }

    const createNodeAtViewportCenter = () => {
        const rect = containerRef.value?.getBoundingClientRect?.()
        if (!rect) return
        customContextMenu.visible = false
        const clientX = rect.left + rect.width / 2
        const clientY = rect.top + rect.height / 2
        spawnMenu.value = {
            visible: true,
            x: clientX,
            y: clientY,
            sourceNodeId: null,
            portType: 'success',
            sourcePortId: 'success',
            clientX,
            clientY
        }
    }

    // ===== 子图复制 / 粘贴（Ctrl+C / Ctrl+V 与右键菜单） =====
    const clipboardSubgraph = ref(null)
    const lastMousePos = ref({ x: 0, y: 0 })   // 最近鼠标位置（世界坐标），Ctrl+V 落点兜底

    const handleCopyNode = () => {
        const targetId = customContextMenu.targetId || localSelectedNodeIds.value[0]
        const selectedIds = localSelectedNodeIds.value.includes(targetId)
            ? [...localSelectedNodeIds.value]
            : (targetId ? [targetId] : [])
        const snapshot = buildSubgraphSnapshot(dataTasks.value, props.edges, selectedIds)
        if (!hasSnapshotContent(snapshot)) {
            ElMessage.warning('请先选中要复制的节点')
            return
        }
        clipboardSubgraph.value = snapshot
        customContextMenu.visible = false
        ElMessage.success(`已复制 ${snapshot.nodes.length} 个节点及 ${snapshot.edges.length} 条内部连线`)
    }

    const handlePasteNode = () => {
        customContextMenu.visible = false
        if (!hasSnapshotContent(clipboardSubgraph.value)) {
            ElMessage.warning('剪贴板为空，请先复制节点或子图 (Ctrl+C)')
            return
        }
        pasteClipboardNode()
    }

    const pasteClipboardNode = () => {
        if (!hasSnapshotContent(clipboardSubgraph.value)) return
        let position
        let sourceNodeId = null
        let sourcePort = 'success'
        let sourcePortId = 'success'

        if (localSelectedNodeIds.value.length === 1) {
            // 选中一个节点：把复制子图的首节点插入其主出口。
            const sel = renderNodes.value.find(n => n.node_id === localSelectedNodeIds.value[0])
            if (sel) {
                sourceNodeId = sel.node_id
                const primaryPort = getPrimarySourcePort(sel, props.edges)
                sourcePort = primaryPort.key
                sourcePortId = primaryPort.stableId || primaryPort.key
                position = {
                    x: Math.round((sel.position.x + sel.w + 40) / GRID_SIZE) * GRID_SIZE,
                    y: sel.position.y
                }
            }
        }
        if (!position) {
            // 无选中：粘贴到最近鼠标位置（世界坐标）
            const rect = containerRef.value?.getBoundingClientRect()
            const cx = rect ? lastMousePos.value.x : 0
            const cy = rect ? lastMousePos.value.y : 0
            position = {
                x: Math.round(cx / GRID_SIZE) * GRID_SIZE,
                y: Math.round(cy / GRID_SIZE) * GRID_SIZE
            }
        }

        emit('paste-subgraph', {
            snapshot: JSON.parse(JSON.stringify(clipboardSubgraph.value)),
            position,
            sourceNodeId,
            sourcePort,
            sourcePortId
        })
    }

    // ===== 连线计算：几何与视觉状态分离，选择/执行变化不再触发 A* =====
    const routedEdges = computed(() => {
        const allNodes = renderNodes.value
        const activeDraggingId = draggingNodeId.value
        const isActuallyMoving = hasMoved.value
        const movingIds = activeDraggingId && isActuallyMoving && localSelectedNodeIds.value.includes(activeDraggingId)
            ? new Set(localSelectedNodeIds.value)
            : new Set(activeDraggingId ? [activeDraggingId] : [])

        const routerNodes = normalizeNodeList(allNodes)
        const segmentCosts = new Map()
        const crossingCosts = new Map()
        const edges = []

        // 障碍签名：排除正在拖拽的节点（拖拽期间其他边形状稳定，落定后签名变化全量重算）
        let obstacleSig = ''
        for (const n of allNodes) {
            if (activeDraggingId && isActuallyMoving && movingIds.has(n.node_id)) continue
            obstacleSig += `${n.node_id}:${n.position.x},${n.position.y},${n.w},${n.h}|`
        }

        const stableRoutingSig = (props.edges || []).map(edge => {
            const routing = normalizeEdgeRouting(edge.routing)
            return `${edge.edge_id}:${routing.waypoints.map(point => `${point.id}@${point.x},${point.y}`).join(';')}`
        }).join('|')
        const edgeSetSig = flatEdges.value.map(edge => `${edge.edgeId}:${edge.sourceNodeId}>${edge.targetNodeId}:${edge.sourcePort}`).join('|')

        const pushEdge = ({ sourceNode, targetNode, sourcePort, edgeIdBase, isFailFlag, extra = {}, edgeId, candIndex }) => {
            const standardPort = normalizePortType(sourcePort)
            const isThisEdgeDragging = activeDraggingId && isActuallyMoving &&
                (movingIds.has(sourceNode.node_id) || movingIds.has(targetNode.node_id))
            const routing = normalizeEdgeRouting(
                waypointDrafts[edgeIdBase]
                    ? { mode: 'manual', waypoints: waypointDrafts[edgeIdBase] }
                    : extra?.routing
            )

            let path = ''
            let arrowDir = 'down'
            let rawPixelPoints = []

            const computeRoute = () => {
                const result = computeEdgePath(sourceNode, targetNode, routerNodes, standardPort, {
                    waypoints: routing.waypoints,
                    segmentCosts,
                    crossingCosts
                })
                path = result.pathD
                arrowDir = result.arrowDir
                rawPixelPoints = result.points || []
            }

            try {
                if (isThisEdgeDragging) {
                    // 拖拽热路径只画轻量正交预览，松手后再恢复完整 A*。
                    const start = getPortPosition(sourceNode, standardPort)
                    const end = getPortPosition(targetNode, 'entry')
                    rawPixelPoints = getSimpleOrthoPoints(start, end, standardPort)
                    path = getSimpleOrthoPath(start, end, standardPort)
                    arrowDir = getArrowDirection(rawPixelPoints)
                } else {
                    // 静态：几何、边集合和持久转接点共同作为缓存签名。
                    const key = [
                        edgeSetSig, stableRoutingSig,
                        routing.waypoints.map(point => `${point.id}@${point.x},${point.y}`).join(';'),
                        sourceNode.node_id, sourceNode.position.x, sourceNode.position.y, sourceNode.h,
                        targetNode.node_id, targetNode.position.x, targetNode.position.y, targetNode.h,
                        standardPort, obstacleSig
                    ].join('|')
                    const cached = routeCache.get(key)
                    if (cached) {
                        path = cached.path
                        arrowDir = cached.arrowDir
                        rawPixelPoints = cached.rawPixelPoints
                    } else {
                        computeRoute()
                        if (routeCache.size > 1500) routeCache.clear()
                        routeCache.set(key, { path, arrowDir, rawPixelPoints })
                    }
                }
            } catch (e) {
                console.warn('[CanvasView] computeEdgePath 失败，使用兜底路径:', e)
                const sPt = getPortPosition(sourceNode, sourcePort)
                const ePt = getPortPosition(targetNode, 'entry')
                path = getSimpleOrthoPath(sPt, ePt, standardPort)
                rawPixelPoints = [sPt, ePt]
                arrowDir = getArrowDirection(rawPixelPoints)
            }

            registerRouteUsage(segmentCosts, crossingCosts, rawPixelPoints)

            const isFail = !!isFailFlag
            const markerPrefix = isFail ? 'fail' : 'succ'

            edges.push({
                id: edgeIdBase,
                sourceNodeId: sourceNode.node_id,
                targetNodeId: targetNode.node_id,
                typeFlag: sourcePort === 'success' ? 'success' : (sourcePort === 'failure' ? 'failure' : 'branch'),
                sourcePort,
                candIndex: candIndex ?? extra?.candIndex,
                edgeId,
                ...extra,
                path,
                isFail,
                markerUrl: `url(#arrow-${markerPrefix}-${arrowDir})`,
                selected: false,
                rawPixelPoints,
                waypoints: routing.waypoints
            })
        }

        // 稳定顺序保证通道成本、动态端口和微车道不会因数组渲染顺序抖动。
        const corridorCount = {}
        const flatEdgeList = [...flatEdges.value].sort((a, b) => {
            const sourceCompare = String(a.sourceNodeId).localeCompare(String(b.sourceNodeId), 'zh-CN', { numeric: true })
            const portCompare = String(a.sourcePort).localeCompare(String(b.sourcePort), 'zh-CN', { numeric: true })
            const targetCompare = String(a.targetNodeId).localeCompare(String(b.targetNodeId), 'zh-CN', { numeric: true })
            return sourceCompare || portCompare || targetCompare || String(a.edgeId).localeCompare(String(b.edgeId))
        })
        for (const derived of flatEdgeList) {
            const sourceNode = renderNodeById.value.get(derived.sourceNodeId)
            const targetNode = renderNodeById.value.get(derived.targetNodeId)
            if (!sourceNode || !targetNode) continue

            const key = `${derived.sourceNodeId}-${derived.targetNodeId}`
            corridorCount[key] = (corridorCount[key] || 0) + 1

            pushEdge({
                sourceNode,
                targetNode,
                sourcePort: derived.sourcePort,
                edgeIdBase: derived.edgeIdBase || `e_${derived.sourceNodeId}_${derived.targetNodeId}_${corridorCount[key]}`,
                isFailFlag: derived.isFailFlag,
                edgeId: derived.edgeId,
                candIndex: derived.candIndex,
                extra: derived.extra
            })
        }

        return applyLineJumps(applyMicroLanes(edges))
    })

    const computedEdges = computed(() => {
        const edges = applyEdgeVisualStates(routedEdges.value, {
            selectedNodeIds: localSelectedNodeIds.value,
            hoveredNodeId: hoveredNodeId.value,
            selectedEdgeIds: selectedEdgeId.value
                ? [selectedEdgeId.value]
                : (hoveredEdgeId.value ? [hoveredEdgeId.value] : (store.selectedEdgeIds || [])),
            previousActiveNodeId: store.previousActiveNodeId,
            currentActiveNodeId: store.currentActiveNodeId,
            executionRunning: store.isRunning
        })

        // 用户实时拉线预览：无箭头（终点用发光球，由 CanvasEdgeLayer 渲染）
        if (drawingConnection.value.active) {
            const sourceNode = renderNodeById.value.get(drawingConnection.value.sourceNodeId)
            if (sourceNode) {
                const portType = drawingConnection.value.portType
                const startPt = getPortPosition(sourceNode, portType)
                const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }

                const pathStr = getSimpleOrthoPath(startPt, mousePt, portType)

                edges.push({
                    id: 'temp_drawing',
                    path: pathStr,
                    isFail: portType === 'failure',
                    markerUrl: '',
                    selected: false,
                    gridPoints: [],
                    rawPixelPoints: [startPt, mousePt]
                })
            }
        }
        return edges
    })

    const visibleComputedEdges = computed(() => filterEdgesToViewport(
        computedEdges.value,
        viewport.value,
        containerSize,
        renderNodes.value.length > 250 ? 250 : Number.MAX_SAFE_INTEGER
    ))

    // ===== 小地图 =====
    let minimapFrame = 0
    const readCanvasToken = (name, fallback) => {
        const host = containerRef.value
        if (!host || typeof globalThis.getComputedStyle !== 'function') return fallback
        return globalThis.getComputedStyle(host).getPropertyValue(name).trim() || fallback
    }

    const drawMinimap = () => {
        const canvas = minimapCanvasRef.value
        if (!canvas || !containerRef.value) return
        const ctx = canvas.getContext('2d')
        const mapW = canvas.width
        const mapH = canvas.height

        ctx.clearRect(0, 0, mapW, mapH)
        ctx.fillStyle = readCanvasToken('--app-bg-panel', '#1a1a18')
        ctx.fillRect(0, 0, mapW, mapH)

        const nodes = renderNodes.value
        if (!nodes.length) return

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

        nodes.forEach(n => {
            const p = toMapCoord(n.position.x, n.position.y)
            ctx.fillStyle = n.selected
                ? readCanvasToken('--app-color-primary', '#d95417')
                : readCanvasToken('--app-text-placeholder', '#6d6d66')
            ctx.fillRect(p.x, p.y, Math.max(4, n.w * mapScale), Math.max(3, n.h * mapScale))
        })

        const containerW = containerRef.value.clientWidth
        const containerH = containerRef.value.clientHeight
        const viewLeft = -viewport.value.x / viewport.value.zoom
        const viewTop = -viewport.value.y / viewport.value.zoom
        const viewW = containerW / viewport.value.zoom
        const viewH = containerH / viewport.value.zoom

        const vpCoord = toMapCoord(viewLeft, viewTop)
        ctx.strokeStyle = readCanvasToken('--app-color-primary', '#d95417')
        ctx.lineWidth = 1.5
        ctx.strokeRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
        ctx.fillStyle = readCanvasToken('--app-color-primary-dim', 'rgba(217, 84, 23, 0.14)')
        ctx.fillRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
    }

    const scheduleMinimapDraw = () => {
        if (!store.uiState.minimapExpanded || minimapFrame) return
        const requestFrame = globalThis.requestAnimationFrame || (callback => globalThis.setTimeout(callback, 16))
        minimapFrame = requestFrame(() => {
            minimapFrame = 0
            drawMinimap()
        })
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
        scheduleMinimapDraw()
    }

    // The minimap only depends on geometry. Deep-watching every render-node
    // also traversed params, preview metadata and ports on each form edit.
    const minimapGeometryKey = computed(() => renderNodes.value
        .map(node => `${node.node_id}:${node.position.x},${node.position.y},${node.w},${node.h}`)
        .join('|'))
    watch([
        minimapGeometryKey,
        () => viewport.value.x,
        () => viewport.value.y,
        () => viewport.value.zoom,
    ], () => {
        scheduleMinimapDraw()
    }, { flush: 'post' })

    watch(() => store.uiState.minimapExpanded, (val) => {
        if (val) {
            nextTick(scheduleMinimapDraw)
        }
    })

    // ===== 鼠标事件 =====
    const selectNodeFromPointer = (e, node) => {
        if (e.shiftKey) {
            const anchorId = store.selectionAnchorId || store.primaryNodeId || store.selectedNodeId
            const path = anchorId ? findSelectionPath(props.edges, anchorId, node.node_id) : null
            if (path) {
                store.selectPath(path.nodeIds, path.edgeIds, anchorId, node.node_id)
            } else {
                store.selectNode(node.node_id)
            }
            return 'selection-only'
        }
        if (e.ctrlKey || e.metaKey) {
            store.toggleNodeSelection(node.node_id)
            return 'selection-only'
        }
        if (!localSelectedNodeIds.value.includes(node.node_id) || localSelectedNodeIds.value.length <= 1) {
            store.selectNode(node.node_id)
        }
        return 'drag'
    }

    const completeRectangleSelection = () => {
        if (!selectionBox.value.visible || !containerRef.value) return
        const rect = containerRef.value.getBoundingClientRect()
        const toWorld = (clientX, clientY) => ({
            x: (clientX - rect.left - viewport.value.x) / viewport.value.zoom,
            y: (clientY - rect.top - viewport.value.y) / viewport.value.zoom
        })
        const start = toWorld(selectionBox.value.startX, selectionBox.value.startY)
        const end = toWorld(selectionBox.value.endX, selectionBox.value.endY)
        const box = {
            minX: Math.min(start.x, end.x),
            maxX: Math.max(start.x, end.x),
            minY: Math.min(start.y, end.y),
            maxY: Math.max(start.y, end.y)
        }
        const selectedIds = renderNodes.value.filter(node => {
            const position = node.position || { x: 0, y: 0 }
            return position.x < box.maxX && position.x + node.w > box.minX &&
                position.y < box.maxY && position.y + node.h > box.minY
        }).map(node => node.node_id)
        store.selectNodes(selectedIds, {
            primaryId: selectedIds[0] || null,
            anchorId: selectedIds[0] || null
        })
    }

    const onCanvasMouseDown = (e) => {
        // 工具栏/菜单内点击不触发画布平移
        if (e.target.closest('.canvas-toolbar') || e.target.closest('.canvas-context-menu') || e.target.closest('.spawn-menu')) return
        customContextMenu.visible = false

        const isBlankArea = e.target === containerRef.value ||
            e.target.classList.contains('canvas-viewport') ||
            e.target.tagName === 'svg' ||
            e.target.classList.contains('canvas-edges-layer')

        if (isBlankArea) {
            clearSelection()
            selectedEdgeId.value = null
            editingEdgeId.value = ''
            selectedWaypoint.edgeId = ''
            selectedWaypoint.waypointId = ''
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

        if (selectNodeFromPointer(e, node) === 'selection-only') {
            e.stopPropagation()
            return
        }

        selectedEdgeId.value = null
        editingEdgeId.value = ''
        selectedWaypoint.edgeId = ''
        selectedWaypoint.waypointId = ''

        draggingNodeId.value = node.node_id
        dragStartMouse.value = { x: e.clientX, y: e.clientY }
        nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
        dragInitialPositions.value = new Map(
            renderNodes.value
                .filter(item => localSelectedNodeIds.value.includes(item.node_id))
                .map(item => [item.node_id, { ...(item.position || { x: 0, y: 0 }) }])
        )
        hasMoved.value = false
        e.stopPropagation()
    }

    const processGlobalMouseMove = (e) => {
        isCtrlHeldRef.value = e.ctrlKey

        // 记录最近鼠标位置（世界坐标），供 Ctrl+V 粘贴定位
        if (containerRef.value) {
            const rect = containerRef.value.getBoundingClientRect()
            lastMousePos.value = {
                x: (e.clientX - rect.left - viewport.value.x) / viewport.value.zoom,
                y: (e.clientY - rect.top - viewport.value.y) / viewport.value.zoom
            }
        }

        if (waypointDrag.active) {
            const draft = waypointDrafts[waypointDrag.edgeId]
            if (!Array.isArray(draft) || !draft[waypointDrag.index]) return
            const point = clientToWorld(e.clientX, e.clientY)
            draft[waypointDrag.index] = {
                ...draft[waypointDrag.index],
                x: Math.round(point.x / GRID_SIZE) * GRID_SIZE,
                y: Math.round(point.y / GRID_SIZE) * GRID_SIZE
            }
            return
        }

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

                const movingIds = localSelectedNodeIds.value.includes(draggingNodeId.value)
                    ? new Set(localSelectedNodeIds.value)
                    : new Set([draggingNodeId.value])
                const primaryInitial = dragInitialPositions.value.get(draggingNodeId.value) || nodeInitialPos.value
                const movement = { x: rawX - primaryInitial.x, y: rawY - primaryInitial.y }
                for (const movingId of movingIds) {
                    const initial = dragInitialPositions.value.get(movingId)
                    if (!initial) continue
                    localDraftPositions[movingId] = {
                        x: initial.x + movement.x,
                        y: initial.y + movement.y
                    }
                }

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
                    if (movingIds.has(otherNode.node_id)) continue
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

    // Windows 高采样率鼠标可能在一帧内产生数十次 move。画布只消费
    // 当前显示帧的最后一个位置，避免未选节点、连线和碰撞预览重复计算。
    let pointerMoveFrame = 0
    let queuedPointerEvent = null
    const requestPointerFrame = globalThis.requestAnimationFrame || (callback => globalThis.setTimeout(callback, 16))
    const cancelPointerFrame = globalThis.cancelAnimationFrame || globalThis.clearTimeout
    const flushPointerMove = () => {
        if (pointerMoveFrame) {
            cancelPointerFrame(pointerMoveFrame)
            pointerMoveFrame = 0
        }
        const event = queuedPointerEvent
        queuedPointerEvent = null
        if (event) processGlobalMouseMove(event)
    }
    const onGlobalMouseMove = (e) => {
        queuedPointerEvent = e
        isCtrlHeldRef.value = e.ctrlKey
        if (pointerMoveFrame) return
        pointerMoveFrame = requestPointerFrame(() => {
            pointerMoveFrame = 0
            const event = queuedPointerEvent
            queuedPointerEvent = null
            if (event) processGlobalMouseMove(event)
        })
    }

    const settleMultiNodeDrag = async (primaryNodeId) => {
        const selectedIds = new Set(localSelectedNodeIds.value)
        const primaryInitial = dragInitialPositions.value.get(primaryNodeId) || nodeInitialPos.value
        const primaryDraft = localDraftPositions[primaryNodeId] || primaryInitial
        const delta = {
            x: Math.round((primaryDraft.x - primaryInitial.x) / GRID_SIZE) * GRID_SIZE,
            y: Math.round((primaryDraft.y - primaryInitial.y) / GRID_SIZE) * GRID_SIZE
        }
        const sizeById = new Map(renderNodes.value.map(node => [node.node_id, {
            w: node.w || NODE_GRID_W * GRID_SIZE,
            h: node.h || 120
        }]))
        const externalNodes = renderNodes.value.filter(node => !selectedIds.has(node.node_id))
        const GAP = GRID_SIZE
        const candidates = new Map()
        for (const nodeId of selectedIds) {
            const initial = dragInitialPositions.value.get(nodeId)
            if (!initial) continue
            candidates.set(nodeId, { x: initial.x + delta.x, y: initial.y + delta.y })
        }
        const fits = (offsetX, offsetY) => {
            for (const [nodeId, position] of candidates) {
                const size = sizeById.get(nodeId) || { w: NODE_GRID_W * GRID_SIZE, h: 120 }
                for (const other of externalNodes) {
                    const otherPosition = other.position || { x: 0, y: 0 }
                    const otherSize = sizeById.get(other.node_id) || { w: NODE_GRID_W * GRID_SIZE, h: 120 }
                    if (!(
                        position.x + offsetX + size.w + GAP <= otherPosition.x ||
                        position.x + offsetX >= otherPosition.x + otherSize.w + GAP ||
                        position.y + offsetY + size.h + GAP <= otherPosition.y ||
                        position.y + offsetY >= otherPosition.y + otherSize.h + GAP
                    )) return false
                }
            }
            return true
        }
        let correction = { x: 0, y: 0 }
        if (!fits(0, 0)) {
            outer: for (let radius = 1; radius <= 30; radius += 1) {
                for (let x = -radius; x <= radius; x += 1) {
                    for (const y of [-radius, radius]) {
                        const offsetX = x * GRID_SIZE
                        const offsetY = y * GRID_SIZE
                        if (fits(offsetX, offsetY)) {
                            correction = { x: offsetX, y: offsetY }
                            break outer
                        }
                    }
                }
                for (let y = -radius + 1; y < radius; y += 1) {
                    for (const x of [-radius, radius]) {
                        const offsetX = x * GRID_SIZE
                        const offsetY = y * GRID_SIZE
                        if (fits(offsetX, offsetY)) {
                            correction = { x: offsetX, y: offsetY }
                            break outer
                        }
                    }
                }
            }
        }

        const tasks = JSON.parse(JSON.stringify(dataTasks.value))
        for (const task of tasks) {
            for (const node of task.nodes || []) {
                const position = candidates.get(node.node_id)
                if (!position) continue
                node.position = {
                    x: position.x + correction.x,
                    y: position.y + correction.y
                }
            }
        }
        for (const nodeId of selectedIds) delete localDraftPositions[nodeId]
        dragInitialPositions.value = new Map()
        emit('update-geometry', {
            tasks,
            movedNodeIds: [...selectedIds],
            delta: { x: delta.x + correction.x, y: delta.y + correction.y }
        })
        ElMessage.success(`已整体移动 ${selectedIds.size} 个节点`)
    }

    const settleWorkflowDrag = async (nodeId) => {
        const rawPos = localDraftPositions[nodeId] || nodeInitialPos.value
        const finalPos = {
            x: Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE,
            y: Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
        }

        // 画布只负责当前流程内排版；跨流程整理由左侧资源树显式完成。
        const tasks = JSON.parse(JSON.stringify(dataTasks.value))
        localTasksOverride.value = tasks

        const targetNodeObj = renderNodes.value.find(n => n.node_id === nodeId)
        const currentNodeSize = { w: targetNodeObj?.w || (NODE_GRID_W * GRID_SIZE), h: targetNodeObj?.h || 120 }
        const safePos = resolveCollisionsAndPushOthers(nodeId, finalPos, renderNodes.value, currentNodeSize)
        for (const task of tasks) {
            const found = (task.nodes || []).find(n => n.node_id === nodeId)
            if (found) {
                found.position = safePos
                break
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

        emit('update-geometry', { tasks, movedNodeIds: [nodeId], delta: null })
        delete localDraftPositions[nodeId]
        ElMessage.success('节点位置已更新')
    }

    const onGlobalMouseUp = async (e) => {
        flushPointerMove()
        isPanning.value = false

        if (waypointDrag.active) {
            const { edgeId, index } = waypointDrag
            const draft = Array.isArray(waypointDrafts[edgeId])
                ? waypointDrafts[edgeId].map(point => ({ ...point }))
                : []
            const current = draft[index]
            if (current) {
                const resolved = findNearestFreeWaypoint(current, renderNodes.value)
                if (resolved) {
                    const moved = resolved.x !== current.x || resolved.y !== current.y
                    draft[index] = { ...current, ...resolved }
                    saveEdgeWaypoints(edgeId, draft)
                    if (moved) ElMessage.info('转接点已自动避让节点')
                } else {
                    draft.splice(index, 1)
                    saveEdgeWaypoints(edgeId, draft)
                    ElMessage.warning('转接点附近无可用位置，已恢复该段自动路由')
                }
            }
            delete waypointDrafts[edgeId]
            Object.assign(waypointDrag, { active: false, edgeId: '', waypointId: '', index: -1 })
            return
        }

        if (selectionBox.value.visible) {
            completeRectangleSelection()
            selectionBox.value.visible = false
        }

        dragPreviewBox.value.visible = false

        const wasDrawing = drawingConnection.value.active
        const sourceId = drawingConnection.value.sourceNodeId
        const portType = drawingConnection.value.portType
        const sourcePortId = drawingConnection.value.sourcePortId
        drawingConnection.value.active = false

        if (draggingNodeId.value) {
            const nodeId = draggingNodeId.value
            draggingNodeId.value = false
            isCtrlHeldRef.value = false

            if (hasMoved.value) {
                // 两个画布模式共享节点网格吸附、批量移动与碰撞推挤。
                if (localSelectedNodeIds.value.length > 1 && localSelectedNodeIds.value.includes(nodeId)) {
                    await settleMultiNodeDrag(nodeId)
                } else {
                    await settleWorkflowDrag(nodeId)
                }
            }
            hasMoved.value = false
        }

        // 已连出口拖到空白处表示断开；空出口拖到空白处才打开新建节点菜单。
        // 两条路径都以稳定端口 ID 判断，避免动态端口重排后误断或漏连。
        if (wasDrawing) {
            const existing = flatEdges.value.find(edge =>
                edge.sourceNodeId === sourceId && (
                    edge.extra?.sourcePortId === sourcePortId
                    || (!edge.extra?.sourcePortId && edge.sourcePort === portType)
                ))
            if (existing) {
                emit('remove-edge', { ...existing, sourceNodeId: sourceId, sourcePort: portType })
                ElMessage.success('已成功断开连线')
                return
            }

            spawnMenu.value = {
                visible: true,
                x: e.clientX,
                y: e.clientY,
                sourceNodeId: sourceId,
                portType,
                sourcePortId,
                clientX: e.clientX,
                clientY: e.clientY
            }
        }
    }

    const onCanvasWheel = (e) => {
        viewportWheel(e)
        scheduleMinimapDraw()
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
        }

        if (targetX !== 0 || targetY !== 0) {
            viewport.value.x = containerW / 2 - targetX * viewport.value.zoom
            viewport.value.y = containerH / 2 - targetY * viewport.value.zoom
            scheduleMinimapDraw()
        }
    })

    // ===== 拉线落点建立连线 =====
    const onNodeMouseUpCard = (e, targetNode) => {
        if (drawingConnection.value.active) {
            const sourceId = drawingConnection.value.sourceNodeId
            const portType = drawingConnection.value.portType
            const sourcePortId = drawingConnection.value.sourcePortId

            drawingConnection.value.active = false

            if (sourceId && sourceId !== targetNode.node_id) {
                emit('add-edge', {
                    source: sourceId,
                    target: targetNode.node_id,
                    source_port: portType,
                    source_port_id: sourcePortId
                })
                ElMessage.success(`连线指向 ➔ [${targetNode.node_name}]`)
            }
            e.stopPropagation()
        }
    }

    const onNodeDoubleClick = (e, node) => {
        store.selectNode(node.node_id)
        e.stopPropagation()
    }

    const startConnection = (e, nodeId, portType) => {
        if (!containerRef.value) return
        const rect = containerRef.value.getBoundingClientRect()
        const clientX = e.clientX - rect.left
        const clientY = e.clientY - rect.top

        const sourceNode = renderNodes.value.find(n => n.node_id === nodeId)
        const sourcePt = sourceNode ? getPortPosition(sourceNode, portType) : null
        const descriptor = sourceNode
            ? getSourcePortDescriptors(sourceNode, props.edges, FAILURE_PORT_TYPES)
                .find(port => port.key === portType)
            : null

        drawingConnection.value = {
            active: true,
            sourceNodeId: nodeId,
            portType,
            sourcePortId: descriptor?.stableId || portType,
            sourceX: sourcePt?.x ?? 0,
            sourceY: sourcePt?.y ?? 0,
            currentX: (clientX - viewport.value.x) / viewport.value.zoom,
            currentY: (clientY - viewport.value.y) / viewport.value.zoom,
            previewMarkerUrl: ''
        }
        e.stopPropagation()
    }

    const onEdgeClick = (edge) => {
        store.clearSelection()
        selectedEdgeId.value = edge.id
        editingEdgeId.value = edge.id
    }

    const persistedEdge = edgeId => (props.edges || []).find(edge => edge.edge_id === edgeId) || null

    const progressOnPath = (points, point) => {
        let travelled = 0
        let best = { distance: Infinity, progress: 0 }
        const list = points || []
        for (let index = 0; index < list.length - 1; index += 1) {
            const start = list[index]
            const end = list[index + 1]
            const horizontal = start.y === end.y
            const length = horizontal ? Math.abs(end.x - start.x) : Math.abs(end.y - start.y)
            if (!length) continue
            const ratio = horizontal
                ? Math.max(0, Math.min(1, (point.x - start.x) / (end.x - start.x || 1)))
                : Math.max(0, Math.min(1, (point.y - start.y) / (end.y - start.y || 1)))
            const projection = horizontal
                ? { x: start.x + (end.x - start.x) * ratio, y: start.y }
                : { x: start.x, y: start.y + (end.y - start.y) * ratio }
            const distance = Math.hypot(point.x - projection.x, point.y - projection.y)
            if (distance < best.distance) best = { distance, progress: travelled + length * ratio }
            travelled += length
        }
        return best.progress
    }

    const saveEdgeWaypoints = (edgeId, waypoints) => {
        const normalized = normalizeEdgeRouting({ mode: 'manual', waypoints })
        emit('update-edge-routing', { edgeId, routing: normalized })
    }

    const addWaypointAt = (edge, point) => {
        if (!edge?.id) return
        const resolved = findNearestFreeWaypoint(point, renderNodes.value)
        if (!resolved) {
            ElMessage.warning('附近没有可用的网格位置，未添加转接点')
            return
        }
        const source = persistedEdge(edge.id)
        const routing = normalizeEdgeRouting(source?.routing)
        const waypoint = {
            id: `waypoint_${globalThis.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now()}${Math.random().toString(36).slice(2, 7)}`}`,
            ...resolved
        }
        const path = edge.renderPoints || edge.rawPixelPoints || []
        const ordered = [...routing.waypoints, waypoint]
            .sort((a, b) => progressOnPath(path, a) - progressOnPath(path, b))
        editingEdgeId.value = edge.id
        selectedWaypoint.edgeId = edge.id
        selectedWaypoint.waypointId = waypoint.id
        saveEdgeWaypoints(edge.id, ordered)
    }

    const addWaypointFromEdgeEvent = (event, edge) => {
        event?.preventDefault?.()
        event?.stopPropagation?.()
        addWaypointAt(edge, clientToWorld(event.clientX, event.clientY))
    }

    const openEdgeContextMenu = (event, edge) => {
        event.preventDefault()
        event.stopPropagation()
        editingEdgeId.value = edge.id
        selectedEdgeId.value = edge.id
        customContextMenu.visible = true
        customContextMenu.targetType = 'edge'
        customContextMenu.targetId = edge.id
        customContextMenu.targetName = `${edge.sourceNodeId} → ${edge.targetNodeId}`
        customContextMenu.clientX = event.clientX
        customContextMenu.clientY = event.clientY
        customContextMenu.x = event.clientX + 8
        customContextMenu.y = event.clientY + 8
        customContextMenu.worldPoint = clientToWorld(event.clientX, event.clientY)
        menuZIndex.value = getNextZIndex()
        spawnMenu.value.visible = false
    }

    const addWaypointFromContextMenu = () => {
        const edge = routedEdges.value.find(item => item.id === customContextMenu.targetId)
        const point = customContextMenu.worldPoint
        customContextMenu.visible = false
        if (edge && point) addWaypointAt(edge, point)
    }

    const resetSelectedEdgeRouting = () => {
        const edgeId = customContextMenu.targetId || editingEdgeId.value
        customContextMenu.visible = false
        if (!edgeId) return
        delete waypointDrafts[edgeId]
        selectedWaypoint.edgeId = ''
        selectedWaypoint.waypointId = ''
        emit('update-edge-routing', { edgeId, routing: { mode: 'auto', waypoints: [] } })
        ElMessage.success('已恢复自动路由')
    }

    const startWaypointDrag = (event, edge, waypoint, index) => {
        event.preventDefault()
        event.stopPropagation()
        const routing = normalizeEdgeRouting(persistedEdge(edge.id)?.routing)
        waypointDrafts[edge.id] = routing.waypoints.map(point => ({ ...point }))
        Object.assign(waypointDrag, { active: true, edgeId: edge.id, waypointId: waypoint.id, index })
        selectedWaypoint.edgeId = edge.id
        selectedWaypoint.waypointId = waypoint.id
        editingEdgeId.value = edge.id
    }

    const focusWaypoint = (edge, waypoint) => {
        if (!edge?.id || !waypoint?.id) return
        editingEdgeId.value = edge.id
        selectedEdgeId.value = edge.id
        selectedWaypoint.edgeId = edge.id
        selectedWaypoint.waypointId = waypoint.id
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

        // Ctrl+C 复制选中节点 / Ctrl+V 粘贴（输入框聚焦时不触发）
        const ctrl = e.ctrlKey || e.metaKey
        if (ctrl && (e.key === 'c' || e.key === 'v') && !checkInputFocus()) {
            if (e.key === 'c') {
                if (localSelectedNodeIds.value.length > 0) {
                    customContextMenu.targetId = localSelectedNodeIds.value[0]
                    handleCopyNode()
                }
            } else {
                pasteClipboardNode()
            }
            return
        }

        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)
            && selectedWaypoint.edgeId && !checkInputFocus()) {
            const edge = persistedEdge(selectedWaypoint.edgeId)
            const routing = normalizeEdgeRouting(edge?.routing)
            const index = routing.waypoints.findIndex(point => point.id === selectedWaypoint.waypointId)
            if (index >= 0) {
                e.preventDefault()
                const delta = {
                    ArrowLeft: [-GRID_SIZE, 0],
                    ArrowRight: [GRID_SIZE, 0],
                    ArrowUp: [0, -GRID_SIZE],
                    ArrowDown: [0, GRID_SIZE]
                }[e.key]
                routing.waypoints[index] = {
                    ...routing.waypoints[index],
                    x: routing.waypoints[index].x + delta[0],
                    y: routing.waypoints[index].y + delta[1]
                }
                saveEdgeWaypoints(edge.edge_id, routing.waypoints)
            }
            return
        }

        if ((e.key === 'Delete' || e.key === 'Backspace') && !checkInputFocus()) {
            if (selectedWaypoint.edgeId) {
                const edge = persistedEdge(selectedWaypoint.edgeId)
                const routing = normalizeEdgeRouting(edge?.routing)
                const next = routing.waypoints.filter(point => point.id !== selectedWaypoint.waypointId)
                saveEdgeWaypoints(selectedWaypoint.edgeId, next)
                selectedWaypoint.edgeId = ''
                selectedWaypoint.waypointId = ''
                e.preventDefault()
                return
            }
            if (selectedEdgeId.value && localSelectedNodeIds.value.length === 0) {
                const edge = computedEdges.value.find(item => item.id === selectedEdgeId.value)
                if (edge) {
                    emit('remove-edge', {
                        sourceNodeId: edge.sourceNodeId,
                        targetNodeId: edge.targetNodeId,
                        sourcePort: edge.sourcePort,
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
        const sourcePortId = spawnMenu.value.sourcePortId

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

        const nodeId = `node_${globalThis.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now()}${Math.random().toString(36).slice(2, 8)}`}`
        emit('create-node', {
            nodeId,
            type: nodeType,
            position,
            sourceNodeId: sourceId,
            portType,
            sourcePortId,
            announce: true
        })
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
        nextTick(scheduleMinimapDraw)
    })

    onUnmounted(() => {
        queuedPointerEvent = null
        if (pointerMoveFrame) {
            cancelPointerFrame(pointerMoveFrame)
            pointerMoveFrame = 0
        }
        if (minimapFrame) {
            const cancelFrame = globalThis.cancelAnimationFrame || globalThis.clearTimeout
            cancelFrame(minimapFrame)
            minimapFrame = 0
        }
        window.removeEventListener('mousemove', onGlobalMouseMove)
        window.removeEventListener('mouseup', onGlobalMouseUp)
        window.removeEventListener('keydown', globalKeydownHandler)
        window.removeEventListener('keyup', globalKeyupHandler)
        window.removeEventListener('keydown', _onUndoHotkey, true)
        containerResizeObserver?.disconnect()
    })

    const getViewportCenter = () => {
        const width = containerRef.value?.clientWidth || 0
        const height = containerRef.value?.clientHeight || 0
        return {
            x: Math.round((width / 2 - viewport.value.x) / viewport.value.zoom),
            y: Math.round((height / 2 - viewport.value.y) / viewport.value.zoom)
        }
    }

    defineExpose({ getViewportCenter })
</script>

<style scoped>
    .toolbar-separator {
        width: 1px;
        height: 18px;
        margin: 0 2px;
        background: var(--app-border-subtle, rgba(255, 255, 255, .1));
    }
</style>
