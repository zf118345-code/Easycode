// src/utils/workflowRouter.js
import PF from 'pathfinding'

/**
 * 完美的网格化正交路由引擎 (严格遵循端口固定与网格折线对齐)
 * @param {Object} sourceNode 源节点 { position: {x, y} }
 * @param {Object} targetNode 目标节点 { position: {x, y} }
 * @param {Array} allNodes 所有节点（用于网格障碍物避让）
 * @param {String} portType 'succ' (成功->底部) 或 'fail' (失败->右侧)
 */
export function getGridOrthogonalRoute(sourceNode, targetNode, allNodes = [], portType = 'succ') {
    // 定义你的网格单位大小（可以根据你的节点卡片尺寸调整，比如节点宽160高80，网格单位设为 40px 或 80px）
    const GRID_SIZE = 40

    // 换算成网格坐标系下的辅助函数
    const toGrid = (val) => Math.round(val / GRID_SIZE)
    const toPixel = (val) => val * GRID_SIZE

    const mapMinX = -50, mapMinY = -50
    const mapWidth = 200
    const mapHeight = 200

    const grid = new PF.Grid(mapWidth, mapHeight)

    // 1. 将所有节点及其周围的安全距离（Padding）标记为网格障碍物
    const PADDING_GRIDS = 1 // 环绕四周的一圈安全网格距离
    allNodes.forEach(node => {
        if (node.node_id === sourceNode.node_id && node.node_id === targetNode.node_id) return

        const xGrids = toGrid(node.position.x)
        const yGrids = toGrid(node.position.y)
        const wGrids = Math.round(160 / GRID_SIZE) // 节点固定宽度 160
        const hGrids = Math.round(80 / GRID_SIZE)  // 节点固定高度 80

        for (let gx = xGrids - PADDING_GRIDS; gx <= xGrids + wGrids + PADDING_GRIDS; gx++) {
            for (let gy = yGrids - PADDING_GRIDS; gy <= yGrids + hGrids + PADDING_GRIDS; gy++) {
                const realX = gx - mapMinX
                const realY = gy - mapMinY
                if (realX >= 0 && realX < mapWidth && realY >= 0 && realY < mapHeight) {
                    grid.setWalkableAt(realX, realY, false)
                }
            }
        }
    })

    // 2. 根据你的规则确定起终点位置
    // 源节点出口：succ(成功)在底部中心，fail(失败)在右侧中心
    const sBox = { x: sourceNode.position.x, y: sourceNode.position.y, w: 160, h: 80 }
    const tBox = { x: targetNode.position.x, y: targetNode.position.y, w: 160, h: 80 }

    let startPixelX, startPixelY
    if (portType === 'succ') {
        startPixelX = sBox.x + sBox.w / 2 // 底部中心
        startPixelY = sBox.y + sBox.h
    } else {
        startPixelX = sBox.x + sBox.w    // 右侧中心
        startPixelY = sBox.y + sBox.h / 2
    }

    // 目标节点入口：统一规定在顶部中心
    const endPixelX = tBox.x + tBox.w / 2
    const endPixelY = tBox.y

    const startGX = toGrid(startPixelX) - mapMinX
    const startGY = toGrid(startPixelY) - mapMinY
    const endGX = toGrid(endPixelX) - mapMinX
    const endGY = toGrid(endPixelY) - mapMinY

    // 确保起终点网格可通行
    if (startGX >= 0 && startGX < mapWidth && startGY >= 0 && startGY < mapHeight) {
        grid.setWalkableAt(startGX, startGY, true)
    }
    if (endGX >= 0 && endGX < mapWidth && endGY >= 0 && endGY < mapHeight) {
        grid.setWalkableAt(endGX, endGY, true)
    }

    // 3. 使用 A* 寻找纯正交的网格路径
    const finder = new PF.AStarFinder({
        allowDiagonal: false, // 绝对禁止斜线，只允许沿着网格线水平/垂直走
        dontCrossCorners: true
    })

    const path = finder.findPath(startGX, startGY, endGX, endGY, grid.clone())

    if (path && path.length > 0) {
        // 将网格还原为真实像素坐标
        let rawPoints = path.map(p => ({
            x: toPixel(p[0] + mapMinX),
            y: toPixel(p[1] + mapMinY)
        }))

        // 强行修正起点和终点，使其精准对齐到卡片边缘的连接桩像素
        rawPoints[0] = { x: startPixelX, y: startPixelY }
        rawPoints[rawPoints.length - 1] = { x: endPixelX, y: endPixelY }

        // 共线简化（将同一条直线上的中间点抹掉，只留拐角）
        let simplifiedPts = [rawPoints[0]]
        for (let i = 1; i < rawPoints.length - 1; i++) {
            const prev = simplifiedPts[simplifiedPts.length - 1]
            const curr = rawPoints[i]
            const next = rawPoints[i + 1]
            const isCollinear = (curr.x === prev.x && curr.x === next.x) || (curr.y === prev.y && curr.y === next.y)
            if (!isCollinear) {
                simplifiedPts.push(curr)
            }
        }
        simplifiedPts.push(rawPoints[rawPoints.length - 1])

        // 组装 SVG path
        let pathStr = `M ${simplifiedPts[0].x} ${simplifiedPts[0].y}`
        for (let i = 1; i < simplifiedPts.length; i++) {
            pathStr += ` L ${simplifiedPts[i].x} ${simplifiedPts[i].y}`
        }

        return {
            startPt: simplifiedPts[0],
            endPt: simplifiedPts[simplifiedPts.length - 1],
            pathStr
        }
    }

    // 兜底直线
    return {
        startPt: { x: startPixelX, y: startPixelY },
        endPt: { x: endPixelX, y: endPixelY },
        pathStr: `M ${startPixelX} ${startPixelY} L ${endPixelX} ${endPixelY}`
    }
}