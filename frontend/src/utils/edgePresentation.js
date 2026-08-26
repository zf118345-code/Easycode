import { GRID_SIZE, getRoundedPathString } from './canvasRouter'

const DEFAULT_LANE_SPACING = 4
const DEFAULT_JUMP_RADIUS = 6

function clonePoint(point) {
    return { x: Number(point?.x || 0), y: Number(point?.y || 0) }
}

function dedupePoints(points) {
    const output = []
    for (const point of points || []) {
        const normalized = clonePoint(point)
        const last = output[output.length - 1]
        if (!last || last.x !== normalized.x || last.y !== normalized.y) output.push(normalized)
    }
    return output
}

function compressCollinear(points) {
    const list = dedupePoints(points)
    if (list.length <= 2) return list
    const output = [list[0]]
    for (let index = 1; index < list.length - 1; index += 1) {
        const previous = output[output.length - 1]
        const current = list[index]
        const next = list[index + 1]
        const sameX = previous.x === current.x && current.x === next.x
        const sameY = previous.y === current.y && current.y === next.y
        if (!sameX && !sameY) output.push(current)
    }
    output.push(list[list.length - 1])
    return output
}

export function pointsToSegments(points, edgeId = '') {
    const list = dedupePoints(points)
    const segments = []
    for (let index = 0; index < list.length - 1; index += 1) {
        const start = list[index]
        const end = list[index + 1]
        const horizontal = start.y === end.y
        const vertical = start.x === end.x
        if (!horizontal && !vertical) continue
        segments.push({
            edgeId,
            index,
            start,
            end,
            orientation: horizontal ? 'h' : 'v',
            axis: horizontal ? start.y : start.x,
            min: horizontal ? Math.min(start.x, end.x) : Math.min(start.y, end.y),
            max: horizontal ? Math.max(start.x, end.x) : Math.max(start.y, end.y),
            length: horizontal ? Math.abs(end.x - start.x) : Math.abs(end.y - start.y)
        })
    }
    return segments
}

function laneOffsetForIndex(index, spacing) {
    if (index === 0) return 0
    const distance = Math.ceil(index / 2) * spacing
    return index % 2 ? -distance : distance
}

function buildLaneAdjustedPoints(points, offsets) {
    const source = dedupePoints(points)
    const segments = pointsToSegments(source)
    if (!segments.length) return source
    const shifted = segments.map((segment, index) => {
        // The first and last segment stay anchored to the real ports.
        const offset = index === 0 || index === segments.length - 1
            ? 0
            : Number(offsets.get(segment.index) || 0)
        if (segment.orientation === 'h') {
            return {
                ...segment,
                start: { x: segment.start.x, y: segment.start.y + offset },
                end: { x: segment.end.x, y: segment.end.y + offset }
            }
        }
        return {
            ...segment,
            start: { x: segment.start.x + offset, y: segment.start.y },
            end: { x: segment.end.x + offset, y: segment.end.y }
        }
    })

    const output = [clonePoint(shifted[0].start)]
    for (let index = 0; index < shifted.length; index += 1) {
        const segment = shifted[index]
        const last = output[output.length - 1]
        if (last.x !== segment.start.x || last.y !== segment.start.y) {
            if (last.x !== segment.start.x && last.y !== segment.start.y) {
                const previous = shifted[index - 1]
                const corner = previous?.orientation === 'h'
                    ? { x: segment.start.x, y: last.y }
                    : { x: last.x, y: segment.start.y }
                output.push(corner)
            }
            output.push(clonePoint(segment.start))
        }
        output.push(clonePoint(segment.end))
    }
    return compressCollinear(output)
}

/**
 * Gives collinear, overlapping interior segments deterministic visual lanes.
 * Logical A* points stay untouched; only renderPoints/path are changed.
 */
