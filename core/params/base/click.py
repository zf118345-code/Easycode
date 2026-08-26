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
            'position_reference_size': {'type': 'list_int2', 'default': [0, 0], 'hidden': True},
            'coordinate_space': {'type': 'str', 'default': 'workspace_px', 'hidden': True},
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
            'input_mode': {
                'type': 'select',
                'options': [
                    {'value': 'background', 'label': '后台优先（推荐）'},
                    {'value': 'physical', 'label': '物理鼠标（需项目授权）'},
                ],
                'default': 'background',
                'label': 'PC 点击方式',
                'help': '默认绝不移动物理鼠标。物理模式只有在项目设置允许回退时才能使用；模拟器始终强制ADB。',
            },
            'verification_mode': {
                'type': 'select',
                'options': [
                    {'value': 'none', 'label': '不验证（最快）'},
                    {'value': 'frame_change', 'label': '验证画面发生变化'},
                ],
                'default': 'none',
                'label': '点击后置验证',
                'help': '验证仅证明画面有明显变化。高速识图点击应继续使用“等待出现/消失”等更强的节点语义。',
            },
            'verification_timeout_ms': {
                'type': 'int', 'default': 600, 'min': 50, 'max': 10000, 'label': '验证超时 (ms)',
                'visible_when': {'verification_mode': 'frame_change'},
            },
            },
    }
}
