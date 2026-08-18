# core/variables/types/list.py
from typing import Any

from core.variables.base import BaseVariableType, VariableTypeRegistry


@VariableTypeRegistry.register('list')
class ListVariableType(BaseVariableType):
    label = '数组 (List)'

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """完全自定义的数组操作表单配置 Schema"""
        return {
            'list_item_value': {
                'type': 'str',  # 普通输入框（取消变量选择器）
                'label': '追加元素值/变量（支持 {var}）',

                'default': '',
                'placeholder': '可填值或 {变量名}',
                'visible_if': {'field': 'op_action', 'operator': 'eq', 'value': 'push'},
            },
            'list_join_delimiter': {
                'type': 'str',
                'label': '连接分隔符',
                'default': ',',
                'visible_if': {'field': 'op_action', 'operator': 'eq', 'value': 'join'},
            },
            'list_join_target_var': {
                'type': 'str',
                'label': '输出到文本变量名',
                'default': '',
                'placeholder': '请输入用于接收拼接结果的字符串变量名',
                'visible_if': {'field': 'op_action', 'operator': 'eq', 'value': 'join'},
            },
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        curr_list = list(old_val) if isinstance(old_val, list) else []
        op = params.get('list_op') or params.get('op_action', 'push')

        if op == 'push':
            item = cls.resolve_val(context, params.get('list_item_value', ''))
            curr_list.append(item)
            return curr_list

        elif op == 'pop':
            if curr_list:
                curr_list.pop()
            return curr_list

        elif op == 'clear':
            return []

        elif op == 'join':
            delimiter = str(params.get('list_join_delimiter', ','))
            target_str_var = str(params.get('list_join_target_var', '')).strip()
            # 将列表项连接为字符串
            joined_str = delimiter.join([str(x) for x in curr_list])
            # 如果指定了接收的文本变量，写入全局上下文
            if target_str_var and hasattr(context, 'variables'):
                context.variables[target_str_var] = joined_str
                context.log(f'🔗 [数组 Join] 拼接结果存入变量 [{target_str_var}]: {joined_str}')
            return curr_list  # 原数组保持不变

        return curr_list
