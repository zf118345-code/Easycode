// canvasRouter.js
// Production-grade orthogonal router for node-to-node edges.
// Design principles:
//   1. Port stubs — 连线从端口沿所在边的法线先垂直行驶 1 格（20px），进入终点时同样垂直进入。
//   2. Obstacle avoidance — stub 之间在网格上做 A* 寻路（曼哈顿最短），任意一段不进入任何节点矩形。
//   3. Grid-aligned — 所有路径点落在网格线上（世界坐标 = CSS px，与节点同坐标系）。
//   4. Fallback — 无路可达（节点围死/网格过大）时回退旧策略折线，边永不消失。
//   5. Parallel edges — 多边平行时对中间段做垂直偏移分离。
//   6. Final path rendered as rounded polyline via getRoundedPathString.

import {
    GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
    getPortPosition, getArrowDirection, getMarkerId
} from './canvasShared'

const STUB_GRIDS = 1               // 出/入端口垂直行驶的格数（= 基础安全间距 1 格）
const ROUND_RADIUS = 8             // 路径圆角半径（仅渲染层视觉，不参与路由判断）
const PARALLEL_STEP = 3            // 平行线最小偏移步长 = LINE_WIDTH(2) + MIN_GAP(1)
const PARALLEL_MAX_OFFSET = 9      // 最大允许偏移 = 道路宽/2(20) - 最小边界距(10) - 线宽/2(1)
const TURN_PENALTY = 0.05          // A* 转弯惩罚（偏好少折弯的最短路径）
const MAX_GRID_CELLS = 250000      // A* 格点上限，超出回退简易折线

const DEFAULT_ROUTE_OFFSET = 50    // legacy 回退路径偏移
const PARALLEL_OFFSET = 20         // legacy 平行偏移（仅回退路径使用）

/**
 * 平行线偏移序列（需求 2.2 / 2.3）：
 *   第 1 条居中（0），后续按 +step / -step / +2step / -2step ... 交替扩展；
 *   偏移量绝对值不得超过 PARALLEL_MAX_OFFSET（9px）——超出即触发停止条件，
 *   该线及后续所有线保持与最近一条线相同的偏移量（重叠）。
 *   线数 5 → [0, +3, -3, +6, -6]；线数 8 → [0,3,-3,6,-6,9,-9,-9]
 */
export function buildParallelOffsets(count, step = PARALLEL_STEP, maxOffset = PARALLEL_MAX_OFFSET) {
    const offsets = [0]
    let k = 1
    while (offsets.length < count) {
        const pos = k * step
        if (pos <= maxOffset) {
            offsets.push(pos)
            if (offsets.length < count) offsets.push(-pos)
        } else {
            const last = offsets[offsets.length - 1]
            while (offsets.length < count) offsets.push(last)
        }
        k++
    }
    return offsets
}

// ---------------------------------------------------------------------------
// Obstacles / stubs
// ---------------------------------------------------------------------------

/** 端口所在边向外法线方向：entry 在左缘（-x），其余端口在右缘（+x） */
function portOutwardDir(portType) {
    return portType === 'entry' ? -1 : 1
}

/** 节点占位矩形（世界坐标，含动态高度） */
function nodeRect(node) {
    const x = node?.position?.x || 0
    const y = node?.position?.y || 0
    const w = node?.size?.w || node?.w || NODE_WIDTH
    const h = node?.size?.h || node?.h || NODE_MIN_HEIGHT
    return { x, y, w, h }
}

function dedupePoints(points) {
    const out = []
    for (const p of points) {
        const last = out[out.length - 1]
        if (!last || Math.abs(p.x - last.x) > 0.5 || Math.abs(p.y - last.y) > 0.5) out.push(p)
    }
    return out
}

/** 压缩共线同向点，减少折线拐点数 */
function compressCollinear(points) {
    if (points.length <= 2) return points
    const out = [points[0]]
    for (let i = 1; i < points.length - 1; i++) {
        const prev = out[out.length - 1]
        const cur = points[i]
        const next = points[i + 1]
        const cross = (cur.x - prev.x) * (next.y - cur.y) - (cur.y - prev.y) * (next.x - cur.x)
        const dot = (cur.x - prev.x) * (next.x - cur.x) + (cur.y - prev.y) * (next.y - cur.y)
        if (Math.abs(cross) < 1e-9 && dot >= -1e-9) continue
        out.push(cur)
    }
    out.push(points[points.length - 1])
    return out
}

