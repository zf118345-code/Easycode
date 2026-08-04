<template>
    <div class="workflow-canvas-container" @click="onCanvasClick">
        <VueFlow v-model:nodes="flowNodes"
                 v-model:edges="flowEdges"
                 :default-viewport="{ zoom: 1 }"
                 :min-zoom="0.2"
                 :max-zoom="4"
                 fit-view-on-init
                 class="dark-vue-flow"
                 @node-click="onNodeClick"
                 @edge-click="onEdgeClick"
                 @pane-click="onPaneClick"
                 @node-drag-stop="onNodeDragStop"
                 @connect="onConnect"
                 @connect-start="onConnectStart"
                 @connect-end="onConnectEnd">
            <Background :pattern-color="'#313352'" :gap="16" />
            <Controls />
            <MiniMap />
        </VueFlow>

        <!-- 方案 B 核心：绝对定位视口层，完美跟随缩放平移 -->
        <div class="task-groups-viewport-layer" :style="viewportStyle">
            <div v-for="group in dynamicGroups"
                 :key="group.groupId"
                 class="absolute-task-group"
                 :style="{
             left: group.box.x + 'px',
             top: group.box.y + 'px',
             width: group.box.w + 'px',
             height: group.box.h + 'px'
           }">
                <div class="group-title-badge"
                     @mousedown="startGroupDrag($event, group.groupId)">
                    <div class="group-name-text">{{ group.groupName }}</div>
                    <div class="group-sub-info">
                        <span class="left-info">间隔: {{ group.loopInterval || 0 }}s</span>
                        <span class="right-info">循环: {{ group.loopCount }}次</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 拖线松手菜单 -->
        <div v-if="spawnMenu.visible"
             class="spawn-menu"
             :style="{ left: spawnMenu.x + 'px', top: spawnMenu.y + 'px' }">
            <div class="spawn-menu-header">
                ⚡ 快捷创建并连接 ({{ spawnMenu.portType === 'fail' ? '🔴 失败分支' : '🟢 成功流向' }})
            </div>
            <div class="spawn-menu-list">
                <div v-for="(label, type) in availableNodeTypes"
                     :key="type"
                     class="spawn-menu-item"
                     @click="createAndConnectNode(type)">
                    {{ label }}
                </div>
            </div>
        </div>
    </div>
</template>

