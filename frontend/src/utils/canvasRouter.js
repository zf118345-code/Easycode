// canvasRouter.js
// Production-grade orthogonal router for node-to-node edges.
// Design principles (reference: Figma / Miro / n8n / Draw.io):
//   1. Pure geometry — deterministic, smooth, no "flying" lines.
//   2. Routing driven by actual port positions (bottom = success/branch, right = failure, top = entry).
//   3. For each edge, pick a routing strategy based on source port direction and target relative position.
//   4. Routes never self-intersect for a single edge; parallel offsets separate multi-edges.
//   5. Final path is rendered as a smooth rounded polyline (radius 12px) via getRoundedPathString.

import {
    GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
    getPortPosition, getArrowDirection, getMarkerId
} from './canvasShared'

const DEFAULT_ROUTE_OFFSET = 50
const PARALLEL_OFFSET = 20

// ---------------------------------------------------------------------------
// Strategy selection
// ---------------------------------------------------------------------------

function selectStrategy(sourcePort, srcPt, tgtPt) {
    const dx = tgtPt.x - srcPt.x
    const dy = tgtPt.y - srcPt.y

    // Step 4 网格化端口：success/exit_*/branch_*/failure 均位于节点右缘，从右侧引出
    let srcDir = 'right'
    if (sourcePort === 'entry') srcDir = 'up'

    const tgtToRight = dx >= 0
    const tgtBelow = dy >= 0

    if (srcDir === 'down') {
        if (tgtBelow && tgtToRight) return 'Z-right'
        if (tgtBelow && !tgtToRight) return 'Z-left'
        if (!tgtBelow && tgtToRight) return 'S-right-up'
        return 'S-left-up'
    }
    if (srcDir === 'right') {
        if (tgtToRight) return 'Z-right'
        return 'U-turn'
    }
    if (srcDir === 'up') {
        if (!tgtBelow && tgtToRight) return 'S-right-down'
        if (!tgtBelow && !tgtToRight) return 'S-left-down'
        return 'fallback'
    }
    return 'fallback'
}

// ---------------------------------------------------------------------------
// Path builders per strategy
// ---------------------------------------------------------------------------

function buildZRight(src, tgt, offset) {
    const midY = src.y + Math.max(offset, Math.abs(tgt.y - src.y) * 0.4)
    return [src, { x: src.x, y: midY }, { x: tgt.x, y: midY }, tgt]
}

function buildZLeft(src, tgt, offset) {
    const midY = src.y + Math.max(offset, Math.abs(tgt.y - src.y) * 0.4)
    return [src, { x: src.x, y: midY }, { x: tgt.x, y: midY }, tgt]
}

function buildSRightUp(src, tgt, offset) {
    const downY = src.y + offset
    const midX = Math.max(src.x + offset, tgt.x + 30)
    return [src, { x: src.x, y: downY }, { x: midX, y: downY }, { x: midX, y: tgt.y }, tgt]
}

function buildSLeftUp(src, tgt, offset) {
    const downY = src.y + offset
    const midX = Math.min(src.x - offset, tgt.x - 30)
    return [src, { x: src.x, y: downY }, { x: midX, y: downY }, { x: midX, y: tgt.y }, tgt]
}

function buildURight(src, tgt, offset) {
    const midX = src.x + Math.max(offset, Math.abs(tgt.x - src.x) * 0.4)
    return [src, { x: midX, y: src.y }, { x: midX, y: tgt.y }, tgt]
}

function buildUTurn(src, tgt, offset) {
    const bottomY = Math.max(src.y, tgt.y) + offset
    const midX = src.x + offset
    return [src, { x: midX, y: src.y }, { x: midX, y: bottomY }, { x: tgt.x, y: bottomY }, tgt]
}

function buildSRightDown(src, tgt, offset) {
    const upY = src.y - offset
    const midX = Math.max(src.x + offset, tgt.x + 30)
    return [src, { x: src.x, y: upY }, { x: midX, y: upY }, { x: midX, y: tgt.y }, tgt]
}

function buildSLeftDown(src, tgt, offset) {
    const upY = src.y - offset
    const midX = Math.min(src.x - offset, tgt.x - 30)
    return [src, { x: src.x, y: upY }, { x: midX, y: upY }, { x: midX, y: tgt.y }, tgt]
}

function buildFallback(src, tgt, _offset) {
    const midY = (src.y + tgt.y) / 2
    return [src, { x: src.x, y: midY }, { x: tgt.x, y: midY }, tgt]
}

// ---------------------------------------------------------------------------
// Router entrypoint
// ---------------------------------------------------------------------------

/**
 * Compute a clean orthogonal path for an edge between two nodes.
 */
