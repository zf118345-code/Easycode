<template>
    <div ref="containerRef"
         class="custom-canvas-container"
         @mousedown="onCanvasMouseDown"
         @wheel="onCanvasWheel"
         @contextmenu="onContextMenu">

        <!-- 视口变换层 -->
        <div class="canvas-viewport" :style="viewportStyle">

            <!-- SVG 连线层 -->
            <svg class="canvas-edges-layer">
                <defs>
                    <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
                        <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1" />
                    </pattern>

                    <marker id="arrow-succ-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 2 L 8 2 L 5 9 z" fill="#4ed19c" />
                    </marker>
                    <marker id="arrow-succ-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 8 L 8 8 L 5 1 z" fill="#4ed19c" />
                    </marker>
                    <marker id="arrow-succ-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 2 L 2 8 L 9 5 z" fill="#4ed19c" />
                    </marker>
                    <marker id="arrow-succ-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 8 2 L 8 8 L 1 5 z" fill="#4ed19c" />
                    </marker>

                    <marker id="arrow-fail-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 2 L 8 2 L 5 9 z" fill="#f56c6c" />
                    </marker>
                    <marker id="arrow-fail-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 8 L 8 8 L 5 1 z" fill="#f56c6c" />
                    </marker>
                    <marker id="arrow-fail-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 2 2 L 2 8 L 9 5 z" fill="#f56c6c" />
                    </marker>
                    <marker id="arrow-fail-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
                        <path d="M 8 2 L 8 8 L 1 5 z" fill="#f56c6c" />
                    </marker>

                    <marker id="arrow-preview" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 2 L 10 5 L 0 8 z" fill="#4ed19c" />
                    </marker>
                </defs>

                <rect x="-5000" y="-5000" width="15000" height="15000" fill="url(#grid-pattern)" pointer-events="none" />

                <!-- 纯净流光连线层 -->
                <g v-for="edge in computedEdges" :key="edge.id">
                    <path :d="edge.path"
                          :class="['edge-path', { 'is-selected': edge.selected, 'is-danger': edge.isFail }]"
                          :marker-end="edge.markerUrl"
                          @click.stop="onEdgeClick(edge)" />
                    <path :d="edge.path"
                          :class="['edge-flow-path', { 'is-danger': edge.isFail }]"
                          pointer-events="none" />
                </g>

                <path v-if="drawingConnection.active" :d="drawingConnection.path" class="edge-path preview-path" :marker-end="drawingConnection.previewMarkerUrl" />
            </svg>

            <!-- 任务组包围框 -->
            <div v-for="group in dynamicGroups"
                 :key="group.groupId"
                 :data-group-id="group.groupId"
                 :class="['canvas-group-box', { 'is-focused': activeFocusedGroupId === group.groupId }]"
                 :style="{
                     left: group.box.x + 'px',
                     top: group.box.y + 'px',
                     width: group.box.w + 'px',
                     height: group.box.h + 'px'
                 }">
                <div class="group-title-badge" :data-group-id="group.groupId" @mousedown.stop="startGroupDrag($event, group.groupId)" @dblclick.stop="openGroupInspector($event, group)">
                    <div class="group-name-text">📁 {{ group.groupName }}</div>
                    <div class="group-sub-info">
                        <span>间隔: {{ group.loopInterval || 0 }}s</span>
                        <span>循环: {{ group.loopCount }}次</span>
                    </div>
                </div>
            </div>

            <!-- 节点拖拽预览框 -->
            <div v-if="draggingNodeId && dragPreviewBox.visible"
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

            <!-- 节点卡片层 -->
            <div v-for="node in renderNodes"
                 :key="node.node_id"
                 :data-node-id="node.node_id"
                 :class="['canvas-node-card', { 'is-selected': node.selected }]"
                 :style="{ left: node.position.x + 'px', top: node.position.y + 'px', width: node.w + 'px', height: node.h + 'px' }"
                 @mousedown.stop="onNodeMouseDown($event, node)"
                 @mouseup="onNodeMouseUpCard($event, node)"
                 @dblclick.stop="onNodeDoubleClick($event, node)">

                <!-- 1. 卡片头部：左侧图标 + 名称 -->
                <div class="node-header" :data-node-id="node.node_id">
                    <div class="node-header-left" :data-node-id="node.node_id">
                        <component :is="getNodeIcon(node.node_type)" class="node-type-icon" />
                        <span class="node-title" :data-node-id="node.node_id">{{ node.node_name }}</span>
                    </div>
                </div>

                <!-- 2. 卡片中间主体区：最高限制 1:1，超高图自动应用高斯模糊背景和 contain -->
                <div class="node-body" :data-node-id="node.node_id">
                    <div v-if="node.node_type === 'image_recognition'"
                         class="node-image-embedded"
                         :style="node.params?.image_source ? { '--bg-image-url': `url(${getImageThumbnailUrl(node.params.image_source)})` } : {}">
                        <img v-if="node.params?.image_source"
                             :src="getImageThumbnailUrl(node.params.image_source)"
                             :class="['embedded-template-img', { 'is-contain': isSpecialTallImage(node.node_id) }]"
                             alt="模板"
                             @load="(e) => onImageLoaded(e, node.node_id)"
                             @error="$event.target.style.display = 'none'" />
                        <div v-else class="embedded-placeholder">
                            <Image style="width: 16px; height: 16px; opacity: 0.5; margin-bottom: 2px;" />
                            <span>未选模板</span>
                        </div>
                    </div>
                </div>

                <!-- 3. 卡片底部固定边栏（Footer）：居左对齐展示延时与循环 -->
                <div class="node-footer-bar" :data-node-id="node.node_id">
                    <span class="footer-tag">延时: {{ node.delay_before ?? 200 }}ms</span>
                    <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
                </div>

                <div class="node-handle target-handle top-handle" title="入口位置"></div>
                <div class="node-handle source-handle succ-handle" title="成功流向出口" @mousedown.stop="startConnection($event, node.node_id, 'succ')"></div>
                <div v-if="node.showFailPort" class="node-handle source-handle fail-handle" title="失败分支出口" @mousedown.stop="startConnection($event, node.node_id, 'fail')"></div>
            </div>

        </div>

        <!-- 1. 绑定 store.logExpanded 的运行控制台日志面板 -->
        <div class="canvas-log-panel" v-show="store.logExpanded">
            <div class="log-panel-header" @click="store.toggleLogPanel">
                <span>📝 运行控制台日志</span>
                <span class="collapse-icon">▼ 收起</span>
            </div>
            <div class="log-panel-body">
                <div class="log-placeholder-text">暂无最新运行日志输出...</div>
            </div>
        </div>

        <!-- 2. 绑定 store.minimapExpanded 的全景缩略图导航面板 -->
        <div class="minimap-container" v-show="store.minimapExpanded">
            <div class="minimap-header" @click="store.toggleMinimap">
                <span>🗺️ 全景导航</span>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="minimap-body">
                <canvas ref="minimapCanvasRef" width="200" height="150" @click="onMinimapClick"></canvas>
            </div>
        </div>

        <!-- 框选UI -->
        <div v-if="selectionBox.visible" class="selection-box" :style="selectionBoxStyle"></div>

        <!-- 节点类型选择菜单 -->
        <div v-if="spawnMenu.visible"
             class="spawn-menu"
             :style="{ left: spawnMenu.x + 'px', top: spawnMenu.y + 'px' }"
             @mousedown.stop
             @click.stop>
            <div class="spawn-menu-header">
                ⚡ {{ spawnMenu.sourceNodeId ? `快捷创建并连接` : '✨ 选择新建节点类型' }}
            </div>
            <div class="spawn-menu-list">
                <div v-for="(label, type) in availableNodeTypes" :key="type" class="spawn-menu-item" @click="createAndConnectNode(type)">
                    {{ label }}
                </div>
            </div>
        </div>

        <!-- 画布空白处右键菜单（已精简：去除头部，纯净Windows风格） -->
        <div v-if="customContextMenu.visible"
             class="custom-context-menu"
             :style="{ left: customContextMenu.x + 'px', top: customContextMenu.y + 'px' }"
             @mousedown.stop
             @click.stop>

            <template v-if="customContextMenu.targetType === 'node'">
                <div class="menu-item" @click="handleRunFromNode">
                    <CirclePlay class="menu-item-icon" style="color: var(--el-color-primary);" />
                    <span>从此节点开始运行</span>
                </div>
                <div class="menu-item danger" @click="handleDeleteNode">
                    <Trash2 class="menu-item-icon" />
                    <span>删除节点</span>
                </div>
            </template>

            <template v-else-if="customContextMenu.targetType === 'group'">
                <div class="menu-item danger" @click="handleDeleteGroup">
                    <Trash2 class="menu-item-icon" />
                    <span>删除组</span>
                </div>
            </template>

            <template v-else-if="customContextMenu.targetType === 'canvas_in_group'">
                <div class="menu-item" @click="handleCanvasNewNode">
                    📁 在当前组 [{{ customContextMenu.targetName }}] 新建节点
                </div>
                <div class="menu-item" @click="handleCanvasNewGroup">
                    📁 新建任务组
                </div>
            </template>

            <template v-else-if="customContextMenu.targetType === 'canvas_public'">
                <div class="menu-item" @click="handleCanvasNewNode">
                    ✨ 在新建组中新建节点
                </div>
                <div class="menu-item" @click="handleCanvasNewGroup">
                    📁 新建任务组
                </div>
            </template>

            <template v-else>
                <div class="menu-item" @click="handleCanvasNewGroup">
                    📁 新建任务组
                </div>
                <div class="menu-item" @click="handleCanvasNewNode">
                    ✨ 新建节点
                </div>
            </template>
        </div>

        <WorkflowInspector v-if="inspector.visible"
                           :visible="inspector.visible"
                           :target-type="inspector.targetType"
                           :target-data="inspector.targetData"
                           :targets="inspector.targets"
                           :position="inspector.position"
                           @update="onInspectorUpdate"
                           @close="closeInspector" />
    </div>
