# core/conditions/evaluator.py
from core.conditions.base import ConditionRegistry


def evaluate_condition(cond_data: dict, context) -> bool:
    """
    统一评估入口函数
    :param cond_data: 平铺条件定义（形如 {"condition_type": "variable_check", ...}）
    :param context: 执行上下文 ExecutionContext
    """
    if not cond_data or not isinstance(cond_data, dict):
        return True

    cond_type = cond_data.get('condition_type', 'variable_check')

    handler_cls = ConditionRegistry.get(cond_type)
    if not handler_cls:
        if hasattr(context, 'log'):
            context.log(f' [条件评估] 未找到条件类型处理器: {cond_type}', 'warning')
        return False

    return handler_cls.evaluate(cond_data, context)
