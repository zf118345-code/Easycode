import { describe, it, expect } from 'vitest'
import { computeEdgePath, routeOrthogonal, buildParallelOffsets } from '../canvasRouter'
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
        const result = computeEdgePath(src, tgt, [src, tgt], 'success', {})

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

        const result = computeEdgePath(src, tgt, allNodes, 'success', {})
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

        const result = computeEdgePath(src, tgt, [src, tall, tgt], 'success', {})
        expectSegmentsAvoidRect(result.points, { x: 300, y: 0, w: 160, h: 200 })
    })

    it('无路可达（障碍围死）时回退折线，边永不消失', () => {
        const src = makeNode('src', 0, 0)
        const tgt = makeNode('tgt', 600, 0)
        const wall = makeNode('wall', -1000, -1000, 2600, 2600)

        const result = computeEdgePath(src, tgt, [src, tgt, wall], 'success', {})
        expect(result.pathD).toBeTruthy()
        expect(result.points.length).toBeGreaterThanOrEqual(2)
    })

    it('buildParallelOffsets 偏移序列：居中 + 交替 ±step，超限后重叠', () => {
        expect(buildParallelOffsets(1)).toEqual([0])
        expect(buildParallelOffsets(2)).toEqual([0, 3])
        expect(buildParallelOffsets(3)).toEqual([0, 3, -3])
        expect(buildParallelOffsets(4)).toEqual([0, 3, -3, 6])
        expect(buildParallelOffsets(5)).toEqual([0, 3, -3, 6, -6])
        expect(buildParallelOffsets(7)).toEqual([0, 3, -3, 6, -6, 9, -9])
        // 第 8 条候选 +12 > 9 → 触发停止条件，与最近一条（-9）重叠
        expect(buildParallelOffsets(8)).toEqual([0, 3, -3, 6, -6, 9, -9, -9])
        expect(buildParallelOffsets(12)).toEqual([0, 3, -3, 6, -6, 9, -9, -9, -9, -9, -9, -9])
        // 所有偏移绝对值不得超过 9px
        const offs = buildParallelOffsets(20)
        expect(Math.max(...offs.map(Math.abs))).toBe(9)
    })

    it('水平走廊平行边按 Y 轴错开（序列 [0, +3]）', () => {
        const src = makeNode('src', 0, 0)
        const tgt = makeNode('tgt', 600, 0)
        const allNodes = [src, tgt]

        const edge0 = computeEdgePath(src, tgt, allNodes, 'success', { offsetIndex: 0, totalParallel: 2 })
        const edge1 = computeEdgePath(src, tgt, allNodes, 'success', { offsetIndex: 1, totalParallel: 2 })

        expect(edge0.pathD).not.toBe(edge1.pathD)
        // 第 1 条居中（无偏移），第 2 条 +3px
        expect(edge0.points[2].y).toBe(20)
        expect(edge1.points[2].y).toBe(23)
        // 垂直间距 3px ≥ LINE_WIDTH + MIN_GAP
        expect(edge1.points[2].y - edge0.points[2].y).toBe(3)

        for (const pts of [edge0.points, edge1.points]) {
            expectOrthogonal(pts)
        }
    })

    it('纵走廊（垂直主导段）平行边按 X 轴错开', () => {
        const src = makeNode('src', 0, 0)
        const tgt = makeNode('tgt', 0, 300)
        const allNodes = [src, tgt]

        const edge0 = computeEdgePath(src, tgt, allNodes, 'success', { offsetIndex: 0, totalParallel: 2 })
        const edge1 = computeEdgePath(src, tgt, allNodes, 'success', { offsetIndex: 1, totalParallel: 2 })

        expect(edge0.pathD).not.toBe(edge1.pathD)
        // 中间段为垂直走廊：edge0 无偏移（points[2]=(180,440)）、edge1 X 错开 3px（points[3]=(183,440)）
        expect(edge0.points[2].y).toBe(edge1.points[3].y)
        expect(edge1.points[3].x - edge0.points[2].x).toBe(3)

        for (const pts of [edge0.points, edge1.points]) {
            expectOrthogonal(pts)
        }
    })

    it('平行边偏移后线边缘距节点边界 ≥10px（停止阈值）', () => {
        const src = makeNode('src', 0, 0)
        const mid = makeNode('mid', 300, 0)
        const tgt = makeNode('tgt', 600, 0)
        const allNodes = [src, mid, tgt]
        const rects = allNodes.map(n => ({ x: n.position.x, y: n.position.y, w: n.w, h: n.h }))

        for (const offsetIndex of [0, 1]) {
            const result = computeEdgePath(src, tgt, allNodes, 'success', { offsetIndex, totalParallel: 2 })
            // 偏移后的中间段不得进入节点外扩 10px 后的区域（线边缘 ≥10px）
            expectMiddleSegmentsKeepMargin(result.points, rects, 10)
        }
    })

    it('中间路径段与所有节点保持至少 1 格（20px）间距（基础安全间距）', () => {
        const src = makeNode('src', 0, 0)
        const mid = makeNode('mid', 300, 0)
        const tgt = makeNode('tgt', 600, 0)
        const allNodes = [src, mid, tgt]
        const rects = allNodes.map(n => ({ x: n.position.x, y: n.position.y, w: n.w, h: n.h }))

        const result = computeEdgePath(src, tgt, allNodes, 'success', {})
        const pts = result.points
        // 中间段（跳过首尾 stub 段）不得进入任何节点外扩 20px 后的区域
        expectMiddleSegmentsKeepMargin(pts, rects, GRID_SIZE)
        // 起止 stub 段仍贴端口：起点 = success 端口，第一点 = 端口右移 1 格
        expect(pts[0]).toEqual({ x: 160, y: 20 })
        expect(pts[1].x - pts[0].x).toBe(GRID_SIZE)
        expect(pts[1].y).toBe(20)
    })
})
