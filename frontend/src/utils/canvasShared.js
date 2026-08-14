// canvasShared.js
// Shared constants and CSS for WorkflowCanvas + TopologyCanvas.
// All visual styles are centralized here and injected once by useCanvasSharedStyle.
// This is the SINGLE SOURCE OF TRUTH for canvas styling — no component-level CSS overrides.

// ========== 尺寸常量 ==========

export const GRID_SIZE = 20
export const NODE_GRID_W = 8
export const NODE_WIDTH = NODE_GRID_W * GRID_SIZE
export const NODE_MIN_HEIGHT = 72
export const PORT_RADIUS = 7
export const EDGE_STROKE_WIDTH = 2
export const EDGE_HOVER_STROKE_WIDTH = 4
export const EDGE_FLOW_DASH = '8 12'
export const EDGE_FLOW_DURATION = '0.8s'

// ========== 节点类型配置 ==========

export const NODE_TYPE_CONFIG = {
    click:            { color: '#409eff', icon: 'MousePointerClick', label: '点击动作' },
    wait:             { color: '#e6a23c', icon: 'Timer',           label: '等待' },
    log:              { color: '#909399', icon: 'ScrollText',      label: '日志' },
    image_recognition:{ color: '#67c23a', icon: 'Image',           label: '图像识别' },
    ocr_recognition:  { color: '#9b59b6', icon: 'Type',            label: 'OCR 识别' },
    branch:           { color: '#f56c6c', icon: 'GitBranch',      label: '分支选择' },
    logic_check:      { color: '#fd7e14', icon: 'Filter',          label: '逻辑判断' },
    variable_op:      { color: '#17a2b8', icon: 'Variable',       label: '变量操作' },
    script_call:      { color: '#6f42c1', icon: 'Code',           label: '脚本调用' },
    set_window:       { color: '#20c997', icon: 'AppWindow',       label: '窗口设置' },
    page_state:       { color: '#4ed19c', icon: 'MapPin',          label: '页面状态' },
    smart_jump:       { color: '#ff6b6b', icon: 'Navigation',      label: '智能跳转' }
}

export const DEFAULT_NODE_CONFIG = {
    color: '#5a6478',
    icon: 'Square',
    label: '节点'
}

export function getNodeConfig(nodeType) {
    return NODE_TYPE_CONFIG[nodeType] || DEFAULT_NODE_CONFIG
}

// ========== 通用工具 ==========

export function snapToGrid(value, grid = GRID_SIZE) {
    return Math.round(value / grid) * grid
}

export function snapPositionToGrid(x, y, grid = GRID_SIZE) {
    return { x: snapToGrid(x, grid), y: snapToGrid(y, grid) }
}

// ========== 端口位置计算 ==========

/**
 * Compute the absolute pixel position of a given port on a node.
 * Layout model (industry standard):
 *   - entry (target) — left-middle: connection lands on the left side of node
 *   - success        — bottom-center: primary exit
 *   - failure        — right-middle: failure exit
 *   - exit_N / branch_N — right side, stacked by index
 */
