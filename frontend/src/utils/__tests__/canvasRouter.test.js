import { describe, it, expect } from 'vitest'
import { computeEdgePath, routeOrthogonal } from '../canvasRouter'
import { GRID_SIZE } from '../canvasShared'

function makeNode(id, x, y, w = 160, h = 100) {
    return {
        node_id: id,
        position: { x, y },
        w,
        h,
        size: { w, h }
    }
}

/** 点是否严格落在矩形内部（不含边界） */
function strictlyInside(p, rect) {
    return p.x > rect.x && p.x < rect.x + rect.w && p.y > rect.y && p.y < rect.y + rect.h
}

/** 折线任意线段不进入矩形内部（采样判断，线段均为轴对齐） */
function expectSegmentsAvoidRect(points, rect) {
    expect(points.length).toBeGreaterThanOrEqual(2)
    for (let i = 0; i < points.length - 1; i++) {
        const a = points[i]
        const b = points[i + 1]
        for (const t of [0.25, 0.5, 0.75]) {
            const p = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
            expect(strictlyInside(p, rect)).toBe(false)
        }
    }
}

/** 中间路径段（跳过首段 stub、末段 enter）与所有节点外扩 margin 后的矩形无交点 */
function expectMiddleSegmentsKeepMargin(points, rects, margin) {
    expect(points.length).toBeGreaterThanOrEqual(4)
    for (let i = 1; i < points.length - 2; i++) {
        const a = points[i]
        const b = points[i + 1]
        for (const t of [0.25, 0.5, 0.75]) {
            const p = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
            for (const r of rects) {
                const xIn = p.x > r.x - margin && p.x < r.x + r.w + margin
                const yIn = p.y > r.y - margin && p.y < r.y + r.h + margin
                expect(xIn && yIn).toBe(false)
            }
        }
    }
}

/** 全程正交（相邻点 x 或 y 相等） */
function expectOrthogonal(points) {
    for (let i = 0; i < points.length - 1; i++) {
        const horiz = points[i + 1].x === points[i].x
        const vert = points[i + 1].y === points[i].y
        expect(horiz || vert).toBe(true)
    }
}

describe('canvasRouter 绕障正交路由', () => {
    it('出端口沿法线垂直行驶 1 格（20px），进端口水平垂直进入', () => {
        const src = makeNode('src', 0, 0)
        const tgt = makeNode('tgt', 300, 0)
        const result = computeEdgePath(src, tgt, [src, tgt], 'success')

        const pts = result.points
        // 起点 = success 端口 (0+160, 0+20)
        expect(pts[0]).toEqual({ x: 160, y: 20 })
        // stub：第二点 = 起点右移 1 格，同 y（垂直引出）
        expect(pts[1].x - pts[0].x).toBe(GRID_SIZE)
        expect(pts[1].y).toBe(20)
        // 终点 = entry 端口 (300, 20)，倒数第二点 = 终点左移 1 格（水平进入）
        expect(pts[pts.length - 1]).toEqual({ x: 300, y: 20 })
        expect(pts[pts.length - 2].x).toBe(300 - GRID_SIZE)
        expect(pts[pts.length - 2].y).toBe(20)
        expect(result.pathD).toBeTruthy()
    })

    it('routeOrthogonal 避开障碍矩形（曼哈顿最短绕行）', () => {
        const obstacle = { x: 300, y: 0, w: 160, h: 100 }
        const points = routeOrthogonal({ x: 180, y: 20 }, { x: 580, y: 20 }, [obstacle])
        expect(points).not.toBeNull()

        // 起点终点不变
        expect(points[0]).toEqual({ x: 180, y: 20 })
        expect(points[points.length - 1]).toEqual({ x: 580, y: 20 })
        // 绕行：所有线段不进入矩形内部，且确实发生了绕行（至少 4 个点）
        expectSegmentsAvoidRect(points, obstacle)
        expect(points.length).toBeGreaterThanOrEqual(4)
    })

    it('两节点之间有障碍节点时路径绕开，任意线段不进入任何节点矩形', () => {
        const src = makeNode('src', 0, 0)
        const mid = makeNode('mid', 300, 0)
        const tgt = makeNode('tgt', 600, 0)
        const allNodes = [src, mid, tgt]

        const result = computeEdgePath(src, tgt, allNodes, 'success')
        const pts = result.points
        expect(result.pathD).toBeTruthy()

        for (const n of allNodes) {
            expectSegmentsAvoidRect(pts, { x: n.position.x, y: n.position.y, w: n.w, h: n.h })
        }
    })

    it('高度动态变化后的节点同样被避开（使用最新尺寸）', () => {
        const src = makeNode('src', 0, 0)
        // 障碍节点更高（动态高度 200px）：直行 y=20 依然被挡
        const tall = makeNode('tall', 300, 0, 160, 200)
        const tgt = makeNode('tgt', 600, 0)

        const result = computeEdgePath(src, tgt, [src, tall, tgt], 'success')
        expectSegmentsAvoidRect(result.points, { x: 300, y: 0, w: 160, h: 200 })
    })

    it('无路可达（障碍围死）时回退折线，边永不消失', () => {
        const src = makeNode('src', 0, 0)
        const tgt = makeNode('tgt', 600, 0)
        const wall = makeNode('wall', -1000, -1000, 2600, 2600)

        const result = computeEdgePath(src, tgt, [src, tgt, wall], 'success')
        expect(result.pathD).toBeTruthy()
        expect(result.points.length).toBeGreaterThanOrEqual(2)
    })

    it('中间路径段与所有节点保持至少 1 格（20px）间距（基础安全间距）', () => {
        const src = makeNode('src', 0, 0)
        const mid = makeNode('mid', 300, 0)
        const tgt = makeNode('tgt', 600, 0)
        const allNodes = [src, mid, tgt]
        const rects = allNodes.map(n => ({ x: n.position.x, y: n.position.y, w: n.w, h: n.h }))

        const result = computeEdgePath(src, tgt, allNodes, 'success')
        const pts = result.points
        // 中间段（跳过首尾 stub 段）不得进入任何节点外扩 20px 后的区域
        expectMiddleSegmentsKeepMargin(pts, rects, GRID_SIZE)
        // 起止 stub 段仍贴端口：起点 = success 端口，第一点 = 端口右移 1 格
        expect(pts[0]).toEqual({ x: 160, y: 20 })
        expect(pts[1].x - pts[0].x).toBe(GRID_SIZE)
        expect(pts[1].y).toBe(20)
    })

    it('路径点全部沿网格（相邻点轴对齐且中间点落在 20px 网格线上）', () => {
        const src = makeNode('src', 0, 0)
        const mid = makeNode('mid', 300, 0)
        const tgt = makeNode('tgt', 600, 0)

        const result = computeEdgePath(src, tgt, [src, mid, tgt], 'success')
        const pts = result.points
        expectOrthogonal(pts)
        // 中间点（不含端口首尾与 stub 出线点）必须落在网格线上
        for (let i = 2; i < pts.length - 2; i++) {
            expect(pts[i].x % GRID_SIZE === 0).toBe(true)
            expect(pts[i].y % GRID_SIZE === 0).toBe(true)
        }
    })
})
