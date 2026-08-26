PARAM_DEFINITIONS = {
    'scroll': {
        'label': '滚动',
        'modes': ['workflow', 'topology'],
        'params': {
            'gesture_mode': {
                'type': 'select', 'default': 'auto', 'label': '滚动方式',
                'options': [
                    {'value': 'auto', 'label': '自动（推荐）'},
                    {'value': 'wheel', 'label': 'PC滚轮'},
                    {'value': 'touch', 'label': '触控滑动（PC / Android）'},
                ],
                'help': '自动模式在PC使用后台滚轮，在Android使用连续触控手势。',
            },
            'direction': {
                'type': 'select', 'default': 'down', 'label': '浏览方向',
                'options': [
                    {'value': 'down', 'label': '向下浏览'}, {'value': 'up', 'label': '向上浏览'},
                    {'value': 'right', 'label': '向右浏览'}, {'value': 'left', 'label': '向左浏览'},
                    {'value': 'custom', 'label': '自定义触控路径'},
                ],
                'help': '这里描述内容的浏览方向；触控手势会自动换算为相反的手指移动方向。',
            },
            'position_mode': {
                'type': 'select', 'default': 'center', 'label': '起始位置',
                'options': [{'value': 'center', 'label': '工作面板中心'}, {'value': 'custom', 'label': '自定义坐标'}],
            },
            'position': {
                'type': 'list_int2_picker', 'default': [480, 270], 'label': '自定义起点',
                'visible_if': {'field': 'position_mode', 'operator': 'eq', 'value': 'custom'},
            },
            'end_position': {
                'type': 'list_int2_picker', 'default': [480, 54], 'label': '自定义终点',
                'visible_if': {'field': 'direction', 'operator': 'eq', 'value': 'custom'},
            },
            'distance_mode': {
                'type': 'select', 'default': 'percent', 'label': '触控距离',
                'options': [{'value': 'percent', 'label': '按工作面板比例'}, {'value': 'pixels', 'label': '固定像素'}],
                'visible_if': {'field': 'direction', 'operator': 'ne', 'value': 'custom'},
            },
            'distance_percent': {
                'type': 'int', 'default': 40, 'min': 1, 'max': 95, 'label': '距离比例', 'suffix': '%',
                'visible_if': {'field': 'distance_mode', 'operator': 'eq', 'value': 'percent'},
            },
            'distance_px': {
                'type': 'int', 'default': 300, 'min': 1, 'max': 10000, 'step': 10, 'label': '固定距离', 'suffix': 'px',
                'visible_if': {'field': 'distance_mode', 'operator': 'eq', 'value': 'pixels'},
            },
            'wheel_ticks': {'type': 'int', 'default': 3, 'min': 1, 'max': 100, 'label': '每次滚轮格数'},
            'duration_ms': {'type': 'int', 'default': 300, 'min': 0, 'max': 30000, 'step': 10, 'label': '触控移动时长', 'suffix': 'ms'},
            'release_mode': {
                'type': 'select', 'default': 'normal', 'label': '终点释放方式',
                'options': [{'value': 'normal', 'label': '立即释放'}, {'value': 'hold', 'label': '短暂停留后释放'}],
                'help': '短暂停留后释放可用于降低带惯性的列表滚动。',
            },
            'hold_after_ms': {
                'type': 'int', 'default': 120, 'min': 0, 'max': 10000, 'step': 10, 'label': '终点保持', 'suffix': 'ms',
                'visible_if': {'field': 'release_mode', 'operator': 'eq', 'value': 'hold'},
            },
            'easing': {
                'type': 'select', 'default': 'linear', 'label': '移动曲线',
                'options': [{'value': 'linear', 'label': '匀速'}, {'value': 'ease_in_out', 'label': '平滑加减速'}],
            },
            'termination_mode': {
                'type': 'select', 'default': 'fixed', 'label': '结束条件',
                'options': [
                    {'value': 'fixed', 'label': '固定次数'}, {'value': 'image_present', 'label': '图像出现'},
                    {'value': 'image_absent', 'label': '图像消失'}, {'value': 'page_present', 'label': '页面出现'},
                    {'value': 'expression', 'label': '表达式为真'},
                ],
            },
            'repeat_count': {'type': 'int', 'default': 1, 'min': 1, 'max': 1000, 'label': '滚动次数', 'visible_if': {'field': 'termination_mode', 'operator': 'eq', 'value': 'fixed'}},
            'max_repeat_count': {'type': 'int', 'default': 20, 'min': 1, 'max': 10000, 'label': '安全次数上限', 'visible_if': {'field': 'termination_mode', 'operator': 'ne', 'value': 'fixed'}},
            'timeout_ms': {'type': 'int', 'default': 10000, 'min': 100, 'max': 3600000, 'step': 100, 'label': '安全超时', 'suffix': 'ms', 'visible_if': {'field': 'termination_mode', 'operator': 'ne', 'value': 'fixed'}},
            'stop_image_source': {'type': 'file', 'default': '', 'label': '结束特征图片', 'visible_if': {'field': 'termination_mode', 'operator': 'in', 'value': ['image_present', 'image_absent']}},
            'stop_threshold': {'type': 'int', 'default': 85, 'min': 1, 'max': 100, 'label': '结束特征相似度', 'suffix': '%', 'visible_if': {'field': 'termination_mode', 'operator': 'in', 'value': ['image_present', 'image_absent']}},
            'stop_region_type': {
                'type': 'select', 'default': 'fullwindow', 'label': '结束特征区域',
                'options': [{'value': 'fullwindow', 'label': '整个工作面板'}, {'value': 'recorded', 'label': '录制区域'}, {'value': 'custom', 'label': '自定义区域'}],
                'visible_if': {'field': 'termination_mode', 'operator': 'in', 'value': ['image_present', 'image_absent']},
            },
            'stop_region_value': {'type': 'list_int4_picker', 'default': [0, 0, 0, 0], 'label': '结束特征范围', 'visible_if': {'field': 'stop_region_type', 'operator': 'in', 'value': ['recorded', 'custom']}},
            'stop_region_reference_size': {'type': 'list_int2', 'default': [0, 0], 'hidden': True},
            'stop_page_id': {'type': 'page_select', 'default': '', 'label': '目标页面', 'visible_if': {'field': 'termination_mode', 'operator': 'eq', 'value': 'page_present'}},
            'stop_expression': {'type': 'str', 'default': '', 'label': '结束表达式', 'placeholder': '$var{loaded} == true', 'visible_if': {'field': 'termination_mode', 'operator': 'eq', 'value': 'expression'}},
            'repeat_interval_ms': {'type': 'int', 'default': 150, 'min': 0, 'max': 60000, 'step': 10, 'label': '每次间隔', 'suffix': 'ms'},
            'post_wait_ms': {'type': 'int', 'default': 100, 'min': 0, 'max': 60000, 'step': 10, 'label': '结束后等待', 'suffix': 'ms'},
            'input_mode': {
                'type': 'select', 'default': 'background', 'label': 'PC输入方式',
                'options': [{'value': 'background', 'label': '后台优先（推荐）'}, {'value': 'physical', 'label': '物理输入'}],
            },
            'position_reference_size': {'type': 'list_int2', 'default': [960, 540], 'hidden': True},
            'coordinate_space': {'type': 'str', 'default': 'workspace_px', 'hidden': True},
        },
    }
}
