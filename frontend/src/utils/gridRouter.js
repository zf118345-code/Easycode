// frontend/src/utils/gridRouter.js
import PF from 'pathfinding'

export class GridWorkflowRouter {
    constructor(gridSize = 20) {
        this.GRID_SIZE = gridSize
    }

    toGridCoord(pixelX, pixelY) {
        return {
            x: Math.round(pixelX / this.GRID_SIZE),
            y: Math.round(pixelY / this.GRID_SIZE)
        }
    }

    toPixelCoord(gridX, gridY) {
        return {
            x: gridX * this.GRID_SIZE,
            y: gridY * this.GRID_SIZE
        }
    }

    getNodeCornerGrids(node) {
        const w = node.w || 160
        const h = node.h || 80
        const x = node.position?.x || 0
        const y = node.position?.y || 0

        return {
            topLeft: this.toGridCoord(x, y),
            topRight: this.toGridCoord(x + w, y),
            bottomLeft: this.toGridCoord(x, y + h),
            bottomRight: this.toGridCoord(x + w, y + h)
        }
    }

    route(sourceNode, targetNode, allNodes = [], portType = 'succ', enableSimplify = true) {
        const sSize = { w: sourceNode.w || 160, h: sourceNode.h || 80 }
        const tSize = { w: targetNode.w || 160, h: targetNode.h || 80 }

        const mapWidth = 300
        const mapHeight = 300
        const gridCols = mapWidth
        const gridRows = mapHeight
        const gridOffsetX = 150
        const gridOffsetY = 150

        const grid = new PF.Grid(gridCols, gridRows)

        // 1. 节点建筑物设为不可通行
        allNodes.forEach(n => {
            const x = n.position?.x || 0
            const y = n.position?.y || 0
            const w = n.w || 160
            const h = n.h || 80

            const gStart = this.toGridCoord(x, y)
            const gEnd = this.toGridCoord(x + w, y + h)

            const minGX = Math.max(0, gStart.x + gridOffsetX)
            const maxGX = Math.min(gridCols - 1, gEnd.x + gridOffsetX)
            const minGY = Math.max(0, gStart.y + gridOffsetY)
            const maxGY = Math.min(gridRows - 1, gEnd.y + gridOffsetY)

            for (let gx = minGX; gx <= maxGX; gx++) {
                for (let gy = minGY; gy <= maxGY; gy++) {
                    grid.setWalkableAt(gx, gy, false)
                }
            }
        })

        // 2. ⚡ 精准计算不同端口类型的起止像素桩
        let startPixelPt = { x: 0, y: 0 }

        if (portType === 'succ') {
            startPixelPt = { x: sourceNode.position.x + sSize.w / 2, y: sourceNode.position.y + sSize.h }
        } else if (portType.startsWith('branch_')) {
            // ⚡ 核心修正：锁定 CSS 真实卡片高度与边距（卡片顶边距 8 + 头部 16 + 容器边距 4 + 列表边距 2 + 单项中心 12 = 42px，单项步长 28px）
            const cIdx = parseInt(portType.split('_')[1]) || 0
            const exactOffsetY = 42 + cIdx * 28
            startPixelPt = { x: sourceNode.position.x + sSize.w, y: sourceNode.position.y + exactOffsetY }
        } else {
            // ⚡ 核心修正：Branch 节点的 Else 兜底红点在右下方（bottom: 12px），中心 Y 轴为 h - 18px
            const isBranchNode = sourceNode.node_type === 'branch'
            const exactOffsetY = isBranchNode ? (sSize.h - 18) : (sSize.h / 2)
            startPixelPt = { x: sourceNode.position.x + sSize.w, y: sourceNode.position.y + exactOffsetY }
        }

        const endPixelPt = {
            x: targetNode.position.x + tSize.w / 2,
            y: targetNode.position.y
        }

        let stubStart = { ...startPixelPt }
        if (portType === 'succ') {
            stubStart.y += this.GRID_SIZE
        } else {
            // 所有右侧导出的端口，初始向右向外延伸一个网格
            stubStart.x += this.GRID_SIZE
        }

        let stubEnd = {
            x: endPixelPt.x,
            y: endPixelPt.y - this.GRID_SIZE
        }

        const makeWalkable = (pt) => {
            const g = this.toGridCoord(pt.x, pt.y)
            const gx = g.x + gridOffsetX
            const gy = g.y + gridOffsetY
            if (gx >= 0 && gx < gridCols && gy >= 0 && gy < gridRows) {
                grid.setWalkableAt(gx, gy, true)
            }
        }
        makeWalkable(startPixelPt)
        makeWalkable(stubStart)
        makeWalkable(stubEnd)
        makeWalkable(endPixelPt)

        const startG = this.toGridCoord(stubStart.x, stubStart.y)
        const endG = this.toGridCoord(stubEnd.x, stubEnd.y)

        const sX = Math.min(Math.max(startG.x + gridOffsetX, 0), gridCols - 1)
        const sY = Math.min(Math.max(startG.y + gridOffsetY, 0), gridRows - 1)
        const eX = Math.min(Math.max(endG.x + gridOffsetX, 0), gridCols - 1)
        const eY = Math.min(Math.max(endG.y + gridOffsetY, 0), gridRows - 1)

        const finder = new PF.AStarFinder({
            allowDiagonal: false,
            dontCrossCorners: true
        })

        const path = finder.findPath(sX, sY, eX, eY, grid.clone())
        let simplifiedPts = []

        if (path && path.length > 0) {
            let rawPoints = path.map(p => this.toPixelCoord(p[0] - gridOffsetX, p[1] - gridOffsetY))

            rawPoints = [
                startPixelPt,
                stubStart,
                ...rawPoints,
                stubEnd,
                endPixelPt
            ]

            let orthogonalPts = [rawPoints[0]]
            for (let i = 1; i < rawPoints.length; i++) {
                const prev = orthogonalPts[orthogonalPts.length - 1]
                const curr = rawPoints[i]

                if (prev.x !== curr.x && prev.y !== curr.y) {
                    orthogonalPts.push({ x: curr.x, y: prev.y })
                }
                orthogonalPts.push(curr)
            }

            simplifiedPts = [orthogonalPts[0]]
            for (let i = 1; i < orthogonalPts.length - 1; i++) {
                const prev = simplifiedPts[simplifiedPts.length - 1]
                const curr = orthogonalPts[i]
                const next = orthogonalPts[i + 1]
                const isCollinear = (curr.x === prev.x && curr.x === next.x) || (curr.y === prev.y && curr.y === next.y)
                if (!isCollinear) {
                    simplifiedPts.push(curr)
                }
            }
            simplifiedPts.push(orthogonalPts[orthogonalPts.length - 1])

        } else {
            const midY = (startPixelPt.y + endPixelPt.y) / 2
            simplifiedPts = [
                startPixelPt,
                stubStart,
                { x: stubStart.x, y: midY },
                { x: endPixelPt.x, y: midY },
                stubEnd,
                endPixelPt
            ]
        }

        const gridPoints = simplifiedPts.map(pt => this.toGridCoord(pt.x, pt.y))
        const rawPixelPoints = simplifiedPts.map(pt => ({ x: pt.x, y: pt.y }))

        let pathStr = `M ${simplifiedPts[0].x} ${simplifiedPts[0].y}`
        for (let i = 1; i < simplifiedPts.length; i++) {
            pathStr += ` L ${simplifiedPts[i].x} ${simplifiedPts[i].y}`
        }

        let arrowDir = 'down'
        if (rawPixelPoints && rawPixelPoints.length >= 2) {
            let p1 = rawPixelPoints[rawPixelPoints.length - 2]
            let p2 = rawPixelPoints[rawPixelPoints.length - 1]

            for (let i = rawPixelPoints.length - 1; i > 0; i--) {
                if (rawPixelPoints[i].x !== rawPixelPoints[i - 1].x || rawPixelPoints[i].y !== rawPixelPoints[i - 1].y) {
                    p2 = rawPixelPoints[i]
                    p1 = rawPixelPoints[i - 1]
                    break
                }
            }

            const dx = p2.x - p1.x
            const dy = p2.y - p1.y

            if (Math.abs(dx) >= Math.abs(dy)) {
                arrowDir = dx > 0 ? 'right' : 'left'
            } else {
                arrowDir = dy > 0 ? 'down' : 'up'
            }
        }

        return {
            startPt: simplifiedPts[0],
            endPt: simplifiedPts[simplifiedPts.length - 1],
            pathStr,
            gridPoints,
            rawPixelPoints,
            arrowDir
        }
    }
}

export const router = new GridWorkflowRouter(20)