// ---------------------------------------------------------------------------
// Grid A* (lattice points)
// ---------------------------------------------------------------------------

class MinHeap {
    constructor() { this.arr = [] }
    get size() { return this.arr.length }
    push(item) {
        const a = this.arr
        a.push(item)
        let i = a.length - 1
        while (i > 0) {
            const p = (i - 1) >> 1
            if (a[p].f <= a[i].f) break
            ;[a[p], a[i]] = [a[i], a[p]]
            i = p
        }
    }
    pop() {
        const a = this.arr
        const top = a[0]
        const last = a.pop()
        if (a.length) {
            a[0] = last
            let i = 0
            for (;;) {
                const l = i * 2 + 1
                const r = l + 1
                let m = i
                if (l < a.length && a[l].f < a[m].f) m = l
                if (r < a.length && a[r].f < a[m].f) m = r
                if (m === i) break
                ;[a[m], a[i]] = [a[i], a[m]]
                i = m
            }
        }
        return top
    }
}

/**
 * 网格 A* 正交寻路：从 start 到 end 的曼哈顿最短路径，避开所有障碍矩形。
 * 路径点落在网格线上；格点严格落在障碍矩形（可外扩 margin）内部时视为阻塞（起点/终点强制可达）。
 * @param {{x:number,y:number}} start / end  世界坐标（网格对齐）
 * @param {Array<{x,y,w,h}>} obstacleRects   障碍节点矩形
 * @param {{grid?:number, margin?:number}} options  margin：障碍外扩（平行边平移后仍保持间距）
 * @returns {Array<{x,y}>|null}  路径点序列（首=start、尾=end）；无路或网格过大返回 null
 */
export function routeOrthogonal(start, end, obstacleRects = [], options = {}) {
    const grid = options.grid || GRID_SIZE
    const margin = options.margin || 0
    const gx0 = Math.round(start.x / grid)
    const gy0 = Math.round(start.y / grid)
    const gx1 = Math.round(end.x / grid)
    const gy1 = Math.round(end.y / grid)

    if (Math.abs(gx0 - gx1) + Math.abs(gy0 - gy1) <= 1) {
        return [{ ...start }, { ...end }]
    }

    const pad = 2
    let minX = Math.min(gx0, gx1) - pad
    let maxX = Math.max(gx0, gx1) + pad
    let minY = Math.min(gy0, gy1) - pad
    let maxY = Math.max(gy0, gy1) + pad
    for (const r of obstacleRects) {
        minX = Math.min(minX, Math.floor((r.x - margin) / grid) - pad)
        maxX = Math.max(maxX, Math.ceil((r.x + r.w + margin) / grid) + pad)
        minY = Math.min(minY, Math.floor((r.y - margin) / grid) - pad)
        maxY = Math.max(maxY, Math.ceil((r.y + r.h + margin) / grid) + pad)
    }

    const cols = maxX - minX + 1
    const rows = maxY - minY + 1
    if (cols * rows > MAX_GRID_CELLS) return null

    const toIndex = (x, y) => (y - minY) * cols + (x - minX)
    const toCoord = (idx) => ({ x: minX + (idx % cols), y: minY + Math.floor(idx / cols) })

    const rects = obstacleRects.map(r => ({
        x: r.x - margin, y: r.y - margin,
        x2: r.x + r.w + margin, y2: r.y + r.h + margin
    }))
    const blocked = new Uint8Array(cols * rows)
    for (let y = minY; y <= maxY; y++) {
        for (let x = minX; x <= maxX; x++) {
            const wx = x * grid
            const wy = y * grid
            for (const r of rects) {
                if (wx > r.x && wx < r.x2 && wy > r.y && wy < r.y2) {
                    blocked[toIndex(x, y)] = 1
                    break
                }
            }
        }
    }

    const startIdx = toIndex(gx0, gy0)
    const goalIdx = toIndex(gx1, gy1)
    blocked[startIdx] = 0
    blocked[goalIdx] = 0

    const gScore = new Float64Array(cols * rows).fill(Infinity)
    const parent = new Int32Array(cols * rows).fill(-1)
    const closed = new Uint8Array(cols * rows)
    gScore[startIdx] = 0

    const open = new MinHeap()
    open.push({ idx: startIdx, f: Math.abs(gx1 - gx0) + Math.abs(gy1 - gy0), dir: 0 })

    const DIRS = [[1, 0, 1], [-1, 0, 2], [0, 1, 3], [0, -1, 4]]

    let found = false
    while (open.size) {
        const cur = open.pop()
        if (closed[cur.idx]) continue
        closed[cur.idx] = 1
        if (cur.idx === goalIdx) { found = true; break }

        const c = toCoord(cur.idx)
        for (const [dx, dy, dirCode] of DIRS) {
            const nx = c.x + dx
            const ny = c.y + dy
            if (nx < minX || nx > maxX || ny < minY || ny > maxY) continue
            const nIdx = toIndex(nx, ny)
            if (blocked[nIdx] || closed[nIdx]) continue
            const turnPenalty = cur.dir && cur.dir !== dirCode ? TURN_PENALTY : 0
            const ng = gScore[cur.idx] + 1 + turnPenalty
            if (ng < gScore[nIdx]) {
                gScore[nIdx] = ng
                parent[nIdx] = cur.idx
                const h = Math.abs(gx1 - nx) + Math.abs(gy1 - ny)
                open.push({ idx: nIdx, f: ng + h, dir: dirCode })
            }
        }
    }

    if (!found) return null

    const pathIdx = []
    let cur = goalIdx
    while (cur !== -1) {
        pathIdx.push(cur)
        if (cur === startIdx) break
        cur = parent[cur]
    }
    pathIdx.reverse()

    const worldPoints = pathIdx.map(i => {
        const c = toCoord(i)
        return { x: c.x * grid, y: c.y * grid }
    })

    // 首末点替换为实际 start/end 坐标（非网格对齐的 margin 偏移量，
    // 如 stub 28px 会被 round 吸附到 20px 格点，必须还原）。
    // exitPt/enterPt 与各自格点只差 x 方向偏移，替换后路径保持轴对齐。
    worldPoints[0] = { ...start }
    worldPoints[worldPoints.length - 1] = { ...end }

    return compressCollinear(worldPoints)
}

