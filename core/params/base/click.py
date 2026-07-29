PARAM_DEFINITIONS = {
    "click": {
        "label": "鼠标点击",
        "params": {
            "position": {
                "type": "list_int2",
                "default": [0, 0],
                "label": "点击位置"
            },
            "is_relative": {
                "type": "bool",
                "default": True,
                "label": "相对窗口"
            },
            "button": {
                "type": "select",
                "options": ["left", "right", "middle"],
                "default": "left",
                "label": "鼠标按钮"
            }
        }
    }
}