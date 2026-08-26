"""Image interaction node with explicit, stable completion semantics."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.asset_service import AssetService
from core.services.input_dispatcher import click_workspace
from core.services.runtime_session import GLOBAL_TEMPLATE_CACHE, FramePacket, create_visual_frame_stream
from core.services.runtime_target import capture_workspace_region, refresh_work_area, workspace_rect
from core.utils import (
    load_image,
    match_prepared_template_cv,
    match_template_cv,
    prepare_template_cv,
    resource_path,
)


WAIT_PRESENT = 'wait_present'
WAIT_ABSENT = 'wait_absent'
CLICK_ONCE = 'click_once'
CLICK_UNTIL_ABSENT = 'click_until_absent'
CLICK_UNTIL_STOP = 'click_until_stop'
VALID_MODES = {WAIT_PRESENT, WAIT_ABSENT, CLICK_ONCE, CLICK_UNTIL_ABSENT, CLICK_UNTIL_STOP}


@dataclass
class _RunStats:
    started_ns: int
    frames: int = 0
    clicks: int = 0
    capture_ms: list[float] = field(default_factory=list)
    frame_age_ms: list[float] = field(default_factory=list)
    match_ms: list[float] = field(default_factory=list)
    capture_tier: str = 'standard_capture'

    @staticmethod
    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        return float(np.percentile(np.asarray(values, dtype=np.float64), 95))

    def result(self) -> dict[str, Any]:
        elapsed_ms = max(0.001, (time.monotonic_ns() - self.started_ns) / 1_000_000.0)
        return {
            'elapsed_ms': round(elapsed_ms, 3),
            'frames': self.frames,
            'click_count': self.clicks,
            'processed_fps': round(self.frames * 1000.0 / elapsed_ms, 3),
            'capture_p95_ms': round(self._p95(self.capture_ms), 3),
            'frame_age_p95_ms': round(self._p95(self.frame_age_ms), 3),
            'match_p95_ms': round(self._p95(self.match_ms), 3),
            'capture_tier': self.capture_tier,
        }


@dataclass(frozen=True)
class _PreparedTemplate:
    reference: str
    variants: tuple
    gray_scale: bool


@NodeExecutorRegistry.register('image_recognition')
class ImageRecognitionNodeExecutor(BaseNodeExecutor):
    def __init__(self):
        self.debug_dir = resource_path('debug_screenshots')
        os.makedirs(self.debug_dir, exist_ok=True)

    @staticmethod
    def _mode(params: dict[str, Any]) -> str:
        return str(params.get('execution_mode') or '').strip().lower()

    @staticmethod
    def _parse_scales(params: dict[str, Any], context) -> tuple[float, ...] | None:
        raw = params.get('match_scales')
        if raw is None or str(raw).strip() == '':
            raw = context.get_setting('multi_scale_scales', '1.0,0.75,0.5')
        try:
            values = tuple(float(value) for value in str(raw).split(',') if value.strip())
            return values or None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _load_template(reference: str, context) -> tuple[Any, bool]:
        memory_templates = getattr(context, '_memory_templates', {}) or {}
        if reference in memory_templates:
            return memory_templates[reference], True
        resolved = AssetService.resolve(context.project_dir, reference)
        template, cached = GLOBAL_TEMPLATE_CACHE.get(resolved['full_path'], load_image)
        return template, cached

    @staticmethod
    def _configured_region(
        params: dict[str, Any],
        context,
        workspace_size: tuple[int, int],
        *,
        prefix: str = '',
        reference: str = '',
    ) -> tuple[int, int, int, int]:
        region_type = str(params.get(f'{prefix}region_type', 'fullwindow') or 'fullwindow')
        value = params.get(f'{prefix}region_value', [0, 0, 0, 0])

        def valid_region(candidate) -> bool:
            return (
                isinstance(candidate, (list, tuple))
                and len(candidate) == 4
                and all(isinstance(item, (int, float)) for item in candidate)
                and float(candidate[2]) > 0
                and float(candidate[3]) > 0
            )

        reference_size = params.get(f'{prefix}region_reference_size')
        if region_type == 'recorded' and reference:
            try:
                record = AssetService.resolve(context.project_dir, reference).get('record') or {}
                capture = record.get('capture') if isinstance(record, dict) else None
                captured_region = capture.get('region') if isinstance(capture, dict) else None
                if valid_region(captured_region):
                    if list(value or []) != list(captured_region):
                        label = '停止特征' if prefix else '目标图片'
                        context.log(
                            f'[录制区域] {label}节点区域为空或已过期，采用资源元数据: {list(captured_region)}',
                            'warning',
                        )
                    value = captured_region
                    reference_size = capture.get('reference_size') or reference_size
            except (FileNotFoundError, ValueError):
                # 模板加载阶段会给出资源错误；这里仅负责区域选择。
                pass

        if region_type in {'recorded', 'custom'}:
            if not valid_region(value):
                label = '录制区域' if region_type == 'recorded' else '自定义区域'
                raise ValueError(f'{label}无效，区域必须是 [x, y, 宽, 高] 且宽高大于 0，当前值: {value}')
            return workspace_rect(context, value, reference_size)
        return 0, 0, int(workspace_size[0]), int(workspace_size[1])

    @staticmethod
    def _union(*regions: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        left = min(region[0] for region in regions)
        top = min(region[1] for region in regions)
        right = max(region[0] + region[2] for region in regions)
        bottom = max(region[1] + region[3] for region in regions)
        return left, top, right - left, bottom - top

    @staticmethod
    def _crop(packet: FramePacket, desired: tuple[int, int, int, int]):
        local_x = desired[0] - packet.region[0]
        local_y = desired[1] - packet.region[1]
        width, height = desired[2], desired[3]
        if local_x == 0 and local_y == 0 and width == packet.region[2] and height == packet.region[3]:
            return packet.image
        if local_x < 0 or local_y < 0 or local_x + width > packet.region[2] or local_y + height > packet.region[3]:
            raise RuntimeError(f'匹配区域 {desired} 超出当前帧 {packet.region}')
        if hasattr(packet.image, 'crop'):
            return packet.image.crop((local_x, local_y, local_x + width, local_y + height))
        array = np.asarray(packet.image)
        return array[local_y : local_y + height, local_x : local_x + width]

    @staticmethod
    def _match(
        packet: FramePacket,
        region: tuple[int, int, int, int],
        template,
        *,
        gray_scale: bool,
        scales,
    ) -> tuple[float, tuple[int, int] | None, float]:
        started_ns = time.monotonic_ns()
        screenshot = ImageRecognitionNodeExecutor._crop(packet, region)
        if isinstance(template, _PreparedTemplate):
            confidence, local_center = match_prepared_template_cv(
                screenshot,
                template.variants,
                gray_scale=template.gray_scale,
            )
        else:
            confidence, local_center = match_template_cv(
                screenshot,
                template,
                gray_scale=gray_scale,
                scales=scales,
            )
        elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000.0
        if local_center is None:
            return float(confidence), None, elapsed_ms
        return (
            float(confidence),
            (region[0] + int(local_center[0]), region[1] + int(local_center[1])),
            elapsed_ms,
        )

    @staticmethod
    def _screen_position(context, workspace_position: tuple[int, int] | None):
        if workspace_position is None:
            return None
        left, top, _, _ = refresh_work_area(context)
        return left + workspace_position[0], top + workspace_position[1]

    @staticmethod
    def _is_stopped(context) -> bool:
        return bool(getattr(context, 'is_stopped', False))

    def execute(self, node, context):
        params = node.params
        mode = self._mode(params)
        if mode not in VALID_MODES:
            context.log(f'图像节点运行模式无效或缺失: {mode or "(空)"}', 'error')
            return self.build_result(False, error='invalid execution mode')
        template_reference = str(params.get('image_source') or '').strip()
        if not template_reference:
            context.log('未指定目标图片', 'error')
            return self.build_result(False, error='template name missing')

        try:
            template, template_cached = self._load_template(template_reference, context)
        except (FileNotFoundError, ValueError) as exc:
            context.log(f'模板文件不存在: {exc}', 'error')
            return self.build_result(False, error='template not found')
        except Exception as exc:
            context.log(f'模板文件加载失败: {exc}', 'error')
            return self.build_result(False, error='template load error')

        stop_reference = str(params.get('stop_image_source') or '').strip()
        stop_template = None
        stop_template_cached = False
        if mode == CLICK_UNTIL_STOP:
            if not stop_reference:
                context.log('持续点击到停止特征模式必须指定停止图片', 'error')
                return self.build_result(False, error='stop template missing')
            try:
                stop_template, stop_template_cached = self._load_template(stop_reference, context)
            except (FileNotFoundError, ValueError) as exc:
                context.log(f'停止特征模板不存在: {exc}', 'error')
                return self.build_result(False, error='stop template not found')
            except Exception as exc:
                context.log(f'停止特征模板加载失败: {exc}', 'error')
                return self.build_result(False, error='stop template load error')

        _, _, workspace_width, workspace_height = refresh_work_area(context)
        workspace_size = (workspace_width, workspace_height)
        try:
            target_region = self._configured_region(
                params,
                context,
                workspace_size,
                reference=template_reference,
            )
            stop_region = (
                self._configured_region(
                    params,
                    context,
                    workspace_size,
                    prefix='stop_',
                    reference=stop_reference,
                )
                if mode == CLICK_UNTIL_STOP
                else target_region
            )
        except (TypeError, ValueError) as exc:
            context.log(f'图像识别区域配置无效: {exc}', 'error')
            return self.build_result(False, error=str(exc), extra={'stop_reason': 'invalid_region'})
        capture_region = self._union(target_region, stop_region)

        threshold = max(0.0, min(1.0, float(params.get('threshold', 85)) / 100.0))
        stop_threshold = max(0.0, min(1.0, float(params.get('stop_threshold', 85)) / 100.0))
        gray_scale = bool(params.get('gray_scale', False))
        stop_gray_scale = bool(params.get('stop_gray_scale', False))
        scales = self._parse_scales(params, context)
        if np.asarray(template).ndim >= 2:
            template = _PreparedTemplate(
                reference=template_reference,
                variants=prepare_template_cv(template, gray_scale=gray_scale, scales=scales),
                gray_scale=gray_scale,
            )
        if stop_template is not None:
            if np.asarray(stop_template).ndim >= 2:
                stop_template = _PreparedTemplate(
                    reference=stop_reference,
                    variants=prepare_template_cv(stop_template, gray_scale=stop_gray_scale, scales=scales),
                    gray_scale=stop_gray_scale,
                )
        timeout_ms = max(1, int(params.get('timeout', 3000) or 3000))
        click_interval_ms = max(0, int(params.get('click_interval_ms', 80) or 0))
        max_clicks = max(1, int(params.get('max_clicks', 100) or 1))
        present_stable_frames = max(1, int(params.get('present_stable_frames', 1) or 1))
        absent_stable_frames = max(1, int(params.get('absent_stable_frames', 2) or 1))
        stop_stable_frames = max(1, int(params.get('stop_stable_frames', 1) or 1))
        frame_interval_ms = max(0, int(params.get('frame_interval_ms', 0) or 0))
        performance_mode = str(params.get('performance_mode') or 'auto').strip().lower()

        current_reference_size = [workspace_width, workspace_height]

        def capture():
            image, actual_region = capture_workspace_region(
                context,
                list(capture_region),
                current_reference_size,
            )
            return image, actual_region

        stats = _RunStats(started_ns=time.monotonic_ns())
        deadline_ns = stats.started_ns + timeout_ms * 1_000_000
        last_sequence = 0
        last_click_ns = 0
        present_count = 0
        absent_count = 0
        stop_count = 0
        target_seen = False
        last_stop_confidence = 0.0
        best_confidence = 0.0
        best_stop_confidence = 0.0
        last_target_position = None
        target_currently_present = False
        last_input = None
        last_packet = None
        stop_reason = 'timeout'

        def perform_target_click(confidence: float):
            nonlocal last_input, last_click_ns
            if stats.clicks >= max_clicks:
                return self._finish(
                    False, mode, 'max_clicks_reached', stats,
                    error='max clicks reached', confidence=confidence,
                    stop_confidence=last_stop_confidence,
                    workspace_position=last_target_position,
                    screen_position=self._screen_position(context, last_target_position),
                    input_result=last_input,
                )
            last_input = self._smart_click(last_target_position, context)
            if not last_input.get('ok'):
                context.log(f'图像已识别，但输入失败: {last_input.get("message", "")}', 'error')
                return self._finish(
                    False, mode, 'input_failed', stats,
                    error=last_input.get('message', 'click failed'), confidence=confidence,
                    stop_confidence=last_stop_confidence,
                    workspace_position=last_target_position,
                    screen_position=self._screen_position(context, last_target_position),
                    input_result=last_input,
                )
            stats.clicks += 1
            last_click_ns = time.monotonic_ns()
            if mode == CLICK_ONCE:
                return self._finish(
                    True, mode, 'clicked_once', stats,
                    confidence=confidence,
                    workspace_position=last_target_position,
                    screen_position=self._screen_position(context, last_target_position),
                    input_result=last_input,
                    template_cached=template_cached,
                )
            return None

        context.log(
            f'[图像交互] 模式={mode}，目标={template_reference}，超时={timeout_ms}ms，'
            f'模板缓存={"命中" if template_cached else "载入"}'
        )

        try:
            stream = create_visual_frame_stream(
                context,
                capture,
                capture_region=capture_region,
                workspace_size=workspace_size,
                performance_mode=performance_mode,
                min_interval_ms=frame_interval_ms,
            )
            stats.capture_tier = str(getattr(stream, 'provider', stats.capture_tier))
        except Exception as exc:
            context.log(str(exc), 'error')
            return self._finish(
                False, mode, 'capture_provider_unavailable', stats,
                error=str(exc), confidence=best_confidence,
            )
        try:
            with stream:
                while time.monotonic_ns() < deadline_ns:
                    if self._is_stopped(context):
                        stop_reason = 'cancelled'
                        break
                    remaining_s = max(0.001, (deadline_ns - time.monotonic_ns()) / 1_000_000_000.0)
                    repeating = mode in {CLICK_UNTIL_ABSENT, CLICK_UNTIL_STOP}
                    cadenced_repeat = repeating and click_interval_ms > 0
                    poll_timeout_s = remaining_s
                    if cadenced_repeat and target_currently_present and last_target_position is not None:
                        elapsed_since_click_ns = time.monotonic_ns() - last_click_ns if last_click_ns else 0
                        due_in_ns = max(0, click_interval_ms * 1_000_000 - elapsed_since_click_ns)
                        poll_timeout_s = min(remaining_s, max(0.001, due_in_ns / 1_000_000_000.0))
                    try:
                        packet = stream.next(last_sequence, poll_timeout_s)
                    except TimeoutError:
                        # A static Android surface may not emit duplicate video
                        # frames. Keep the click cadence from the last *freshly
                        # matched* frame; any actual UI transition emits a new
                        # frame and is evaluated before the next heartbeat tap.
                        click_due = (
                            last_click_ns == 0
                            or time.monotonic_ns() - last_click_ns >= click_interval_ms * 1_000_000
                        )
                        if cadenced_repeat and target_currently_present and last_target_position is not None and click_due:
                            terminal_result = perform_target_click(best_confidence)
                            if terminal_result is not None:
                                return terminal_result
                        continue
                    except Exception as exc:
                        context.log(str(exc), 'error')
                        return self._finish(
                            False, mode, 'capture_failed', stats, error='capture failed',
                            confidence=best_confidence, stop_confidence=best_stop_confidence,
                            input_result=last_input,
                        )

                    last_packet = packet
                    last_sequence = packet.sequence
                    stats.frames += 1
                    stats.capture_tier = packet.provider
                    stats.capture_ms.append(packet.capture_duration_ms)
                    stats.frame_age_ms.append((time.monotonic_ns() - packet.captured_at_ns) / 1_000_000.0)

                    # Stop feature always wins on the same frame. No target
                    # click may be emitted after it has met the stability rule.
                    if stop_template is not None:
                        last_stop_confidence, _, match_ms = self._match(
                            packet, stop_region, stop_template,
                            gray_scale=stop_gray_scale, scales=scales,
                        )
                        stats.match_ms.append(match_ms)
                        best_stop_confidence = max(best_stop_confidence, last_stop_confidence)
                        stop_count = stop_count + 1 if last_stop_confidence >= stop_threshold else 0
                        if stop_count >= stop_stable_frames:
                            return self._finish(
                                True, mode, 'stop_feature_found', stats,
                                confidence=best_confidence, stop_confidence=last_stop_confidence,
                                workspace_position=last_target_position,
                                screen_position=self._screen_position(context, last_target_position),
                                input_result=last_input,
                                template_cached=template_cached and stop_template_cached,
                            )

                    last_confidence, target_position, match_ms = self._match(
                        packet, target_region, template,
                        gray_scale=gray_scale, scales=scales,
                    )
                    stats.match_ms.append(match_ms)
                    best_confidence = max(best_confidence, last_confidence)
                    found = last_confidence >= threshold and target_position is not None
                    target_currently_present = found

                    if found:
                        target_seen = True
                        last_target_position = target_position
                        present_count += 1
                        absent_count = 0
                    else:
                        present_count = 0
                        absent_count += 1

                    if mode == WAIT_PRESENT and present_count >= present_stable_frames:
                        return self._finish(
                            True, mode, 'target_found', stats,
                            confidence=last_confidence,
                            workspace_position=last_target_position,
                            screen_position=self._screen_position(context, last_target_position),
                            template_cached=template_cached,
                        )

                    if mode == WAIT_ABSENT and absent_count >= absent_stable_frames:
                        return self._finish(
                            True, mode, 'target_absent', stats,
                            confidence=best_confidence,
                            template_cached=template_cached,
                        )

                    if mode == CLICK_UNTIL_ABSENT and target_seen and absent_count >= absent_stable_frames:
                        return self._finish(
                            True, mode, 'target_disappeared', stats,
                            confidence=best_confidence,
                            workspace_position=last_target_position,
                            screen_position=self._screen_position(context, last_target_position),
                            input_result=last_input,
                            template_cached=template_cached,
                        )

                    should_click = mode in {CLICK_ONCE, CLICK_UNTIL_ABSENT, CLICK_UNTIL_STOP} and found
                    click_due = last_click_ns == 0 or time.monotonic_ns() - last_click_ns >= click_interval_ms * 1_000_000
                    if should_click and click_due:
                        terminal_result = perform_target_click(last_confidence)
                        if terminal_result is not None:
                            return terminal_result
        finally:
            if bool(getattr(context, 'image_log_enabled', False)) and last_packet is not None:
                self._save_debug_screenshot(np.asarray(last_packet.image), template_reference, context)

        error = 'cancelled' if stop_reason == 'cancelled' else 'timeout'
        context.log(
            f'[图像交互] {"已取消" if error == "cancelled" else "超时"}: {template_reference} | '
            f'最高置信度={best_confidence:.2f} | 帧={stats.frames} | 点击={stats.clicks}',
            'warning' if error == 'cancelled' else 'info',
        )
        return self._finish(
            False, mode, stop_reason, stats, error=error,
            confidence=best_confidence, stop_confidence=best_stop_confidence,
            workspace_position=last_target_position,
            screen_position=self._screen_position(context, last_target_position),
            input_result=last_input,
            template_cached=template_cached and (stop_template is None or stop_template_cached),
        )

    def _finish(
        self,
        success: bool,
        mode: str,
        stop_reason: str,
        stats: _RunStats,
        *,
        error: str | None = None,
        confidence: float = 0.0,
        stop_confidence: float = 0.0,
        workspace_position=None,
        screen_position=None,
        input_result=None,
        template_cached: bool = False,
    ):
        extra = {
            **stats.result(),
            'execution_mode': mode,
            'stop_reason': stop_reason,
            'confidence': float(confidence),
            'stop_confidence': float(stop_confidence),
            'workspace_pos': workspace_position,
            'pos': screen_position,
            'input': input_result,
            'template_cached': bool(template_cached),
        }
        return self.build_result(success, error=error, extra=extra)

    @staticmethod
    def _smart_click(work_pos, context):
        if work_pos is None:
            return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': '识别位置为空'}
        return click_workspace(context, work_pos[0], work_pos[1], requested_mode='background')

    def _save_debug_screenshot(self, screen, template_name, context):
        timestamp = int(time.time() * 1000)
        task_name = context.current_task_name.replace(' ', '_') if context.current_task_name else 'unknown'
        node_index = context.current_node_index + 1
        safe_name = re.sub(r'[^\w.-]+', '_', template_name, flags=re.UNICODE).strip('_') or 'template'
        filepath = os.path.join(self.debug_dir, f'{task_name}_{node_index}_{safe_name}_{timestamp}.png')

        image = np.asarray(screen)
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(filepath, image)

        files = sorted(
            [name for name in os.listdir(self.debug_dir) if name.endswith('.png')],
            key=lambda name: os.path.getmtime(os.path.join(self.debug_dir, name)),
        )
        max_files = int(context.get_setting('debug_screenshot_max', 20))
        for old_file in files[:-max_files] if len(files) > max_files else []:
            os.remove(os.path.join(self.debug_dir, old_file))
