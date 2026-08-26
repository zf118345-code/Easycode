import { describe, expect, it } from 'vitest'
import {
    BLOCK_GAP,
    BLOCK_MIN_HEIGHT,
    BLOCK_MIN_WIDTH,
    canPlaceBlock,
    containedNodeIds,
    resizeBlockFromHandle
} from '@/utils/canvasBlocks'
import { autoLayoutGraphGeometry } from '@/utils/autoLayout'

const block = (overrides = {}) => ({
    block_id: 'block_a',
    name: '阶段 A',
    x: 0,
    y: 0,
    width: 400,
    height: 260,
    ...overrides
})

const node = (node_id, x, y, w = 160, h = 96) => ({
    node_id,
    position: { x, y },
    size: { w, h }
})

describe('geometric canvas blocks', () => {
    it('only owns nodes fully inside the content territory', () => {
        const nodes = [
            node('inside', 40, 70),
            node('touching-title', 40, 30),
            node('partly-outside', 280, 70),
            node('between-blocks', 390, 70)
        ]
        expect(containedNodeIds(block(), nodes)).toEqual(['inside'])
    })

    it('enforces one grid gap and minimum resize dimensions', () => {
        const existing = [block()]
        expect(canPlaceBlock(block({ block_id: 'block_b', x: 400 + BLOCK_GAP, y: 0 }), existing)).toBe(true)
        expect(canPlaceBlock(block({ block_id: 'block_b', x: 400, y: 0 }), existing)).toBe(false)

        const resized = resizeBlockFromHandle(block(), 'nw', 1000, 1000)
        expect(resized.width).toBe(BLOCK_MIN_WIDTH)
        expect(resized.height).toBe(BLOCK_MIN_HEIGHT)
    })

    it('moves blocks as rigid units while preserving member offsets', () => {
        const graph = {
            nodes: [node('first', 40, 70), node('second', 220, 120), node('loose', 700, 40)],
            edges: [],
            blocks: [block({ x: 300, y: 300 })]
        }
        graph.nodes[0].position = { x: 340, y: 370 }
        graph.nodes[1].position = { x: 520, y: 420 }
        const before = {
            x: graph.nodes[1].position.x - graph.nodes[0].position.x,
            y: graph.nodes[1].position.y - graph.nodes[0].position.y
        }

        const laidOut = autoLayoutGraphGeometry(graph, { scope: 'whole', rowLimit: 1600 })
        const first = laidOut.nodes.find(item => item.node_id === 'first')
        const second = laidOut.nodes.find(item => item.node_id === 'second')
        expect(second.position.x - first.position.x).toBe(before.x)
        expect(second.position.y - first.position.y).toBe(before.y)
        expect(laidOut.blocks[0]).toMatchObject({ x: 80, y: 80 })
    })
})
