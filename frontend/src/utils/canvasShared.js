// canvasShared.js
// Shared constants and CSS for WorkflowCanvas + TopologyCanvas.
// All visual styles are centralized here and injected once by useCanvasSharedStyle.
// This is the SINGLE SOURCE OF TRUTH for canvas styling — no component-level CSS overrides.

import { NODE_REGISTRY, DEFAULT_NODE_CONFIG, getNodeConfig } from '../config/nodeRegistry'

// ========== 尺寸常量 ==========

export const GRID_SIZE = 20
export const NODE_GRID_W = 8
export const NODE_WIDTH = NODE_GRID_W * GRID_SIZE
export const NODE_MIN_HEIGHT = 60   // 最小高度 3 格（头部 32 + footer 24 向上取整）
export const PORT_RADIUS = 7
export const EDGE_STROKE_WIDTH = 2
export const EDGE_HOVER_STROKE_WIDTH = 4
export const EDGE_FLOW_DASH = '8 12'
export const EDGE_FLOW_DURATION = '0.8s'

// ========== 端口网格布局常量（一切以网格为单位） ==========

export const PORT_GRID_TOP = 1        // entry / success 距顶格数
export const PORT_GRID_BOTTOM = 1     // failure 距底格数
export const PORT_GRID_STEP = 2       // 动态出口间距格数（旧网格布局保留，行对齐后仅作回退）
export const PORT_DIAMETER = 14       // 端口直径 (px)
export const NODE_HEADER_H = 32       // 头部高度 (px)
export const NODE_FOOTER_H = 24       // Footer 高度 (px)

// ========== 行对齐端口几何（与 nodeRegistry content 规则 / CanvasNodeCard CSS 保持联动） ==========
export const BODY_PAD_TOP = 6         // 内容区顶部内边距 (px)
export const COND_ROW_H = 24          // 候选行 / 出口行行高 (px)
export const COND_ROW_GAP = 4         // 行间距 (px)
export const COND_ROW_PITCH = COND_ROW_H + COND_ROW_GAP  // 行距 (28px)
export const INFO_LINE_H = 20         // 页面特征摘要信息行高 (px)

// ========== 节点类型配置（统一注册表，两模式共用，见 config/nodeRegistry.js） ==========

export const NODE_TYPE_CONFIG = NODE_REGISTRY
export { DEFAULT_NODE_CONFIG, getNodeConfig }

// ========== 通用工具 ==========

export function snapToGrid(value, grid = GRID_SIZE) {
    return Math.round(value / grid) * grid
}

export function snapPositionToGrid(x, y, grid = GRID_SIZE) {
    return { x: snapToGrid(x, grid), y: snapToGrid(y, grid) }
}

// ========== 端口位置计算（Step 4：网格坐标系） ==========

/**
 * 读取节点动态端口列表（由 CanvasView 注入 node.ports.dynamic）
 */
export function getNodeDynamicPorts(node) {
    return node?.ports?.dynamic || []
}

/**
 * 行对齐端口：端口中心 = 对应行的垂直中心（头部 + 内容区起始 + 行距）
 *   - branch_N   : 第 N 个候选行中心
 *   - exit_N     : 第 N 个出口行中心（page_state 有特征摘要行时整体下移一行）
 */
export function getRowAlignedPortTop(node, index) {
    // 出口行从内容区起始处排布（页面节点卡片仅展示出口行，无特征摘要行）
    const base = NODE_HEADER_H + BODY_PAD_TOP
    return base + index * COND_ROW_PITCH + COND_ROW_H / 2
}

/**
 * 端口中心距节点顶部的像素偏移（网格坐标）
 *   - entry   : 距顶 1 格
 *   - success : 距顶 1 格
 *   - failure : 距底 1 格（随节点最新高度 h 联动）
 *   - branch_N / exit_N：行对齐（与候选行/出口行垂直中心重合），越界时 clamp 到 failure 之上
 */
