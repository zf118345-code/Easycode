# core/conditions/__init__.py
import importlib
import os

from core.conditions.base import BaseConditionEvaluator, ConditionRegistry

# 动态加载 current_dir/handlers 目录下所有的评估策略模块
handlers_dir = os.path.join(os.path.dirname(__file__), 'handlers')

if os.path.exists(handlers_dir):
    for file in os.listdir(handlers_dir):
        if file.endswith('.py') and not file.startswith('__'):
            module_name = f'core.conditions.handlers.{file[:-3]}'
            importlib.import_module(module_name)

__all__ = ['ConditionRegistry', 'BaseConditionEvaluator']
