PARAM_DEFINITIONS = {
    'call_function': {
        'label': '调用函数',
        'modes': ['workflow', 'function'],
        'params': {
            'function_id': {
                'type': 'function_select', 'default': '', 'label': '目标函数',
                'help': '函数只调用一次。需要重复时，请在外层使用循环节点。',
            },
            'input_bindings': {
                'type': 'function_input_bindings', 'default': [], 'label': '参数绑定',
                'help': '传入常量、表达式、全局变量、上下文或当前函数局部值。',
            },
            'output_bindings': {
                'type': 'function_output_bindings', 'default': [], 'label': '输出写回',
                'help': '把函数输出写入 $var、$ctx 或当前函数的 $local；参数只读。',
            },
        },
    },
}

