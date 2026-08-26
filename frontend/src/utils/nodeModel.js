// frontend/src/utils/nodeModel.js
// 画布节点的统一尺寸与端口模型。

import { NODE_WIDTH, NODE_MIN_HEIGHT } from './canvasShared'

// ========== 端口命名归一化 ==========

export function normalizePortType(portType) {
    return portType || 'success'
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

// ========== 端口位置计算（统一入口，给 computedEdges / 拉线预览复用） ==========

import { getPortPosition as sharedGetPortPosition } from './canvasShared'

/**
 * 统一端口位置计算。
 */
export function getPortPosition(node, portType, options = {}) {
    const standardPort = normalizePortType(portType)
    // 如果 node 没有 size，先注入
    const normalizedNode = node.size ? node : normalizeNode(node)
    return sharedGetPortPosition(normalizedNode, standardPort, options)
}

// ========== 箭头方向 / Marker 计算 ==========

export { getArrowDirection, getMarkerId } from './canvasShared'
