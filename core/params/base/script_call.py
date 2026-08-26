# core/params/base/script_call.py

PARAM_DEFINITIONS = {
    'script_call': {
        'label': '调用能力',
        'modes': ['workflow', 'topology'],
        'params': {
            'capability_id': {
                'type': 'capability_select',
                'default': '',
                'label': '能力函数',
                'help': '选择内置、项目级或共享能力。契约定义输入、输出、权限和版本。',
            },
            'capability_version': {
                'type': 'str',
                'default': '',
                'label': '固定版本',
                'placeholder': '留空使用最新版本',
            },
            'input_bindings': {
                'type': 'capability_input_bindings',
                'default': [],
                'label': '能力输入',
                'help': '支持常量、$var.name、$ctx.name 与 =表达式。',
            },
            'output_bindings': {
                'type': 'capability_output_bindings',
                'default': [],
                'label': '结果映射',
                'help': '把能力 data 中的结果写入 $var.name 或 $ctx.name。',
            },
            'timeout_ms': {
                'type': 'int', 'default': 30000, 'min': 1, 'max': 86400000,
                'label': '调用超时', 'suffix': 'ms',
            },
            'retry_count': {
                'type': 'int', 'default': 0, 'min': 0, 'max': 20,
                'label': '失败重试次数',
                'help': '只有声明为幂等的能力允许自动重试。',
            },
            'retry_interval_ms': {
                'type': 'int', 'default': 200, 'min': 0, 'max': 60000,
                'label': '重试间隔', 'suffix': 'ms',
            },
        },
    }
}
