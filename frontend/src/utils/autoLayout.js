const clone = (value) => JSON.parse(JSON.stringify(value || []))

function layoutNodeSet(nodes, edges, origin = { x: 80, y: 80 }) {
    if (!nodes.length) return
    const ids = new Set(nodes.map(node => node.node_id))
    const outgoing = new Map(nodes.map(node => [node.node_id, []]))
    const indegree = new Map(nodes.map(node => [node.node_id, 0]))
    for (const edge of edges || []) {
        if (!ids.has(edge.source_node) || !ids.has(edge.target_node)) continue
        outgoing.get(edge.source_node).push(edge.target_node)
        indegree.set(edge.target_node, indegree.get(edge.target_node) + 1)
    }
    const queue = nodes.filter(node => indegree.get(node.node_id) === 0).map(node => node.node_id)
    const level = new Map(queue.map(id => [id, 0]))
    const visited = new Set()
    while (queue.length) {
        const current = queue.shift()
        visited.add(current)
        for (const target of outgoing.get(current) || []) {
            level.set(target, Math.max(level.get(target) || 0, (level.get(current) || 0) + 1))
            indegree.set(target, indegree.get(target) - 1)
            if (indegree.get(target) === 0) queue.push(target)
        }
    }
    const fallbackLevel = Math.max(0, ...level.values()) + 1
    nodes.forEach(node => { if (!visited.has(node.node_id)) level.set(node.node_id, fallbackLevel) })
    const rows = new Map()
    for (const node of nodes) {
        const column = level.get(node.node_id) || 0
        const row = rows.get(column) || 0
        node.position = { x: origin.x + column * 240, y: origin.y + row * 120 }
        rows.set(column, row + 1)
    }
}

export function autoLayoutTasks(tasks, edges, options = {}) {
    const next = clone(tasks)
    const scope = options.scope || 'whole'
    const selected = new Set(options.selectedNodeIds || [])
    const currentTaskId = options.currentTaskId
    let groupOffset = 80
    for (const task of next) {
        let nodes = task.nodes || []
        if (scope === 'group' && task.task_id !== currentTaskId) continue
        if (scope === 'selection') nodes = nodes.filter(node => selected.has(node.node_id))
        if (!nodes.length) continue
        const origin = scope === 'whole'
            ? { x: groupOffset, y: 80 }
            : {
                x: Math.min(...nodes.map(node => node.position?.x ?? 80)),
                y: Math.min(...nodes.map(node => node.position?.y ?? 80))
            }
        layoutNodeSet(nodes, edges, origin)
        if (scope === 'whole') {
            groupOffset = Math.max(groupOffset + 360, Math.max(...nodes.map(node => node.position.x)) + 360)
        }
    }
    return next
}

export function autoLayoutGraphGeometry(graph, options = {}) {
    const nodes = clone(graph?.nodes || [])
    const edges = clone(graph?.edges || [])
    const laidOut = autoLayoutTasks([{ task_id: 'graph', nodes }], edges, options)
    return { nodes: laidOut[0]?.nodes || nodes }
}