export function applyMicroLanes(edges, options = {}) {
    const spacing = Number(options.spacing || DEFAULT_LANE_SPACING)
    const minOverlap = Number(options.minOverlap || GRID_SIZE * 2)
    const result = (edges || []).map(edge => ({
        ...edge,
        rawPixelPoints: dedupePoints(edge.rawPixelPoints),
        renderPoints: dedupePoints(edge.rawPixelPoints),
        jumpArcs: []
    }))
    const records = []
    for (const edge of result) {
        const segments = pointsToSegments(edge.rawPixelPoints, edge.id)
        for (const segment of segments) {
            if (segment.index === 0 || segment.index === segments.length - 1) continue
            if (segment.length < minOverlap) continue
            records.push(segment)
        }
    }

    const corridorGroups = new Map()
    records.forEach(record => {
        const key = `${record.orientation}:${record.axis}`
        if (!corridorGroups.has(key)) corridorGroups.set(key, [])
        corridorGroups.get(key).push(record)
    })
    const components = []
    for (const recordsOnAxis of corridorGroups.values()) {
        // Interval sweep: collinear segments form a component when they overlap
        // by at least minOverlap. This remains O(S log S), even for 1000 edges
        // sharing one corridor, instead of comparing every pair.
        recordsOnAxis.sort((a, b) => a.min - b.min || a.max - b.max)
        let component = []
        let farthestEnd = Number.NEGATIVE_INFINITY
        for (const record of recordsOnAxis) {
            if (component.length && record.min > farthestEnd - minOverlap) {
                components.push(component)
                component = []
                farthestEnd = Number.NEGATIVE_INFINITY
            }
            component.push(record)
            farthestEnd = Math.max(farthestEnd, record.max)
        }
        if (component.length) components.push(component)
    }
    const offsetsByEdge = new Map()
    for (const component of components) {
        const edgeIds = [...new Set(component.map(record => record.edgeId))]
            .sort((a, b) => String(a).localeCompare(String(b), 'zh-CN', { numeric: true }))
        if (edgeIds.length < 2) continue
        const laneByEdge = new Map(edgeIds.map((edgeId, index) => [edgeId, laneOffsetForIndex(index, spacing)]))
        for (const record of component) {
            if (!offsetsByEdge.has(record.edgeId)) offsetsByEdge.set(record.edgeId, new Map())
            offsetsByEdge.get(record.edgeId).set(record.index, laneByEdge.get(record.edgeId))
        }
    }

    for (const edge of result) {
        const offsets = offsetsByEdge.get(edge.id) || new Map()
        edge.renderPoints = buildLaneAdjustedPoints(edge.rawPixelPoints, offsets)
        edge.path = getRoundedPathString(edge.renderPoints, 8)
        edge.hasMicroLanes = offsets.size > 0
    }
    return result
}

function isInteriorCrossing(segment, coordinate, margin) {
    return coordinate > segment.min + margin && coordinate < segment.max - margin
}

function buildJumpArc(orientation, x, y, radius) {
    if (orientation === 'h') {
        return {
            gapPath: `M ${x - radius - 2} ${y} L ${x + radius + 2} ${y}`,
            bridgePath: `M ${x - radius} ${y} Q ${x} ${y - radius} ${x + radius} ${y}`
        }
    }
    return {
        gapPath: `M ${x} ${y - radius - 2} L ${x} ${y + radius + 2}`,
        bridgePath: `M ${x} ${y - radius} Q ${x + radius} ${y} ${x} ${y + radius}`
    }
}

/** Adds deterministic bridge metadata at perpendicular non-connected crossings. */
export function applyLineJumps(edges, options = {}) {
    const radius = Number(options.radius || DEFAULT_JUMP_RADIUS)
    const margin = radius + 4
    const bucketSize = Math.max(GRID_SIZE * 4, Number(options.bucketSize || GRID_SIZE * 10))
    const result = (edges || []).map(edge => ({ ...edge, jumpArcs: [] }))
    const edgeById = new Map(result.map(edge => [edge.id, edge]))
    const horizontals = []
    const verticalBuckets = new Map()
    for (const edge of result) {
        for (const segment of pointsToSegments(edge.renderPoints || edge.rawPixelPoints, edge.id)) {
            if (segment.orientation === 'h') {
                horizontals.push(segment)
                continue
            }
            const bucket = Math.floor(segment.axis / bucketSize)
            if (!verticalBuckets.has(bucket)) verticalBuckets.set(bucket, [])
            verticalBuckets.get(bucket).push(segment)
        }
    }
    const seen = new Set()
    for (const horizontal of horizontals) {
        const firstBucket = Math.floor(horizontal.min / bucketSize)
        const lastBucket = Math.floor(horizontal.max / bucketSize)
        for (let bucket = firstBucket; bucket <= lastBucket; bucket += 1) {
            for (const vertical of verticalBuckets.get(bucket) || []) {
                if (horizontal.edgeId === vertical.edgeId) continue
                const x = vertical.axis
                const y = horizontal.axis
                if (!isInteriorCrossing(horizontal, x, margin) || !isInteriorCrossing(vertical, y, margin)) continue
                const horizontalEdge = edgeById.get(horizontal.edgeId)
                const verticalEdge = edgeById.get(vertical.edgeId)
                if (!horizontalEdge || !verticalEdge) continue
                const jumper = String(horizontalEdge.id).localeCompare(String(verticalEdge.id), 'zh-CN', { numeric: true }) >= 0
                    ? horizontalEdge
                    : verticalEdge
                const jumperSegment = jumper.id === horizontal.edgeId ? horizontal : vertical
                const key = `${jumper.id}|${jumperSegment.orientation}|${x}|${y}`
                if (seen.has(key)) continue
                seen.add(key)
                jumper.jumpArcs.push({
                    x,
                    y,
                    orientation: jumperSegment.orientation,
                    ...buildJumpArc(jumperSegment.orientation, x, y, radius)
                })
            }
        }
    }
    return result
}

