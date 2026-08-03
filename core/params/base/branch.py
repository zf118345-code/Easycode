# core/params/base/branch.py

PARAM_DEFINITIONS = {
    "branch": {
        "label": "分支选择",
        "params": {
            "best_match_mode": {
                "type": "bool",
                "default": True,
                "label": "最高置信度竞态 (比对所有图片取最高分分支)"
            },
            "candidates": {
                "type": "branch_candidate_editor",
                "default": [],
                "label": "多分支判定列表"
            },
            "on_failure": {
                "type": "dict",
                "label": "兜底失败跳转 (全不满足时)",
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