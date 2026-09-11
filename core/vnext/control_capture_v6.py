"""Target-bounded semantic control capture shared by IDE and Player."""

from __future__ import annotations

from typing import Any

from core.vnext.target_runtime import WindowsTargetDriver


class ControlCaptureError(RuntimeError):
    def __init__(self, error_id: str, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = transient


def _windows_candidates(
    project_path: str,
    target: dict[str, Any],
    point: tuple[int, int],
    reference_size: tuple[int, int],
    *,
    capture_region: tuple[int, int, int, int] | list[int] | None = None,
    expected_hwnd: int | None = None,
    exclude_process_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    from core.services.capture_mode import build_control_selector
    from core.services.uia_service import inspect_point_candidates

    frame_width, frame_height = reference_size
    driver = None
    if isinstance(capture_region, (list, tuple)) and len(capture_region) == 4:
        left, top, right, bottom = (int(value) for value in capture_region)
        hwnd = int(expected_hwnd or 0)
    else:
        driver = WindowsTargetDriver(project_path, target)
        left, top, right, bottom = driver._box
        hwnd = int(driver.hwnd)
        if (target.get('work_area') or {}).get('mode') == 'window':
            from core.services.screenshot_service import window_image_screen_box
            left, top, right, bottom = window_image_screen_box(driver.hwnd, reference_size)
    width, height = max(1, right - left), max(1, bottom - top)
    local_x = round(int(point[0]) * width / frame_width)
    local_y = round(int(point[1]) * height / frame_height)
    screen_x, screen_y = left + local_x, top + local_y
    target_hwnd = 0 if (target.get('work_area') or {}).get('mode') == 'desktop' else hwnd
    try:
        raw = inspect_point_candidates(
            screen_x,
            screen_y,
            expected_hwnd=target_hwnd,
            exclude_process_ids=exclude_process_ids,
        )
    finally:
        if driver is not None:
            driver.close()
    result: list[dict[str, Any]] = []
    from core.vnext.control_selector_v2 import build_selector_v2, record_matches_strategy

    test_records = [
        {
            'automation_id': str(item.get('automation_id') or ''),
            'name': str(item.get('name') or ''),
            'text': str(item.get('name') or ''),
            'class_name': str(item.get('class_name') or ''),
            'control_type': str(item.get('control_type') or ''),
            'ancestor_path': item.get('ancestor_path') or [],
            'rect': {
                'kind': 'rect', 'x': int((item.get('rect') or [0, 0, 0, 0])[0]),
                'y': int((item.get('rect') or [0, 0, 0, 0])[1]),
                'width': max(0, int((item.get('rect') or [0, 0, 0, 0])[2]) - int((item.get('rect') or [0, 0, 0, 0])[0])),
                'height': max(0, int((item.get('rect') or [0, 0, 0, 0])[3]) - int((item.get('rect') or [0, 0, 0, 0])[1])),
            },
        }
        for item in raw if isinstance(item, dict) and isinstance(item.get('rect'), (list, tuple)) and len(item.get('rect')) == 4
    ]
    for info in raw:
        rect = info.get('rect') or [0, 0, 0, 0]
        x0 = max(0, int(rect[0]) - left)
        y0 = max(0, int(rect[1]) - top)
        x1 = min(width, int(rect[2]) - left)
        y1 = min(height, int(rect[3]) - top)
        if x1 <= x0 or y1 <= y0:
            continue
        base_selector = build_control_selector(info, str(target.get('target_id') or ''))
        selector = build_selector_v2(
            base_selector,
            captured_space_version=f"{target.get('target_id') or ''}:{frame_width}x{frame_height}",
            test_strategy=lambda strategy: sum(
                record_matches_strategy(record, strategy) for record in test_records
            ),
        )
        result.append({
            'label': str(info.get('name') or info.get('automation_id') or info.get('class_name') or '未命名控件'),
            'role': str(info.get('control_type') or 'control'),
            'frame_rect': [
                round(x0 * frame_width / width),
                round(y0 * frame_height / height),
                max(1, round((x1 - x0) * frame_width / width)),
                max(1, round((y1 - y0) * frame_height / height)),
            ],
            'selector': selector,
        })
    if not result:
        raise ControlCaptureError('control.not_at_point', '当前位置没有可识别控件；请在目标窗口内重新点击')
    return result


def resolve_control_candidates(
    project_path: str,
    target: dict[str, Any],
    point: tuple[int, int],
    reference_size: tuple[int, int],
    *,
    capture_region: tuple[int, int, int, int] | list[int] | None = None,
    expected_hwnd: int | None = None,
    semantic_snapshot: list[Any] | None = None,
    exclude_process_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    if len(point) != 2 or len(reference_size) != 2 or min(reference_size) <= 0:
        raise ControlCaptureError('control.coordinate_space_invalid', '控件捕获坐标空间无效')
    target_type = str(target.get('type') or '')
    if target_type == 'windows':
        return _windows_candidates(
            project_path, target, point, reference_size,
            capture_region=capture_region,
            expected_hwnd=expected_hwnd,
            exclude_process_ids=exclude_process_ids,
        )
    if target_type == 'android_adb':
        from core.vnext.android_control_v6 import (
            AdbUiAutomatorAdapter,
            AndroidControlError,
            control_candidates_at,
        )
        try:
            if semantic_snapshot is not None:
                return control_candidates_at(
                    semantic_snapshot,
                    int(point[0]), int(point[1]),
                    str(target.get('target_id') or ''),
                    'android_uiautomator',
                    source_size=reference_size,
                )
            return AdbUiAutomatorAdapter(str(target.get('device_serial') or '')).capture_candidates_at(
                int(point[0]), int(point[1]), str(target.get('target_id') or ''), reference_size,
            )
        except AndroidControlError as exc:
            raise ControlCaptureError(exc.error_id, str(exc), transient=exc.transient) from exc
    if target_type == 'android_local':
        raise ControlCaptureError('control.native_host_required', 'Android 本机控件请使用 APK Player 的无障碍捕获器')
    raise ControlCaptureError('control.unsupported_target', '当前操作目标不支持控件捕获')


__all__ = ['ControlCaptureError', 'resolve_control_candidates']
