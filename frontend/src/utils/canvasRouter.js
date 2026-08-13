// canvasRouter.js
// 两全其美的连线路由引擎（零外部依赖）：
// 1. BFS 网格寻路 — 线永远不穿过节点（继承 WorkflowCanvas 的优点）
// 2. 边间距偏移 — 平行线错开，避免重叠（解决 WorkflowCanvas 的缺点）
// 3. 端口感知 — 从精确端口位置出发，到达精确端口位置
// 4. 拖拽降级 — 拖拽时用简化折线，松手后 BFS 重算
// 5. 贝塞尔圆角 — 路径圆角化，视觉柔和
// 两个画布（WorkflowCanvas / TopologyCanvas）共用此模块
// 修复：移除 pathfinding npm 依赖，改用纯 JS BFS 实现

import {
    GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
    getPortPosition, getArrowDirection, getMarkerId
} from './canvasShared'

// BFS 网格参数
const GRID_CELL = GRID_SIZE  // 每格 20px，与画布网格一致
const GRID_PADDING = 200     // 网格边界留白
const GRID_DIM = 600         // 600 * 20 = 12000px 覆盖范围

/**
 * 轻量级 BFS 网格路由器
 * 不依赖任何外部库，纯 JavaScript 实现
 */
export class GridRouter {
    constructor() {
        this.gridW = GRID_DIM
        this.gridH = GRID_DIM
        this.gridOffset = GRID_PADDING
    }

    /**
     * 像素坐标 -> 网格坐标
     */
    toGridCoord(x, y) {
        return {
            gx: Math.floor((x + this.gridOffset) / GRID_CELL),
            gy: Math.floor((y + this.gridOffset) / GRID_CELL)
        }
    }

    /**
     * 网格坐标 -> 像素坐标（格子中心）
     */
    toPixelCoord(gx, gy) {
        return {
            x: gx * GRID_CELL - this.gridOffset + GRID_CELL / 2,
            y: gy * GRID_CELL - this.gridOffset + GRID_CELL / 2
        }
    }

    /**
     * 将节点矩形标记为网格障碍物
     */
    markObstacle(walkable, node) {
        const x = node.position?.x || 0
        const y = node.position?.y || 0
        const w = node.size?.w || NODE_WIDTH
        const h = node.size?.h || NODE_MIN_HEIGHT

        const minGX = Math.max(0, Math.floor((x + this.gridOffset) / GRID_CELL))
        const minGY = Math.max(0, Math.floor((y + this.gridOffset) / GRID_CELL))
        const maxGX = Math.min(this.gridW - 1, Math.floor((x + w + this.gridOffset) / GRID_CELL))
        const maxGY = Math.min(this.gridH - 1, Math.floor((y + h + this.gridOffset) / GRID_CELL))

        for (let gx = minGX; gx <= maxGX; gx++) {
            for (let gy = minGY; gy <= maxGY; gy++) {
                walkable[gy * this.gridW + gx] = false
            }
        }
    }

    /**
     * 在起止点附近清除障碍（确保端口可出发/到达）
     */
    clearAround(walkable, gx, gy, radius = 1) {
        for (let dy = -radius; dy <= radius; dy++) {
            for (let dx = -radius; dx <= radius; dx++) {
                const x = gx + dx
                const y = gy + dy
                if (x >= 0 && x < this.gridW && y >= 0 && y < this.gridH) {
                    walkable[y * this.gridW + x] = true
                }
            }
        }
    }

    /**
     * BFS 寻路核心
     * @returns {Array<[gx, gy]>} 网格路径，或 null
     */
    bfs(walkable, startGX, startGY, endGX, endGY) {
        if (startGX === endGX && startGY === endGY) return [[startGX, startGY]]

        const W = this.gridW
        const visited = new Uint8Array(W * this.gridH)
        const parent = new Int32Array(W * this.gridH).fill(-1)
        const queue = []
        let head = 0

        const startIdx = startGY * W + startGX
        visited[startIdx] = 1
        queue.push(startIdx)

        // 4 方向：右、下、左、上
        const dirs = [[1, 0], [0, 1], [-1, 0], [0, -1]]

        while (head < queue.length) {
            const curIdx = queue[head++]
            const curGX = curIdx % W
            const curGY = Math.floor(curIdx / W)

            if (curGX === endGX && curGY === endGY) {
                // 回溯路径
                const path = []
                let idx = curIdx
                while (idx !== -1) {
                    path.push([idx % W, Math.floor(idx / W)])
                    idx = parent[idx]
                }
                path.reverse()
                return path
            }

            for (const [dx, dy] of dirs) {
                const nx = curGX + dx
                const ny = curGY + dy
                if (nx < 0 || nx >= W || ny < 0 || ny >= this.gridH) continue
                const nIdx = ny * W + nx
                if (visited[nIdx]) continue
                if (!walkable[nIdx]) continue
                visited[nIdx] = 1
                parent[nIdx] = curIdx
                queue.push(nIdx)
            }
        }

        return null
    }

