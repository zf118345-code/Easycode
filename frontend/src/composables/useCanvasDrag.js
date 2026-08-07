import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

export function useCanvasDrag(store, renderNodes, dynamicGroups, viewport, GRID_SIZE, NODE_GRID_W, NODE_GRID_H) {
    const localDraftPositions = reactive({})
    const draggingNodeId = ref(null)
    const dragStartMouse = ref({ x: 0, y: 0 })
    const nodeInitialPos = ref({ x: 0, y: 0 })
    const hasMoved = ref(false)
    const isCtrlHeldRef = ref(false)

    const draggedSourceGroupSnapshot = ref(null)
    const ghostPlaceholder = ref(null)
    const dragPreviewBox = ref({ visible: false, x: 0, y: 0, w: 0, h: 0, hasCollision: false })

    const calculateOverlapRatio = (rectA, rectB) => {
        if (!rectA || !rectB) return 0
        const xOverlap = Math.max(0, Math.min(rectA.x + rectA.w, rectB.x + rectB.w) - Math.max(rectA.x, rectB.x))
        const yOverlap = Math.max(0, Math.min(rectA.y + rectA.h, rectB.y + rectB.h) - Math.max(rectA.y, rectB.y))
        const intersectionArea = xOverlap * yOverlap
        const areaA = rectA.w * rectA.h
        if (areaA <= 0) return 0
        return intersectionArea / areaA
    }

    const resolveCollisionsAndPushOthers = (targetNodeId, dropPos, allNodes, nodeSize) => {
        const MIN_GAP = 2 * GRID_SIZE
        const stepW = nodeSize.w + MIN_GAP
        const stepH = nodeSize.h + MIN_GAP

        let movingNodes = [{ id: targetNodeId, pos: { ...dropPos } }]
        localDraftPositions[targetNodeId] = { ...dropPos }

        let maxIterations = 15
        let iteration = 0

        while (iteration < maxIterations) {
            iteration++
            let hasNewCollision = false

            for (let i = 0; i < movingNodes.length; i++) {
                const current = movingNodes[i]
                const currPos = current.pos
                const currSize = nodeSize

                for (const other of allNodes) {
                    if (other.node_id === current.id) continue
                    if (movingNodes.some(m => m.id === other.node_id)) continue
                    if (ghostPlaceholder.value && other.node_id === ghostPlaceholder.value.node_id) continue

                    const otherPos = localDraftPositions[other.node_id] || other.position || { x: 0, y: 0 }
                    const otherSize = { w: other.w || nodeSize.w, h: other.h || nodeSize.h }

                    const isIntersect = !(
                        currPos.x + currSize.w + MIN_GAP <= otherPos.x ||
                        currPos.x >= otherPos.x + otherSize.w + MIN_GAP ||
                        currPos.y + currSize.h + MIN_GAP <= otherPos.y ||
                        currPos.y >= otherPos.y + otherSize.h + MIN_GAP
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
                            nextPos.x = dx > 0 ? currPos.x - stepW : currPos.x + stepW
                        } else {
                            nextPos.y = dy > 0 ? currPos.y - stepH : currPos.y + stepH
                        }

                        nextPos.x = Math.round(nextPos.x / GRID_SIZE) * GRID_SIZE
                        nextPos.y = Math.round(nextPos.y / GRID_SIZE) * GRID_SIZE

                        localDraftPositions[other.node_id] = nextPos
                        other.position = nextPos
                        movingNodes.push({ id: other.node_id, pos: nextPos })
                    }
                }
            }
            if (!hasNewCollision) break
        }
        return localDraftPositions[targetNodeId] || dropPos
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
                            nextBox.x = dx > 0 ? currBox.x + currBox.w + MIN_GROUP_GAP : currBox.x - otherBox.w - MIN_GROUP_GAP
                        } else {
                            nextBox.y = dy > 0 ? currBox.y + currBox.h + MIN_GROUP_GAP : currBox.y - otherBox.h - MIN_GROUP_GAP
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

    const onNodeMouseDown = (e, node) => {
        isCtrlHeldRef.value = e.ctrlKey
        draggedSourceGroupSnapshot.value = null
        ghostPlaceholder.value = null

        ghostPlaceholder.value = {
            node_id: `ghost_${node.node_id}`,
            position: { ...node.position },
            w: NODE_GRID_W * GRID_SIZE,
            h: NODE_GRID_H * GRID_SIZE
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

        draggingNodeId.value = node.node_id
        dragStartMouse.value = { x: e.clientX, y: e.clientY }
        nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
        hasMoved.value = false
        e.stopPropagation()
    }

    return {
        localDraftPositions,
        draggingNodeId,
        dragStartMouse,
        nodeInitialPos,
        hasMoved,
        isCtrlHeldRef,
        draggedSourceGroupSnapshot,
        ghostPlaceholder,
        dragPreviewBox,
        resolveCollisionsAndPushOthers,
        resolveGroupCollisionsAndPushOthers,
        calculateOverlapRatio,
        onNodeMouseDown
    }
}