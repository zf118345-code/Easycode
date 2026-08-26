// frontend/src/utils/portModel.js
// 节点端口模型纯函数：从「节点 + 当前画布实体边」派生端口列表（可见性 / connected / 虚线占位口）。
// 由 CanvasView.renderNodes 消费，与画布渲染解耦，便于单元测试。
//
// 端口语义（与执行器 source_port 一一对应）：
//   - success / failure : 固定端口（branch 隐藏 success；page_state 两者都隐藏）
//   - branch_N          : branch 候选成功口（N = 候选下标）
//   - exit_N            : page_state 出口口（N = 出口序号，由拓扑边推导）
//   - pending 虚线口    : page_state 尾部占位口（连线后实体化并长出下一个）

/**
 * 解析动态端口名索引：branch_2 → 2、exit_0 → 0；非动态端口名返回 null
 */
export function parseDynamicPortIndex(name) {
    if (typeof name !== 'string') return null
    const m = name.match(/^(?:branch|exit|outcome)_(\d+)$/)
    return m ? parseInt(m[1], 10) : null
}

/**
 * 是否为动态端口名（branch_N / exit_N）
 */
export function isDynamicPortName(name) {
    return parseDynamicPortIndex(name) !== null
}

/**
 * branch 候选 → 动态端口定义（端口数 = 候选数，与候选行一一对应）
 */
export function getDefinedDynamicPorts(node, nodeType) {
    if (nodeType === 'branch') {
        return (node?.params?.candidates || []).map((c, i) => ({
            name: `branch_${i}`,
            label: `分支 ${i + 1}`,
            stableId: c.candidate_id
        }))
    }
    if (nodeType === 'call_function') {
        return (node?._functionOutcomes || []).map((outcome, index) => ({
            name: `outcome_${index}`,
            label: outcome.name || `结果 ${index + 1}`,
            stableId: outcome.outcome_id,
            role: 'outcome',
            color: outcome.color === 'danger' || outcome.outcome_id === 'system_exception' ? 'red' : 'green'
        }))
    }
    return []
}

/**
 * 从当前画布实体边推导 page_state 的出口端口（bound，按 exit_N 序号升序）
 * 端口标签取边的 label（出口名称），缺省回退「出口 N」
 * @returns {Array<{name, label}>}
 */
export function getPageStateExitPorts(node, edges) {
    const list = []
    for (const e of edges || []) {
        if (e.source_node !== node?.node_id) continue
        const port = e.source_port || ''
        const idx = parseDynamicPortIndex(port)
        if (idx !== null && port.startsWith('exit_')) {
            list.push({ name: `exit_${idx}`, label: e.label || `出口 ${idx + 1}`, rawIndex: idx, stableId: e.source_port_id })
        }
    }
    list.sort((a, b) => a.rawIndex - b.rawIndex)
    return list.map(item => ({ name: item.name, label: item.label, stableId: item.stableId }))
}

/**
 * 构建节点端口模型
 * @param {Object} node   扁平节点（含 node_id / node_type / params）
 * @param {Array}  edges  当前画布实体边
 * @param {Array}  failurePortTypes 允许失败口的节点类型白名单
 * @returns {{success:{visible,connected}, failure:{visible,connected}, dynamic:Array}}
 */
export function buildNodePorts(node, edges = [], failurePortTypes = []) {
    const nodeType = node?.type || node?.node_type
    const connectedSet = new Set()
    for (const e of edges || []) {
        if (e.source_node === node?.node_id) {
            connectedSet.add(e.source_port)
            connectedSet.add(e.source_port_id)
        }
    }
    const has = (p) => connectedSet.has(p)

    let dynamic = []
    let successVisible = true

    if (nodeType === 'branch') {
        // 候选命中即成功路径：隐藏 success 口，端口数 = 候选数
        successVisible = false
        dynamic = getDefinedDynamicPorts(node, nodeType)
    } else if (nodeType === 'page_state') {
        // 出口 = 拓扑出边（bound）+ 尾部虚线占位口（pending）
        successVisible = false
        const exits = getPageStateExitPorts(node, edges)
        const maxIdx = exits.length
            ? Math.max(...exits.map(p => parseDynamicPortIndex(p.name) ?? -1))
            : -1
        dynamic = [
            ...exits.map(p => ({ ...p, status: 'bound' })),
            { name: `exit_${maxIdx + 1}`, label: '+ 新出口', status: 'pending' }
        ]
    } else if (nodeType === 'call_function') {
        successVisible = false
        dynamic = getDefinedDynamicPorts(node, nodeType)
    }

    dynamic.sort((a, b) => {
        const ai = parseDynamicPortIndex(a.name) ?? 0
        const bi = parseDynamicPortIndex(b.name) ?? 0
        return ai - bi
    })

    return {
        success: { visible: successVisible, connected: has('success') },
        failure: {
            visible: failurePortTypes.includes(nodeType) || has('failure'),
            connected: has('failure')
        },
        dynamic: dynamic.map(d => ({
            ...d,
            connected: has(d.name) || has(d.stableId)
        }))
    }
}

export const FAILURE_PORT_TYPES = [
    'image_recognition', 'ocr_recognition', 'branch', 'logic_check'
]

/**
 * A single semantic source-port list consumed by the canvas and CaptureHost.
 * stableId 与 branch_N/exit_N 的显示位置分开存储，因此重排不会改变连线身份。
 */
export function getSourcePortDescriptors(node, edges = [], failurePortTypes = FAILURE_PORT_TYPES) {
    if (!node) return []
    const ports = buildNodePorts(node, edges, failurePortTypes)
    const descriptors = []
    if (ports.success.visible) {
        descriptors.push({
            key: 'success', stableId: 'success', role: 'success', label: '成功',
            order: 1, connected: ports.success.connected, color: 'green'
        })
    }
    for (const item of ports.dynamic) {
        if (item.status === 'pending') continue
        const index = (parseDynamicPortIndex(item.name) ?? 0) + 1
        const role = item.role || (item.name.startsWith('branch_') ? 'branch' : item.name.startsWith('exit_') ? 'exit' : 'outcome')
        descriptors.push({
            key: item.name,
            stableId: item.stableId,
            role,
            label: item.label || `${role === 'branch' ? '分支' : role === 'exit' ? '出口' : '结果'} ${index}`,
            order: index,
            connected: Boolean(item.connected),
            color: item.color || 'green'
        })
    }
    if (ports.failure.visible) {
        descriptors.push({
            key: 'failure', stableId: 'failure', role: 'failure', label: '失败',
            order: 1, connected: ports.failure.connected, color: 'red'
        })
    }
    return descriptors
}

export function getPrimarySourcePort(node, edges = []) {
    const nodeType = node?.node_type || node?.type
    if (nodeType === 'page_state') {
        return {
            key: 'exit_0', stableId: `exit_${node?.node_id || 'pending'}_0`,
            role: 'exit', label: '出口 1', order: 1, color: 'green'
        }
    }
    const descriptors = getSourcePortDescriptors(node, edges)
    return descriptors.find(port => port.role !== 'failure') || descriptors[0] || {
        key: 'success', stableId: 'success', role: 'success', label: '成功', order: 1, color: 'green'
    }
}
