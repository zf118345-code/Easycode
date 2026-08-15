// frontend/src/config/nodeIconsConfig.js
// 统一节点图标配置，消除多处图标映射重复
// 被 ProjectExplorerPanel / NodeListPanel / NodeInspectorPanel 等共用
import {
    MousePointerClick, Timer, ScrollText, Image, Type, GitBranch,
    Filter, Variable, Code, AppWindow, MapPin, Navigation, Square,
    // 旧版组件中使用过的别名图标（保持兼容）
    Clock, Target, FileSearch, SearchCheck, Binary, ListOrdered,
    FileCode, Compass, ScanText, Folder,
    Search, Share
} from 'lucide-vue-next'

// 统一的节点类型 -> 图标组件映射
export const NODE_ICON_MAP = {
    click: MousePointerClick,
    wait: Timer,
    log: ScrollText,
    image_recognition: Image,
    ocr_recognition: Type,
    branch: GitBranch,
    logic_check: Filter,
    variable_op: Variable,
    script_call: Code,
    set_window: AppWindow,
    page_state: MapPin,
    smart_jump: Navigation
}

// 统一的节点类型 -> 颜色映射
export const NODE_COLOR_MAP = {
    click: '#409eff',
    wait: '#e6a23c',
    log: '#909399',
    image_recognition: '#67c23a',
    ocr_recognition: '#9b59b6',
    branch: '#f56c6c',
    logic_check: '#fd7e14',
    variable_op: '#17a2b8',
    script_call: '#6f42c1',
    set_window: '#20c997',
    page_state: '#4ed19c',
    smart_jump: '#ff6b6b'
}

// 统一的节点类型 -> 标签映射
export const NODE_LABEL_MAP = {
    click: '点击',
    wait: '等待',
    log: '日志',
    image_recognition: '图像识别',
    ocr_recognition: 'OCR',
    branch: '条件分支',
    logic_check: '逻辑判断',
    variable_op: '变量操作',
    script_call: '脚本调用',
    set_window: '窗口设置',
    page_state: '页面状态',
    smart_jump: '智能跳转'
}

// 默认值
export const DEFAULT_NODE_ICON = Square
export const DEFAULT_NODE_COLOR = '#409eff'
export const DEFAULT_NODE_LABEL = '节点'

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
