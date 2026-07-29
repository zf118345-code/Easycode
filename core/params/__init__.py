import os
import glob
import importlib

ALL_PARAMS = {}

def load_all_params():
    global ALL_PARAMS
    ALL_PARAMS.clear()
    # 获取当前目录下所有子包
    base_dir = os.path.dirname(__file__)
    for entry in os.listdir(base_dir):
        full_path = os.path.join(base_dir, entry)
        if os.path.isdir(full_path) and not entry.startswith('_'):
            # 扫描子包内的所有 .py 文件
            for py_file in glob.glob(os.path.join(full_path, "*.py")):
                if os.path.basename(py_file).startswith('_'):
                    continue
                module_name = os.path.basename(py_file)[:-3]
                package = f"core.params.{entry}.{module_name}"
                try:
                    module = importlib.import_module(package)
                    if hasattr(module, "PARAM_DEFINITIONS"):
                        ALL_PARAMS.update(module.PARAM_DEFINITIONS)
                except Exception as e:
                    print(f"加载参数模块 {package} 失败: {e}")
    return ALL_PARAMS

load_all_params()