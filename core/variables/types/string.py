# core/variables/types/string.py
from typing import Any

from core.variables.base import BaseVariableType, VariableTypeRegistry


@VariableTypeRegistry.register('string')
class StringVariableType(BaseVariableType):
    label = '文本 (String)'

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return {
            'str_value': {
                'type': 'str',
                'label': '操作文本/值（支持 {var} 变量）',
                'default': '',
                'placeholder': '可填数字、字符串或 {变量名}',
                'visible_if': {
                    'field': 'op_action',
                    'operator': 'in',
                    'value': ['set', 'append', 'replace'],
                },
            },
            'replace_find': {
                'type': 'str',
                'label': '查找目标文本',
                'default': '',
                'visible_if': {'field': 'op_action', 'operator': 'eq', 'value': 'replace'},
            },
            'replace_with': {
                'type': 'str',
                'label': '替换为新内容',
                'default': '',
                'visible_if': {'field': 'op_action', 'operator': 'eq', 'value': 'replace'},
            },
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        str_op = params.get('str_op') or params.get('op_action', 'set')
        curr_str = str(old_val) if old_val is not None else ''

        if str_op == 'set':
            return str(cls.resolve_val(context, params.get('str_value', '')))

        elif str_op == 'append':
            append_val = str(cls.resolve_val(context, params.get('str_value', '')))
            return curr_str + append_val

        elif str_op == 'replace':
            find_txt = str(params.get('replace_find', ''))
            with_txt = str(params.get('replace_with', ''))
            return curr_str.replace(find_txt, with_txt)

        return curr_str
