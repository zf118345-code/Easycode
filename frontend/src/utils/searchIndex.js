const flattenStrings = (value, output = []) => {
    if (typeof value === 'string') output.push(value)
    else if (Array.isArray(value)) value.forEach(item => flattenStrings(item, output))
    else if (value && typeof value === 'object') Object.values(value).forEach(item => flattenStrings(item, output))
    return output
}

const referenceTokens = (value) => {
    const refs = []
    for (const text of flattenStrings(value)) {
        for (const match of text.matchAll(/\$(var|ctx)(?:\.|\{)([\w.-]+)\}?/g)) {
            refs.push({ kind: 'variable', id: match[2], namespace: match[1] })
        }
    }
    return refs
}

export function buildSearchIndex(blueprint = {}) {
    const records = []
    const searchableTasks = [
        { task: { task_id: 'main', task_name: '主流程', ...(blueprint.main_graph || {}) }, canvas: 'workflow', kind: 'main' },
        ...(blueprint.functions || []).map(fn => ({ task: { task_id: fn.function_id, task_name: fn.name, ...(fn.graph || {}) }, canvas: 'function', kind: 'function' })),
        { task: { task_id: 'page_map', task_name: '页面地图', ...(blueprint.page_map || {}) }, canvas: 'topology', kind: 'page_map' }
    ]
    for (const entry of searchableTasks) {
        const { task, canvas } = entry
        const taskId = task.task_id
        records.push({
            kind: entry.kind, id: taskId, taskId, canvas,
            title: task.task_name || taskId,
                subtitle: [...(task.tags || []), task.description].filter(Boolean).join(' · '),
            references: []
        })
        for (const node of task.nodes || []) {
            const strings = flattenStrings(node.params || {})
            const references = referenceTokens(node.params || {})
            if (node.node_type === 'call_function' && node.params?.function_id) {
                references.push({ kind: 'function', id: node.params.function_id })
            }
            for (const text of strings) {
                const clean = text.replace(/\\/g, '/')
                if (/\.(?:png|jpg|jpeg)$/i.test(clean) || node.node_type?.includes('recognition')) {
                    references.push({ kind: 'template', id: clean.replace(/\.(?:png|jpg|jpeg)$/i, '') })
                }
            }
            records.push({
                kind: canvas === 'topology' ? 'page' : 'node', id: node.node_id, nodeId: node.node_id, taskId, canvas,
                title: node.node_name || node.node_id,
                subtitle: `${task.task_name || taskId} · ${node.node_type || 'unknown'}`,
                searchExtra: strings.join(' '),
                references
            })
        }
    }
    for (const name of Object.keys(blueprint.variables || {})) {
        records.push({ kind: 'variable', id: name, title: name, subtitle: '全局变量', references: [] })
    }
    for (const record of records) {
        record.searchText = [record.kind, record.id, record.title, record.subtitle, record.searchExtra]
            .filter(Boolean).join(' ').toLowerCase()
    }
    return records
}

export function searchIndex(records, query, limit = 80) {
    const terms = String(query || '').trim().toLowerCase().split(/\s+/).filter(Boolean)
    if (!terms.length) return records.slice(0, limit)
    return records
        .map(record => {
            if (!terms.every(term => record.searchText.includes(term))) return null
            const title = record.title.toLowerCase()
            const score = terms.reduce((total, term) => total + (title === term ? 100 : title.startsWith(term) ? 30 : title.includes(term) ? 10 : 1), 0)
            return { ...record, score }
        })
        .filter(Boolean)
        .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title))
        .slice(0, limit)
}

export function findReferences(records, kind, id) {
    return records.filter(record => (record.references || []).some(reference => reference.kind === kind && reference.id === id))
}