export function getNodePortTop(node, portType) {
    const h = node?.h || node?.size?.h || NODE_MIN_HEIGHT

    if (portType === 'entry') return PORT_GRID_TOP * GRID_SIZE
    if (portType === 'success' || portType === 'succ') return PORT_GRID_TOP * GRID_SIZE
    if (portType === 'failure' || portType === 'fail') return h - PORT_GRID_BOTTOM * GRID_SIZE

    const m = typeof portType === 'string' ? portType.match(/^(?:branch|exit)_(\d+)$/) : null
    if (m) {
        const idx = parseInt(m[1], 10) || 0
        return Math.min(getRowAlignedPortTop(node, idx), h - PORT_GRID_BOTTOM * GRID_SIZE - 4)
    }
    if (portType === 'exit' || portType === 'exit_0') {
        return getRowAlignedPortTop(node, 0)
    }
    // 未知端口类型：右侧中部兜底
    return h / 2
}

/**
 * 计算节点的绝对端口坐标
 *   entry 在左缘，其余端口在右缘；纵向全部落在网格线上
 */
export function getPortPosition(node, portType, _options = {}) {
    const x = node.position?.x || 0
    const y = node.position?.y || 0
    const w = node.w || node.size?.w || NODE_WIDTH
    const top = getNodePortTop(node, portType)

    if (portType === 'entry') {
        return { x, y: y + top }
    }
    return { x: x + w, y: y + top }
}

/**
 * 节点高度计算（内容驱动 + 网格向上取整，两模式共用）
 * 总高度 = ceil(头部 32 + max(内容区, 动态端口预留) + Footer 24, 最小 60) 向上取整到网格
 * 动态端口预留：第 k 个动态端口位于 (1 + 2(k+1)) 格处，预留保证最后一枚
 * 位于 failure（距底 1 格）之上至少 1 格：reserve = max(0, 40×N + 4)
 * @param {number} contentHeight 内容区估算高度(px)，0 表示无内容
 * @param {number} dynamicCount  动态端口数量
 */
export function computeCanvasNodeHeight(contentHeight, dynamicCount) {
    const count = Math.max(0, dynamicCount || 0)
    const reserve = Math.max(0, 40 * count + 4)
    const content = Math.max(contentHeight || 0, reserve)
    const raw = NODE_HEADER_H + content + NODE_FOOTER_H
    return Math.ceil(Math.max(raw, NODE_MIN_HEIGHT) / GRID_SIZE) * GRID_SIZE
}

// ========== 箭头方向 ==========

export function getArrowDirection(points) {
    if (!points || points.length < 2) return 'right'
    const last = points[points.length - 1]
    const prev = points[points.length - 2]
    const dx = last.x - prev.x
    const dy = last.y - prev.y
    if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? 'right' : 'left'
    return dy > 0 ? 'down' : 'up'
}

export function getMarkerId(portType, direction) {
    const isFailure = portType === 'failure' || portType === 'fail'
    const isSuccess = portType === 'success' || portType === 'succ' ||
                      portType === 'exit' || portType.startsWith('exit_') ||
                      portType.startsWith('branch_')
    const prefix = isFailure ? 'arrow-fail' : (isSuccess ? 'arrow-succ' : 'arrow-default')
    if (prefix === 'arrow-default') return 'arrow-default'
    return `${prefix}-${direction}`
}

// ========== 碰撞检测 ==========

export function isColliding(a, b) {
    const ax = a.position?.x || 0
    const ay = a.position?.y || 0
    const aw = a.size?.w || NODE_WIDTH
    const ah = a.size?.h || NODE_MIN_HEIGHT
    const bx = b.position?.x || 0
    const by = b.position?.y || 0
    const bw = b.size?.w || NODE_WIDTH
    const bh = b.size?.h || NODE_MIN_HEIGHT
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by
}

