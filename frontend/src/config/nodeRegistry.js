// frontend/src/config/nodeRegistry.js
// 统一节点注册表：流程（workflow）与拓扑（topology）两模式共用的一套可配置节点定义。
// 数据来源分层：
//   - label / modes（可用画布白名单）：以后端 /api/params 配置为准（单一数据源，部署可配）；
//   - icon / color / content（外观与内容区渲染规则）：保留前端（icon 是组件引用、content 是渲染规则）。
// 前端内置表仅作兜底（后端配置未加载/测试环境），后端配置优先。
//
// content 规则（null = 内容区高度为 0）：
//   { kind: 'image', minHeight }            模板缩略图（宽高比保持，最小高度 minHeight）
//   { kind: 'ocr', minHeight }              模板缩略图 + 识别配置行（最小高度 minHeight）
//   { kind: 'branch-candidates', rowHeight, rowGap, rowPadding } 候选列表（每候选一行）
//   { kind: 'page-info', lineHeight, rowPadding } 页面特征/出口信息行（有才显示）

export const NODE_REGISTRY = {
    click:             { label: '鼠标点击',       icon: 'MousePointerClick', color: '#409eff', modes: ['workflow', 'topology'], content: null },
    wait:              { label: '等待',           icon: 'Timer',             color: '#e6a23c', modes: ['workflow', 'topology'], content: null },
    log:               { label: '日志输出',       icon: 'ScrollText',        color: '#909399', modes: ['workflow'],            content: null },
    image_recognition: { label: '图像识别',       icon: 'Image',             color: '#67c23a', modes: ['workflow', 'topology'], content: { kind: 'image', minHeight: 80 } },
    ocr_recognition:   { label: '文字识别 (OCR)', icon: 'Type',              color: '#9b59b6', modes: ['workflow', 'topology'], content: { kind: 'ocr', minHeight: 60 } },
    branch:            { label: '分支选择',       icon: 'GitBranch',         color: '#f56c6c', modes: ['workflow'],            content: { kind: 'branch-candidates', rowHeight: 24, rowGap: 4, rowPadding: 12 } },
    logic_check:       { label: '逻辑判断',       icon: 'Filter',            color: '#fd7e14', modes: ['workflow'],            content: null },
    variable_op:       { label: '变量操作',       icon: 'Variable',          color: '#17a2b8', modes: ['workflow'],            content: null },
    script_call:       { label: '调用脚本',       icon: 'Code',              color: '#6f42c1', modes: ['workflow'],            content: null },
    set_window:        { label: '窗口设置',       icon: 'AppWindow',         color: '#20c997', modes: ['workflow'],            content: null },
    control:           { label: '控件操作',       icon: 'ScanSearch',        color: '#00bcd4', modes: ['workflow'],            content: null },
    page_state:        { label: '页面状态',       icon: 'MapPin',            color: '#4ed19c', modes: ['topology'],            content: { kind: 'page-info', lineHeight: 20, rowPadding: 12, exitRowHeight: 24, exitRowGap: 4 } },
    smart_jump:        { label: '智能跳转',       icon: 'Navigation',        color: '#ff6b6b', modes: ['workflow'],            content: null }
}

export const DEFAULT_NODE_CONFIG = {
    color: '#5a6478',
    icon: 'Square',
    label: '节点'
}

/**
 * 节点外观配置：label 优先后端 /api/params 定义（单一数据源），icon/color 用前端表
 * @param {string} nodeType
 * @param {Object} backendDefs 后端参数定义（projectStore.paramsDefinitions，可选）
 */
export function getNodeConfig(nodeType, backendDefs) {
    const cfg = NODE_REGISTRY[nodeType] || DEFAULT_NODE_CONFIG
    const backend = backendDefs && backendDefs[nodeType]
    if (!backend) return cfg
    return {
        ...cfg,
        label: backend.label || cfg.label
    }
}

/**
 * 某画布模式可用的节点类型映射 { type: label }（菜单/新建节点用）
 * modes 与 label 以后端 /api/params 配置为准，前端表兜底；后端新增类型自动出现在白名单
 * @param {string} mode 'workflow' | 'topology'
 * @param {Object} [backendDefs] 后端参数定义（projectStore.paramsDefinitions）
 */
export function getNodeTypesForMode(mode, backendDefs) {
    const result = {}
    const types = new Set([
        ...Object.keys(NODE_REGISTRY),
        ...Object.keys(backendDefs || {})
    ])
    for (const type of types) {
        const backend = backendDefs && backendDefs[type]
        const cfg = NODE_REGISTRY[type]
        const modes = backend?.modes || cfg?.modes
        if (!modes || !modes.includes(mode)) continue
        result[type] = backend?.label || cfg?.label || type
    }
    return result
}

/** 节点类型的内容区展示规则；无内容返回 null */
export function getNodeContentSpec(nodeType) {
    const cfg = NODE_REGISTRY[nodeType]
    if (!cfg || !cfg.content) return null
    return cfg.content
}

/** 内容区实际占用的信息行数/行数（与 CanvasNodeCard 渲染规则一一对应）
 *  @param {number} [dynamicCount] 动态端口数量（page_state 出口行数 = bound + pending，由画布边推导） */
export function estimateNodeContentHeight(node, dynamicCount = 0) {
    const nodeType = node?.type || node?.node_type
    const spec = getNodeContentSpec(nodeType)
    if (!spec) return 0

    if (spec.kind === 'image' || spec.kind === 'ocr') {
        return spec.minHeight
    }
    if (spec.kind === 'branch-candidates') {
        const count = node?.params?.candidates?.length || 0
        const rows = Math.max(count, 1)   // 空态「未配置分流条件」占位一行
        return rows * spec.rowHeight + Math.max(0, rows - 1) * spec.rowGap + spec.rowPadding
    }
    if (spec.kind === 'page-info') {
        // 页面节点卡片只展示出口行（含虚线占位）；特征详情在属性面板查看
        const rows = Math.max(dynamicCount || 0, 0)
        if (rows > 0) {
            return spec.rowPadding + rows * spec.exitRowHeight + Math.max(0, rows - 1) * spec.exitRowGap
        }
        return 0
    }
    return 0
}
