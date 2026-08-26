from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('call_function')
class CallFunctionNodeExecutor(BaseNodeExecutor):
    """Emit one typed function call intent for the graph scheduler."""

    def execute(self, node, context):
        params = node.params or {}
        function_id = str(params.get('function_id') or '').strip()
        if not function_id:
            return {'success': False, 'error': '未选择目标函数'}
        return {
            'success': True,
            'call_function': {
                'function_id': function_id,
                'input_bindings': list(params.get('input_bindings') or []),
                'output_bindings': list(params.get('output_bindings') or []),
            },
        }