export function resolveCollisionsAndPushOthers(nodes, draggedNode, maxIterations = 15) {
    const pushed = new Set()
    const MIN_GAP = GRID_SIZE * 2

    for (let iter = 0; iter < maxIterations; iter++) {
        let hasCollision = false
        for (const other of nodes) {
            if (other === draggedNode || other.node_id === draggedNode.node_id) continue
            if (pushed.has(other.node_id)) continue

            const dragExpanded = {
                ...draggedNode,
                position: {
                    x: (draggedNode.position?.x || 0) - MIN_GAP / 2,
                    y: (draggedNode.position?.y || 0) - MIN_GAP / 2
                },
                size: {
                    w: (draggedNode.size?.w || NODE_WIDTH) + MIN_GAP,
                    h: (draggedNode.size?.h || NODE_MIN_HEIGHT) + MIN_GAP
                }
            }
            if (isColliding(dragExpanded, other)) {
                hasCollision = true
                pushed.add(other.node_id)
                const dcx = (draggedNode.position?.x || 0) + (draggedNode.size?.w || NODE_WIDTH) / 2
                const dcy = (draggedNode.position?.y || 0) + (draggedNode.size?.h || NODE_MIN_HEIGHT) / 2
                const ocx = (other.position?.x || 0) + (other.size?.w || NODE_WIDTH) / 2
                const ocy = (other.position?.y || 0) + (other.size?.h || NODE_MIN_HEIGHT) / 2
                const dx = ocx - dcx
                const dy = ocy - dcy
                const dist = Math.sqrt(dx * dx + dy * dy) || 1
                const pushDist = MIN_GAP
                const newX = snapToGrid((other.position?.x || 0) + (dx / dist) * pushDist)
                const newY = snapToGrid((other.position?.y || 0) + (dy / dist) * pushDist)
                other.position = { x: newX, y: newY }
            }
        }
        if (!hasCollision) break
    }
    return nodes.filter(n => pushed.has(n.node_id))
}

// ========== 组包围盒 / 创建避让（新建节点与新建组自动推开，不再重叠） ==========

export const GROUP_PADDING_GRIDS = 3      // 组内边距（格）
export const GROUP_TITLE_H = 24           // 组标题高度 (px)
export const GROUP_MIN_W = 220
export const GROUP_MIN_H = 140

/** 组包围盒（与 CanvasView.dynamicGroups 的推导规则一致：成员包围盒 + 内边距 + 标题） */
export function computeGroupBox(nodes, paddingGrids = GROUP_PADDING_GRIDS) {
    const list = Array.isArray(nodes) ? nodes : []
    const padding = paddingGrids * GRID_SIZE
    if (!list.length) return { x: 60, y: 60, w: GROUP_MIN_W, h: GROUP_MIN_H }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const n of list) {
        const x = n.position?.x ?? 0
        const y = n.position?.y ?? 0
        const w = n.size?.w ?? NODE_WIDTH
        const h = n.size?.h ?? NODE_MIN_HEIGHT
        if (x < minX) minX = x
        if (y < minY) minY = y
        if (x + w > maxX) maxX = x + w
        if (y + h > maxY) maxY = y + h
    }
    const w = Math.max(maxX - minX + padding * 2, GROUP_MIN_W)
    const h = Math.max(maxY - minY + padding * 2 + GROUP_TITLE_H, GROUP_MIN_H)
    return { x: minX - padding, y: minY - padding, w, h }
}

/**
 * 新建节点避让：从给定位置开始，若与现有矩形集合碰撞则沿右下方向逐格外移，
 * 返回第一个无碰撞的网格对齐坐标（不移动任何现有对象——新节点被挤开，旧布局不动）。
 * @param {Array<{position:{x,y}, size?:{w,h}}>} others 现有节点（矩形）
 * @param {{x:number,y:number}} pos 期望位置
 * @param {{w:number,h:number}} size 新节点尺寸
 */
export function findFreePosition(others, pos, size = { w: NODE_WIDTH, h: NODE_MIN_HEIGHT }) {
    const MIN_GAP = GRID_SIZE * 2
    let x = pos?.x ?? 0
    let y = pos?.y ?? 0
    const step = GRID_SIZE
    let attempt = 0
    while (attempt < 200) {
        const candidate = { position: { x, y }, size }
        const collides = (others || []).some(o => isColliding(candidate, o))
        if (!collides) {
            return { x: snapToGrid(x), y: snapToGrid(y) }
        }
        // 沿右下方向逐格外移（简单稳定，不惊动旧布局）
        x += step
        if (x > pos.x + size.w + step * 4) {
            x = pos.x
            y += step
        }
        attempt += 1
    }
    return { x: snapToGrid(x), y: snapToGrid(y) }
}

