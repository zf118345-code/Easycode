<!-- frontend/src/components/WorkflowCanvas.vue -->
<template>
    <div
ref="containerRef"
         class="custom-canvas-container"
         @mousedown="onCanvasMouseDown"
         @wheel="onCanvasWheel"
         @contextmenu="onContextMenu">
        <!-- 视口变换层 -->
        <div class="canvas-viewport" :style="viewportStyle">
<!-- SVG 连线层（已提取为 CanvasEdgeLayer 组件） -->
            <CanvasEdgeLayer
                :edges="computedEdges"
                :drawing-connection="drawingConnection"
                @edge-click="onEdgeClick" />

            <!-- 任务组包围框 -->
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
                <div class="group-title-badge" :data-group-id="group.groupId" @mousedown.stop="startGroupDrag($event, group.groupId)" @dblclick.stop="openGroupInspector($event, group)">
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

            <!-- 节点卡片层（已提取为 CanvasNodeCard 组件） -->
            <CanvasNodeCard
                v-for="node in renderNodes"
                :key="node.node_id"
                :node="node"
                :selected="node.selected"
                :is-active-debug="store.currentActiveNodeId === node.node_id"
                :has-breakpoint="uiStore.hasBreakpoint(node.node_id)"
                :current-project-path="store.currentProjectPath"
                :blueprint-version="store.blueprint?.version || 0"
                @node-mousedown="onNodeMouseDown"
                @node-mouseup="onNodeMouseUpCard"
                @node-dblclick="onNodeDoubleClick"
                @node-contextmenu="openNodeContextMenu"
                @toggle-breakpoint="handleToggleBreakpoint"
                @start-connection="startConnection"
                @image-loaded="onImageLoadedFromCard" />
</div>

        <!-- 全景缩略图导航面板 -->
        <div class="minimap-container" v-show="store.minimapExpanded">
            <canvas ref="minimapCanvasRef" width="150" height="110" @click="onMinimapClick" />
        </div>

        <!-- 框选 UI -->
        <div v-if="selectionBox.visible" class="selection-box" :style="selectionBoxStyle" />

        <!-- 右键菜单 + 节点选择菜单（已提取为 CanvasContextMenu 组件） -->
        <CanvasContextMenu
            :spawn-menu="spawnMenu"
            :context-menu="customContextMenu"
            :menu-z-index="menuZIndex"
            :available-node-types="availableNodeTypes"
            :has-breakpoint="customContextMenu.targetId ? uiStore.hasBreakpoint(customContextMenu.targetId) : false"
            :is-paused="store.isPaused"
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
    import { blueprintApi } from '@/api/blueprintApi'
    import { computeEdgePath, getSimpleOrthoPath, getRoundedPathString as canvasRoundedPath } from '@/utils/canvasRouter'
    import {
        normalizePortType, normalizeNodeList,
        getPortPosition, getArrowDirection
    } from '@/utils/nodeModel'
    import { getNextZIndex } from '@/utils/zIndexManager'

    // ===== 画布增强 Composables（快捷键/撤销重做/连线标签） =====
    import { useCanvasKeyboard } from '@/composables/useCanvasKeyboard'
    import { createPiniaUndoRedo } from '@/composables/useUndoRedo'
<<<<<<< HEAD
    import { useEdgeLabels } from '@/composables/useEdgeLabels'
    import CanvasNodeCard from '@/components/canvas/CanvasNodeCard.vue'
    import CanvasEdgeLayer from '@/components/canvas/CanvasEdgeLayer.vue'
    import CanvasContextMenu from '@/components/canvas/CanvasContextMenu.vue'
=======
>>>>>>> code-architecture-review-lGUoYn

    import {
        MousePointerClick, Clock, Target, FileSearch, GitBranch, SearchCheck,
        Binary, ListOrdered, FileCode, Image, CirclePlay, Trash2, Compass
    } from 'lucide-vue-next'
    import { GRID_SIZE, NODE_GRID_W, NODE_TYPE_CONFIG } from '@/utils/canvasShared'

    const store = useMainStore()
    const uiStore = useUiStore()

    // ===== 注册快捷键：Ctrl+S 保存 / Delete 删除节点 / Ctrl+A 全选 =====
    useCanvasKeyboard({
        onSave: async () => {
            await store.saveBlueprintImmediately()
            ElMessage.success('蓝图已保存')
        },
        onDelete: async () => {
            // 复用批量删除能力（兼容多选删除）
            await uiStore.batchDeleteNodes()
        },
        onSelectAll: () => {
            uiStore.selectAllNodes()
        }
    })

    // ===== Undo/Redo（Ctrl+Z / Ctrl+Shift+Z） =====
    const undoRedo = createPiniaUndoRedo()
    // 额外注册撤销/重做快捷键
    function _onUndoHotkey(e) {
        const ctrl = e.ctrlKey || e.metaKey
        if (!ctrl) return
        if (e.key === 'z' && !e.shiftKey) {
            e.preventDefault(); e.stopPropagation(); undoRedo.undo()
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
            e.preventDefault(); e.stopPropagation(); undoRedo.redo()
        }
    }
    onMounted(() => { window.addEventListener('keydown', _onUndoHotkey, true) })
    onUnmounted(() => { window.removeEventListener('keydown', _onUndoHotkey, true) })

    const containerRef = ref(null)
    const minimapCanvasRef = ref(null)
    const menuZIndex = ref(3000)
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

    const closeSpawnMenu = () => { spawnMenu.value.visible = false }

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

    const selectedEdgeId = ref(null)
    const localSelectedNodeIds = ref([])


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

    // 图标映射统一从 canvasShared.NODE_TYPE_CONFIG 获取
    const _iconComponentCache = {
        MousePointerClick, Clock, Target, FileSearch, GitBranch, SearchCheck,
        Binary, ListOrdered, FileCode, Image, CirclePlay, Trash2, Compass
    }
    const getNodeIcon = (nodeType) => {
        const config = NODE_TYPE_CONFIG[nodeType]
        return (config && _iconComponentCache[config.icon]) || FileCode
    }

    const getNodeShortLabel = (nodeType) => {
        const label = availableNodeTypes[nodeType] || nodeType
        return label.replace(/^[^\u4e00-\u9fa5]+/, '').trim()
    }

    // ⚡ 格式化 Branch 条件的纯简描述
    const formatCondDesc = (item) => {
        if (!item) return '未配置条件'
        const condType = item.condition_type || item.type || 'variable_check'
        const params = item.params || item

        if (condType === 'image_exists') {
            const opText = params.exist_mode === 'not_exists' ? '不存在' : '存在'
            return `🖼️ ${opText}: ${params.image_source || '未选图片'}`
        }
        if (condType === 'text_contains') {
            return `🔤 文本: ${params.target_text || '未设文本'}`
        }
        if (condType === 'variable_check') {
            return `🔢 变量: ${params.variable_name || params.var_name || '未选'} (${params.operator || 'eq'}) ${params.compare_value ?? params.target_value ?? ''}`
        }
        if (condType === 'window_state') {
            return `🪟 窗口: ${params.window_title || '默认'} (${params.state_check || '存在'})`
        }
        if (condType === 'file_exists') {
            return `📂 文件: ${params.file_path || '未设路径'}`
        }
        return `判定: ${condType}`
    }

    const getImageThumbnailUrl = (imageSource) => {
        if (!imageSource) return ''
        let cleanName = imageSource.replace(/\\/g, '/')
        if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) cleanName += '.png'
        const version = store.blueprint?.version || 0
        return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&v=${version}`
    }

    const hasFailurePort = (nodeType) => ['image_recognition', 'ocr_recognition', 'branch', 'logic_check'].includes(nodeType)

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
            const tasks = store.blueprint?.tasks || []
            for (let i = 0; i < tasks.length; i++) {
                if ((tasks[i].nodes || []).some(n => n.node_id === draggingNodeId.value)) {
                    return `group_${tasks[i].task_id || i}`
                }
            }
        }
        if (localSelectedNodeIds.value.length > 0) {
            const firstSelId = localSelectedNodeIds.value[0]
            const tasks = store.blueprint?.tasks || []
            for (let i = 0; i < tasks.length; i++) {
                if ((tasks[i].nodes || []).some(n => n.node_id === firstSelId)) {
                    return `group_${tasks[i].task_id || i}`
                }
            }
        }
        return null
    })

    const renderNodes = computed(() => {
        const tasks = store.blueprint?.tasks || []
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
                } else if (node.node_type === 'branch') {
                    const candCount = node.params?.candidates?.length || 0
                    contentHeightPx += Math.max(candCount * 28, 30)
                }

                const exactGrids = contentHeightPx / GRID_SIZE
                const gridCount = Math.ceil(exactGrids)
                const finalHeight = gridCount * GRID_SIZE

                const w = NODE_GRID_W * GRID_SIZE
                allNodesList.push({
                    ...node,
                    position: { x: gridX, y: gridY },
                    w,
                    h: finalHeight,
                    size: { w, h: finalHeight },
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

    const onImageLoadedFromCard = ({ nodeId, width, height, cardInnerWidth }) => {
        const ratio = height / width
        if (ratio > 1) {
            tallImageFlags[nodeId] = true
            dynamicImageHeights[nodeId] = cardInnerWidth
        } else {
            tallImageFlags[nodeId] = false
            dynamicImageHeights[nodeId] = Math.round(cardInnerWidth * ratio)
        }
    }

    const isSpecialTallImage = (nodeId) => !!tallImageFlags[nodeId]

    const fitViewToNodes = () => {
        nextTick(() => {
            const tasks = store.blueprint?.tasks || []
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

            drawMinimap()
        })
    }

    const dynamicGroups = computed(() => {
        const tasks = store.blueprint?.tasks || []
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

    const handleRunFromNode = async () => {
        const nodeId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!nodeId) return

        let targetTaskId = null
        const tasks = store.blueprint?.tasks || []
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
            if (result && result.status === 'started') {
                ElMessage.success('任务已成功从当前节点启动！')
            } else {
                ElMessage.error('执行失败')
            }
        } catch (err) {
            ElMessage.error('执行请求失败: ' + err.message)
        }
    }

    // ===== 调试：右键节点打开上下文菜单 =====
    function openNodeContextMenu(e, node) {
        customContextMenu.visible = true
        customContextMenu.targetType = 'node'
        customContextMenu.targetId = node.node_id
        customContextMenu.targetName = node.node_name
        customContextMenu.clientX = e.clientX
        customContextMenu.clientY = e.clientY
        // 相对容器坐标
        const rect = containerRef.value?.getBoundingClientRect?.()
        customContextMenu.x = rect ? (e.clientX - rect.left) + 8 : e.offsetX
        customContextMenu.y = rect ? (e.clientY - rect.top) + 8 : e.offsetY
        menuZIndex.value = getNextZIndex()
        closeSpawnMenu()
    }

    // ===== 调试：切换节点断点 =====
    function handleToggleBreakpoint(nodeId) {
        if (!nodeId) return
        const added = uiStore.toggleBreakpoint(nodeId)
        customContextMenu.visible = false
        ElMessage.info(
            added ? `🔴 已设置断点：${nodeId}` : `⚪ 已移除断点：${nodeId}`
        )
    }

    // ===== 调试：设置断点并运行到此处 =====
    async function handleAddBreakpointAndRun(nodeId) {
        if (!nodeId) return
        uiStore.enableBreakpoint(nodeId)
        customContextMenu.visible = false

        // 找到归属 task 并执行
        const tasks = store.blueprint?.tasks || []
        let targetTaskId = null
        for (const task of tasks) {
            if ((task.nodes || []).some(n => n.node_id === nodeId)) {
                targetTaskId = task.task_id
                break
            }
        }
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


    const handleDeleteNode = async () => {
        const nodeId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!nodeId) return

        try {
            const tasks = store.blueprint?.tasks || []
            for (const task of tasks) {
                if (task.nodes) {
                    task.nodes = task.nodes.filter(n => n.node_id !== nodeId)
                }
            }
            store.blueprint.tasks = tasks.filter(t => (t.nodes || []).length > 0)
            await store.saveBlueprintImmediately()
            ElMessage.success('节点已成功删除')
        } catch (err) {
            ElMessage.error('删除节点失败: ' + err.message)
        }
    }

    const handleDeleteGroup = async () => {
        const taskId = customContextMenu.targetId
        customContextMenu.visible = false
        if (!taskId) return

        try {
            await blueprintApi.deleteTask(taskId, store.currentProjectPath)
            await store.loadProjectData()
            ElMessage.success('任务组已成功删除')
        } catch (err) {
            ElMessage.error('删除任务组失败: ' + err.message)
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
                await blueprintApi.createTask(store.currentProjectPath, { task_name: groupName.trim(), nodes: [] })
                await store.loadProjectData()
                ElMessage.success(`任务组 [${groupName}] 创建成功`)
            }
        } catch (err) {
            if (err !== 'cancel') {
                ElMessage.error(err.message || '创建任务组失败')
            }
        }
    }

    // ⚡ 核心连线计算：支持常规成功、行级分支（branch_i）与 Else/失败兜底出口
    // 使用 canvasRouter 统一 BFS 寻路（移除 pathfinding 依赖 + gridRouter + pathSmooth）
    const computedEdges = computed(() => {
        let edges = []
        const allNodes = renderNodes.value
        const activeDraggingId = draggingNodeId.value
        const isActuallyMoving = hasMoved.value

        // 构建供 canvasRouter 使用的归一化节点列表（已有 size 字段，但显式过一遍更安全）
        const routerNodes = normalizeNodeList(allNodes)

        const pushEdge = ({ sourceNode, targetNode, legacyPort, edgeIdBase, isFailFlag, extra = {} }) => {
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
                // 把 path string 转 points 给箭头方向用
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
                    console.warn('[WorkflowCanvas] computeEdgePath 失败，使用兜底路径:', e)
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

            const edgeId = edgeIdBase
            edges.push({
                id: edgeId,
                sourceNodeId: sourceNode.node_id,
                targetNodeId: targetNode.node_id,
                typeFlag: legacyPort === 'succ' ? 'succ' : (legacyPort === 'fail' ? 'fail' : 'branch'),
                ...extra,
                path,
                isFail,
                markerUrl: `url(#arrow-${markerPrefix}-${arrowDir})`,
                selected: selectedEdgeId.value === edgeId,
                labelX: startPt && endPt ? (startPt.x + endPt.x) / 2 : 0,
                labelY: startPt && endPt ? (startPt.y + endPt.y) / 2 - 10 : 0,
                rawPixelPoints
            })
        }

        allNodes.forEach(node => {
            // 1. 普通节点常规成功出口
            if (node.node_type !== 'branch' && node.params?.on_success?.target_node) {
                const target = allNodes.find(n => n.node_id === node.params.on_success.target_node)
                if (target) {
                    pushEdge({
                        sourceNode: node,
                        targetNode: target,
                        legacyPort: 'succ',
                        edgeIdBase: `e_${node.node_id}_succ_${target.node_id}`,
                        isFailFlag: false
                    })
                }
            }

            // 2. Branch 节点：多路行级分支出口 (branch_0, branch_1...)
            if (node.node_type === 'branch' && Array.isArray(node.params?.candidates)) {
                node.params.candidates.forEach((cand, cIdx) => {
                    if (cand?.on_success?.target_node) {
                        const target = allNodes.find(n => n.node_id === cand.on_success.target_node)
                        if (target) {
                            const portType = `branch_${cIdx}`
                            pushEdge({
                                sourceNode: node,
                                targetNode: target,
                                legacyPort: portType,
                                edgeIdBase: `e_${node.node_id}_branch_${cIdx}_${target.node_id}`,
                                isFailFlag: false,
                                extra: { candIndex: cIdx }
                            })
                        }
                    }
                })
            }

            // 3. 失败 / Else 兜底出口
            if (node.params?.on_failure?.target_node) {
                const target = allNodes.find(n => n.node_id === node.params.on_failure.target_node)
                if (target) {
                    pushEdge({
                        sourceNode: node,
                        targetNode: target,
                        legacyPort: 'fail',
                        edgeIdBase: `e_${node.node_id}_fail_${target.node_id}`,
                        isFailFlag: true
                    })
                }
            }
        })

        // 4. 用户实时拉线预览（使用统一端口位置计算 + 圆角路径）
        if (drawingConnection.value.active) {
            const sourceNode = allNodes.find(n => n.node_id === drawingConnection.value.sourceNodeId)
            if (sourceNode) {
                const portType = drawingConnection.value.portType
                const startPt = getPortPosition(sourceNode, portType)
                const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }

                let safeStartY = startPt.y
                if (normalizePortType(portType) === 'success') {
                    safeStartY = Math.max(startPt.y + 20, mousePt.y)
                }

                const rawPoints = [
                    startPt,
                    { x: startPt.x, y: safeStartY },
                    { x: mousePt.x, y: safeStartY },
                    mousePt
                ]

                const pathStr = canvasRoundedPath(rawPoints, 10)
                const arrowDir = getArrowDirection(rawPoints)
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
            store.clearSelection()
            store.setSelectedGroup(null)
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

        const tasks = store.blueprint?.tasks || []
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

        store.selectNodes([...localSelectedNodeIds.value])
        store.setSelectedGroup(null)

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

                const tasks = store.blueprint?.tasks || []
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

                store.blueprint.tasks = tasks.filter(t => (t.nodes || []).length > 0)
                await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)

                draggedSourceGroupSnapshot.value = null
                ghostPlaceholder.value = null
                delete localDraftPositions[nodeId]

                ElMessage.success('节点排版及组归属更新成功')
            }
            hasMoved.value = false
        }

        // ⚡ 拖拽空放断开原有连线
        if (wasDrawing) {
            const tasks = store.blueprint?.tasks || []
            if (tasks.length === 0) return

            let sourceNodeObj = null
            for (const t of tasks) {
                const found = (t.nodes || []).find(n => n.node_id === sourceId)
                if (found) { sourceNodeObj = found; break }
            }

            if (sourceNodeObj) {
                let hasExisting = false

                if (portType.startsWith('branch_')) {
                    const cIdx = parseInt(portType.split('_')[1]) || 0
                    if (sourceNodeObj.params?.candidates?.[cIdx]?.on_success?.target_node) {
                        hasExisting = true
                        sourceNodeObj.params.candidates[cIdx].on_success = {}
                    }
                } else if (portType === 'fail' && sourceNodeObj.params?.on_failure?.target_node) {
                    hasExisting = true
                    sourceNodeObj.params.on_failure = {}
                } else if (portType === 'succ' && sourceNodeObj.params?.on_success?.target_node) {
                    hasExisting = true
                    sourceNodeObj.params.on_success = {}
                }

                if (hasExisting) {
                    try {
                        await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
                        ElMessage.success('已成功断开连线')
                    } catch (err) {
                        console.error('断线保存失败:', err)
                        ElMessage.error('断线保存失败')
                    }
                    return
                }
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

    // ⚡ 释放鼠标确认建立 Branch 行级或通用连线
    const onNodeMouseUpCard = async (e, targetNode) => {
        if (drawingConnection.value.active) {
            const sourceId = drawingConnection.value.sourceNodeId
            const portType = drawingConnection.value.portType

            drawingConnection.value.active = false

            const tasks = store.blueprint?.tasks || []
            if (tasks.length === 0) {
                ElMessage.warning('数据同步中，请稍候再试...')
                e.stopPropagation()
                return
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

                    const connectionData = {
                        target_task: targetTaskFound ? targetTaskFound.task_id : '',
                        target_node: targetNode.node_id
                    }

                    if (portType.startsWith('branch_')) {
                        const cIdx = parseInt(portType.split('_')[1]) || 0
                        if (!sourceNodeObj.params.candidates) sourceNodeObj.params.candidates = []
                        if (sourceNodeObj.params.candidates[cIdx]) {
                            sourceNodeObj.params.candidates[cIdx].on_success = { ...connectionData }
                            ElMessage.success(`分支 ${cIdx + 1} 成功指向 ➔ [${targetNode.node_name}]`)
                        }
                    } else if (portType === 'fail') {
                        sourceNodeObj.params.on_failure = { ...connectionData }
                        ElMessage.success(`Else/失败分支指向 ➔ [${targetNode.node_name}]`)
                    } else {
                        sourceNodeObj.params.on_success = { ...connectionData }
                        ElMessage.success(`成功流向指向 ➔ [${targetNode.node_name}]`)
                    }

                    try {
                        await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
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
        store.selectNode(node.node_id)
        store.setSelectedGroup(null)
        localSelectedNodeIds.value = [node.node_id]
        e.stopPropagation()
    }

    const openGroupInspector = (e, group) => {
        store.setSelectedGroup(group.groupId)
        store.clearSelection()
        localSelectedNodeIds.value = []
        e.stopPropagation()
    }

    const startGroupDrag = (e, groupId) => {
        e.stopPropagation()
        const startX = e.clientX
        const startY = e.clientY
        let hasGroupMoved = false

        const tasks = store.blueprint?.tasks || []
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

            if (!hasGroupMoved) return

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

            store.blueprint.tasks = JSON.parse(JSON.stringify(tasks.filter(t => (t.nodes || []).length > 0)))

            try {
                await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
                ElMessage.success('任务组移动及互斥排版保存成功')
            } catch (err) {
                console.error('保存任务组位移失败', err)
                ElMessage.error('保存任务组位移失败')
            }
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
        ElMessage.info(`已选中连线`)
    }

    // ⚡ 快捷键删除选中连线（兼容 Branch 多分支出口）
    const globalKeydownHandler = async (e) => {
        if (e.key === 'Control') {
            isCtrlHeldRef.value = true
        }

        if ((e.key === 'Delete' || e.key === 'Backspace') && selectedEdgeId.value) {
            const edge = computedEdges.value.find(item => item.id === selectedEdgeId.value)
            if (edge) {
                const tasks = store.blueprint?.tasks || []
                let modified = false
                for (const t of tasks) {
                    const foundNode = (t.nodes || []).find(n => n.node_id === edge.sourceNodeId)
                    if (foundNode) {
                        if (edge.typeFlag === 'branch' && foundNode.params?.candidates?.[edge.candIndex]) {
                            foundNode.params.candidates[edge.candIndex].on_success = {}
                            modified = true
                        } else if (edge.typeFlag === 'fail' && foundNode.params?.on_failure) {
                            foundNode.params.on_failure = {}
                            modified = true
                        } else if (edge.typeFlag === 'succ' && foundNode.params?.on_success) {
                            foundNode.params.on_success = {}
                            modified = true
                        }
                    }
                }
                if (modified) {
                    await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
                    selectedEdgeId.value = null
                    ElMessage.success('已成功断开连线')
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

            const tasks = store.blueprint?.tasks || []
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

                if (portType.startsWith('branch_')) {
                    const cIdx = parseInt(portType.split('_')[1]) || 0
                    if (sourceNodeObj.params.candidates?.[cIdx]) {
                        sourceNodeObj.params.candidates[cIdx].on_success = connectionData
                    }
                } else if (portType === 'fail') {
                    sourceNodeObj.params.on_failure = connectionData
                } else {
                    sourceNodeObj.params.on_success = connectionData
                }
            }

            targetNodesList.push(newNode)
            store.blueprint.tasks = tasks

            await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)

            localSelectedNodeIds.value = [newNodeId]
            store.selectNode(newNodeId)

            ElMessage.success(`成功创建节点: [${newNode.node_name}]`)
        } catch (err) {
            console.error('创建节点出错详情:', err)
            ElMessage.error('创建节点失败，请检查控制台日志')
        }
    }

    onMounted(async () => {
        window.addEventListener('mousemove', onGlobalMouseMove)
        window.addEventListener('mouseup', onGlobalMouseUp)
        window.addEventListener('keydown', globalKeydownHandler)
        window.addEventListener('keyup', globalKeyupHandler)
        if (store.currentProjectPath) {
            await store.loadProjectData()
        }
        fitViewToNodes()
        nextTick(drawMinimap)
    })

    onUnmounted(() => {
        window.removeEventListener('mousemove', onGlobalMouseMove)
        window.removeEventListener('mouseup', onGlobalMouseUp)
        window.removeEventListener('keydown', globalKeydownHandler)
        window.removeEventListener('keyup', globalKeyupHandler)
    })
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

    .minimap-container {
        position: absolute;
        right: 16px;
        bottom: 16px;
        width: 150px;
        height: 110px;
        background: rgba(20, 22, 34, 0.65);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        z-index: 998;
        overflow: hidden;
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
        overflow: visible !important; /* ⚡ 允许锚点外溢 */
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

        /* ===== 调试：当前执行命中节点高亮 ===== */
        .canvas-node-card.is-active-debug {
            border: 2px solid #ffb020 !important;
            box-shadow: 0 0 0 3px rgba(255, 176, 32, 0.35), 0 6px 18px rgba(255, 176, 32, 0.25) !important;
            animation: debug-pulse 1.2s ease-in-out infinite;
        }

        @keyframes debug-pulse {
            0%, 100% { filter: brightness(1); }
            50%      { filter: brightness(1.12); }
        }

    /* ===== 节点头部断点 gutter + 当前执行标签 ===== */
    .node-breakpoint-gutter {
        width: 18px; height: 18px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        margin-right: 4px; cursor: pointer; user-select: none;
        border-radius: 50%;
        transition: background-color 0.15s;
    }
    .node-breakpoint-gutter:hover { background: rgba(255,255,255,0.08); }
    .node-breakpoint-gutter .bp-dot {
        width: 12px; height: 12px; border-radius: 50%;
        background: #e5484d;
        box-shadow: 0 0 6px rgba(229, 72, 77, 0.8), inset 0 -2px 0 rgba(0,0,0,0.2);
    }
    .node-breakpoint-gutter.active { background: rgba(229, 72, 77, 0.12); }

    .node-debug-tag {
        display: inline-flex; align-items: center; justify-content: center;
        width: 18px; height: 18px; border-radius: 50%;
        background: #ffb020; color: #1a1a1a;
        box-shadow: 0 0 8px rgba(255, 176, 32, 0.8);
        flex-shrink: 0;
        animation: debug-pulse 1s ease-in-out infinite;
    }
    .debug-pulse-icon { width: 12px; height: 12px; }

        /* ===== 调试：当前执行命中节点高亮 ===== */
        .canvas-node-card.is-active-debug {
            border: 2px solid #ffb020 !important;
            box-shadow: 0 0 0 3px rgba(255, 176, 32, 0.35), 0 6px 18px rgba(255, 176, 32, 0.25) !important;
            animation: debug-pulse 1.2s ease-in-out infinite;
        }

        @keyframes debug-pulse {
            0%, 100% { filter: brightness(1); }
            50%      { filter: brightness(1.12); }
        }

    /* ===== 节点头部断点 gutter + 当前执行标签 ===== */
    .node-breakpoint-gutter {
        width: 18px; height: 18px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        margin-right: 4px; cursor: pointer; user-select: none;
        border-radius: 50%;
        transition: background-color 0.15s;
    }
    .node-breakpoint-gutter:hover { background: rgba(255,255,255,0.08); }
    .node-breakpoint-gutter .bp-dot {
        width: 12px; height: 12px; border-radius: 50%;
        background: #e5484d;
        box-shadow: 0 0 6px rgba(229, 72, 77, 0.8), inset 0 -2px 0 rgba(0,0,0,0.2);
    }
    .node-breakpoint-gutter.active { background: rgba(229, 72, 77, 0.12); }

    .node-debug-tag {
        display: inline-flex; align-items: center; justify-content: center;
        width: 18px; height: 18px; border-radius: 50%;
        background: #ffb020; color: #1a1a1a;
        box-shadow: 0 0 8px rgba(255, 176, 32, 0.8);
        flex-shrink: 0;
        animation: debug-pulse 1s ease-in-out infinite;
    }
    .debug-pulse-icon { width: 12px; height: 12px; }

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
        overflow: visible !important; /* ⚡ 核心修正：取消隐藏，拒绝裁切行级绿点 */
        margin: 4px 0;
    }

    /* ⚡ Branch 行级条件列表与锚点样式 */
    .branch-candidates-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
        width: 100%;
        padding: 2px 0;
        overflow: visible !important;
    }

    .branch-candidate-item {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--el-border-color-light);
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 10px;
        height: 24px;
        overflow: visible !important; /* ⚡ 允许内部锚点半嵌在卡片右侧 */
        z-index: 2;
    }

    .branch-cand-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--el-text-color-regular);
        max-width: 180px;
    }

    .branch-handle {
        right: -18px; /* ⚡ 核心修正：考虑到卡片内边距，使锚点精准嵌入右侧边框 */
        top: 50%;
        transform: translateY(-50%);
        background: #4ed19c;
        z-index: 10;
    }

    .empty-cand-placeholder {
        font-size: 10px;
        color: var(--el-text-color-placeholder);
        text-align: center;
        padding: 8px 0;
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
            background: transparent;
            border-radius: 50%;
        }

        .node-handle:hover {
            border-color: #ffffff;
            box-shadow: 0 0 8px rgba(78, 209, 156, 0.6);
        }

    .top-handle {
        top: -6px;
        left: 50%;
        cursor: auto;
        transform: translateX(-50%);
        background: #181926;
        border: 2px solid #f2f2f3;
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

    /* ⚡ 针对 Branch 节点，将 Else 兜底红点下移至右下方，避免与行级绿点覆盖 */
    .canvas-node-card:has(.branch-candidates-list) .fail-handle {
        top: auto !important;
        bottom: 12px !important;
        transform: none !important;
    }

    .selection-box {
        position: absolute;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid #4ed19c;
        pointer-events: none;
        z-index: 999;
    }

    .spawn-menu, .custom-context-menu {
        position: fixed;
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

    .menu-divider {
        height: 1px;
        margin: 4px 8px;
        background: var(--el-border-color-lighter);
        opacity: 0.8;
    }
    .bp-dot-inline {
        display: inline-block; width: 10px; height: 10px; border-radius: 50%;
        background: #e5484d; box-shadow: 0 0 4px rgba(229, 72, 77, 0.7);
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

    .edge-path:hover, .edge-path.is-selected {
        stroke: #ffffff;
        stroke-width: 4;
        filter: drop-shadow(0 0 6px #4ed19c);
    }

    .edge-path.is-danger {
        stroke: #f56c6c;
    }
</style>