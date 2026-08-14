# core/variables/types/number.py
from typing import Any

from core.variables.base import BaseVariableType, VariableTypeRegistry


@VariableTypeRegistry.register('number')
class NumberVariableType(BaseVariableType):
    label = '数值 (Number)'

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return {
            'num_op': {
                'type': 'select',
                'label': '操作方式',
                'options': [
                    {'value': 'set', 'label': '赋值 (=)'},
                    {'value': 'add', 'label': '加 (+)'},
                    {'value': 'sub', 'label': '减 (-)'},
                    {'value': 'mul', 'label': '乘 (*)'},
                    {'value': 'div', 'label': '除 (/)'},
                    {'value': 'mod', 'label': '取余 (%)'},
                ],
                'default': 'add',
                'visible_if': {'field': 'var_type', 'operator': 'eq', 'value': 'number'},
            },
            'num_value': {
                'type': 'variable',
                'label': '操作数值/变量',
                'default': '1',
                'visible_if': {'field': 'var_type', 'operator': 'eq', 'value': 'number'},
            },
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        num_op = params.get('num_op', 'add')
        operand = cls.resolve_val(context, params.get('num_value', 0), 0)

        try:
            operand = float(operand) if '.' in str(operand) else int(operand)
        except ValueError:
            operand = 0

        curr_num = 0
        if old_val is not None:
            try:
                curr_num = float(old_val) if '.' in str(old_val) else int(old_val)
            except ValueError:
                curr_num = 0

        if num_op == 'set':
            return operand
        elif num_op == 'add':
            return curr_num + operand
        elif num_op == 'sub':
            return curr_num - operand
        elif num_op == 'mul':
            return curr_num * operand
        elif num_op == 'div':
            return curr_num / operand if operand != 0 else curr_num
        elif num_op == 'mod':
            return curr_num % operand if operand != 0 else curr_num

        return curr_num
