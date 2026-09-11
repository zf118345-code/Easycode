const TYPE_LABELS: Record<string, string> = {
    any: '任意值', string: '文本', int64: '整数', float64: '小数', percentage: '百分比', bool: '是 / 否',
    duration: '持续时间', date: '日期', datetime: '日期与时间', time: '时间', timezone: '时区', point: '坐标', rect: '区域', size: '尺寸',
    path: '路径', relative_path: '项目内路径', url: '网址', gesture_path: '手势路径', key_chord: '快捷键', json: 'JSON 数据', json_value: 'JSON 数据', message_value: '消息内容',
    target_ref: '操作目标', target_info: '目标信息', instance_ref: 'Player 实例', window_ref: '窗口', window_selector: '窗口选择器', window_status: '窗口状态',
    application_ref: '应用', application_run_ref: '已启动的应用', application_exit_result: '应用退出结果', frame_ref: '画面', color: '颜色',
    asset_ref: '资源', file_ref: '文件', directory_ref: '文件夹',
    control_ref: '控件', control_selector: '控件选择器', image_match: '图像匹配结果', received_message: '收到的消息',
    control_status: '控件状态', filesystem_filter: '文件筛选条件', filesystem_entry: '文件项',
    http_body: '请求正文', http_pair: 'HTTP 字段', http_response: 'HTTP 响应', http_download_result: '下载结果', multipart_field: '上传字段',
    image_click_loop_result: '连续点击结果', image_click_condition_result: '点击并验证结果', ocr_preprocess: '识字预处理', ocr_result: '识字结果',
    message_batch: '消息批次', message_cancel_result: '取消消息结果', message_read_wait_result: '消息读取结果',
    tree_delete_report: '文件夹删除结果', tree_operation_report: '文件夹操作结果',
    error: '异常信息', null: '空值', unit: '无返回值', void: '无返回值',
}

function genericBody(typeId: string, prefix: string): string | null {
    return typeId.startsWith(`${prefix}<`) && typeId.endsWith('>') ? typeId.slice(prefix.length + 1, -1) : null
}

function splitTopLevel(body: string): string[] {
    const parts: string[] = []
    let depth = 0
    let start = 0
    for (let index = 0; index < body.length; index += 1) {
        if (body[index] === '<') depth += 1
        else if (body[index] === '>') depth -= 1
        else if (body[index] === ',' && depth === 0) {
            parts.push(body.slice(start, index).trim())
            start = index + 1
        }
    }
    parts.push(body.slice(start).trim())
    return parts
}

export function programTypeDisplayName(typeId: string): string {
    if (TYPE_LABELS[typeId]) return TYPE_LABELS[typeId]
    const optional = genericBody(typeId, 'optional')
    if (optional) return `可选的${programTypeDisplayName(optional)}`
    const list = genericBody(typeId, 'list')
    if (list) return `列表（${programTypeDisplayName(list)}）`
    const map = genericBody(typeId, 'map')
    if (map) {
        const [key = 'any', value = 'any'] = splitTopLevel(map)
        return `字典（${programTypeDisplayName(key)} → ${programTypeDisplayName(value)}）`
    }
    const asset = genericBody(typeId, 'asset_ref')
    if (asset) return asset === 'image' ? '图片资源' : '资源'
    if (genericBody(typeId, 'file_ref')) return '文件'
    if (genericBody(typeId, 'directory_ref')) return '文件夹'
    if (genericBody(typeId, 'enum')) return '可选项'
    if (genericBody(typeId, 'list_selector')) return '列表逐项处理'
    if (genericBody(typeId, 'map_selector')) return '字典逐项处理'
    return typeId
}