export function getPortPosition(node, portType, _options = {}) {
    const x = node.position?.x || 0
    const y = node.position?.y || 0
    const w = node.size?.w || NODE_WIDTH
    const h = node.size?.h || NODE_MIN_HEIGHT

    switch (portType) {
        case 'entry':
            return { x, y: y + h / 2 }
        case 'success':
        case 'succ':
            return { x: x + w / 2, y: y + h }
        case 'failure':
        case 'fail':
            return { x: x + w, y: y + h / 2 }
        case 'exit':
        case 'exit_0':
            return { x: x + w, y: y + h / 2 }
        default: {
            if (portType.startsWith('branch_') || portType.startsWith('exit_')) {
                const idx = parseInt(portType.split('_')[1]) || 0
                const rowY = y + 42 + idx * 28
                const clampedY = Math.min(rowY, y + h - 16)
                return { x: x + w, y: clampedY }
            }
            return { x: x + w / 2, y: y + h }
        }
    }
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

// ========== 共享边 CSS ==========

export const SHARED_EDGE_CSS = `
.canvas-edges-layer {
    position: absolute;
    top: 0;
    left: 0;
    overflow: visible;
    pointer-events: none;
    width: 100%;
    height: 100%;
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

/* Edge label */
.edge-label {
    fill: #c4c9d4;
    font-size: 11px;
    pointer-events: none;
    paint-order: stroke;
    stroke: rgba(20, 22, 34, 0.92);
    stroke-width: 3px;
    stroke-linejoin: round;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-weight: 500;
    user-select: none;
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
    overflow: hidden;
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
    will-change: transform;
}

/* Grid background */
.grid-background {
    background-image:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
    background-size: ${GRID_SIZE}px ${GRID_SIZE}px;
    background-position: -1px -1px;
}

/* ---------- Node Card ---------- */
.canvas-node-card {
    --node-accent: #409eff;
    position: absolute;
    background: #1e2038;
    border: 1.5px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: visible;
    cursor: grab;
    user-select: none;
    transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.05s ease;
    box-shadow:
        0 4px 16px rgba(0, 0, 0, 0.4),
        0 0 0 1px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.04);
    display: flex;
    flex-direction: column;
    z-index: 2;
}
.canvas-node-card:active {
    cursor: grabbing;
}
.canvas-node-card:hover {
    border-color: rgba(78, 209, 156, 0.5);
    box-shadow:
        0 8px 28px rgba(0, 0, 0, 0.5),
        0 0 0 1px rgba(78, 209, 156, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
}
.canvas-node-card.is-selected {
    border: 2px solid #4ed19c;
    box-shadow:
        0 0 0 3px rgba(78, 209, 156, 0.3),
        0 8px 28px rgba(0, 0, 0, 0.45);
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
    padding: 8px 14px;
    border-radius: 12px 12px 0 0;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: linear-gradient(135deg, var(--node-accent) 0%, rgba(0, 0, 0, 0.35) 100%);
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    position: relative;
    flex-shrink: 0;
}
.node-header::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 0, 0, 0.4), transparent);
}
.node-header-left {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
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
.node-body {
    padding: 10px 14px;
    font-size: 11px;
    color: #c4c9d4;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: visible;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.015), rgba(0, 0, 0, 0.2));
    gap: 4px;
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
    background: rgba(0, 0, 0, 0.2);
    border-radius: 0 0 12px 12px;
}
.footer-tag {
    font-size: 10px;
    color: #8b93a7;
    background: rgba(255, 255, 255, 0.05);
    padding: 2px 7px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.04);
    font-weight: 500;
}

/* ---------- Ports / Handles ---------- */
.node-handle {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    cursor: crosshair;
    z-index: 8;
    border: 2px solid #12131e;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    box-sizing: border-box;
    background: #3a3d52;
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
    transform: scale(1.4);
    box-shadow: 0 0 12px rgba(78, 209, 156, 0.8);
    border-color: #ffffff;
    z-index: 10;
}

/* Entry port (left side) - gray, indicates where edges land */
.entry-handle {
    left: -7px;
    top: 50%;
    transform: translateY(-50%);
    cursor: default;
    background: #4a4d62;
    border: 2px solid #6b7090;
    z-index: 5;
}
.entry-handle:hover {
    transform: translateY(-50%) scale(1.15);
    box-shadow: 0 0 0 transparent;
    border-color: #6b7090;
    cursor: default;
}

/* Success port (bottom) - green, primary exit */
.succ-handle {
    bottom: -7px;
    left: 50%;
    transform: translateX(-50%);
    background: #4ed19c;
    border-color: #2a8565;
    box-shadow: 0 0 0 1px rgba(78, 209, 156, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3);
}
.succ-handle:hover {
    background: #5de0a9;
    box-shadow: 0 0 12px rgba(78, 209, 156, 0.9);
}

/* Failure port (right) - red, failure exit */
.fail-handle {
    right: -7px;
    top: 50%;
    transform: translateY(-50%);
    background: #f56c6c;
    border-color: #a03838;
    box-shadow: 0 0 0 1px rgba(245, 108, 108, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3);
}
.fail-handle:hover {
    background: #ff7878;
    box-shadow: 0 0 12px rgba(245, 108, 108, 0.9);
}

/* Exit ports (right side, stacked) - green */
.exit-handle {
    right: -7px;
    transform: translateY(-50%);
    background: #4ed19c;
    border-color: #2a8565;
    box-shadow: 0 0 0 1px rgba(78, 209, 156, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3);
}
.exit-handle:hover {
    background: #5de0a9;
    box-shadow: 0 0 12px rgba(78, 209, 156, 0.9);
}

/* Branch node: failure port repositions to avoid overlap with branch exits */
.canvas-node-card:has(.branch-candidates-list) .fail-handle {
    top: auto !important;
    bottom: 12px !important;
    transform: none !important;
}

/* ---------- Breakpoint / Debug ---------- */
.node-breakpoint-gutter {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 4px;
    cursor: pointer;
    user-select: none;
    border-radius: 50%;
    transition: background-color 0.15s;
}
.node-breakpoint-gutter:hover {
    background: rgba(255, 255, 255, 0.15);
}
.node-breakpoint-gutter .bp-dot {
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #e5484d;
    box-shadow: 0 0 8px rgba(229, 72, 77, 0.85), inset 0 -2px 0 rgba(0, 0, 0, 0.25);
}
.node-breakpoint-gutter.active {
    background: rgba(229, 72, 77, 0.18);
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
.branch-candidates-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    padding: 2px 0;
    overflow: visible;
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
    padding: 5px 10px;
    font-size: 11px;
    min-height: 26px;
    overflow: visible;
    z-index: 2;
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
.branch-handle {
    right: -18px;
    top: 50%;
    transform: translateY(-50%);
    background: #4ed19c;
    z-index: 10;
}
.empty-cand-placeholder {
    font-size: 11px;
    color: #6b7280;
    text-align: center;
    padding: 10px 0;
    font-style: italic;
}

/* ---------- Image Node ---------- */
.node-image-embedded {
    position: relative;
    width: 100%;
    height: 100%;
    background: rgba(18, 19, 28, 0.8);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    min-height: 60px;
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
    right: 16px;
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
