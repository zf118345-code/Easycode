PARAM_DEFINITIONS = {
    'function_entry': {
        'label': '函数入口', 'modes': ['function'], 'params': {},
    },
    'function_return': {
        'label': '函数返回', 'modes': ['function'],
        'params': {
            'outcome_id': {'type': 'function_outcome_select', 'default': '', 'label': '返回结果'},
            'output_bindings': {'type': 'function_return_bindings', 'default': [], 'label': '返回值'},
        },
    },
}

