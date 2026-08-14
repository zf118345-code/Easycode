<!--
  TopologyCanvas.vue
  重写：使用共享 canvasRouter.js（A* 网格寻路 + 边间距偏移）
  统一 canvasShared.js 样式（与 WorkflowCanvas 一致的节点卡片、端口、连线、流光动画）
  统一碰撞推挤算法、20px 网格吸附、方向感知箭头
-->
<template>
    <div ref="containerRef"
         class="topology-canvas-container"
         @mousedown="onContainerMouseDown"
         @wheel.prevent="onWheel"
         @contextmenu.prevent="onContextMenu">
        <!-- SVG 连线层 + 网格背景 -->
        <div class="canvas-viewport grid-background"
             :style="{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`, transformOrigin: '0 0' }">
            <svg class="canvas-edges-layer" :width="svgWidth" :height="svgHeight">
                <defs v-html="ARROW_MARKERS_SVG"></defs>

                <!-- 已有连线 -->
                <template v-for="edge in renderedEdges" :key="edge.edge_id">
                    <path :d="edge.pathD"
                          class="edge-path"
                          :class="{
              'is-success': edge.source_port !== 'failure',
              'is-failure': edge.source_port === 'failure',
              'is-selected': edge.edge_id === selectedEdgeId
            }"
                          :marker-end="`url(#${edge.markerId})`"
                          @click.stop="onEdgeClick(edge)" />
                    <!-- 流光动画 -->
                    <path :d="edge.pathD"
                          class="edge-flow-path"
                          v-if="edge.edge_id !== selectedEdgeId" />
                    <!-- 连线标签 -->
                    <text v-if="edge.label"
                          :x="edge.labelX"
                          :y="edge.labelY"
                          class="edge-label"
                          text-anchor="middle">{{ edge.label }}</text>
                </template>

                <!-- 实时拉线预览 -->
                <path v-if="drawingConnection.active"
                      :d="previewPathD"
                      class="edge-path is-success"
                      stroke-dasharray="6 4"
                      opacity="0.6" />
            </svg>

            <!-- 节点卡片层 -->
            <div v-for="node in topologyNodes"
                 :key="node.node_id"
                 class="canvas-node-card"
                 :class="{
          'is-selected': node.node_id === selectedTopologyNodeId,
          'is-action': node.type !== 'page_state'
        }"
                 :style="getNodeStyle(node)"
                 @mousedown.stop="onNodeMouseDown($event, node)"
                 @contextmenu.prevent.stop="onNodeContextMenu($event, node)">
                <!-- 节点头部 -->
                <div class="node-header" :style="{ background: getNodeHeaderColor(node.type) }">
                    <component :is="getNodeIcon(node.type)" :size="14" />
                    <span class="node-title">{{ node.node_name || node.label || node.page_id || '未命名' }}</span>
                </div>

                <!-- 节点主体 -->
                <div class="node-body">
                    <div v-if="node.type === 'page_state' && node.page_id" class="node-info">
                        <span class="info-label">页面:</span> {{ node.page_id }}
                    </div>
                    <div v-if="node.features && node.features.length" class="node-info">
                        <span class="info-label">特征:</span> {{ node.features.length }} 个 ({{ node.feature_mode || 'and' }})
                    </div>
                    <div v-if="node.exits && node.exits.length" class="node-info">
                        <span class="info-label">出口:</span> {{ node.exits.length }} 个
                    </div>
                </div>

                <!-- 入口端口（左侧） -->
                <div class="node-port port-entry"
                     style="left: -6px; top: 50%; transform: translateY(-50%);"
                     title="入口"></div>

                <!-- 成功出口端口（底部中心） -->
                <div v-if="node.type === 'page_state' || node.type === 'smart_jump'"
                     class="node-port port-success"
                     style="left: 50%; bottom: -6px; transform: translateX(-50%);"
                     title="成功出口"
                     @mousedown.stop="startConnection($event, node, 'success')"></div>

                <!-- 失败出口端口（右侧底部） -->
                <div v-if="node.type === 'page_state' || node.type === 'image_recognition' || node.type === 'ocr_recognition'"
                     class="node-port port-failure"
                     style="right: -6px; bottom: 12px;"
                     title="失败出口"
                     @mousedown.stop="startConnection($event, node, 'failure')"></div>

                <!-- 动态多出口端口（右侧） -->
                <div v-for="(exit, idx) in (node.exits || [])"
                     :key="`exit_${idx}`"
                     class="node-port port-exit"
                     :style="{ right: '-6px', top: `${42 + idx * 28}px` }"
                     :title="exit.label || `出口${idx + 1}`"
                     @mousedown.stop="startConnection($event, node, `exit_${idx}`)"></div>
            </div>
        </div>

        <!-- 工具栏 -->
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

        <!-- 右键菜单 -->
        <div v-if="contextMenu.visible"
             class="canvas-context-menu"
             :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }">
            <template v-if="contextMenu.type === 'canvas'">
                <div class="menu-item" @click="addNode('page_state')">新增页面状态</div>
                <div class="menu-item" @click="addNode('click')">新增点击动作</div>
                <div class="menu-item" @click="addNode('wait')">新增等待动作</div>
                <div class="menu-item" @click="addNode('image_recognition')">新增图像识别</div>
                <div class="menu-item" @click="addNode('ocr_recognition')">新增 OCR 识别</div>
            </template>
            <template v-if="contextMenu.type === 'node'">
                <div class="menu-item" @click="editNodeCondition(contextMenu.node)">编辑条件</div>
                <div class="menu-item" @click="addExit(contextMenu.node)">新增出口</div>
                <div class="menu-item" @click="editNodeParams(contextMenu.node)">编辑参数</div>
                <div class="menu-divider"></div>
                <div class="menu-item menu-danger" @click="deleteNode(contextMenu.node)">删除节点</div>
            </template>
        </div>

        <!-- 条件编辑器 -->
        <ConditionDialog v-if="conditionDialog.visible"
                         :visible="conditionDialog.visible"
                         :initial-data="conditionDialog.data"
                         :show-jump-config="false"
                         @save="onConditionSave"
                         @close="conditionDialog.visible = false" />
    </div>
