export const LOG_CATEGORY_OPTIONS = Object.freeze([
    { key: 'all', label: '全部' },
    { key: 'execution', label: '执行' },
    { key: 'node', label: '节点' },
    { key: 'vision', label: '识别' },
    { key: 'navigation', label: '导航' },
    { key: 'operation', label: '操作' },
    { key: 'data', label: '数据' },
    { key: 'issues', label: '问题' }
])

const VALID_CATEGORIES = new Set(LOG_CATEGORY_OPTIONS.map(item => item.key).filter(key => !['all', 'issues'].includes(key)))
const CATEGORY_MARKERS = Object.freeze([
    ['navigation', ['智能跳转', '弹窗处理', '寻路', '路径节点', '当前位置']],
    ['vision', ['页面状态', 'ocr', '图像识别', '识图', '模板匹配', '目标截图']],
    ['operation', ['目标绑定', '输入验证', '点击', '控件操作', 'set_window', '工作窗口', 'adb', '滚动', '滑动', '拖拽', '长按', '文本输入', '物理输入']],
    ['data', ['变量操作', '变量写入', '条件评估', '逻辑判断', 'branch', '分支', '调用能力', '能力 ', '脚本', '表达式']],
    ['node', ['node', '节点执行', '节点完成', '节点失败', '前置延迟', '等待 ']]
])
const DECORATIONS = ['✅', '❌', '⚠️', '⚠', '🎯', '🚀', '📋', '🔍', '📏', '💥', '🎉', '🔨', '♻️', '♻', '⚡', '🛑', '🏁', '⏱️', '▶️', '⏹️', '⏭️', '⏸️', '🤖', '📱', '🖥️', '🔄', '🔢', '📝', '⏰']

export const getLogText = item => {
    const raw = typeof item === 'object' && item !== null ? (item.message || JSON.stringify(item)) : String(item)
    return DECORATIONS.reduce((text, icon) => text.split(icon).join(''), raw).trimStart()
}

export const getLogTime = item => {
    if (typeof item === 'object' && item !== null) return item.time || 'INFO'
    return 'INFO'
}

export const getLogLevel = item => {
    const explicit = typeof item === 'object' && item !== null
        ? String(item.level || item.status || '').toLowerCase()
        : ''
    const raw = typeof item === 'object' && item !== null ? String(item.message || '') : String(item)
    if (['error', 'failed', 'failure'].includes(explicit) || /❌|💥|ERROR|失败|异常|终止/.test(raw)) return 'error'
    if (['warning', 'warn'].includes(explicit) || /⚠|WARNING|警告|提醒/.test(raw)) return 'warning'
    return 'info'
}

export const getLogCategory = item => {
    const explicit = typeof item === 'object' && item !== null ? String(item.category || '').toLowerCase() : ''
    if (VALID_CATEGORIES.has(explicit)) return explicit
    const text = getLogText(item).toLowerCase()
    for (const [category, markers] of CATEGORY_MARKERS) {
        if (markers.some(marker => text.includes(marker))) return category
    }
    return 'execution'
}

export const normalizeLogItem = (item, index = 0) => ({
    key: typeof item === 'object' && item !== null && (item._client_id != null || item.id != null)
        ? String(item._client_id ?? item.id)
        : `${getLogTime(item)}-${index}`,
    time: getLogTime(item),
    text: getLogText(item),
    level: getLogLevel(item),
    category: getLogCategory(item),
    raw: item
})

export const isLogInFilter = (log, filter) => {
    if (filter === 'all') return true
    if (filter === 'issues') return ['warning', 'error'].includes(log.level)
    return log.category === filter
}
