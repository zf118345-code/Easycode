# core/variables/types/string.py
from typing import Dict, Any
from core.variables.base import BaseVariableType, VariableTypeRegistry


@VariableTypeRegistry.register("string")
class StringVariableType(BaseVariableType):
    label = "文本 (String)"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "str_op": {
                "type": "select",
                "label": "操作方式",
                "options": [
                    {"value": "set", "label": "直接赋值"},
                    {"value": "append", "label": "尾部追加"},
                    {"value": "replace", "label": "文本替换"}
                ],
                "default": "set",
                "visible_if": {"field": "var_type", "operator": "eq", "value": "string"}
            },
            "str_value": {
                "type": "variable",
                "label": "操作文本/变量",
                "default": "",
                "visible_if": {
                    "field": "var_type", "operator": "eq", "value": "string",
                    "sub_field": "str_op", "sub_operator": "in", "sub_value": ["set", "append"]
                }
            },
            "replace_find": {
                "type": "string",
                "label": "查找目标文本",
                "default": "",
                "visible_if": {
                    "field": "var_type", "operator": "eq", "value": "string",
                    "sub_field": "str_op", "sub_operator": "eq", "sub_value": "replace"
                }
            },
            "replace_with": {
                "type": "string",
                "label": "替换为新内容",
                "default": "",
                "visible_if": {
                    "field": "var_type", "operator": "eq", "value": "string",
                    "sub_field": "str_op", "sub_operator": "eq", "sub_value": "replace"
                }
            }
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        str_op = params.get("str_op", "set")
        curr_str = str(old_val) if old_val is not None else ""

        if str_op == "set":
            return str(cls.resolve_val(context, params.get("str_value", "")))

        elif str_op == "append":
            append_val = str(cls.resolve_val(context, params.get("str_value", "")))
            return curr_str + append_val

        elif str_op == "replace":
            find_txt = str(params.get("replace_find", ""))
            with_txt = str(params.get("replace_with", ""))
            return curr_str.replace(find_txt, with_txt)

        return curr_str