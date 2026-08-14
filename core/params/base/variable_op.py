# core/params/base/variable_op.py
from typing import Any

from core.variables import VariableTypeRegistry


def build_variable_op_params() -> dict[str, Any]:
    """根据注册的数据类型，动态生成变量操作节点的参数定义"""
    all_types = VariableTypeRegistry.get_all_types()

    type_options = []
    dynamic_sub_params: dict[str, Any] = {}

    for type_id, type_cls in all_types.items():
        type_options.append({'value': type_id, 'label': type_cls.label})
        schema = type_cls.get_schema()
        dynamic_sub_params.update(schema)

    params_def: dict[str, Any] = {
        'target_var': {
            'type': 'variable',  # ⚡ 强变量选择：必须选择已有或侧边栏创建的变量名
            'label': '目标变量',
            'default': '',
        },
        'var_type': {'type': 'select', 'label': '变量类型', 'options': type_options, 'default': 'number'},
        'op_action': {
            'type': 'select',
            'label': '操作方式',
            'options': [
                {'value': 'set', 'label': '赋值 (=)'},
                {'value': 'add', 'label': '加 (+)'},
                {'value': 'sub', 'label': '减 (-)'},
                {'value': 'mul', 'label': '乘 (*)'},
                {'value': 'div', 'label': '除 (/)'},
                {'value': 'append', 'label': '文本/列表追加 (Append)'},
                {'value': 'clear', 'label': '重置/清空 (Clear)'},  # ⚡ 扩展 Clear 重置清空能力
            ],
            'default': 'set',
        },
    }

    params_def.update(dynamic_sub_params)

    on_success_config: dict[str, Any] = {
        'type': 'dict',
        'label': '成功跳转',
        'sub': {
            'jump_type': {
                'type': 'select',
                'options': [
                    {'value': 'next', 'label': '下一个节点'},
                    {'value': 'node', 'label': '跳转节点'},
                    {'value': 'end', 'label': '结束流程'},
                ],
                'default': 'next',
                'label': '跳转类型',
            }
        },
    }

    params_def['on_success'] = on_success_config

    return params_def


PARAM_DEFINITIONS: dict[str, Any] = {'variable_op': {'label': '变量操作', 'params': build_variable_op_params()}}