</template>

<script>
    import { ref, computed, onMounted, onUnmounted, reactive, nextTick, watch } from 'vue'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import axios from 'axios'
    import WorkflowInspector from './WorkflowInspector.vue'
    import { router } from '@/utils/gridRouter'
    import { getRoundedPathString } from '@/utils/pathSmooth'

    import {
        MousePointerClick,
        Clock,
        Target,
        FileSearch,
        GitBranch,
        SearchCheck,
        Binary,
        ListOrdered,
        FileCode,
        Image,
        CirclePlay,
        Trash2
    } from 'lucide-vue-next'

    export default {
        name: 'WorkflowCanvas',
        components: {
            WorkflowInspector,
            MousePointerClick,
            Clock,
            Target,
            FileSearch,
            GitBranch,
            SearchCheck,
            Binary,
            ListOrdered,
            FileCode,
            Image,
            CirclePlay,
            Trash2
        },
        setup() {
            const store = useMainStore()
            const containerRef = ref(null)
            const minimapCanvasRef = ref(null)

            const isCtrlHeldRef = ref(false)
            const draggedSourceGroupSnapshot = ref(null)
            const ghostPlaceholder = ref(null)

            const viewport = ref({ x: 0, y: 0, zoom: 1 })
            const isPanning = ref(false)
            const panStart = ref({ x: 0, y: 0 })

            const localDraftPositions = reactive({})
            const draggingNodeId = ref(null)
            const dragStartMouse = ref({ x: 0, y: 0 })
            const nodeInitialPos = ref({ x: 0, y: 0 })
            const hasMoved = ref(false)

            const dynamicImageHeights = reactive({})
            const tallImageFlags = reactive({})

            const dragPreviewBox = ref({ visible: false, x: 0, y: 0, w: 0, h: 0, hasCollision: false })

            const selectionBox = ref({ visible: false, startX: 0, startY: 0, endX: 0, endY: 0 })
            const drawingConnection = ref({ active: false, sourceNodeId: null, portType: 'succ', currentX: 0, currentY: 0, previewMarkerUrl: 'url(#arrow-preview)' })

            const spawnMenu = ref({ visible: false, x: 0, y: 0, sourceNodeId: null, portType: 'succ', clientX: 0, clientY: 0 })

            const customContextMenu = reactive({
                visible: false,
                x: 0,
                y: 0,
                targetType: 'canvas',
                targetId: null,
                targetName: '',
                clientX: 0,
                clientY: 0
            })

            const inspector = ref({ visible: false, targetType: 'node', targetData: null, targets: [], position: { x: 100, y: 100 } })

            const selectedEdgeId = ref(null)
            const localSelectedNodeIds = ref([])

            const GRID_SIZE = 20
            const NODE_GRID_W = 8

            const availableNodeTypes = {
                click: '🖱️ 鼠标点击',
                wait: '⏳ 等待',
                image_recognition: '🎯 图像识别',
                ocr_recognition: '👁️ 文字识别 (OCR)',
                branch: '🔀 分支选择',
                logic_check: '🔍 逻辑判断',
                variable_op: '🔢 变量操作',
                log: '📝 日志输出',
                script_call: '📜 调用脚本'
            }

            const nodeIconComponentMap = {
                click: 'MousePointerClick',
                wait: 'Clock',
                image_recognition: 'Target',
                ocr_recognition: 'FileSearch',
                branch: 'GitBranch',
                logic_check: 'SearchCheck',
                variable_op: 'Binary',
                log: 'ListOrdered',
                script_call: 'FileCode'
            }

            const getNodeIcon = (nodeType) => {
                return nodeIconComponentMap[nodeType] || 'FileCode'
            }

            const getNodeShortLabel = (nodeType) => {
                const label = availableNodeTypes[nodeType] || nodeType
                return label.replace(/^[^\u4e00-\u9fa5]+/, '').trim()
            }

            const getImageThumbnailUrl = (imageSource) => {
                if (!imageSource) return ''
                let cleanName = imageSource.replace(/\\/g, '/')
                if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) {
                    cleanName += '.png'
                }
                const version = store.taskNodesVersion || 0
                return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&v=${version}`
            }

            const hasFailurePort = (nodeType) => {
                return ['image_recognition', 'ocr_recognition', 'branch', 'logic_check'].includes(nodeType)
            }

            const viewportStyle = computed(() => ({
                transform: `translate(${viewport.value.x}px, ${viewport.value.y}px) scale(${viewport.value.zoom})`,
                transformOrigin: '0 0'
            }))

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
                    const tasks = store.currentTaskData?.tasks || []
                    for (let i = 0; i < tasks.length; i++) {
                        if ((tasks[i].nodes || []).some(n => n.node_id === draggingNodeId.value)) {
                            return `group_${tasks[i].task_id || i}`
                        }
                    }
                }
                if (localSelectedNodeIds.value.length > 0) {
                    const firstSelId = localSelectedNodeIds.value[0]
                    const tasks = store.currentTaskData?.tasks || []
                    for (let i = 0; i < tasks.length; i++) {
                        if ((tasks[i].nodes || []).some(n => n.node_id === firstSelId)) {
                            return `group_${tasks[i].task_id || i}`
                        }
                    }
                }
                return null
            })

            const isNodeFocused = (nodeId) => {
                if (!activeFocusedGroupId.value) return false
                const tasks = store.currentTaskData?.tasks || []
                for (let i = 0; i < tasks.length; i++) {
                    const gId = `group_${tasks[i].task_id || i}`
                    if (gId === activeFocusedGroupId.value) {
                        return (tasks[i].nodes || []).some(n => n.node_id === nodeId)
                    }
                }
                return false
            }

            const renderNodes = computed(() => {
                const tasks = store.currentTaskData?.tasks || []
                let allNodesList = []

                tasks.forEach((task) => {
                    const rawNodes = task.nodes || []
                    rawNodes.forEach((node, nIndex) => {
                        const rawPos = localDraftPositions[node.node_id] || node.position || { x: 60 + (nIndex % 3) * 200, y: 60 + Math.floor(nIndex / 3) * 120 }
                        const gridX = Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE
                        const gridY = Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
                        const isSel = localSelectedNodeIds.value.includes(node.node_id)

                        let contentHeightPx = 52
                        if (node.node_type === 'image_recognition') {
                            if (dynamicImageHeights[node.node_id]) {
                                contentHeightPx += dynamicImageHeights[node.node_id]
                            } else {
                                contentHeightPx += 120
                            }
                        }

                        const exactGrids = contentHeightPx / GRID_SIZE
                        const gridCount = Math.ceil(exactGrids)
                        const finalHeight = gridCount * GRID_SIZE

                        allNodesList.push({
                            ...node,
                            position: { x: gridX, y: gridY },
                            w: NODE_GRID_W * GRID_SIZE,
                            h: finalHeight,
                            showFailPort: hasFailurePort(node.node_type),
                            selected: isSel
                        })
                    })
                })
                return allNodesList
            })

            const onImageLoaded = (e, nodeId) => {
                const img = e.target
                const naturalW = img.naturalWidth || 100
                const naturalH = img.naturalHeight || 100
                const cardInnerWidth = (NODE_GRID_W * GRID_SIZE) - 24

                const ratio = naturalH / naturalW
                if (ratio > 1) {
                    tallImageFlags[nodeId] = true
                    dynamicImageHeights[nodeId] = cardInnerWidth
                } else {
                    tallImageFlags[nodeId] = false
                    dynamicImageHeights[nodeId] = Math.round(cardInnerWidth * ratio)
                }
            }

            const isSpecialTallImage = (nodeId) => {
                return !!tallImageFlags[nodeId]
            }

            const fitViewToNodes = () => {
                nextTick(() => {
                    const tasks = store.currentTaskData?.tasks || []
                    let allNodes = []
                    tasks.forEach(t => { if (t.nodes) allNodes.push(...t.nodes) })
                    if (allNodes.length === 0 || !containerRef.value) return

                    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
                    allNodes.forEach(n => {
                        const pos = n.position || { x: 0, y: 0 }
                        const w = NODE_GRID_W * GRID_SIZE
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

                    if (typeof drawMinimap === 'function') {
                        drawMinimap()
                    }
                })
            }

            const dynamicGroups = computed(() => {
                const tasks = store.currentTaskData?.tasks || []
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

                if (!containerRef.value) return
                const rect = containerRef.value.getBoundingClientRect()
                const clientX = e.clientX - rect.left
                const clientY = e.clientY - rect.top
                const worldX = (clientX - viewport.value.x) / viewport.value.zoom
                const worldY = (clientY - viewport.value.y) / viewport.value.zoom

                let hitGroup = null
                for (const g of dynamicGroups.value) {
                    const box = g.box
                    if (worldX >= box.x && worldX <= box.x + box.w && worldY >= box.y && worldY <= box.y + box.h) {
                        hitGroup = g
                        break
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

            // ⭐ 从当前节点开始运行
            const handleRunFromNode = async () => {
                const nodeId = customContextMenu.targetId
                customContextMenu.visible = false
                if (!nodeId) return

                let targetTaskId = null
                const tasks = store.currentTaskData?.tasks || []
                for (const task of tasks) {
                    if ((task.nodes || []).some(n => n.node_id === nodeId)) {
                        targetTaskId = task.task_id
                        break
                    }
                }

                if (!targetTaskId) {
                    ElMessage.error('未找到该节点所属的任务组')
                    return
                }

                try {
                    ElMessage.info('正在从当前节点启动任务...')
                    const result = await store.runTask(targetTaskId, nodeId)
                    if (result.status === 'started') {
                        ElMessage.success('任务已成功从当前节点启动！')
                    } else {
                        ElMessage.error('执行失败: ' + (result.message || '未知错误'))
                    }
                } catch (err) {
                    ElMessage.error('执行请求失败: ' + (err.response?.data?.detail || err.message))
                }
            }

            const handleDeleteNode = async () => {
                const nodeId = customContextMenu.targetId
                customContextMenu.visible = false
                if (!nodeId) return

                try {
                    const tasks = store.currentTaskData?.tasks || []
                    for (const task of tasks) {
                        if (task.nodes) {
                            task.nodes = task.nodes.filter(n => n.node_id !== nodeId)
                        }
                    }
                    store.currentTaskData.tasks = tasks.filter(t => (t.nodes || []).length > 0)

                    await axios.post('/api/blueprint/save', {
                        project_path: store.currentProjectPath,
                        blueprint_data: store.currentTaskData
                    })
                    await store.loadTasks()
                    store.taskNodesVersion++
                    ElMessage.success('节点已成功删除')
                } catch (err) {
                    ElMessage.error('删除节点失败')
                }
            }

            const handleDeleteGroup = async () => {
                const taskId = customContextMenu.targetId
                customContextMenu.visible = false
                if (!taskId) return

                try {
                    await axios.delete(`/api/tasks/${taskId}`, {
                        params: { project_path: store.currentProjectPath }
                    })
                    await store.loadTasks()
                    store.taskNodesVersion++
                    ElMessage.success('任务组已成功删除')
                } catch (err) {
                    ElMessage.error('删除任务组失败: ' + (err.response?.data?.detail || err.message))
                }
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
                customContextMenu.visible = false
                try {
                    const { value: groupName } = await ElMessageBox.prompt('请输入新任务组名称', '新建任务组', {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        inputPattern: /\S+/,
                        inputErrorMessage: '任务组名称不能为空'
                    })

                    if (groupName) {
                        await store.createNewTask(groupName.trim())
                        await store.loadTasks()
                        store.taskNodesVersion++
                        ElMessage.success(`任务组 [${groupName}] 创建成功`)
                    }
                } catch (err) {
                    if (err !== 'cancel') {
                        ElMessage.error(err.message || '创建任务组失败')
                    }
                }
            }

            const getArrowDirection = (points) => {
                if (!points || points.length < 2) return 'down'
                let p1 = points[points.length - 2]
                let p2 = points[points.length - 1]

                for (let i = points.length - 1; i > 0; i--) {
                    if (points[i].x !== points[i - 1].x || points[i].y !== points[i - 1].y) {
                        p2 = points[i]
                        p1 = points[i - 1]
                        break
                    }
                }

                const dx = p2.x - p1.x
                const dy = p2.y - p1.y

                let dir = 'down'
                if (Math.abs(dx) >= Math.abs(dy)) {
                    dir = dx > 0 ? 'right' : 'left'
                } else {
                    dir = dy > 0 ? 'down' : 'up'
                }
                return dir
            }

            const computedEdges = computed(() => {
                let edges = []
                const allNodes = renderNodes.value
                const activeDraggingId = draggingNodeId.value
                const isActuallyMoving = hasMoved.value

                allNodes.forEach(node => {
                    if (node.params?.on_success?.target_node) {
                        const target = allNodes.find(n => n.node_id === node.params.on_success.target_node)
                        if (target) {
                            let smoothPathStr = ''
                            let arrowDir = 'down'
                            let routeResult = null

                            const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)

                            if (isThisEdgeDragging) {
                                const startPt = { x: node.position.x + node.w / 2, y: node.position.y + node.h }
                                const endPt = { x: target.position.x + target.w / 2, y: target.position.y }
                                const simplePoints = [startPt, { x: startPt.x, y: (startPt.y + endPt.y) / 2 }, { x: endPt.x, y: (startPt.y + endPt.y) / 2 }, endPt]
                                smoothPathStr = getRoundedPathString(simplePoints, 10)
                                arrowDir = getArrowDirection(simplePoints)
                                routeResult = { startPt, endPt }
                            } else {
                                const rr = router.route(node, target, allNodes, 'succ', true)
                                routeResult = rr
                                smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
                                arrowDir = getArrowDirection(rr.rawPixelPoints)
                            }

                            const edgeId = `e_${node.node_id}_succ_${target.node_id}`
                            edges.push({
                                id: edgeId,
                                sourceNodeId: node.node_id,
                                targetNodeId: target.node_id,
                                typeFlag: 'succ',
                                path: smoothPathStr,
                                isFail: false,
                                markerUrl: `url(#arrow-succ-${arrowDir})`,
                                selected: selectedEdgeId.value === edgeId,
                                labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
                                labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
                                rawPixelPoints: routeResult.rawPixelPoints || []
                            })
                        }
                    }

                    if (node.params?.on_failure?.target_node) {
                        const target = allNodes.find(n => n.node_id === node.params.on_failure.target_node)
                        if (target) {
                            let smoothPathStr = ''
                            let arrowDir = 'down'
                            let routeResult = null

                            const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)

                            if (isThisEdgeDragging) {
                                const startPt = { x: node.position.x + node.w, y: node.position.y + node.h / 2 }
                                const endPt = { x: target.position.x, y: target.position.y + target.h / 2 }
                                const simplePoints = [startPt, { x: (startPt.x + endPt.x) / 2, y: startPt.y }, { x: (startPt.x + endPt.x) / 2, y: endPt.y }, endPt]
                                smoothPathStr = getRoundedPathString(simplePoints, 10)
                                arrowDir = getArrowDirection(simplePoints)
                                routeResult = { startPt, endPt }
                            } else {
                                const rr = router.route(node, target, allNodes, 'fail')
                                routeResult = rr
                                smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
                                arrowDir = getArrowDirection(rr.rawPixelPoints)
                            }

                            const edgeId = `e_${node.node_id}_fail_${target.node_id}`
                            edges.push({
                                id: edgeId,
                                sourceNodeId: node.node_id,
                                targetNodeId: target.node_id,
                                typeFlag: 'fail',
                                path: smoothPathStr,
                                isFail: true,
                                markerUrl: `url(#arrow-fail-${arrowDir})`,
                                selected: selectedEdgeId.value === edgeId,
                                labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
                                labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
                                rawPixelPoints: routeResult.rawPixelPoints || []
                            })
                        }
                    }
                })

                if (drawingConnection.value.active) {
                    const sourceNode = allNodes.find(n => n.node_id === drawingConnection.value.sourceNodeId)
                    if (sourceNode) {
                        const startPt = drawingConnection.value.portType === 'succ'
                            ? { x: sourceNode.position.x + sourceNode.w / 2, y: sourceNode.position.y + sourceNode.h }
                            : { x: sourceNode.position.x + sourceNode.w, y: sourceNode.position.y + sourceNode.h / 2 }

                        const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }

                        let safeStartY = startPt.y
                        if (drawingConnection.value.portType === 'succ') {
                            safeStartY = Math.max(startPt.y + 20, mousePt.y)
                        }

                        const rawPoints = [
                            startPt,
                            { x: startPt.x, y: safeStartY },
                            { x: mousePt.x, y: safeStartY },
                            mousePt
                        ]

                        const pathStr = getRoundedPathString(rawPoints, 10)
                        const arrowDir = getArrowDirection(rawPoints)
                        drawingConnection.value.previewMarkerUrl = `url(#arrow-${drawingConnection.value.portType === 'fail' ? 'fail' : 'succ'}-${arrowDir})`

                        edges.push({
                            id: 'temp_drawing',
                            path: pathStr,
                            label: '',
                            isFail: drawingConnection.value.portType === 'fail',
                            markerUrl: drawingConnection.value.previewMarkerUrl,
                            selected: false,
                            labelX: 0,
                            labelY: 0,
                            gridPoints: [],
                            rawPixelPoints: rawPoints
                        })
                    }
                }

                return edges
            })

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

            watch(() => store.minimapExpanded, (val) => {
                if (val) {
                    nextTick(drawMinimap)
                }
            })

            const onCanvasMouseDown = (e) => {
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
                    selectedEdgeId.value = null
                    inspector.value.visible = false
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

                const tasks = store.currentTaskData?.tasks || []
                tasks.forEach((t, tIdx) => {
                    const found = (t.nodes || []).find(n => n.node_id === node.node_id)
                    if (found) {
                        const groupInfo = dynamicGroups.value[tIdx]
                        if (groupInfo && groupInfo.box) {
                            draggedSourceGroupSnapshot.value = { ...groupInfo.box }
                        }
                    }
                })

                if (e.ctrlKey) {
                    if (localSelectedNodeIds.value.includes(node.node_id)) {
                        localSelectedNodeIds.value = localSelectedNodeIds.value.filter(id => id !== node.node_id)
                    } else {
                        localSelectedNodeIds.value.push(node.node_id)
                    }
                } else {
                    if (!localSelectedNodeIds.value.includes(node.node_id)) {
                        localSelectedNodeIds.value = [node.node_id]
                    }
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

            const resolveCollisionsAndPushOthers = (targetNodeId, dropPos, allNodes, nodeSize) => {
                const GAP_GRIDS = 2

                let movingNodes = [{ id: targetNodeId, pos: { ...dropPos }, h: nodeSize.h, w: nodeSize.w }]
                localDraftPositions[targetNodeId] = { ...dropPos }

                let maxIterations = 15
                let iteration = 0

                while (iteration < maxIterations) {
                    iteration++
                    let hasNewCollision = false

                    for (let i = 0; i < movingNodes.length; i++) {
                        const current = movingNodes[i]
                        const currPos = current.pos
                        const currSize = { w: current.w || nodeSize.w, h: current.h || nodeSize.h }

                        for (const other of allNodes) {
                            if (other.node_id === current.id) continue
                            if (movingNodes.some(m => m.id === other.node_id)) continue
                            if (ghostPlaceholder.value && other.node_id === ghostPlaceholder.value.node_id) continue

                            const alreadyMoved = movingNodes.find(m => m.id === other.node_id)
                            const otherPos = alreadyMoved ? alreadyMoved.pos : (localDraftPositions[other.node_id] || other.position)
                            const otherSize = {
                                w: other.w || nodeSize.w,
                                h: alreadyMoved ? alreadyMoved.h : (other.h || 120)
                            }

                            const isIntersect = !(
                                currPos.x + currSize.w + 40 <= otherPos.x ||
                                currPos.x >= otherPos.x + otherSize.w + 40 ||
                                currPos.y + currSize.h + 40 <= otherPos.y ||
                                currPos.y >= otherPos.y + otherSize.h + 40
                            )

                            if (isIntersect) {
                                hasNewCollision = true

                                const currCenterX = currPos.x + currSize.w / 2
                                const otherCenterX = otherPos.x + otherSize.w / 2
                                const currCenterY = currPos.y + currSize.h / 2
                                const otherCenterY = otherPos.y + otherSize.h / 2

                                const dx = currCenterX - otherCenterX
                                const dy = currCenterY - otherCenterY

                                let nextPos = { ...otherPos }

                                if (Math.abs(dx) > Math.abs(dy)) {
                                    if (dx < 0) {
                                        const overlapPx = (currPos.x + currSize.w) - otherPos.x
                                        const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
                                        nextPos.x = otherPos.x + (overlapGrids + GAP_GRIDS) * GRID_SIZE
                                    } else {
                                        const overlapPx = (otherPos.x + otherSize.w) - currPos.x
                                        const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
                                        nextPos.x = otherPos.x - (overlapGrids + GAP_GRIDS) * GRID_SIZE
                                    }
                                } else {
                                    if (dy < 0) {
                                        const overlapPx = (currPos.y + currSize.h) - otherPos.y
                                        const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
                                        nextPos.y = otherPos.y + (overlapGrids + GAP_GRIDS) * GRID_SIZE
                                    } else {
                                        const overlapPx = (otherPos.y + otherSize.h) - currPos.y
                                        const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
                                        nextPos.y = otherPos.y - (overlapGrids + GAP_GRIDS) * GRID_SIZE
                                    }
                                }

                                nextPos.x = Math.round(nextPos.x / GRID_SIZE) * GRID_SIZE
                                nextPos.y = Math.round(nextPos.y / GRID_SIZE) * GRID_SIZE

                                localDraftPositions[other.node_id] = nextPos
                                other.position = nextPos

                                movingNodes.push({
                                    id: other.node_id,
                                    pos: nextPos,
                                    h: otherSize.h,
                                    w: otherSize.w
                                })
                            }
                        }
                    }
                    if (!hasNewCollision) break
                }
                return localDraftPositions[targetNodeId] || dropPos
            }

            const calculateOverlapRatio = (rectA, rectB) => {
                if (!rectA || !rectB) return 0
                const xOverlap = Math.max(0, Math.min(rectA.x + rectA.w, rectB.x + rectB.w) - Math.max(rectA.x, rectB.x))
                const yOverlap = Math.max(0, Math.min(rectA.y + rectA.h, rectB.y + rectB.h) - Math.max(rectA.y, rectB.y))
                const intersectionArea = xOverlap * yOverlap
                const areaA = rectA.w * rectA.h
                if (areaA <= 0) return 0
                return intersectionArea / areaA
            }

            const resolveGroupCollisionsAndPushOthers = (draggingTaskId, newBox, allGroups) => {
                const MIN_GROUP_GAP = GRID_SIZE
                let movingGroups = [{ id: draggingTaskId, box: { ...newBox } }]
                let adjustedBoxes = { [draggingTaskId]: { ...newBox } }

                let maxIterations = 10
                let iteration = 0

                while (iteration < maxIterations) {
                    iteration++
                    let hasNewCollision = false

                    for (let i = 0; i < movingGroups.length; i++) {
                        const current = movingGroups[i]
                        const currBox = current.box

                        for (const other of allGroups) {
                            if (other.taskId === current.id) continue
                            if (movingGroups.some(m => m.id === other.taskId)) continue

                            const otherBox = adjustedBoxes[other.taskId] || other.box

                            const isIntersect = !(
                                currBox.x + currBox.w + MIN_GROUP_GAP <= otherBox.x ||
                                currBox.x >= otherBox.x + otherBox.w + MIN_GROUP_GAP ||
                                currBox.y + currBox.h + MIN_GROUP_GAP <= otherBox.y ||
                                currBox.y >= otherBox.y + otherBox.h + MIN_GROUP_GAP
                            )

                            if (isIntersect) {
                                hasNewCollision = true

                                const currCenterX = currBox.x + currBox.w / 2
                                const otherCenterX = otherBox.x + otherBox.w / 2
                                const currCenterY = currBox.y + currBox.h / 2
                                const otherCenterY = otherBox.y + otherBox.h / 2

                                const dx = otherCenterX - currCenterX
                                const dy = otherCenterY - currCenterY

                                const overlapX = Math.min(currBox.x + currBox.w + MIN_GROUP_GAP - otherBox.x, otherBox.x + otherBox.w + MIN_GROUP_GAP - currBox.x)
                                const overlapY = Math.min(currBox.y + currBox.h + MIN_GROUP_GAP - otherBox.y, otherBox.y + otherBox.h + MIN_GROUP_GAP - currBox.y)

                                let nextBox = { ...otherBox }

                                if (overlapX < overlapY) {
                                    if (dx > 0) {
                                        nextBox.x = currBox.x + currBox.w + MIN_GROUP_GAP
                                    } else {
                                        nextBox.x = currBox.x - otherBox.w - MIN_GROUP_GAP
                                    }
                                } else {
                                    if (dy > 0) {
                                        nextBox.y = currBox.y + currBox.h + MIN_GROUP_GAP
                                    } else {
                                        nextBox.y = currBox.y - otherBox.h - MIN_GROUP_GAP
                                    }
                                }

                                nextBox.x = Math.round(nextBox.x / GRID_SIZE) * GRID_SIZE
                                nextBox.y = Math.round(nextBox.y / GRID_SIZE) * GRID_SIZE

                                adjustedBoxes[other.taskId] = nextBox
                                movingGroups.push({ id: other.taskId, box: nextBox })
                            }
                        }
                    }
                    if (!hasNewCollision) break
                }
                return adjustedBoxes
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

                // 1. 如果是节点拖拽释放逻辑
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

                        const tasks = store.currentTaskData?.tasks || []
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

                        tasks.forEach(t => {
                            if (t && typeof t === 'object') {
                                delete t.tasks
                            }
                        })

                        const cleanedTasks = tasks.filter(t => (t.nodes || []).length > 0)

                        if (store.currentTaskData) {
                            store.currentTaskData.tasks = JSON.parse(JSON.stringify(cleanedTasks))
                        }

                        try {
                            await axios.post('/api/blueprint/save', {
                                project_path: store.currentProjectPath,
                                blueprint_data: store.currentTaskData
                            })
                        } catch (saveErr) {
                            console.error('保存蓝图失败:', saveErr)
                        }

                        draggedSourceGroupSnapshot.value = null
                        ghostPlaceholder.value = null
                        delete localDraftPositions[nodeId]

                        await store.loadTasks()
                        store.taskNodesVersion++
                        ElMessage.success('节点排版及组归属更新成功')
                    }
                    hasMoved.value = false
                }

                // 2. 如果是从端口拉线，并且松手在空白处：
                // 2. 如果是从端口拉线，并且松手在空白处：
                if (wasDrawing) {
                    const tasks = store.currentTaskData?.tasks || []
                    if (tasks.length === 0) return

                    let sourceNodeObj = null
                    for (const t of tasks) {
                        const found = (t.nodes || []).find(n => n.node_id === sourceId)
                        if (found) { sourceNodeObj = found; break }
                    }

                    if (sourceNodeObj) {
                        const hasExisting = (
                            (portType === 'fail' && sourceNodeObj.params?.on_failure?.target_node) ||
                            (portType === 'succ' && sourceNodeObj.params?.on_success?.target_node)
                        )

                        // 如果原本有线，拖到空白处 ➔ 彻底断开
                        if (hasExisting) {
                            if (portType === 'fail') {
                                sourceNodeObj.params.on_failure = {}
                            } else {
                                sourceNodeObj.params.on_success = {}
                            }

                            // ⭐ 核心优化：先强制本地响应式更新，再异步存盘，避免被接口耗时回滚
                            store.taskNodesVersion++

                            try {
                                // 直接调用底层保存接口，不走可能引起冲突的封装方法
                                await axios.post('/api/blueprint/save', {
                                    project_path: store.currentProjectPath,
                                    blueprint_data: store.currentTaskData
                                })
                                ElMessage.success('已成功断开连线')
                            } catch (err) {
                                console.error('断线保存失败:', err)
                                ElMessage.error('断线保存失败')
                            }
                            return
                        }
                    }

                    // 如果原本没有线，拖到空白处 ➔ 弹出创建菜单
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
                if (e.target.closest('.workflow-inspector-wrapper') || e.target.closest('.inspector-backdrop')) {
                    return
                }

                e.preventDefault()
                if (!containerRef.value) return

                const rect = containerRef.value.getBoundingClientRect()
                const mouseX = e.clientX - rect.left
                const mouseY = e.clientY - rect.top

                const oldZoom = viewport.value.zoom
                const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9
                const newZoom = Math.min(Math.max(oldZoom * zoomFactor, 0.2), 4)

                if (newZoom === oldZoom) return

                const worldX = (mouseX - viewport.value.x) / oldZoom
                const worldY = (mouseY - viewport.value.y) / oldZoom

                viewport.value.zoom = newZoom
                viewport.value.x = mouseX - worldX * newZoom
                viewport.value.y = mouseY - worldY * newZoom

                if (typeof drawMinimap === 'function') {
                    drawMinimap()
                }
            }

            const onNodeMouseUpCard = async (e, targetNode) => {
                if (drawingConnection.value.active) {
                    const sourceId = drawingConnection.value.sourceNodeId
                    const portType = drawingConnection.value.portType

                    // 锁死当前连线状态
                    drawingConnection.value.active = false

                    const tasks = store.currentTaskData?.tasks || []
                    if (tasks.length === 0) {
                        ElMessage.warning('数据正在同步中，请稍候再试...');
                        e.stopPropagation();
                        return;
                    }

                    if (sourceId && sourceId !== targetNode.node_id) {
                        let sourceNodeObj = null
                        let targetTaskFound = null

                        for (const t of tasks) {
                            const foundSource = (t.nodes || []).find(n => n.node_id === sourceId)
                            if (foundSource) sourceNodeObj = foundSource

                            const foundTarget = (t.nodes || []).find(n => n.node_id === targetNode.node_id)
                            if (foundTarget) targetTaskFound = t
                        }

                        if (sourceNodeObj) {
                            if (!sourceNodeObj.params) sourceNodeObj.params = {}

                            // 防止历史引用粘连
                            if (sourceNodeObj.params.on_success === sourceNodeObj.params.on_failure) {
                                sourceNodeObj.params.on_success = {}
                                sourceNodeObj.params.on_failure = {}
                            }

                            const connectionData = {
                                target_task: targetTaskFound ? targetTaskFound.task_id : '',
                                target_node: targetNode.node_id
                            }

                            // 赋值连线
                            if (portType === 'fail') {
                                sourceNodeObj.params.on_failure = { ...connectionData }
                                ElMessage.success(`失败分支连线已成功指向 ➔ [${targetNode.node_name}]`)
                            } else {
                                sourceNodeObj.params.on_success = { ...connectionData }
                                ElMessage.success(`成功流向连线已成功指向 ➔ [${targetNode.node_name}]`)
                            }

                            // ⭐ 核心优化：直接本地刷新视图版本，线条立刻呈现，不依赖会引起回滚的 reload
                            store.taskNodesVersion++

                            try {
                                // 直接调用底层保存接口，绝对保证第一次就写入成功且不被旧数据覆盖
                                await axios.post('/api/blueprint/save', {
                                    project_path: store.currentProjectPath,
                                    blueprint_data: store.currentTaskData
                                })
                            } catch (saveErr) {
                                console.error('连线保存失败:', saveErr)
                                ElMessage.error('连线保存失败')
                            }
                        }
                    }
                    e.stopPropagation()
                }
            }

            const onNodeDoubleClick = (e, node) => {
                const targets = localSelectedNodeIds.value.length > 1
                    ? renderNodes.value.filter(n => localSelectedNodeIds.value.includes(n.node_id))
                    : []

                let centerX = window.innerWidth / 2 - 190
                let centerY = window.innerHeight / 2 - 250
                if (containerRef.value) {
                    const rect = containerRef.value.getBoundingClientRect()
                    centerX = rect.left + rect.width / 2 - 190
                    centerY = rect.top + rect.height / 2 - 250
                }

                inspector.value = {
                    visible: true,
                    targetType: targets.length > 1 ? 'batch' : 'node',
                    targetData: node,
                    targets: targets,
                    zIndex: 250,
                    position: { x: Math.max(20, centerX), y: Math.max(20, centerY) }
                }
            }

            const openGroupInspector = (e, group) => {
                let centerX = window.innerWidth / 2 - 190
                let centerY = window.innerHeight / 2 - 200
                if (containerRef.value) {
                    const rect = containerRef.value.getBoundingClientRect()
                    centerX = rect.left + rect.width / 2 - 190
                    centerY = rect.top + rect.height / 2 - 200
                }

                inspector.value = {
                    visible: true,
                    targetType: 'group',
                    targetData: group,
                    targets: [],
                    zIndex: 250,
                    position: { x: Math.max(20, centerX), y: Math.max(20, centerY) }
                }
            }

            const startGroupDrag = (e, groupId) => {
                e.stopPropagation()
                const startX = e.clientX
                const startY = e.clientY
                let hasGroupMoved = false

                const tasks = store.currentTaskData?.tasks || []
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
                        if (targetBox) {
                            const origGroup = dynamicGroups.value.find(g => g.taskId === t.task_id)
                            if (origGroup) {
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
                        }
                        if (t && typeof t === 'object') {
                            delete t.tasks
                        }
                        (t.nodes || []).forEach(n => {
                            delete localDraftPositions[n.node_id]
                        })
                    })

                    if (store.currentTaskData) {
                        store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                    }

                    try {
                        await axios.post('/api/blueprint/save', {
                            project_path: store.currentProjectPath,
                            blueprint_data: store.currentTaskData
                        })
                        store.taskNodesVersion++
                        ElMessage.success('任务组移动及互斥排版保存成功')
                    } catch (err) {
                        console.error('保存任务组位移失败', err)
                        ElMessage.error('保存任务组位移失败')
                    }

                    await store.loadTasks()
                }

                window.addEventListener('mousemove', onMouseMove)
                window.addEventListener('mouseup', onMouseUp)
            }

            const startConnection = (e, nodeId, portType) => {
                if (!containerRef.value) return
                const rect = containerRef.value.getBoundingClientRect()
                const clientX = e.clientX - rect.left
                const clientY = e.clientY - rect.top

                drawingConnection.value = {
                    active: true,
                    sourceNodeId: nodeId,
                    portType,
                    currentX: (clientX - viewport.value.x) / viewport.value.zoom,
                    currentY: (clientY - viewport.value.y) / viewport.value.zoom,
                    previewMarkerUrl: 'url(#arrow-preview)'
                }
                e.stopPropagation()
            }

            const onEdgeClick = (edge) => {
                selectedEdgeId.value = edge.id
                ElMessage.info(`已选中连线 (${edge.label || '流向'})`)
            }

            const globalKeydownHandler = async (e) => {
                if (e.key === 'Control') {
                    isCtrlHeldRef.value = true
                }

                if ((e.key === 'Delete' || e.key === 'Backspace') && selectedEdgeId.value) {
                    const edge = computedEdges.value.find(item => item.id === selectedEdgeId.value)
                    if (edge) {
                        const tasks = store.currentTaskData?.tasks || []
                        let modified = false
                        for (const t of tasks) {
                            const foundNode = (t.nodes || []).find(n => n.node_id === edge.sourceNodeId)
                            if (foundNode) {
                                if (edge.typeFlag === 'fail' && foundNode.params?.on_failure) {
                                    foundNode.params.on_failure = {}
                                    modified = true
                                } else if (edge.typeFlag === 'succ' && foundNode.params?.on_success) {
                                    foundNode.params.on_success = {}
                                    modified = true
                                }
                            }
                        }
                        if (modified) {
                            await store.saveCurrentTask(true)
                            store.taskNodesVersion++
                            selectedEdgeId.value = null
                            ElMessage.success('已成功删除连线')
                        }
                    }
                }
            }

            const globalKeyupHandler = (e) => {
                if (e.key === 'Control') {
                    isCtrlHeldRef.value = false
                }
            }

            const createAndConnectNode = async (nodeType) => {
                try {
                    const sourceId = spawnMenu.value.sourceNodeId
                    const portType = spawnMenu.value.portType

                    const targetClientX = spawnMenu.value.clientX || customContextMenu.clientX || window.innerWidth / 2
                    const targetClientY = spawnMenu.value.clientY || customContextMenu.clientY || window.innerHeight / 2

                    spawnMenu.value.visible = false
                    customContextMenu.visible = false

                    const tasks = store.currentTaskData?.tasks || []
                    let targetTask = null, sourceNodeObj = null

                    if (sourceId) {
                        for (const t of tasks) {
                            const found = (t.nodes || []).find(n => n.node_id === sourceId)
                            if (found) { targetTask = t; sourceNodeObj = found; break }
                        }
                    } else {
                        const contextType = customContextMenu.targetType
                        const contextTaskId = customContextMenu.targetId

                        if (contextType === 'canvas_in_group' && contextTaskId) {
                            targetTask = tasks.find(t => t.task_id === contextTaskId)
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
                    }

                    if (!targetTask) return

                    const newNodeId = `node_${Date.now()}`
                    delete targetTask.tasks

                    if (!targetTask.nodes) {
                        targetTask.nodes = []
                    }
                    const targetNodesList = targetTask.nodes

                    if (!containerRef.value) return
                    const rect = containerRef.value.getBoundingClientRect()

                    const spawnX = targetClientX - rect.left
                    const spawnY = targetClientY - rect.top

                    const rawSpawnX = (spawnX - viewport.value.x) / viewport.value.zoom - (NODE_GRID_W * GRID_SIZE) / 2
                    const rawSpawnY = (spawnY - viewport.value.y) / viewport.value.zoom - 40

                    const chineseLabel = getNodeShortLabel(nodeType)
                    const sameTypeCount = targetNodesList.filter(n => n.node_type === nodeType).length + 1
                    const friendlyName = `${chineseLabel}_${sameTypeCount}`

                    const newNode = {
                        node_id: newNodeId,
                        node_name: friendlyName,
                        node_type: nodeType,
                        params: {},
                        delay_before: 200,
                        loop_count: 1,
                        position: {
                            x: Math.round(rawSpawnX / GRID_SIZE) * GRID_SIZE,
                            y: Math.round(rawSpawnY / GRID_SIZE) * GRID_SIZE
                        }
                    }

                    if (sourceNodeObj) {
                        if (!sourceNodeObj.params) sourceNodeObj.params = {}

                        const targetTaskId = targetTask ? targetTask.task_id : ''
                        const connectionData = {
                            target_task: targetTaskId,
                            target_node: newNodeId
                        }

                        if (portType === 'fail') {
                            sourceNodeObj.params.on_failure = connectionData
                        } else {
                            sourceNodeObj.params.on_success = connectionData
                        }
                    }

                    targetNodesList.push(newNode)

                    tasks.forEach(t => {
                        if (t && typeof t === 'object') {
                            delete t.tasks
                        }
                    })

                    if (store.currentTaskData) {
                        store.currentTaskData.tasks = tasks
                    }

                    await axios.post('/api/blueprint/save', {
                        project_path: store.currentProjectPath,
                        blueprint_data: store.currentTaskData
                    })

                    await store.loadTasks()
                    store.taskNodesVersion++

                    localSelectedNodeIds.value = [newNodeId]

                    await nextTick()
                    const createdNodeObj = targetNodesList.find(n => n.node_id === newNodeId)
                    if (createdNodeObj) {
                        inspector.value = {
                            visible: true,
                            targetType: 'node',
                            targetData: createdNodeObj,
                            targets: [],
                            position: {
                                x: Math.min(targetClientX + 15, window.innerWidth - 300),
                                y: Math.min(targetClientY + 15, window.innerHeight - 400)
                            }
                        }
                    }

                    ElMessage.success(`成功创建节点: [${newNode.node_name}]`)
                } catch (err) {
                    console.error('创建节点出错详情:', err)
                    ElMessage.error('创建节点失败，请检查控制台日志')
                }
            }

            const onInspectorUpdate = async () => {
                await store.saveCurrentTask(true)
                store.taskNodesVersion++
            }

            const closeInspector = async () => {
                inspector.value.visible = false
                store.taskNodesVersion++
            }

            onMounted(async () => {
                window.addEventListener('mousemove', onGlobalMouseMove)
                window.addEventListener('mouseup', onGlobalMouseUp)
                window.addEventListener('keydown', globalKeydownHandler)
                window.addEventListener('keyup', globalKeyupHandler)
                await store.loadTasks()
                fitViewToNodes()
                nextTick(drawMinimap)
            })

            onUnmounted(() => {
                window.removeEventListener('mousemove', onGlobalMouseMove)
                window.removeEventListener('mouseup', onGlobalMouseUp)
                window.removeEventListener('keydown', globalKeydownHandler)
                window.removeEventListener('keyup', globalKeyupHandler)
            })

            return {
                store,
                containerRef,
                minimapCanvasRef,
                viewportStyle,
                renderNodes,
                dynamicGroups,
                computedEdges,
                selectionBox,
                selectionBoxStyle,
                spawnMenu,
                inspector,
                availableNodeTypes,
                drawingConnection,
                draggingNodeId,
                dragPreviewBox,
                customContextMenu,
                onContextMenu,
                handleRunFromNode,
                handleDeleteNode,
                handleDeleteGroup,
                handleCanvasNewNode,
                handleCanvasNewGroup,
                onMinimapClick,
                onCanvasMouseDown,
                onNodeMouseUpCard,
                onCanvasWheel,
                onNodeMouseDown,
                onNodeDoubleClick,
                openGroupInspector,
                startGroupDrag,
                startConnection,
                onEdgeClick,
                createAndConnectNode,
                onInspectorUpdate,
                closeInspector,
                activeFocusedGroupId,
                isNodeFocused,
                localSelectedNodeIds,
                fitViewToNodes,
                getNodeIcon,
                getNodeShortLabel,
                getImageThumbnailUrl,
                onImageLoaded,
                isSpecialTallImage
            }
        }
    }
