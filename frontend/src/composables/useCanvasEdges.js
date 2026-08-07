import { computed } from 'vue'
import { router } from '@/utils/gridRouter'
import { getRoundedPathString } from '@/utils/pathSmooth'

export function useCanvasEdges(renderNodes, draggingNodeId, hasMoved, selectedEdgeId, drawingConnection) {
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
            if (node.on_success?.target_node) {
                const target = allNodes.find(n => n.node_id === node.on_success.target_node)
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

            if (node.on_failure?.target_node) {
                const target = allNodes.find(n => n.node_id === node.on_failure.target_node)
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

    return {
        computedEdges
    }
}