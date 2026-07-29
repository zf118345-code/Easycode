PARAM_DEFINITIONS = {
    "branch": {
        "label": "分支选择",
        "params": {
            "candidates": {
                "type": "list_dict",
                "label": "候选模板",
                "sub": {
                    "template": {"type": "str", "default": "", "label": "模板名称"},
                    "target": {"type": "str", "default": "", "label": "跳转目标"},
                    "threshold": {"type": "int", "default": 85, "label": "匹配阈值"}
                }
            },
            "region": {
                "type": "dict",
                "label": "搜索区域",
                "sub": {
                    "type": {
                        "type": "select",
                        "options": ["fullwindow", "recorded"],
                        "default": "fullwindow",
                        "label": "区域类型"
                    },
                    "value": {
                        "type": "list_int4",
                        "default": [0, 0, 0, 0],
                        "label": "区域坐标"
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
    }
}