    /**
     * 完整路由：从源端口到目标端口
     * @param {Object} sourceNode
     * @param {Object} targetNode
     * @param {Array} allNodes - 所有节点（障碍物）
     * @param {String} sourcePort - 源端口类型
     * @param {String} targetPort - 目标端口类型
     * @param {Object} options - { offsetIndex, totalParallel, avoidNodes }
     * @returns {Array<{x, y}>} 像素路径点数组
     */
    route(sourceNode, targetNode, allNodes, sourcePort = 'success', targetPort = 'entry', options = {}) {
        const { offsetIndex = 0, totalParallel = 1, avoidNodes = [] } = options

        // 1. 计算起止端口像素位置
        const startPt = getPortPosition(sourceNode, sourcePort, options)
        const endPt = getPortPosition(targetNode, targetPort, options)

        // 边间距偏移：平行边在垂直方向错开
        const offset = totalParallel > 1
            ? (offsetIndex - (totalParallel - 1) / 2) * (GRID_CELL * 0.75)
            : 0

        // 2. 构建可通行网格
        const walkable = new Uint8Array(this.gridW * this.gridH).fill(1)

        // 3. 所有节点设为障碍物（除了源和目标）
        allNodes.forEach(n => {
            if (n === sourceNode || n === targetNode) return
            if (avoidNodes.includes(n.node_id)) return
            this.markObstacle(walkable, n)
        })

        // 4. 转换为网格坐标
        const startGrid = this.toGridCoord(startPt.x, startPt.y)
        const endGrid = this.toGridCoord(endPt.x, endPt.y)

        // 起止点附近清除障碍（确保端口可通行）
        this.clearAround(walkable, startGrid.gx, startGrid.gy, 2)
        this.clearAround(walkable, endGrid.gx, endGrid.gy, 2)

        // 5. BFS 寻路
        let path = this.bfs(walkable, startGrid.gx, startGrid.gy, endGrid.gx, endGrid.gy)

        if (!path || path.length < 2) {
            // BFS 失败，降级为中点折线
            return this.fallbackPath(startPt, endPt, sourcePort)
        }

        // 6. 转换为像素坐标
        const pixelPath = path.map(([gx, gy]) => this.toPixelCoord(gx, gy))

        // 替换首尾为精确端口位置
        pixelPath[0] = startPt
        pixelPath[pixelPath.length - 1] = endPt

        // 7. 正交化 + 去共线点
        const simplified = this.simplifyPath(pixelPath)

        // 8. 应用边间距偏移（在平行段错开）
        const offsetPath = this.applyOffset(simplified, offset, sourcePort, targetPort)

        return offsetPath
    }

    /**
     * 去共线点简化
     */
    simplifyPath(points) {
        if (points.length < 3) return points
        const result = [points[0]]
        for (let i = 1; i < points.length - 1; i++) {
            const prev = points[i - 1]
            const curr = points[i]
            const next = points[i + 1]
            // 如果三点共线，跳过中间点
            const cross = (curr.x - prev.x) * (next.y - curr.y) - (curr.y - prev.y) * (next.x - curr.x)
            if (Math.abs(cross) > 0.01) {
                result.push(curr)
            }
        }
        result.push(points[points.length - 1])
        return result
    }

    /**
     * 应用边间距偏移
     * 在路径的中间段上叠加垂直偏移，使平行线错开
     */
    applyOffset(points, offset, sourcePort, targetPort) {
        if (offset === 0 || points.length < 2) return points

        const result = [...points]
        for (let i = 1; i < result.length - 1; i++) {
            const prev = result[i - 1]
            const curr = result[i]
            const next = result[i + 1]

            // 判断是水平段还是垂直段
            const isHorizontal = Math.abs(curr.x - prev.x) > Math.abs(curr.y - prev.y)
            if (isHorizontal) {
                result[i] = { x: curr.x, y: curr.y + offset }
            } else {
                result[i] = { x: curr.x + offset, y: curr.y }
            }
        }
        return result
    }

