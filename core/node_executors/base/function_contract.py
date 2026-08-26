from core.expressions import evaluate_expression
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('function_entry')
class FunctionEntryNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        return {'success': True}


@NodeExecutorRegistry.register('function_return')
class FunctionReturnNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params or {}
        outcome_id = str(params.get('outcome_id') or '').strip()
        if not outcome_id:
            return {'success': False, 'error': '返回节点未选择结果出口'}
        outputs = {}
        for binding in params.get('output_bindings') or []:
            if not isinstance(binding, dict):
                continue
            output_id = str(binding.get('output_id') or '').strip()
            if not output_id:
                continue
            raw = binding.get('value')
            outputs[output_id] = evaluate_expression(raw, context) if isinstance(raw, str) else raw
        return {'success': True, 'function_return': {'outcome_id': outcome_id, 'outputs': outputs}}