</template>

<script setup>
    import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
    import { useMainStore } from '@/stores/index'
    import {
        GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
        NODE_TYPE_CONFIG, getNodeConfig,
        snapToGrid, snapPositionToGrid,
        getPortPosition,
        resolveCollisionsAndPushOthers,
        ARROW_MARKERS_SVG
    } from '@/utils/canvasShared'
    import { computeEdgePath, getSimpleOrthoPath } from '@/utils/canvasRouter'
    import {
        Plus, Minus, Maximize, MousePointerClick, Timer, Image,
        Type, MapPin, Navigation, ScrollText, GitBranch, Filter,
        Variable, Code, AppWindow, Square
    } from 'lucide-vue-next'
    import ConditionDialog from '@/components/conditions/ConditionDialog.vue'

    const store = useMainStore()
    const containerRef = ref(null)

    // 视口状态
    const viewport = reactive({ x: 0, y: 0, zoom: 1 })
    const svgWidth = ref(5000)
    const svgHeight = ref(5000)

    // 交互状态
    const isPanning = ref(false)
    const panStart = reactive({ x: 0, y: 0, vx: 0, vy: 0 })
    const draggingNode = ref(null)
    const dragStart = reactive({ x: 0, y: 0, nx: 0, ny: 0 })
    const drawingConnection = reactive({
        active: false,
        sourceNode: null,
        sourcePort: 'success',
        mouseX: 0,
        mouseY: 0
    })
    const selectedEdgeId = ref(null)
    const contextMenu = reactive({ visible: false, x: 0, y: 0, type: 'canvas', node: null })
    const conditionDialog = reactive({ visible: false, data: null, node: null })

    // 节点白名单
    const NODE_WHITELIST = ['page_state', 'click', 'wait', 'log', 'image_recognition', 'ocr_recognition']

    // 图标映射
    const ICON_MAP = {
        MousePointerClick, Timer, Image, Type, MapPin, Navigation,
        ScrollText, GitBranch, Filter, Variable, Code, AppWindow, Square
    }

    // ========== 计算属性 ==========

    const topologyNodes = computed(() => store.topologyNodes)
    const topologyEdges = computed(() => store.topologyEdges)

    // 将拓扑节点转换为路由器需要的格式（带 size）
    const nodesForRouting = computed(() => {
        return topologyNodes.value.map(n => ({
            ...n,
            position: n.position || { x: 0, y: 0 },
            size: { w: NODE_WIDTH, h: getNodeHeight(n) }
        }))
    })

    function getNodeHeight(node) {
        let h = 38 // header
        if (node.type === 'page_state') {
            if (node.page_id) h += 18
            if (node.features?.length) h += 18
            if (node.exits?.length) h += 18
        }
        // 出口端口空间
        const exitCount = node.exits?.length || 0
        if (exitCount > 0) h = Math.max(h, 42 + exitCount * 28)
        return Math.max(NODE_MIN_HEIGHT, snapToGrid(h + 8))
    }

    // 渲染连线：使用 A* 寻路 + 边间距偏移
    const renderedEdges = computed(() => {
        if (!topologyNodes.value.length) return []

        const allNodes = nodesForRouting.value
        const result = []

        // 统计同源同目标的平行边数量
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
            const isDragging = draggingNode.value === sourceNode.node_id || draggingNode.value === targetNode.node_id

            const { pathD, markerId, points } = computeEdgePath(
                sourceNode, targetNode, allNodes, sourcePort,
                { isDragging, offsetIndex, totalParallel }
            )

            // 标签位置
            let labelX = 0, labelY = 0
            if (edge.label && points.length >= 2) {
                const midIdx = Math.floor(points.length / 2)
                labelX = (points[midIdx - 1].x + points[midIdx].x) / 2
                labelY = (points[midIdx - 1].y + points[midIdx].y) / 2 - 8
            }

            result.push({
                edge_id: edge.edge_id,
                pathD,
                markerId,
                source_port: sourcePort,
                label: edge.label || '',
                labelX,
                labelY
            })
        }

        return result
    })

    // 实时拉线预览路径
    const previewPathD = computed(() => {
        if (!drawingConnection.active || !drawingConnection.sourceNode) return ''
        const sourceNode = nodesForRouting.value.find(n => n.node_id === drawingConnection.sourceNode)
        if (!sourceNode) return ''

        const startPt = getPortPosition(sourceNode, drawingConnection.sourcePort)
        const endPt = { x: drawingConnection.mouseX, y: drawingConnection.mouseY }

        return getSimpleOrthoPath(startPt, endPt, drawingConnection.sourcePort)
    })

    // ========== 样式计算 ==========

    function getNodeStyle(node) {
        const pos = node.position || { x: 0, y: 0 }
        return {
            left: `${pos.x}px`,
            top: `${pos.y}px`,
            width: `${NODE_WIDTH}px`
        }
    }

    function getNodeHeaderColor(type) {
        const config = getNodeConfig(type)
        return config.color
    }

    function getNodeIcon(type) {
        const config = getNodeConfig(type)
        return ICON_MAP[config.icon] || Square
    }

    // ========== 端口位置 ==========（使用共享 getPortPosition，不再重复实现）

    // ========== 鼠标交互 ==========

    function onContainerMouseDown(e) {
        if (e.button === 0) {
            // 左键空白处：开始平移
            isPanning.value = true
            panStart.x = e.clientX
            panStart.y = e.clientY
            panStart.vx = viewport.x
            panStart.vy = viewport.y
            selectedEdgeId.value = null
            contextMenu.visible = false
        }
    }

    function onNodeMouseDown(e, node) {
        if (e.button !== 0) return
        e.preventDefault()

        store.selectTopologyNode(node.node_id)
        draggingNode.value = node.node_id

        dragStart.x = e.clientX
        dragStart.y = e.clientY
        dragStart.nx = node.position?.x || 0
        dragStart.ny = node.position?.y || 0

        // 注册全局 mousemove
        window.addEventListener('mousemove', onNodeMouseMove)
        window.addEventListener('mouseup', onNodeMouseUp)
    }

    function onNodeMouseMove(e) {
        if (!draggingNode.value) return

        const node = topologyNodes.value.find(n => n.node_id === draggingNode.value)
        if (!node) return

        const dx = (e.clientX - dragStart.x) / viewport.zoom
        const dy = (e.clientY - dragStart.y) / viewport.zoom

        const newX = snapToGrid(dragStart.nx + dx)
        const newY = snapToGrid(dragStart.ny + dy)

        node.position = { x: newX, y: newY }
    }

    function onNodeMouseUp(e) {
        if (draggingNode.value) {
            const draggedNode = topologyNodes.value.find(n => n.node_id === draggingNode.value)
            if (draggedNode) {
                // 碰撞推挤
                const pushed = resolveCollisionsAndPushOthers(topologyNodes.value, draggedNode)
                // 保存
                store.saveTopologyToBlueprint()
            }
            draggingNode.value = null
        }

        // 修复：连线释放由 onGlobalMouseUp 统一处理，此处不再重复

        window.removeEventListener('mousemove', onNodeMouseMove)
        window.removeEventListener('mouseup', onNodeMouseUp)
    }

    function onWheel(e) {
        const delta = e.deltaY > 0 ? 0.9 : 1.1
        const newZoom = Math.max(0.2, Math.min(4, viewport.zoom * delta))

        // 以鼠标位置为中心缩放
        const rect = containerRef.value.getBoundingClientRect()
        const mouseX = e.clientX - rect.left
        const mouseY = e.clientY - rect.top

        const wx = (mouseX - viewport.x) / viewport.zoom
        const wy = (mouseY - viewport.y) / viewport.zoom

        viewport.zoom = newZoom
        viewport.x = mouseX - wx * newZoom
        viewport.y = mouseY - wy * newZoom
    }

    // 全局 mousemove（平移 + 拉线）
    function onGlobalMouseMove(e) {
        if (isPanning.value) {
            viewport.x = panStart.vx + (e.clientX - panStart.x)
            viewport.y = panStart.vy + (e.clientY - panStart.y)
        }

        if (drawingConnection.active) {
            const rect = containerRef.value.getBoundingClientRect()
            drawingConnection.mouseX = (e.clientX - rect.left - viewport.x) / viewport.zoom
            drawingConnection.mouseY = (e.clientY - rect.top - viewport.y) / viewport.zoom
        }
    }

    function onGlobalMouseUp(e) {
        isPanning.value = false

        // 修复：在全局 mouseup 中处理连线释放（不依赖 onNodeMouseUp）
        if (drawingConnection.active) {
            handleConnectionDrop(e)
        }
    }

    // ========== 连线创建 ==========

    function startConnection(e, node, portType) {
        e.preventDefault()
        e.stopPropagation()

        drawingConnection.active = true
        drawingConnection.sourceNode = node.node_id
        drawingConnection.sourcePort = portType

        const rect = containerRef.value.getBoundingClientRect()
        drawingConnection.mouseX = (e.clientX - rect.left - viewport.x) / viewport.zoom
        drawingConnection.mouseY = (e.clientY - rect.top - viewport.y) / viewport.zoom

        // 修复：不再重复注册 onGlobalMouseMove/onGlobalMouseUp
        // 它们已在 onMounted 中注册，且 onGlobalMouseUp 会处理连线释放
    }

    function handleConnectionDrop(e) {
        drawingConnection.active = false

        // 检测是否释放在某个节点上
        const rect = containerRef.value.getBoundingClientRect()
        const dropX = (e.clientX - rect.left - viewport.x) / viewport.zoom
        const dropY = (e.clientY - rect.top - viewport.y) / viewport.zoom

        const targetNode = nodesForRouting.value.find(n => {
            const nx = n.position?.x || 0
            const ny = n.position?.y || 0
            const nw = NODE_WIDTH
            const nh = getNodeHeight(n)
            return dropX >= nx && dropX <= nx + nw && dropY >= ny && dropY <= ny + nh
        })

        if (targetNode && targetNode.node_id !== drawingConnection.sourceNode) {
            store.addTopologyEdge({
                edge_id: `edge_${Date.now()}`,
                source: drawingConnection.sourceNode,
                target: targetNode.node_id,
                source_port: drawingConnection.sourcePort,
                label: ''
            })
        }

        drawingConnection.sourceNode = null
        // 修复：不再移除全局监听器（由 onMounted/onUnmounted 管理）
    }

    function onEdgeClick(edge) {
        selectedEdgeId.value = edge.edge_id
    }

    // ========== 右键菜单 ==========

    function onContextMenu(e) {
        const rect = containerRef.value.getBoundingClientRect()
        contextMenu.x = e.clientX
        contextMenu.y = e.clientY
        contextMenu.type = 'canvas'
        contextMenu.visible = true
    }

    function onNodeContextMenu(e, node) {
        contextMenu.x = e.clientX
        contextMenu.y = e.clientY
        contextMenu.type = 'node'
        contextMenu.node = node
        contextMenu.visible = true
    }

    // ========== 节点操作 ==========

    function addNode(type) {
        if (!NODE_WHITELIST.includes(type)) return

        const rect = containerRef.value.getBoundingClientRect()
        const centerX = (rect.width / 2 - viewport.x) / viewport.zoom
        const centerY = (rect.height / 2 - viewport.y) / viewport.zoom

        const nodeData = {
            node_id: `topo_${Date.now()}`,
            node_name: getNodeConfig(type).label,
            type,
            page_id: type === 'page_state' ? `page_${Date.now().toString(36)}` : '',
            position: snapPositionToGrid(centerX - NODE_WIDTH / 2, centerY - 30),
            features: [],
            feature_mode: 'and',
            exits: [],
            params: {},
            condition: null
        }

        store.addTopologyNode(nodeData)
        contextMenu.visible = false
    }

    function deleteNode(node) {
        store.removeTopologyNode(node.node_id)
        contextMenu.visible = false
    }

    function addExit(node) {
        const exits = node.exits || []
        exits.push({
            exit_id: `exit_${Date.now()}`,
            label: `出口${exits.length + 1}`,
            target_page_id: '',
            action: ''
        })
        store.updateTopologyNode(node.node_id, { exits })
        contextMenu.visible = false
    }

    function editNodeCondition(node) {
        conditionDialog.data = node.condition
        conditionDialog.node = node
        conditionDialog.visible = true
        contextMenu.visible = false
    }

    function editNodeParams(node) {
        // 可以跳转到右侧检查器面板
        store.selectTopologyNode(node.node_id)
        contextMenu.visible = false
    }

    function onConditionSave(data) {
        if (conditionDialog.node) {
            store.updateTopologyNode(conditionDialog.node.node_id, { condition: data.condition })
        }
        conditionDialog.visible = false
    }

    // ========== 视图操作 ==========

    function zoomIn() {
        viewport.zoom = Math.min(4, viewport.zoom * 1.2)
    }

    function zoomOut() {
        viewport.zoom = Math.max(0.2, viewport.zoom * 0.8)
    }

    function resetView() {
        viewport.x = 0
        viewport.y = 0
        viewport.zoom = 1
    }

    // ========== 生命周期 ==========

    // 修复：提取为命名函数以便正确移除
    function onDocumentClick() {
        contextMenu.visible = false
    }

    onMounted(() => {
        window.addEventListener('mousemove', onGlobalMouseMove)
        window.addEventListener('mouseup', onGlobalMouseUp)
        document.addEventListener('click', onDocumentClick)

        // 初始化：如果拓扑数据为空，尝试从 blueprint 加载
        if (!topologyNodes.value.length) {
            store.loadTopologyFromBlueprint()
        }
    })

    onUnmounted(() => {
        window.removeEventListener('mousemove', onGlobalMouseMove)
        window.removeEventListener('mouseup', onGlobalMouseUp)
        // 修复：移除 document click 监听器，避免内存泄漏
        document.removeEventListener('click', onDocumentClick)
    })
