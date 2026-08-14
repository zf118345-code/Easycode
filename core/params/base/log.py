# core/params/base/log.py

PARAM_DEFINITIONS = {
    'log': {
        'label': '日志输出',
        'params': {
            'message': {
                'type': 'textarea',  # ⚡ 修正：改为 textarea 多行文本框，支持任意文本与 {var_name} 变量拼接
                'default': '',
                'label': '日志内容',
                'placeholder': '支持普通文本与变量拼接，如: 当前运行到第 {numrun} 次，数值为 {newnum}',
                'rows': 3,
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
