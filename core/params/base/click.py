# core/params/base/click.py

PARAM_DEFINITIONS = {
    'click': {
        'label': '鼠标点击',
        'params': {
            'position': {
                'type': 'list_int2_picker',  # 带取点按钮的 X, Y 坐标对
                'default': [0, 0],
                'label': '点击位置 (X, Y)',
            },
            'button': {
                'type': 'select',
                'options': [
                    {'value': 'left', 'label': '左键'},
                    {'value': 'right', 'label': '右键'},
                    {'value': 'middle', 'label': '中键'},
                ],
                'default': 'left',
                'label': '鼠标按键',
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
