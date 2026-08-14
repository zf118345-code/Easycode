<!--
  TopologyCanvas.vue
  Unified canvas: shares CanvasNodeCard / CanvasEdgeLayer / CanvasContextMenu with WorkflowCanvas
  Same visual style, same interaction model. Only data source and node catalog differ.
-->
<template>
    <div
ref="containerRef"
         class="topology-canvas-container"
         @mousedown="onContainerMouseDown"
         @wheel.prevent="onWheel"
         @contextmenu.prevent="onContextMenu">
        <!-- 视口变换层 -->
        <div
class="canvas-viewport grid-background"
             :style="{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`, transformOrigin: '0 0' }">
<!-- SVG 连线层（共享子组件） -->
            <CanvasEdgeLayer
                :edges="computedEdges"
                :drawing-connection="drawingConnection"
                :svg-width="svgWidth"
                :svg-height="svgHeight"
                @edge-click="onEdgeClick" />

            <!-- 节点卡片层（共享子组件，拓扑模式） -->
            <CanvasNodeCard
                v-for="node in renderNodes"
                :key="node.node_id"
                :node="node"
                :selected="node.node_id === selectedNodeId"
                :is-active-debug="false"
                :has-breakpoint="false"
                :mode="'topology'"
                @node-mousedown="onNodeMouseDown"
                @node-mouseup="onNodeMouseUp"
                @node-dblclick="onNodeDoubleClick"
                @node-contextmenu="openNodeContextMenu"
                @start-connection="startConnection" />
        </div>

        <!-- 缩放工具栏 -->
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

        <!-- 右键菜单（共享子组件） -->
        <CanvasContextMenu
            :context-menu="customContextMenu"
            :spawn-menu="spawnMenu"
            :menu-z-index="menuZIndex"
            :available-node-types="availableNodeTypes"
            :has-breakpoint="false"
            :is-paused="false"
            @create-and-connect="createAndConnectNode"
            @delete-node="handleDeleteNode"
            @canvas-new-node="handleCanvasNewNode" />
    </div>
</template>

