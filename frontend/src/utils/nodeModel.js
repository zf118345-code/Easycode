// frontend/src/utils/nodeModel.js
// 统一数据模型适配层：抹平 WorkflowCanvas / TopologyCanvas / 路由系统 之间的节点结构与端口命名差异
//
// 主要解决：
// 1. 节点尺寸字段：历史代码用 node.w / node.h，新路由 canvasRouter 用 node.size.w / node.size.h
// 2. 端口命名差异：历史 'succ' / 'fail'，新路由 'success' / 'failure'
// 3. Branch 端口命名：旧 branch_N，新 branch_N（保持一致，但归一化出口）

import { NODE_WIDTH, NODE_MIN_HEIGHT } from './canvasShared'

// ========== 端口命名归一化 ==========

const PORT_ALIAS = {
    'succ': 'success',
    'success': 'success',
    'fail': 'failure',
    'failure': 'failure',
    'entry': 'entry'
}

/**
 * 将历史端口名归一化为标准端口名
 *   'succ'   → 'success'
 *   'fail'   → 'failure'
 *   'branch_N' / 'exit_N' 原样保留
 */
export function normalizePortType(portType) {
    if (!portType) return 'success'
    if (PORT_ALIAS[portType]) return PORT_ALIAS[portType]
    // branch_N / exit_N 原样通过
    return portType
}

/**
 * 反向映射：标准端口名 → 旧端口名（供仍使用旧命名的 API 临时过渡）
 */
export function legacyPortType(portType) {
    if (portType === 'success') return 'succ'
    if (portType === 'failure') return 'fail'
    return portType
}

// ========== 节点尺寸字段归一化 ==========

/**
 * 读取节点宽度，兼容 node.w 与 node.size.w
 */
export function getNodeWidth(node) {
    if (!node) return NODE_WIDTH
    if (typeof node.size?.w === 'number') return node.size.w
    if (typeof node.w === 'number') return node.w
    return NODE_WIDTH
}

/**
 * 读取节点高度，兼容 node.h 与 node.size.h
 */
export function getNodeHeight(node) {
    if (!node) return NODE_MIN_HEIGHT
    if (typeof node.size?.h === 'number') return node.size.h
    if (typeof node.h === 'number') return node.h
    return NODE_MIN_HEIGHT
}

/**
 * 写入统一尺寸字段，返回带 size 的新节点对象（浅拷贝）
 * canvasRouter 等新模块需要 node.size.w / node.size.h
 */
export function normalizeNode(node) {
    if (!node) return null
    const w = getNodeWidth(node)
    const h = getNodeHeight(node)
    return {
        ...node,
        size: { w, h },
        w,
        h
    }
}

/**
 * 批量归一化节点数组
 */
export function normalizeNodeList(nodes) {
    if (!Array.isArray(nodes)) return []
    return nodes.map(n => normalizeNode(n))
}

/**
 * 从 renderNodes 的构造处生成标准模型（给 canvasRouter 用）
 * canvasRouter 只关心 position 和 size
 */
export function toRouterNode(node) {
    if (!node) return null
    return {
        node_id: node.node_id,
        position: node.position || { x: 0, y: 0 },
        size: {
            w: getNodeWidth(node),
            h: getNodeHeight(node)
        }
    }
}

// ========== 端口位置计算（统一入口，给 computedEdges / 拉线预览复用） ==========

import { getPortPosition as sharedGetPortPosition } from './canvasShared'

/**
 * 统一端口位置计算：接收历史端口名或标准端口名，内部归一化后调用 canvasShared
 */
export function getPortPosition(node, portType, options = {}) {
    const standardPort = normalizePortType(portType)
    // 如果 node 没有 size，先注入
    const normalizedNode = node.size ? node : normalizeNode(node)
    return sharedGetPortPosition(normalizedNode, standardPort, options)
}

// ========== 箭头方向 / Marker 计算 ==========

export { getArrowDirection, getMarkerId } from './canvasShared'

// ========== 连线路径结果格式转换 ==========

/**
 * 将 canvasRouter.computeEdgePath 返回的结果，转成旧 gridRouter 的结构
 * 目的：让 WorkflowCanvas 中已有的 computedEdges 逻辑无需大改即可切换路由
 *
 * 新返回: { pathD, arrowDir, markerId, points }
 * 旧期望: { startPt, endPt, pathStr, rawPixelPoints, arrowDir }
 */
export function adaptRouterResult(routerResult) {
    if (!routerResult) {
        return {
            startPt: { x: 0, y: 0 },
            endPt: { x: 0, y: 0 },
            pathStr: '',
            rawPixelPoints: [],
            arrowDir: 'down'
        }
    }
    const pts = routerResult.points || []
    return {
        startPt: pts[0] || { x: 0, y: 0 },
        endPt: pts[pts.length - 1] || { x: 0, y: 0 },
        pathStr: routerResult.pathD || '',
        rawPixelPoints: pts,
        arrowDir: routerResult.arrowDir || 'down',
        markerId: routerResult.markerId || 'arrow-default'
    }
}
