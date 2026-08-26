// frontend/src/composables/useNodeDrag.js
// 节点拖拽 + 网格吸附 + 碰撞推挤
import { ref, reactive } from 'vue'

/**
 * 节点拖拽 composable
 * @param {Object} options
 * @param {import('vue').Ref<{x:number,y:number,zoom:number}>} options.viewport
 * @param {Function} options.getRenderNodes - 返回当前 renderNodes computed 值
 * @param {number} options.GRID_SIZE
 * @param {number} options.NODE_GRID_W
 */
export function useNodeDrag(options) {
    const { viewport, getRenderNodes, GRID_SIZE, NODE_GRID_W } = options

    // 拖拽状态
    const draggingNodeId = ref(null)
    const dragStartMouse = ref({ x: 0, y: 0 })
    const nodeInitialPos = ref({ x: 0, y: 0 })
    const hasMoved = ref(false)
    const isCtrlHeldRef = ref(false)

    // 拖拽预览
    const dragPreviewBox = ref({ visible: false, x: 0, y: 0, w: 0, h: 0, hasCollision: false })

    // 草稿位置（拖拽中暂存）
    const localDraftPositions = reactive({})

    // 框选
    const selectionBox = ref({ visible: false, startX: 0, startY: 0, endX: 0, endY: 0 })

    /**
     * 节点鼠标按下：初始化拖拽状态
     */
    const onNodeMouseDown = (e, node) => {
        isCtrlHeldRef.value = e.ctrlKey
        draggingNodeId.value = node.node_id
        dragStartMouse.value = { x: e.clientX, y: e.clientY }
        nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
        hasMoved.value = false
        e.stopPropagation()
    }

    /**
     * 拖拽移动：更新草稿位置 + 碰撞预览
     */
    const onDragMove = (e) => {
        isCtrlHeldRef.value = e.ctrlKey
        if (!draggingNodeId.value) return

        const dist = Math.hypot(e.clientX - dragStartMouse.value.x, e.clientY - dragStartMouse.value.y)
        if (dist > 6) {
            hasMoved.value = true
        }

        if (!hasMoved.value) return

        const dx = (e.clientX - dragStartMouse.value.x) / viewport.value.zoom
        const dy = (e.clientY - dragStartMouse.value.y) / viewport.value.zoom

        const rawX = nodeInitialPos.value.x + dx
        const rawY = nodeInitialPos.value.y + dy

        localDraftPositions[draggingNodeId.value] = { x: rawX, y: rawY }

        // 碰撞预览
        const MIN_GAP = 2 * GRID_SIZE
        const renderNodes = getRenderNodes()
        const currentDraggingNode = renderNodes.find(n => n.node_id === draggingNodeId.value)
        const nodeW = currentDraggingNode?.w || (NODE_GRID_W * GRID_SIZE)
        const nodeH = currentDraggingNode?.h || 120

        const previewX = rawX - MIN_GAP
        const previewY = rawY - MIN_GAP
        const previewW = nodeW + MIN_GAP * 2
        const previewH = nodeH + MIN_GAP * 2

        let isColliding = false
        const currentBox = { minX: rawX, maxX: rawX + nodeW, minY: rawY, maxY: rawY + nodeH }

        for (const otherNode of renderNodes) {
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

        dragPreviewBox.value = { visible: true, x: previewX, y: previewY, w: previewW, h: previewH, hasCollision: isColliding }
    }

    /**
     * 碰撞推挤：将周围节点推开以避免重叠
     */
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

                        movingNodes.push({ id: other.node_id, pos: nextPos, h: otherSize.h, w: otherSize.w })
                    }
                }
            }
            if (!hasNewCollision) break
        }
        return localDraftPositions[targetNodeId] || dropPos
    }

    /**
     * 重置拖拽状态
     */
    const resetDragState = () => {
        draggingNodeId.value = null
        hasMoved.value = false
        isCtrlHeldRef.value = false
        dragPreviewBox.value.visible = false
    }

    /**
     * 清理草稿位置
     */
    const clearDraft = (nodeId) => {
        delete localDraftPositions[nodeId]
    }

    /**
     * 同步草稿位置到节点
     */
    const syncDraftsToNodes = (tasks) => {
        tasks.forEach(t => {
            (t.nodes || []).forEach(n => {
                if (localDraftPositions[n.node_id]) {
                    n.position = localDraftPositions[n.node_id]
                    delete localDraftPositions[n.node_id]
                }
            })
        })
    }

    return {
        // 状态
        draggingNodeId,
        hasMoved,
        isCtrlHeldRef,
        dragPreviewBox,
        localDraftPositions,
        selectionBox,
        // 方法
        onNodeMouseDown,
        onDragMove,
        resolveCollisionsAndPushOthers,
        resetDragState,
        clearDraft,
        syncDraftsToNodes,
        // 直接暴露 GRID_SIZE 供外部使用
        GRID_SIZE
    }
}
