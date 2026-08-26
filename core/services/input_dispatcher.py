"""统一输入分发器：后台优先、严格失败、模拟器强制 ADB。"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

from core.services.background_input import (
    background_click,
    background_drag,
    background_drag_path,
    background_scroll,
    background_text,
    is_foreground_window,
)
from core.services.runtime_target import RuntimeTargetError, workspace_point, workspace_to_android
from core.services.runtime_session import get_android_input_session


_PHYSICAL_INPUT_LOCK = threading.Lock()


def _work_mode(context) -> str:
    variables = getattr(context, 'variables', None)
    if isinstance(variables, dict) and variables.get('work_mode'):
        return str(variables.get('work_mode')).strip().lower()
    return str(getattr(context, 'work_mode', '') or '').strip().lower()


def _is_fullscreen(context) -> bool:
    return _work_mode(context) in {'desktop', 'fullscreen', 'full_screen'}


def _allow_physical(context) -> bool:
    if _is_fullscreen(context):
        return True
    return bool(
        context.get_setting('allow_physical_fallback', False)
        if hasattr(context, 'get_setting')
        else False
    )


def physical_fallback_allowed(context) -> bool:
    """Public policy query used by executors that perform semantic verification."""
    return _allow_physical(context)


def _activate_physical_target(context) -> tuple[bool, str]:
    """窗口模式物理输入前确保目标仍在前台；全屏模式无需绑定窗口。"""
    hwnd = getattr(context, 'window_hwnd', None)
    if not hwnd or _is_fullscreen(context):
        return True, ''
    if is_foreground_window(hwnd):
        return True, ''
    try:
        import win32con
        import win32gui

        root = int(win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd)
        if win32gui.IsIconic(root):
            win32gui.ShowWindow(root, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(root, win32con.SW_SHOW)
        win32gui.BringWindowToTop(root)
        win32gui.SetForegroundWindow(root)
        if not is_foreground_window(root):
            return False, '无法将目标工作窗口激活到前台'
        return True, ''
    except Exception as exc:
        return False, f'激活目标工作窗口失败: {exc}'


def _run_physical(context, operation, failure_prefix: str) -> dict:
    """串行执行一次物理输入，并无条件恢复操作前的鼠标位置。"""
    if not _PHYSICAL_INPUT_LOCK.acquire(timeout=0.5):
        return {
            'ok': False,
            'method': 'physical',
            'delivery': 'busy',
            'message': '物理输入通道正被其他任务占用（等待500ms后仍未释放）',
        }
    pyautogui = None
    original = None
    try:
        import pyautogui as _pyautogui

        pyautogui = _pyautogui
        original = pyautogui.position()
        activated, message = _activate_physical_target(context)
        if not activated:
            return {'ok': False, 'method': 'physical', 'delivery': 'failed', 'message': message}
        return operation(pyautogui)
    except Exception as exc:
        return {'ok': False, 'method': 'physical', 'delivery': 'failed', 'message': f'{failure_prefix}: {exc}'}
    finally:
        if pyautogui is not None and original is not None:
            try:
                pyautogui.moveTo(int(original[0]), int(original[1]))
            except Exception:
                pass
        _PHYSICAL_INPUT_LOCK.release()


def _warn_physical_fallback(context, kind: str, reason: str) -> None:
    message = f'[输入回退] {kind}后台输入失败：{reason}；已回退至物理输入'
    try:
        context.log(message, 'warning')
    except Exception:
        pass


def _physical_click(screen_x: int, screen_y: int, button: str, clicks: int, *, context=None) -> dict:
    try:
        def operation(pyautogui):
            pyautogui.click(screen_x, screen_y, button=button, clicks=clicks)
            return {
                'ok': True,
                'method': 'physical',
                'delivery': 'delivered_unverified',
                'verified': False,
                'message': f'物理点击屏幕({screen_x},{screen_y})，效果未验证',
            }
        return _run_physical(context, operation, '物理点击失败')
    except Exception as exc:
        return {'ok': False, 'method': 'physical', 'delivery': 'failed', 'message': f'物理点击失败: {exc}'}


def _adb_click(context, x: int, y: int, clicks: int, button: str) -> dict:
    if button != 'left':
        return {'ok': False, 'method': 'adb', 'delivery': 'unsupported', 'message': 'ADB tap仅支持左键语义'}
    device_id = str(getattr(context, 'device_id', '') or '').strip()
    if not device_id:
        return {
            'ok': False,
            'method': 'adb',
            'delivery': 'failed',
            'message': '模拟器未绑定唯一ADB设备，禁止回退物理鼠标',
        }
    transport = str(
        context.get_setting('android_input_transport', 'auto')
        if hasattr(context, 'get_setting')
        else 'auto'
    ).strip().lower()

    # If a visual node already owns a pinned scrcpy stream, inject through its
    # paired control socket. Capture and input then share one warm session and
    # no device-side ``input`` process is created for each tap.
    if transport in {'auto', 'scrcpy'}:
        scrcpy_session = getattr(context, '_android_video_session', None)
        if scrcpy_session is not None and hasattr(scrcpy_session, 'tap'):
            width = int(getattr(context, 'android_width', 0) or 0)
            height = int(getattr(context, 'android_height', 0) or 0)
            work_rect = getattr(context, 'window_rect', None)
            if isinstance(work_rect, (list, tuple)) and len(work_rect) >= 4:
                work_width, work_height = int(work_rect[2]), int(work_rect[3])
                if width > 0 and height > 0 and (work_width >= work_height) != (width >= height):
                    width, height = height, width
            if width > 0 and height > 0:
                result = None
                for _ in range(max(1, int(clicks or 1))):
                    result = scrcpy_session.tap(x, y, width, height)
                    if not result.get('ok'):
                        break
                if result and result.get('ok'):
                    return result
                if transport == 'scrcpy':
                    return result or {
                        'ok': False,
                        'method': 'scrcpy_control',
                        'delivery': 'failed',
                        'message': 'scrcpy 控制通道未产生结果',
                    }
        elif transport == 'scrcpy':
            return {
                'ok': False,
                'method': 'scrcpy_control',
                'delivery': 'unavailable',
                'message': '当前节点尚未建立 scrcpy 高速画面/控制会话',
            }

    # Reuse one warm adb shell per execution.  This removes host-side adb
    # startup from every tap while keeping the old subprocess transport as an
    # explicit compatibility tier.
    if transport != 'subprocess':
        try:
            session = get_android_input_session(context)
            result = None
            for _ in range(max(1, int(clicks or 1))):
                result = session.tap(x, y)
                if not result.get('ok'):
                    return result
            return result or {
                'ok': False,
                'method': 'adb_persistent',
                'delivery': 'failed',
                'message': 'ADB持久输入未产生结果',
            }
        except Exception as exc:
            if transport == 'persistent':
                return {
                    'ok': False,
                    'method': 'adb_persistent',
                    'delivery': 'failed',
                    'message': f'ADB持久输入通道不可用: {exc}',
                }
            # ``auto`` may fall back to another ADB background transport, but
            # never to the PC mouse.  The method remains visible in the result.

    try:
        for _ in range(max(1, int(clicks or 1))):
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell', 'input', 'tap', str(x), str(y)],
                capture_output=True,
                text=True,
                timeout=4,
            )
            if result.returncode != 0:
                return {
                    'ok': False,
                    'method': 'adb',
                    'delivery': 'failed',
                    'message': f'ADB点击失败: {(result.stderr or result.stdout).strip()}',
                }
        return {
            'ok': True,
            'method': 'adb',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'ADB点击设备[{device_id}]坐标({x},{y})，效果未验证',
            'transport_fallback': transport == 'auto',
        }
    except Exception as exc:
        return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': f'ADB点击异常: {exc}'}


def click_workspace(
    context,
    x: Any,
    y: Any,
    *,
    reference_size=None,
    button: str = 'left',
    clicks: int = 1,
    requested_mode: str = 'background',
) -> dict:
    """点击工作区坐标。

    ``allow_physical_fallback`` 在PC窗口模式默认关闭、只能由项目显式开启；全屏模式固定开启。
    模拟器无论该开关为何值都强制 ADB，
    因为 ADB 断线后点击模拟器窗口无法保证命中同一实例。
    """

    try:
        work_x, work_y, screen_x, screen_y = workspace_point(context, x, y, reference_size)
    except RuntimeTargetError as exc:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': str(exc)}

    button = str(button or 'left').lower()
    if button not in {'left', 'right', 'middle'}:
        return {'ok': False, 'method': 'none', 'delivery': 'unsupported', 'message': f'不支持的按键: {button}'}
    try:
        click_count = max(1, int(clicks or 1))
    except (TypeError, ValueError):
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': f'点击次数无效: {clicks!r}'}

    if bool(getattr(context, 'is_emulator', False)):
        try:
            android_x, android_y = workspace_to_android(
                context,
                work_x,
                work_y,
                current_work_area=getattr(context, 'window_rect', None),
            )
        except RuntimeTargetError as exc:
            return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': str(exc)}
        result = _adb_click(context, android_x, android_y, click_count, button)
        result.update(
            {
                'workspace_point': [work_x, work_y],
                'screen_point': [screen_x, screen_y],
                'android_point': [android_x, android_y],
            }
        )
        return result

    allow_physical = _allow_physical(context)
    mode = str(requested_mode or 'background').strip().lower()
    if _is_fullscreen(context):
        mode = 'physical'
    if mode in {'physical', 'foreground', 'mouse'}:
        if not allow_physical:
            return {
                'ok': False,
                'method': 'physical',
                'delivery': 'blocked',
                'message': '项目未开启“允许后台输入失败时回退物理输入”',
            }
        result = _physical_click(screen_x, screen_y, button, click_count, context=context)
    else:
        hwnd = getattr(context, 'window_hwnd', None)
        if hwnd:
            profile = getattr(context, '_input_capability_profile', None)
            known = profile.get('background_click') if isinstance(profile, dict) else None
            if not isinstance(known, dict):
                try:
                    from core.services.target_capability_profile import target_capability_profiles

                    known = target_capability_profiles.observation(context, 'background_click')
                    if isinstance(known, dict):
                        if not isinstance(profile, dict):
                            profile = {}
                            setattr(context, '_input_capability_profile', profile)
                        profile['background_click'] = known
                except Exception:
                    known = None
            if isinstance(known, dict) and known.get('supported') is False:
                result = {
                    'ok': False,
                    'method': 'background',
                    'delivery': 'unsupported',
                    'message': f'当前目标已验证不响应后台点击: {known.get("reason", "未知原因")}',
                }
            else:
                result = background_click(hwnd, screen_x, screen_y, button=button, clicks=click_count)
            result.setdefault('delivery', 'delivered_unverified' if result.get('ok') else 'failed')
            result.setdefault('verified', False)
            if result.get('ok'):
                result['message'] = f'{result.get("message", "后台消息已投递")}；效果未验证'
        else:
            result = {
                'ok': False,
                'method': 'background',
                'delivery': 'unsupported',
                'message': '未绑定窗口，桌面坐标不存在可定向的后台点击后端',
            }
        if not result.get('ok') and allow_physical:
            reason = result.get('message', '后台输入失败')
            result = _physical_click(screen_x, screen_y, button, click_count, context=context)
            result['fallback_reason'] = reason
            result['message'] = f'后台输入失败({reason})，已按项目设置回退；{result.get("message", "")}'
            _warn_physical_fallback(context, '点击', reason)

    result.update({'workspace_point': [work_x, work_y], 'screen_point': [screen_x, screen_y]})
    return result


def _physical_drag(
    start_screen: tuple[int, int],
    end_screen: tuple[int, int],
    *,
    button: str,
    duration_ms: int,
    hold_before_ms: int,
    hold_after_ms: int,
    stop_check=None,
    context=None,
) -> dict:
    def operation(pyautogui):
        pyautogui.moveTo(*start_screen)
        pyautogui.mouseDown(button=button)
        try:
            if hold_before_ms:
                time.sleep(max(0, hold_before_ms) / 1000.0)
            if stop_check and stop_check():
                return {'ok': False, 'method': 'physical', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
            pyautogui.moveTo(*end_screen, duration=max(0, duration_ms) / 1000.0)
            if hold_after_ms:
                time.sleep(max(0, hold_after_ms) / 1000.0)
            return {
                'ok': True,
                'method': 'physical',
                'delivery': 'delivered_unverified',
                'verified': False,
                'message': f'物理拖拽 {start_screen}->{end_screen}，效果未验证',
            }
        finally:
            pyautogui.mouseUp(button=button)
    return _run_physical(context, operation, '物理拖拽失败')


def _physical_drag_path(
    path_points: list[dict],
    *,
    button: str,
    easing: str,
    stop_check=None,
    context=None,
) -> dict:
    def operation(pyautogui):
        first = path_points[0]
        pyautogui.moveTo(*first['point'])
        pyautogui.mouseDown(button=button)
        try:
            if first.get('hold_ms'):
                time.sleep(max(0, int(first['hold_ms'])) / 1000.0)
            for segment in path_points[1:]:
                if stop_check and stop_check():
                    return {'ok': False, 'method': 'physical', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
                tween = pyautogui.easeInOutQuad if easing == 'ease_in_out' else pyautogui.linear
                pyautogui.moveTo(*segment['point'], duration=max(0, int(segment.get('move_ms', 0))) / 1000.0, tween=tween)
                if segment.get('hold_ms'):
                    time.sleep(max(0, int(segment['hold_ms'])) / 1000.0)
            return {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'物理拖拽已连续执行 {len(path_points)} 个路径点，效果未验证'}
        finally:
            pyautogui.mouseUp(button=button)
    return _run_physical(context, operation, '物理路径拖拽失败')


def _adb_swipe(
    context,
    start_android: tuple[int, int],
    end_android: tuple[int, int],
    *,
    duration_ms: int,
    hold_before_ms: int,
    hold_after_ms: int,
    steps: int,
    stop_check=None,
) -> dict:
    device_id = str(getattr(context, 'device_id', '') or '').strip()
    if not device_id:
        return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': '模拟器未绑定唯一ADB设备'}
    transport = str(context.get_setting('android_input_transport', 'auto') if hasattr(context, 'get_setting') else 'auto').strip().lower()
    width = int(getattr(context, 'android_width', 0) or 0)
    height = int(getattr(context, 'android_height', 0) or 0)
    work_rect = getattr(context, 'window_rect', None)
    if isinstance(work_rect, (list, tuple)) and len(work_rect) >= 4:
        work_width, work_height = int(work_rect[2]), int(work_rect[3])
        if width > 0 and height > 0 and (work_width >= work_height) != (width >= height):
            width, height = height, width

    if transport in {'auto', 'scrcpy'}:
        try:
            from core.services.android_stream import get_android_control_session

            session = get_android_control_session(context)
            result = session.swipe(
                *start_android,
                *end_android,
                width,
                height,
                duration_ms=duration_ms,
                hold_before_ms=hold_before_ms,
                hold_after_ms=hold_after_ms,
                steps=steps,
                stop_check=stop_check,
            )
            if result.get('ok') or transport == 'scrcpy':
                return result
        except Exception as exc:
            if transport == 'scrcpy':
                return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy滑动通道不可用: {exc}'}

    if transport != 'subprocess':
        try:
            session = get_android_input_session(context)
            result = session.swipe(
                *start_android,
                *end_android,
                duration_ms=duration_ms + hold_before_ms,
                hold_after_ms=hold_after_ms,
            )
            if result.get('ok') or transport == 'persistent':
                return result
        except Exception as exc:
            if transport == 'persistent':
                return {'ok': False, 'method': 'adb_persistent', 'delivery': 'failed', 'message': f'ADB持久滑动通道不可用: {exc}'}

    total_ms = max(1, int(duration_ms or 0) + int(hold_before_ms or 0) + int(hold_after_ms or 0))
    try:
        result = subprocess.run(
            [
                'adb', '-s', device_id, 'shell', 'input', 'swipe',
                str(start_android[0]), str(start_android[1]), str(end_android[0]), str(end_android[1]), str(total_ms),
            ],
            capture_output=True,
            text=True,
            timeout=max(4.0, total_ms / 1000.0 + 2.0),
        )
        if result.returncode != 0:
            return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': f'ADB滑动失败: {(result.stderr or result.stdout).strip()}'}
        return {'ok': True, 'method': 'adb', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'ADB滑动已投递 {start_android}->{end_android}，效果未验证'}
    except Exception as exc:
        return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': f'ADB滑动异常: {exc}'}


def _adb_swipe_path(context, path_points: list[dict], *, easing: str, stop_check=None) -> dict:
    if len(path_points) < 2:
        return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': 'Android拖拽路径至少需要两个点'}
    transport = str(context.get_setting('android_input_transport', 'auto') if hasattr(context, 'get_setting') else 'auto').strip().lower()
    width = int(getattr(context, 'android_width', 0) or 0)
    height = int(getattr(context, 'android_height', 0) or 0)
    work_rect = getattr(context, 'window_rect', None)
    if isinstance(work_rect, (list, tuple)) and len(work_rect) >= 4:
        work_width, work_height = int(work_rect[2]), int(work_rect[3])
        if width > 0 and height > 0 and (work_width >= work_height) != (width >= height):
            width, height = height, width
    if transport in {'auto', 'scrcpy'}:
        try:
            from core.services.android_stream import get_android_control_session

            result = get_android_control_session(context).swipe_path(
                path_points, width, height, easing=easing, stop_check=stop_check,
            )
            if result.get('ok') or transport == 'scrcpy':
                return result
        except Exception as exc:
            if transport == 'scrcpy':
                return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy路径拖拽通道不可用: {exc}'}
    if len(path_points) > 2:
        return {
            'ok': False,
            'method': 'adb',
            'delivery': 'unsupported',
            'message': '多点连续拖拽需要可用的scrcpy控制通道；普通ADB swipe会在每段之间松手，已阻止不等价回退',
        }
    first, last = path_points
    return _adb_swipe(
        context,
        tuple(first['point']),
        tuple(last['point']),
        duration_ms=max(0, int(last.get('move_ms', 0))),
        hold_before_ms=max(0, int(first.get('hold_ms', 0))),
        hold_after_ms=max(0, int(last.get('hold_ms', 0))),
        steps=max(1, round(max(16, int(last.get('move_ms', 0))) / 16)),
        stop_check=stop_check,
    )


def drag_workspace(
    context,
    start_x: Any,
    start_y: Any,
    end_x: Any,
    end_y: Any,
    *,
    reference_size=None,
    button: str = 'left',
    duration_ms: int = 300,
    hold_before_ms: int = 0,
    hold_after_ms: int = 0,
    steps: int = 12,
    requested_mode: str = 'background',
    stop_check=None,
) -> dict:
    """在统一工作区坐标系内执行拖拽/滑动/长按。"""
    try:
        sx, sy, ssx, ssy = workspace_point(context, start_x, start_y, reference_size)
        ex, ey, esx, esy = workspace_point(context, end_x, end_y, reference_size)
    except RuntimeTargetError as exc:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': str(exc)}
    button = str(button or 'left').lower()
    if button not in {'left', 'right', 'middle'}:
        return {'ok': False, 'method': 'none', 'delivery': 'unsupported', 'message': f'不支持的按键: {button}'}
    if bool(getattr(context, 'is_emulator', False)):
        if button != 'left':
            return {'ok': False, 'method': 'adb', 'delivery': 'unsupported', 'message': 'Android触摸手势只支持左键/单指语义'}
        try:
            android_start = workspace_to_android(context, sx, sy, current_work_area=getattr(context, 'window_rect', None))
            android_end = workspace_to_android(context, ex, ey, current_work_area=getattr(context, 'window_rect', None))
        except RuntimeTargetError as exc:
            return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': str(exc)}
        result = _adb_swipe(
            context,
            android_start,
            android_end,
            duration_ms=max(0, int(duration_ms or 0)),
            hold_before_ms=max(0, int(hold_before_ms or 0)),
            hold_after_ms=max(0, int(hold_after_ms or 0)),
            steps=max(1, int(steps or 1)),
            stop_check=stop_check,
        )
        result.update({'workspace_start': [sx, sy], 'workspace_end': [ex, ey], 'android_start': list(android_start), 'android_end': list(android_end)})
        return result

    allow_physical = _allow_physical(context)
    mode = str(requested_mode or 'background').strip().lower()
    if _is_fullscreen(context):
        mode = 'physical'
    if mode in {'physical', 'foreground', 'mouse'}:
        if not allow_physical:
            return {'ok': False, 'method': 'physical', 'delivery': 'blocked', 'message': '项目未开启物理输入授权'}
        result = _physical_drag((ssx, ssy), (esx, esy), button=button, duration_ms=duration_ms, hold_before_ms=hold_before_ms, hold_after_ms=hold_after_ms, stop_check=stop_check, context=context)
    else:
        hwnd = getattr(context, 'window_hwnd', None)
        result = background_drag(
            hwnd,
            (ssx, ssy),
            (esx, esy),
            button=button,
            duration_ms=duration_ms,
            hold_before_ms=hold_before_ms,
            hold_after_ms=hold_after_ms,
            steps=steps,
            stop_check=stop_check,
        ) if hwnd else {'ok': False, 'method': 'background', 'delivery': 'unsupported', 'message': '未绑定窗口，无法定向后台拖拽'}
        if not result.get('ok') and result.get('delivery') != 'cancelled' and allow_physical:
            reason = result.get('message', '后台拖拽失败')
            result = _physical_drag((ssx, ssy), (esx, esy), button=button, duration_ms=duration_ms, hold_before_ms=hold_before_ms, hold_after_ms=hold_after_ms, stop_check=stop_check, context=context)
            result['fallback_reason'] = reason
            _warn_physical_fallback(context, '拖拽', reason)
    result.update({'workspace_start': [sx, sy], 'workspace_end': [ex, ey], 'screen_start': [ssx, ssy], 'screen_end': [esx, esy]})
    return result


def drag_path_workspace(
    context,
    path_points: list[dict],
    *,
    reference_size=None,
    button: str = 'left',
    easing: str = 'linear',
    requested_mode: str = 'background',
    stop_check=None,
) -> dict:
    """连续执行一条工作区多点路径；中途不会松开鼠标或触摸。"""
    if not isinstance(path_points, list) or not path_points:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': '拖拽路径为空'}
    if len(path_points) > 32:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': '拖拽路径最多支持32个点'}
    workspace_path = []
    screen_path = []
    try:
        for index, item in enumerate(path_points):
            position = item.get('position') if isinstance(item, dict) else None
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': f'拖拽路径第{index + 1}个点无效'}
            wx, wy, sx, sy = workspace_point(context, position[0], position[1], reference_size)
            values = {'move_ms': max(0, int(item.get('move_ms', 0) or 0)), 'hold_ms': max(0, int(item.get('hold_ms', 0) or 0))}
            workspace_path.append({'point': [wx, wy], **values})
            screen_path.append({'point': [sx, sy], **values})
    except RuntimeTargetError as exc:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': str(exc)}

    button = str(button or 'left').lower()
    if button not in {'left', 'right', 'middle'}:
        return {'ok': False, 'method': 'none', 'delivery': 'unsupported', 'message': f'不支持的按键: {button}'}
    if bool(getattr(context, 'is_emulator', False)):
        if button != 'left':
            return {'ok': False, 'method': 'adb', 'delivery': 'unsupported', 'message': 'Android触摸手势只支持单指语义'}
        android_path = []
        try:
            for item in workspace_path:
                point = workspace_to_android(context, item['point'][0], item['point'][1], current_work_area=getattr(context, 'window_rect', None))
                android_path.append({'point': list(point), 'move_ms': item['move_ms'], 'hold_ms': item['hold_ms']})
        except RuntimeTargetError as exc:
            return {'ok': False, 'method': 'adb', 'delivery': 'failed', 'message': str(exc)}
        result = _adb_swipe_path(context, android_path, easing=easing, stop_check=stop_check)
        result.update({'workspace_path': workspace_path, 'android_path': android_path})
        return result

    allow_physical = _allow_physical(context)
    mode = str(requested_mode or 'background').strip().lower()
    if _is_fullscreen(context):
        mode = 'physical'
    if mode in {'physical', 'foreground', 'mouse'}:
        if not allow_physical:
            return {'ok': False, 'method': 'physical', 'delivery': 'blocked', 'message': '项目未开启物理输入授权'}
        result = _physical_drag_path(screen_path, button=button, easing=easing, stop_check=stop_check, context=context)
    else:
        hwnd = getattr(context, 'window_hwnd', None)
        result = background_drag_path(hwnd, screen_path, button=button, easing=easing, stop_check=stop_check) if hwnd else {
            'ok': False, 'method': 'background', 'delivery': 'unsupported', 'message': '未绑定窗口，无法定向后台拖拽',
        }
        if not result.get('ok') and result.get('delivery') != 'cancelled' and allow_physical:
            reason = result.get('message', '后台拖拽失败')
            result = _physical_drag_path(screen_path, button=button, easing=easing, stop_check=stop_check, context=context)
            result['fallback_reason'] = reason
            _warn_physical_fallback(context, '拖拽', reason)
    result.update({'workspace_path': workspace_path, 'screen_path': screen_path})
    return result


def scroll_workspace(
    context,
    x: Any,
    y: Any,
    *,
    ticks: int,
    reference_size=None,
    requested_mode: str = 'background',
) -> dict:
    """在PC目标窗口投递语义滚轮；Android请使用 ``drag_workspace``。"""
    try:
        wx, wy, screen_x, screen_y = workspace_point(context, x, y, reference_size)
    except RuntimeTargetError as exc:
        return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': str(exc)}
    if bool(getattr(context, 'is_emulator', False)):
        return {'ok': False, 'method': 'adb', 'delivery': 'unsupported', 'message': 'Android不支持鼠标滚轮，请使用滑动模式'}
    allow_physical = _allow_physical(context)
    mode = str(requested_mode or 'background').strip().lower()
    if _is_fullscreen(context):
        mode = 'physical'
    if mode in {'physical', 'foreground', 'mouse'}:
        if not allow_physical:
            return {'ok': False, 'method': 'physical', 'delivery': 'blocked', 'message': '项目未开启物理输入授权'}
        def operation(pyautogui):
            pyautogui.moveTo(screen_x, screen_y)
            pyautogui.scroll(int(ticks))
            return {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'物理滚轮已执行，格数={int(ticks)}'}
        result = _run_physical(context, operation, '物理滚轮失败')
    else:
        hwnd = getattr(context, 'window_hwnd', None)
        result = background_scroll(hwnd, screen_x, screen_y, int(ticks)) if hwnd else {'ok': False, 'method': 'background', 'delivery': 'unsupported', 'message': '未绑定窗口，无法后台滚轮'}
        if not result.get('ok') and allow_physical:
            reason = result.get('message', '后台滚轮失败')
            def operation(pyautogui):
                pyautogui.moveTo(screen_x, screen_y)
                pyautogui.scroll(int(ticks))
                return {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'后台滚轮失败后按授权回退，格数={int(ticks)}'}
            result = _run_physical(context, operation, '滚轮回退失败')
            result['fallback_reason'] = reason
            _warn_physical_fallback(context, '滚轮', reason)
    result.update({'workspace_point': [wx, wy], 'screen_point': [screen_x, screen_y]})
    return result


def _adb_text(context, text: str, *, clear_before: bool = False, submit_key: str = 'none') -> dict:
    transport = str(context.get_setting('android_input_transport', 'auto') if hasattr(context, 'get_setting') else 'auto').strip().lower()
    if transport in {'auto', 'scrcpy'}:
        try:
            from core.services.android_stream import get_android_control_session

            session = get_android_control_session(context)
            if clear_before:
                selected = session.keyevent(29, metastate=0x1000)  # KEYCODE_A + META_CTRL_ON
                if not selected.get('ok'):
                    return selected
                cleared = session.keyevent(67)  # KEYCODE_DEL
                if not cleared.get('ok'):
                    return cleared
            result = session.inject_text(text)
            if result.get('ok'):
                key_map = {'enter': 66, 'tab': 61, 'escape': 111}
                if str(submit_key or 'none').lower() in key_map:
                    key_result = session.keyevent(key_map[str(submit_key).lower()])
                    if not key_result.get('ok'):
                        return key_result
                return result
            if transport == 'scrcpy':
                return result
        except Exception as exc:
            if transport == 'scrcpy':
                return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy文本通道不可用: {exc}'}
    try:
        session = get_android_input_session(context)
        if clear_before:
            selected = session.keycombination(113, 29)  # KEYCODE_CTRL_LEFT + KEYCODE_A
            if not selected.get('ok'):
                return selected
            cleared = session.keyevent(67)
            if not cleared.get('ok'):
                return cleared
        result = session.text(text)
        if result.get('ok'):
            key_map = {'enter': 66, 'tab': 61, 'escape': 111}
            if str(submit_key or 'none').lower() in key_map:
                key_result = session.keyevent(key_map[str(submit_key).lower()])
                if not key_result.get('ok'):
                    return key_result
                result['submit_key'] = str(submit_key).lower()
        return result
    except Exception as exc:
        return {'ok': False, 'method': 'adb_persistent', 'delivery': 'failed', 'message': f'ADB文本输入失败: {exc}'}


def text_workspace(
    context,
    text: str,
    *,
    position=None,
    reference_size=None,
    click_before: bool = True,
    clear_before: bool = False,
    interval_ms: int = 0,
    submit_key: str = 'none',
    requested_mode: str = 'background',
    stop_check=None,
) -> dict:
    """将文本定向输入已绑定的PC窗口或Android实例。"""
    point_data = None
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        try:
            point_data = workspace_point(context, position[0], position[1], reference_size)
        except RuntimeTargetError as exc:
            return {'ok': False, 'method': 'none', 'delivery': 'failed', 'message': str(exc)}
        if click_before:
            click_result = click_workspace(
                context,
                position[0],
                position[1],
                reference_size=reference_size,
                requested_mode=requested_mode,
            )
            if not click_result.get('ok'):
                return click_result
    if bool(getattr(context, 'is_emulator', False)):
        result = _adb_text(context, str(text or ''), clear_before=clear_before, submit_key=submit_key)
        if point_data:
            result['workspace_point'] = [point_data[0], point_data[1]]
        return result

    hwnd = getattr(context, 'window_hwnd', None)
    allow_physical = _allow_physical(context)
    mode = str(requested_mode or 'background').strip().lower()
    if _is_fullscreen(context):
        mode = 'physical'
    if mode in {'physical', 'foreground', 'keyboard'}:
        if not allow_physical:
            return {'ok': False, 'method': 'physical', 'delivery': 'blocked', 'message': '项目未开启物理输入授权'}
        def operation(pyautogui):
            if clear_before:
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
            pyautogui.write(str(text or ''), interval=max(0, int(interval_ms or 0)) / 1000.0)
            if submit_key in {'enter', 'tab', 'escape'}:
                pyautogui.press(submit_key)
            return {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'物理键盘已输入长度={len(str(text or ""))}'}
        return _run_physical(context, operation, '物理文本输入失败')
    if not hwnd:
        return {'ok': False, 'method': 'background', 'delivery': 'unsupported', 'message': '未绑定窗口，无法定向文本输入'}
    screen_point = (point_data[2], point_data[3]) if point_data else None
    result = background_text(
        hwnd,
        str(text or ''),
        screen_point=screen_point,
        clear_before=clear_before,
        interval_ms=interval_ms,
        submit_key=submit_key,
        stop_check=stop_check,
    )
    if not result.get('ok') and result.get('delivery') != 'cancelled' and allow_physical:
        reason = result.get('message', '后台文本输入失败')
        def operation(pyautogui):
            if clear_before:
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
            pyautogui.write(str(text or ''), interval=max(0, int(interval_ms or 0)) / 1000.0)
            if submit_key in {'enter', 'tab', 'escape'}:
                pyautogui.press(submit_key)
            return {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'后台输入失败后按授权回退，长度={len(str(text or ""))}'}
        result = _run_physical(context, operation, '文本输入回退失败')
        result['fallback_reason'] = reason
        _warn_physical_fallback(context, '文本输入', reason)
    if point_data:
        result.update({'workspace_point': [point_data[0], point_data[1]], 'screen_point': [point_data[2], point_data[3]]})
    return result