</script>

<style scoped>
    .custom-canvas-container {
        width: 100%;
        height: 100%;
        background: #2b2d3d;
        position: relative;
        overflow: hidden;
        user-select: none;
    }

    .canvas-viewport {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        will-change: transform;
    }

    .canvas-log-panel {
        position: absolute;
        left: 20px;
        bottom: 20px;
        width: 300px;
        background: rgba(38, 40, 61, 0.95);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        z-index: 997;
        overflow: hidden;
        user-select: none;
        transition: all 0.2s;
    }

    .log-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 10px;
        background: rgba(25, 26, 38, 0.95);
        font-size: 12px;
        font-weight: bold;
        color: var(--el-color-primary);
        cursor: pointer;
        border-bottom: 1px solid var(--el-border-color-light);
    }

        .log-panel-header:hover {
            background: var(--el-fill-color-light);
        }

    .log-panel-body {
        padding: 10px;
        font-size: 11px;
        color: var(--el-text-color-regular);
        max-height: 120px;
        overflow-y: auto;
    }

    .minimap-container {
        position: absolute;
        right: 20px;
        bottom: 20px;
        width: 200px;
        background: rgba(38, 40, 61, 0.9);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        z-index: 998;
        overflow: hidden;
        user-select: none;
        transition: height 0.2s;
    }

    .minimap-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 10px;
        background: rgba(25, 26, 38, 0.95);
        font-size: 12px;
        font-weight: bold;
        color: var(--el-color-primary);
        cursor: pointer;
        border-bottom: 1px solid var(--el-border-color-light);
    }

        .minimap-header:hover {
            background: var(--el-fill-color-light);
        }

    .collapse-icon {
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }

    .minimap-body {
        width: 200px;
        height: 150px;
        background: #181926;
        cursor: crosshair;
        display: flex;
        justify-content: center;
        align-items: center;
    }

        .minimap-body canvas {
            display: block;
        }

    .canvas-edges-layer {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 1;
        overflow: visible;
    }

    .canvas-group-box {
        position: absolute;
        box-sizing: border-box;
        border: 2px dashed #4ed19c;
        border-radius: 12px;
        background: rgba(78, 209, 156, 0.02);
        pointer-events: none;
        transition: border-width 0.2s ease, border-color 0.2s ease;
    }

        .canvas-group-box.is-focused {
            border: 3.5px solid #4ed19c;
        }

    .group-title-badge {
        position: absolute;
        top: -26px;
        left: 16px;
        right: 16px;
        background: var(--el-bg-color-page);
        padding: 4px 10px;
        color: #4ed19c;
        border: 1px dashed #4ed19c;
        border-radius: 6px;
        pointer-events: auto;
        cursor: grab;
        display: flex;
        flex-direction: column;
        gap: 2px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }

    .node-drag-preview-box {
        position: absolute;
        border: 2px dashed #4ed19c;
        background: rgba(78, 209, 156, 0.08);
        border-radius: 10px;
        pointer-events: none;
        z-index: 9;
        box-sizing: border-box;
    }

        .node-drag-preview-box.is-danger {
            border-color: #f56c6c;
            background: rgba(245, 108, 108, 0.12);
        }

    .preview-inner-tag {
        position: absolute;
        top: 6px;
        left: 8px;
        font-size: 10px;
        font-weight: bold;
        color: #4ed19c;
        background: rgba(43, 45, 61, 0.85);
        padding: 2px 6px;
        border-radius: 4px;
    }

    .canvas-node-card {
        position: absolute;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 8px 12px 6px 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        cursor: grab;
        z-index: 10;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: border-color 0.2s, box-shadow 0.2s;
    }

        .canvas-node-card:active {
            cursor: grabbing;
        }

        .canvas-node-card:hover {
            border-color: #4ed19c;
            box-shadow: 0 0 10px rgba(78, 209, 156, 0.3);
        }

        .canvas-node-card.is-selected {
            border: 2px solid var(--el-color-primary);
            box-shadow: 0 0 12px rgba(78, 209, 156, 0.5);
        }

    .node-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        flex-shrink: 0;
    }

    .node-header-left {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .node-type-icon {
        width: 15px;
        height: 15px;
        color: rgba(255, 255, 255, 0.9);
        flex-shrink: 0;
    }

    .node-title {
        font-size: 11px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .node-body {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        overflow: hidden;
        margin: 4px 0;
    }

    .node-image-embedded {
        position: relative;
        width: 100%;
        height: 100%;
        background: rgba(18, 19, 28, 0.6);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
    }

        .node-image-embedded::before {
            content: '';
            position: absolute;
            inset: -15px;
            background-image: var(--bg-image-url);
            background-size: cover;
            background-position: center;
            filter: blur(12px) brightness(0.45);
            z-index: 1;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .node-image-embedded:has(.embedded-template-img.is-contain)::before {
            opacity: 1;
        }

    .embedded-template-img {
        position: relative;
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 5px;
        display: block;
        z-index: 2;
        pointer-events: none;
    }

        .embedded-template-img.is-contain {
            object-fit: contain !important;
        }

    .embedded-placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        z-index: 2;
    }

    .node-footer-bar {
        display: flex;
        justify-content: flex-start;
        align-items: center;
        gap: 6px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 4px;
        margin-top: auto;
        flex-shrink: 0;
    }

    .footer-tag {
        font-size: 9px;
        color: var(--el-text-color-secondary);
        background: rgba(255, 255, 255, 0.04);
        padding: 1px 5px;
        border-radius: 4px;
    }

    .node-handle {
        position: absolute;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        cursor: crosshair;
        z-index: 5;
        border: 2px solid #181926;
        transition: transform 0.15s, box-shadow 0.15s;
    }
        .node-handle::after {
            content: '';
            position: absolute;
            top: -10px;
            left: -10px;
            right: -10px;
            bottom: -10px;
            background: transparent; /* 完全透明，用户肉眼不可见 */
            border-radius: 50%;
        }

        .node-handle:hover {
            border-color: #ffffff;
            box-shadow: 0 0 8px rgba(78, 209, 156, 0.6);
        }

    .top-handle {
        top: -6px;
        left: 50%;
        cursor:auto;
        transform: translateX(-50%);
        background: #181926; /* 深色球体内部填充（与卡片背景色一致） */
        border: 2px solid #f2f2f3; /* 白色边框 */
    }

    .succ-handle {
        bottom: -6px;
        left: 50%;
        transform: translateX(-50%);
        background: #4ed19c;
    }

    .fail-handle {
        right: -6px;
        top: 50%;
        transform: translateY(-50%);
        background: #f56c6c;
    }

    .selection-box {
        position: absolute;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid #4ed19c;
        pointer-events: none;
        z-index: 999;
    }

    .spawn-menu {
        position: fixed;
        z-index: 9999;
        width: 210px;
        background: var(--el-bg-color-overlay);
        border: 1px solid var(--el-color-primary);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
        padding: 6px 0;
    }

    .spawn-menu-header {
        padding: 6px 12px;
        font-size: 11px;
        font-weight: bold;
        color: var(--el-color-primary);
        border-bottom: 1px solid var(--el-border-color-light);
        margin-bottom: 4px;
    }

    .spawn-menu-list {
        max-height: 220px;
        overflow-y: auto;
    }

    .spawn-menu-item {
        padding: 8px 14px;
        font-size: 12px;
        color: var(--el-text-color-regular);
        cursor: pointer;
    }

        .spawn-menu-item:hover {
            background: var(--el-fill-color-light);
            color: var(--el-color-primary);
            padding-left: 18px;
        }

    .custom-context-menu {
        position: fixed;
        z-index: 99999;
        width: 180px;
        background: var(--el-bg-color-overlay, #26283d);
        border: 1px solid var(--el-border-color-light, #313352);
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
        padding: 6px 0;
    }

    .menu-item {
        padding: 8px 14px;
        font-size: 12px;
        color: var(--el-text-color-regular);
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
    }

        .menu-item:hover {
            background: var(--el-fill-color-light);
            color: var(--el-text-color-primary);
        }

        .menu-item.danger:hover {
            background: rgba(245, 108, 108, 0.15);
            color: #f56c6c;
        }

    .menu-item-icon {
        width: 14px;
        height: 14px;
        flex-shrink: 0;
    }

    .edge-path {
        fill: none;
        stroke: #4ed19c;
        stroke-width: 2.5;
        pointer-events: stroke;
        cursor: pointer;
        transition: stroke 0.2s;
    }

    .edge-flow-path {
        fill: none;
        stroke: #ffffff;
        stroke-width: 2.5;
        stroke-dasharray: 8 16;
        animation: flowAnimation 0.8s linear infinite;
        opacity: 0.85;
    }

        .edge-flow-path.is-danger {
            stroke: #ffadad;
        }

    @keyframes flowAnimation {
        from {
            stroke-dashoffset: 24;
        }

        to {
            stroke-dashoffset: 0;
        }
    }

    .preview-path {
        stroke-dasharray: 5 5;
        animation: dash 1s linear infinite;
    }

    @keyframes dash {
        to {
            stroke-dashoffset: -10;
        }
    }

    .edge-path:hover, .edge-path.is-selected {
        stroke: #ffffff;
        stroke-width: 4;
        filter: drop-shadow(0 0 6px #4ed19c);
    }

    .edge-path.is-danger {
        stroke: #f56c6c;
    }
</style>