<script>
    import { ref, watch, computed, onMounted, onUnmounted, h } from 'vue'
    import { VueFlow, useVueFlow, Position, Handle, MarkerType } from '@vue-flow/core'
    import { Background } from '@vue-flow/background'
    import { Controls } from '@vue-flow/controls'
    import { MiniMap } from '@vue-flow/minimap'
    import { useMainStore } from '@/stores'
    import { ElMessage } from 'element-plus'

    import '@vue-flow/core/dist/style.css'
    import '@vue-flow/core/dist/theme-default.css'
    import '@vue-flow/controls/dist/style.css'
    import '@vue-flow/minimap/dist/style.css'

    export default {
        name: 'WorkflowCanvas',
        components: {
            VueFlow,
            Background,
            Controls,
            MiniMap
        },
        setup() {
            const store = useMainStore()
            const { screenToFlowCoordinate, viewport } = useVueFlow()

            const flowNodes = ref([])
            const flowEdges = ref([])
            const dynamicGroups = ref([])
            const spawnMenu = ref({ visible: false, x: 0, y: 0, sourceNodeId: null, portType: 'succ', clientX: 0, clientY: 0 })

            const draggingExistingConnection = ref(null)

            const viewportStyle = computed(() => {
                const v = viewport.value || { x: 0, y: 0, zoom: 1 }
                return {
                    transform: `translate(${v.x}px, ${v.y}px) scale(${v.zoom})`,
                    transformOrigin: '0 0'
                }
            })

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

            const hasFailurePort = (nodeType) => {
                return ['image_recognition', 'ocr_recognition', 'branch', 'logic_check'].includes(nodeType)
            }

            const syncBlueprintCanvas = () => {
                let tasks = []
                if (store.currentTaskData) {
                    if (Array.isArray(store.currentTaskData.tasks)) {
                        tasks = store.currentTaskData.tasks
                    } else {
                        tasks = [store.currentTaskData]
                    }
                }

                const newNodes = []
                const newEdges = []
                const newGroups = []

                let groupStartY = 50

                tasks.forEach((task, tIndex) => {
                    const groupId = `group_${task.task_id || tIndex}`
                    const groupName = task.task_name || store.currentProjectName || `任务组 ${tIndex + 1}`
                    const rawNodes = task.nodes || store.nodes || []

                    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity

                    if (rawNodes.length > 0) {
                        rawNodes.forEach((node, nIndex) => {
                            const posX = node.position?.x ?? (50 + (nIndex % 3) * 190)
                            const posY = node.position?.y ?? (groupStartY + 40 + Math.floor(nIndex / 3) * 100)

                            minX = Math.min(minX, posX)
                            minY = Math.min(minY, posY)
                            maxX = Math.max(maxX, posX + 160)
                            maxY = Math.max(maxY, posY + 60)
                        })
                    } else {
                        minX = 50; minY = groupStartY; maxX = 250; maxY = groupStartY + 100
                    }

                    const padding = 30
                    const boxX = minX - padding
                    const boxY = minY - padding - 35
                    const boxW = (maxX - minX) + padding * 2
                    const boxH = (maxY - minY) + padding * 2 + 35

                    const boxDescriptor = { x: boxX, y: boxY, w: Math.max(boxW, 240), h: Math.max(boxH, 130) }

                    newGroups.push({
                        groupId,
                        groupName,
                        loopCount: task.loop_count || 1,
                        loopInterval: task.loop_interval || 0,
                        box: boxDescriptor
                    })

                    rawNodes.forEach((node, nIndex) => {
                        const posX = node.position?.x ?? (minX + (nIndex % 3) * 190)
                        const posY = node.position?.y ?? (minY + Math.floor(nIndex / 3) * 100)
                        const isSelected = store.selectedNodeId === node.node_id
                        const showFailPort = hasFailurePort(node.node_type)

                        const handles = [
                            h(Handle, { type: 'target', position: Position.Top, id: 'target_in' }),
                            h(Handle, { type: 'source', position: Position.Bottom, id: 'succ_out' })
                        ]

                        if (showFailPort) {
                            handles.push(
                                h(Handle, { type: 'source', position: Position.Bottom, id: 'fail_out', class: 'failure-handle' })
                            )
                        }

                        newNodes.push({
                            id: node.node_id,
                            label: () => h('div', { class: 'custom-node-content' }, [
                                h('div', { class: 'node-title' }, `${nIndex + 1}. ${node.node_name || node.node_id}`),
                                h('div', { class: 'node-type-tag' }, `[${node.node_type}]`),
                                ...handles
                            ]),
                            position: { x: posX, y: posY },
                            zIndex: 10,
                            style: {
                                background: 'var(--el-fill-color-blank)',
                                color: 'var(--el-text-color-primary)',
                                border: isSelected ? '2px solid var(--el-color-primary)' : '1px solid var(--el-border-color-light)',
                                borderRadius: '8px',
                                padding: '10px 14px',
                                fontSize: '12px',
                                fontWeight: '600',
                                boxShadow: isSelected ? '0 0 12px rgba(78, 209, 156, 0.4)' : '0 4px 12px rgba(0,0,0,0.3)',
                                cursor: 'pointer',
                                width: '160px',
                                minHeight: '60px'
                            }
                        })

                        // 成功跳转连线
                        const onSuccess = node.on_success || {}
                        if (onSuccess.target_node) {
                            const isSelfLoop = node.node_id === onSuccess.target_node
                            if (isSelfLoop) {
                                const waypointId = `waypoint_${node.node_id}_succ`
                                newNodes.push({
                                    id: waypointId,
                                    type: 'default',
                                    position: { x: posX + 200, y: posY + 20 },
                                    label: () => h('div', { style: 'position: relative; width: 100%; height: 100%;' }, [
                                        h(Handle, { type: 'target', position: Position.Bottom, id: 'wp_in', style: { bottom: '0%', left: '50%', transform: 'translateX(-50%)', background: '#4ed19c', border: '2px solid #181926' } }),
                                        h(Handle, { type: 'source', position: Position.Top, id: 'wp_out', style: { top: '0%', left: '50%', transform: 'translateX(-50%)', background: '#4ed19c', border: '2px solid #181926' } })
                                    ]),
                                    style: { width: '16px', height: '16px', background: '#4ed19c', borderRadius: '50%', border: '2px solid #ffffff', padding: '0', minHeight: 'unset', boxShadow: '0 0 8px rgba(78,209,156,0.6)' },
                                    zIndex: 11
                                })
                                newEdges.push({
                                    id: `e_${node.node_id}_succ_wp`,
                                    source: node.node_id,
                                    sourceHandle: 'succ_out',
                                    target: waypointId,
                                    targetHandle: 'wp_in',
                                    type: 'smoothstep',
                                    style: { stroke: '#4ed19c', strokeWidth: 2 }
                                })
                                newEdges.push({
                                    id: `e_wp_${node.node_id}_succ_target`,
                                    source: waypointId,
                                    sourceHandle: 'wp_out',
                                    target: onSuccess.target_node,
                                    targetHandle: 'target_in',
                                    type: 'smoothstep',
                                    label: '循环重试',
                                    animated: true,
                                    markerEnd: { type: MarkerType.ArrowClosed, color: '#4ed19c' },
                                    style: { stroke: '#4ed19c', strokeWidth: 2 },
                                    labelStyle: { fill: '#4ed19c', fontWeight: 'bold', fontSize: '10px' },
                                    labelBgStyle: { fill: '#181926' }
                                })
                            } else {
                                newEdges.push({
                                    id: `e_${node.node_id}_succ_${onSuccess.target_node}`,
                                    source: node.node_id,
                                    sourceHandle: 'succ_out',
                                    target: onSuccess.target_node,
                                    targetHandle: 'target_in',
                                    type: 'default',
                                    label: '流向',
                                    animated: true,
                                    markerEnd: { type: MarkerType.ArrowClosed, color: '#4ed19c' },
                                    style: { stroke: '#4ed19c', strokeWidth: 2 },
                                    labelStyle: { fill: '#4ed19c', fontWeight: 'bold', fontSize: '10px' },
                                    labelBgStyle: { fill: '#181926' }
                                })
                            }
                        }

                        // 失败跳转连线
                        const onFailure = node.on_failure || {}
                        if (onFailure.target_node) {
                            const isSelfLoop = node.node_id === onFailure.target_node
                            if (isSelfLoop) {
                                const waypointId = `waypoint_${node.node_id}_fail`
                                newNodes.push({
                                    id: waypointId,
                                    type: 'default',
                                    position: { x: posX + 200, y: posY + 20 },
                                    label: () => h('div', { style: 'position: relative; width: 100%; height: 100%;' }, [
                                        h(Handle, { type: 'target', position: Position.Bottom, id: 'wp_in', style: { bottom: '0%', left: '50%', transform: 'translateX(-50%)', background: '#f56c6c', border: '2px solid #181926' } }),
                                        h(Handle, { type: 'source', position: Position.Top, id: 'wp_out', style: { top: '0%', left: '50%', transform: 'translateX(-50%)', background: '#f56c6c', border: '2px solid #181926' } })
                                    ]),
                                    style: { width: '16px', height: '16px', background: '#f56c6c', borderRadius: '50%', border: '2px solid #ffffff', padding: '0', minHeight: 'unset', boxShadow: '0 0 8px rgba(245,108,108,0.6)' },
                                    zIndex: 11
                                })
                                newEdges.push({
                                    id: `e_${node.node_id}_fail_wp`,
                                    source: node.node_id,
                                    sourceHandle: 'fail_out',
                                    target: waypointId,
                                    targetHandle: 'wp_in',
                                    type: 'smoothstep',
                                    style: { stroke: '#f56c6c', strokeWidth: 2 }
                                })
                                newEdges.push({
                                    id: `e_wp_${node.node_id}_fail_target`,
                                    source: waypointId,
                                    sourceHandle: 'wp_out',
                                    target: onFailure.target_node,
                                    targetHandle: 'target_in',
                                    type: 'smoothstep',
                                    label: '未找到重试',
                                    markerEnd: { type: MarkerType.ArrowClosed, color: '#f56c6c' },
                                    style: { stroke: '#f56c6c', strokeWidth: 2 },
                                    labelStyle: { fill: '#f56c6c', fontWeight: 'bold', fontSize: '10px' },
                                    labelBgStyle: { fill: '#181926' }
                                })
                            } else {
                                newEdges.push({
                                    id: `e_${node.node_id}_fail_${onFailure.target_node}`,
                                    source: node.node_id,
                                    sourceHandle: 'fail_out',
                                    target: onFailure.target_node,
                                    targetHandle: 'target_in',
                                    type: 'default',
                                    label: '失败',
                                    markerEnd: { type: MarkerType.ArrowClosed, color: '#4ed19c' },
                                    style: { stroke: '#f56c6c', strokeWidth: 2, strokeDasharray: '4 4' },
                                    labelStyle: { fill: '#f56c6c', fontWeight: 'bold', fontSize: '10px' },
                                    labelBgStyle: { fill: '#181926' }
                                })
                            }
                        }
                    })

                    groupStartY = boxY + boxH + 60
                })

                flowNodes.value = newNodes
                flowEdges.value = newEdges
                dynamicGroups.value = newGroups
            }

            watch(
                () => [store.currentTaskData, store.nodes, store.selectedNodeId],
                () => {
                    syncBlueprintCanvas()
                },
                { immediate: true, deep: true }
            )

            const onNodeClick = ({ node }) => {
                spawnMenu.value.visible = false
                store.selectNode(node.id)
            }

            const onEdgeClick = ({ edge }) => {
                spawnMenu.value.visible = false
                flowEdges.value.forEach(e => {
                    e.style = { ...e.style, strokeWidth: e.id === edge.id ? 4 : 2 }
                })
                store.selectedNodeId = null
                ElMessage({
                    message: `已选中连线 (${edge.id})，按 Delete 键可将其删除`,
                    type: 'info',
                    duration: 2000
                })
            }

            const onPaneClick = () => {
                store.selectedNodeId = null
                spawnMenu.value.visible = false
                flowEdges.value.forEach(e => {
                    if (e.style?.strokeWidth > 2) {
                        e.style = { ...e.style, strokeWidth: 2 }
                    }
                })
            }

            const onConnectStart = (params, event) => {
                let nodeId = params?.nodeId || params?.node?.id
                let handleId = params?.handleId || params?.handle?.id

                if (!nodeId && store.selectedNodeId) {
                    nodeId = store.selectedNodeId
                }

                draggingExistingConnection.value = { nodeId, handleId }
            }

            const onConnectEnd = async (event) => {
                const { clientX, clientY } = event
                const target = event.target

                const isBlankArea = !target.closest('.vue-flow__handle') && !target.closest('.vue-flow__node')

                if (isBlankArea && draggingExistingConnection.value && draggingExistingConnection.value.nodeId) {
                    const { nodeId, handleId } = draggingExistingConnection.value

                    let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                    let targetNodeObj = null
                    for (const task of tasks) {
                        const found = (task.nodes || store.nodes).find(n => n.node_id === nodeId)
                        if (found) { targetNodeObj = found; break; }
                    }

                    const isFail = handleId?.includes('fail')
                    const hasExistingTarget = targetNodeObj && (
                        (isFail && targetNodeObj.on_failure?.target_node) ||
                        (!isFail && targetNodeObj.on_success?.target_node)
                    )

                    // 如果端口原本有连线 ➔ 拖到空白处执行删除
                    if (hasExistingTarget) {
                        let modified = false
                        for (const task of tasks) {
                            const foundNode = (task.nodes || store.nodes).find(n => n.node_id === nodeId)
                            if (foundNode) {
                                if (isFail && foundNode.on_failure) {
                                    foundNode.on_failure.target_node = ''
                                    modified = true
                                } else if (!isFail && foundNode.on_success) {
                                    foundNode.on_success.target_node = ''
                                    modified = true
                                }
                            }
                        }

                        if (modified) {
                            if (store.currentTaskData) {
                                store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                            }
                            await store.saveCurrentTask(true)
                            syncBlueprintCanvas()
                            ElMessage.success('已成功断开并删除连线')
                            draggingExistingConnection.value = null
                            return
                        }
                    }

                    // 如果端口原本没有连线 ➔ 延时弹出快捷创建菜单
                    if (nodeId) {
                        const portType = (handleId && handleId.includes('fail')) ? 'fail' : 'succ'
                        setTimeout(() => {
                            spawnMenu.value = {
                                visible: true,
                                x: clientX,
                                y: clientY,
                                sourceNodeId: nodeId,
                                portType,
                                clientX,
                                clientY
                            }
                        }, 50)
                    }
                }
                draggingExistingConnection.value = null
            }

            const startGroupDrag = (e, groupId) => {
                e.stopPropagation()
                const startX = e.clientX
                const startY = e.clientY

                let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                const taskIndex = tasks.findIndex((t, idx) => `group_${t.task_id || idx}` === groupId)
                if (taskIndex === -1) return

                const taskNodes = tasks[taskIndex].nodes || store.nodes
                const initialPositions = taskNodes.map(n => ({ x: n.position?.x || 0, y: n.position?.y || 0 }))

                const onMouseMove = (moveEvent) => {
                    const dx = moveEvent.clientX - startX
                    const dy = moveEvent.clientY - startY

                    taskNodes.forEach((n, idx) => {
                        if (!n.position) n.position = { x: 0, y: 0 }
                        n.position.x = initialPositions[idx].x + dx
                        n.position.y = initialPositions[idx].y + dy
                    })
                    syncBlueprintCanvas()
                }

                const onMouseUp = async () => {
                    window.removeEventListener('mousemove', onMouseMove)
                    window.removeEventListener('mouseup', onMouseUp)

                    if (store.currentTaskData) {
                        store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                    }
                    await store.saveCurrentTask(true)
                    ElMessage.success('任务组整体移动保存成功')
                }

                window.addEventListener('mousemove', onMouseMove)
                window.addEventListener('mouseup', onMouseUp)
            }

            const onNodeDragStop = async ({ node }) => {
                let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                for (const task of tasks) {
                    const targetNode = (task.nodes || store.nodes).find(n => n.node_id === node.id)
                    if (targetNode) {
                        targetNode.position = { x: node.position.x, y: node.position.y }
                        break
                    }
                }
                if (store.currentTaskData) {
                    store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                }
                await store.saveCurrentTask(true)
                syncBlueprintCanvas()
            }

            const createAndConnectNode = async (nodeType) => {
                const sourceId = spawnMenu.value.sourceNodeId
                const portType = spawnMenu.value.portType
                spawnMenu.value.visible = false

                let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                let targetTask = null, sourceNodeObj = null
                for (const t of tasks) {
                    const found = (t.nodes || store.nodes).find(n => n.node_id === sourceId)
                    if (found) { targetTask = t; sourceNodeObj = found; break }
                }

                if (!sourceNodeObj) return

                const newNodeId = `node_${Date.now()}`
                const targetNodesList = targetTask?.nodes || store.nodes
                const newNodeName = `${nodeType}_${targetNodesList.length + 1}`

                const flowPos = screenToFlowCoordinate({ x: spawnMenu.value.clientX, y: spawnMenu.value.clientY })
                const newPosX = flowPos.x - 80
                const newPosY = flowPos.y - 30

                const newNode = {
                    node_id: newNodeId,
                    node_name: newNodeName,
                    node_type: nodeType,
                    params: {},
                    delay_before: 0,
                    loop_count: 1,
                    enabled: true,
                    on_success: { jump_type: 'node', target_node: '' },
                    on_failure: { jump_type: 'node', target_node: '' },
                    position: { x: newPosX, y: newPosY }
                }

                if (portType === 'fail') {
                    if (!sourceNodeObj.on_failure) sourceNodeObj.on_failure = { jump_type: 'node', target_node: '' }
                    sourceNodeObj.on_failure.target_node = newNodeId
                } else {
                    if (!sourceNodeObj.on_success) sourceNodeObj.on_success = { jump_type: 'node', target_node: '' }
                    sourceNodeObj.on_success.target_node = newNodeId
                }

                targetNodesList.push(newNode)

                if (store.currentTaskData) {
                    store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                }
                await store.saveCurrentTask(true)
                syncBlueprintCanvas()
                store.selectNode(newNodeId)
                ElMessage.success(`快捷创建 [${portType === 'fail' ? '🔴 失败分支' : '🟢 成功流向'}] 节点成功: [${newNodeName}]`)
            }

            const onConnect = async (params) => {
                spawnMenu.value.visible = false
                let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                let foundNode = null
                for (const task of tasks) {
                    foundNode = (task.nodes || store.nodes).find(n => n.node_id === params.source)
                    if (foundNode) break
                }

                if (foundNode) {
                    const isFail = params.sourceHandle?.includes('fail')
                    if (isFail) {
                        if (!foundNode.on_failure) foundNode.on_failure = { jump_type: 'node', target_node: '' }
                        foundNode.on_failure.target_node = params.target
                        ElMessage.success(`失败分支连线绑定成功 ➔ [${params.target}]`)
                    } else {
                        if (!foundNode.on_success) foundNode.on_success = { jump_type: 'node', target_node: '' }
                        foundNode.on_success.target_node = params.target
                        ElMessage.success(`成功流向连线绑定成功 ➔ [${params.target}]`)
                    }

                    if (store.currentTaskData) {
                        store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                    }
                    await store.saveCurrentTask(true)
                    syncBlueprintCanvas()
                }
            }

            const globalClickHandler = (e) => {
                if (e.target.closest('.spawn-menu')) return
                if (!e.target.closest('.vue-flow__handle') && !e.target.closest('.vue-flow__edge')) {
                    spawnMenu.value.visible = false
                }
            }

            const globalKeydownHandler = async (e) => {
                if (e.key === 'Delete' || e.key === 'Backspace') {
                    const selectedEdge = flowEdges.value.find(edge => edge.style?.strokeWidth > 2)
                    if (selectedEdge) {
                        const edgeId = selectedEdge.id
                        let sourceNodeId = ''
                        let typeFlag = ''

                        if (edgeId.includes('_fail_')) {
                            typeFlag = 'fail'
                            sourceNodeId = edgeId.substring(2, edgeId.indexOf('_fail_'))
                        } else if (edgeId.includes('_succ_')) {
                            typeFlag = 'succ'
                            sourceNodeId = edgeId.substring(2, edgeId.indexOf('_succ_'))
                        }

                        if (sourceNodeId && typeFlag) {
                            let tasks = store.currentTaskData?.tasks || (store.currentTaskData ? [store.currentTaskData] : [])
                            let modified = false
                            for (const task of tasks) {
                                const foundNode = (task.nodes || store.nodes).find(n => n.node_id === sourceNodeId)
                                if (foundNode) {
                                    if (typeFlag === 'fail' && foundNode.on_failure) {
                                        foundNode.on_failure.target_node = ''
                                        modified = true
                                    } else if (typeFlag === 'succ' && foundNode.on_success) {
                                        foundNode.on_success.target_node = ''
                                        modified = true
                                    }
                                }
                            }

                            if (modified) {
                                if (store.currentTaskData) {
                                    store.currentTaskData.tasks = JSON.parse(JSON.stringify(tasks))
                                }
                                await store.saveCurrentTask(true)
                                syncBlueprintCanvas()
                                ElMessage.success('已通过快捷键删除连线')
                            }
                        }
                    }
                }
            }

            onMounted(() => {
                window.addEventListener('click', globalClickHandler)
                window.addEventListener('keydown', globalKeydownHandler)
            })
            onUnmounted(() => {
                window.removeEventListener('click', globalClickHandler)
                window.removeEventListener('keydown', globalKeydownHandler)
            })

            return {
                flowNodes,
                flowEdges,
                dynamicGroups,
                viewportStyle,
                spawnMenu,
                availableNodeTypes,
                onNodeClick,
                onEdgeClick,
                onPaneClick,
                startGroupDrag,
                onNodeDragStop,
                onConnectStart,
                onConnectEnd,
                createAndConnectNode,
                onConnect
            }
        }
    }