export function computeEdgePath(sourceNode, targetNode, allNodes, sourcePort = 'success', options = {}) {
    const { offsetIndex = 0, totalParallel = 1 } = options

    const startPt = getPortPosition(sourceNode, sourcePort, options)
    const endPt = getPortPosition(targetNode, 'entry', options)

    const absDx = Math.abs(endPt.x - startPt.x)
    const absDy = Math.abs(endPt.y - startPt.y)

    if (absDx < 3 && absDy < 3) {
        const points = [startPt, endPt]
        return finalize(points, sourcePort)
    }

    const offset = DEFAULT_ROUTE_OFFSET + Math.max(0, totalParallel - 1) * 10
    const parallelShift = totalParallel > 1
        ? (offsetIndex - (totalParallel - 1) / 2) * PARALLEL_OFFSET
        : 0

    const strategy = selectStrategy(sourcePort, startPt, endPt)
    let points
    switch (strategy) {
        case 'Z-right':       points = buildZRight(startPt, endPt, offset); break
        case 'Z-left':        points = buildZLeft(startPt, endPt, offset); break
        case 'S-right-up':    points = buildSRightUp(startPt, endPt, offset); break
        case 'S-left-up':     points = buildSLeftUp(startPt, endPt, offset); break
        case 'U-right':       points = buildURight(startPt, endPt, offset); break
        case 'U-turn':        points = buildUTurn(startPt, endPt, offset); break
        case 'S-right-down':  points = buildSRightDown(startPt, endPt, offset); break
        case 'S-left-down':   points = buildSLeftDown(startPt, endPt, offset); break
        default:              points = buildFallback(startPt, endPt, offset)
    }

    if (parallelShift !== 0 && points.length >= 3) {
        points = applyParallelOffset(points, parallelShift)
    }

    return finalize(points, sourcePort)
}

function finalize(points, sourcePort) {
    const pathD = getRoundedPathString(points, 12)
    const arrowDir = getArrowDirection(points)
    const markerId = getMarkerId(sourcePort, arrowDir)
    return { pathD, arrowDir, markerId, points }
}

function applyParallelOffset(points, shift) {
    if (points.length < 3) return points
    const result = [points[0]]
    for (let i = 1; i < points.length - 1; i++) {
        const prev = points[i - 1]
        const curr = points[i]
        const isHoriz = Math.abs(curr.x - prev.x) > Math.abs(curr.y - prev.y)
        if (isHoriz) {
            result.push({ x: curr.x, y: curr.y + shift })
        } else {
            result.push({ x: curr.x + shift, y: curr.y })
        }
    }
    result.push(points[points.length - 1])
    return result
}

// ---------------------------------------------------------------------------
// Rounded polyline (used by edges and preview paths)
// ---------------------------------------------------------------------------

export function getRoundedPathString(points, radius = 12) {
    if (!points || points.length < 2) return ''
    if (points.length === 2) {
        return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
    }

    let path = `M ${points[0].x} ${points[0].y}`

    for (let i = 1; i < points.length - 1; i++) {
        const prev = points[i - 1]
        const curr = points[i]
        const next = points[i + 1]

        const v1x = curr.x - prev.x
        const v1y = curr.y - prev.y
        const v2x = next.x - curr.x
        const v2y = next.y - curr.y

        const v1Len = Math.sqrt(v1x * v1x + v1y * v1y) || 1
        const v2Len = Math.sqrt(v2x * v2x + v2y * v2y) || 1

        const r = Math.min(radius, v1Len / 2, v2Len / 2)
        const p1x = curr.x - (v1x / v1Len) * r
        const p1y = curr.y - (v1y / v1Len) * r
        const p2x = curr.x + (v2x / v2Len) * r
        const p2y = curr.y + (v2y / v2Len) * r

        path += ` L ${p1x} ${p1y}`
        path += ` Q ${curr.x} ${curr.y} ${p2x} ${p2y}`
    }

    const last = points[points.length - 1]
    path += ` L ${last.x} ${last.y}`
    return path
}

// ---------------------------------------------------------------------------
// Preview path (used during drag-to-connect)
// ---------------------------------------------------------------------------

export function getSimpleOrthoPath(start, end, sourcePort = 'success') {
    const dx = end.x - start.x
    const dy = end.y - start.y
    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    if (absDx < 4 && absDy < 4) {
        return `M ${start.x} ${start.y} L ${end.x} ${end.y}`
    }

    // Step 4 网格化端口：success/动态/failure 均从右缘引出；entry 向上
    let srcDir = 'right'
    if (sourcePort === 'entry') srcDir = 'up'

    const offset = 40
    let points

    if (srcDir === 'down') {
        const midY = start.y + Math.max(offset, absDy * 0.3)
        points = [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end]
    } else if (srcDir === 'right') {
        const midX = start.x + Math.max(offset, absDx * 0.3)
        points = [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end]
    } else {
        const midY = start.y - Math.max(offset, absDy * 0.3)
        points = [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end]
    }

    return getRoundedPathString(points, 10)
}

/**
 * Legacy bezier (not used anymore, kept for backward compat).
 */
export function getSimpleBezierPath(start, end) {
    const dx = Math.abs(end.x - start.x)
    const offset = Math.max(40, dx * 0.4)
    return `M ${start.x} ${start.y + offset}, ${end.x} ${end.y - offset}, ${end.x} ${end.y}`
}

export { GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT }
