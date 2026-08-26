PARAM_DEFINITIONS = {
    'text_input': {
        'label': '文本输入',
        'modes': ['workflow', 'topology'],
        'params': {
            'text': {
                'type': 'textarea',
                'default': '',
                'label': '输入内容',
                'placeholder': '支持 $var{name} / $ctx{name}',
            },
            'position': {
                'type': 'list_int2_picker',
                'default': [480, 270],
                'label': '输入位置',
                'help': '默认点击工作面板中心获取焦点；可直接用捕获模式替换为实际输入框坐标。',
            },
            'click_before': {'type': 'bool', 'default': True, 'label': '输入前点击聚焦'},
            'clear_before': {'type': 'bool', 'default': False, 'label': '输入前清空原内容'},
            'interval_ms': {'type': 'int', 'default': 0, 'min': 0, 'max': 5000, 'step': 10, 'label': '字符间隔', 'suffix': 'ms'},
            'submit_key': {
                'type': 'select',
                'default': 'none',
                'label': '输入后按键',
                'options': [
                    {'value': 'none', 'label': '无'},
                    {'value': 'enter', 'label': 'Enter'},
                    {'value': 'tab', 'label': 'Tab'},
                    {'value': 'escape', 'label': 'Esc'},
                ],
            },
            'sensitive': {'type': 'bool', 'default': False, 'label': '敏感内容（日志脱敏）'},
            'input_mode': {
                'type': 'select',
                'default': 'background',
                'label': 'PC输入方式',
                'options': [
                    {'value': 'background', 'label': '后台优先（推荐）'},
                    {'value': 'physical', 'label': '物理键盘（需项目授权）'},
                ],
            },
            'position_reference_size': {'type': 'list_int2', 'default': [960, 540], 'hidden': True},
            'coordinate_space': {'type': 'str', 'default': 'workspace_px', 'hidden': True},
        },
    }
}
