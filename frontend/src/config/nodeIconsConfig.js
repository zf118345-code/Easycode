// frontend/src/config/nodeIconsConfig.js
// 兼容现有面板导入路径；真实定义只来自 nodeRegistry + Lucide 组件注册表。
import { Square } from 'lucide-vue-next'
import { DEFAULT_NODE_CONFIG, NODE_REGISTRY } from '@/config/nodeRegistry'
import { NODE_ICON_MAP as LUCIDE_ICON_MAP } from '@/utils/nodeIcons'

// 统一的节点类型 -> 图标组件映射
export const NODE_ICON_MAP = Object.fromEntries(
    Object.entries(NODE_REGISTRY).map(([type, config]) => [type, LUCIDE_ICON_MAP[config.icon] || Square])
)

// 统一的节点类型 -> 颜色映射
export const NODE_COLOR_MAP = Object.fromEntries(
    Object.entries(NODE_REGISTRY).map(([type, config]) => [type, config.color])
)

// 统一的节点类型 -> 标签映射
export const NODE_LABEL_MAP = Object.fromEntries(
    Object.entries(NODE_REGISTRY).map(([type, config]) => [type, config.label])
)

// 默认值
export const DEFAULT_NODE_ICON = Square
export const DEFAULT_NODE_COLOR = DEFAULT_NODE_CONFIG.color
export const DEFAULT_NODE_LABEL = DEFAULT_NODE_CONFIG.label

// 辅助函数
export function getNodeIcon(nodeType) {
    return NODE_ICON_MAP[nodeType] || DEFAULT_NODE_ICON
}

export function getNodeColor(nodeType) {
    return NODE_COLOR_MAP[nodeType] || DEFAULT_NODE_COLOR
}

export function getNodeLabel(nodeType) {
    return NODE_LABEL_MAP[nodeType] || DEFAULT_NODE_LABEL
}

// 获取节点完整配置
export function getNodeFullConfig(nodeType) {
    return {
        icon: getNodeIcon(nodeType),
        color: getNodeColor(nodeType),
        label: getNodeLabel(nodeType)
    }
}
