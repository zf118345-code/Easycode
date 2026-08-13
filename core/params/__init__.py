# core/params/__init__.py
import os
import sys
import importlib

ALL_PARAMS = {}

def load_all_params():
    global ALL_PARAMS
    ALL_PARAMS.clear()

    # ⚡ 工业级路径对齐：智能兼容 PyInstaller 解压目录 (_MEIxxxx) 与源码开发环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = os.path.join(sys._MEIPASS, "core", "params", "base")
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(current_dir, "base")

    if not os.path.exists(base_dir):
        print(f"警告: 参数基准目录不存在: {base_dir}")
        return ALL_PARAMS

    # 自动扫描 base 目录下的所有 .py 文件
    for filename in os.listdir(base_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = filename[:-3]  # 去掉 .py 后缀
            package = f"core.params.base.{module_name}"
            try:
                module = importlib.import_module(package)
                if hasattr(module, "PARAM_DEFINITIONS"):
                    ALL_PARAMS.update(module.PARAM_DEFINITIONS)
            except Exception as e:
                print(f"加载参数模块 {package} 失败: {e}")

    return ALL_PARAMS

# 初始化加载
load_all_params()