# core/params/base/wait.py

PARAM_DEFINITIONS = {
    'wait': {
        'label': '等待',
        'modes': ['workflow', 'topology'],
        'params': {
            'duration_ms': {
                'type': 'int',
                'default': 1000,
                'min': 0,
                'max': 600000,
                'step': 100,
                'label': '等待时长',
                'suffix': 'ms',  # ⚡ 统一毫秒单位
            },
            },
    }
}
