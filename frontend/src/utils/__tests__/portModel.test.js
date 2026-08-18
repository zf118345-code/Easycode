import { describe, it, expect } from 'vitest'
import {
    parseDynamicPortIndex,
    isDynamicPortName,
    getDefinedDynamicPorts,
    getPageStateExitPorts,
    buildNodePorts
} from '../portModel'

const FAILURE_TYPES = ['image_recognition', 'ocr_recognition', 'branch', 'logic_check']

function makeNode(nodeType, params = {}, nodeId = 'n1') {
    return { node_id: nodeId, node_type: nodeType, type: nodeType, params }
}

function makeEdges(...list) {
    return list.map((e, i) => ({ edge_id: `e${i}`, canvas: 'topology', ...e }))
}

describe('portModel 端口名解析', () => {
    it('parseDynamicPortIndex 解析 branch_N / exit_N', () => {
        expect(parseDynamicPortIndex('branch_0')).toBe(0)
        expect(parseDynamicPortIndex('exit_2')).toBe(2)
        expect(parseDynamicPortIndex('exit')).toBe(null)
        expect(parseDynamicPortIndex('success')).toBe(null)
        expect(parseDynamicPortIndex('')).toBe(null)
    })

    it('isDynamicPortName 识别动态端口名（含旧 exit 别名）', () => {
        expect(isDynamicPortName('branch_1')).toBe(true)
        expect(isDynamicPortName('exit_0')).toBe(true)
        expect(isDynamicPortName('exit')).toBe(true)
        expect(isDynamicPortName('success')).toBe(false)
        expect(isDynamicPortName('failure')).toBe(false)
    })
})

describe('portModel branch 端口', () => {
    it('2 个候选 → 2 个成功口（branch_0/branch_1）+ 失败口，success 隐藏', () => {
        const node = makeNode('branch', { candidates: [{ condition: {} }, { condition: {} }] })
        const ports = buildNodePorts(node, [], FAILURE_TYPES)
        expect(ports.success.visible).toBe(false)
        expect(ports.failure.visible).toBe(true)
        expect(ports.dynamic.map(p => p.name)).toEqual(['branch_0', 'branch_1'])
        expect(ports.dynamic.every(p => p.status !== 'pending')).toBe(true)
        expect(ports.dynamic.every(p => !p.connected)).toBe(true)
    })

    it('1 个候选 → 1 个成功口', () => {
        const node = makeNode('branch', { candidates: [{ condition: {} }] })
        const ports = buildNodePorts(node, [], FAILURE_TYPES)
        expect(ports.dynamic).toHaveLength(1)
        expect(ports.dynamic[0].name).toBe('branch_0')
    })

    it('候选已连线时端口 connected 状态正确', () => {
        const node = makeNode('branch', { candidates: [{ condition: {} }, { condition: {} }] })
        const edges = makeEdges(
            { source_node: 'n1', source_port: 'branch_1', target_node: 'n2' },
            { source_node: 'n1', source_port: 'failure', target_node: 'n3' }
        )
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic[0].connected).toBe(false)
        expect(ports.dynamic[1].connected).toBe(true)
        expect(ports.failure.connected).toBe(true)
    })
})

