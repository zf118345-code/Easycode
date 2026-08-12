# core/conditions/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Type


class ConditionRegistry:
    """条件评估策略注册表中心"""
    _registry: Dict[str, Type['BaseConditionEvaluator']] = {}

    @classmethod
    def register(cls, cond_type: str):
        def decorator(subclass: Type['BaseConditionEvaluator']):
            cls._registry[cond_type] = subclass
            subclass.cond_type = cond_type
            return subclass
        return decorator

    @classmethod
    def get(cls, cond_type: str) -> Type['BaseConditionEvaluator']:
        return cls._registry.get(cond_type)


class BaseConditionEvaluator(ABC):
    cond_type: str = ""

    @classmethod
    @abstractmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        """根据节点参数和运行上下文计算判定结果，返回 True / False"""
        pass