# core/params/base/ocr_recognition.py

PARAM_DEFINITIONS = {
    "ocr_recognition": {
        "label": "文字识别 (OCR)",
        "params": {
            "region_value": {
                "type": "list_int4_picker",
                "default": [0, 0, 0, 0],
                "label": "自定义识别范围 [X, Y, W, H]"
            },
            "gray_scale": {
                "type": "bool",
                "default": True,
                "label": "开启灰度/二值化增强 (提升复杂背景对比度)"
            },
            "gray_threshold": {
                "type": "int",
                "default": 127,
                "label": "二值化灰度阈值 (0-255，调节至文字最清晰)",
                "min": 0,
                "max": 255,
                "step": 1,
                "visible_if": {
                    "field": "gray_scale",
                    "operator": "eq",
                    "value": True
                }
            },
            "save_to_var": {
                "type": "str",
                "default": "",
                "label": "保存识别文本到变量 (如: coin_num)"
            },
            "timeout": {
                "type": "int",
                "default": 3000,
                "label": "超时时间 (ms)",
                "min": 100,
                "step": 100
            },
            "on_success_action": {
                "type": "select",
                "options": [
                    {"value": "noop", "label": "无操作"},
                    {"value": "click_center", "label": "点击识别区域中心"}
                ],
                "default": "noop",
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