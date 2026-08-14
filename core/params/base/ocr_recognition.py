# core/params/base/ocr_recognition.py

PARAM_DEFINITIONS = {
    'ocr_recognition': {
        'label': '文字识别 (OCR)',
        'params': {
            'image_source': {'type': 'file', 'default': '', 'label': 'OCR 文字视角模板'},
            'gray_scale': {'type': 'bool', 'default': True, 'label': '去除背景干扰 (灰度处理)'},
            'gray_threshold': {
                'type': 'int',
                'default': 127,
                'label': '二值化灰度阈值 (0-255，调节至文字最清晰)',
                'min': 0,
                'max': 255,
                'step': 1,
                'visible_if': {'field': 'gray_scale', 'operator': 'eq', 'value': True},
            },
            'save_to_var': {
                'type': 'variable',
                'default': '',
                'label': '保存识别文本到变量',
                'placeholder': '请输入或选择变量名 (如: coin_num)',
            },
            'region_type': {
                'type': 'select',
                'options': [
                    {'value': 'fullwindow', 'label': '整个工作面板'},
                    {'value': 'recorded', 'label': '录制时的坐标区域'},
                    {'value': 'custom', 'label': '自定义区域'},
                ],
                'default': 'recorded',
                'label': '识别区域',
            },
            'region_value': {
                'type': 'list_int4_picker',
                'default': [0, 0, 0, 0],
                'label': '识别区域坐标 [X, Y, W, H]',
                'visible_if': {'field': 'region_type', 'operator': 'in', 'value': ['recorded', 'custom']},
            },
            'timeout': {
                'type': 'int',
                'default': 3000,
                'label': '超时时间',
                'suffix': 'ms',  # ⚡ 增加单位后缀
                'min': 100,
                'step': 100,
            },
            'on_success_action': {
                'type': 'select',
                'options': [
                    {'value': 'noop', 'label': '无操作'},
                    {'value': 'click_center', 'label': '点击识别区域中心'},
                ],
                'default': 'noop',
                'label': '识别成功后操作',
            },
            'on_success': {
                'type': 'dict',
                'label': '成功跳转',
                'sub': {
                    'jump_type': {
                        'type': 'select',
                        'options': [
                            {'value': 'next', 'label': '下一个节点'},
                            {'value': 'node', 'label': '跳转节点'},
                            {'value': 'task', 'label': '跳转任务'},
                            {'value': 'end', 'label': '结束流程'},
                        ],
                        'default': 'next',
                        'label': '跳转类型',
                    },
                    'target_task': {
                        'type': 'select',
                        'options': [],
                        'label': '目标任务',
                        'default': '',
                        'visible_if': {'field': 'jump_type', 'operator': 'eq', 'value': 'task'},
                    },
                    'target_node': {
                        'type': 'select',
                        'options': [],
                        'label': '目标节点',
                        'default': '',
                        'visible_if': {'field': 'jump_type', 'operator': 'in', 'value': ['node', 'task']},
                    },
                },
            },
            'on_failure': {
                'type': 'dict',
                'label': '失败跳转',
                'sub': {
                    'jump_type': {
                        'type': 'select',
                        'options': [
                            {'value': 'next', 'label': '下一个节点'},
                            {'value': 'node', 'label': '跳转节点'},
                            {'value': 'task', 'label': '跳转任务'},
                            {'value': 'end', 'label': '结束流程'},
                        ],
                        'default': 'next',
                        'label': '跳转类型',
                    },
                    'target_task': {
                        'type': 'select',
                        'options': [],
                        'label': '目标任务',
                        'default': '',
                        'visible_if': {'field': 'jump_type', 'operator': 'eq', 'value': 'task'},
                    },
                    'target_node': {
                        'type': 'select',
                        'options': [],
                        'label': '目标节点',
                        'default': '',
                        'visible_if': {'field': 'jump_type', 'operator': 'in', 'value': ['node', 'task']},
                    },
                },
            },
        },
    }
}