// ========== 共享边 CSS ==========

export const SHARED_EDGE_CSS = `
.canvas-edges-layer {
    position: absolute;
    overflow: visible;
    pointer-events: none;
    z-index: 1;
}
.canvas-edges-layer g {
    pointer-events: auto;
}

/* Edge base styles */
.edge-path {
    fill: none;
    stroke: #4ed19c;
    stroke-width: ${EDGE_STROKE_WIDTH};
    stroke-linecap: round;
    stroke-linejoin: round;
    pointer-events: stroke;
    cursor: pointer;
    filter: drop-shadow(0 0 0 transparent);
    transition: stroke-width 0.15s ease, filter 0.15s ease, stroke 0.15s ease;
}
.edge-path.is-failure { stroke: #f56c6c; }
.edge-path.is-default { stroke: #8b93a7; }

.edge-path:hover {
    stroke-width: ${EDGE_HOVER_STROKE_WIDTH};
    filter: drop-shadow(0 0 8px rgba(78, 209, 156, 0.7));
}
.edge-path.is-failure:hover {
    filter: drop-shadow(0 0 8px rgba(245, 108, 108, 0.7));
}
.edge-path.is-selected {
    stroke-width: 3.5;
    stroke: #ffffff !important;
    filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.8));
}

/* 悬停联动：候选行/出口行悬停时，对应端口的所有出边高亮 */
.edge-path.is-port-hovered {
    stroke-width: 3.5;
    filter: drop-shadow(0 0 8px rgba(78, 209, 156, 0.7));
}
.edge-path.is-port-hovered.is-failure {
    filter: drop-shadow(0 0 8px rgba(245, 108, 108, 0.7));
}

/* Edge hit area for easier clicking */
.edge-hit-area {
    fill: none;
    stroke: transparent;
    stroke-width: 14;
    pointer-events: stroke;
    cursor: pointer;
}
.edge-hit-area.is-selected {
    stroke: rgba(255, 255, 255, 0.08);
}

/* Flow animation overlay */
.edge-flow-path {
    fill: none;
    stroke: rgba(78, 209, 156, 0.85);
    stroke-width: 1.8;
    stroke-dasharray: ${EDGE_FLOW_DASH};
    animation: edgeFlow ${EDGE_FLOW_DURATION} linear infinite;
    pointer-events: none;
    opacity: 0.6;
}
.edge-flow-path.is-failure {
    stroke: rgba(245, 108, 108, 0.85);
}
@keyframes edgeFlow {
    from { stroke-dashoffset: 20; }
    to   { stroke-dashoffset: 0; }
}

/* Preview / drag-time path */
.edge-path.preview-path {
    stroke: #4ed19c;
    stroke-dasharray: 6 4;
    opacity: 0.9;
    pointer-events: none;
    animation: edgeFlow 1s linear infinite;
}
.edge-path.preview-path.is-failure {
    stroke: #f56c6c;
}

/* 拖动连线预览终点：连线颜色的发光球（无箭头，松手后恢复箭头） */
.preview-drawing .preview-drag-ball {
    fill: #4ed19c;
    filter: drop-shadow(0 0 5px rgba(78, 209, 156, 0.9)) drop-shadow(0 0 14px rgba(78, 209, 156, 0.6));
    pointer-events: none;
}
.preview-drawing.is-failure .preview-drag-ball {
    fill: #f56c6c;
    filter: drop-shadow(0 0 5px rgba(245, 108, 108, 0.9)) drop-shadow(0 0 14px rgba(245, 108, 108, 0.6));
}
.preview-drawing.is-failure .edge-path.preview-path {
    stroke: #f56c6c;
}

/* Context / spawn menu */
.spawn-menu {
    position: fixed;
    min-width: 200px;
    background: rgba(24, 26, 40, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 0;
    z-index: 1000;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
}
.spawn-menu-header {
    padding: 8px 16px 6px;
    font-size: 11px;
    color: #8b93a7;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    margin-bottom: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-weight: 600;
}
.spawn-menu-list {
    display: flex;
    flex-direction: column;
}
.spawn-menu-item {
    padding: 9px 16px;
    font-size: 13px;
    color: #e0e0e0;
    cursor: pointer;
    transition: background 0.12s, color 0.12s, padding-left 0.12s;
    display: flex;
    align-items: center;
    gap: 10px;
}
.spawn-menu-item:hover {
    background: rgba(78, 209, 156, 0.12);
    color: #4ed19c;
    padding-left: 20px;
}
.spawn-menu-item .menu-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
}

.custom-context-menu {
    position: fixed;
    min-width: 200px;
    background: rgba(24, 26, 40, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 6px 0;
    z-index: 1000;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
}
.menu-item {
    padding: 8px 16px;
    font-size: 13px;
    color: #e0e0e0;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
    display: flex;
    align-items: center;
    gap: 10px;
}
.menu-item:hover {
    background: rgba(78, 209, 156, 0.12);
    color: #4ed19c;
}
.menu-item.danger { color: #f56c6c; }
.menu-item.danger:hover {
    background: rgba(245, 108, 108, 0.15);
    color: #ffffff;
}
.menu-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin: 4px 8px;
}
.menu-item-icon {
    width: 14px;
    height: 14px;
}
.bp-dot-inline {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #e5484d;
    box-shadow: 0 0 6px rgba(229, 72, 77, 0.8);
}
`