</script>

<style scoped>
    .topology-canvas-container {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #1a1b26;
        cursor: grab;
    }

        .topology-canvas-container:active {
            cursor: grabbing;
        }

    .canvas-viewport {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
    }

    .canvas-edges-layer {
        position: absolute;
        top: 0;
        left: 0;
        pointer-events: none;
        overflow: visible;
    }

        .canvas-edges-layer .edge-path {
            pointer-events: stroke;
            cursor: pointer;
        }

    /* 使用共享样式 */
    :deep(.edge-path) {
        fill: none;
        stroke-width: 2.5px;
        stroke-linecap: round;
        stroke-linejoin: round;
        transition: stroke 0.2s, stroke-width 0.2s;
    }

    :deep(.edge-path.is-success) {
        stroke: #4ed19c;
    }

    :deep(.edge-path.is-failure) {
        stroke: #f56c6c;
    }

    :deep(.edge-path.is-selected) {
        stroke: #ffffff;
        stroke-width: 4px;
        filter: drop-shadow(0 0 6px rgba(255,255,255,0.6));
    }

    :deep(.edge-path:hover) {
        stroke-width: 4px;
        filter: drop-shadow(0 0 4px rgba(255,255,255,0.4));
    }

    :deep(.edge-flow-path) {
        fill: none;
        stroke: rgba(255, 255, 255, 0.7);
        stroke-width: 2px;
        stroke-dasharray: 8 16;
        animation: edgeFlow 0.8s linear infinite;
        pointer-events: none;
    }

    @keyframes edgeFlow {
        from {
            stroke-dashoffset: 24;
        }

        to {
            stroke-dashoffset: 0;
        }
    }

    .edge-label {
        fill: #a0a1ab;
        font-size: 11px;
        pointer-events: none;
    }

    /* 节点卡片 */
    .canvas-node-card {
        position: absolute;
        background: #1e1f2b;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        overflow: visible;
        cursor: move;
        user-select: none;
        transition: box-shadow 0.2s, border-color 0.2s;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

        .canvas-node-card:hover {
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            border-color: rgba(78, 209, 156, 0.4);
        }

        .canvas-node-card.is-selected {
            border-color: #4ed19c;
            box-shadow: 0 0 0 2px rgba(78, 209, 156, 0.3), 0 4px 16px rgba(0, 0, 0, 0.3);
        }

        .canvas-node-card.is-action {
            border-style: dashed;
        }

    .node-header {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 8px 8px 0 0;
        font-size: 12px;
        font-weight: 500;
        color: #fff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .node-title {
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .node-body {
        padding: 6px 10px;
        font-size: 11px;
        color: #a0a1ab;
    }

    .node-info {
        line-height: 18px;
    }

    .info-label {
        color: #6b7280;
    }

    /* 端口 */
    .node-port {
        position: absolute;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        border: 2px solid #1e1f2b;
        cursor: crosshair;
        z-index: 10;
        transition: transform 0.15s;
    }

        .node-port:hover {
            transform: scale(1.4);
        }

        .node-port.port-success {
            background: #4ed19c;
        }

        .node-port.port-failure {
            background: #f56c6c;
        }

        .node-port.port-entry {
            background: #909399;
            cursor: default;
        }

        .node-port.port-exit {
            background: #4ed19c;
        }

    /* 网格背景 */
    .grid-background {
        background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
        background-size: 20px 20px;
    }

    /* 工具栏 */
    .canvas-toolbar {
        position: absolute;
        bottom: 16px;
        right: 16px;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        background: rgba(30, 31, 43, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        backdrop-filter: blur(8px);
        z-index: 100;
    }

    .toolbar-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border: none;
        background: transparent;
        color: #a0a1ab;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.2s, color 0.2s;
    }

        .toolbar-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }

    .zoom-display {
        font-size: 12px;
        color: #a0a1ab;
        min-width: 40px;
        text-align: center;
    }

    /* 右键菜单 */
    .canvas-context-menu {
        position: fixed;
        min-width: 160px;
        background: rgba(30, 31, 43, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 4px 0;
        z-index: 1000;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }

    .menu-item {
        padding: 8px 16px;
        font-size: 13px;
        color: #e0e0e0;
        cursor: pointer;
        transition: background 0.15s;
    }

        .menu-item:hover {
            background: rgba(78, 209, 156, 0.15);
        }

        .menu-item.menu-danger:hover {
            background: rgba(245, 108, 108, 0.15);
            color: #f56c6c;
        }

    .menu-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.1);
        margin: 4px 0;
    }
</style>
