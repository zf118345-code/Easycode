# core/registry.py
from core.params import ALL_PARAMS


class NodeExecutorRegistry:
    _executors = {}

    @classmethod
    def register(cls, node_type):
        def decorator(executor_class):
            cls._executors[node_type] = executor_class
            # 从 ALL_PARAMS 提取默认参数
            defaults = {}
            if node_type in ALL_PARAMS:
                param_defs = ALL_PARAMS[node_type].get('params', {})
                for pname, pdef in param_defs.items():
                    if 'default' in pdef:
                        defaults[pname] = pdef['default']
                    elif pdef.get('type') == 'dict':
                        sub_defaults = {}
                        for sk, sv in pdef.get('sub', {}).items():
                            if 'default' in sv:
                                sub_defaults[sk] = sv['default']
                        if sub_defaults:
                            defaults[pname] = sub_defaults
                    elif pdef.get('type') == 'list_dict':
                        defaults[pname] = []
            executor_class.default_params = defaults
            return executor_class

        return decorator

    @classmethod
    def get(cls, node_type):
        return cls._executors.get(node_type)

    @classmethod
    def get_defaults(cls, node_type):
        if node_type in cls._executors:
            return getattr(cls._executors[node_type], 'default_params', {})
        return {}
