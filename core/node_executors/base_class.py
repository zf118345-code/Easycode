# core/node_executors/base_class.py
class BaseNodeExecutor:
    default_params = {}

    def execute(self, node, context):
        raise NotImplementedError()