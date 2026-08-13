// canvasShared.js
// 两个画布共享的常量、样式、碰撞检测、箭头方向计算
// 统一 WorkflowCanvas 和 TopologyCanvas 的视觉与交互

// ========== 共享常量 ==========

export const GRID_SIZE = 20
export const NODE_GRID_W = 8           // 节点宽度 = 8 * 20 = 160px
export const NODE_WIDTH = NODE_GRID_W * GRID_SIZE  // 160
export const NODE_MIN_HEIGHT = 60
export const PORT_RADIUS = 6
export const EDGE_STROKE_WIDTH = 2.5
export const EDGE_FLOW_DASH = '8 16'
export const EDGE_FLOW_DURATION = '0.8s'
export const ARROW_SIZE = 8

// ========== 节点类型配色（统一两画布） ==========

export const NODE_TYPE_CONFIG = {
    click: { color: '#409eff', icon: 'MousePointerClick', label: '点击' },
    wait: { color: '#e6a23c', icon: 'Timer', label: '等待' },
    log: { color: '#909399', icon: 'ScrollText', label: '日志' },
    image_recognition: { color: '#67c23a', icon: 'Image', label: '图像识别' },
    ocr_recognition: { color: '#9b59b6', icon: 'Type', label: 'OCR' },
    branch: { color: '#f56c6c', icon: 'GitBranch', label: '条件分支' },
    logic_check: { color: '#fd7e14', icon: 'Filter', label: '逻辑判断' },
    variable_op: { color: '#17a2b8', icon: 'Variable', label: '变量操作' },
    script_call: { color: '#6f42c1', icon: 'Code', label: '脚本调用' },
    set_window: { color: '#20c997', icon: 'AppWindow', label: '窗口设置' },
    page_state: { color: '#4ed19c', icon: 'MapPin', label: '页面状态' },
    smart_jump: { color: '#ff6b6b', icon: 'Navigation', label: '智能跳转' },
}

// 默认节点配置
export const DEFAULT_NODE_CONFIG = {
    color: '#409eff',
    icon: 'Square',
    label: '节点'
}

export function getNodeConfig(nodeType) {
    return NODE_TYPE_CONFIG[nodeType] || DEFAULT_NODE_CONFIG
}

// ========== 网格对齐 ==========

export function snapToGrid(value, grid = GRID_SIZE) {
    return Math.round(value / grid) * grid
}

export function snapPositionToGrid(x, y, grid = GRID_SIZE) {
    return {
        x: snapToGrid(x, grid),
        y: snapToGrid(y, grid)
    }
}

// ========== 端口位置计算（统一两画布的端口锚点） ==========

/**
 * 计算节点端口的世界坐标
 * @param {Object} node - 节点对象 { position: {x, y}, size: {w, h} }
 * @param {String} portType - 端口类型: 'success' | 'failure' | 'branch_N' | 'entry' | 'exit_N'
 * @param {Object} options - { branchIndex, exitIndex }
 * @returns {{x: number, y: number}}
 */
export function getPortPosition(node, portType, options = {}) {
    const x = node.position?.x || 0
    const y = node.position?.y || 0
    const w = node.size?.w || NODE_WIDTH
    const h = node.size?.h || NODE_MIN_HEIGHT

    switch (portType) {
        case 'entry':
            // 入口：左侧垂直居中
            return { x, y: y + h / 2 }

        case 'success':
            // 成功出口：底部中心
            return { x: x + w / 2, y: y + h }

        case 'failure':
            // 失败出口：右侧底部
            return { x: x + w, y: y + h - 18 }

        case 'exit':
        case 'exit_0':
            // 拓扑出口：右侧居中
            return { x: x + w, y: y + h / 2 }

        default:
            // branch_N 或 exit_N
            if (portType.startsWith('branch_') || portType.startsWith('exit_')) {
                const idx = parseInt(portType.split('_')[1]) || 0
                // 分支/出口：右侧，按索引垂直排列
                return { x: x + w, y: y + 42 + idx * 28 }
            }
            // 默认：底部中心
            return { x: x + w / 2, y: y + h }
    }
}

// ========== 箭头方向计算 ==========

/**
 * 根据路径最后两点的向量计算箭头方向
 * @returns {'up' | 'down' | 'left' | 'right'}
 */
export function getArrowDirection(points) {
    if (!points || points.length < 2) return 'right'
    const last = points[points.length - 1]
    const prev = points[points.length - 2]
    const dx = last.x - prev.x
    const dy = last.y - prev.y

    if (Math.abs(dx) > Math.abs(dy)) {
        return dx > 0 ? 'right' : 'left'
    } else {
        return dy > 0 ? 'down' : 'up'
    }
}

// ========== 碰撞检测与推挤（从 WorkflowCanvas 提取） ==========

/**
 * AABB 碰撞检测
 */
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

/**
 * 迭代式碰撞推挤
 * 当节点重叠时，按中心连线方向推开周围节点
 * @param {Array} nodes - 所有节点
 * @param {Object} draggedNode - 被拖拽的节点
 * @param {Number} maxIterations - 最大迭代次数
 * @returns {Array} 被推挤的节点列表（需要保存位置）
 */
