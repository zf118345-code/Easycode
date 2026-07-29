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
                    "top": {
                        "type": "int",
                        "default": 0,
                        "label": "上"
                    },
                    "bottom": {
                        "type": "int",
                        "default": 0,
                        "label": "下"
                    },
                    "left": {
                        "type": "int",
                        "default": 0,
                        "label": "左"
                    },
                    "right": {
                        "type": "int",
                        "default": 0,
                        "label": "右"
                    }
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
            "on_success_jump": {
                "type": "dict",
                "label": "成功时跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "str",
                        "default": "",
                        "label": "目标 ID"
                    },
                    "target_node": {
                        "type": "str",
                        "default": "",
                        "label": "目标节点 ID"
                    }
                }
            },
            "on_failure_jump": {
                "type": "dict",
                "label": "失败时跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "str",
                        "default": "",
                        "label": "目标 ID"
                    },
                    "target_node": {
                        "type": "str",
                        "default": "",
                        "label": "目标节点 ID"
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
            "on_success_jump": {
                "type": "dict",
                "label": "成功时跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "str",
                        "default": "",
                        "label": "目标 ID"
                    },
                    "target_node": {
                        "type": "str",
                        "default": "",
                        "label": "目标节点 ID"
                    }
                }
            },
            "on_failure_jump": {
                "type": "dict",
                "label": "失败时跳转",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["next", "node", "task", "end"],
                        "default": "next",
                        "label": "跳转类型"
                    },
                    "target": {
                        "type": "str",
                        "default": "",
                        "label": "目标 ID"
                    },
                    "target_node": {
                        "type": "str",
                        "default": "",
                        "label": "目标节点 ID"
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