# core/params/base/branch.py

PARAM_DEFINITIONS = {
    "branch": {
        "label": "分支选择",
        "params": {
            "match_strategy": {
                "type": "select",
                "label": "分流策略",
                "options": [
                    {"value": "first", "label": "顺序优先 (命中即跳)"},
                    {"value": "best", "label": "分数优先 (全项最高分)"}
                ],
                "default": "first"
            },
            "candidates": {
                "type": "branch_candidate_editor",
                "default": [],
                "label": "多分支判定列表"
            },
            "timeout": {
                "type": "int",
                "default": 3000,
                "label": "匹配超时时长",
                "suffix": "ms",
                "min": 0,
                "step": 500
            },
            "on_failure": {
                "type": "dict",
                "label": "Else 兜底跳转 (所有分支均未满足时)",
                "sub": {
                    "target_task": {
                        "type": "select",
                        "options": [],
                        "label": "目标任务",
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