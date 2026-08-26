import time

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.input_dispatcher import drag_path_workspace, drag_workspace


@NodeExecutorRegistry.register('drag')
class DragNodeExecutor(BaseNodeExecutor):
    @staticmethod
    def _wait(context, milliseconds: int) -> bool:
        deadline = time.monotonic() + max(0, int(milliseconds or 0)) / 1000.0
        while time.monotonic() < deadline:
            if bool(getattr(context, 'is_stopped', False)):
                return False
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        return True

    def execute(self, node, context):
        params = node.params
        action = str(params.get('action') or 'drag').lower()
        path = params.get('path_points')
        if not isinstance(path, list) or not path:
            return self.build_result(False, '拖拽/长按缺少路径点，请重新录入手势')
        path = path[:32]
        if action == 'long_press':
            first = path[0] if path else {}
            position = first.get('position') if isinstance(first, dict) else None
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                return self.build_result(False, '长按坐标无效')
            result = drag_workspace(
                context, position[0], position[1], position[0], position[1],
                reference_size=params.get('position_reference_size'),
                button=str(params.get('button') or 'left'),
                duration_ms=0,
                hold_before_ms=max(1, int(params.get('long_press_ms', 800) or 800)),
                hold_after_ms=0,
                steps=1,
                requested_mode=str(params.get('input_mode') or 'background'),
                stop_check=lambda: bool(getattr(context, 'is_stopped', False)),
            )
        elif action == 'drag':
            if len(path) < 2:
                return self.build_result(False, '拖拽路径至少需要起点和终点')
            result = drag_path_workspace(
                context,
                path,
                reference_size=params.get('position_reference_size'),
                button=str(params.get('button') or 'left'),
                easing=str(params.get('easing') or 'linear'),
                requested_mode=str(params.get('input_mode') or 'background'),
                stop_check=lambda: bool(getattr(context, 'is_stopped', False)),
            )
        else:
            return self.build_result(False, f'不支持的拖拽操作: {action}')
        label = '长按' if action == 'long_press' else '拖拽'
        if not result.get('ok'):
            context.log(f'{label}失败: {result.get("message", "未知错误")}', 'error')
            return self.build_result(False, result.get('message', f'{label}失败'), {'input_result': result})
        if not self._wait(context, int(params.get('release_wait_ms', 100) or 0)):
            return self.build_result(False, f'{label}已被停止', {'cancelled': True, 'input_result': result})
        context.log(f'{label}已投递：方式={result.get("method", "unknown")}，路径点={1 if action == "long_press" else len(path)}（效果待界面验证）')
        return self.build_result(True, extra={'input_result': result})
