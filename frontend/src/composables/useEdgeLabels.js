// frontend/src/composables/useEdgeLabels.js
// 画布节点多条件连线标签可视化
import { computed } from 'vue'

/**
 * 连线标签可视化 composable
 * @param {Object} options - { edges, getNodeById }
 *   edges: ref/computed of edge array
 *   getNodeById: (nodeId) => node object with position
 */
export function useEdgeLabels(options = {}) {
    const { edges, getNodeById } = options

    // 标签颜色映射（按 source_port 类型）
    const PORT_COLORS = {
        success: '#4ed19c',
        failure: '#f56c6c',
        exit: '#4ed19c',
        default: '#909399'
    }

    // 标签文本映射
    const PORT_LABELS = {
        success: '成功',
        failure: '失败',
        exit: '出口',
        default: ''
    }

    /**
     * 计算连线中点
     */
    function getMidpoint(x1, y1, x2, y2) {
        return { x: (x1 + x2) / 2, y: (y1 + y2) / 2 }
    }

    /**
     * 计算标签渲染数据
     */
    const labelData = computed(() => {
        if (!edges || !edges.value) return []

        return edges.value.map(edge => {
            const sourceNode = getNodeById(edge.source_node || edge.source)
            const targetNode = getNodeById(edge.target_node || edge.target)

            if (!sourceNode || !targetNode) return null

            const sx = sourceNode.position?.x || 0
            const sy = sourceNode.position?.y || 0
            const sw = sourceNode.size?.w || 160
            const sh = sourceNode.size?.h || 60
            const tx = targetNode.position?.x || 0
            const ty = targetNode.position?.y || 0

            // 起点偏移：从源节点边缘出发
            const startX = sx + sw / 2
            const startY = sy + sh

            // 终点偏移：目标节点顶部中心
            const endX = tx + (targetNode.size?.w || 160) / 2
            const endY = ty

            const mid = getMidpoint(startX, startY, endX, endY)

            // 确定标签文本
            const port = edge.source_port || edge.source_exit || 'default'
            let labelText = edge.label || ''
            if (!labelText) {
                labelText = PORT_LABELS[port] || ''
            }

            // 如果有条件，添加条件摘要
            if (edge.condition && typeof edge.condition === 'object') {
                const condType = edge.condition.type || ''
                if (condType && !labelText) {
                    labelText = condType
                }
            }

            if (!labelText) return null

            // 估算标签尺寸
            const labelWidth = Math.max(labelText.length * 7 + 12, 36)
            const labelHeight = 18

            return {
                edgeId: edge.edge_id,
                x: mid.x - labelWidth / 2,
                y: mid.y - labelHeight / 2,
                width: labelWidth,
                height: labelHeight,
                text: labelText,
                color: PORT_COLORS[port] || PORT_COLORS.default,
                bgColor: 'rgba(29, 30, 48, 0.9)',
                port
            }
        }).filter(Boolean)
    })

    /**
     * 生成 SVG 标签元素
     * 用于在 template 中渲染
     */
    const svgLabels = computed(() => {
        return labelData.value.map(label => ({
            ...label,
            rectProps: {
                x: label.x,
                y: label.y,
                width: label.width,
                height: label.height,
                rx: 4,
                fill: label.bgColor,
                stroke: label.color,
                'stroke-width': 1
            },
            textProps: {
                x: label.x + label.width / 2,
                y: label.y + label.height / 2 + 4,
                'text-anchor': 'middle',
                fill: label.color,
                'font-size': 11,
                'font-weight': 500
            }
        }))
    })

    return {
        labelData,
        svgLabels,
        PORT_COLORS,
        PORT_LABELS
    }
}
