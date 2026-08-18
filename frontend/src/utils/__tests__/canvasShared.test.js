import { describe, it, expect } from 'vitest'
import {
    GRID_SIZE,
    getNodePortTop,
    getPortPosition,
    computeCanvasNodeHeight,
    PORT_GRID_TOP,
    PORT_GRID_BOTTOM,
    PORT_GRID_STEP
} from '../canvasShared'

function makeNode({ h = 100, dynamicCount = 0 } = {}) {
    return {
        position: { x: 80, y: 40 },
        w: 160,
        h,
        size: { w: 160, h },
        ports: {
            success: { visible: true, connected: false },
            failure: { visible: true, connected: false },
            dynamic: Array.from({ length: dynamicCount }, (_, i) => ({ name: `branch_${i}`, label: `分支 ${i + 1}`, connected: false }))
        }
    }
}

describe('canvasShared 网格化端口布局', () => {
    it('entry 位于左缘距顶 1 格', () => {
        const node = makeNode({ h: 100 })
        expect(getNodePortTop(node, 'entry')).toBe(PORT_GRID_TOP * GRID_SIZE)
        const pos = getPortPosition(node, 'entry')
        expect(pos).toEqual({ x: 80, y: 40 + PORT_GRID_TOP * GRID_SIZE })
    })

    it('success 位于右缘距顶 1 格', () => {
        const node = makeNode({ h: 100 })
        expect(getNodePortTop(node, 'success')).toBe(PORT_GRID_TOP * GRID_SIZE)
        const pos = getPortPosition(node, 'succ')
        expect(pos).toEqual({ x: 80 + 160, y: 40 + PORT_GRID_TOP * GRID_SIZE })
    })

    it('failure 位于右缘距底 1 格（随节点最新高度联动）', () => {
        const node = makeNode({ h: 140 })
        expect(getNodePortTop(node, 'failure')).toBe(140 - PORT_GRID_BOTTOM * GRID_SIZE)
        const pos = getPortPosition(node, 'fail')
        expect(pos.x).toBe(80 + 160)
        expect(pos.y).toBe(40 + 140 - PORT_GRID_BOTTOM * GRID_SIZE)
    })

    it('动态端口行对齐：branch_N / exit_N 位于对应行垂直中心', () => {
        const node = makeNode({ h: 200, dynamicCount: 3 })
        // 行中心 = 头部32 + 内容区起始6 + N×行距28 + 半行12
        for (let k = 0; k < 3; k++) {
            const expectedTop = 32 + 6 + k * 28 + 12
            expect(getNodePortTop(node, `branch_${k}`)).toBe(expectedTop)
            expect(getNodePortTop(node, `exit_${k}`)).toBe(expectedTop)
        }
        const pos = getPortPosition(node, 'exit_1')
        expect(pos.x).toBe(80 + 160)
        expect(pos.y).toBe(40 + 32 + 6 + 28 + 12)
    })

    it('页面节点卡片仅展示出口行（无特征摘要行偏移）', () => {
        const node = {
            ...makeNode({ h: 200 }),
            node_type: 'page_state',
            params: { features: [{ condition_type: 'image_exists' }], feature_mode: 'or' }
        }
        expect(getNodePortTop(node, 'exit_0')).toBe(50)
        expect(getNodePortTop(node, 'exit_1')).toBe(50 + 28)
    })

    it('动态端口越界时向底部 clamp（不超过 failure 之上）', () => {
        const node = makeNode({ h: 100, dynamicCount: 5 })
        const top = getNodePortTop(node, 'branch_4')
        expect(top).toBeLessThanOrEqual(100 - PORT_GRID_BOTTOM * GRID_SIZE)
        expect(top).toBe(100 - PORT_GRID_BOTTOM * GRID_SIZE - 4)
    })

    it('exit / exit_0 视为第一个动态端口（行对齐起点）', () => {
        const node = makeNode({ h: 100 })
        expect(getNodePortTop(node, 'exit')).toBe(50)
        expect(getNodePortTop(node, 'exit_0')).toBe(50)
    })

    it('computeCanvasNodeHeight 无内容时最小 3 格（头部32+footer24 向上取整 = 60px）', () => {
        const h = computeCanvasNodeHeight(0, 0)
        expect(h).toBe(60)
        expect(h % GRID_SIZE).toBe(0)
    })

    it('computeCanvasNodeHeight 随动态端口数增长（每端口 +2 格）', () => {
        expect(computeCanvasNodeHeight(0, 0)).toBe(60)
        expect(computeCanvasNodeHeight(0, 1)).toBe(100)
        expect(computeCanvasNodeHeight(0, 2)).toBe(140)
        expect(computeCanvasNodeHeight(0, 3)).toBe(180)
    })

    it('computeCanvasNodeHeight 动态端口数无上限（严格随内容增长）', () => {
        const h12 = computeCanvasNodeHeight(0, 12)
        expect(h12).toBe(540)   // 56 + max(0, 40*12+4) = 540
        expect(h12 % GRID_SIZE).toBe(0)
    })

    it('computeCanvasNodeHeight 内容高度参与计算（内容多的节点更高）', () => {
        const empty = computeCanvasNodeHeight(0, 0)
        const image = computeCanvasNodeHeight(120, 0)
        expect(image).toBeGreaterThan(empty)
        expect(image % GRID_SIZE).toBe(0)
        expect(image).toBe(180)  // ceil((32+120+24)/20)*20
    })

    it('computeCanvasNodeHeight 内容与端口预留取较大者（端口永不重叠）', () => {
        // 1 个候选（内容 36px）vs 2 个动态端口的预留 84px → 取 84
        expect(computeCanvasNodeHeight(36, 2)).toBe(140)
        // 内容 200px 压过 1 个端口的预留 44px → 取 200
        expect(computeCanvasNodeHeight(200, 1)).toBe(260)
    })
})