</script>

<style scoped>
    .workflow-canvas-container {
        width: 100%;
        height: 100%;
        background: var(--el-bg-color-page);
        position: relative;
        overflow: hidden;
    }

    .task-groups-viewport-layer {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 5;
        will-change: transform;
    }

    .absolute-task-group {
        position: absolute;
        box-sizing: border-box;
        border: 2px dashed #4ed19c;
        border-radius: 12px;
        background: rgba(78, 209, 156, 0.02);
    }

    .group-title-badge {
        position: absolute;
        top: -24px;
        left: 16px;
        right: 16px;
        background: var(--el-bg-color-page);
        padding: 4px 10px;
        color: #4ed19c;
        border: 1px dashed #4ed19c;
        border-radius: 6px;
        pointer-events: auto;
        cursor: grab;
        user-select: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

        .group-title-badge:active {
            cursor: grabbing;
        }

        .group-title-badge:hover {
            background: var(--el-fill-color-light);
            border-color: #5ce3aa;
        }

    .group-name-text {
        font-size: 12px;
        font-weight: bold;
    }

    .group-sub-info {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        color: var(--el-text-color-secondary);
        font-weight: normal;
    }

    :deep(.custom-node-content) {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    :deep(.node-title) {
        font-size: 12px;
        font-weight: 600;
    }

    :deep(.node-type-tag) {
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }

    /* 顶部入口与底部成功出口 (纯净绿球) */
    :deep(.vue-flow__handle) {
        width: 12px;
        height: 12px;
        background: #4ed19c;
        border: 2px solid #181926;
        border-radius: 50%;
        left: 50%;
        transform: translateX(-50%);
    }

    :deep(.vue-flow__handle:hover) {
        border-color: #ffffff;
        box-shadow: 0 0 8px rgba(78, 209, 156, 0.8);
    }

    /* 底部右下角失败分支出口 (纯正红球，稳居右下角) */
    :deep(.vue-flow__handle.failure-handle) {
        background: #f56c6c !important;
        right: 10px !important;
        left: auto !important;
        transform: none !important;
    }

    :deep(.vue-flow__handle.failure-handle:hover) {
        border-color: #ffffff !important;
        box-shadow: 0 0 8px rgba(245, 108, 108, 0.8) !important;
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

    :deep(.vue-flow) {
        background-color: var(--el-bg-color-page);
        z-index: 2;
    }

    :deep(.vue-flow__controls) {
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
    }

    :deep(.vue-flow__controls-button) {
        background: var(--el-fill-color-blank);
        border-bottom: 1px solid var(--el-border-color-light);
        color: var(--el-text-color-primary);
    }

    :deep(.vue-flow__minimap) {
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
    }
</style>