// ---------------------------------------------------------------------------
// Router entrypoint
// ---------------------------------------------------------------------------

/**
 * Compute an obstacle-avoiding orthogonal path for an edge between two nodes.
 * @param sourceNode / targetNode  渲染节点（含最新 position / size，动态高度）
 * @param allNodes  全部渲染节点（作为障碍矩形）
 * @param sourcePort 'success'|'failure'|'branch_N'|'exit_N'|'entry'
 * @param options { offsetIndex, totalParallel }  平行边偏移（拓扑多边）
 */
export function computeEdgePath(sourceNode, targetNode, allNodes, sourcePort = 'success', options = {}) {
    const { offsetIndex = 0, totalParallel = 1 } = options

    const startPt = getPortPosition(sourceNode, sourcePort, options)
    const endPt = getPortPosition(targetNode, 'entry', options)

    if (Math.abs(endPt.x - startPt.x) < 3 && Math.abs(endPt.y - startPt.y) < 3) {
        return finalize([startPt, endPt], sourcePort)
    }

    // 平行线偏移（需求 2）：按序列 [0, +step, -step, +2step, -2step, ...] 取第 offsetIndex 条，
    // |偏移| ≤ PARALLEL_MAX_OFFSET（9px），超出停止扩展（后续线重叠）
    const parallelShift = totalParallel > 1
        ? buildParallelOffsets(totalParallel)[Math.min(offsetIndex, totalParallel - 1)]
        : 0

    // 基础安全间距（需求 1）：路由障碍恒外扩 1 格（20px），不因圆角/平行偏移放大；
    // 圆角渲染只影响视觉，不参与路由判断——路由层只保证原始正交拐点 ≥20px。
    // 平行偏移允许借用安全间距（偏移后线边缘 ≥10px，由 PARALLEL_MAX_OFFSET 保证）。
    const srcDir = portOutwardDir(sourcePort)
    const exitPt = { x: startPt.x + srcDir * STUB_GRIDS * GRID_SIZE, y: startPt.y }
    const enterPt = { x: endPt.x - STUB_GRIDS * GRID_SIZE, y: endPt.y }

    const obstacles = (allNodes || []).map(nodeRect)

    const midPoints = routeOrthogonal(exitPt, enterPt, obstacles, { grid: GRID_SIZE, margin: GRID_SIZE })

    if (!midPoints) {
        // 无路可达 / 网格过大：回退旧策略折线，保证边永不消失
        return legacyComputeEdgePath(startPt, endPt, sourcePort, offsetIndex, totalParallel)
    }

    let points = dedupePoints([startPt, ...midPoints, endPt])

    if (parallelShift !== 0) {
        points = dedupePoints(offsetRoutedPath(points, parallelShift))
    }

    return finalize(points, sourcePort)
}

