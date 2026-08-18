# core/params/base/logic_check.py

from .defaults import NODE_DEFAULTS

PARAM_DEFINITIONS = {
    'logic_check': {
        'label': '逻辑判断',
        'modes': ['workflow'],
        'params': {
            'timeout': {'type': 'int', 'default': NODE_DEFAULTS['timeout'], 'label': '匹配超时时长', 'suffix': 'ms', 'min': 0, 'step': 500},
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
            },
    }
}
