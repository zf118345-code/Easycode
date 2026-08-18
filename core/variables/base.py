# core/variables/base.py
from abc import ABC, abstractmethod
from typing import Any


class VariableTypeRegistry:
    """全局变量类型注册表中心"""

    _registry: dict[str, type['BaseVariableType']] = {}

    @classmethod
    def register(cls, type_id: str):
        """装饰器：用于自动注册数据类型类"""

        def decorator(subclass: type['BaseVariableType']):
            cls._registry[type_id] = subclass
            subclass.type_id = type_id
            return subclass

        return decorator

    @classmethod
    def get(cls, type_id: str) -> type['BaseVariableType']:
        return cls._registry.get(type_id)

    @classmethod
    def get_all_types(cls) -> dict[str, type['BaseVariableType']]:
        return cls._registry


class BaseVariableType(ABC):
    """数据类型抽象基类：所有具体数据类型都必须继承此类"""

    type_id: str = ''
    label: str = ''

    @classmethod
    @abstractmethod
    def get_schema(cls) -> dict[str, Any]:
        """
        返回该数据类型对应的操作表单 Schema
        用于自动生成前端属性检查器的参数 UI
        """
        pass

    @classmethod
    @abstractmethod
    def execute(cls, op: str, old_val: Any, params: dict, context: Any) -> Any:
        """
        执行具体的变量操作
        :param op: 操作符标识 (如 'push', 'join')
        :param old_val: 变更前的旧值
        :param params: 节点填写的参数字典
        :param context: 执行上下文 ExecutionContext
        :return: 变更后的新值
        """
        pass

    @staticmethod
    def resolve_val(context: Any, val_str: Any, default: Any = None) -> Any:
        """公共工具函数：解析值 —— 统一走模板变量引擎（$var{} / $ctx{} / $env{} 前缀语法），
        裸变量名不再识别；解析结果自动尝试转为数字"""
        if val_str is None:
            return default
        val_str_copy = str(val_str)
        if hasattr(context, 'variables'):
            from core.utils import resolve_template_string

            val_str_copy = resolve_template_string(val_str_copy, context)

        # 尝试转为数字
        try:
            if '.' in val_str_copy:
                return float(val_str_copy)
            return int(val_str_copy)
        except ValueError:
            return val_str_copy
