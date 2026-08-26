PARAM_DEFINITIONS = {
    'drag': {
        'label': '拖拽 / 长按',
        'modes': ['workflow', 'topology'],
        'params': {
            'action': {
                'type': 'select', 'default': 'drag', 'label': '操作',
                'options': [{'value': 'drag', 'label': '拖拽'}, {'value': 'long_press', 'label': '长按'}],
            },
            'path_points': {
                'type': 'gesture_path', 'label': '手势路径',
                'default': [
                    {'position': [384, 270], 'move_ms': 0, 'hold_ms': 0},
                    {'position': [576, 270], 'move_ms': 300, 'hold_ms': 0},
                ],
                'min_points': 2, 'max_points': 32,
                'help': '拖拽可添加途径点，整条路径只按下一次并在终点松开；长按只使用第一个点。',
            },
            'long_press_ms': {'type': 'int', 'default': 800, 'min': 1, 'max': 60000, 'step': 10, 'label': '长按时长', 'suffix': 'ms', 'visible_if': {'field': 'action', 'operator': 'eq', 'value': 'long_press'}},
            'release_wait_ms': {'type': 'int', 'default': 100, 'min': 0, 'max': 60000, 'step': 10, 'label': '释放后等待', 'suffix': 'ms'},
            'easing': {
                'type': 'select', 'default': 'linear', 'label': '移动曲线',
                'options': [{'value': 'linear', 'label': '匀速'}, {'value': 'ease_in_out', 'label': '平滑加减速'}],
            },
            'button': {
                'type': 'select', 'default': 'left', 'label': 'PC鼠标按键',
                'options': [{'value': 'left', 'label': '左键'}, {'value': 'right', 'label': '右键'}, {'value': 'middle', 'label': '中键'}],
            },
            'input_mode': {
                'type': 'select', 'default': 'background', 'label': 'PC输入方式',
                'options': [{'value': 'background', 'label': '后台优先（推荐）'}, {'value': 'physical', 'label': '物理输入'}],
            },
            'position_reference_size': {'type': 'list_int2', 'default': [960, 540], 'hidden': True},
            'coordinate_space': {'type': 'str', 'default': 'workspace_px', 'hidden': True},
        },
    }
}
