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

    it('failure 位于右缘距底 1 格', () => {
        const node = makeNode({ h: 140 })
        expect(getNodePortTop(node, 'failure')).toBe(140 - PORT_GRID_BOTTOM * GRID_SIZE)
        const pos = getPortPosition(node, 'fail')
        expect(pos.x).toBe(80 + 160)
        expect(pos.y).toBe(40 + 140 - PORT_GRID_BOTTOM * GRID_SIZE)
    })

    it('动态端口从 success 下方每隔 1 格排列', () => {
        const node = makeNode({ h: 200, dynamicCount: 3 })
        for (let k = 0; k < 3; k++) {
            const expectedTop = (PORT_GRID_TOP + PORT_GRID_STEP * (k + 1)) * GRID_SIZE
            expect(getNodePortTop(node, `branch_${k}`)).toBe(expectedTop)
            expect(getNodePortTop(node, `exit_${k}`)).toBe(expectedTop)
        }
        const pos = getPortPosition(node, 'exit_1')
        expect(pos.x).toBe(80 + 160)
        expect(pos.y).toBe(40 + (PORT_GRID_TOP + PORT_GRID_STEP * 2) * GRID_SIZE)
    })

    it('动态端口越界时向底部 clamp（不超过 failure 之上）', () => {
        const node = makeNode({ h: 100, dynamicCount: 5 })
        const top = getNodePortTop(node, 'branch_4')
        expect(top).toBeLessThanOrEqual(100 - PORT_GRID_BOTTOM * GRID_SIZE)
        expect(top).toBe(100 - PORT_GRID_BOTTOM * GRID_SIZE)
    })

    it('exit / exit_0 视为第一个动态端口', () => {
        const node = makeNode({ h: 100 })
        expect(getNodePortTop(node, 'exit')).toBe((PORT_GRID_TOP + PORT_GRID_STEP) * GRID_SIZE)
        expect(getNodePortTop(node, 'exit_0')).toBe((PORT_GRID_TOP + PORT_GRID_STEP) * GRID_SIZE)
    })

    it('computeCanvasNodeHeight 最小 5 格且吸附网格', () => {
        const h = computeCanvasNodeHeight(40, 0)
        expect(h).toBeGreaterThanOrEqual(100)
        expect(h % GRID_SIZE).toBe(0)
    })

    it('computeCanvasNodeHeight 随动态端口数增长（每端口 1 格）', () => {
        const h0 = computeCanvasNodeHeight(40, 0)
        const h3 = computeCanvasNodeHeight(40, 3)
        expect(h3 - h0).toBe(3 * GRID_SIZE)
    })

    it('computeCanvasNodeHeight 动态端口超上限时封顶增长', () => {
        const h10 = computeCanvasNodeHeight(40, 10)
        const h12 = computeCanvasNodeHeight(40, 12)
        expect(h12).toBe(h10)
    })

    it('computeCanvasNodeHeight 内容高度参与计算（图片节点更高）', () => {
        const normal = computeCanvasNodeHeight(40, 0)
        const image = computeCanvasNodeHeight(120, 0)
        expect(image).toBeGreaterThan(normal)
        expect(image % GRID_SIZE).toBe(0)
    })
})