    /**
     * 降级路径：中点折线
     */
    fallbackPath(start, end, sourcePort) {
        const isFromBottom = sourcePort === 'success' || sourcePort === 'exit' || sourcePort.startsWith('exit_')
        const isFromRight = sourcePort === 'failure'

        if (isFromRight) {
            const midX = (start.x + end.x) / 2
            return [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end]
        } else if (isFromBottom) {
            const midY = (start.y + end.y) / 2
            return [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end]
        } else {
            const midY = (start.y + end.y) / 2
            return [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end]
        }
    }
}

// 单例路由器（避免每次创建新实例）
const _router = new GridRouter()

/**
 * 路径圆角化
 * 将硬直角折线转为圆角 SVG path 字符串
 */
export function getRoundedPathString(points, radius = 10) {
    if (!points || points.length < 2) return ''
    if (points.length === 2) {
        return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
    }

    let path = `M ${points[0].x} ${points[0].y}`

    for (let i = 1; i < points.length - 1; i++) {
        const prev = points[i - 1]
        const curr = points[i]
        const next = points[i + 1]

        // 计算入射和出射向量
        const v1x = curr.x - prev.x
        const v1y = curr.y - prev.y
        const v2x = next.x - curr.x
        const v2y = next.y - curr.y

        const v1Len = Math.sqrt(v1x * v1x + v1y * v1y) || 1
        const v2Len = Math.sqrt(v2x * v2x + v2y * v2y) || 1

        // 圆角起点和终点
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

/**
 * 简化版贝塞尔路径（拖拽时使用，不走 BFS）
 */
export function getSimpleBezierPath(start, end) {
    const dy = Math.abs(end.y - start.y)
    const dx = Math.abs(end.x - start.x)
    const offset = Math.max(40, dx * 0.4)
    return `M ${start.x} ${start.y} C ${start.x} ${start.y + offset}, ${end.x} ${end.y - offset}, ${end.x} ${end.y}`
}

/**
 * 简化版折线路径（拖拽时使用）
 */
export function getSimpleOrthoPath(start, end, sourcePort = 'success') {
    const isFromBottom = sourcePort === 'success' || sourcePort === 'exit' || sourcePort.startsWith('exit_')
    const isFromRight = sourcePort === 'failure'

    if (isFromRight) {
        const midX = (start.x + end.x) / 2
        return `M ${start.x} ${start.y} L ${midX} ${start.y} L ${midX} ${end.y} L ${end.x} ${end.y}`
    } else if (isFromBottom) {
        const midY = (start.y + end.y) / 2
        return `M ${start.x} ${start.y} L ${start.x} ${midY} L ${end.x} ${midY} L ${end.x} ${end.y}`
    } else {
        const midY = (start.y + end.y) / 2
        return `M ${start.x} ${start.y} L ${start.x} ${midY} L ${end.x} ${midY} L ${end.x} ${end.y}`
    }
}

/**
 * 计算连线的完整 SVG path（BFS 路由 + 圆角化）
 * @param {Object} sourceNode
 * @param {Object} targetNode
 * @param {Array} allNodes
 * @param {String} sourcePort
 * @param {Object} options - { isDragging, offsetIndex, totalParallel }
 * @returns {{ pathD: string, arrowDir: string, markerId: string, points: Array }}
 */
export function computeEdgePath(sourceNode, targetNode, allNodes, sourcePort = 'success', options = {}) {
    const { isDragging = false, offsetIndex = 0, totalParallel = 1 } = options

    const startPt = getPortPosition(sourceNode, sourcePort, options)
    const endPt = getPortPosition(targetNode, 'entry', options)

    let points
    if (isDragging) {
        // 拖拽时用简化折线（不走 BFS，避免每帧寻路卡顿）
        points = _router.fallbackPath(startPt, endPt, sourcePort)
    } else {
        // 静态时走 BFS 寻路
        try {
            points = _router.route(sourceNode, targetNode, allNodes, sourcePort, 'entry', {
                offsetIndex,
                totalParallel
            })
        } catch (e) {
            // 异常时降级
            console.warn('[canvasRouter] BFS 路由失败，降级为折线:', e)
            points = _router.fallbackPath(startPt, endPt, sourcePort)
        }
    }

    // 圆角化
    const pathD = getRoundedPathString(points, 10)

    // 箭头方向
    const arrowDir = getArrowDirection(points)
    const markerId = getMarkerId(sourcePort, arrowDir)

    return { pathD, arrowDir, markerId, points }
}
