// frontend/src/utils/__tests__/canvasAvoidance.test.js
// 新建节点自动避让。
import { describe, it, expect } from 'vitest'
import {
    GRID_SIZE, NODE_WIDTH, NODE_MIN_HEIGHT,
    findFreePosition, isColliding
} from '../canvasShared'

const nodeAt = (x, y, w = NODE_WIDTH, h = NODE_MIN_HEIGHT) => ({ position: { x, y }, size: { w, h } })

describe('findFreePosition 新建节点避让', () => {
    it('无碰撞时保持原位置（网格对齐）', () => {
        const pos = findFreePosition([nodeAt(500, 500)], { x: 100, y: 100 })
        expect(pos).toEqual({ x: 100, y: 100 })
    })

    it('有碰撞时沿右下方向推挤到无碰撞位置', () => {
        // 期望位置与已有节点完全重叠 → 被推开
        const occupied = nodeAt(0, 0)
        const pos = findFreePosition([occupied], { x: 0, y: 0 })
        expect(pos.x).toBeGreaterThanOrEqual(0)
        expect(pos.y).toBeGreaterThanOrEqual(0)
        const collides = isColliding({ position: pos, size: { w: NODE_WIDTH, h: NODE_MIN_HEIGHT } }, occupied)
        expect(collides).toBe(false)  // ⚡ 新位置不再与旧节点重叠
        expect(pos.x % GRID_SIZE).toBe(0)
        expect(pos.y % GRID_SIZE).toBe(0)
    })

    it('多个障碍物：最终位置避开全部', () => {
        const others = [
            nodeAt(0, 0),
            nodeAt(0 + NODE_WIDTH + 40, 0),
            nodeAt(0, 0 + NODE_MIN_HEIGHT + 40),
        ]
        const pos = findFreePosition(others, { x: 0, y: 0 })
        const candidate = { position: pos, size: { w: NODE_WIDTH, h: NODE_MIN_HEIGHT } }
        expect(others.some(o => isColliding(candidate, o))).toBe(false)
    })
})
