# core/params/base/script_call.py

PARAM_DEFINITIONS = {
    "script_call": {
        "label": "调用脚本",
        "params": {
            "script": {
                "type": "str",  # ⚡ 修正：改为常规字符串输入框
                "default": "",
                "label": "脚本名称",
                "placeholder": "请输入脚本文件名称，如 demo_script.py"
            },
            "entry": {
                "type": "str",  # ⚡ 修正：改为常规字符串输入框
                "default": "",
                "label": "入口函数",
                "placeholder": "请输入入口函数名，如 main"
            },
            "return_on_complete": {
                "type": "bool",
                "default": False,
                "label": "完成后返回"
            }
        }
    }
}