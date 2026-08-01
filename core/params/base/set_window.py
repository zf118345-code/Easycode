# core/params/base/set_window.py

PARAM_DEFINITIONS = {
    "set_window": {
        "label": "设置工作窗口",
        "params": {
            "work_mode": {
                "type": "select",
                "options": [
                    {"value": "window", "label": "指定窗口/模拟器"},
                    {"value": "desktop", "label": "全桌面模式"}
                ],
                "default": "window",
                "label": "工作模式"
            },
            "title": {
                "type": "window_select",  # 升级为可自动拉取+手写的窗口选择器
                "default": "",
                "label": "窗口标题",
                "visible_if": {
                    "field": "work_mode",
                    "operator": "eq",
                    "value": "window"
                }
            },
            "is_emulator": {
                "type": "bool",
                "default": False,
                "label": "模拟器模式",
                "visible_if": {
                    "field": "work_mode",
                    "operator": "eq",
                    "value": "window"
                }
            },
            "content_offset": {
                "type": "dict",
                "label": "内容裁剪(T,B,L,R)",
                "sub": {
                    "top": {"type": "int", "default": 0, "label": "上"},
                    "bottom": {"type": "int", "default": 0, "label": "下"},
                    "left": {"type": "int", "default": 0, "label": "左"},
                    "right": {"type": "int", "default": 0, "label": "右"}
                }
            },
            "target_content_width": {
                "type": "int",
                "default": 0,
                "label": "目标内容宽度(0不修改)",
                "visible_if": {
                    "field": "work_mode",
                    "operator": "eq",
                    "value": "window"
                }
            },
            "target_content_height": {
                "type": "int",
                "default": 0,
                "label": "目标内容高度(0不修改)",
                "visible_if": {
                    "field": "work_mode",
                    "operator": "eq",
                    "value": "window"
                }
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