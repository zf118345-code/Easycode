# core/variables/__init__.py
import os
import importlib
from core.variables.base import VariableTypeRegistry, BaseVariableType

# 动态加载 current_dir/types 目录下所有的类型定义模块
types_dir = os.path.join(os.path.dirname(__file__), "types")

if os.path.exists(types_dir):
    for file in os.listdir(types_dir):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = f"core.variables.types.{file[:-3]}"
            importlib.import_module(module_name)

__all__ = ["VariableTypeRegistry", "BaseVariableType"]