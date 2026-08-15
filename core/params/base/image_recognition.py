# core/params/base/image_recognition.py

PARAM_DEFINITIONS = {
    'image_recognition': {
        'label': '图像识别',
        'modes': ['workflow', 'topology'],
        'params': {
            'image_source': {'type': 'file', 'default': '', 'label': '模板图片'},
            'gray_scale': {'type': 'bool', 'default': True, 'label': '去除背景干扰 (灰度处理)'},
            'gray_threshold': {
                'type': 'int',
                'default': 127,
                'label': '二值化灰度阈值',
                'min': 0,
                'max': 255,
                'step': 1,
                'visible_if': {'field': 'gray_scale', 'operator': 'eq', 'value': True},
            },
            'threshold': {
                'type': 'int',
                'default': 85,
                'label': '匹配相似度',
                'suffix': '%',  # ⚡ 增加单位后缀，驱动 ControlNumber 正确显示 0-99%
                'min': 1,
                'max': 100,
            },
            'timeout': {
                'type': 'int',
                'default': 3000,
                'label': '匹配超时时长',
                'suffix': 'ms',  # ⚡ 增加单位后缀
                'min': 100,
                'step': 100,
            },
            'region_type': {
                'type': 'select',
                'options': [
                    {'value': 'fullwindow', 'label': '整个工作面板'},
                    {'value': 'recorded', 'label': '录制时的坐标区域'},
                    {'value': 'custom', 'label': '自定义区域'},
                ],
                'default': 'fullwindow',
                'label': '匹配区域',
            },
            'region_value': {
                'type': 'list_int4_picker',
                'default': [0, 0, 0, 0],
                'label': '匹配区域坐标',
                'visible_if': {'field': 'region_type', 'operator': 'in', 'value': ['recorded', 'custom']},
            },
            'on_success_action': {
                'type': 'select',
                'options': [{'value': 'noop', 'label': '无操作'}, {'value': 'click_center', 'label': '点击目标中心'}],
                'default': 'click_center',
                'label': '识别成功后操作',
            },
            },
    }
}
