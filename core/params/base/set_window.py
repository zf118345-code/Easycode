# core/params/base/set_window.py

PARAM_DEFINITIONS = {
    'set_window': {
        'label': '设置工作窗口',
        'modes': ['workflow'],
        'params': {
            'work_mode': {
                'type': 'select',
                'options': [
                    {'value': 'window', 'label': '指定窗口/模拟器'},
                    {'value': 'desktop', 'label': '全桌面模式'},
                ],
                'default': 'window',
                'label': '工作模式',
            },
            'title': {
                'type': 'window_select',
                'default': '',
                'label': '窗口标题',
                'visible_if': {'field': 'work_mode', 'operator': 'eq', 'value': 'window'},
            },
            'is_emulator': {
                'type': 'bool',
                'default': False,
                'label': '模拟器模式',
                'visible_if': {'field': 'work_mode', 'operator': 'eq', 'value': 'window'},
            },
            'content_offset': {
                'type': 'margin4',  # ⚡ 改为专属类型 margin4
                'default': [0, 0, 0, 0],
                'label': '内容裁剪 (T, B, L, R)',
            },
            'target_content_size': {
                'type': 'size2',  # ⚡ 改为专属类型 size2
                'default': [0, 0],
                'label': '目标尺寸 (W, H)',
                'visible_if': {'field': 'work_mode', 'operator': 'eq', 'value': 'window'},
            },
            },
    }
}
