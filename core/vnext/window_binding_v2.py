"""Safe Windows top-level window capture and target resolution.

HWND and PID are process-lifetime hints, never durable identities.  A captured
binding may recover after restart only when its stable title/class/executable
fingerprint identifies exactly one visible top-level window.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Iterable


class WindowBindingResolutionError(RuntimeError):
    def __init__(self, message: str, *, error_id: str, transient: bool = False) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = transient


def _process_identity(process_id: int) -> tuple[str, int]:
    try:
        import psutil

        process = psutil.Process(int(process_id))
        return str(process.name() or ''), max(0, int(process.create_time() * 1000))
    except Exception:
        return '', 0


def enumerate_window_candidates(*, exclude_process_ids: Iterable[int] = ()) -> list[dict[str, Any]]:
    if os.name != 'nt':
        raise WindowBindingResolutionError(
            '窗口捕获只支持 Windows 宿主', error_id='target.platform_unsupported',
        )
    try:
        import win32gui
        import win32process
    except ImportError as exc:
        raise WindowBindingResolutionError(
            'Windows 窗口驱动缺少 pywin32', error_id='target.driver_failed', transient=True,
        ) from exc

    excluded = {int(item) for item in exclude_process_ids if int(item or 0) > 0}
    candidates: list[dict[str, Any]] = []

    def visit(hwnd: int, _extra: Any) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = str(win32gui.GetWindowText(hwnd) or '').strip()
            if not title:
                return
            left, top, right, bottom = (int(value) for value in win32gui.GetWindowRect(hwnd))
            if right <= left or bottom <= top:
                return
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if int(process_id) in excluded:
                return
            executable_name, process_started_at_ms = _process_identity(int(process_id))
            candidates.append({
                'hwnd': int(hwnd),
                'process_id': int(process_id),
                'thread_id': int(thread_id),
                'process_started_at_ms': process_started_at_ms,
                'title': title,
                'class_name': str(win32gui.GetClassName(hwnd) or ''),
                'executable_name': executable_name,
                'rect': [left, top, right, bottom],
                'minimized': bool(win32gui.IsIconic(hwnd)),
            })
        except Exception:
            # A window may disappear while EnumWindows is walking the z-order.
            return

    win32gui.EnumWindows(visit, None)
    return candidates


def _title_matches(title: str, expected: str, mode: str) -> bool:
    if mode == 'exact':
        return title == expected
    if mode == 'regex':
        try:
            return bool(re.search(expected, title, re.IGNORECASE))
        except re.error as exc:
            raise WindowBindingResolutionError(
                f'窗口标题正则表达式无效：{exc}', error_id='target.reference_invalid',
            ) from exc
    return expected.casefold() in title.casefold()


def _stable_binding_matches(candidate: dict[str, Any], binding: dict[str, Any]) -> bool:
    expected_class = str(binding.get('class_name') or '')
    expected_executable = str(binding.get('executable_name') or '')
    return (
        (not expected_class or str(candidate.get('class_name') or '') == expected_class)
        and (
            not expected_executable
            or str(candidate.get('executable_name') or '').casefold() == expected_executable.casefold()
        )
    )


def _captured_instance_matches(candidate: dict[str, Any], binding: dict[str, Any]) -> bool:
    if int(candidate.get('hwnd') or 0) != int(binding.get('hwnd') or 0):
        return False
    if int(candidate.get('process_id') or 0) != int(binding.get('process_id') or 0):
        return False
    expected_started = int(binding.get('process_started_at_ms') or 0)
    actual_started = int(candidate.get('process_started_at_ms') or 0)
    if expected_started and actual_started and abs(expected_started - actual_started) > 1000:
        return False
    return _stable_binding_matches(candidate, binding)


def choose_target_window(
    target: dict[str, Any], candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    expected = str(target.get('window_title') or '').strip()
    if not expected:
        raise WindowBindingResolutionError(
            'Windows 目标尚未填写窗口标题', error_id='target.reference_invalid',
        )
    mode = str(target.get('window_match') or 'contains')
    if mode not in {'contains', 'exact', 'regex'}:
        raise WindowBindingResolutionError(
            '窗口标题匹配方式无效', error_id='target.reference_invalid',
        )
    title_matches = [
        candidate for candidate in candidates
        if _title_matches(str(candidate.get('title') or ''), expected, mode)
    ]
    binding = target.get('window_binding')
    if isinstance(binding, dict):
        cached = next(
            (candidate for candidate in title_matches if _captured_instance_matches(candidate, binding)),
            None,
        )
        if cached is not None:
            return cached, 'captured_instance'
        stable = [candidate for candidate in title_matches if _stable_binding_matches(candidate, binding)]
        if len(stable) == 1:
            return stable[0], 'stable_recovery'
        if len(stable) > 1:
            raise WindowBindingResolutionError(
                f'捕获的窗口实例已失效，稳定特征仍匹配到 {len(stable)} 个窗口，请重新捕获',
                error_id='target.window_binding_ambiguous',
            )
        if title_matches:
            raise WindowBindingResolutionError(
                '捕获的窗口实例已失效，当前同名窗口与原窗口身份不一致，请重新捕获',
                error_id='target.window_binding_stale',
            )
        raise WindowBindingResolutionError(
            '捕获的目标窗口未出现，请打开窗口或重新捕获',
            error_id='target.offline', transient=True,
        )
    if not title_matches:
        raise WindowBindingResolutionError(
            '目标窗口未出现', error_id='target.offline', transient=True,
        )
    if len(title_matches) > 1:
        raise WindowBindingResolutionError(
            f'窗口标题匹配到 {len(title_matches)} 个目标，请使用捕获按钮选择具体窗口',
            error_id='target.window_binding_ambiguous',
        )
    return title_matches[0], 'title_rule'


def resolve_target_window(
    target: dict[str, Any], *, candidates: list[dict[str, Any]] | None = None,
    exclude_process_ids: Iterable[int] = (), require_ready: bool = True,
) -> tuple[dict[str, Any], str]:
    resolved, method = choose_target_window(
        target,
        candidates if candidates is not None else enumerate_window_candidates(
            exclude_process_ids=exclude_process_ids,
        ),
    )
    if require_ready and bool(resolved.get('minimized')):
        raise WindowBindingResolutionError(
            '目标窗口已最小化，请先还原', error_id='target.offline', transient=True,
        )
    return resolved, method


def captured_binding(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        'binding_version': 1,
        'binding_id': f'window_binding_{uuid.uuid4().hex}',
        'title': str(candidate.get('title') or ''),
        'class_name': str(candidate.get('class_name') or ''),
        'executable_name': str(candidate.get('executable_name') or ''),
        'hwnd': int(candidate.get('hwnd') or 0),
        'process_id': int(candidate.get('process_id') or 0),
        'process_started_at_ms': int(candidate.get('process_started_at_ms') or 0),
        'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }


def candidate_at_screen_point(
    candidates: list[dict[str, Any]], point: tuple[int, int],
) -> dict[str, Any]:
    x, y = (int(point[0]), int(point[1]))
    # EnumWindows preserves top-to-bottom z-order, so the first containing
    # window is the one shown in the frozen desktop frame.
    for candidate in candidates:
        rect = candidate.get('rect')
        if (
            isinstance(rect, (list, tuple)) and len(rect) == 4
            and int(rect[0]) <= x < int(rect[2])
            and int(rect[1]) <= y < int(rect[3])
        ):
            return candidate
    raise WindowBindingResolutionError(
        '点击位置没有可捕获的应用窗口，请点击窗口内容区域',
        error_id='target.window_capture_missed',
    )


def flash_window(hwnd: int) -> None:
    if os.name != 'nt' or int(hwnd or 0) <= 0:
        return
    try:
        import win32gui

        win32gui.FlashWindow(int(hwnd), True)
    except Exception:
        return


__all__ = [
    'WindowBindingResolutionError', 'candidate_at_screen_point', 'captured_binding',
    'choose_target_window', 'enumerate_window_candidates', 'flash_window',
    'resolve_target_window',
]
