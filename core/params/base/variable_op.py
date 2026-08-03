# core/params/base/variable_op.py

PARAM_DEFINITIONS = {
    "variable_op": {
        "label": "变量操作",
        "params": {
            "var_name": {
                "type": "str",
                "default": "",
                "label": "目标变量名 (如: run_count)"
            },
            "op_type": {
                "type": "select",
                "options": [
                    {"value": "set", "label": "赋值 (=)"},
                    {"value": "add", "label": "加法 (+)"},
                    {"value": "sub", "label": "减法 (-)"},
                    {"value": "mul", "label": "乘法 (*)"},
                    {"value": "div", "label": "除法 (/)"},
                    {"value": "clear", "label": "清空变量"}
                ],
                "default": "set",
                "label": "操作类型"
            },
            "value": {
                "type": "str",
                "default": "",
                "label": "操作数值/表达式",
                "visible_if": {
                    "field": "op_type",
                    "operator": "ne",
                    "value": "clear"
                }
            }
        }
    }
}