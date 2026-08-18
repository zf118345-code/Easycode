// frontend/src/testFixtures/controlSchema.js
// ⚡ control 节点 schema fixture：与后端 core/params/base/control.py 对齐（两端同步维护）
// 供链路冒烟 / ParamRenderer / NodeInspectorPanel 测试共用
export const CONTROL_SCHEMA = {
    label: '控件操作',
    modes: ['workflow'],
    params: {
        action: {
            type: 'select', label: '操作方式', default: 'click',
            options: ['click', 'double_click', 'hover', 'input_text', 'get_text', 'exists']
                .map(v => ({ value: v, label: v }))
        },
        by: {
            type: 'select', label: '查找方式', default: 'uia_name',
            options: ['uia_name', 'uia_type', 'uia_id', 'uia_class', 'class_name', 'text', 'control_type']
                .map(v => ({ value: v, label: v }))
        },
        target: { type: 'str', label: '控件标识', default: '' },
        window_title: { type: 'str', label: '目标窗口标题', default: '' },
        index: {
            type: 'int', label: '匹配序号', default: 0, min: 0,
            help: [
                '0 = 第一个匹配的控件。',
                '同一窗口存在多个同类控件时，可指定第 N 个（0 开始）。'
            ]
        },
        text_input: {
            type: 'str', label: '输入内容', default: '',
            visible_if: { field: 'action', operator: 'eq', value: 'input_text' }
        },
        save_to_var: {
            type: 'str', label: '保存结果到变量', default: '',
            visible_if: { field: 'action', operator: 'in', value: ['get_text', 'exists'] }
        },
        timeout: { type: 'int', label: '查找超时时长', default: 3000, suffix: 'ms' }
    }
}