export function applyEdgeVisualStates(edges, options = {}) {
    const selected = new Set(options.selectedNodeIds || [])
    const hoveredNodeId = options.hoveredNodeId || ''
    const focusIds = selected.size ? selected : new Set(hoveredNodeId ? [hoveredNodeId] : [])
    const focusActive = focusIds.size > 0
    const selectedEdges = new Set(options.selectedEdgeIds || [])
    return (edges || []).map(edge => {
        const sourceFocused = focusIds.has(edge.sourceNodeId)
        const targetFocused = focusIds.has(edge.targetNodeId)
        const internal = focusActive && sourceFocused && targetFocused
        const boundary = focusActive && sourceFocused !== targetFocused
        const dimmed = focusActive && !sourceFocused && !targetFocused
        const executing = !!options.executionRunning
            && options.previousActiveNodeId === edge.sourceNodeId
            && options.currentActiveNodeId === edge.targetNodeId
        return {
            ...edge,
            selected: selectedEdges.has(edge.id),
            focusState: internal ? 'internal' : (boundary ? 'boundary' : (dimmed ? 'dimmed' : 'default')),
            dimmed,
            executing
        }
    })
}

export function normalizeEdgeRouting(routing) {
    const waypoints = Array.isArray(routing?.waypoints)
        ? routing.waypoints
            .filter(point => Number.isFinite(Number(point?.x)) && Number.isFinite(Number(point?.y)))
            .map((point, index) => ({
                id: String(point.id || `waypoint_${index}`),
                x: Math.round(Number(point.x) / GRID_SIZE) * GRID_SIZE,
                y: Math.round(Number(point.y) / GRID_SIZE) * GRID_SIZE
            }))
        : []
    return { mode: waypoints.length ? 'manual' : 'auto', waypoints }
}

function nodeRect(node, margin = GRID_SIZE) {
    const position = node?.position || { x: 0, y: 0 }
    const width = node?.size?.w || node?.w || 160
    const height = node?.size?.h || node?.h || 80
    return {
        left: Number(position.x || 0) - margin,
        top: Number(position.y || 0) - margin,
        right: Number(position.x || 0) + width + margin,
        bottom: Number(position.y || 0) + height + margin
    }
}

function pointInsideAnyNode(point, nodes, margin) {
    return (nodes || []).some(node => {
        const rect = nodeRect(node, margin)
        return point.x > rect.left && point.x < rect.right && point.y > rect.top && point.y < rect.bottom
    })
}

export function findNearestFreeWaypoint(point, nodes, options = {}) {
    const grid = Number(options.grid || GRID_SIZE)
    const margin = Number(options.margin ?? GRID_SIZE)
    const maxRings = Number(options.maxRings || 24)
    const origin = {
        x: Math.round(Number(point?.x || 0) / grid) * grid,
        y: Math.round(Number(point?.y || 0) / grid) * grid
    }
    if (!pointInsideAnyNode(origin, nodes, margin)) return origin
    for (let ring = 1; ring <= maxRings; ring += 1) {
        for (let dx = -ring; dx <= ring; dx += 1) {
            for (const dy of [-ring, ring]) {
                const candidate = { x: origin.x + dx * grid, y: origin.y + dy * grid }
                if (!pointInsideAnyNode(candidate, nodes, margin)) return candidate
            }
        }
        for (let dy = -ring + 1; dy < ring; dy += 1) {
            for (const dx of [-ring, ring]) {
                const candidate = { x: origin.x + dx * grid, y: origin.y + dy * grid }
                if (!pointInsideAnyNode(candidate, nodes, margin)) return candidate
            }
        }
    }
    return null
}

/** Mutates persisted edges and moves/removes waypoints covered by nodes. */
export function reconcileEdgeWaypoints(edges, nodes) {
    let moved = 0
    let removed = 0
    for (const edge of edges || []) {
        const routing = normalizeEdgeRouting(edge.routing)
        if (!routing.waypoints.length) continue
        const next = []
        for (const waypoint of routing.waypoints) {
            const resolved = findNearestFreeWaypoint(waypoint, nodes)
            if (!resolved) {
                removed += 1
                continue
            }
            if (resolved.x !== waypoint.x || resolved.y !== waypoint.y) moved += 1
            next.push({ ...waypoint, ...resolved })
        }
        edge.routing = { mode: next.length ? 'manual' : 'auto', waypoints: next }
    }
    return { moved, removed }
}

export function translateInternalEdgeWaypoints(edges, selectedNodeIds, delta) {
    const selected = new Set(selectedNodeIds || [])
    const dx = Number(delta?.x || 0)
    const dy = Number(delta?.y || 0)
    if ((!dx && !dy) || selected.size < 2) return 0
    let changed = 0
    for (const edge of edges || []) {
        if (!selected.has(edge.source_node) || !selected.has(edge.target_node)) continue
        const routing = normalizeEdgeRouting(edge.routing)
        if (!routing.waypoints.length) continue
        edge.routing = {
            mode: 'manual',
            waypoints: routing.waypoints.map(point => ({ ...point, x: point.x + dx, y: point.y + dy }))
        }
        changed += 1
    }
    return changed
}
