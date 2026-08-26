<!-- frontend/src/components/CanvasPage.vue
  唯一画布页面（业务流程与页面拓扑完全共用一个页面/一套逻辑）：
  - 画布渲染/交互（节点卡片、连线、端口、拖拽、碰撞、断点、缩放、快捷键）全部复用 CanvasView
  - 工作区只从左侧导航进入；canvasMode 决定读取主流程、函数图或 page_map
    与显示哪些节点类型（nodeRegistry 白名单）；持久化图统一为 {nodes, edges}
-->
<template>
    <div class="canvas-page-shell">
        <div v-if="isFunctionWorkspaceEmpty" class="function-workspace-empty">
            <div class="function-empty-icon"><Braces :size="22" /></div>
            <strong>选择一个函数开始编辑</strong>
            <p>函数拥有独立画布、形参、局部变量、输出和结果出口。</p>
            <button type="button" @click="requestCreateFunction"><Plus :size="14" />新建函数</button>
        </div>
        <CanvasView
            v-else
            ref="canvasViewRef"
            :mode="canvasMode"
            :tasks="renderCanvasData.tasks"
            :edges="renderCanvasData.edges"
            :available-node-types="availableNodeTypes"
            :has-breakpoints="true"
            :on-save="handleSave"
            :on-delete="handleDelete"
            :on-select-all="handleSelectAll"
            :on-undo="activeUndoRedo.undo"
            :on-redo="activeUndoRedo.redo"
            @update-tasks="handleUpdateTasks"
            @update-geometry="handleUpdateGeometry"
            @add-edge="handleAddEdge"
            @remove-edge="handleRemoveEdge"
            @update-edge-routing="handleUpdateEdgeRouting"
            @create-node="handleCreateNode"
            @paste-subgraph="handlePasteSubgraph"
            @delete-node="handleDeleteNode" />
    </div>
    <el-dialog v-model="layoutDialogVisible" title="自动布局预览" width="460px" append-to-body @closed="cancelLayoutPreview">
        <el-form label-width="90px">
            <el-form-item label="布局范围">
                <el-radio-group v-model="layoutScope">
                    <el-radio-button value="whole">整个画布</el-radio-button>
                    <el-radio-button value="selection">选中节点</el-radio-button>
                </el-radio-group>
            </el-form-item>
            <el-alert type="info" :closable="false" title="预览不会写入项目；确认后保存，取消则恢复原布局。" />
        </el-form>
        <template #footer>
            <el-button @click="cancelLayoutPreview">取消</el-button>
            <el-button @click="previewAutoLayout">生成预览</el-button>
            <el-button type="primary" :disabled="!layoutPreviewActive" @click="confirmAutoLayout">确认布局</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
    import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
    import { useIdeStore, useUiStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { createCanvasUndoRedo } from '@/composables/useUndoRedo'
    import { getNodeTypesForMode } from '@/config/nodeRegistry'
    import {
        applyEdge,
        reconcileGraphIntegrity,
        removeEdge,
        removeNode,
        findEdgeAtPort
    } from '@/utils/workflowEdgeModel'
    import { buildNodeDefaultParams, NODE_DEFAULTS } from '@/utils/nodeDefaults'
    import { buildControlParamsFromInfo, buildControlNodeName } from '@/utils/captureNode'
    import {
        NODE_WIDTH, NODE_MIN_HEIGHT, computeCanvasNodeHeight,
        findFreePosition
    } from '@/utils/canvasShared'
    import CanvasView from '@/components/canvas/CanvasView.vue'
    import { autoLayoutGraphGeometry } from '@/utils/autoLayout'
    import { getPrimarySourcePort, getSourcePortDescriptors } from '@/utils/portModel'
    import { getGraph, getGraphLabel, MAIN_GRAPH_ID } from '@/utils/flowModel'
    import { notifyActionError } from '@/utils/userActionErrors'
    import {
        normalizeEdgeRouting,
        reconcileEdgeWaypoints,
        translateInternalEdgeWaypoints
    } from '@/utils/edgePresentation'
    import { Braces, Plus } from 'lucide-vue-next'

    const store = useIdeStore()
    const uiStore = useUiStore()
    const layoutDialogVisible = ref(false)
    const layoutScope = ref('whole')
    const layoutPreviewActive = ref(false)
    const layoutOriginal = ref(null)
    const canvasViewRef = ref(null)

    function nextUniqueName(items, base, field) {
        const names = new Set((items || []).map(item => String(item?.[field] || '')))
        if (!names.has(base)) return base
        let suffix = 1
        while (names.has(`${base}${suffix}`)) suffix += 1
        return `${base}${suffix}`
    }

    function settlePeerCollisions(nodes, maxIterations = 20) {
        const list = nodes || []
        const gap = 24
        for (let iteration = 0; iteration < maxIterations; iteration += 1) {
            let changed = false
            for (let i = 0; i < list.length; i += 1) {
                for (let j = i + 1; j < list.length; j += 1) {
                    const a = list[i]
                    const b = list[j]
                    const aw = a.size?.w || NODE_WIDTH
                    const ah = a.size?.h || NODE_MIN_HEIGHT
                    const bw = b.size?.w || NODE_WIDTH
                    const bh = b.size?.h || NODE_MIN_HEIGHT
                    const ax = a.position?.x || 0
                    const ay = a.position?.y || 0
                    const bx = b.position?.x || 0
                    const by = b.position?.y || 0
                    const overlapX = Math.min(ax + aw + gap, bx + bw + gap) - Math.max(ax, bx)
                    const overlapY = Math.min(ay + ah + gap, by + bh + gap) - Math.max(ay, by)
                    if (overlapX <= 0 || overlapY <= 0) continue
                    changed = true
                    if (overlapX < overlapY) {
                        const push = Math.ceil(overlapX / 2 / 20) * 20
                        const direction = ax <= bx ? -1 : 1
                        a.position.x += direction * push
                        b.position.x -= direction * push
                    } else {
                        const push = Math.ceil(overlapY / 2 / 20) * 20
                        const direction = ay <= by ? -1 : 1
                        a.position.y += direction * push
                        b.position.y -= direction * push
                    }
                }
            }
            if (!changed) break
        }
    }

    const canvasMode = computed(() => store.canvasMode || 'workflow')
    const isTopology = computed(() => canvasMode.value === 'topology')
    const isFunctionCanvas = computed(() => canvasMode.value === 'function')
    const isFunctionWorkspaceEmpty = computed(() => isFunctionCanvas.value && store.functionWorkspaceEmpty)
    const activeGraph = computed(() => (
        isFunctionWorkspaceEmpty.value
            ? null
            : isTopology.value
            ? store.blueprint.page_map
            : getGraph(store.blueprint, isFunctionCanvas.value ? store.currentTaskId : MAIN_GRAPH_ID)
    ))
    const activeGraphLabel = computed(() => isTopology.value ? '页面地图' : getGraphLabel(store.blueprint, isFunctionCanvas.value ? store.currentTaskId : MAIN_GRAPH_ID))

    function requestCreateFunction() {
        window.dispatchEvent(new CustomEvent('easycode:create-function'))
    }

    // 节点可用类型：modes/label 来自后端 /api/params 配置（单一数据源），前端表兜底
    const availableNodeTypes = computed(() => getNodeTypesForMode(canvasMode.value, store.paramsDefinitions))

    // ===== 当前数据源（唯一模式判断点 1：读取哪个 JSON） =====
    const renderCanvasData = computed(() => {
        const graph = activeGraph.value
        if (!graph) return { tasks: [], edges: [] }
        const graphId = isTopology.value ? 'page_map' : (isFunctionCanvas.value ? store.currentTaskId : MAIN_GRAPH_ID)
        return {
            tasks: [{ task_id: graphId, task_name: activeGraphLabel.value, role: isFunctionCanvas.value ? 'function' : canvasMode.value, nodes: graph.nodes }],
            edges: graph.edges || []
        }
    })

    const canvasName = computed(() => (isTopology.value ? 'topology' : 'workflow'))

    // 撤销重做：主流程/函数与页面地图分别维护历史，避免跨工作区撤销
    const workflowUndoRedo = createCanvasUndoRedo('workflow')
    const topologyUndoRedo = createCanvasUndoRedo('topology')
    const activeUndoRedo = computed(() => (isTopology.value ? topologyUndoRedo : workflowUndoRedo))
    watch(() => store.currentTaskId, () => workflowUndoRedo.clear())

    // ===== 保存路由（唯一模式判断点 2：写入哪个 JSON） =====
    async function saveCanvas() {
        reconcileGraphIntegrity(renderCanvasData.value.tasks, activeGraph.value?.edges || [])
        if (isTopology.value) {
            await store.saveTopologyData()
        } else {
            await store.saveWorkflowImmediately()
        }
    }

    // ===== 节点结构更新（三类画布复用同一套逻辑） =====

    async function handleUpdateTasks(tasks) {
        activeUndoRedo.value.commit()
        if (activeGraph.value) activeGraph.value.nodes = JSON.parse(JSON.stringify(tasks?.[0]?.nodes || []))
        const repaired = reconcileEdgeWaypoints(activeGraph.value?.edges || [], activeGraph.value?.nodes || [])
        await saveCanvas()
        if (repaired.moved || repaired.removed) {
            ElMessage.info(`${repaired.moved + repaired.removed} 个转接点已自动避让节点`)
        }
    }

    async function handleUpdateGeometry({ tasks, movedNodeIds = [], delta = null }) {
        activeUndoRedo.value.commit()
        if (activeGraph.value && tasks) activeGraph.value.nodes = JSON.parse(JSON.stringify(tasks?.[0]?.nodes || []))
        if (activeGraph.value && delta) {
            translateInternalEdgeWaypoints(activeGraph.value.edges || [], movedNodeIds, delta)
        }
        const repaired = reconcileEdgeWaypoints(activeGraph.value?.edges || [], activeGraph.value?.nodes || [])
        await saveCanvas()
        if (repaired.moved || repaired.removed) {
            ElMessage.info(`${repaired.moved + repaired.removed} 个转接点已自动避让节点`)
        }
    }

    async function handleAddEdge(payload) {
        activeUndoRedo.value.commit()
        const edges = renderCanvasData.value.edges
        const sourceNode = (renderCanvasData.value.tasks || [])
            .flatMap(task => task.nodes || [])
            .find(node => node.node_id === payload.source)
        const normalizedPort = payload.source_port
        const descriptor = sourceNode
            ? getSourcePortDescriptors(sourceNode, edges).find(port => port.key === normalizedPort)
            : null
        const isNewPageExit = (sourceNode?.node_type || sourceNode?.type) === 'page_state'
            && String(normalizedPort || '').startsWith('exit_')
            && !descriptor
        const generatedExitId = isNewPageExit
            ? `exit_${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`}`
            : ''
        applyEdge(edges, {
            ...payload,
            source_port_id: payload.source_port_id || descriptor?.stableId || generatedExitId || normalizedPort,
            canvas: canvasName.value,
            tasks: renderCanvasData.value.tasks
        })
        await saveCanvas()
    }

    async function handleRemoveEdge(edge) {
        if (!edge || !edge.sourceNodeId) return
        activeUndoRedo.value.commit()
        const edges = renderCanvasData.value.edges
        const removed = removeEdge(edges, edge)
        if (removed) {
            await saveCanvas()
        }
    }

    async function handleUpdateEdgeRouting({ edgeId, routing }) {
        if (!edgeId || !activeGraph.value) return
        const edge = (activeGraph.value.edges || []).find(item => item.edge_id === edgeId)
        if (!edge) return
        activeUndoRedo.value.commit()
        const normalized = normalizeEdgeRouting(routing)
        if (normalized.waypoints.length) edge.routing = normalized
        else delete edge.routing
        await saveCanvas()
    }

    async function handleCreateNode(payload) {
        if (!activeGraph.value) {
            ElMessage.error('当前画布尚未就绪，请重新打开主流程、函数或页面地图后再新建节点')
            return { error: 'active graph missing' }
        }
        activeUndoRedo.value.commit()
        const tasks = renderCanvasData.value.tasks
        const graphBefore = JSON.parse(JSON.stringify(activeGraph.value || { nodes: [], edges: [] }))
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

        if (!targetTask && !isTopology.value && store.currentTaskId) {
            targetTask = tasks.find(task => task.task_id === store.currentTaskId) || null
        }
        if (!targetTask) targetTask = tasks[0] || null
        if (!targetTask) {
            ElMessage.error('当前画布没有可写入的流程，请重新打开对应画布后再试')
            return { error: 'active graph missing' }
        }

        if (!targetTask.nodes) targetTask.nodes = []

        const defaultNames = {
            click: '点击节点',
            image_recognition: '图像识别节点',
            ocr_recognition: 'OCR识别节点',
            page_state: '页面节点',
            control: '控件节点'
        }
        const chineseLabel = (availableNodeTypes.value[payload.type] || payload.type).replace(/^[^\u4e00-\u9fa5]+/, '').trim()
        const defaultBase = defaultNames[payload.type] || `${chineseLabel || payload.type}节点`
        const newNode = {
            node_id: payload.nodeId,
            node_name: payload.nodeName || nextUniqueName(targetTask.nodes, defaultBase, 'node_name'),
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

        // 新节点只在当前流程/集合内避让；流程之间不共享画布空间。
        const newNodeSize = {
            w: NODE_WIDTH,
            h: computeCanvasNodeHeight(newNode.params ? Object.keys(newNode.params).length : 0, 0)
        }
        // 避开当前流程已有节点（把新节点推到无碰撞位置，旧布局不动）
        const sameGroupNodes = (targetTask.nodes || []).map(n => ({
            position: n.position, size: { w: NODE_WIDTH, h: NODE_MIN_HEIGHT }
        }))
        const freePos = findFreePosition(sameGroupNodes, newNode.position, newNodeSize)
        newNode.position = { x: freePos.x, y: freePos.y }
        const displacedEdge = sourceNodeObj
            ? findEdgeAtPort(renderCanvasData.value.edges, payload.sourceNodeId, payload.portType, payload.sourcePortId)
            : null
        // 新节点必须先成为图中的正式成员，再建立连线。否则跨组归属无法
        // 解析，且会产生“节点已创建但连线半提交”的中间状态。
        targetTask.nodes.push(newNode)
        if (sourceNodeObj) {
            const connected = applyEdge(renderCanvasData.value.edges, {
                source: payload.sourceNodeId,
                target: payload.nodeId,
                source_port: payload.portType,
                source_port_id: payload.sourcePortId,
                canvas: canvasName.value,
                tasks: renderCanvasData.value.tasks
            })
            if (!connected) {
                targetTask.nodes = targetTask.nodes.filter(node => node.node_id !== newNode.node_id)
                if (targetTask.nodes.length === 0 && targetTask.role !== 'main') {
                    const index = tasks.findIndex(task => task.task_id === targetTask.task_id)
                    if (index >= 0) tasks.splice(index, 1)
                }
                ElMessage.error('节点与连线未能原子创建，请重新拉线')
                return { error: 'edge creation failed' }
            }
            // 插入语义必须保留原出口的显示/运行元数据。出口名称属于
            // A 的端口，因此留在 A → X；跨任务返回语义属于通往原下游
            // 的跳转，因此稍后转移到 X → B。
            if (displacedEdge) {
                const upstreamEdge = findEdgeAtPort(
                    renderCanvasData.value.edges,
                    payload.sourceNodeId,
                    payload.portType,
                    payload.sourcePortId
                )
                if (upstreamEdge && displacedEdge.label != null) {
                    upstreamEdge.label = displacedEdge.label
                }
            }
        }

        if (displacedEdge) {
            const downstreamPort = getPrimarySourcePort(newNode, [])
            applyEdge(renderCanvasData.value.edges, {
                source: payload.nodeId,
                target: displacedEdge.target_node,
                source_port: downstreamPort.key,
                source_port_id: downstreamPort.stableId,
                canvas: canvasName.value,
                tasks: renderCanvasData.value.tasks
            })
        }
        // Initial placement avoids direct overlap; after insertion all peers in
        // this group participate with equal weight, while other groups stay put.
        settlePeerCollisions(targetTask.nodes)
        try {
            await saveCanvas()
        } catch (error) {
            if (activeGraph.value) {
                activeGraph.value.nodes = graphBefore.nodes || []
                activeGraph.value.edges = graphBefore.edges || []
            }
            ElMessage.error(`节点创建失败，画布已恢复：${error?.message || '保存失败'}`)
            return { error: error?.message || 'save failed' }
        }
        uiStore.selectNodes([newNode.node_id], { primaryId: newNode.node_id, anchorId: newNode.node_id })
        uiStore.setFocusTarget({ type: 'node', id: newNode.node_id, timestamp: Date.now() })
        if (payload.announce !== false) ElMessage.success(`已创建节点“${newNode.node_name}”`)
        return { node: newNode, taskId: targetTask.task_id, displacedEdge }
    }

    function createIndependentId(prefix) {
        return `${prefix}_${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`}`
    }

    async function handlePasteSubgraph(payload) {
        const snapshot = payload?.snapshot
        if (!Array.isArray(snapshot?.nodes) || snapshot.nodes.length === 0) {
            ElMessage.warning('剪贴板中没有可粘贴的节点')
            return
        }
        activeUndoRedo.value.commit()
        const tasks = renderCanvasData.value.tasks
        const edges = renderCanvasData.value.edges
        let targetTask = null
        let sourceNode = null
        if (payload.sourceNodeId) {
            for (const task of tasks) {
                const found = (task.nodes || []).find(node => node.node_id === payload.sourceNodeId)
                if (!found) continue
                sourceNode = found
                targetTask = task
                break
            }
        }
        if (!targetTask && payload.groupId) {
            targetTask = tasks.find(task => task.task_id === payload.groupId) || null
        }
        if (!targetTask && !isTopology.value && store.currentTaskId) {
            targetTask = tasks.find(task => task.task_id === store.currentTaskId) || null
        }
        if (!targetTask) targetTask = tasks[0] || null
        if (!targetTask) return
        if (!targetTask.nodes) targetTask.nodes = []

        const sourcePrimaryId = snapshot.selectionOrder?.find(id => snapshot.nodes.some(node => node.node_id === id))
            || snapshot.nodes[0].node_id
        const sourcePrimaryNode = snapshot.nodes.find(node => node.node_id === sourcePrimaryId) || snapshot.nodes[0]
        const targetPosition = payload.position || sourcePrimaryNode.position || { x: 0, y: 0 }
        const delta = {
            x: Number(targetPosition.x || 0) - Number(sourcePrimaryNode.position?.x || 0),
            y: Number(targetPosition.y || 0) - Number(sourcePrimaryNode.position?.y || 0)
        }
        const nodeIdMap = new Map()
        const clonedNodes = snapshot.nodes.map(source => {
            const node = JSON.parse(JSON.stringify(source))
            const nextId = createIndependentId('node')
            nodeIdMap.set(source.node_id, nextId)
            node.node_id = nextId
            node.position = {
                x: Math.round((Number(source.position?.x || 0) + delta.x) / 20) * 20,
                y: Math.round((Number(source.position?.y || 0) + delta.y) / 20) * 20
            }
            if ((node.node_type || node.type) === 'page_state' && node.params) {
                node.params.page_id = createIndependentId('page')
            }
            return node
        })
        targetTask.nodes.push(...clonedNodes)

        const copiedEdges = []
        for (const sourceEdge of snapshot.edges || []) {
            const mappedSource = nodeIdMap.get(sourceEdge.source_node)
            const mappedTarget = nodeIdMap.get(sourceEdge.target_node)
            if (!mappedSource || !mappedTarget) continue
            const edge = JSON.parse(JSON.stringify(sourceEdge))
            edge.source_node = mappedSource
            edge.target_node = mappedTarget
            edge.edge_id = `e_${mappedSource}_${edge.source_port}_${mappedTarget}`
            edge.canvas = canvasName.value
            if (edge.routing?.waypoints?.length) {
                edge.routing = {
                    mode: 'manual',
                    waypoints: edge.routing.waypoints.map(point => ({
                        ...point,
                        id: createIndependentId('waypoint'),
                        x: Number(point.x || 0) + delta.x,
                        y: Number(point.y || 0) + delta.y
                    }))
                }
            }
            copiedEdges.push(edge)
        }
        edges.push(...copiedEdges)

        const mappedPrimaryId = nodeIdMap.get(sourcePrimaryId)
        if (sourceNode && mappedPrimaryId) {
            const sourcePort = payload.sourcePort || getPrimarySourcePort(sourceNode, edges).key
            const sourcePortId = payload.sourcePortId || sourcePort
            const displacedEdge = findEdgeAtPort(edges, sourceNode.node_id, sourcePort, sourcePortId)
            applyEdge(edges, {
                source: sourceNode.node_id,
                target: mappedPrimaryId,
                source_port: sourcePort,
                source_port_id: sourcePortId,
                canvas: canvasName.value,
                tasks
            })
            if (displacedEdge) {
                const outgoing = new Map()
                for (const edge of copiedEdges) {
                    if (!outgoing.has(edge.source_node)) outgoing.set(edge.source_node, [])
                    outgoing.get(edge.source_node).push(edge)
                }
                for (const list of outgoing.values()) {
                    list.sort((a, b) => String(a.source_port).localeCompare(String(b.source_port), 'zh-CN', { numeric: true }))
                }
                let tailId = mappedPrimaryId
                const visited = new Set()
                while (!visited.has(tailId) && (outgoing.get(tailId) || []).length) {
                    visited.add(tailId)
                    tailId = outgoing.get(tailId)[0].target_node
                }
                const tailNode = clonedNodes.find(node => node.node_id === tailId)
                const downstreamPort = getPrimarySourcePort(tailNode, edges)
                applyEdge(edges, {
                    source: tailId,
                    target: displacedEdge.target_node,
                    source_port: downstreamPort.key,
                    source_port_id: downstreamPort.stableId || downstreamPort.key,
                    canvas: canvasName.value,
                    tasks
                })
            }
        }

        settlePeerCollisions(targetTask.nodes)
        const orderedIds = (snapshot.selectionOrder || snapshot.nodes.map(node => node.node_id))
            .map(id => nodeIdMap.get(id))
            .filter(Boolean)
        uiStore.selectNodes(orderedIds, {
            primaryId: mappedPrimaryId,
            anchorId: mappedPrimaryId
        })
        await saveCanvas()
        ElMessage.success(`已粘贴 ${clonedNodes.length} 个独立节点及 ${copiedEdges.length} 条内部连线`)
    }

    async function handleDeleteNode(payload) {
        const owner = renderCanvasData.value.tasks.find(task => (task.nodes || []).some(node => node.node_id === payload?.nodeId))
        const target = owner?.nodes?.find(node => node.node_id === payload?.nodeId)
        if (target?.fixed) return ElMessage.warning('函数入口是固定节点，不能删除')
        try {
            await ElMessageBox.confirm(
                `确定删除节点“${target?.node_name || payload?.nodeId || '未命名节点'}”吗？相关连线也会删除，可使用撤销恢复。`,
                '删除节点',
                { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
            )
        } catch { return }
        activeUndoRedo.value.commit()
        const tasks = renderCanvasData.value.tasks
        const edges = renderCanvasData.value.edges
        const nextTasks = removeNode(tasks, edges, payload?.nodeId)
        if (activeGraph.value) activeGraph.value.nodes = nextTasks[0]?.nodes || []
        if (activeGraph.value) activeGraph.value.edges = edges
        uiStore.clearSelection()
        await saveCanvas()
        ElMessage.success('节点已删除')
    }

    // ===== 通用操作（两 Tab 共用） =====

    async function handleSave() {
        await store.saveBlueprintImmediately()
        ElMessage.success('蓝图已保存')
    }

    function openAutoLayout() {
        if (!activeGraph.value) return ElMessage.warning('请先打开可编辑画布')
        layoutOriginal.value = JSON.parse(JSON.stringify({ nodes: activeGraph.value.nodes || [] }))
        layoutPreviewActive.value = false
        layoutDialogVisible.value = true
    }

    function previewAutoLayout() {
        const selectedNodeIds = uiStore.selectedNodeIds || []
        if (layoutScope.value === 'selection' && !selectedNodeIds.length) {
            ElMessage.warning('请先选中要布局的节点')
            return
        }
        const original = layoutOriginal.value || JSON.parse(JSON.stringify({ nodes: activeGraph.value?.nodes || [] }))
        const preview = autoLayoutGraphGeometry({
            nodes: original.nodes || [],
            edges: renderCanvasData.value.edges
        }, {
            scope: layoutScope.value,
            selectedNodeIds
        })
        if (activeGraph.value) {
            activeGraph.value.nodes = preview.nodes
        }
        layoutPreviewActive.value = true
    }

    async function confirmAutoLayout() {
        if (!layoutPreviewActive.value) return
        const preview = JSON.parse(JSON.stringify({ nodes: activeGraph.value?.nodes || [] }))
        const original = JSON.parse(JSON.stringify(layoutOriginal.value || { nodes: [] }))
        if (activeGraph.value) {
            activeGraph.value.nodes = original.nodes || []
        }
        activeUndoRedo.value.commit()
        if (activeGraph.value) {
            activeGraph.value.nodes = preview.nodes || []
        }
        await saveCanvas()
        layoutOriginal.value = null
        layoutPreviewActive.value = false
        layoutDialogVisible.value = false
        ElMessage.success('自动布局已保存，可使用撤销恢复')
    }

    function cancelLayoutPreview() {
        if (layoutPreviewActive.value && layoutOriginal.value) {
            const original = JSON.parse(JSON.stringify(layoutOriginal.value))
            if (activeGraph.value) {
                activeGraph.value.nodes = original.nodes || []
            }
        }
        layoutOriginal.value = null
        layoutPreviewActive.value = false
        layoutDialogVisible.value = false
    }

    async function handleDelete() {
        const ids = uiStore.selectedNodeIds || []
        if (!ids.length) {
            ElMessage.warning('请先选中要删除的节点')
            return
        }
        const tasks = renderCanvasData.value.tasks
        const edges = renderCanvasData.value.edges
        const fixedIds = new Set((tasks[0]?.nodes || []).filter(node => node.fixed).map(node => node.node_id))
        const removableIds = ids.filter(id => !fixedIds.has(id))
        if (!removableIds.length) return ElMessage.warning('选中的节点不可删除')
        try {
            await ElMessageBox.confirm(
                `确定删除选中的 ${removableIds.length} 个节点吗？相关连线也会删除，可使用撤销恢复。`,
                '删除选中节点',
                { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
            )
        } catch { return }
        let nextTasks = tasks
        for (const id of removableIds) {
            nextTasks = removeNode(nextTasks, edges, id)
        }
        if (activeGraph.value) activeGraph.value.nodes = nextTasks[0]?.nodes || []
        if (activeGraph.value) activeGraph.value.edges = edges
        activeUndoRedo.value.commit()
        uiStore.clearSelection()
        await saveCanvas()
        ElMessage.success(`已删除 ${removableIds.length} 个节点`)
    }

    function handleSelectAll() {
        const allIds = (renderCanvasData.value.tasks || []).flatMap(t => (t.nodes || []).map(n => n.node_id))
        if (!allIds.length) return
        // 已全选 -> 取消全选
        if (uiStore.selectedNodeIds.length === allIds.length &&
            allIds.every(id => uiStore.selectedNodeIds.includes(id))) {
            uiStore.selectNodes([])
            return
        }
        uiStore.selectNodes(allIds)
    }

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
        const context = getCaptureContext()
        const sourceNodeId = context.anchorKind === 'node' ? context.anchorNodeId : null
        const sourceNode = sourceNodeId
            ? (renderCanvasData.value.tasks || []).flatMap(task => task.nodes || []).find(node => node.node_id === sourceNodeId)
            : null
        const port = context.selectedPort || (sourceNode ? getPrimarySourcePort(sourceNode, renderCanvasData.value.edges) : null)
        const position = sourceNode ? positionAfterNode(sourceNode) : { ...(context.viewportCenter || { x: 0, y: 0 }) }

        await handleCreateNode({
            nodeId,
            type: 'control',
            nodeName,
            params,
            position,
            sourceNodeId,
            groupId: sourceNode ? null : context.groupId,
            portType: port?.key || 'success',
            sourcePortId: port?.stableId || port?.key || 'success',
            announce: false,
        })
        uiStore.selectNodes([nodeId])
        ElMessage.success(`已生成控件节点 [${nodeName}]（${by} = ${target}）`)
    }

    const captureChains = new Map()

    function getCaptureContext() {
        const tasks = renderCanvasData.value.tasks || []
        const edges = renderCanvasData.value.edges || []
        const selectedIds = uiStore.selectedNodeIds?.length
            ? [...uiStore.selectedNodeIds]
            : (uiStore.selectedNodeId ? [uiStore.selectedNodeId] : [])
        const viewportCenter = canvasViewRef.value?.getViewportCenter?.() || { x: 0, y: 0 }
        if (selectedIds.length === 1) {
            for (const task of tasks) {
                const node = (task.nodes || []).find(item => item.node_id === selectedIds[0])
                if (!node) continue
                const primary = getPrimarySourcePort(node, edges)
                const described = getSourcePortDescriptors(node, edges)
                const ports = described.length ? described : [primary]
                return {
                    canvasMode: canvasMode.value,
                    anchorKind: 'node',
                    anchorNodeId: node.node_id,
                    groupId: task.task_id,
                    viewportCenter,
                    ports,
                    selectedPort: primary
                }
            }
        }
        const activeTask = isTopology.value
            ? tasks[0]
            : tasks.find(task => task.task_id === store.currentTaskId)
        if (activeTask) {
            return {
                canvasMode: canvasMode.value,
                anchorKind: isTopology.value ? 'page_map' : (isFunctionCanvas.value ? 'function' : 'main'),
                groupId: activeTask.task_id,
                viewportCenter,
                ports: [],
                selectedPort: null
            }
        }
        return {
            canvasMode: canvasMode.value,
            anchorKind: isTopology.value ? 'page_map' : 'project',
            groupId: tasks[0]?.task_id || null,
            viewportCenter,
            ports: [],
            selectedPort: null
        }
    }

    function positionAfterNode(node) {
        return {
            x: Math.round(((node?.position?.x || 0) + NODE_WIDTH + 60) / 20) * 20,
            y: Math.round((node?.position?.y || 0) / 20) * 20
        }
    }

    function resolveCaptureChain(snapshotId, initialContext = {}) {
        if (!captureChains.has(snapshotId)) {
            captureChains.set(snapshotId, {
                snapshotId,
                anchorKind: initialContext.anchorKind || 'project',
                tailNodeId: initialContext.anchorNodeId || null,
                groupId: initialContext.groupId || null,
                viewportCenter: initialContext.viewportCenter || { x: 0, y: 0 },
                transactions: []
            })
        }
        return captureChains.get(snapshotId)
    }

    async function executeCaptureCommand(command) {
        const snapshotId = command.snapshot_id
        const chain = resolveCaptureChain(command.capture_chain_id || snapshotId, command.capture_context || {})
        if (command.kind === 'rollback_operation') {
            const transaction = chain.transactions.at(-1)
            if (!transaction || transaction.operationId !== command.operation_id) {
                return { ok: true, skipped: true, message: '操作未提交或已被其他操作取代' }
            }
            if (transaction.canvasMutated) {
                activeUndoRedo.value.undo()
                try {
                    await saveCanvas()
                } catch (error) {
                    activeUndoRedo.value.redo()
                    await saveCanvas().catch(() => {})
                    throw error
                }
                chain.tailNodeId = transaction.previousTail || null
                chain.groupId = transaction.previousGroup || chain.groupId
            }
            chain.transactions.pop()
            return { ok: true, rolledBack: true }
        }
        if (command.kind === 'undo') {
            const transaction = chain.transactions.at(-1)
            if (!transaction) return { ok: false, message: '当前捕获会话没有可撤销操作' }
            if (transaction.canvasMutated) {
                activeUndoRedo.value.undo()
                try {
                    await saveCanvas()
                } catch (error) {
                    activeUndoRedo.value.redo()
                    await saveCanvas().catch(() => {})
                    throw error
                }
                chain.tailNodeId = transaction.previousTail || null
                chain.groupId = transaction.previousGroup || chain.groupId
            }
            chain.transactions.pop()
            return {
                ok: true,
                undo_asset_transaction: transaction.assetTransaction || '',
                tailNodeId: chain.tailNodeId,
                ports: chain.tailNodeId ? getCaptureTailPorts(chain.tailNodeId) : [],
                selectedPort: transaction.previousPort || null
            }
        }
        if (command.kind === 'record') {
            chain.transactions.push({
                canvasMutated: false,
                assetTransaction: command.asset_transaction || '',
                previousTail: chain.tailNodeId,
                previousGroup: chain.groupId,
                previousPort: command.port || null,
                operationId: command.operation_id || ''
            })
            return { ok: true, tailNodeId: chain.tailNodeId, ports: getCaptureTailPorts(chain.tailNodeId) }
        }

        const allowed = canvasMode.value === 'topology'
            ? ['click', 'image', 'ocr', 'page']
            : ['click', 'image', 'ocr']
        if (!allowed.includes(command.kind)) {
            throw new Error(command.kind === 'page' ? '页面节点只能在页面拓扑画布创建' : '当前画布不允许该捕获节点')
        }
        const referenceSize = command.reference_size || [0, 0]
        const rects = command.rects || []
        const templateKeys = command.template_keys || []
        const assetRefs = command.asset_refs || templateKeys
        let type = 'click'
        let params = buildNodeDefaultParams('click', store.paramsDefinitions)
        if (command.kind === 'click') {
            if (!Array.isArray(command.point) || command.point.length !== 2) throw new Error('缺少有效坐标点')
            params = {
                ...params,
                position: command.point.map(Number),
                position_reference_size: referenceSize,
                coordinate_space: 'workspace_px'
            }
        } else if (command.kind === 'image') {
            if (rects.length !== 1 || assetRefs.length !== 1) throw new Error('图像识别要求恰好一个框选范围')
            type = 'image_recognition'
            params = {
                ...buildNodeDefaultParams(type, store.paramsDefinitions),
                image_source: assetRefs[0],
                region_type: 'recorded',
                region_value: rects[0],
                region_reference_size: referenceSize,
                coordinate_space: 'workspace_px'
            }
        } else if (command.kind === 'ocr') {
            if (rects.length !== 1 || assetRefs.length !== 1) throw new Error('OCR识别要求恰好一个框选范围')
            type = 'ocr_recognition'
            params = {
                ...buildNodeDefaultParams(type, store.paramsDefinitions),
                image_source: assetRefs[0],
                region_type: 'recorded',
                region_value: rects[0],
                region_reference_size: referenceSize,
                coordinate_space: 'workspace_px'
            }
        } else if (command.kind === 'page') {
            if (!rects.length || rects.length !== assetRefs.length) throw new Error('页面特征资源与框选数量不一致')
            type = 'page_state'
            params = {
                ...buildNodeDefaultParams(type, store.paramsDefinitions),
                page_id: `page_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`,
                feature_mode: 'and',
                features: assetRefs.map((key, index) => ({
                    condition_type: 'image_exists',
                    exist_mode: 'exists',
                    image_source: key,
                    gray_scale: true,
                    gray_threshold: 127,
                    threshold: 85,
                    region_type: 'recorded',
                    region_value: rects[index],
                    region_reference_size: referenceSize,
                    coordinate_space: 'workspace_px',
                    negate: false
                }))
            }
        }

        const previousTail = chain.tailNodeId
        const previousGroup = chain.groupId
        let sourceNode = null
        if (chain.tailNodeId) {
            sourceNode = (renderCanvasData.value.tasks || [])
                .flatMap(task => task.nodes || [])
                .find(node => node.node_id === chain.tailNodeId)
        }
        const port = command.port || (sourceNode ? getPrimarySourcePort(sourceNode, renderCanvasData.value.edges) : null)
        const nodeId = `node_${Date.now()}${Math.random().toString(36).slice(2, 7)}`
        const position = sourceNode
            ? positionAfterNode(sourceNode)
            : { ...chain.viewportCenter }
        try {
            const created = await handleCreateNode({
                nodeId,
                type,
                params,
                position,
                sourceNodeId: sourceNode?.node_id || null,
                groupId: sourceNode ? null : chain.groupId,
                portType: port?.key || 'success',
                sourcePortId: port?.stableId || port?.key || 'success',
                announce: false
            })
            if (created?.error) return { ok: false, message: created.error }
            chain.tailNodeId = nodeId
            chain.groupId = created?.taskId || chain.groupId
            chain.transactions.push({
                canvasMutated: true,
                assetTransaction: command.asset_transaction || '',
                previousTail,
                previousGroup,
                previousPort: command.port || null,
                operationId: command.operation_id || ''
            })
            return {
                ok: true,
                nodeId,
                nodeName: created?.node?.node_name || '',
                tailNodeId: nodeId,
                groupId: chain.groupId,
                ports: getCaptureTailPorts(nodeId),
                // 页面节点尚未连线时也有一个稳定的“出口 1”，CaptureHost
                // 必须显示它，不能等第一条线生成后才出现下拉项。
                selectedPort: getPrimarySourcePort(created.node, renderCanvasData.value.edges)
            }
        } catch (error) {
            activeUndoRedo.value.undo()
            await saveCanvas().catch(() => {})
            throw error
        }
    }

    function getCaptureTailPorts(nodeId) {
        if (!nodeId) return []
        const node = (renderCanvasData.value.tasks || []).flatMap(task => task.nodes || []).find(item => item.node_id === nodeId)
        if (!node) return []
        const ports = getSourcePortDescriptors(node, renderCanvasData.value.edges)
        return ports.length ? ports : [getPrimarySourcePort(node, renderCanvasData.value.edges)]
    }

    const navigateToFlow = async event => {
        const taskId = event?.detail?.taskId
        if (!taskId || (taskId !== MAIN_GRAPH_ID && !(store.blueprint.functions || []).some(item => item.function_id === taskId))) return
        try {
            await store.navigateToGraph(taskId === MAIN_GRAPH_ID ? 'workflow' : 'function', taskId)
            uiStore.setFocusTarget({ type: 'graph', id: taskId, timestamp: Date.now() })
        } catch (error) {
            notifyActionError(error, '无法打开目标流程')
        }
    }
    onMounted(() => {
        window.addEventListener('easycode:navigate-flow', navigateToFlow)
    })
    onUnmounted(() => {
        window.removeEventListener('easycode:navigate-flow', navigateToFlow)
    })

    const undoCanvas = () => {
        if (!activeUndoRedo.value.canUndo.value) return false
        activeUndoRedo.value.undo()
        return true
    }
    const redoCanvas = () => {
        if (!activeUndoRedo.value.canRedo.value) return false
        activeUndoRedo.value.redo()
        return true
    }

    defineExpose({
        createControlNodeFromCapture,
        executeCaptureCommand,
        getCaptureContext,
        undoCanvas,
        redoCanvas,
        saveCanvas,
        openAutoLayout
    })
</script>

<style scoped>
.canvas-page-shell{width:100%;height:100%;min-height:0;display:flex;flex-direction:column;background:var(--el-bg-color-page)}
.canvas-page-shell :deep(.custom-canvas-container){min-height:0;flex:1}
.function-workspace-empty{flex:1;min-height:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px;text-align:center;color:var(--app-text-secondary);background:var(--app-canvas-bg)}
.function-empty-icon{width:44px;height:44px;display:grid;place-items:center;margin-bottom:12px;border:1px solid var(--app-border-subtle);border-radius:10px;background:var(--app-panel-bg);color:var(--el-color-primary)}
.function-workspace-empty strong{font-size:14px;color:var(--app-text-primary)}
.function-workspace-empty p{max-width:360px;margin:7px 0 16px;font-size:11px;line-height:1.6;color:var(--app-text-placeholder)}
.function-workspace-empty button{height:30px;display:flex;align-items:center;gap:6px;padding:0 11px;border:0;border-radius:6px;background:var(--el-color-primary);color:var(--app-color-on-primary);font:inherit;cursor:pointer}
.function-workspace-empty button:hover{background:var(--app-color-primary-hover)}
.function-workspace-empty button:focus-visible{outline:0;box-shadow:var(--focus-ring)}
</style>
