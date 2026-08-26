export const MAIN_GRAPH_ID = 'main'
export const SYSTEM_EXCEPTION_OUTCOME_ID = 'system_exception'

export function createMainGraph() {
    return { graph_id: MAIN_GRAPH_ID, nodes: [], edges: [] }
}

export function createPageMap() {
    return { schema_version: 3, nodes: [], edges: [] }
}

export function createStableId(prefix) {
    return `${prefix}_${globalThis.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now()}${Math.random().toString(16).slice(2)}`}`
}

export function createFunctionDefinition(name = '新建函数', folderId = null) {
    const functionId = createStableId('function')
    const entryId = createStableId('node')
    const returnId = createStableId('node')
    const successId = createStableId('outcome')
    return {
        function_id: functionId,
        name,
        description: '',
        folder_id: folderId,
        parameters: [],
        local_variables: [],
        outputs: [],
        outcomes: [
            { outcome_id: successId, name: '成功', color: 'success' },
            { outcome_id: SYSTEM_EXCEPTION_OUTCOME_ID, name: '异常', color: 'danger', system: true, immutable: true }
        ],
        test_cases: [],
        graph: {
            graph_id: functionId,
            entry_node_id: entryId,
            nodes: [
                { node_id: entryId, node_name: '函数入口', node_type: 'function_entry', params: {}, delay_before: 0, loop_count: 1, enabled: true, fixed: true, position: { x: 80, y: 160 }, size: { w: 180, h: 84 } },
                { node_id: returnId, node_name: '返回成功', node_type: 'function_return', params: { outcome_id: successId, output_bindings: [] }, delay_before: 0, loop_count: 1, enabled: true, position: { x: 420, y: 160 }, size: { w: 180, h: 92 } }
            ],
            edges: []
        }
    }
}

export function getFunction(functions, functionId) {
    return (functions || []).find(item => item?.function_id === functionId) || null
}

export function getGraph(blueprint, graphId = MAIN_GRAPH_ID, canvasMode = 'workflow') {
    if (canvasMode === 'topology') return blueprint?.page_map || null
    if (graphId === MAIN_GRAPH_ID) return blueprint?.main_graph || null
    return getFunction(blueprint?.functions, graphId)?.graph || null
}

export function getGraphLabel(blueprint, graphId = MAIN_GRAPH_ID) {
    if (graphId === MAIN_GRAPH_ID) return '主流程'
    return getFunction(blueprint?.functions, graphId)?.name || graphId
}

export function collectFunctionReferences(blueprint, targetFunctionId = '') {
    const owners = [
        { graphId: MAIN_GRAPH_ID, graph: blueprint?.main_graph },
        ...(blueprint?.functions || []).map(item => ({ graphId: item.function_id, graph: item.graph }))
    ]
    const references = []
    for (const owner of owners) {
        for (const node of owner.graph?.nodes || []) {
            if (node?.node_type !== 'call_function') continue
            const target = String(node.params?.function_id || '').trim()
            if (targetFunctionId && target !== targetFunctionId) continue
            references.push({ ownerGraphId: owner.graphId, nodeId: node.node_id, targetFunctionId: target })
        }
    }
    return references
}
