# core/params/base/image_recognition.py

PARAM_DEFINITIONS = {
    "image_recognition": {
        "label": "图像识别",
        "params": {
            "image_source": {
                "type": "file",
                "default": "",
                "label": "模板图片"
            },
            "threshold": {
                "type": "int",
                "default": 85,
                "label": "匹配阈值 (%)",
                "min": 1,
                "max": 100
            },
            "timeout": {
                "type": "int",
                "default": 3000,
                "label": "超时时间 (ms)",
                "min": 100,
                "step": 100
            },
            "gray_scale": {
                "type": "bool",
                "default": True,
                "label": "灰度匹配 (推荐)"
            },
            "region_type": {
                "type": "select",
                "options": [
                    {"value": "fullwindow", "label": "整个工作区"},
                    {"value": "recorded", "label": "录入区域"},
                    {"value": "custom", "label": "自定义区域"}
                ],
                "default": "fullwindow",
                "label": "搜索区域"
            },
            "region_value": {
                "type": "list_int4_picker",
                "default": [0, 0, 0, 0],
                "label": "区域坐标 [X, Y, W, H]",
                "visible_if": {
                    "field": "region_type",
                    "operator": "in",
                    "value": ["recorded", "custom"]
                }
            },
            "on_success_action": {
                "type": "select",
                "options": [
                    {"value": "noop", "label": "无操作"},
                    {"value": "click_center", "label": "点击目标中心"}
                ],
                "default": "click_center",
                "label": "识别成功后操作"
            },
            "on_success": {
                "type": "dict",
                "label": "成功跳转",
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