// frontend/src/utils/captureNode.js
// 控件捕获 → 控件节点参数推导（纯函数，CanvasPage 使用，便于测试）
// 与后端 capture_mode.build_control_params 逻辑保持一致

/**
 * 捕获控件信息 → 控件操作节点查找参数（by/target 自动选择 UIA 查找方式）
 * @param {Object} info 捕获信息（name/control_type/automation_id/class_name）
 * @returns {{by: string, target: string}}
 */
export function buildControlParamsFromInfo(info) {
    if (!info || typeof info !== 'object') return { by: 'uia_name', target: '' }
    const name = String(info.name || '').trim()
    if (name) return { by: 'uia_name', target: name }
    const ctype = String(info.control_type || '').trim()
    if (ctype) return { by: 'uia_type', target: ctype }
    const aid = String(info.automation_id || '').trim()
    if (aid) return { by: 'uia_id', target: aid }
    const cls = String(info.class_name || '').trim()
    if (cls) return { by: 'uia_class', target: cls }
    return { by: 'uia_name', target: '' }
}

/** 生成节点名（控件_名称，截断 12 字符） */
export function buildControlNodeName(info) {
    if (!info || typeof info !== 'object') return '控件_未命名'
    const name = String(info.name || '').trim()
    const ctype = String(info.control_type || '').trim()
    const target = name || ctype || '未命名'
    return `控件_${target.slice(0, 12)}`
}

/**
 * 捕获的完整控件信息 → 分行展示文本（只读 textarea 用，兼容 UIA 与 Win32 两种字段集）
 * @param {Object} info 捕获信息（control_info 隐藏字段）
 * @param {string} target 兜底控件名称（无 control_info 的旧节点）
 * @returns {string} 如 "控件名称：确定\n控件类型：button\n自动化ID：btn_1\n…"
 */
export function formatControlInfo(info, target = '') {
    const rows = []
    const push = (label, value) => {
        const v = String(value ?? '').trim()
        if (v) rows.push(`${label}：${v}`)
    }
    if (!info || typeof info !== 'object') {
        if (target) rows.push(`控件名称：${target}`)
        return rows.join('\n')
    }
    push('控件名称', info.name || info.text)          // UIA: name；Win32: text
    push('控件类型', info.control_type)
    push('自动化ID', info.automation_id)               // UIA 特有
    push('类名', info.class_name)
    push('窗口标题', info.window_title)                // UIA 顶层窗口标题
    const top = info.top_level_window                  // Win32 嵌套的顶层窗口信息
    if (top) push('窗口标题', top.text || top.title)
    push('句柄', info.hwnd)
    if (info.is_enabled !== undefined) push('可用状态', info.is_enabled ? '可用' : '禁用')
    if (Array.isArray(info.rect) && info.rect.length === 4) {
        push('坐标', `[${info.rect[0]}, ${info.rect[1]}, ${info.rect[2]}, ${info.rect[3]}]`)
    }
    if (!rows.length && target) rows.push(`控件名称：${target}`)
    return rows.join('\n')
}
