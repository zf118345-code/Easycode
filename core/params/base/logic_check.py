# core/params/base/logic_check.py

PARAM_DEFINITIONS = {
    'logic_check': {
        'label': '逻辑判断',
        'params': {
            'timeout': {'type': 'int', 'default': 3000, 'label': '匹配超时时长', 'suffix': 'ms', 'min': 0, 'step': 500},
            'logic_mode': {
                'type': 'select',
                'options': [
                    {'value': 'or', 'label': '任意一个满足 (OR)'},
                    {'value': 'and', 'label': '全部达成才满足 (AND)'},
                ],
                'default': 'or',
                'label': '判定组合逻辑',
            },
            'conditions': {'type': 'condition_list_editor', 'default': [], 'label': '判定条件列表'},
            'on_success': {
                'type': 'dict',
                'label': '成功跳转 (逻辑组合满足时)',
                'sub': {
                    'target_task': {'type': 'select', 'options': [], 'label': '目标任务', 'default': ''},
                    'target_node': {'type': 'select', 'options': [], 'label': '目标节点', 'default': ''},
                },
            },
            'on_failure': {
                'type': 'dict',
                'label': '失败跳转 (逻辑组合不满足时)',
                'sub': {
                    'target_task': {'type': 'select', 'options': [], 'label': '目标任务', 'default': ''},
                    'target_node': {'type': 'select', 'options': [], 'label': '目标节点', 'default': ''},
                },
            },
        },
    }
}
