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

function fullyContained(block, node) {
    const x = Number(node.position?.x || 0)
    const y = Number(node.position?.y || 0)
    const width = Number(node.size?.w || 160)
    const height = Number(node.size?.h || 96)
    const left = Number(block.x || 0) + 20
    const top = Number(block.y || 0) + 52
    const right = Number(block.x || 0) + Number(block.width || 200) - 20
    const bottom = Number(block.y || 0) + Number(block.height || 160) - 20
    return x >= left && y >= top && x + width <= right && y + height <= bottom
}

/**
 * Block-aware layout. Blocks are rigid geometry units: their internal nodes keep
 * their exact relative positions. Only uncontained nodes are graph-laid out.
 */
export function autoLayoutGraphGeometry(graph, options = {}) {
    const nodes = clone(graph?.nodes || [])
    const edges = clone(graph?.edges || [])
    const blocks = clone(graph?.blocks || [])
    if (!blocks.length) {
        return { nodes: autoLayoutTasks([{ task_id: 'graph', nodes }], edges, options)[0].nodes, blocks }
    }

    const contained = new Set()
    const membersByBlock = new Map()
    for (const block of blocks) {
        const members = nodes.filter(node => fullyContained(block, node))
        membersByBlock.set(block.block_id, members)
        members.forEach(node => contained.add(node.node_id))
    }

    if ((options.scope || 'whole') === 'whole') {
        let cursorX = 80
        let cursorY = 80
        let rowHeight = 0
        const rowLimit = Math.max(900, Number(options.rowLimit || 1600))
        for (const block of blocks) {
            const width = Number(block.width || 400)
            const height = Number(block.height || 260)
            if (cursorX > 80 && cursorX + width > rowLimit) {
                cursorX = 80
                cursorY += rowHeight + 80
                rowHeight = 0
            }
            const dx = cursorX - Number(block.x || 0)
            const dy = cursorY - Number(block.y || 0)
            block.x = cursorX
            block.y = cursorY
            for (const node of membersByBlock.get(block.block_id) || []) {
                node.position = { x: Number(node.position?.x || 0) + dx, y: Number(node.position?.y || 0) + dy }
            }
            cursorX += width + 80
            rowHeight = Math.max(rowHeight, height)
        }
        const looseNodes = nodes.filter(node => !contained.has(node.node_id))
        layoutNodeSet(looseNodes, edges, { x: 80, y: cursorY + rowHeight + 100 })
    } else {
        const selected = new Set(options.selectedNodeIds || [])
        const looseSelection = nodes.filter(node => selected.has(node.node_id) && !contained.has(node.node_id))
        if (looseSelection.length) {
            layoutNodeSet(looseSelection, edges, {
                x: Math.min(...looseSelection.map(node => node.position?.x ?? 80)),
                y: Math.min(...looseSelection.map(node => node.position?.y ?? 80))
            })
        }
    }
    return { nodes, blocks }
}
