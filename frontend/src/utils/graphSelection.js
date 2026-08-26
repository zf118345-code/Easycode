function edgeKey(edge) {
    return String(edge?.edge_id || edge?.edgeId || edge?.id || '')
}

function sourceOf(edge) {
    return edge?.source_node || edge?.sourceNodeId || edge?.source || ''
}

function targetOf(edge) {
    return edge?.target_node || edge?.targetNodeId || edge?.target || ''
}

function portOf(edge) {
    return String(edge?.source_port || edge?.sourcePort || '')
}

function findDirectedPath(edges, startNodeId, endNodeId) {
    if (!startNodeId || !endNodeId) return null
    if (startNodeId === endNodeId) return { nodeIds: [startNodeId], edgeIds: [] }

    const outgoing = new Map()
    for (const edge of edges || []) {
        const source = sourceOf(edge)
        const target = targetOf(edge)
        if (!source || !target) continue
        if (!outgoing.has(source)) outgoing.set(source, [])
        outgoing.get(source).push(edge)
    }
    for (const list of outgoing.values()) {
        list.sort((a, b) => {
            const portCompare = portOf(a).localeCompare(portOf(b), 'zh-CN', { numeric: true })
            return portCompare || edgeKey(a).localeCompare(edgeKey(b), 'zh-CN', { numeric: true })
        })
    }

    const queue = [startNodeId]
    const visited = new Set([startNodeId])
    const predecessor = new Map()
    while (queue.length) {
        const current = queue.shift()
        for (const edge of outgoing.get(current) || []) {
            const target = targetOf(edge)
            if (visited.has(target)) continue
            visited.add(target)
            predecessor.set(target, { nodeId: current, edge })
            if (target === endNodeId) {
                const nodeIds = [endNodeId]
                const edgeIds = []
                let cursor = endNodeId
                while (cursor !== startNodeId) {
                    const previous = predecessor.get(cursor)
                    if (!previous) return null
                    nodeIds.push(previous.nodeId)
                    edgeIds.push(edgeKey(previous.edge))
                    cursor = previous.nodeId
                }
                nodeIds.reverse()
                edgeIds.reverse()
                return { nodeIds, edgeIds }
            }
            queue.push(target)
        }
    }
    return null
}

/**
 * File-explorer style Shift selection for a graph. The directed path from
 * anchor to target wins; when only the reverse route exists it is returned
 * in anchor-to-target display order. Unconnected nodes return null.
 */
export function findSelectionPath(edges, anchorNodeId, targetNodeId) {
    const forward = findDirectedPath(edges, anchorNodeId, targetNodeId)
    if (forward) return forward
    const reverse = findDirectedPath(edges, targetNodeId, anchorNodeId)
    if (!reverse) return null
    return {
        nodeIds: [...reverse.nodeIds].reverse(),
        edgeIds: [...reverse.edgeIds].reverse()
    }
}

export function buildSubgraphSnapshot(tasks, edges, selectedNodeIds) {
    const selectionOrder = Array.from(new Set((selectedNodeIds || []).filter(Boolean)))
    const requested = new Set(selectionOrder)
    const nodes = []
    const taskByNode = {}
    for (const task of tasks || []) {
        for (const node of task.nodes || []) {
            if (!requested.has(node.node_id)) continue
            nodes.push(JSON.parse(JSON.stringify(node)))
            taskByNode[node.node_id] = task.task_id
        }
    }
    const selected = new Set(nodes.map(node => node.node_id))
    const internalEdges = (edges || [])
        .filter(edge => selected.has(sourceOf(edge)) && selected.has(targetOf(edge)))
        .map(edge => JSON.parse(JSON.stringify(edge)))
    return {
        version: 1,
        selectionOrder: selectionOrder.filter(id => nodes.some(node => node.node_id === id)),
        nodes,
        edges: internalEdges,
        taskByNode
    }
}

export function hasSnapshotContent(snapshot) {
    return Array.isArray(snapshot?.nodes) && snapshot.nodes.length > 0
}
