# core/params/base/branch.py

from .defaults import NODE_DEFAULTS

PARAM_DEFINITIONS = {
    'branch': {
        'label': '分支选择',
        'modes': ['workflow'],
        'params': {
            'match_strategy': {
                'type': 'select',
                'label': '分流策略',
                'options': [
                    {'value': 'first', 'label': '顺序优先 (命中即跳)'},
                    {'value': 'best', 'label': '分数优先 (全项最高分)'},
                ],
                'default': 'first',
            },
            'candidates': {'type': 'branch_candidate_editor', 'default': [], 'label': '多分支判定列表'},
            'timeout': {'type': 'int', 'default': NODE_DEFAULTS['timeout'], 'label': '匹配超时时长', 'suffix': 'ms', 'min': 0, 'step': 500},
            },
    }
}
