# core/params/base/wait.py

PARAM_DEFINITIONS = {
    'wait': {
        'label': '等待',
        'modes': ['workflow', 'topology'],
        'params': {
            'wait_mode': {
                'type': 'select',
                'default': 'duration',
                'label': '计时模式',
                'options': [
                    {'value': 'duration', 'label': '等待一段时间'},
                    {'value': 'until_datetime', 'label': '等待到指定日期时间'},
                    {'value': 'until_clock', 'label': '等待到下一次每日时刻'},
                ],
                'help': '所有模式都可被“停止任务”立即中断。',
            },
            'duration_ms': {
                'type': 'int',
                'default': 1000,
                'min': 0,
                'max': 604800000,
                'step': 100,
                'label': '等待时长',
                'suffix': 'ms',  # ⚡ 统一毫秒单位
                'visible_if': {'field': 'wait_mode', 'operator': 'eq', 'value': 'duration'},
            },
            'target_datetime': {
                'type': 'str',
                'default': '',
                'label': '目标日期时间',
                'placeholder': '2026-08-25 08:30:00 / $var{next_run_at}',
                'visible_if': {'field': 'wait_mode', 'operator': 'eq', 'value': 'until_datetime'},
            },
            'target_clock': {
                'type': 'str',
                'default': '00:00:00',
                'label': '每日时刻',
                'placeholder': '12:00:00 / $var{daily_clock}',
                'visible_if': {'field': 'wait_mode', 'operator': 'eq', 'value': 'until_clock'},
            },
            'poll_interval_ms': {
                'type': 'int',
                'default': 100,
                'min': 20,
                'max': 1000,
                'step': 20,
                'label': '停止响应间隔',
                'suffix': 'ms',
                'help': '越小停止响应越快，默认100ms已兼顾低占用。',
            },
        },
    }
}
