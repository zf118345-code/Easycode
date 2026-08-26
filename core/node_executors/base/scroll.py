import time

from core.conditions.evaluator import evaluate_condition
from core.expressions import ExpressionError, evaluate_expression
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.input_dispatcher import drag_workspace, scroll_workspace


@NodeExecutorRegistry.register('scroll')
class ScrollNodeExecutor(BaseNodeExecutor):
    @staticmethod
    def _wait(context, milliseconds: int) -> bool:
        deadline = time.monotonic() + max(0, int(milliseconds or 0)) / 1000.0
        while time.monotonic() < deadline:
            if bool(getattr(context, 'is_stopped', False)):
                return False
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        return True

    @staticmethod
    def _workspace_size(context) -> tuple[int, int]:
        rect = getattr(context, 'window_rect', None)
        if isinstance(rect, (list, tuple)) and len(rect) >= 4:
            return max(1, int(rect[2])), max(1, int(rect[3]))
        return 960, 540

    @classmethod
    def _path(cls, params: dict, context) -> tuple[list[int], list[int], object]:
        current_width, current_height = cls._workspace_size(context)
        custom_position = str(params.get('position_mode') or 'center') == 'custom'
        direction = str(params.get('direction') or 'down').lower()
        candidate_reference = params.get('position_reference_size')
        try:
            reference_values = [int(candidate_reference[0]), int(candidate_reference[1])]
            valid_reference = reference_values[0] > 0 and reference_values[1] > 0
        except (IndexError, TypeError, ValueError):
            reference_values = []
            valid_reference = False
        # A custom coordinate/end point is recorded in the reference canvas.
        # Keep the complete path in that same coordinate domain and let the
        # dispatcher scale it exactly once to the current work area.
        reference = reference_values if valid_reference and (custom_position or direction == 'custom') else None
        width, height = (int(reference[0]), int(reference[1])) if reference else (current_width, current_height)
        start = list(params.get('position') or [width // 2, height // 2]) if custom_position else [width // 2, height // 2]
        if direction == 'custom':
            return start, list(params.get('end_position') or start), reference
        if str(params.get('distance_mode') or 'percent') == 'pixels':
            distance = max(1, int(params.get('distance_px', 300) or 300))
        else:
            axis = height if direction in {'up', 'down'} else width
            distance = max(1, round(axis * max(1, min(95, int(params.get('distance_percent', 40) or 40))) / 100))
        # 参数描述内容浏览方向；触摸点需要向相反方向移动。
        offsets = {'down': (0, -distance), 'up': (0, distance), 'right': (-distance, 0), 'left': (distance, 0)}
        dx, dy = offsets.get(direction, offsets['down'])
        end = [max(0, min(width - 1, int(start[0]) + dx)), max(0, min(height - 1, int(start[1]) + dy))]
        return start, end, reference

    @staticmethod
    def _termination_met(params: dict, context) -> bool:
        mode = str(params.get('termination_mode') or 'fixed')
        if mode == 'fixed':
            return False
        # 输入后的判定必须使用新画面，不能复用上一个执行步骤的缓存帧。
        if hasattr(context, '_step_screen'):
            context._step_screen = None
        if mode in {'image_present', 'image_absent'}:
            return bool(evaluate_condition({
                'condition_type': 'image_exists',
                'image_source': params.get('stop_image_source') or '',
                'exist_mode': 'exists' if mode == 'image_present' else 'not_exists',
                'threshold': params.get('stop_threshold', 85),
                'region_type': params.get('stop_region_type', 'fullwindow'),
                'region_value': params.get('stop_region_value') or [0, 0, 0, 0],
                'region_reference_size': params.get('stop_region_reference_size'),
            }, context))
        if mode == 'page_present':
            page_id = str(params.get('stop_page_id') or '')
            evaluator = getattr(context, '_evaluate_expected_page', None)
            return bool(page_id and callable(evaluator) and evaluator(page_id) == page_id)
        if mode == 'expression':
            expression = str(params.get('stop_expression') or '').strip()
            if not expression:
                return False
            try:
                return bool(evaluate_expression(expression, context))
            except ExpressionError as exc:
                context.log(f'滚动结束表达式无效: {exc}', 'error')
                return False
        return False

    def execute(self, node, context):
        params = node.params
        direction = str(params.get('direction') or 'down').lower()
        mode = str(params.get('gesture_mode') or 'auto').lower()
        if mode == 'swipe':  # 旧项目运行期兼容，持久化迁移后不再写出该值
            mode = 'touch'
        if mode not in {'auto', 'wheel', 'touch'}:
            return self.build_result(False, f'不支持的滚动方式: {mode}')
        is_emulator = bool(getattr(context, 'is_emulator', False))
        if mode == 'wheel' and is_emulator:
            return self.build_result(False, 'Android不支持鼠标滚轮，请选择自动或触控滑动')
        if mode == 'wheel' and direction not in {'up', 'down'}:
            return self.build_result(False, 'PC滚轮只支持向上或向下浏览')
        use_wheel = mode == 'wheel' or (mode == 'auto' and not is_emulator and direction in {'up', 'down'})
        start, end, reference = self._path(params, context)
        termination = str(params.get('termination_mode') or 'fixed')
        repeat_count = max(1, int(params.get('repeat_count', 1) or 1)) if termination == 'fixed' else max(1, int(params.get('max_repeat_count', 20) or 20))
        deadline = time.monotonic() + max(100, int(params.get('timeout_ms', 10000) or 10000)) / 1000.0
        input_mode = str(params.get('input_mode') or 'background')
        result = None
        matched = self._termination_met(params, context) if termination != 'fixed' else False
        performed = 0
        while performed < repeat_count and not matched:
            if bool(getattr(context, 'is_stopped', False)):
                return self.build_result(False, '滚动已被停止', {'cancelled': True})
            if termination != 'fixed' and time.monotonic() >= deadline:
                break
            if use_wheel:
                ticks = max(1, int(params.get('wheel_ticks', 3) or 1))
                ticks = -ticks if direction == 'down' else ticks
                result = scroll_workspace(context, start[0], start[1], ticks=ticks, reference_size=reference, requested_mode=input_mode)
            else:
                result = drag_workspace(
                    context, start[0], start[1], end[0], end[1], reference_size=reference,
                    duration_ms=int(params.get('duration_ms', 300) or 0),
                    hold_after_ms=int(params.get('hold_after_ms', 120) or 0) if params.get('release_mode') == 'hold' else 0,
                    steps=max(1, round(max(16, int(params.get('duration_ms', 300) or 0)) / 16)),
                    requested_mode=input_mode,
                    stop_check=lambda: bool(getattr(context, 'is_stopped', False)),
                )
            if not result.get('ok'):
                context.log(f'滚动失败: {result.get("message", "未知错误")}', 'error')
                return self.build_result(False, result.get('message', '滚动失败'), {'input_result': result})
            performed += 1
            if termination != 'fixed':
                matched = self._termination_met(params, context)
            if performed < repeat_count and not matched and not self._wait(context, int(params.get('repeat_interval_ms', 150) or 0)):
                return self.build_result(False, '滚动已被停止', {'cancelled': True})
        if termination != 'fixed' and not matched:
            return self.build_result(False, f'滚动结束条件未在安全上限内满足（次数={performed}）', {'input_result': result, 'attempts': performed})
        if not self._wait(context, int(params.get('post_wait_ms', 100) or 0)):
            return self.build_result(False, '滚动已被停止', {'cancelled': True})
        context.log(f'滚动已完成：方式={"wheel" if use_wheel else "touch"}，次数={performed}，输入后端={result.get("method", "none") if result else "none"}')
        return self.build_result(True, extra={'input_result': result, 'attempts': performed, 'termination_matched': matched})
