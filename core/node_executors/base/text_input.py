from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.input_dispatcher import text_workspace
from core.utils import resolve_template_string


@NodeExecutorRegistry.register('text_input')
class TextInputNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        text = resolve_template_string(params.get('text', ''), context)
        if text is None:
            text = ''
        result = text_workspace(
            context,
            str(text),
            position=params.get('position'),
            reference_size=params.get('position_reference_size'),
            click_before=bool(params.get('click_before', True)),
            clear_before=bool(params.get('clear_before', False)),
            interval_ms=int(params.get('interval_ms', 0) or 0),
            submit_key=str(params.get('submit_key') or 'none'),
            requested_mode=str(params.get('input_mode') or 'background'),
            stop_check=lambda: bool(getattr(context, 'is_stopped', False)),
        )
        if not result.get('ok'):
            context.log(f'文本输入失败: {result.get("message", "未知错误")}', 'error')
            return self.build_result(False, result.get('message', '文本输入失败'), {'input_result': result})
        shown = '已脱敏' if bool(params.get('sensitive', False)) else f'长度={len(str(text))}'
        context.log(f'文本输入已投递：{shown}，方式={result.get("method", "unknown")}（效果待界面验证）')
        return self.build_result(True, extra={'input_result': result})
