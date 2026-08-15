# core/params/base/log.py

PARAM_DEFINITIONS = {
    'log': {
        'label': '日志输出',
        'modes': ['workflow'],
        'params': {
            'message': {
                'type': 'textarea',  # ⚡ 修正：改为 textarea 多行文本框，支持任意文本与 {var_name} 变量拼接
                'default': '',
                'label': '日志内容',
                'placeholder': '支持普通文本与变量拼接，如: 当前运行到第 {numrun} 次，数值为 {newnum}',
                'rows': 3,
            },
            },
    }
}
