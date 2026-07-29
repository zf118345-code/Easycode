PARAM_DEFINITIONS = {
    "image_recognition": {
        "label": "图像识别",
        "params": {
            "image_source": {
                "type": "file",
                "label": "模板图片",
                "default": ""
            },
            "region_type": {
                "type": "select",
                "options": ["fullwindow", "recorded", "custom"],
                "default": "fullwindow",
                "label": "搜索区域类型"
            },
            "region_value": {
                "type": "list_int4",
                "default": [0, 0, 0, 0],
                "label": "区域坐标 (x,y,w,h)"
            },
            "region_is_relative": {
                "type": "bool",
                "default": True,
                "label": "相对窗口"
            },
            "threshold": {
                "type": "int",
                "default": 85,
                "min": 0,
                "max": 100,
                "label": "匹配阈值"
            },
            "timeout": {
                "type": "int",
                "default": 3000,
                "min": 100,
                "max": 30000,
                "label": "超时时间(ms)"
            },
            "gray_scale": {
                "type": "bool",
                "default": False,
                "label": "灰度匹配"
            },
            "on_success_action": {
                "type": "select",
                "options": ["noop", "click_center"],
                "default": "noop",
                "label": "成功操作"
            },
            "on_success": {
                "type": "dict",
                "label": "成功跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "select",
                        "options": [],
                        "label": "目标",
                        "default": ""
                    },
                    "target_node": {
                        "type": "select",
                        "options": [],
                        "label": "目标节点",
                        "default": ""
                    }
                }
            },
            "on_failure": {
                "type": "dict",
                "label": "失败跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "select",
                        "options": [],
                        "label": "目标",
                        "default": ""
                    },
                    "target_node": {
                        "type": "select",
                        "options": [],
                        "label": "目标节点",
                        "default": ""
                    }
                }
            }
        }
    }
}