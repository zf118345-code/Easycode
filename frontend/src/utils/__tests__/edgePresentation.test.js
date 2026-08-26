import { describe, expect, it } from 'vitest'

import {
    applyEdgeVisualStates,
    applyLineJumps,
    applyMicroLanes,
    normalizeEdgeRouting,
    reconcileEdgeWaypoints,
    translateInternalEdgeWaypoints,
} from '../edgePresentation'

describe('edgePresentation', () => {
    it('选中节点时突出相关边、压低无关边，并且只标记真实执行边', () => {
        const edges = [
            { id: 'ab', sourceNodeId: 'a', targetNodeId: 'b' },
            { id: 'bc', sourceNodeId: 'b', targetNodeId: 'c' },
            { id: 'de', sourceNodeId: 'd', targetNodeId: 'e' },
        ]
        const result = applyEdgeVisualStates(edges, {
            selectedNodeIds: ['a', 'b'],
            previousActiveNodeId: 'b',
            currentActiveNodeId: 'c',
            executionRunning: true,
        })

        expect(result.find(edge => edge.id === 'ab').focusState).toBe('internal')
        expect(result.find(edge => edge.id === 'bc').focusState).toBe('boundary')
        expect(result.find(edge => edge.id === 'de').dimmed).toBe(true)
        expect(result.filter(edge => edge.executing).map(edge => edge.id)).toEqual(['bc'])
    })

    it('为重合的内部通道分配稳定微车道', () => {
        const points = [
            { x: 0, y: 0 }, { x: 20, y: 0 }, { x: 20, y: 80 },
            { x: 200, y: 80 }, { x: 200, y: 0 }, { x: 220, y: 0 },
        ]
        const result = applyMicroLanes([
            { id: 'edge_a', rawPixelPoints: points },
            { id: 'edge_b', rawPixelPoints: points },
        ])

        expect(result.every(edge => edge.hasMicroLanes)).toBe(true)
        expect(result[0].path).not.toBe(result[1].path)
    })

    it('只在垂直交叉处为确定的一条边生成 Line Jump', () => {
        const result = applyLineJumps([
            { id: 'edge_a', renderPoints: [{ x: 0, y: 60 }, { x: 200, y: 60 }] },
            { id: 'edge_b', renderPoints: [{ x: 100, y: 0 }, { x: 100, y: 120 }] },
        ])

        expect(result.find(edge => edge.id === 'edge_a').jumpArcs).toHaveLength(0)
        expect(result.find(edge => edge.id === 'edge_b').jumpArcs).toEqual([
            expect.objectContaining({ x: 100, y: 60, orientation: 'v' }),
        ])
    })

    it('转接点吸附网格、避让节点，并随内部多选整体平移', () => {
        const edges = [{
            edge_id: 'edge_ab', source_node: 'a', target_node: 'b',
            routing: normalizeEdgeRouting({ waypoints: [{ id: 'w1', x: 52, y: 48 }] }),
        }]
        const nodes = [{ node_id: 'obstacle', position: { x: 20, y: 20 }, size: { w: 80, h: 80 } }]
        const repaired = reconcileEdgeWaypoints(edges, nodes)

        expect(repaired.moved).toBe(1)
        expect(edges[0].routing.waypoints[0]).not.toEqual(expect.objectContaining({ x: 60, y: 40 }))
        const before = { ...edges[0].routing.waypoints[0] }
        expect(translateInternalEdgeWaypoints(edges, ['a', 'b'], { x: 40, y: -20 })).toBe(1)
        expect(edges[0].routing.waypoints[0]).toEqual(expect.objectContaining({
            x: before.x + 40,
            y: before.y - 20,
        }))
    })

    it('1000 条稀疏边的微车道与跨线分析保持在交互级预算内', () => {
        const edges = Array.from({ length: 1000 }, (_, index) => {
            const row = index % 100
            const column = Math.floor(index / 100)
            const y = row * 40
            const x = column * 260
            return {
                id: `edge_${index}`,
                rawPixelPoints: [
                    { x, y }, { x: x + 20, y },
                    { x: x + 20, y: y + 20 }, { x: x + 220, y: y + 20 },
                    { x: x + 220, y }, { x: x + 240, y },
                ],
            }
        })

        const started = performance.now()
        const result = applyLineJumps(applyMicroLanes(edges))
        const elapsed = performance.now() - started

        expect(result).toHaveLength(1000)
        // 宽松回归门槛：防止重新退化为全图无条件 O(S²)，不把 CI 当微基准平台。
        expect(elapsed).toBeLessThan(2000)
    })
})