export function resolveCollisionsAndPushOthers(nodes, draggedNode, maxIterations = 15) {
    const pushed = new Set()
    const MIN_GAP = GRID_SIZE * 2  // 节点间最小间距

    for (let iter = 0; iter < maxIterations; iter++) {
        let hasCollision = false

        for (const other of nodes) {
            if (other === draggedNode || other.node_id === draggedNode.node_id) continue
            if (pushed.has(other.node_id)) continue

            // 扩展 draggedNode 的边界用于间距检测
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

                // 计算推挤方向（中心连线）
                const dcx = (draggedNode.position?.x || 0) + (draggedNode.size?.w || NODE_WIDTH) / 2
                const dcy = (draggedNode.position?.y || 0) + (draggedNode.size?.h || NODE_MIN_HEIGHT) / 2
                const ocx = (other.position?.x || 0) + (other.size?.w || NODE_WIDTH) / 2
                const ocy = (other.position?.y || 0) + (other.size?.h || NODE_MIN_HEIGHT) / 2

                const dx = ocx - dcx
                const dy = ocy - dcy
                const dist = Math.sqrt(dx * dx + dy * dy) || 1

                // 沿推挤方向移动到刚好不重叠
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

// ========== SVG Marker 定义（统一 8 方向箭头） ==========

export const ARROW_MARKERS_SVG = `
  <defs>
    <!-- 成功连线箭头（绿色） -->
    <marker id="arrow-succ-right" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#4ed19c" />
    </marker>
    <marker id="arrow-succ-left" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 10 0 L 0 5 L 10 10 z" fill="#4ed19c" />
    </marker>
    <marker id="arrow-succ-up" viewBox="0 0 10 10" refX="5" refY="1" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 10 L 5 0 L 10 10 z" fill="#4ed19c" />
    </marker>
    <marker id="arrow-succ-down" viewBox="0 0 10 10" refX="5" refY="9" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 5 10 L 10 0 z" fill="#4ed19c" />
    </marker>
    <!-- 失败连线箭头（红色） -->
    <marker id="arrow-fail-right" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#f56c6c" />
    </marker>
    <marker id="arrow-fail-left" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 10 0 L 0 5 L 10 10 z" fill="#f56c6c" />
    </marker>
    <marker id="arrow-fail-up" viewBox="0 0 10 10" refX="5" refY="1" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 10 L 5 0 L 10 10 z" fill="#f56c6c" />
    </marker>
    <marker id="arrow-fail-down" viewBox="0 0 10 10" refX="5" refY="9" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 5 10 L 10 0 z" fill="#f56c6c" />
    </marker>
    <!-- 默认箭头（灰色） -->
    <marker id="arrow-default" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#909399" />
    </marker>
  </defs>
`

/**
 * 根据 portType 和方向获取 marker ID
 */
export function getMarkerId(portType, direction) {
    const isSuccess = portType === 'success' || portType === 'exit' || portType.startsWith('exit_')
    const isFailure = portType === 'failure'
    const prefix = isFailure ? 'arrow-fail' : (isSuccess ? 'arrow-succ' : 'arrow-default')

    if (prefix === 'arrow-default') return 'arrow-default'
    return `${prefix}-${direction}`
}

// ========== 共享 CSS 样式字符串 ==========

export const SHARED_EDGE_CSS = `
  .edge-path {
    fill: none;
    stroke-width: ${EDGE_STROKE_WIDTH};
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: stroke 0.2s, stroke-width 0.2s;
    pointer-events: stroke;
    cursor: pointer;
  }
  .edge-path.is-success { stroke: #4ed19c; }
  .edge-path.is-failure { stroke: #f56c6c; }
  .edge-path.is-default { stroke: #909399; }
  .edge-path.is-selected {
    stroke: #ffffff;
    stroke-width: 4;
    filter: drop-shadow(0 0 6px rgba(255,255,255,0.6));
  }
  .edge-path:hover {
    stroke-width: 4;
    filter: drop-shadow(0 0 4px rgba(255,255,255,0.4));
  }
  .edge-flow-path {
    fill: none;
    stroke: rgba(255, 255, 255, 0.7);
    stroke-width: 2;
    stroke-dasharray: ${EDGE_FLOW_DASH};
    animation: edgeFlow ${EDGE_FLOW_DURATION} linear infinite;
    pointer-events: none;
  }
  @keyframes edgeFlow {
    from { stroke-dashoffset: 24; }
    to { stroke-dashoffset: 0; }
  }
`

export const SHARED_NODE_CSS = `
  .canvas-node-card {
    position: absolute;
    background: var(--el-fill-color-blank, #1e1f2b);
    border: 1px solid var(--el-border-color, rgba(255,255,255,0.08));
    border-radius: 8px;
    overflow: visible;
    cursor: move;
    user-select: none;
    transition: box-shadow 0.2s, border-color 0.2s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }
  .canvas-node-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    border-color: rgba(78, 209, 156, 0.4);
  }
  .canvas-node-card.is-selected {
    border-color: #4ed19c;
    box-shadow: 0 0 0 2px rgba(78, 209, 156, 0.3), 0 4px 16px rgba(0,0,0,0.3);
  }
  .canvas-node-card.is-disabled {
    opacity: 0.5;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 8px 8px 0 0;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .node-body {
    padding: 8px 10px;
    font-size: 11px;
    color: var(--el-text-color-regular, #a0a1ab);
  }
  .node-port {
    position: absolute;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid #1e1f2b;
    cursor: crosshair;
    z-index: 10;
    transition: transform 0.15s;
  }
  .node-port:hover {
    transform: scale(1.4);
  }
  .node-port.port-success {
    background: #4ed19c;
  }
  .node-port.port-failure {
    background: #f56c6c;
  }
  .node-port.port-entry {
    background: #909399;
  }
  .node-port.port-exit {
    background: #4ed19c;
  }
  .grid-background {
    background-image:
      linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
    background-size: ${GRID_SIZE}px ${GRID_SIZE}px;
  }
`