<script setup>
    import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
    import { useMainStore } from '@/stores/index'
    import {
        GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
        snapToGrid,
        getPortPosition,
        getMarkerId
    } from '@/utils/canvasShared'
    import { computeEdgePath } from '@/utils/canvasRouter'
    import { normalizePortType, normalizeNodeList } from '@/utils/nodeModel'
    import { useCanvasSharedStyle } from '@/composables/useCanvasSharedStyle'
    useCanvasSharedStyle()

    import { Plus, Minus, Maximize } from 'lucide-vue-next'
    import CanvasNodeCard from '@/components/canvas/CanvasNodeCard.vue'
    import CanvasEdgeLayer from '@/components/canvas/CanvasEdgeLayer.vue'
    import CanvasContextMenu from '@/components/canvas/CanvasContextMenu.vue'

    const store = useMainStore()
    const containerRef = ref(null)

    // ===== 视口状态（与 WorkflowCanvas 一致） =====
    const viewport = reactive({ x: 0, y: 0, zoom: 1 })
    const svgWidth = ref(5000)
    const svgHeight = ref(3000)

    // ===== 交互状态 =====
    const isPanning = ref(false)
    const panStart = reactive({ x: 0, y: 0, vx: 0, vy: 0 })
    const draggingNodeId = ref(null)
    const dragStartPos = reactive({ x: 0, y: 0, nx: 0, ny: 0 })
    const selectedNodeId = ref(null)
    const selectedEdgeId = ref(null)
    const menuZIndex = ref(3000)

    // ===== 拉线状态 =====
    const drawingConnection = reactive({
        active: false,
        currentX: 0,
        currentY: 0,
        sourceNodeId: null,
        portType: 'success',
        sourceX: 0,
        sourceY: 0,
        previewMarkerUrl: ''
    })

    // ===== 右键菜单 =====
    const customContextMenu = reactive({
        visible: false,
        x: 0,
        y: 0,
        targetType: 'canvas_public',
        targetId: null,
        clickX: 0,
        clickY: 0
    })
    const spawnMenu = reactive({ visible: false, x: 0, y: 0 })

    // ===== 节点白名单（拓扑模式可创建的节点类型） =====
    const availableNodeTypes = {
        page_state: '页面状态',
        click: '点击动作',
        wait: '等待动作',
        image_recognition: '图像识别',
        ocr_recognition: 'OCR 识别'
    }

    // ========== 数据计算 ==========

    const topologyNodes = computed(() => store.topologyNodes)
    const topologyEdges = computed(() => store.topologyEdges)

    const computeTopologyNodeHeight = (node) => {
        let h = 38
        if (node.type === 'page_state') {
            if (node.page_id) h += 18
            if (node.features?.length) h += 18
            if (node.exits?.length) h += 18
        }
        const exitCount = node.exits?.length || 0
        if (exitCount > 0) h = Math.max(h, 42 + exitCount * 28)
        return Math.max(NODE_MIN_HEIGHT, snapToGrid(h + 8))
    }

    const renderNodes = computed(() => {
        const raw = topologyNodes.value.map(n => {
            const pos = n.position || { x: 0, y: 0 }
            const gridX = Math.round(pos.x / GRID_SIZE) * GRID_SIZE
            const gridY = Math.round(pos.y / GRID_SIZE) * GRID_SIZE
            const w = NODE_WIDTH
            const h = computeTopologyNodeHeight(n)
            return {
                ...n,
                node_type: n.type,
                node_name: n.node_name || n.label || n.page_id || '未命名',
                position: { x: gridX, y: gridY },
                w,
                h,
                size: { w, h },
                showFailPort: ['page_state', 'image_recognition', 'ocr_recognition'].includes(n.type),
                selected: selectedNodeId.value === n.node_id
            }
        })
        return normalizeNodeList(raw)
    })

    // ========== 连线路径计算 ==========

    const computedEdges = computed(() => {
        if (!topologyNodes.value.length) return []

        const allNodes = renderNodes.value
        const result = []

        const parallelCount = {}
        const parallelIndex = {}
        topologyEdges.value.forEach(edge => {
            const key = `${edge.source}-${edge.target}`
            parallelCount[key] = (parallelCount[key] || 0) + 1
        })

        for (const edge of topologyEdges.value) {
            const sourceNode = allNodes.find(n => n.node_id === edge.source)
            const targetNode = allNodes.find(n => n.node_id === edge.target)
            if (!sourceNode || !targetNode) continue

            const key = `${edge.source}-${edge.target}`
            parallelIndex[key] = (parallelIndex[key] || 0) + 1
            const offsetIndex = parallelIndex[key] - 1
            const totalParallel = parallelCount[key]

            const sourcePort = edge.source_port || 'exit'
            const isDragging = draggingNodeId.value === sourceNode.node_id || draggingNodeId.value === targetNode.node_id

            const { pathD, markerId, points } = computeEdgePath(
                sourceNode, targetNode, allNodes, sourcePort,
                { isDragging, offsetIndex, totalParallel }
            )

            const isFail = sourcePort === 'failure' || sourcePort === 'fail'
            const markerUrl = `url(#${markerId})`

            result.push({
                id: edge.edge_id || `e_${edge.source}_${edge.target}`,
                path: pathD,
                markerUrl,
                isFail,
                selected: selectedEdgeId.value === (edge.edge_id || `e_${edge.source}_${edge.target}`),
                label: edge.label || '',
                labelX: points.length >= 2 ? (points[0].x + points[points.length - 1].x) / 2 : 0,
                labelY: points.length >= 2 ? (points[0].y + points[points.length - 1].y) / 2 - 10 : 0,
                rawPixelPoints: points
            })
        }

        return result
    })

    // ========== 视口操作 ==========

    const zoomIn = () => { viewport.zoom = Math.min(4, viewport.zoom * 1.2) }
    const zoomOut = () => { viewport.zoom = Math.max(0.2, viewport.zoom * 0.8) }
    const resetView = () => { viewport.x = 0; viewport.y = 0; viewport.zoom = 1 }

    const onWheel = (e) => {
        const delta = e.deltaY > 0 ? 0.9 : 1.1
        viewport.zoom = Math.max(0.2, Math.min(4, viewport.zoom * delta))
    }

    const onContainerMouseDown = (e) => {
        if (e.target.closest('.canvas-node-card') || e.target.closest('.canvas-toolbar')) return
        selectedNodeId.value = null
        selectedEdgeId.value = null

        // 开始平移
        isPanning.value = true
        panStart.x = e.clientX
        panStart.y = e.clientY
        panStart.vx = viewport.x
        panStart.vy = viewport.y

        if (e.button === 2 || e.shiftKey) {
            customContextMenu.visible = true
            customContextMenu.x = e.clientX
            customContextMenu.y = e.clientY
            customContextMenu.targetType = 'canvas_public'
            customContextMenu.clickX = e.clientX
            customContextMenu.clickY = e.clientY
        }
    }

    const onContextMenu = (e) => {
        e.preventDefault()
        customContextMenu.visible = true
        customContextMenu.x = e.clientX
        customContextMenu.y = e.clientY
        customContextMenu.targetType = 'canvas_public'
        customContextMenu.clickX = e.clientX
        customContextMenu.clickY = e.clientY
    }

    // ========== 节点交互 ==========

    const onNodeMouseDown = (e, node) => {
        e.stopPropagation()
        selectedNodeId.value = node.node_id
        draggingNodeId.value = node.node_id
        dragStartPos.x = e.clientX
        dragStartPos.y = e.clientY
        dragStartPos.nx = node.position.x
        dragStartPos.ny = node.position.y

        const onMove = (ev) => {
            if (!draggingNodeId.value) return
            const dx = (ev.clientX - dragStartPos.x) / viewport.zoom
            const dy = (ev.clientY - dragStartPos.y) / viewport.zoom
            const newX = snapToGrid(dragStartPos.nx + dx)
            const newY = snapToGrid(dragStartPos.ny + dy)
            store.updateTopologyNode(node.node_id, { position: { x: newX, y: newY } })
        }
        const onUp = () => {
            draggingNodeId.value = null
            window.removeEventListener('mousemove', onMove)
            window.removeEventListener('mouseup', onUp)
        }
        window.addEventListener('mousemove', onMove)
        window.addEventListener('mouseup', onUp)
    }

    const onNodeMouseUp = () => { draggingNodeId.value = null }

    const onNodeDoubleClick = (e, node) => {
        store.selectTopologyNode(node.node_id)
    }

    const openNodeContextMenu = (e, node) => {
        e.preventDefault()
        e.stopPropagation()
        selectedNodeId.value = node.node_id
        customContextMenu.visible = true
        customContextMenu.x = e.clientX
        customContextMenu.y = e.clientY
        customContextMenu.targetType = 'node'
        customContextMenu.targetId = node.node_id
    }

    // ========== 连线交互 ==========

    const startConnection = (e, nodeId, portType) => {
        e.stopPropagation()
        const node = renderNodes.value.find(n => n.node_id === nodeId)
        if (!node) return

        const pt = getPortPosition(node, portType)
        drawingConnection.active = true
        drawingConnection.sourceX = pt.x
        drawingConnection.sourceY = pt.y
        drawingConnection.currentX = pt.x
        drawingConnection.currentY = pt.y
        drawingConnection.sourceNodeId = nodeId
        drawingConnection.portType = portType

        const standardPort = normalizePortType(portType)
        const arrowDir = 'right'
        drawingConnection.previewMarkerUrl = `url(#${getMarkerId(standardPort, arrowDir)})`

        const onMove = (ev) => {
            if (!drawingConnection.active) return
            const rect = containerRef.value?.getBoundingClientRect()
            if (rect) {
                drawingConnection.currentX = (ev.clientX - rect.left - viewport.x) / viewport.zoom
                drawingConnection.currentY = (ev.clientY - rect.top - viewport.y) / viewport.zoom
            }
        }
        const onUp = (ev) => {
            if (!drawingConnection.active) return
            const target = document.elementFromPoint(ev.clientX, ev.clientY)
            const card = target?.closest('.canvas-node-card')
            if (card) {
                const targetId = card.getAttribute('data-node-id')
                if (targetId && targetId !== nodeId) {
                    store.addTopologyEdge({
                        source: nodeId,
                        target: targetId,
                        source_port: portType === 'succ' ? 'success' : portType === 'fail' ? 'failure' : portType,
                        edge_id: `e_${nodeId}_${portType}_${targetId}`
                    })
                }
            }
            drawingConnection.active = false
        }
        window.addEventListener('mousemove', onMove)
        window.addEventListener('mouseup', onUp, { once: true })
    }

    const onEdgeClick = (edge) => {
        selectedEdgeId.value = edge.id
    }

    // ========== 右键菜单操作 ==========

    const handleCanvasNewNode = (nodeType, x, y) => {
        const nodeId = `topo_${Date.now()}`
        store.addTopologyNode({
            node_id: nodeId,
            type: nodeType,
            node_name: availableNodeTypes[nodeType] || nodeType,
            position: { x: snapToGrid(x), y: snapToGrid(y) }
        })
        customContextMenu.visible = false
    }

    const createAndConnectNode = (nodeType, x, y) => {
        const newId = `topo_${Date.now()}`
        store.addTopologyNode({
            node_id: newId,
            type: nodeType,
            node_name: availableNodeTypes[nodeType] || nodeType,
            position: { x: snapToGrid(x), y: snapToGrid(y) }
        })
        if (drawingConnection.sourceNodeId) {
            store.addTopologyEdge({
                source: drawingConnection.sourceNodeId,
                target: newId,
                source_port: drawingConnection.portType === 'succ' ? 'success' : drawingConnection.portType === 'fail' ? 'failure' : drawingConnection.portType,
                edge_id: `e_${drawingConnection.sourceNodeId}_${drawingConnection.portType}_${newId}`
            })
        }
        customContextMenu.visible = false
        drawingConnection.active = false
    }

    const handleDeleteNode = (nodeId) => {
        store.deleteTopologyNode(nodeId)
        store.topologyEdges = store.topologyEdges.filter(e => e.source !== nodeId && e.target !== nodeId)
        selectedNodeId.value = null
        customContextMenu.visible = false
    }

    // ========== 全局事件 ==========

    const onGlobalMouseMove = (e) => {
        if (isPanning.value) {
            viewport.x = panStart.vx + (e.clientX - panStart.x)
            viewport.y = panStart.vy + (e.clientY - panStart.y)
        }
    }

    const onGlobalMouseUp = () => {
        if (isPanning.value) {
            isPanning.value = false
        }
    }

    const onDocClick = (e) => {
        if (!e.target.closest('.canvas-context-menu')) {
            customContextMenu.visible = false
        }
    }

    // ========== 生命周期 ==========

    onMounted(() => {
        window.addEventListener('mousemove', onGlobalMouseMove)
        window.addEventListener('mouseup', onGlobalMouseUp)
        document.addEventListener('click', onDocClick)

        if (!topologyNodes.value.length) {
            store.loadTopologyFromBlueprint?.()
        }

        nextTick(() => {
            if (containerRef.value) {
                svgWidth.value = containerRef.value.clientWidth + 2000
                svgHeight.value = containerRef.value.clientHeight + 1500
            }
        })
    })

    onUnmounted(() => {
        window.removeEventListener('mousemove', onGlobalMouseMove)
        window.removeEventListener('mouseup', onGlobalMouseUp)
        document.removeEventListener('click', onDocClick)
    })

    watch(topologyNodes, () => {
        nextTick(() => {
            if (containerRef.value) {
                svgWidth.value = containerRef.value.clientWidth + 2000
                svgHeight.value = containerRef.value.clientHeight + 1500
            }
        })
    }, { deep: true })
</script>