// ========== 共享节点 CSS ==========

export const SHARED_NODE_CSS = `
/* ---------- Canvas Container ---------- */
.custom-canvas-container,
.topology-canvas-container {
    width: 100%;
    height: 100%;
    position: relative;
    /* clip：连程序化滚动一并禁止（防止 scrollIntoView 等悄悄滚动画布导致坐标系偏移） */
    overflow: hidden;
    overflow: clip;
    user-select: none;
    background: #1a1b2e;
}
.custom-canvas-container {
    cursor: grab;
}
.custom-canvas-container:active {
    cursor: grabbing;
}

.canvas-viewport {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

/* 矢量网格线（由世界图层 SVG 绘制） */
.canvas-grid-line {
    fill: none;
    stroke: rgba(255, 255, 255, 0.04);
    stroke-width: 1;
    pointer-events: none;
}
.canvas-grid-line-major {
    stroke: rgba(255, 255, 255, 0.07);
}

/* ---------- Node Card ---------- */
.canvas-node-card {
    --node-accent: #409eff;
    position: absolute;
    background: var(--node-card-bg, rgba(30, 32, 50, 0.92));
    border: 1px solid var(--node-card-border, rgba(255, 255, 255, 0.08));
    border-radius: var(--node-card-radius, 10px);
    overflow: visible;
    cursor: grab;
    user-select: none;
    transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.05s ease;
    box-shadow: var(--node-card-shadow, 0 4px 20px rgba(0, 0, 0, 0.5));
    display: flex;
    flex-direction: column;
    z-index: 2;
}
.canvas-node-card:active {
    cursor: grabbing;
}
.canvas-node-card:hover {
    border-color: rgba(78, 209, 156, 0.5);
    box-shadow: var(--node-card-shadow-hover, 0 8px 28px rgba(0, 0, 0, 0.55));
}
.canvas-node-card.is-selected {
    border: 2px solid #4ed19c;
    box-shadow:
        0 0 0 3px rgba(78, 209, 156, 0.25),
        0 4px 20px rgba(0, 0, 0, 0.5);
}
.canvas-node-card.is-active-debug {
    border: 2px solid #ffb020 !important;
    box-shadow:
        0 0 0 4px rgba(255, 176, 32, 0.25),
        0 12px 32px rgba(255, 176, 32, 0.2) !important;
    animation: debug-pulse 1.2s ease-in-out infinite;
}
@keyframes debug-pulse {
    0%, 100% { filter: brightness(1); }
    50%      { filter: brightness(1.2); }
}
.canvas-node-card.is-disabled { opacity: 0.55; }

/* ---------- Node Header ---------- */
.node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 8px 12px;
    box-sizing: border-box;
    border-radius: 10px 10px 0 0;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: transparent;
    position: relative;
    flex-shrink: 0;
}
.node-header-left {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
    padding-left: 4px;
}
.node-type-icon {
    width: 15px;
    height: 15px;
    color: #fff;
    flex-shrink: 0;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.4));
}
.node-title {
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    line-height: 1.3;
}

/* ---------- Node Body ---------- */
/* 内容驱动：body 高度 = 节点高 - 头部 - footer（含网格取整松弛区）；
   无内容时 padding 为 0，只留取整后的松弛空隙 */
.node-body {
    padding: 0;
    font-size: 11px;
    color: #c4c9d4;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    overflow: hidden;
    background: var(--node-content-bg, rgba(0, 0, 0, 0.15));
    gap: 0;
}
.node-info { line-height: 18px; }
.info-label { color: #7a8296; margin-right: 4px; }

/* ---------- Node Footer ---------- */
.node-footer-bar {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding: 6px 12px;
    margin-top: auto;
    flex-shrink: 0;
    background: var(--node-footer-bg, rgba(0, 0, 0, 0.1));
    border-radius: 0 0 10px 10px;
}
.footer-tag {
    font-size: 10px;
    color: #8b93a7;
    font-weight: 500;
}

/* ---------- Ports / Handles ---------- */
.node-handle {
    position: absolute;
    width: ${PORT_DIAMETER}px;
    height: ${PORT_DIAMETER}px;
    border-radius: 50%;
    cursor: crosshair;
    z-index: 8;
    border: 2px solid var(--port-ring, #12131e);
    box-sizing: border-box;
    background: var(--port-color, #3a3d52);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    transform: translateY(-50%);
    transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}
.node-handle::after {
    content: '';
    position: absolute;
    top: -12px;
    left: -12px;
    right: -12px;
    bottom: -12px;
    background: transparent;
    border-radius: 50%;
}
.node-handle:hover {
    transform: translateY(-50%) scale(1.3);
    box-shadow: 0 0 10px var(--port-glow, rgba(78, 209, 156, 0.8));
    z-index: 10;
}

/* 空心状态：定义存在但未连线，提示可拖出连线 */
.node-handle.is-unconnected {
    background: transparent;
    border-style: dashed;
    opacity: 0.55;
    box-shadow: none;
}
.node-handle.is-unconnected:hover {
    opacity: 1;
    box-shadow: 0 0 10px var(--port-glow, rgba(78, 209, 156, 0.8));
}

/* Entry port (left, 1 grid from top) - gray, where edges land */
.entry-handle {
    left: -7px;
    cursor: default;
    --port-color: var(--port-entry, #4a4d62);
    border-color: var(--port-entry-border, #6b7090);
    z-index: 5;
}
.entry-handle:hover {
    box-shadow: 0 0 0 transparent;
    transform: translateY(-50%) scale(1.15);
}

/* Success port (right, 1 grid from top) - green, primary exit */
.succ-handle {
    right: -7px;
    --port-color: var(--port-success, #4ed19c);
    --port-glow: rgba(78, 209, 156, 0.8);
    border-color: var(--port-success-border, #2a8565);
}

/* Failure port (right, 1 grid from bottom) - red, failure exit */
.fail-handle {
    right: -7px;
    --port-color: var(--port-failure, #f56c6c);
    --port-glow: rgba(245, 108, 108, 0.8);
    border-color: var(--port-failure-border, #a03838);
}

/* Dynamic ports (right, 1 grid step, stacked between success and failure) - green */
.dyn-handle {
    right: -7px;
    --port-color: var(--port-success, #4ed19c);
    --port-glow: rgba(78, 209, 156, 0.8);
    border-color: var(--port-success-border, #2a8565);
}

/* Pending 虚线占位口（page_state 尾部“新出口”槽位）：虚线空心 + 呼吸脉冲邀请连线 */
.node-handle.is-pending {
    background: transparent;
    border-style: dashed;
    border-color: var(--port-success-border, #2a8565);
    opacity: 0.8;
    animation: pending-pulse 1.6s ease-in-out infinite;
}
.node-handle.is-pending:hover {
    opacity: 1;
}
@keyframes pending-pulse {
    0%, 100% { box-shadow: 0 0 0 rgba(78, 209, 156, 0); transform: translateY(-50%) scale(1); }
    50%      { box-shadow: 0 0 12px rgba(78, 209, 156, 0.7); transform: translateY(-50%) scale(1.12); }
}

/* 行 ↔ 端口悬停联动：悬停任一侧，另一侧同步高亮 */
.branch-candidate-item.is-port-hovered,
.page-exit-item.is-port-hovered {
    background: rgba(78, 209, 156, 0.16) !important;
    border-color: rgba(78, 209, 156, 0.55) !important;
}
.page-exit-item {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 0 10px;
    font-size: 11px;
    height: 24px;
    box-sizing: border-box;
    flex-shrink: 0;
    overflow: hidden;
    transition: background 0.12s, border-color 0.12s;
}
.page-exit-item:hover {
    background: rgba(78, 209, 156, 0.08);
    border-color: rgba(78, 209, 156, 0.3);
}
.page-exit-item.is-pending-row {
    border-style: dashed;
    opacity: 0.55;
    font-style: italic;
}
.page-exit-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #c4c9d4;
    flex: 1;
    min-width: 0;
}

/* ---------- Breakpoint / Debug ---------- */
/* 断点槽：标题栏右侧；三态样式——
   未设置：空心圆环（hover 变亮）；已设置：实心红点 + 外发光；命中：脉冲放大 */
.node-breakpoint-gutter {
    width: 12px;
    height: 12px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-left: 8px;
    cursor: pointer;
    user-select: none;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.15);
    box-sizing: border-box;
    transition: border-color 0.15s, background-color 0.15s, box-shadow 0.15s;
}
.node-breakpoint-gutter:hover {
    border-color: rgba(255, 255, 255, 0.3);
}
.node-breakpoint-gutter .bp-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #e5484d;
    box-shadow: 0 0 8px rgba(229, 72, 77, 0.6);
    transition: box-shadow 0.15s;
}
.node-breakpoint-gutter.active {
    border-color: rgba(229, 72, 77, 0.6);
}
.node-breakpoint-gutter.active:hover {
    border-color: rgba(229, 72, 77, 0.9);
}
/* 断点命中（调试暂停于此节点）：脉冲呼吸灯 + 发光放大 */
.canvas-node-card.is-active-debug .node-breakpoint-gutter.active .bp-dot {
    animation: breakpoint-pulse 0.9s ease-in-out infinite;
    box-shadow: 0 0 16px rgba(229, 72, 77, 0.9);
}
@keyframes breakpoint-pulse {
    0%, 100% { transform: scale(1); }
    50%      { transform: scale(1.35); }
}
.node-debug-tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #ffb020;
    color: #1a1a1a;
    box-shadow: 0 0 10px rgba(255, 176, 32, 0.85);
    flex-shrink: 0;
    animation: debug-pulse 1s ease-in-out infinite;
}
.debug-pulse-icon { width: 12px; height: 12px; }

/* ---------- Branch Node ---------- */
/* 行高/间距与 config/nodeRegistry.js 的 rowHeight=24 / rowGap=4 / rowPadding=12 保持一致 */
.branch-candidates-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    padding: 6px 12px;
    box-sizing: border-box;
    overflow: hidden;
}
.branch-candidate-item {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 0 10px;
    font-size: 11px;
    height: 24px;
    box-sizing: border-box;
    flex-shrink: 0;
    overflow: hidden;
    transition: background 0.12s, border-color 0.12s;
}
.branch-candidate-item:hover {
    background: rgba(78, 209, 156, 0.08);
    border-color: rgba(78, 209, 156, 0.3);
}
.branch-cand-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #c4c9d4;
    flex: 1;
    min-width: 0;
}
.empty-cand-placeholder {
    font-size: 11px;
    color: #6b7280;
    text-align: center;
    height: 24px;
    line-height: 24px;
    font-style: italic;
}

/* ---------- Image Node ---------- */
/* 缩略图块：最小高度 80px（与 nodeRegistry minHeight 一致），padding 计入块高 */
.node-image-embedded {
    position: relative;
    width: 100%;
    height: 100%;
    padding: 8px 12px;
    box-sizing: border-box;
    background: rgba(18, 19, 28, 0.8);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    min-height: 80px;
}
.embedded-template-img {
    position: relative;
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 6px;
    display: block;
    z-index: 2;
    pointer-events: none;
}
.embedded-template-img.is-contain {
    object-fit: contain;
}
.embedded-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 5px;
    font-size: 11px;
    color: #6b7280;
    z-index: 2;
}

/* ---------- OCR Node ---------- */
/* 缩略图 + 配置行，最小高度 60px（与 nodeRegistry minHeight 一致） */
.ocr-preview-block {
    width: 100%;
    height: 100%;
    min-height: 60px;
    padding: 8px 12px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
}
.ocr-thumb {
    width: 44px;
    height: 44px;
    object-fit: cover;
    border-radius: 6px;
    flex-shrink: 0;
    background: rgba(18, 19, 28, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.08);
}
.ocr-thumb-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
}
.ocr-info-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
}
.ocr-info-col .node-info {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ---------- Page State Node ---------- */
/* 信息行：行高 20px、内边距 12px（与 nodeRegistry lineHeight/rowPadding 一致）；
   出口行间距 4px 与 branch 候选行一致（端口行对齐公式按同一几何） */
.page-info-list {
    width: 100%;
    padding: 6px 12px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow: hidden;
}
.page-info-list .node-info {
    line-height: 20px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ---------- Group Box ---------- */
.canvas-group-box {
    position: absolute;
    box-sizing: border-box;
    border: 2px dashed rgba(78, 209, 156, 0.4);
    border-radius: 14px;
    background: rgba(78, 209, 156, 0.025);
    pointer-events: none;
    transition: border-color 0.2s ease, background 0.2s ease;
}
.canvas-group-box.is-focused {
    border: 2.5px solid #4ed19c;
    background: rgba(78, 209, 156, 0.05);
}
.group-title-badge {
    position: absolute;
    top: -28px;
    left: 14px;
    right: 14px;
    background: #262840;
    padding: 5px 12px;
    color: #4ed19c;
    border: 1px solid rgba(78, 209, 156, 0.4);
    border-radius: 8px;
    pointer-events: auto;
    cursor: grab;
    display: flex;
    flex-direction: column;
    gap: 2px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}
.group-name-text {
    font-size: 12px;
    font-weight: 600;
}
.group-sub-info {
    font-size: 10px;
    color: #8b93a7;
    display: flex;
    gap: 10px;
}

/* ---------- Drag Preview ---------- */
.node-drag-preview-box {
    position: absolute;
    border: 2px dashed rgba(78, 209, 156, 0.6);
    background: rgba(78, 209, 156, 0.08);
    border-radius: 12px;
    pointer-events: none;
    z-index: 9;
    box-sizing: border-box;
    transition: border-color 0.15s, background 0.15s;
}
.node-drag-preview-box.is-danger {
    border-color: #f56c6c;
    background: rgba(245, 108, 108, 0.12);
}
.preview-inner-tag {
    position: absolute;
    top: 6px;
    left: 10px;
    font-size: 11px;
    font-weight: 600;
    color: #4ed19c;
    background: rgba(26, 27, 46, 0.9);
    padding: 3px 8px;
    border-radius: 5px;
    backdrop-filter: blur(4px);
}

/* ---------- Selection Box ---------- */
.selection-box {
    position: absolute;
    background: rgba(78, 209, 156, 0.1);
    border: 1px solid #4ed19c;
    border-radius: 4px;
    pointer-events: none;
    z-index: 999;
}

/* ---------- Minimap ---------- */
.minimap-container {
    position: absolute;
    right: 16px;
    bottom: 16px;
    width: 160px;
    height: 120px;
    background: rgba(20, 22, 34, 0.8);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    z-index: 998;
    overflow: hidden;
}

/* ---------- Canvas Toolbar ---------- */
.canvas-toolbar {
    position: absolute;
    bottom: 16px;
    left: 16px;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    background: rgba(26, 27, 46, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    z-index: 100;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
}
.toolbar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: none;
    background: transparent;
    color: #a0a1ab;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
.toolbar-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
}
.zoom-display {
    font-size: 12px;
    color: #a0a1ab;
    min-width: 42px;
    text-align: center;
    font-weight: 500;
}
`