describe('portModel page_state 端口（出口 = 拓扑边 + 虚线占位）', () => {
    it('无出口边 → 只有 1 个 pending 虚线占位口，success/failure 均隐藏', () => {
        const node = makeNode('page_state', { page_id: 'p1', features: [], feature_mode: 'and' })
        const ports = buildNodePorts(node, [], FAILURE_TYPES)
        expect(ports.success.visible).toBe(false)
        expect(ports.failure.visible).toBe(false)
        expect(ports.dynamic).toHaveLength(1)
        expect(ports.dynamic[0]).toMatchObject({ name: 'exit_0', status: 'pending' })
        expect(ports.dynamic[0].connected).toBe(false)
    })

    it('1 条出口边 → exit_0 bound + exit_1 pending；标签取边 label', () => {
        const node = makeNode('page_state', { page_id: 'p1' })
        const edges = makeEdges(
            { source_node: 'n1', source_port: 'exit_0', target_node: 'n2', label: '点[商店]' }
        )
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic.map(p => p.name)).toEqual(['exit_0', 'exit_1'])
        expect(ports.dynamic[0]).toMatchObject({ label: '点[商店]', status: 'bound', connected: true })
        expect(ports.dynamic[1]).toMatchObject({ status: 'pending', connected: false })
    })

    it('2 条出口边 → exit_0/exit_1 bound + exit_2 pending（按序号升序）', () => {
        const node = makeNode('page_state', { page_id: 'p1' })
        const edges = makeEdges(
            { source_node: 'n1', source_port: 'exit_1', target_node: 'n3', label: '出口 2' },
            { source_node: 'n1', source_port: 'exit_0', target_node: 'n2', label: '出口 1' }
        )
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic.map(p => p.name)).toEqual(['exit_0', 'exit_1', 'exit_2'])
        expect(ports.dynamic[0].label).toBe('出口 1')
        expect(ports.dynamic[1].label).toBe('出口 2')
        expect(ports.dynamic[2]).toMatchObject({ name: 'exit_2', status: 'pending' })
    })

    it('旧 exit 别名端口归一为 exit_0', () => {
        const node = makeNode('page_state', { page_id: 'p1' })
        const edges = makeEdges({ source_node: 'n1', source_port: 'exit', target_node: 'n2' })
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic.map(p => p.name)).toEqual(['exit_0', 'exit_1'])
        expect(ports.dynamic[0].connected).toBe(true)
    })

    it('缺号出口边（exit_1 无 exit_0）→ bound 保留原序号，pending 取最大序号 + 1', () => {
        const node = makeNode('page_state', { page_id: 'p1' })
        const edges = makeEdges({ source_node: 'n1', source_port: 'exit_1', target_node: 'n2' })
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic.map(p => p.name)).toEqual(['exit_1', 'exit_2'])
        expect(ports.dynamic[1].status).toBe('pending')
    })
})

describe('portModel 其他节点类型', () => {
    it('普通节点：success 可见、无动态口', () => {
        const node = makeNode('click', {})
        const ports = buildNodePorts(node, [], FAILURE_TYPES)
        expect(ports.success.visible).toBe(true)
        expect(ports.failure.visible).toBe(false)
        expect(ports.dynamic).toHaveLength(0)
    })

    it('历史数据兼容：其他类型节点上的动态边补进端口', () => {
        const node = makeNode('wait', {})
        const edges = makeEdges({ source_node: 'n1', source_port: 'exit_0', target_node: 'n2' })
        const ports = buildNodePorts(node, edges, FAILURE_TYPES)
        expect(ports.dynamic.map(p => p.name)).toEqual(['exit_0'])
        expect(ports.dynamic[0].connected).toBe(true)
    })
})

describe('portModel 辅助函数', () => {
    it('getDefinedDynamicPorts：branch 候选生成端口，其余类型为空', () => {
        const branch = makeNode('branch', { candidates: [{}, {}, {}] })
        expect(getDefinedDynamicPorts(branch, 'branch').map(p => p.name)).toEqual(['branch_0', 'branch_1', 'branch_2'])
        expect(getDefinedDynamicPorts(makeNode('click', {}), 'click')).toEqual([])
    })

    it('getPageStateExitPorts：出边按序号升序，label 缺省回退出口 N', () => {
        const node = makeNode('page_state', { page_id: 'p1' })
        const edges = makeEdges(
            { source_node: 'n1', source_port: 'exit_1', target_node: 'n3' },
            { source_node: 'n1', source_port: 'exit_0', target_node: 'n2', label: '点[商店]' },
            { source_node: 'n9', source_port: 'exit_0', target_node: 'n9' }
        )
        const exits = getPageStateExitPorts(node, edges)
        expect(exits.map(e => e.name)).toEqual(['exit_0', 'exit_1'])
        expect(exits[0].label).toBe('点[商店]')
        expect(exits[1].label).toBe('出口 2')
    })
})
