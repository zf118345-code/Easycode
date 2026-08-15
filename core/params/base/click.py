# core/params/base/click.py

PARAM_DEFINITIONS = {
    'click': {
        'label': '鼠标点击',
        'modes': ['workflow', 'topology'],
        'params': {
            'position': {
                'type': 'list_int2_picker',  # 带取点按钮的 X, Y 坐标对
                'default': [0, 0],
                'label': '点击位置 (X, Y)',
            },
            'button': {
                'type': 'select',
                'options': [
                    {'value': 'left', 'label': '左键'},
                    {'value': 'right', 'label': '右键'},
                    {'value': 'middle', 'label': '中键'},
                ],
                'default': 'left',
                'label': '鼠标按键',
            },
            },
    }
}
