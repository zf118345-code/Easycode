PARAM_DEFINITIONS = {
    "set_window": {
        "label": "设置窗口",
        "params": {
            "title": {
                "type": "str",
                "default": "",
                "label": "窗口标题"
            },
            "is_emulator": {
                "type": "bool",
                "default": False,
                "label": "模拟器模式"
            },
            "device_id": {
                "type": "str",
                "default": "",
                "label": "设备 ID"
            },
            "content_offset": {
                "type": "dict",
                "label": "内容裁剪",
                "sub": {
                    "top": {"type": "int", "default": 0, "label": "上"},
                    "bottom": {"type": "int", "default": 0, "label": "下"},
                    "left": {"type": "int", "default": 0, "label": "左"},
                    "right": {"type": "int", "default": 0, "label": "右"}
                }
            },
            "activate": {
                "type": "bool",
                "default": True,
                "label": "激活窗口"
            },
            "android_width": {
                "type": "int",
                "default": 0,
                "label": "Android 宽度"
            },
            "android_height": {
                "type": "int",
                "default": 0,
                "label": "Android 高度"
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
    },
    "resize_window": {
        "label": "调整窗口大小",
        "params": {
            "target_content_width": {
                "type": "int",
                "default": 1280,
                "label": "目标内容宽度"
            },
            "target_content_height": {
                "type": "int",
                "default": 720,
                "label": "目标内容高度"
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
    },
    "reset_window": {
        "label": "重置窗口",
        "params": {}
    }
}