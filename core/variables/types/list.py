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
            'list_op': {
                'type': 'select',
                'label': '操作方式',
                'options': [
                    {'value': 'push', 'label': '追加元素 (Push)'},
                    {'value': 'pop', 'label': '移除末尾元素 (Pop)'},
                    {'value': 'clear', 'label': '清空列表'},
                    {'value': 'join', 'label': '拼接为文本 (Join)'},
                ],
                'default': 'push',
                'visible_if': {'field': 'var_type', 'operator': 'eq', 'value': 'list'},
            },
            'list_item_value': {
                'type': 'variable',
                'label': '追加元素值/变量',
                'default': '',
                'visible_if': {
                    'field': 'var_type',
                    'operator': 'eq',
                    'value': 'list',
                    'sub_field': 'list_op',
                    'sub_operator': 'eq',
                    'sub_value': 'push',
                },
            },
            'list_join_delimiter': {
                'type': 'string',
                'label': '连接分隔符',
                'default': ',',
                'visible_if': {
                    'field': 'var_type',
                    'operator': 'eq',
                    'value': 'list',
                    'sub_field': 'list_op',
                    'sub_operator': 'eq',
                    'sub_value': 'join',
                },
            },
            'list_join_target_var': {
                'type': 'string',
                'label': '输出到文本变量名',
                'default': '',
                'placeholder': '请输入用于接收拼接结果的字符串变量名',
                'visible_if': {
                    'field': 'var_type',
                    'operator': 'eq',
                    'value': 'list',
                    'sub_field': 'list_op',
                    'sub_operator': 'eq',
                    'sub_value': 'join',
                },
            },
        }

    @classmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        curr_list = list(old_val) if isinstance(old_val, list) else []
        op = params.get('list_op', 'push')

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
