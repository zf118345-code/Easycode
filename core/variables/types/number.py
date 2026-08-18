# core/variables/types/number.py
from typing import Any

from core.variables.base import BaseVariableType, VariableTypeRegistry


@VariableTypeRegistry.register('number')
class NumberVariableType(BaseVariableType):
    label = '数值 (Number)'

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return {
            'num_value': {
                'type': 'str',  # 普通输入框（取消变量选择器）
                'label': '操作数值/变量（支持 {var}）',

                'default': '1',
                'placeholder': '可填数字或 {变量名}',
                'visible_if': {
                    'field': 'op_action',
                    'operator': 'in',
                    'value': ['set', 'add', 'sub', 'mul', 'div', 'mod'],
                },
            },
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        num_op = params.get('num_op') or params.get('op_action', 'add')
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
