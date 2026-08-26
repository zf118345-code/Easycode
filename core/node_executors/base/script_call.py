from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('script_call')
class ScriptCallNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        call_mode = str(params.get('call_mode') or 'capability').strip().lower()
        if call_mode != 'capability':
            context.log(f'调用能力节点不支持调用方式: {call_mode}', 'error')
            return {'success': False, 'error': f'unsupported capability call mode: {call_mode}', 'code': 'UNSUPPORTED_CALL_MODE'}
        return self._execute_capability(params, context)

    @staticmethod
    def _execute_capability(params, context):
        from core.services.capability_service import CapabilityError, CapabilityService

        capability_id = str(params.get('capability_id') or '').strip()
        if not capability_id:
            context.log('调用能力节点尚未选择能力', 'error')
            return {'success': False, 'error': 'missing capability id', 'code': 'MISSING_CAPABILITY'}
        try:
            result = CapabilityService.invoke(
                context,
                capability_id,
                version=str(params.get('capability_version') or '').strip(),
                input_bindings=params.get('input_bindings') or [],
                output_bindings=params.get('output_bindings') or [],
                timeout_ms=int(params.get('timeout_ms') or 0) or None,
                retry_count=int(params.get('retry_count') or 0),
                retry_interval_ms=int(params.get('retry_interval_ms') or 200),
            )
        except CapabilityError as exc:
            context.log(f'[调用能力] {exc}', 'error')
            return {'success': False, 'error': str(exc), 'code': 'CAPABILITY_CONFIG_ERROR'}
        except Exception as exc:
            context.log(f'[调用能力] 运行时异常: {exc}', 'error')
            return {'success': False, 'error': str(exc), 'code': 'CAPABILITY_RUNTIME_ERROR'}
        level = 'info' if result.get('success') else 'error'
        message = result.get('message') or result.get('code') or ('完成' if result.get('success') else '失败')
        context.log(f'[调用能力] {capability_id}: {message}', level)
        return result
