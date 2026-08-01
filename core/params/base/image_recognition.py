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
                "options": [
                    {"value": "fullwindow", "label": "全屏"},
                    {"value": "recorded", "label": "录入区域"},
                    {"value": "custom", "label": "自定义"}
                ],
                "default": "fullwindow",
                "label": "搜索区域类型"
            },
            "region_value": {
                "type": "list_int4",
                "default": [0, 0, 0, 0],
                "label": "区域坐标 (x,y,w,h)",
                "visible_if": {
                    "field": "region_type",
                    "operator": "ne",
                    "value": "fullwindow"
                }
            },
            "region_is_relative": {
                "type": "bool",
                "default": True,
                "label": "相对窗口",
                "visible_if": {
                    "field": "region_type",
                    "operator": "ne",
                    "value": "fullwindow"
                }
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
                "options": [
                    {"value": "noop", "label": "无操作"},
                    {"value": "click_center", "label": "点击图片中心"}
                ],
                "default": "click_center",
                "label": "成功操作"
            },
            "on_success": {
                "type": "dict",
                "label": "成功跳转",   # ← 修正
                "sub": {
                    "jump_type": {
                        "type": "select",
                        "options": [
                            {"value": "next", "label": "下一个节点"},
                            {"value": "node", "label": "跳转节点"},
                            {"value": "task", "label": "跳转任务"},
                            {"value": "end", "label": "结束流程"}
                        ],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target_task": {
                        "type": "select",
                        "options": [],
                        "label": "目标任务",
                        "default": "",
                        "visible_if": {
                            "field": "jump_type",
                            "operator": "eq",
                            "value": "task"
                        }
                    },
                    "target_node": {
                        "type": "select",
                        "options": [],
                        "label": "目标节点",
                        "default": "",
                        "visible_if": {
                            "field": "jump_type",
                            "operator": "in",
                            "value": ["node", "task"]
                        }
                    }
                }
            },
            "on_failure": {
                "type": "dict",
                "label": "失败跳转",
                "sub": {
                    "jump_type": {
                        "type": "select",
                        "options": [
                            {"value": "next", "label": "下一个节点"},
                            {"value": "node", "label": "跳转节点"},
                            {"value": "task", "label": "跳转任务"},
                            {"value": "end", "label": "结束流程"}
                        ],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target_task": {
                        "type": "select",
                        "options": [],
                        "label": "目标任务",
                        "default": "",
                        "visible_if": {
                            "field": "jump_type",
                            "operator": "eq",
                            "value": "task"
                        }
                    },
                    "target_node": {
                        "type": "select",
                        "options": [],
                        "label": "目标节点",
                        "default": "",
                        "visible_if": {
                            "field": "jump_type",
                            "operator": "in",
                            "value": ["node", "task"]
                        }
                    }
                }
            }
        }
    }
}