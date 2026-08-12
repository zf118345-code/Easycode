# core/conditions/evaluator.py
import core.conditions.handlers.variable_check
import core.conditions.handlers.image_exists
import core.conditions.handlers.text_contains
import core.conditions.handlers.window_state
import core.conditions.handlers.file_exists
from core.conditions.base import ConditionRegistry


def evaluate_condition(cond_data: dict, context) -> bool:
    """
    统一评估入口函数
    :param cond_data: 条件定义字典 (形如 {"condition_type": "variable_check", "params": {...}})
    :param context: 执行上下文 ExecutionContext
    """
    if not cond_data or not isinstance(cond_data, dict):
        return True

    # 兼容直接嵌套在 params 中的数据结构
    cond_type = cond_data.get("condition_type") or cond_data.get("type", "variable_check")
    params = cond_data.get("params") or cond_data

    handler_cls = ConditionRegistry.get(cond_type)
    if not handler_cls:
        if hasattr(context, 'log'):
            context.log(f"⚠️ [条件评估] 未找到条件类型处理器: {cond_type}", "warning")
        return False

    return handler_cls.evaluate(params, context)