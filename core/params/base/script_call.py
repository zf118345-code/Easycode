PARAM_DEFINITIONS = {
    "script_call": {
        "label": "调用脚本",
        "params": {
            "script": {
                "type": "str",
                "default": "",
                "label": "脚本名称"
            },
            "entry": {
                "type": "str",
                "default": "",
                "label": "入口函数"
            },
            "return_on_complete": {
                "type": "bool",
                "default": False,
                "label": "完成后返回"
            }
        }
    }
}