/**
 * 平行线分离（需求 2.4）：中间段整体偏移，方向由走廊主导方向决定——
 *   横走廊（水平段主导）→ 垂直方向（Y 轴）偏移；
 *   纵走廊（垂直段主导）→ 水平方向（X 轴）偏移。
 * 在 stub 列上加正交连接段，保证首尾仍从原端口引出/进入。
 */
function offsetRoutedPath(points, shift) {
    // points = [startPt, exitPt, ...route 内部点..., enterPt, endPt]
    if (!shift || points.length < 4) return points
    const startPt = points[0]
    const exitPt = points[1]
    const enterPt = points[points.length - 2]
    const endPt = points[points.length - 1]
    const interior = points.slice(2, points.length - 2)

    // 走廊主导方向：统计 exitPt→enterPt 之间所有段（含连接段）的水平/垂直长度
    let horizLen = 0
    let vertLen = 0
    let prev = exitPt
    for (const p of [...interior, enterPt]) {
        if (Math.abs(p.x - prev.x) > Math.abs(p.y - prev.y)) {
            horizLen += Math.abs(p.x - prev.x)
        } else {
            vertLen += Math.abs(p.y - prev.y)
        }
        prev = p
    }
    const isHorizontal = horizLen >= vertLen

    if (!interior.length) {
        // 直线短路由（exit 与 enter 直接相连）：在 stub 列间加分离段
        if (Math.abs(exitPt.x - enterPt.x) + Math.abs(exitPt.y - enterPt.y) > 0) {
            if (isHorizontal) {
                return [
                    startPt,
                    exitPt,
                    { x: exitPt.x, y: exitPt.y + shift },
                    { x: enterPt.x, y: enterPt.y + shift },
                    enterPt,
                    endPt
                ]
            }
            return [
                startPt,
                exitPt,
                { x: exitPt.x + shift, y: exitPt.y },
                { x: enterPt.x + shift, y: enterPt.y },
                enterPt,
                endPt
            ]
        }
        return points
    }

    if (isHorizontal) {
        const shifted = interior.map(p => ({ x: p.x, y: p.y + shift }))
        return [
            startPt,
            exitPt,
            { x: exitPt.x, y: exitPt.y + shift },
            ...shifted,
            { x: enterPt.x, y: enterPt.y + shift },
            enterPt,
            endPt
        ]
    }
    const shifted = interior.map(p => ({ x: p.x + shift, y: p.y }))
    return [
        startPt,
        exitPt,
        { x: exitPt.x + shift, y: exitPt.y },
        ...shifted,
        { x: enterPt.x + shift, y: enterPt.y },
        enterPt,
        endPt
    ]
}

function finalize(points, sourcePort) {
    const pathD = getRoundedPathString(points, ROUND_RADIUS)
    const arrowDir = getArrowDirection(points)
    const markerId = getMarkerId(sourcePort, arrowDir)
    return { pathD, arrowDir, markerId, points }
}

// ---------------------------------------------------------------------------
// Legacy strategy path (fallback when A* fails)
// ---------------------------------------------------------------------------

function legacyComputeEdgePath(startPt, endPt, sourcePort, offsetIndex = 0, totalParallel = 1) {
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

function selectStrategy(sourcePort, srcPt, tgtPt) {
    const dx = tgtPt.x - srcPt.x
    const dy = tgtPt.y - srcPt.y

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
// Preview path (used during drag-to-connect; 瞬时反馈不做逐帧避障)
// ---------------------------------------------------------------------------

export function getSimpleOrthoPath(start, end, sourcePort = 'success') {
    const dx = end.x - start.x
    const dy = end.y - start.y
    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    if (absDx < 4 && absDy < 4) {
        return `M ${start.x} ${start.y} L ${end.x} ${end.y}`
    }

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

export { GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT }
