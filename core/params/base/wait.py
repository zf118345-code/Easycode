# core/params/base/wait.py

PARAM_DEFINITIONS = {
    'wait': {
        'label': '等待',
        'params': {
            'seconds': {
                'type': 'float',
                'default': 1.0,
                'min': 0,
                'max': 60,
                'label': '等待时长',
                'suffix': '秒',  # ⚡ 增加单位后缀
            },
            'on_success': {
                'type': 'dict',
                'label': '成功跳转 (下一步走向)',
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
