import { describe, expect, it } from 'vitest'
import { buildSubgraphSnapshot, findSelectionPath } from '@/utils/graphSelection'

describe('graphSelection', () => {
    const edges = [
        { edge_id: 'ab', source_node: 'a', target_node: 'b', source_port: 'success' },
        { edge_id: 'bc', source_node: 'b', target_node: 'c', source_port: 'success' },
        { edge_id: 'bd', source_node: 'b', target_node: 'd', source_port: 'failure' }
    ]

    it('selects the connected nodes and edges between an anchor and target', () => {
        expect(findSelectionPath(edges, 'a', 'c')).toEqual({
            nodeIds: ['a', 'b', 'c'],
            edgeIds: ['ab', 'bc']
        })
        expect(findSelectionPath(edges, 'c', 'a')).toEqual({
            nodeIds: ['c', 'b', 'a'],
            edgeIds: ['bc', 'ab']
        })
        expect(findSelectionPath(edges, 'a', 'missing')).toBeNull()
    })

    it('copies only edges whose two endpoints are selected', () => {
        const tasks = [{ task_id: 'task', nodes: [
            { node_id: 'a', node_name: 'A' },
            { node_id: 'b', node_name: 'B' },
            { node_id: 'c', node_name: 'C' }
        ] }]
        const snapshot = buildSubgraphSnapshot(tasks, edges, ['a', 'b', 'd'])
        expect(snapshot.selectionOrder).toEqual(['a', 'b'])
        expect(snapshot.nodes.map(node => node.node_id)).toEqual(['a', 'b'])
        expect(snapshot.edges.map(edge => edge.edge_id)).toEqual(['ab'])
    })
})
