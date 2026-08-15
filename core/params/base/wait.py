# core/params/base/wait.py

PARAM_DEFINITIONS = {
    'wait': {
        'label': '等待',
        'modes': ['workflow', 'topology'],
        'params': {
            'seconds': {
                'type': 'float',
                'default': 1.0,
                'min': 0,
                'max': 60,
                'label': '等待时长',
                'suffix': '秒',  # ⚡ 增加单位后缀
            },
            },
    }
}
