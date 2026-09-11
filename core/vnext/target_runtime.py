"""Target adapters used by ECIR instructions.

Adapters own hot capture/input sessions. FastAPI only starts and observes the
run; no frame or click loop crosses the HTTP/WebView boundary.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from core.utils import load_image, match_prepared_template_cv, prepare_template_cv

from .resources import ProjectAssetService
from .runtime import RuntimeFailure
from .vision_analysis_v6 import analyze_template_matches, frame_to_bgr
from .workspace_context import VNextWorkspaceError

_PHYSICAL_INPUT_LOCK = threading.Lock()


class TargetDriver:
    platform = ''
    frame_is_bgr = False

    def __init__(self, project_path: str, target: dict[str, Any]) -> None:
        self.project_path = os.path.realpath(project_path)
        self.target = target
        self._assets = self._load_assets()
        self._last_message = ''
        self._ocr_frame_cache: dict[str, Any] = {}
        self._ocr_analysis_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._frame_references: dict[str, Any] = {}
        self._prepared_asset_cache: dict[str, tuple[str, Any]] = {}
        self._frame_sequence = 0
        self._last_image_match_diagnostic: dict[str, Any] = {}

    def _load_assets(self) -> dict[str, dict[str, Any]]:
        path = os.path.join(self.project_path, 'assets', 'registry.json')
        try:
            with open(path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return {}
        assets = value.get('assets') if isinstance(value, dict) else {}
        return assets if isinstance(assets, dict) else {}

    def resolve_image(self, reference: Any) -> str:
        if isinstance(reference, dict):
            name = str(reference.get('asset_id') or reference.get('resource_name') or '').strip()
        else:
            name = str(reference or '').strip()
        entry = self._assets.get(name)
        if entry is None:
            entry = next((item for item in self._assets.values() if isinstance(item, dict) and (item.get('display_name') == name or name in (item.get('aliases') or []))), None)
        if not isinstance(entry, dict):
            raise RuntimeFailure(f'图片资源不存在：{name}')
        relative = str(entry.get('path') or '').replace('\\', '/').strip('/')
        full = os.path.realpath(os.path.join(self.project_path, *relative.split('/')))
        if os.path.commonpath([self.project_path, full]) != self.project_path or not os.path.isfile(full):
            raise RuntimeFailure(f'图片资源文件不存在：{relative or name}')
        return full

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode in {
            'target.capture_frame', 'frame.save', 'color.read', 'color.find',
            'vision.find', 'vision.find_all', 'input.click', 'input.drag',
            'input.text', 'input.scroll', 'input.key', 'text.recognize',
        }

    def consume_message(self) -> str:
        message, self._last_message = self._last_message, ''
        return message

    def _set_message(self, message: str) -> None:
        self._last_message = str(message or '')

    def image_match_diagnostic(self) -> dict[str, Any]:
        """Return the last image analysis evidence without consuming runtime logs."""

        return deepcopy(getattr(self, '_last_image_match_diagnostic', {}))

    def image_exists_on_frame(self, frame: Any, arguments: dict[str, Any]) -> bool:
        result = self._match_frame_once(
            frame, self._prepared(arguments), float(arguments.get('相似度', 0.85) or 0.85), arguments.get('区域'),
        )
        return bool(result['已找到'])

    def recognize_text_on_frame(self, frame: Any, arguments: dict[str, Any]) -> str:
        import cv2
        import numpy as np

        from core.vision.ocr_engine import (
            get_ocr_engine,
            ocr_engine_recognize,
            preprocess_ocr_image,
        )

        cropped, _, _, crop_meta = self._analysis_crop(frame, arguments.get('区域'))
        if cropped is None:
            self._ocr_frame_cache = {
                'frame': frame,
                'key': (repr(arguments.get('区域')), bool(arguments.get('二值化', False)), int(arguments.get('阈值', 127) or 127)),
                'text': '',
                'crop': crop_meta,
            }
            return ''
        threshold = max(0, min(255, int(arguments.get('阈值', 127) or 127)))
        binary = bool(arguments.get('二值化', False))
        cache_key = (repr(arguments.get('区域')), binary, threshold)
        if self._ocr_frame_cache.get('frame') is frame and self._ocr_frame_cache.get('key') == cache_key:
            return str(self._ocr_frame_cache.get('text') or '')
        image = np.asarray(cropped)
        if image.ndim == 3 and image.shape[2] == 4:
            conversion = cv2.COLOR_BGRA2BGR if self.frame_is_bgr else cv2.COLOR_RGBA2BGR
            image = cv2.cvtColor(image, conversion)
        elif image.ndim == 3 and image.shape[2] == 3 and not self.frame_is_bgr:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        engine_type, engine = get_ocr_engine()
        if engine is None or engine_type == 'none':
            raise RuntimeFailure('没有可用的 OCR 引擎，请安装 RapidOCR 或 ddddocr')
        processed = preprocess_ocr_image(image, gray_scale=binary, gray_threshold=threshold)
        text = ocr_engine_recognize(processed).strip()
        self._ocr_frame_cache = {'frame': frame, 'key': cache_key, 'text': text}
        return text

    @staticmethod
    def _text_matches(text: str, arguments: dict[str, Any]) -> bool:
        expected = str(arguments.get('目标') or '')
        actual = str(text or '')
        if not expected:
            raise RuntimeFailure('OCR 目标文字不能为空')
        mode = str(arguments.get('匹配方式') or '包含').strip().lower()
        ignore_case = bool(arguments.get('忽略大小写', True))
        if mode in {'包含', 'contains'}:
            if ignore_case:
                expected, actual = expected.casefold(), actual.casefold()
            return expected in actual
        if mode in {'完全等于', '等于', 'exact', 'equals'}:
            if ignore_case:
                expected, actual = expected.casefold(), actual.casefold()
            return actual == expected
        if mode in {'正则', 'regex'}:
            try:
                return re.search(expected, actual, re.IGNORECASE if ignore_case else 0) is not None
            except re.error as exc:
                raise RuntimeFailure(f'OCR 正则表达式无效：{exc}') from exc
        raise RuntimeFailure('文字匹配方式只能是“包含”、“完全等于”或“正则”')

    def ocr_contains_on_frame(self, frame: Any, arguments: dict[str, Any]) -> bool:
        return self._text_matches(self.recognize_text_on_frame(frame, arguments), arguments)

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        if opcode == 'target.capture_frame':
            return self._capture_frame_reference()
        if opcode == 'frame.save':
            return self._execute_frame_save(arguments, cancelled)
        if opcode == 'color.read':
            return self._execute_color_read(arguments)
        if opcode == 'color.find':
            return self._execute_color_find(arguments, cancelled)
        if opcode == 'vision.find':
            return self._execute_v6_find(arguments)
        if opcode == 'vision.find_all':
            return self._execute_v6_find_all(arguments)
        if opcode == 'input.click':
            return self._execute_v6_click(arguments, cancelled)
        if opcode == 'input.text' and 'official.input.type_text.parameter.content' in arguments:
            mode = str(arguments.get('official.input.type_text.parameter.mode') or 'auto')
            allowed_modes = {
                'windows': {'auto', 'background', 'physical'},
                'android_adb': {'auto', 'target'},
                'android_local': {'auto', 'target'},
            }.get(self.platform, {'auto'})
            if mode not in allowed_modes:
                raise RuntimeFailure(
                    f'当前目标不支持文本输入模式：{mode}',
                    error_id='target.input_mode_unsupported',
                )
            return self.input_text({
                '内容': arguments.get('official.input.type_text.parameter.content') or '',
                '模式': mode,
            }, cancelled)
        if opcode == 'input.scroll' and 'official.input.scroll.parameter.direction' in arguments:
            return self._execute_v6_scroll(arguments, cancelled)
        if opcode == 'input.drag':
            return self._execute_v6_drag(arguments, cancelled)
        if opcode == 'input.key':
            return self._execute_v6_key(arguments, cancelled)
        if opcode == 'text.recognize':
            return self._execute_v6_ocr(arguments)
        raise RuntimeFailure(f'目标驱动不支持：{opcode}')

    @staticmethod
    def _v6_point(value: Any) -> list[int] | None:
        if value is None:
            return None
        if isinstance(value, dict) and value.get('kind') == 'point':
            return [int(value.get('x', 0)), int(value.get('y', 0))]
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return [int(value[0]), int(value[1])]
        raise RuntimeFailure('坐标参数无效', error_id='target.invalid_point')

    @staticmethod
    def _v6_rect(value: Any) -> list[int] | None:
        if value is None:
            return None
        try:
            if isinstance(value, dict) and value.get('kind') == 'rect':
                raw = [value.get('x'), value.get('y'), value.get('width'), value.get('height')]
            elif isinstance(value, (list, tuple)) and len(value) == 4:
                raw = list(value)
            else:
                raw = []
            if len(raw) == 4 and not any(isinstance(item, bool) for item in raw):
                return [int(item) for item in raw]
        except (TypeError, ValueError, OverflowError):
            pass
        raise RuntimeFailure('区域参数无效', error_id='target.invalid_rect')

    def _capture_frame_reference(self) -> dict[str, Any]:
        frame = self.capture_frame()
        self._frame_sequence += 1
        frame_id = f'frame.{self._frame_sequence}'
        if hasattr(frame, 'shape'):
            height, width = (int(item) for item in frame.shape[:2])
        else:
            width, height = (int(item) for item in frame.size)
        target_reference = {
            'kind': 'target_ref',
            'target_id': str(self.target.get('target_id') or ''),
        }
        space_version = str(self.target.get('space_version') or '').strip()
        if not space_version:
            space_version = f'{target_reference["target_id"] or self.platform}:{width}x{height}'
        reference = {
            'kind': 'frame_ref',
            'frame_ref.field.frame_id': frame_id,
            'frame_ref.field.source_target': target_reference,
            'frame_ref.field.space_version': space_version,
            'frame_ref.field.sequence': self._frame_sequence,
            'frame_ref.field.captured_at': datetime.now(timezone.utc).isoformat(),
            'frame_ref.field.width': width,
            'frame_ref.field.height': height,
        }
        # References are serializable; raw pixels remain owned by the hot
        # target session and never leak into snapshots or ECIR.
        self._frame_references[frame_id] = {'pixels': frame, 'reference': reference}
        return deepcopy(reference)

    def _frame_for_v6_call(
        self,
        arguments: dict[str, Any],
        owner_function_id: str,
    ) -> tuple[Any, dict[str, Any], str]:
        parameter_id = f'{owner_function_id}.parameter.frame'
        supplied = arguments.get(parameter_id)
        if supplied is None:
            reference = self._capture_frame_reference()
        else:
            if not isinstance(supplied, dict) or supplied.get('kind') != 'frame_ref':
                raise RuntimeFailure('画面引用格式无效', error_id='vision.frame_reference_invalid')
            frame_id = str(supplied.get('frame_ref.field.frame_id') or '')
            if not frame_id:
                raise RuntimeFailure('画面引用缺少稳定帧 ID', error_id='vision.frame_reference_invalid')
            reference = supplied
        frame_id = str(reference.get('frame_ref.field.frame_id') or '')
        stored = self._frame_references.get(frame_id)
        if not isinstance(stored, dict) or 'pixels' not in stored or 'reference' not in stored:
            raise RuntimeFailure('画面引用已失效', error_id='vision.frame_reference_expired')
        canonical = stored['reference']
        if supplied is not None and supplied != canonical:
            raise RuntimeFailure('画面引用元数据与当前运行不一致', error_id='vision.frame_reference_invalid')
        source_target = canonical.get('frame_ref.field.source_target')
        source_target_id = str(source_target.get('target_id') or '') if isinstance(source_target, dict) else ''
        current_target_id = str(self.target.get('target_id') or '')
        if source_target_id != current_target_id:
            raise RuntimeFailure('画面引用来自其他操作目标', error_id='vision.frame_reference_invalid')
        return stored['pixels'], deepcopy(canonical), frame_id

    def _execute_frame_save(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        owner = 'official.frame.save'
        frame, _, _ = self._frame_for_v6_call(arguments, owner)
        region = self._v6_rect(arguments.get(f'{owner}.parameter.region'))
        cropped, _, _ = self._crop(frame, region)
        image_format = str(arguments.get(f'{owner}.parameter.format') or 'png').lower()
        if image_format not in {'png', 'jpeg'}:
            raise RuntimeFailure('图片格式只支持 PNG 或 JPEG', error_id='vision.image_format_unsupported')
        quality = arguments.get(f'{owner}.parameter.quality', 90)
        if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100:
            raise RuntimeFailure('JPEG 质量必须为 1 至 100 的整数', error_id='vision.image_quality_invalid')
        if cancelled():
            raise RuntimeFailure('画面保存已取消', error_id='runtime.cancelled')
        try:
            import io
            from PIL import Image

            if hasattr(cropped, 'save'):
                image = cropped
            elif self.frame_is_bgr:
                import cv2
                image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
            else:
                image = Image.fromarray(cropped)
            output = io.BytesIO()
            options = {'quality': quality, 'optimize': True} if image_format == 'jpeg' else {}
            if image_format == 'jpeg' and image.mode not in {'RGB', 'L'}:
                image = image.convert('RGB')
            image.save(output, format='JPEG' if image_format == 'jpeg' else 'PNG', **options)
            content = output.getvalue()
        except Exception as exc:
            raise RuntimeFailure(f'画面编码失败：{exc}', error_id='vision.image_encode_failed', transient=True) from exc
        from .file_runtime_v6 import FileRuntimeV6
        result = FileRuntimeV6().write_authorized_bytes(
            arguments.get(f'{owner}.parameter.file'), content, cancelled,
        )
        self._set_message(f'已保存{image.size[0]}×{image.size[1]} {image_format.upper()} 画面')
        return result

    @staticmethod
    def _v6_color(value: Any) -> tuple[int, int, int, int]:
        if not isinstance(value, dict):
            raise RuntimeFailure('颜色参数无效', error_id='vision.color_invalid')
        try:
            channels = tuple(
                value[f'color.field.{name}'] for name in ('red', 'green', 'blue', 'alpha')
            )
        except KeyError as exc:
            raise RuntimeFailure('颜色参数缺少颜色通道', error_id='vision.color_invalid') from exc
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 255 for item in channels):
            raise RuntimeFailure('颜色通道必须是 0 到 255 的整数', error_id='vision.color_invalid')
        return channels

    @staticmethod
    def _color_result(red: int, green: int, blue: int, alpha: int = 255) -> dict[str, int]:
        return {
            'color.field.red': int(red),
            'color.field.green': int(green),
            'color.field.blue': int(blue),
            'color.field.alpha': int(alpha),
        }

    def _execute_color_read(self, arguments: dict[str, Any]) -> dict[str, int]:
        owner = 'official.color.read'
        frame, _, _ = self._frame_for_v6_call(arguments, owner)
        point = self._v6_point(arguments.get(f'{owner}.parameter.position'))
        if point is None:
            raise RuntimeFailure('颜色读取位置不能为空', error_id='target.invalid_point')
        image = frame_to_bgr(frame, frame_is_bgr=self.frame_is_bgr)
        height, width = image.shape[:2]
        x, y = point
        if x < 0 or y < 0 or x >= width or y >= height:
            raise RuntimeFailure('颜色读取位置超出当前画面', error_id='target.invalid_point')
        blue, green, red = (int(item) for item in image[y, x][:3])
        return self._color_result(red, green, blue)

    def _execute_color_find(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any] | None:
        import numpy as np

        owner = 'official.color.find'
        expected_red, expected_green, expected_blue, expected_alpha = self._v6_color(
            arguments.get(f'{owner}.parameter.color')
        )
        tolerance = arguments.get(f'{owner}.parameter.tolerance', 0)
        if isinstance(tolerance, bool) or not isinstance(tolerance, int) or tolerance < 0 or tolerance > 255:
            raise RuntimeFailure('颜色容差必须是 0 到 255 的整数', error_id='vision.color_tolerance_invalid')
        try:
            region = self._v6_rect(arguments.get(f'{owner}.parameter.region'))
        except RuntimeFailure as exc:
            raise RuntimeFailure(str(exc), error_id='vision.region_invalid') from exc
        frame, _, _ = self._frame_for_v6_call(arguments, owner)
        cropped, offset_x, offset_y, crop_meta = self._analysis_crop(frame, region)
        if cropped is None:
            self._set_message('颜色.查找：未命中，搜索区域与当前画面无交集')
            return None
        clip_note = '，搜索区域已按当前画面裁剪' if crop_meta.get('region_clipped') else ''
        if abs(255 - expected_alpha) > tolerance:
            self._set_message(f'颜色.查找：未命中{clip_note}')
            return None
        image = frame_to_bgr(cropped, frame_is_bgr=self.frame_is_bgr)
        expected = np.asarray([expected_blue, expected_green, expected_red], dtype=np.int16)
        for start in range(0, image.shape[0], 256):
            if cancelled():
                raise RuntimeFailure('颜色查找已取消', error_id='runtime.cancelled')
            stripe = image[start:start + 256, :, :3].astype(np.int16, copy=False)
            mask = np.all(np.abs(stripe - expected) <= tolerance, axis=2)
            positions = np.argwhere(mask)
            if positions.size:
                y, x = (int(item) for item in positions[0])
                result = {'kind': 'point', 'x': offset_x + x, 'y': offset_y + start + y}
                self._set_message(
                    f"颜色.查找：命中坐标({result['x']}, {result['y']}){clip_note}"
                )
                return result
        self._set_message(f'颜色.查找：未命中{clip_note}')
        return None

    def _execute_v6_click(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        position = self._v6_point(arguments.get('official.input.click.parameter.position'))
        if position is None:
            raise RuntimeFailure('输入.点击缺少位置', error_id='target.invalid_point')
        button = str(arguments.get('official.input.click.parameter.button') or 'primary')
        button_name = {'primary': '左键', 'secondary': '右键', 'middle': '中键'}.get(button)
        if button_name is None:
            raise RuntimeFailure(f'不支持的指针按键：{button}', error_id='target.pointer_button_unsupported')
        count = arguments.get('official.input.click.parameter.count', 1)
        hold = arguments.get('official.input.click.parameter.hold', 0)
        interval = arguments.get('official.input.click.parameter.interval', 80)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise RuntimeFailure('点击次数必须是正整数', error_id='target.invalid_click_count')
        if isinstance(hold, bool) or not isinstance(hold, (int, float)) or not math.isfinite(float(hold)) or hold < 0 or hold > 60000:
            raise RuntimeFailure('保持时间必须在 0 至 60 秒之间', error_id='target.invalid_click_hold')
        last: dict[str, Any] = {}
        for index in range(count):
            if cancelled():
                raise RuntimeFailure('点击已取消', error_id='runtime.cancelled')
            if float(hold) > 0:
                last = self.drag_path({
                    '路径': [{'point': [position[0], position[1]], 'move_ms': 0, 'hold_ms': int(hold)}],
                    '缓动': '线性',
                    '按键': button_name,
                }, cancelled)
            else:
                last = self.tap_point(position[0], position[1], button_name)
            if index + 1 < count and float(interval or 0) > 0:
                deadline = time.monotonic() + float(interval) / 1000
                while time.monotonic() < deadline:
                    if cancelled():
                        raise RuntimeFailure('点击已取消', error_id='runtime.cancelled')
                    time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        action = '长按' if float(hold) > 0 else '点击'
        return {**last, 'message': str(last.get('message') or f'已{action} {count} 次')}

    def _execute_v6_scroll(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        mode = str(arguments.get('official.input.scroll.parameter.mode') or 'auto')
        if mode == 'wheel' and self.platform != 'windows':
            raise RuntimeFailure('ADB 目标不支持滚轮模式', error_id='target.scroll_mode_unsupported')
        if mode not in {'auto', 'wheel', 'touch'}:
            raise RuntimeFailure(f'不支持的滚动模式：{mode}', error_id='target.scroll_mode_unsupported')
        direction = str(arguments.get('official.input.scroll.parameter.direction') or 'down')
        if direction not in {'up', 'down', 'left', 'right'}:
            raise RuntimeFailure(f'不支持的滚动方向：{direction}', error_id='target.scroll_direction_unsupported')
        distance = float(arguments.get('official.input.scroll.parameter.distance', 0.6) or 0.6)
        if distance <= 0:
            raise RuntimeFailure('滚动距离必须大于 0', error_id='target.invalid_scroll_distance')
        direction_names = {'up': '上', 'down': '下', 'left': '左', 'right': '右'}
        return self.scroll({
            '方向': direction_names[direction],
            '模式': mode,
            '距离比例': distance,
            '数量': max(1, min(10, round(distance * 10))),
            '位置': self._v6_point(arguments.get('official.input.scroll.parameter.start')),
            '移动时长': arguments.get('official.input.scroll.parameter.duration', 350),
            '终点保持': arguments.get('official.input.scroll.parameter.hold', 80),
        }, cancelled)

    def _execute_v6_drag(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        raw_path = arguments.get('official.input.drag.parameter.path')
        if isinstance(raw_path, dict) and raw_path.get('kind') == 'path':
            raw_path = [
                [int(point.get('x', 0)), int(point.get('y', 0))]
                for point in raw_path.get('points') or []
            ]
        if not isinstance(raw_path, list) or len(raw_path) < 2:
            raise RuntimeFailure('输入.拖拽 的路径至少需要起点和终点', error_id='target.invalid_drag_path')
        duration = arguments.get('official.input.drag.parameter.duration', 350)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(float(duration)) or not 1 <= duration <= 60000:
            raise RuntimeFailure('移动时长必须在 1 毫秒至 60 秒之间', error_id='target.invalid_duration')
        points = [self._v6_point(item) for item in raw_path]
        if any(point is None for point in points):
            raise RuntimeFailure('输入.拖拽 包含无效坐标', error_id='target.invalid_drag_path')
        lengths = [
            math.hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1])
            for index in range(1, len(points))
        ]
        total_length = sum(lengths)
        segment_durations = (
            [float(duration) / len(lengths) for _ in lengths]
            if total_length == 0
            else [float(duration) * length / total_length for length in lengths]
        )
        rounded = [max(0, round(value)) for value in segment_durations]
        if rounded:
            rounded[-1] += int(duration) - sum(rounded)
        raw_path = [
            {'point': [points[0][0], points[0][1]], 'move_ms': 0, 'hold_ms': 0},
            *[
                {'point': [point[0], point[1]], 'move_ms': max(0, rounded[index]), 'hold_ms': 0}
                for index, point in enumerate(points[1:])
            ],
        ]
        easing = str(arguments.get('official.input.drag.parameter.easing') or 'linear')
        if easing not in {'linear', 'ease_in_out'}:
            raise RuntimeFailure(f'不支持的拖拽缓动：{easing}', error_id='target.drag_easing_unsupported')
        return self.drag_path({
            '路径': raw_path,
            '缓动': '缓入缓出' if easing == 'ease_in_out' else '线性',
        }, cancelled)

    @staticmethod
    def _v6_key_chord(value: Any) -> list[str]:
        if not isinstance(value, dict):
            raise RuntimeFailure('按键参数需要强类型 key_chord', error_id='target.invalid_key')
        raw = value.get('key_chord.field.keys')
        if not isinstance(raw, list) or not raw or len(raw) > 4:
            raise RuntimeFailure('按键组合必须包含 1 至 4 个键', error_id='target.invalid_key')
        aliases = {'control': 'ctrl', 'return': 'enter', 'esc': 'escape', 'del': 'delete'}
        keys = [aliases.get(str(item).strip().casefold(), str(item).strip().casefold()) for item in raw]
        if any(not item or not re.fullmatch(r'[a-z0-9_+\-]{1,24}', item) for item in keys):
            raise RuntimeFailure('按键组合包含无效键名', error_id='target.invalid_key')
        if len(set(keys)) != len(keys):
            raise RuntimeFailure('按键组合不能包含重复键', error_id='target.invalid_key')
        return keys

    def _execute_v6_key(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        keys = self._v6_key_chord(arguments.get('official.input.key.parameter.key'))
        action = str(arguments.get('official.input.key.parameter.action') or 'press')
        if action not in {'press', 'down', 'up'}:
            raise RuntimeFailure(f'不支持的按键动作：{action}', error_id='target.invalid_key_action')
        hold_ms = arguments.get('official.input.key.parameter.hold', 0)
        if isinstance(hold_ms, bool) or not isinstance(hold_ms, (int, float)) or hold_ms < 0:
            raise RuntimeFailure('按键保持时间无效', error_id='target.invalid_key_hold')
        if action != 'press' and hold_ms:
            raise RuntimeFailure('仅“按下并释放”动作可以设置保持时间', error_id='target.invalid_key_hold')
        return self.press_key(keys, action, int(hold_ms), cancelled)

    @staticmethod
    def _v6_similarity(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeFailure('相似度必须是 0 到 1 的数字', error_id='vision.similarity_invalid')
        similarity = float(value)
        if not math.isfinite(similarity) or not 0 <= similarity <= 1:
            raise RuntimeFailure('相似度必须是 0 到 1 的数字', error_id='vision.similarity_invalid')
        return similarity

    @staticmethod
    def _reject_unknown_v6_arguments(
        arguments: dict[str, Any],
        owner_function_id: str,
        parameter_names: tuple[str, ...],
    ) -> None:
        allowed = {
            f'{owner_function_id}.parameter.{name}' for name in parameter_names
        }
        unknown = set(arguments) - allowed
        if unknown:
            raise RuntimeFailure(
                f'函数参数必须使用稳定 parameter_id，未知参数：{sorted(unknown)}',
                error_id='runtime.argument_type',
            )

    @staticmethod
    def _v6_result_limit(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
            raise RuntimeFailure('最大结果数必须是 1 到 1000 的整数', error_id='vision.limit_invalid')
        return value

    def _prepared_v6_asset(self, reference: Any) -> tuple[Any, dict[str, Any]]:
        if not isinstance(reference, dict) or reference.get('kind') != 'asset_ref':
            raise RuntimeFailure('图片参数需要稳定资源引用', error_id='vision.asset_reference_invalid')
        asset_id = str(reference.get('asset_id') or '').strip()
        if not asset_id:
            raise RuntimeFailure('图片资源引用缺少 asset_id', error_id='vision.asset_reference_invalid')
        try:
            path, metadata = ProjectAssetService(self.project_path).content_path(asset_id)
        except VNextWorkspaceError as exc:
            detail = str(exc)
            error_id = (
                'vision.asset_corrupt'
                if any(marker in detail for marker in ('哈希', '格式无效', '无法读取'))
                else 'vision.asset_missing'
            )
            raise RuntimeFailure(str(exc), error_id=error_id) from exc
        digest = str(metadata.get('sha256') or '')
        cached = getattr(self, '_prepared_asset_cache', {}).get(asset_id)
        if cached is not None and cached[0] == digest:
            return cached[1], {'kind': 'asset_ref', 'asset_id': asset_id}
        try:
            template = load_image(path)
            variants = prepare_template_cv(
                template,
                gray_scale=False,
                scales=(1.0, 0.9, 1.1, 0.75),
            )
        except Exception as exc:
            raise RuntimeFailure(f'图片资源无法解码：{exc}', error_id='vision.asset_corrupt') from exc
        if not variants:
            raise RuntimeFailure('图片资源尺寸过小，无法用于匹配', error_id='vision.asset_corrupt')
        if not hasattr(self, '_prepared_asset_cache'):
            self._prepared_asset_cache = {}
        self._prepared_asset_cache[asset_id] = (digest, variants)
        return variants, {'kind': 'asset_ref', 'asset_id': asset_id}

    @staticmethod
    def _v6_image_match_record(
        match: Any,
        *,
        source_asset: dict[str, Any],
        source_frame: dict[str, Any],
    ) -> dict[str, Any]:
        x, y, width, height = match.region
        center_x, center_y = match.center
        return {
            'image_match.field.region': {
                'kind': 'rect', 'x': x, 'y': y, 'width': width, 'height': height,
            },
            'image_match.field.center': {'kind': 'point', 'x': center_x, 'y': center_y},
            'image_match.field.similarity': float(match.similarity),
            'image_match.field.source_asset': deepcopy(source_asset),
            'image_match.field.source_frame': deepcopy(source_frame),
            'image_match.field.source_target': deepcopy(source_frame['frame_ref.field.source_target']),
            'image_match.field.space_version': str(source_frame['frame_ref.field.space_version']),
        }

    def _v6_find_matches(
        self,
        arguments: dict[str, Any],
        *,
        owner_function_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        image_parameter = f'{owner_function_id}.parameter.image'
        similarity_parameter = f'{owner_function_id}.parameter.similarity'
        region_parameter = f'{owner_function_id}.parameter.region'
        variants, source_asset = self._prepared_v6_asset(arguments.get(image_parameter))
        similarity = self._v6_similarity(arguments.get(similarity_parameter, 0.85))
        try:
            region = self._v6_rect(arguments.get(region_parameter))
        except RuntimeFailure as exc:
            raise RuntimeFailure(str(exc), error_id='vision.region_invalid') from exc
        frame, source_frame, _ = self._frame_for_v6_call(arguments, owner_function_id)
        cropped, offset_x, offset_y, crop_meta = self._analysis_crop(frame, region)
        self._last_image_match_diagnostic = {
            'owner_function_id': owner_function_id,
            'best_similarity': None,
            'threshold': similarity,
            'match_count': 0,
            **crop_meta,
        }
        if cropped is None:
            return []
        try:
            analysis = analyze_template_matches(
                cropped,
                variants,
                threshold=similarity,
                limit=limit,
                offset_x=offset_x,
                offset_y=offset_y,
                frame_is_bgr=self.frame_is_bgr,
            )
        except Exception as exc:
            raise RuntimeFailure(
                f'图像分析失败：{exc}',
                error_id='vision.analysis_failed',
                transient=True,
            ) from exc
        self._last_image_match_diagnostic = {
            'owner_function_id': owner_function_id,
            'best_similarity': analysis.best_similarity,
            'threshold': similarity,
            'match_count': len(analysis.matches),
            **crop_meta,
        }
        return [
            self._v6_image_match_record(
                item,
                source_asset=source_asset,
                source_frame=source_frame,
            )
            for item in analysis.matches
        ]

    def _v6_match_message(self, prefix: str, matches: list[dict[str, Any]], threshold: float) -> str:
        diagnostic = self.image_match_diagnostic()
        if diagnostic.get('region_empty'):
            return f'{prefix}，搜索区域与当前画面无交集，阈值 {threshold:.3f}'
        best = diagnostic.get('best_similarity')
        if not isinstance(best, (int, float)) and matches:
            best = matches[0].get('image_match.field.similarity')
        score = f'最高相似度 {float(best):.3f}' if isinstance(best, (int, float)) else '最高相似度不可用'
        clipped = '，搜索区域已按当前画面裁剪' if diagnostic.get('region_clipped') else ''
        return f'{prefix}，{score}，阈值 {threshold:.3f}{clipped}'

    def _execute_v6_find(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        self._reject_unknown_v6_arguments(
            arguments,
            'official.image.find',
            ('image', 'similarity', 'region', 'frame'),
        )
        matches = self._v6_find_matches(
            arguments,
            owner_function_id='official.image.find',
            limit=1,
        )
        threshold = self._v6_similarity(
            arguments.get('official.image.find.parameter.similarity', 0.85)
        )
        if not matches:
            self._set_message(self._v6_match_message('图像.查找：未命中', matches, threshold))
            return None
        self._set_message(self._v6_match_message('图像.查找：命中', matches, threshold))
        return matches[0]

    def _execute_v6_find_all(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        self._reject_unknown_v6_arguments(
            arguments,
            'official.image.find_all',
            ('image', 'similarity', 'region', 'frame', 'limit'),
        )
        limit = self._v6_result_limit(
            arguments.get('official.image.find_all.parameter.limit', 100)
        )
        matches = self._v6_find_matches(
            arguments,
            owner_function_id='official.image.find_all',
            limit=limit,
        )
        threshold = self._v6_similarity(
            arguments.get('official.image.find_all.parameter.similarity', 0.85)
        )
        prefix = (
            f'图像.查找全部：命中 {len(matches)} 个结果'
            if matches else '图像.查找全部：未命中'
        )
        self._set_message(self._v6_match_message(prefix, matches, threshold))
        return matches

    @staticmethod
    def _v6_ocr_preprocess(value: Any) -> tuple[bool, bool, int, bool]:
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise RuntimeFailure('OCR 预处理参数格式无效', error_id='ocr.preprocess_invalid')
        allowed = {
            'ocr_preprocess.field.grayscale',
            'ocr_preprocess.field.binary',
            'ocr_preprocess.field.threshold',
            'ocr_preprocess.field.invert',
        }
        unknown = set(value) - allowed
        if unknown:
            raise RuntimeFailure(
                f'OCR 预处理包含未知字段：{sorted(unknown)}',
                error_id='ocr.preprocess_invalid',
            )
        grayscale = value.get('ocr_preprocess.field.grayscale', False)
        binary = value.get('ocr_preprocess.field.binary', False)
        invert = value.get('ocr_preprocess.field.invert', False)
        threshold = value.get('ocr_preprocess.field.threshold', 127)
        if not all(isinstance(item, bool) for item in (grayscale, binary, invert)):
            raise RuntimeFailure('OCR 预处理开关必须是布尔值', error_id='ocr.preprocess_invalid')
        if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
            raise RuntimeFailure('OCR 二值化阈值必须是 0 到 255 的整数', error_id='ocr.preprocess_invalid')
        return grayscale, binary, threshold, invert

    def _execute_v6_ocr(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from core.vision.ocr_engine import (
            OcrAdapterError,
            ocr_engine_recognize_detailed,
            preprocess_ocr_image,
        )

        self._reject_unknown_v6_arguments(
            arguments,
            'official.text.recognize',
            ('region', 'language', 'frame', 'preprocess'),
        )
        language = str(arguments.get('official.text.recognize.parameter.language') or 'auto')
        if language != 'auto':
            raise RuntimeFailure(f'当前 OCR 不支持语言模式：{language}', error_id='ocr.language_unsupported')
        preprocess = self._v6_ocr_preprocess(
            arguments.get('official.text.recognize.parameter.preprocess')
        )
        try:
            region = self._v6_rect(arguments.get('official.text.recognize.parameter.region'))
        except RuntimeFailure as exc:
            raise RuntimeFailure(str(exc), error_id='vision.region_invalid') from exc
        frame, source_frame, frame_id = self._frame_for_v6_call(
            arguments,
            'official.text.recognize',
        )
        cropped, offset_x, offset_y, crop_meta = self._analysis_crop(frame, region)
        if cropped is None:
            actual = crop_meta['actual_region']
            result = {
                'ocr_result.field.text': '',
                'ocr_result.field.lines': [],
                'ocr_result.field.region': {
                    'kind': 'rect',
                    'x': actual[0], 'y': actual[1],
                    'width': actual[2], 'height': actual[3],
                },
                'ocr_result.field.source_frame': deepcopy(source_frame),
                'ocr_result.field.source_target': deepcopy(source_frame['frame_ref.field.source_target']),
                'ocr_result.field.space_version': str(source_frame['frame_ref.field.space_version']),
            }
            self._set_message('[OCR] 未识别到有效文字 | 搜索区域与当前画面无交集')
            return result
        if hasattr(cropped, 'shape'):
            crop_height, crop_width = (int(item) for item in cropped.shape[:2])
        else:
            crop_width, crop_height = (int(item) for item in cropped.size)
        actual_region = (offset_x, offset_y, crop_width, crop_height)
        cache_key = (frame_id, actual_region, language, preprocess)
        cached = getattr(self, '_ocr_analysis_cache', {}).get(cache_key)
        if cached is not None:
            result = deepcopy(cached)
        else:
            grayscale, binary, threshold, invert = preprocess
            try:
                image_bgr = frame_to_bgr(cropped, frame_is_bgr=self.frame_is_bgr)
                prepared = preprocess_ocr_image(
                    image_bgr,
                    gray_scale=grayscale or binary,
                    gray_threshold=threshold,
                    binary=binary,
                    invert=invert,
                )
                recognized = ocr_engine_recognize_detailed(prepared)
            except OcrAdapterError as exc:
                error_id = (
                    'ocr.engine_unavailable'
                    if exc.reason == 'engine_unavailable'
                    else 'ocr.inference_failed'
                )
                raise RuntimeFailure(
                    str(exc),
                    error_id=error_id,
                    transient=error_id == 'ocr.inference_failed',
                ) from exc
            except Exception as exc:
                raise RuntimeFailure(
                    f'OCR 分析失败：{exc}',
                    error_id='ocr.inference_failed',
                    transient=True,
                ) from exc
            lines = []
            for line in recognized.lines:
                x, y, width, height = line.region
                lines.append({
                    'ocr_line.field.text': line.text,
                    'ocr_line.field.region': {
                        'kind': 'rect',
                        'x': int(x + offset_x),
                        'y': int(y + offset_y),
                        'width': int(width),
                        'height': int(height),
                    },
                })
            result = {
                'ocr_result.field.text': recognized.text,
                'ocr_result.field.lines': lines,
                'ocr_result.field.region': {
                    'kind': 'rect',
                    'x': offset_x, 'y': offset_y,
                    'width': crop_width, 'height': crop_height,
                },
                'ocr_result.field.source_frame': deepcopy(source_frame),
                'ocr_result.field.source_target': deepcopy(source_frame['frame_ref.field.source_target']),
                'ocr_result.field.space_version': str(source_frame['frame_ref.field.space_version']),
            }
            if not hasattr(self, '_ocr_analysis_cache'):
                self._ocr_analysis_cache = {}
            self._ocr_analysis_cache[cache_key] = deepcopy(result)
        area = list(actual_region)
        text = str(result['ocr_result.field.text'])
        clip_note = ' | 已按当前画面裁剪' if crop_meta.get('region_clipped') else ''
        self._set_message(
            (f'[OCR] 识别文字={text!r} | 区域={area}' if text else f'[OCR] 未识别到有效文字 | 区域={area}')
            + clip_note
        )
        return result

    def capture_frame(self) -> Any:
        raise NotImplementedError

    def tap_point(self, x: int, y: int, button: str) -> dict[str, Any]:
        raise NotImplementedError

    def input_text(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        raise NotImplementedError

    def scroll(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        raise NotImplementedError

    def drag_path(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        raise NotImplementedError

    def press_key(
        self,
        keys: list[str],
        action: str,
        hold_ms: int,
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _crop(frame: Any, region: Any) -> tuple[Any, int, int]:
        if region is None:
            return frame, 0, 0
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise RuntimeFailure('识别区域必须是 [x, y, 宽, 高]', error_id='vision.region_invalid')
        x, y, width, height = (int(value) for value in region)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise RuntimeFailure(
                '识别区域必须为正尺寸且不能超出左上边界',
                error_id='vision.region_invalid',
            )
        if hasattr(frame, 'shape'):
            frame_height, frame_width = frame.shape[:2]
            if x + width > frame_width or y + height > frame_height:
                raise RuntimeFailure('识别区域超出目标画面', error_id='vision.region_invalid')
            return frame[y:y + height, x:x + width], x, y
        frame_width, frame_height = frame.size
        if x + width > frame_width or y + height > frame_height:
            raise RuntimeFailure('识别区域超出目标画面', error_id='vision.region_invalid')
        return frame.crop((x, y, x + width, y + height)), x, y

    @staticmethod
    def _analysis_crop(frame: Any, region: Any) -> tuple[Any | None, int, int, dict[str, Any]]:
        """Crop a visual-analysis region to the pixels that still exist.

        Author regions are captured in a target coordinate space that can be a
        few pixels larger than a later frame.  Analysis treats the region as a
        search hint: partial overlap is clamped and no overlap is a normal
        empty analysis.  File export keeps using ``_crop`` and remains strict.
        """

        if hasattr(frame, 'shape'):
            frame_height, frame_width = (int(item) for item in frame.shape[:2])
        else:
            frame_width, frame_height = (int(item) for item in frame.size)
        if region is None:
            actual = [0, 0, frame_width, frame_height]
            return frame, 0, 0, {
                'requested_region': actual,
                'actual_region': actual,
                'region_clipped': False,
                'region_empty': frame_width <= 0 or frame_height <= 0,
            }
        if not isinstance(region, (list, tuple)) or len(region) != 4 or any(isinstance(item, bool) for item in region):
            raise RuntimeFailure('识别区域必须是 [x, y, 宽, 高]', error_id='vision.region_invalid')
        try:
            x, y, width, height = (int(value) for value in region)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeFailure('识别区域必须是 [x, y, 宽, 高]', error_id='vision.region_invalid') from exc
        if width <= 0 or height <= 0:
            raise RuntimeFailure('识别区域宽高必须大于 0', error_id='vision.region_invalid')

        right = x + width
        bottom = y + height
        actual_left = max(0, min(frame_width, x))
        actual_top = max(0, min(frame_height, y))
        actual_right = max(0, min(frame_width, right))
        actual_bottom = max(0, min(frame_height, bottom))
        actual_width = max(0, actual_right - actual_left)
        actual_height = max(0, actual_bottom - actual_top)
        requested = [x, y, width, height]
        actual = [actual_left, actual_top, actual_width, actual_height]
        meta = {
            'requested_region': requested,
            'actual_region': actual,
            'region_clipped': actual != requested,
            'region_empty': actual_width == 0 or actual_height == 0,
        }
        if meta['region_empty']:
            return None, actual_left, actual_top, meta
        if hasattr(frame, 'shape'):
            return frame[actual_top:actual_bottom, actual_left:actual_right], actual_left, actual_top, meta
        return frame.crop((actual_left, actual_top, actual_right, actual_bottom)), actual_left, actual_top, meta

    def _prepared(self, arguments: dict[str, Any]):
        image_path = self.resolve_image(arguments.get('图片'))
        template = load_image(image_path)
        return prepare_template_cv(template, gray_scale=False, scales=(1.0, 0.9, 1.1, 0.75))

    def _match_frame_once(self, source_frame: Any, variants: Any, threshold: float, region: Any = None) -> dict[str, Any]:
        frame, offset_x, offset_y, _ = self._analysis_crop(source_frame, region)
        if frame is None:
            return {'已找到': False, '置信度': -1.0, '中心': None, '区域': None}
        confidence = -1.0
        center = None
        matched_size = None
        for width, height, prepared in variants:
            candidate_confidence, candidate_center = match_prepared_template_cv(
                frame,
                ((width, height, prepared),),
                screen_is_bgr=self.frame_is_bgr,
            )
            if candidate_confidence > confidence:
                confidence = candidate_confidence
                center = candidate_center
                matched_size = (width, height)
        found = center is not None and confidence >= threshold
        match_region = None
        if found and matched_size is not None:
            width, height = matched_size
            match_region = [
                int(center[0] - width // 2 + offset_x),
                int(center[1] - height // 2 + offset_y),
                int(width), int(height),
            ]
        return {
            '已找到': bool(found), '置信度': float(confidence),
            '中心': [int(center[0] + offset_x), int(center[1] + offset_y)] if found else None,
            '区域': match_region,
        }

    def _match_once(self, variants: Any, threshold: float, region: Any = None) -> dict[str, Any]:
        return self._match_frame_once(self.capture_frame(), variants, threshold, region)

    @staticmethod
    def normalize_path(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) < 1:
            raise RuntimeFailure('输入.拖拽 的路径至少需要一个起点')
        result = []
        for index, item in enumerate(value[:32]):
            if isinstance(item, (list, tuple)):
                point, move_ms, hold_ms = item, 300 if index else 0, 0
            elif isinstance(item, dict):
                point = item.get('位置', item.get('point'))
                move_ms = item.get('移动时长', item.get('move_ms', 300 if index else 0))
                hold_ms = item.get('保持时间', item.get('hold_ms', 0))
            else:
                raise RuntimeFailure(f'拖拽路径第 {index + 1} 个点无效')
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise RuntimeFailure(f'拖拽路径第 {index + 1} 个点缺少坐标')
            result.append({'point': [int(point[0]), int(point[1])], 'move_ms': int(move_ms or 0), 'hold_ms': int(hold_ms or 0)})
        return result

    def close(self) -> None:
        self._frame_references.clear()
        self._ocr_analysis_cache.clear()
        self._prepared_asset_cache.clear()
        return None

    def capture_overlay_region(self) -> list[int] | None:
        """Return an absolute Windows screen box when one truly exists."""

        return None


class WindowsTargetDriver(TargetDriver):
    platform = 'windows'

    def __init__(self, project_path: str, target: dict[str, Any]) -> None:
        super().__init__(project_path, target)
        self.hwnd = self._find_window()
        self._box = self._workspace_box()
        self._window_references: dict[str, dict[str, Any]] = {}
        self._control_references: dict[str, dict[str, Any]] = {}

    @staticmethod
    def supports(opcode: str) -> bool:
        return TargetDriver.supports(opcode) or opcode in {
            'input.move_pointer',
            'window.find', 'window.current', 'window.activate', 'window.close', 'window.status',
            'window.move', 'window.resize', 'window.ensure_visible', 'window.set_display_state',
            'control.find', 'control.click', 'control.click_selector', 'control.read_text', 'control.input_text',
            'control.read_status', 'control.focus', 'control.set_value', 'control.select',
            'control.toggle', 'control.scroll_into_view',
        }

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> Any:
        if opcode.startswith('window.'):
            return self._execute_window(opcode, arguments, cancelled)
        if opcode.startswith('control.'):
            return self._execute_control(opcode, arguments, cancelled)
        if opcode == 'input.move_pointer':
            return self._execute_move_pointer(arguments, cancelled)
        return super().execute(opcode, arguments, cancelled)

    @staticmethod
    def _activate_window(hwnd: int) -> None:
        """Activate a top-level window, including Windows foreground-lock fallback."""

        import win32con
        import win32gui

        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            if int(win32gui.GetForegroundWindow() or 0) == int(hwnd):
                return
        except Exception:
            # SetForegroundWindow is intentionally restricted by Windows. A
            # process may operate an explicitly bound window but still need to
            # join the current foreground input queue before Windows accepts it.
            pass

        attached: list[tuple[int, int]] = []
        try:
            import win32api
            import win32process

            current_thread = int(win32api.GetCurrentThreadId())
            target_thread = int(win32process.GetWindowThreadProcessId(hwnd)[0])
            foreground = int(win32gui.GetForegroundWindow() or 0)
            foreground_thread = (
                int(win32process.GetWindowThreadProcessId(foreground)[0]) if foreground else 0
            )
            for other_thread in {target_thread, foreground_thread}:
                if other_thread and other_thread != current_thread:
                    try:
                        win32process.AttachThreadInput(current_thread, other_thread, True)
                        attached.append((current_thread, other_thread))
                    except Exception:
                        pass
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
            )
            win32gui.BringWindowToTop(hwnd)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                # A few shells keep rejecting SetForegroundWindow even after
                # the documented input-queue handoff. SwitchToThisWindow is a
                # final user-visible activation request, not an input/click
                # fallback, and is verified below before success is returned.
                import ctypes

                ctypes.windll.user32.SwitchToThisWindow(int(hwnd), True)
        finally:
            if attached:
                import win32process

                for first, second in reversed(attached):
                    try:
                        win32process.AttachThreadInput(first, second, False)
                    except Exception:
                        pass
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if int(win32gui.GetForegroundWindow() or 0) == int(hwnd):
                return
            time.sleep(0.02)
        try:
            # WScript's AppActivate asks the interactive shell to perform the
            # same user-level activation. This is useful when the caller was
            # started by a scheduler/terminal and owns no foreground rights.
            import win32com.client
            import win32process

            process_id = int(win32process.GetWindowThreadProcessId(hwnd)[1])
            win32com.client.Dispatch("WScript.Shell").AppActivate(process_id)
        except Exception:
            pass
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if int(win32gui.GetForegroundWindow() or 0) == int(hwnd):
                return
            time.sleep(0.02)
        try:
            # Windows grants foreground rights while the calling thread is
            # processing a real keyboard transition. Keep this final fallback
            # bounded to an Alt press/release pair and always release the key.
            import win32api

            with _PHYSICAL_INPUT_LOCK:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                try:
                    win32gui.SetForegroundWindow(hwnd)
                finally:
                    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if int(win32gui.GetForegroundWindow() or 0) == int(hwnd):
                return
            time.sleep(0.02)
        if int(win32gui.GetForegroundWindow() or 0) != int(hwnd):
            raise RuntimeError("系统拒绝将目标窗口切换到前台")

    def _find_control(self, selector: Any, timeout_ms: int) -> dict[str, Any] | None:
        if not isinstance(selector, dict):
            raise RuntimeFailure('需要强类型控件选择器', error_id='control.selector_invalid')
        provider = str(selector.get('control_selector.field.provider') or '')
        if provider and provider != 'windows_uia':
            raise RuntimeFailure('控件选择器不属于 Windows UIA 适配器', error_id='control.selector_provider_mismatch')
        source_target = str(selector.get('control_selector.field.target_id') or '')
        if source_target and source_target != str(self.target.get('target_id') or ''):
            raise RuntimeFailure('控件选择器不属于当前目标', error_id='control.reference_invalid')
        from core.services.uia_service import find_control, find_control_by_path, find_control_by_rect

        # “立即查找”表示不进行业务层轮询，并不意味着给 UIA 一个 0ms
        # deadline。原生 UIA 仍需要一个很小且有界的调用预算，0ms 会让
        # find_control 在执行第一次查询前直接返回空结果。
        query_budget_ms = max(100, int(timeout_ms or 0))
        if int(selector.get('control_selector.field.schema_version') or 0) == 2:
            from core.vnext.control_selector_v2 import (
                ControlSelectorV2Error,
                record_matches_strategy,
                resolve_ordered,
            )

            title = self._actual_window_title()

            def as_record(info: dict[str, Any]) -> dict[str, Any]:
                raw_rect = info.get('rect') or [0, 0, 0, 0]
                return {
                    'automation_id': str(info.get('automation_id') or ''),
                    'name': str(info.get('name') or ''),
                    'text': str(info.get('name') or ''),
                    'class_name': str(info.get('class_name') or ''),
                    'control_type': str(info.get('control_type') or ''),
                    'ancestor_path': info.get('ancestor_path') or [],
                    'rect': {
                        'kind': 'rect', 'x': int(raw_rect[0]), 'y': int(raw_rect[1]),
                        'width': max(0, int(raw_rect[2]) - int(raw_rect[0])),
                        'height': max(0, int(raw_rect[3]) - int(raw_rect[1])),
                    },
                }

            def matches(strategy: dict[str, Any]) -> list[dict[str, Any]]:
                kind = str(strategy.get('kind') or '')
                relation = strategy.get('relation_path')
                found: dict[str, Any] | None = None
                if kind == 'relation_path' and isinstance(relation, list) and relation:
                    found = find_control_by_path(title, relation, timeout_ms=query_budget_ms)
                elif kind == 'captured_rect' and isinstance(relation, dict):
                    left, top = int(relation.get('x') or 0), int(relation.get('y') or 0)
                    found = find_control_by_rect(
                        [left, top, left + int(relation.get('width') or 0), top + int(relation.get('height') or 0)],
                        expect_name=str(selector.get('control_selector.field.name') or ''),
                        expect_aid=str(selector.get('control_selector.field.automation_id') or ''),
                        expect_type=str(selector.get('control_selector.field.control_type') or ''),
                    )
                if found is not None:
                    return [found] if record_matches_strategy(as_record(found), strategy) else []
                if kind != 'attributes':
                    return []
                lookup = {
                    'automation_id': 'uia_id', 'name': 'uia_name', 'text': 'uia_name',
                    'class_name': 'uia_class', 'control_type': 'uia_type',
                }
                predicate = next(
                    (item for item in strategy.get('predicates') or [] if lookup.get(str(item.get('field') or '')) and str(item.get('value') or '').strip()),
                    None,
                )
                if predicate is None:
                    return []
                accepted: list[dict[str, Any]] = []
                for index in range(8):
                    candidate = find_control(
                        window_title=title,
                        by=lookup[str(predicate['field'])],
                        target=str(predicate['value']),
                        index=index,
                        timeout_ms=query_budget_ms,
                    )
                    if candidate is None:
                        break
                    if record_matches_strategy(as_record(candidate), strategy):
                        accepted.append(candidate)
                        if len(accepted) > 1:
                            break
                return accepted

            try:
                found, strategy_id = resolve_ordered(selector, matches)
            except ControlSelectorV2Error as exc:
                raise RuntimeFailure(str(exc), error_id=exc.error_id) from exc
            if found is not None:
                found = dict(found)
                found['_selector_strategy_id'] = strategy_id
            return found
        path = selector.get('control_selector.field.ancestor_path')
        if isinstance(path, list) and path:
            found = find_control_by_path(
                self._actual_window_title(), path, timeout_ms=query_budget_ms,
            )
            if found is not None:
                return found
        rect = selector.get('control_selector.field.rect')
        if isinstance(rect, dict) and rect.get('kind') == 'rect':
            left, top = int(rect.get('x', 0)), int(rect.get('y', 0))
            rect = [
                left, top,
                left + int(rect.get('width', 0)),
                top + int(rect.get('height', 0)),
            ]
        if isinstance(rect, (list, tuple)) and len(rect) == 4:
            found = find_control_by_rect(
                rect,
                expect_name=str(selector.get('control_selector.field.name') or ''),
                expect_aid=str(selector.get('control_selector.field.automation_id') or ''),
                expect_type=str(selector.get('control_selector.field.control_type') or ''),
            )
            if found is not None:
                return found
        candidates = (
            ('uia_id', selector.get('control_selector.field.automation_id')),
            ('uia_name', selector.get('control_selector.field.name')),
            ('uia_class', selector.get('control_selector.field.class_name')),
            ('uia_type', selector.get('control_selector.field.control_type')),
        )
        by, target = next(
            ((kind, str(value).strip()) for kind, value in candidates if str(value or '').strip()),
            ('', ''),
        )
        if not by or not target:
            raise RuntimeFailure('控件选择器缺少可用的稳定字段', error_id='control.selector_invalid')
        return find_control(
            window_title=self._actual_window_title(), by=by, target=target,
            index=max(0, int(selector.get('control_selector.field.index', 0) or 0)),
            timeout_ms=query_budget_ms,
        )

    def _actual_window_title(self) -> str:
        import win32gui
        return str(win32gui.GetWindowText(self.hwnd) or self.target.get('window_title') or '')

    def _control_reference(self, selector: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
        token = f'control_ref.{uuid.uuid4().hex}'
        self._control_references[token] = {'selector': dict(selector), 'info': dict(info)}
        rect = info.get('rect') or [0, 0, 0, 0]
        return {
            'control_ref.field.token': token,
            'control_ref.field.target_id': str(self.target.get('target_id') or ''),
            'control_ref.field.name': str(info.get('name') or ''),
            'control_ref.field.automation_id': str(info.get('automation_id') or ''),
            'control_ref.field.control_type': str(info.get('control_type') or ''),
            'control_ref.field.rect': {
                'kind': 'rect', 'x': int(rect[0]), 'y': int(rect[1]),
                'width': max(0, int(rect[2]) - int(rect[0])),
                'height': max(0, int(rect[3]) - int(rect[1])),
            },
        }

    def _resolve_control_reference(self, reference: Any) -> dict[str, Any]:
        if not isinstance(reference, dict):
            raise RuntimeFailure('需要强类型控件引用', error_id='control.reference_invalid')
        if str(reference.get('control_ref.field.target_id') or '') != str(self.target.get('target_id') or ''):
            raise RuntimeFailure('控件引用不属于当前目标', error_id='control.reference_invalid')
        token = str(reference.get('control_ref.field.token') or '')
        entry = self._control_references.get(token)
        if entry is None:
            raise RuntimeFailure('控件引用已失效', error_id='control.reference_invalid')
        info = self._find_control(entry['selector'], 0)
        if info is None:
            raise RuntimeFailure('控件已变化，无法按原选择器重新定位', error_id='control.reference_stale', transient=True)
        entry['info'] = dict(info)
        return info

    @staticmethod
    def _control_center(info: dict[str, Any]) -> tuple[int, int]:
        rect = info.get('rect') or [0, 0, 0, 0]
        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
            raise RuntimeFailure('控件引用缺少屏幕区域', error_id='control.reference_stale', transient=True)
        return (int(rect[0]) + int(rect[2])) // 2, (int(rect[1]) + int(rect[3])) // 2

    def _execute_control(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> Any:
        if cancelled():
            raise RuntimeFailure('控件操作已取消', error_id='runtime.cancelled')
        if opcode == 'control.find':
            selector = arguments.get('official.control.find.parameter.selector')
            info = self._find_control(selector, 0)
            if info is None:
                self._set_message('控件查找：未找到')
                return None
            strategy_id = str(info.get('_selector_strategy_id') or 'legacy')
            self._set_message(f'控件查找：已找到（{strategy_id}）')
            return self._control_reference(selector, info)
        if opcode == 'control.click_selector':
            selector = arguments.get('official.control.click_selector.parameter.selector')
            info = self._find_control(selector, 0)
            if info is None:
                raise RuntimeFailure('控件未找到，未执行点击', error_id='control.not_found', transient=True)
            return self._execute_control('control.click', {
                'official.control.click.parameter.control': self._control_reference(selector, info),
                'official.control.click.parameter.mode': arguments.get('official.control.click_selector.parameter.mode', 'auto'),
            }, cancelled)
        function_id = {
            'control.click': 'official.control.click',
            'control.read_text': 'official.control.read_text',
            'control.input_text': 'official.control.type_text',
            'control.read_status': 'official.control.read_status',
            'control.focus': 'official.control.focus',
            'control.set_value': 'official.control.set_value',
            'control.select': 'official.control.select',
            'control.toggle': 'official.control.toggle',
            'control.scroll_into_view': 'official.control.scroll_into_view',
        }[opcode]
        info = self._resolve_control_reference(
            arguments.get(f'{function_id}.parameter.control'),
        )
        from core.services.uia_service import perform_uia_action

        action = {
            'control.click': 'click',
            'control.read_text': 'get_text',
            'control.input_text': 'input_text',
            'control.read_status': 'get_status',
            'control.focus': 'focus',
            'control.set_value': 'set_value',
            'control.select': 'select',
            'control.toggle': 'toggle',
            'control.scroll_into_view': 'scroll_into_view',
        }[opcode]
        mode = str(arguments.get(f'{function_id}.parameter.mode') or 'auto')
        if opcode in {'control.read_text', 'control.read_status'}:
            mode = 'background'
        if mode not in {'auto', 'background', 'physical'}:
            raise RuntimeFailure('控件操作模式无效', error_id='control.operation_failed')
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        physical_allowed = desktop or bool(self.target.get('allow_physical_fallback', False))

        def physical_operation(pyautogui: Any) -> str:
            if cancelled():
                raise RuntimeFailure('控件操作已取消', error_id='runtime.cancelled')
            x, y = self._control_center(info)
            pyautogui.click(x, y)
            if opcode == 'control.input_text':
                self._send_unicode_text(str(arguments.get(f'{function_id}.parameter.content') or ''))
                return f'点击控件并输入文本，长度={len(str(arguments.get(f"{function_id}.parameter.content") or ""))}'
            return f'点击控件 ({x}, {y})'

        if mode == 'physical':
            if not physical_allowed:
                raise RuntimeFailure(
                    '当前目标已关闭物理输入',
                    error_id='control.physical_input_disabled',
                )
            result = self._run_physical(
                '已明确选择物理控件操作', physical_operation,
                error_id='control.operation_failed',
            )
        else:
            result = perform_uia_action(
                info, action,
                text=str(arguments.get(f'{function_id}.parameter.content') or arguments.get(f'{function_id}.parameter.value') or ''),
                allow_physical_fallback=False,
            )
            if not result.get('ok') and mode == 'auto' and physical_allowed and opcode in {'control.click', 'control.input_text'}:
                reason = f'后台控件操作失败（{result.get("message") or "未知原因"}）'
                result = self._run_physical(
                    reason, physical_operation, error_id='control.operation_failed',
                )
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or '控件操作失败'), error_id='control.operation_failed')
        message = str(result.get('message') or '控件操作完成')
        self._set_message(message)
        if opcode == 'control.read_text':
            return str(result.get('value') or '')
        if opcode == 'control.read_status':
            return result.get('value')
        return True

    @staticmethod
    def _window_selector_matches(selector: Any) -> tuple[str, str, str, int, int]:
        if not isinstance(selector, dict):
            raise RuntimeFailure('需要强类型窗口选择器', error_id='window.selector_invalid')
        title = str(selector.get('window_selector.field.title') or '')
        match_mode = str(selector.get('window_selector.field.match_mode') or 'contains')
        class_name = str(selector.get('window_selector.field.class_name') or '')
        process_id = selector.get('window_selector.field.process_id', 0)
        index = selector.get('window_selector.field.index', 0)
        if not title and not class_name and not process_id:
            raise RuntimeFailure('窗口选择器至少需要标题、类名或进程 ID', error_id='window.selector_invalid')
        if match_mode not in {'contains', 'exact', 'regex'}:
            raise RuntimeFailure('窗口标题匹配模式无效', error_id='window.selector_invalid')
        try:
            process_id = int(process_id or 0)
            index = int(index or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeFailure('窗口选择器序号或进程 ID 无效', error_id='window.selector_invalid') from exc
        if process_id < 0 or index < 0:
            raise RuntimeFailure('窗口选择器序号或进程 ID 不能为负数', error_id='window.selector_invalid')
        return title, match_mode, class_name, process_id, index

    def _find_window_by_selector(self, selector: Any) -> int | None:
        import win32gui
        import win32process

        title_query, mode, class_query, process_id, index = self._window_selector_matches(selector)
        try:
            pattern = re.compile(title_query, re.IGNORECASE) if title_query and mode == 'regex' else None
        except re.error as exc:
            raise RuntimeFailure(f'窗口标题正则无效：{exc}', error_id='window.selector_invalid') from exc
        matches: list[int] = []

        def visit(hwnd: int, _extra: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = str(win32gui.GetWindowText(hwnd) or '')
            class_name = str(win32gui.GetClassName(hwnd) or '')
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not title_query:
                title_matches = True
            elif mode == 'exact':
                title_matches = title == title_query
            elif pattern is not None:
                title_matches = bool(pattern.search(title))
            else:
                title_matches = title_query.casefold() in title.casefold()
            if title_matches and (not class_query or class_name == class_query) and (not process_id or int(pid) == process_id):
                matches.append(int(hwnd))

        win32gui.EnumWindows(visit, None)
        return matches[index] if index < len(matches) else None

    def _window_reference(self, hwnd: int) -> dict[str, Any]:
        import win32gui
        import win32process

        thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
        token = f'window_ref.{uuid.uuid4().hex}'
        identity = {
            'hwnd': int(hwnd), 'process_id': int(process_id), 'thread_id': int(thread_id),
            'class_name': str(win32gui.GetClassName(hwnd) or ''),
        }
        self._window_references[token] = identity
        return {
            'window_ref.field.token': token,
            'window_ref.field.handle': int(hwnd),
            'window_ref.field.process_id': int(process_id),
            'window_ref.field.title': str(win32gui.GetWindowText(hwnd) or ''),
            'window_ref.field.class_name': identity['class_name'],
        }

    def _resolve_window_reference(self, reference: Any) -> int:
        import win32gui
        import win32process

        if not isinstance(reference, dict):
            raise RuntimeFailure('需要强类型窗口引用', error_id='window.reference_invalid')
        token = str(reference.get('window_ref.field.token') or '')
        identity = self._window_references.get(token)
        if identity is None:
            raise RuntimeFailure('窗口引用不属于当前运行会话', error_id='window.reference_invalid')
        hwnd = int(identity['hwnd'])
        if not win32gui.IsWindow(hwnd):
            raise RuntimeFailure('窗口引用已失效', error_id='window.reference_invalid')
        thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
        if (
            int(process_id) != identity['process_id']
            or int(thread_id) != identity['thread_id']
            or str(win32gui.GetClassName(hwnd) or '') != identity['class_name']
        ):
            raise RuntimeFailure('窗口句柄已被其他窗口复用', error_id='window.reference_invalid')
        return hwnd

    def _execute_window(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> Any:
        if cancelled():
            raise RuntimeFailure('窗口操作已取消', error_id='runtime.cancelled')
        import win32con
        import win32gui
        if opcode == 'window.current':
            if not self.hwnd or not win32gui.IsWindow(self.hwnd):
                raise RuntimeFailure('当前目标没有可用的 Windows 窗口', error_id='window.reference_invalid')
            self._set_message('已取得当前目标窗口')
            return self._window_reference(self.hwnd)
        if opcode == 'window.find':
            hwnd = self._find_window_by_selector(arguments.get('official.window.find.parameter.selector'))
            if hwnd is None:
                self._set_message('窗口查找：未找到')
                return None
            self._set_message('窗口查找：已找到')
            return self._window_reference(hwnd)
        function_id = {
            'window.activate': 'official.window.activate',
            'window.close': 'official.window.close',
            'window.status': 'official.window.read_status',
            'window.move': 'official.window.move',
            'window.resize': 'official.window.resize',
            'window.ensure_visible': 'official.window.ensure_visible',
            'window.set_display_state': 'official.window.set_display_state',
        }[opcode]
        window_reference = arguments.get(f'{function_id}.parameter.window')
        hwnd = self._resolve_window_reference(window_reference)
        if opcode == 'window.activate':
            try:
                self._activate_window(hwnd)
            except Exception as exc:
                raise RuntimeFailure(f'窗口激活失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message('已激活窗口')
            return True
        if opcode == 'window.close':
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception as exc:
                raise RuntimeFailure(f'窗口关闭请求失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message('已向窗口发送关闭请求')
            return True
        if opcode == 'window.move':
            position = self._v6_point(arguments.get(f'{function_id}.parameter.position'))
            if position is None:
                raise RuntimeFailure('窗口位置无效', error_id='window.position_invalid')
            try:
                win32gui.SetWindowPos(
                    hwnd, 0, position[0], position[1], 0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
                )
            except Exception as exc:
                raise RuntimeFailure(f'窗口移动失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message(f'已移动窗口到 ({position[0]}, {position[1]})')
            return True
        if opcode == 'window.resize':
            raw = arguments.get(f'{function_id}.parameter.size')
            if not isinstance(raw, dict):
                raise RuntimeFailure('窗口尺寸无效', error_id='window.size_invalid')
            width, height = raw.get('width'), raw.get('height')
            if any(isinstance(item, bool) or not isinstance(item, int) for item in (width, height)) or not (1 <= width <= 32767 and 1 <= height <= 32767):
                raise RuntimeFailure('窗口宽高必须为 1 至 32767 的整数', error_id='window.size_invalid')
            try:
                actual_width = actual_height = 0
                for _attempt in range(3):
                    outer_left, outer_top, outer_right, outer_bottom = (
                        int(item) for item in win32gui.GetWindowRect(hwnd)
                    )
                    client_left, client_top, client_right, client_bottom = (
                        int(item) for item in win32gui.GetClientRect(hwnd)
                    )
                    client_width = max(0, client_right - client_left)
                    client_height = max(0, client_bottom - client_top)
                    outer_width = max(0, outer_right - outer_left)
                    outer_height = max(0, outer_bottom - outer_top)
                    requested_outer_width = width + max(0, outer_width - client_width)
                    requested_outer_height = height + max(0, outer_height - client_height)
                    win32gui.SetWindowPos(
                        hwnd, 0, 0, 0, requested_outer_width, requested_outer_height,
                        win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
                    )
                    verify_left, verify_top, verify_right, verify_bottom = (
                        int(item) for item in win32gui.GetClientRect(hwnd)
                    )
                    actual_width = max(0, verify_right - verify_left)
                    actual_height = max(0, verify_bottom - verify_top)
                    if (actual_width, actual_height) == (width, height):
                        break
                else:
                    raise RuntimeFailure(
                        f'窗口客户区无法调整为 {width}×{height}，实际为 {actual_width}×{actual_height}',
                        error_id='window.operation_failed',
                    )
            except Exception as exc:
                if isinstance(exc, RuntimeFailure):
                    raise
                if getattr(exc, 'winerror', None) == 5 or (getattr(exc, 'args', ()) or (None,))[0] == 5:
                    raise RuntimeFailure(
                        'Windows 拒绝调整窗口；请让 EasyCode/Player 与目标应用使用相同权限级别',
                        error_id='window.permission_denied',
                    ) from exc
                raise RuntimeFailure(f'窗口调整大小失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message(f'已调整窗口客户区为 {width}×{height}')
            return True
        if opcode == 'window.ensure_visible':
            try:
                import win32api

                left, top, right, bottom = (int(item) for item in win32gui.GetWindowRect(hwnd))
                width, height = max(0, right - left), max(0, bottom - top)
                monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
                work_left, work_top, work_right, work_bottom = (
                    int(item) for item in win32api.GetMonitorInfo(monitor)['Work']
                )
                if width > work_right - work_left or height > work_bottom - work_top:
                    raise RuntimeFailure(
                        '当前屏幕工作区无法完整容纳初始化后的窗口',
                        error_id='window.work_area_too_small',
                    )
                safe_left = min(max(left, work_left), work_right - width)
                safe_top = min(max(top, work_top), work_bottom - height)
                if (safe_left, safe_top) != (left, top):
                    win32gui.SetWindowPos(
                        hwnd, 0, safe_left, safe_top, 0, 0,
                        win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
                    )
            except Exception as exc:
                if isinstance(exc, RuntimeFailure):
                    raise
                raise RuntimeFailure(f'窗口完整可见调整失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message('窗口已完整位于屏幕工作区')
            return True
        if opcode == 'window.set_display_state':
            state = str(arguments.get(f'{function_id}.parameter.state') or '')
            command = {
                'restored': win32con.SW_RESTORE,
                'minimized': win32con.SW_MINIMIZE,
                'maximized': win32con.SW_MAXIMIZE,
            }.get(state)
            if command is None:
                raise RuntimeFailure('窗口显示状态无效', error_id='window.display_state_invalid')
            try:
                win32gui.ShowWindow(hwnd, command)
            except Exception as exc:
                raise RuntimeFailure(f'窗口显示状态调整失败：{exc}', error_id='window.operation_failed', transient=True) from exc
            self._set_message({'restored': '已还原窗口', 'minimized': '已最小化窗口', 'maximized': '已最大化窗口'}[state])
            return True
        left, top, right, bottom = (int(item) for item in win32gui.GetWindowRect(hwnd))
        return {
            'window_status.field.title': str(win32gui.GetWindowText(hwnd) or ''),
            'window_status.field.position': {'kind': 'point', 'x': left, 'y': top},
            'window_status.field.size': {'width': max(0, right - left), 'height': max(0, bottom - top)},
            'window_status.field.visible': bool(win32gui.IsWindowVisible(hwnd)),
            'window_status.field.minimized': bool(win32gui.IsIconic(hwnd)),
            'window_status.field.maximized': int(win32gui.GetWindowPlacement(hwnd)[1]) == win32con.SW_SHOWMAXIMIZED,
            'window_status.field.foreground': int(win32gui.GetForegroundWindow() or 0) == hwnd,
            'window_status.field.process_id': int(window_reference.get('window_ref.field.process_id') or 0),
        }

    def _find_window(self) -> int:
        if (self.target.get('work_area') or {}).get('mode') == 'desktop':
            return 0
        try:
            from .window_binding_v2 import WindowBindingResolutionError, resolve_target_window

            # A target scope must be constructible while its window is
            # minimized so the first project statements can restore it. Frame
            # capture/input still perform their own readiness checks after the
            # workflow has had that opportunity.
            candidate, _method = resolve_target_window(self.target, require_ready=False)
            return int(candidate['hwnd'])
        except WindowBindingResolutionError as exc:
            raise RuntimeFailure(
                str(exc), error_id=exc.error_id, transient=exc.transient,
            ) from exc

    def _workspace_box(self) -> tuple[int, int, int, int]:
        import win32gui
        mode = (self.target.get('work_area') or {}).get('mode', 'client')
        if mode == 'desktop':
            import win32api
            return (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
        if mode == 'window':
            return tuple(int(item) for item in win32gui.GetWindowRect(self.hwnd))
        client = win32gui.GetClientRect(self.hwnd)
        left, top = win32gui.ClientToScreen(self.hwnd, (client[0], client[1]))
        right, bottom = win32gui.ClientToScreen(self.hwnd, (client[2], client[3]))
        if mode == 'region':
            region = (self.target.get('work_area') or {}).get('region')
            if not isinstance(region, (list, tuple)) or len(region) != 4:
                raise RuntimeFailure('自定义工作区域必须是 [x, y, 宽, 高]')
            x, y, width, height = (int(value) for value in region)
            if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > right - left or y + height > bottom - top:
                raise RuntimeFailure('自定义工作区域超出窗口客户区')
            return left + x, top + y, left + x + width, top + y + height
        return int(left), int(top), int(right), int(bottom)

    def _run_physical(
        self,
        reason: str,
        operation: Callable[[Any], str],
        *,
        error_id: str = 'target.driver_failed',
    ) -> dict[str, Any]:
        if not _PHYSICAL_INPUT_LOCK.acquire(timeout=0.5):
            raise RuntimeFailure(
                '物理输入通道正被其他任务占用',
                error_id=error_id,
                transient=True,
            )
        try:
            import pyautogui
            import win32con
            import win32gui

            original = pyautogui.position()
            if self.hwnd:
                root = int(win32gui.GetAncestor(self.hwnd, getattr(win32con, 'GA_ROOT', 2)) or self.hwnd)
                if not win32gui.IsWindowVisible(root) or win32gui.IsIconic(root):
                    win32gui.ShowWindow(root, win32con.SW_RESTORE)
                if win32gui.GetForegroundWindow() != root:
                    win32gui.BringWindowToTop(root)
                    win32gui.SetForegroundWindow(root)
            try:
                detail = operation(pyautogui)
            finally:
                pyautogui.moveTo(int(original[0]), int(original[1]))
            return {
                'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified',
                'message': f'{reason}，已使用物理输入并恢复鼠标位置；{detail}',
            }
        except RuntimeFailure as exc:
            if exc.error_id == 'runtime.cancelled':
                raise
            raise RuntimeFailure(
                str(exc), error_id=error_id, transient=True,
            ) from exc
        except Exception as exc:
            raise RuntimeFailure(
                f'物理输入失败：{exc}', error_id=error_id, transient=True,
            ) from exc
        finally:
            _PHYSICAL_INPUT_LOCK.release()

    @staticmethod
    def _send_unicode_text(text: str) -> None:
        """Type UTF-16 code units with SendInput; unlike pyautogui.write this supports Chinese."""

        import ctypes
        from ctypes import wintypes

        class KeyInput(ctypes.Structure):
            _fields_ = [
                ('virtual_key', wintypes.WORD), ('scan_code', wintypes.WORD),
                ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('extra_info', ctypes.c_size_t),
            ]

        class InputUnion(ctypes.Union):
            _fields_ = [('keyboard', KeyInput)]

        class Input(ctypes.Structure):
            _anonymous_ = ('value',)
            _fields_ = [('type', wintypes.DWORD), ('value', InputUnion)]

        events: list[Input] = []
        encoded = str(text or '').encode('utf-16-le')
        for index in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[index:index + 2], 'little')
            events.append(Input(type=1, keyboard=KeyInput(0, unit, 0x0004, 0, 0)))
            events.append(Input(type=1, keyboard=KeyInput(0, unit, 0x0004 | 0x0002, 0, 0)))
        if not events:
            return
        array = (Input * len(events))(*events)
        sent = ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(Input))
        if sent != len(events):
            raise RuntimeFailure(f'Unicode 物理键盘仅投递 {sent}/{len(events)} 个事件')

    def capture_frame(self):
        from core.services.screenshot_service import capture, capture_window_with_info, crop_window_image
        box = self._workspace_box()
        self._box = box
        mode = (self.target.get('work_area') or {}).get('mode', 'client')
        if mode == 'desktop':
            return capture(box)
        image, info = capture_window_with_info(self.hwnd)
        if image is None:
            raise RuntimeFailure(str(info.get('message') or '窗口截图失败'))
        try:
            return crop_window_image(self.hwnd, image, box)
        except Exception as exc:
            raise RuntimeFailure(f'窗口截图区域换算失败：{exc}') from exc

    def capture_overlay_region(self) -> list[int] | None:
        self._box = self._workspace_box()
        return [int(value) for value in self._box]

    def tap_point(self, x: int, y: int, button: str) -> dict[str, Any]:
        from core.services.background_input import background_click
        button_name = {'左键': 'left', '右键': 'right', '中键': 'middle'}.get(button, button)
        self._box = self._workspace_box()
        left, top, right, bottom = self._box
        if not (0 <= x < right - left and 0 <= y < bottom - top):
            raise RuntimeFailure(f'点击坐标超出工作区域：({x}, {y})')
        screen_x, screen_y = left + x, top + y
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        result = {'ok': False, 'message': '全屏幕模式无定向后台窗口'} if desktop else background_click(
            self.hwnd, screen_x, screen_y, button=button_name,
        )
        if not result.get('ok') and (desktop or bool(self.target.get('allow_physical_fallback', False))):
            reason = '全屏幕模式固定使用物理输入' if desktop else f'后台点击失败（{result.get("message") or "未知原因"}）'
            result = self._run_physical(
                reason,
                lambda pyautogui: (
                    pyautogui.click(screen_x, screen_y, button=button_name) or f'点击 ({screen_x}, {screen_y})'
                ),
            )
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or '点击失败'))
        return {**result, 'message': str(result.get('message') or f'点击 ({x}, {y})')}

    def input_text(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        from core.services.background_input import background_text
        self._box = self._workspace_box()
        position = arguments.get('位置')
        screen_point = None
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            screen_point = (self._box[0] + int(position[0]), self._box[1] + int(position[1]))
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        mode = str(arguments.get('模式') or 'auto')
        if mode not in {'auto', 'background', 'physical'}:
            raise RuntimeFailure(
                f'Windows 目标不支持文本输入模式：{mode}',
                error_id='target.input_mode_unsupported',
            )

        def type_text(pyautogui):
            if cancelled():
                raise RuntimeFailure('文本输入已取消')
            if screen_point:
                pyautogui.click(int(screen_point[0]), int(screen_point[1]))
            if bool(arguments.get('输入前清空')):
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
            self._send_unicode_text(str(arguments.get('内容') or ''))
            return f'输入长度={len(str(arguments.get("内容") or ""))}'

        if mode == 'physical':
            if not desktop and not bool(self.target.get('allow_physical_fallback', False)):
                raise RuntimeFailure(
                    '当前目标已关闭物理输入，请在目标设置中允许后再使用',
                    error_id='target.physical_input_disabled',
                )
            return self._run_physical('已明确选择物理键盘输入', type_text)

        result = {'ok': False, 'message': '全屏幕模式无定向后台窗口'} if desktop else background_text(
            self.hwnd, str(arguments.get('内容') or ''), screen_point=screen_point,
            clear_before=bool(arguments.get('输入前清空')), stop_check=cancelled,
        )
        may_fallback = mode == 'auto' and (
            desktop or bool(self.target.get('allow_physical_fallback', False))
        )
        if not result.get('ok') and may_fallback:
            reason = '全屏幕模式固定使用物理输入' if desktop else f'后台文本输入失败（{result.get("message") or "未知原因"}）'
            result = self._run_physical(reason, type_text)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or '后台文本输入失败'))
        return result

    @staticmethod
    def _windows_virtual_key(name: str) -> int:
        import win32con

        if len(name) == 1 and ('a' <= name <= 'z' or '0' <= name <= '9'):
            return ord(name.upper())
        if re.fullmatch(r'f(?:[1-9]|1[0-9]|2[0-4])', name):
            return int(getattr(win32con, f'VK_F{int(name[1:])}'))
        mapping = {
            'alt': win32con.VK_MENU, 'backspace': win32con.VK_BACK,
            'ctrl': win32con.VK_CONTROL, 'delete': win32con.VK_DELETE,
            'down': win32con.VK_DOWN, 'end': win32con.VK_END,
            'enter': win32con.VK_RETURN, 'escape': win32con.VK_ESCAPE,
            'home': win32con.VK_HOME, 'insert': win32con.VK_INSERT,
            'left': win32con.VK_LEFT, 'page_down': win32con.VK_NEXT,
            'page_up': win32con.VK_PRIOR, 'right': win32con.VK_RIGHT,
            'shift': win32con.VK_SHIFT, 'space': win32con.VK_SPACE,
            'tab': win32con.VK_TAB, 'up': win32con.VK_UP,
            'win': getattr(win32con, 'VK_LWIN', 0x5B),
        }
        if name not in mapping:
            raise RuntimeFailure(f'Windows 不支持按键：{name}', error_id='target.invalid_key')
        return int(mapping[name])

    @staticmethod
    def _wait_key_hold(hold_ms: int, cancelled: Callable[[], bool]) -> None:
        deadline = time.monotonic() + max(0, hold_ms) / 1000.0
        while time.monotonic() < deadline:
            if cancelled():
                raise RuntimeFailure('按键操作已取消', error_id='runtime.cancelled')
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))

    def press_key(
        self,
        keys: list[str],
        action: str,
        hold_ms: int,
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        if cancelled():
            raise RuntimeFailure('按键操作已取消', error_id='runtime.cancelled')
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'

        def physical(pyautogui: Any) -> str:
            pressed: list[str] = []
            try:
                if action in {'press', 'down'}:
                    for key in keys:
                        pyautogui.keyDown(key)
                        pressed.append(key)
                if action == 'press':
                    self._wait_key_hold(hold_ms, cancelled)
                    for key in reversed(pressed):
                        pyautogui.keyUp(key)
                    pressed.clear()
                elif action == 'up':
                    for key in reversed(keys):
                        pyautogui.keyUp(key)
            finally:
                # A cancelled press must not leave modifiers held. Explicit
                # ``down`` remains held until a matching ``up`` by design.
                if action == 'press':
                    for key in reversed(pressed):
                        pyautogui.keyUp(key)
            return f'按键={"+".join(keys)}，动作={action}'

        if desktop:
            return self._run_physical('全屏幕模式固定使用物理键盘', physical)
        virtual_keys = [self._windows_virtual_key(key) for key in keys]
        try:
            import win32con
            import win32gui

            if action in {'press', 'down'}:
                for key in virtual_keys:
                    win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, key, 0)
            if action == 'press':
                try:
                    self._wait_key_hold(hold_ms, cancelled)
                finally:
                    for key in reversed(virtual_keys):
                        win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, key, 0)
            elif action == 'up':
                for key in reversed(virtual_keys):
                    win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, key, 0)
            return {
                'ok': True, 'method': 'window_message',
                'delivery': 'delivered_unverified',
                'message': f'后台按键已投递：{"+".join(keys)}（{action}）',
            }
        except RuntimeFailure:
            raise
        except Exception as exc:
            if bool(self.target.get('allow_physical_fallback', False)):
                return self._run_physical(f'后台按键失败（{exc}）', physical)
            raise RuntimeFailure(f'后台按键失败：{exc}', error_id='target.driver_failed', transient=True) from exc

    def _execute_move_pointer(
        self,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        position = self._v6_point(arguments.get('official.input.move_pointer.parameter.position'))
        if position is None:
            raise RuntimeFailure('移动指针缺少位置', error_id='target.invalid_point')
        duration = arguments.get('official.input.move_pointer.parameter.duration', 0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
            raise RuntimeFailure('移动时长无效', error_id='target.invalid_duration')
        self._box = self._workspace_box()
        left, top, right, bottom = self._box
        if not (0 <= position[0] < right - left and 0 <= position[1] < bottom - top):
            raise RuntimeFailure('移动位置超出工作区域', error_id='target.invalid_point')
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        if not desktop and not bool(self.target.get('allow_physical_fallback', False)):
            raise RuntimeFailure('当前目标已关闭物理输入', error_id='target.physical_input_disabled')
        destination = (left + position[0], top + position[1])

        def move(pyautogui: Any) -> str:
            origin = pyautogui.position()
            steps = max(1, min(240, round(max(16, float(duration)) / 16)))
            delay = float(duration) / 1000.0 / steps if duration else 0.0
            for index in range(1, steps + 1):
                if cancelled():
                    raise RuntimeFailure('移动指针已取消', error_id='runtime.cancelled')
                ratio = index / steps
                x = round(int(origin[0]) + (destination[0] - int(origin[0])) * ratio)
                y = round(int(origin[1]) + (destination[1] - int(origin[1])) * ratio)
                pyautogui.moveTo(x, y)
                if delay:
                    time.sleep(delay)
            return f'移动到 ({destination[0]}, {destination[1]})'

        reason = '全屏幕模式物理移动指针' if desktop else '已明确执行物理指针移动'
        return self._run_physical(reason, move)

    def scroll(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        from core.services.background_input import background_scroll
        direction = str(arguments.get('方向') or '下')
        mode = str(arguments.get('模式') or 'auto')
        amount = max(1, int(arguments.get('数量', 3) or 3))
        position = arguments.get('位置')
        self._box = self._workspace_box()
        left, top, right, bottom = self._box
        x, y = (int(position[0]), int(position[1])) if isinstance(position, (list, tuple)) and len(position) >= 2 else ((right - left) // 2, (bottom - top) // 2)
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        if mode == 'touch':
            width, height = right - left, bottom - top
            ratio = max(0.05, min(0.95, float(arguments.get('距离比例', 0.6) or 0.6)))
            if direction in {'上', 'up'}:
                end_x, end_y = x, min(height - 1, y + max(1, round(height * ratio)))
            elif direction in {'下', 'down'}:
                end_x, end_y = x, max(0, y - max(1, round(height * ratio)))
            elif direction in {'左', 'left'}:
                end_x, end_y = min(width - 1, x + max(1, round(width * ratio))), y
            else:
                end_x, end_y = max(0, x - max(1, round(width * ratio))), y
            return self.drag_path({
                '路径': [
                    {'point': [x, y], 'move_ms': 0, 'hold_ms': 0},
                    {
                        'point': [end_x, end_y],
                        'move_ms': int(arguments.get('移动时长', 350) or 350),
                        'hold_ms': int(arguments.get('终点保持', 80) or 80),
                    },
                ],
                '缓动': '线性',
            }, cancelled)
        horizontal = direction in {'左', '右', 'left', 'right'}
        if horizontal:
            ticks = amount if direction in {'右', 'right'} else -amount
        else:
            ticks = amount if direction in {'上', 'up'} else -amount
        result = {'ok': False, 'message': '全屏幕模式无定向后台窗口'} if desktop else background_scroll(
            self.hwnd, left + x, top + y, ticks, horizontal=horizontal,
        )
        if not result.get('ok') and (desktop or bool(self.target.get('allow_physical_fallback', False))):
            reason = '全屏幕模式固定使用物理输入' if desktop else f'后台滚动失败（{result.get("message") or "未知原因"}）'

            def scroll_physical(pyautogui):
                pyautogui.moveTo(left + x, top + y)
                if horizontal:
                    pyautogui.hscroll(ticks)
                else:
                    pyautogui.scroll(ticks)
                return f'滚动量={ticks}'

            result = self._run_physical(reason, scroll_physical)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or '后台滚动失败'))
        return result

    def drag_path(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        from core.services.background_input import background_drag_path
        self._box = self._workspace_box()
        left, top, _, _ = self._box
        points = self.normalize_path(arguments.get('路径'))
        screen_points = [{**item, 'point': [left + item['point'][0], top + item['point'][1]]} for item in points]
        easing = 'ease_in_out' if str(arguments.get('缓动') or '线性') in {'缓入缓出', 'ease_in_out'} else 'linear'
        desktop = (self.target.get('work_area') or {}).get('mode') == 'desktop'
        button = {'左键': 'left', '右键': 'right', '中键': 'middle'}.get(
            str(arguments.get('按键') or '左键'), str(arguments.get('按键') or 'left')
        )
        result = {'ok': False, 'message': '全屏幕模式无定向后台窗口'} if desktop else background_drag_path(
            self.hwnd, screen_points, button=button, easing=easing, stop_check=cancelled,
        )
        if not result.get('ok') and (desktop or bool(self.target.get('allow_physical_fallback', False))):
            reason = '全屏幕模式固定使用物理输入' if desktop else f'后台拖拽失败（{result.get("message") or "未知原因"}）'

            def drag_physical(pyautogui):
                first = screen_points[0]
                pyautogui.moveTo(*first['point'])
                pyautogui.mouseDown(button=button)
                try:
                    if first['hold_ms']:
                        time.sleep(first['hold_ms'] / 1000)
                    for point in screen_points[1:]:
                        if cancelled():
                            raise RuntimeFailure('拖拽已取消')
                        pyautogui.moveTo(*point['point'], duration=max(0, point['move_ms']) / 1000)
                        if point['hold_ms']:
                            time.sleep(point['hold_ms'] / 1000)
                finally:
                    pyautogui.mouseUp(button=button)
                return f'路径点={len(screen_points)}'

            result = self._run_physical(reason, drag_physical)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or '后台拖拽失败'))
        return result

    def close(self) -> None:
        self._window_references.clear()
        self._control_references.clear()
        super().close()


class AndroidAdbTargetDriver(TargetDriver):
    platform = 'android_adb'
    frame_is_bgr = True

    def __init__(self, project_path: str, target: dict[str, Any]) -> None:
        super().__init__(project_path, target)
        self.device_id = str(target.get('device_serial') or '').strip()
        if not self.device_id:
            raise RuntimeFailure(
                'ADB 目标缺少显式设备序列号，请在目标设置中重新绑定设备',
                error_id='target.adb_rebind_required',
            )
        try:
            from core.services.android_stream import ScrcpyVideoSession
            self.session = ScrcpyVideoSession(self.device_id)
            self.session.start()
        except Exception as exc:
            raise RuntimeFailure(
                f'ADB 设备“{self.device_id}”不可用，请检查连接或重新绑定：{exc}',
                error_id='target.adb_rebind_required',
                transient=True,
            ) from exc
        self._sequence = 0
        self._size = (0, 0)
        from .android_control_v6 import AdbUiAutomatorAdapter
        self._control_adapter = AdbUiAutomatorAdapter(self.device_id)
        self._control_references: dict[str, dict[str, Any]] = {}

    @staticmethod
    def supports(opcode: str) -> bool:
        return TargetDriver.supports(opcode) or opcode in {
            'control.find', 'control.click', 'control.click_selector', 'control.read_text', 'control.input_text',
            'control.read_status', 'control.focus', 'control.set_value', 'control.select',
            'control.toggle', 'control.scroll_into_view',
        }

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> Any:
        if opcode.startswith('control.'):
            return self._execute_control(opcode, arguments, cancelled)
        return super().execute(opcode, arguments, cancelled)

    def _control_failure(self, error: Exception) -> RuntimeFailure:
        from .android_control_v6 import AndroidControlError
        if isinstance(error, AndroidControlError):
            return RuntimeFailure(str(error), error_id=error.error_id, transient=error.transient)
        return RuntimeFailure(str(error) or 'ADB 控件操作失败', error_id='control.operation_failed', transient=True)

    def capture_control_selector(self, point: Any) -> dict[str, Any]:
        clean = self._v6_point(point)
        if clean is None:
            raise RuntimeFailure('控件捕获缺少目标坐标', error_id='control.selector_invalid')
        try:
            if self._size == (0, 0):
                self.capture_frame()
            return self._control_adapter.capture_at(
                clean[0], clean[1], str(self.target.get('target_id') or ''), self._size,
            )
        except Exception as exc:
            raise self._control_failure(exc) from exc

    def _control_reference(self, selector: dict[str, Any], node: Any) -> dict[str, Any]:
        token = f'control_ref.{uuid.uuid4().hex}'
        self._control_references[token] = {'selector': deepcopy(selector)}
        left, top, right, bottom = node.bounds
        return {
            'control_ref.field.token': token,
            'control_ref.field.target_id': str(self.target.get('target_id') or ''),
            'control_ref.field.name': node.display_name,
            'control_ref.field.automation_id': node.resource_id,
            'control_ref.field.control_type': node.class_name.rsplit('.', 1)[-1],
            'control_ref.field.rect': {
                'kind': 'rect', 'x': left, 'y': top,
                'width': max(0, right - left), 'height': max(0, bottom - top),
            },
        }

    def _resolve_control_reference(self, reference: Any) -> Any:
        if not isinstance(reference, dict):
            raise RuntimeFailure('需要强类型控件引用', error_id='control.reference_invalid')
        target_id = str(self.target.get('target_id') or '')
        if str(reference.get('control_ref.field.target_id') or '') != target_id:
            raise RuntimeFailure('控件引用不属于当前目标', error_id='control.reference_invalid')
        entry = self._control_references.get(str(reference.get('control_ref.field.token') or ''))
        if entry is None:
            raise RuntimeFailure('控件引用已失效', error_id='control.reference_invalid')
        try:
            node = self._control_adapter.find(entry['selector'], target_id)
        except Exception as exc:
            raise self._control_failure(exc) from exc
        if node is None:
            raise RuntimeFailure('控件已变化，无法按原选择器重新定位', error_id='control.reference_stale', transient=True)
        return node

    def _execute_control(self, opcode: str, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> Any:
        if cancelled():
            raise RuntimeFailure('控件操作已取消', error_id='runtime.cancelled')
        target_id = str(self.target.get('target_id') or '')
        if opcode == 'control.find':
            selector = arguments.get('official.control.find.parameter.selector')
            try:
                node = self._control_adapter.find(selector, target_id)
            except Exception as exc:
                raise self._control_failure(exc) from exc
            if node is None:
                self._set_message('控件查找：未找到')
                return None
            strategy_id = str(getattr(self._control_adapter, 'last_strategy_id', '') or 'legacy')
            self._set_message(f'控件查找：已找到（{strategy_id}）')
            return self._control_reference(selector, node)
        if opcode == 'control.click_selector':
            selector = arguments.get('official.control.click_selector.parameter.selector')
            try:
                node = self._control_adapter.find(selector, target_id)
            except Exception as exc:
                raise self._control_failure(exc) from exc
            if node is None:
                raise RuntimeFailure('控件未找到，未执行点击', error_id='control.not_found', transient=True)
            return self._execute_control('control.click', {
                'official.control.click.parameter.control': self._control_reference(selector, node),
                'official.control.click.parameter.mode': arguments.get('official.control.click_selector.parameter.mode', 'auto'),
            }, cancelled)
        function_id = {
            'control.click': 'official.control.click',
            'control.read_text': 'official.control.read_text',
            'control.input_text': 'official.control.type_text',
            'control.read_status': 'official.control.read_status',
            'control.focus': 'official.control.focus',
            'control.set_value': 'official.control.set_value',
            'control.select': 'official.control.select',
            'control.toggle': 'official.control.toggle',
            'control.scroll_into_view': 'official.control.scroll_into_view',
        }[opcode]
        node = self._resolve_control_reference(arguments.get(f'{function_id}.parameter.control'))
        if not node.enabled and opcode not in {'control.read_text', 'control.read_status'}:
            raise RuntimeFailure('控件当前不可操作', error_id='control.operation_failed')
        mode = str(arguments.get(f'{function_id}.parameter.mode') or 'auto')
        if mode not in {'auto', 'target'}:
            raise RuntimeFailure('ADB 控件只支持自动或目标原生操作', error_id='control.operation_unsupported')
        if opcode == 'control.read_text':
            value = node.text or node.content_description
            self._set_message('已读取控件文本')
            return value
        if opcode == 'control.read_status':
            left, top, right, bottom = node.bounds
            return {
                'control_status.field.enabled': node.enabled,
                'control_status.field.visible': node.visible,
                'control_status.field.checked': node.checked,
                'control_status.field.selected': node.selected,
                'control_status.field.editable': node.editable,
                'control_status.field.focusable': node.focusable,
                'control_status.field.focused': node.focused,
                'control_status.field.current_value': node.text or node.content_description or None,
                'control_status.field.rect': {
                    'kind': 'rect', 'x': left, 'y': top,
                    'width': max(0, right - left), 'height': max(0, bottom - top),
                },
            }
        if opcode == 'control.scroll_into_view':
            if node.visible is False:
                raise RuntimeFailure(
                    'ADB UIAutomator 不能把当前不可见控件滚动到画面内',
                    error_id='control.operation_unsupported',
                )
            self._set_message('控件已在当前可见控件树中，无需滚动')
            return True
        if opcode == 'control.focus' and node.focusable is not True:
            raise RuntimeFailure('该控件未声明可聚焦', error_id='control.operation_unsupported')
        if opcode == 'control.select' and node.selected is None:
            raise RuntimeFailure('该控件未提供可验证的选中状态', error_id='control.operation_unsupported')
        if opcode == 'control.toggle' and node.checked is None:
            raise RuntimeFailure('该控件未提供可验证的勾选状态', error_id='control.operation_unsupported')
        left, top, right, bottom = node.bounds
        if self._size == (0, 0):
            self.capture_frame()
        try:
            from .android_control_v6 import scale_point
            point = scale_point(
                ((left + right) // 2, (top + bottom) // 2),
                self._control_adapter.display_size,
                self._size,
            )
        except Exception as exc:
            raise self._control_failure(exc) from exc
        self.tap_point(point[0], point[1], 'left')
        if opcode in {'control.input_text', 'control.set_value'}:
            if cancelled():
                raise RuntimeFailure('控件操作已取消', error_id='runtime.cancelled')
            selected = self.session.keyevent(29, metastate=0x1000, action='press')
            if not selected.get('ok'):
                raise RuntimeFailure(
                    str(selected.get('message') or 'ADB 控件无法选中原文本'),
                    error_id='control.operation_failed', transient=True,
                )
            result = self.session.inject_text(str(arguments.get(f'{function_id}.parameter.content') or arguments.get(f'{function_id}.parameter.value') or ''), paste=True)
            if not result.get('ok'):
                raise RuntimeFailure(str(result.get('message') or 'ADB 控件输入失败'), error_id='control.operation_failed', transient=True)
            self._set_message('已向控件输入文本')
            return True
        if opcode in {'control.focus', 'control.select', 'control.toggle'}:
            reference = arguments.get(f'{function_id}.parameter.control') or {}
            entry = self._control_references.get(str(reference.get('control_ref.field.token') or '')) or {}
            selector = entry.get('selector')
            expected = {
                'control.focus': lambda current: current.focused is True,
                'control.select': lambda current: current.selected is True,
                'control.toggle': lambda current: current.checked is not None and current.checked != node.checked,
            }[opcode]
            verified = False
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and not cancelled():
                try:
                    current = self._control_adapter.find(selector, target_id)
                except Exception as exc:
                    raise self._control_failure(exc) from exc
                if current is not None and expected(current):
                    verified = True
                    break
                time.sleep(0.05)
            if not verified:
                raise RuntimeFailure(
                    '目标已收到控件操作，但 UIAutomator 未验证到状态变化',
                    error_id='control.operation_failed', transient=True,
                )
            labels = {'control.focus': '聚焦', 'control.select': '选择', 'control.toggle': '切换'}
            self._set_message(f'已通过目标点击并验证控件{labels[opcode]}结果')
            return True
        self._set_message('已点击控件')
        return True

    def capture_frame(self):
        packet = self.session.next(self._sequence, 2.0)
        self._sequence = packet.sequence
        height, width = packet.image.shape[:2]
        self._size = (int(width), int(height))
        return packet.image

    def wait_next_frame(self) -> None:
        return None

    def tap_point(self, x: int, y: int, button: str) -> dict[str, Any]:
        if button not in {'左键', 'left'}:
            raise RuntimeFailure('Android 点击只支持触控语义')
        if self._size == (0, 0):
            self.capture_frame()
        width, height = self._size
        if not (0 <= x < width and 0 <= y < height):
            raise RuntimeFailure(f'点击坐标超出 Android 画面：({x}, {y}) / {width}x{height}')
        result = self.session.tap(x, y, width, height)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or 'ADB 点击失败'))
        return {**result, 'message': str(result.get('message') or f'Android 点击 ({x}, {y})')}

    def input_text(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        if cancelled():
            raise RuntimeFailure('文本输入已取消')
        result = self.session.inject_text(str(arguments.get('内容') or ''), paste=True)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or 'Android 文本输入失败'))
        return result

    @staticmethod
    def _android_key(name: str) -> tuple[int | None, int]:
        modifier_states = {
            'shift': 0x00000001,
            'alt': 0x00000002,
            'ctrl': 0x00001000,
            'win': 0x00010000,
        }
        if name in modifier_states:
            return None, modifier_states[name]
        if len(name) == 1 and 'a' <= name <= 'z':
            return 29 + ord(name) - ord('a'), 0
        if len(name) == 1 and '0' <= name <= '9':
            return 7 + ord(name) - ord('0'), 0
        mapping = {
            'back': 4, 'home': 3, 'backspace': 67, 'delete': 112,
            'down': 20, 'end': 123, 'enter': 66, 'escape': 111,
            'left': 21, 'page_down': 93, 'page_up': 92, 'right': 22,
            'space': 62, 'tab': 61, 'up': 19, 'volume_down': 25,
            'volume_up': 24, 'power': 26,
        }
        if name not in mapping:
            raise RuntimeFailure(f'Android 不支持按键：{name}', error_id='target.invalid_key')
        return mapping[name], 0

    def press_key(
        self,
        keys: list[str],
        action: str,
        hold_ms: int,
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        metastate = 0
        keycodes: list[int] = []
        for key in keys:
            keycode, modifier = self._android_key(key)
            metastate |= modifier
            if keycode is not None:
                keycodes.append(keycode)
        if len(keycodes) != 1:
            raise RuntimeFailure(
                'Android 按键组合必须包含且只能包含一个非修饰键',
                error_id='target.invalid_key',
            )
        result = self.session.keyevent(
            keycodes[0], metastate=metastate, action=action,
            hold_ms=hold_ms, stop_check=cancelled,
        )
        if result.get('delivery') == 'cancelled':
            raise RuntimeFailure('Android 按键已取消', error_id='runtime.cancelled')
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or 'Android 按键失败'), error_id='target.driver_failed', transient=True)
        return result

    def start_application(
        self,
        package: str,
        activity: str,
        arguments: list[str],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        if cancelled():
            raise RuntimeFailure('应用启动已取消', error_id='runtime.cancelled')
        return self.session.start_activity(package, activity, arguments)

    def application_running(self, package: str) -> bool:
        try:
            return bool(self.session.application_running(package))
        except Exception as exc:
            raise RuntimeFailure(
                f'ADB 应用状态查询失败：{exc}',
                error_id='application.lifecycle_unavailable', transient=True,
            ) from exc

    def stop_application(
        self, package: str, cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        if cancelled():
            raise RuntimeFailure('停止应用已取消', error_id='runtime.cancelled')
        return self.session.stop_application(package)

    def scroll(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        if self._size == (0, 0):
            self.capture_frame()
        width, height = self._size
        direction = str(arguments.get('方向') or '下')
        position = arguments.get('位置')
        x, y = (int(position[0]), int(position[1])) if isinstance(position, (list, tuple)) and len(position) >= 2 else (width // 2, height // 2)
        ratio = max(0.05, min(0.95, float(arguments.get('距离比例', 0.6) or 0.6)))
        if direction in {'左', '右', 'left', 'right'}:
            distance = min(width - 1, max(1, round(width * ratio)))
            end_x = max(0, x - distance) if direction in {'右', 'right'} else min(width - 1, x + distance)
            end_y = y
        else:
            distance = min(height - 1, max(1, round(height * ratio)))
            end_x = x
            end_y = max(0, y - distance) if direction in {'下', 'down'} else min(height - 1, y + distance)
        result = self.session.swipe(
            x, y, end_x, end_y, width, height,
            duration_ms=int(arguments.get('移动时长', 300) or 300),
            hold_after_ms=int(arguments.get('终点保持', 80) or 80), stop_check=cancelled,
        )
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or 'Android 滚动失败'))
        return result

    def drag_path(self, arguments: dict[str, Any], cancelled: Callable[[], bool]) -> dict[str, Any]:
        if self._size == (0, 0):
            self.capture_frame()
        width, height = self._size
        easing = 'ease_in_out' if str(arguments.get('缓动') or '线性') in {'缓入缓出', 'ease_in_out'} else 'linear'
        result = self.session.swipe_path(self.normalize_path(arguments.get('路径')), width, height, easing=easing, stop_check=cancelled)
        if not result.get('ok'):
            raise RuntimeFailure(str(result.get('message') or 'Android 拖拽失败'))
        return result

    def close(self) -> None:
        try:
            self.session.close()
        finally:
            self._control_references.clear()
            super().close()


def create_target_driver(project_path: str, target: dict[str, Any] | None) -> TargetDriver | None:
    if target is None:
        return None
    target_type = target.get('type')
    if target_type == 'windows':
        return WindowsTargetDriver(project_path, target)
    if target_type == 'android_adb':
        return AndroidAdbTargetDriver(project_path, target)
    if target_type == 'android_local':
        raise RuntimeFailure('Android 本机目标只允许编译 APK，不能由 Windows IDE 直接执行')
    raise RuntimeFailure(f'未知目标类型：{target_type}')
