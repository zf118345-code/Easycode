"""运行目标与工作区坐标的统一边界。

所有录制坐标均使用裁剪后工作区坐标（workspace_px）。窗口屏幕坐标、
Android 显示坐标和后台截图都必须经由这里转换，避免节点各自解释坐标。
"""

from __future__ import annotations

import io
import math
import subprocess
import time
from typing import Any

from PIL import Image

from core.services import screenshot_service


class RuntimeTargetError(RuntimeError):
    """目标窗口、设备或坐标无效。"""


def _number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeTargetError(f'{label}不是有效数字: {value!r}') from exc
    if not math.isfinite(number):
        raise RuntimeTargetError(f'{label}必须是有限数字')
    return number


def _content_offsets(context) -> tuple[int, int, int, int]:
    raw = getattr(context, 'variables', {}).get('window_content_offset') or {}
    if not isinstance(raw, dict):
        raw = {}
    return (
        int(raw.get('top', 0) or 0),
        int(raw.get('bottom', 0) or 0),
        int(raw.get('left', 0) or 0),
        int(raw.get('right', 0) or 0),
    )


def refresh_work_area(context) -> tuple[int, int, int, int]:
    """返回最新工作区 ``(left, top, width, height)``。

    绑定窗口时每次重新读取客户区，避免窗口移动、缩放和跨屏后继续使用旧坐标。
    桌面模式保留初始化时挂载的裁剪矩形。
    """

    hwnd = getattr(context, 'window_hwnd', None)
    if bool(getattr(context, 'is_emulator', False)):
        configured_size = getattr(context, 'variables', {}).get('target_content_size') or []
        if isinstance(configured_size, (list, tuple)) and len(configured_size) >= 2:
            try:
                configured_width = int(configured_size[0])
                configured_height = int(configured_size[1])
            except (TypeError, ValueError):
                configured_width = configured_height = 0
            if configured_width > 0 and configured_height > 0:
                # ADB 截图/点击只需要稳定的工作区尺寸。窗口未最小化时保留屏幕
                # 原点用于日志；最小化时 Windows 返回 -32000 坐标，改用 (0, 0)。
                left = top = 0
                if hwnd:
                    try:
                        import win32gui

                        if win32gui.IsWindow(hwnd) and not win32gui.IsIconic(hwnd):
                            client = win32gui.GetClientRect(hwnd)
                            left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
                            off_top, _, off_left, _ = _content_offsets(context)
                            left += off_left
                            top += off_top
                    except Exception:
                        left = top = 0
                rect = (int(left), int(top), configured_width, configured_height)
                if getattr(context, 'window_rect', None) != rect:
                    context.window_rect = rect
                    getattr(context, 'variables', {})['window_rect'] = rect
                return rect

    if hwnd:
        try:
            import win32gui

            if not win32gui.IsWindow(hwnd):
                raise RuntimeTargetError('绑定窗口已关闭或句柄失效')
            client = win32gui.GetClientRect(hwnd)
            left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
            right, bottom = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
        except RuntimeTargetError:
            raise
        except Exception as exc:
            raise RuntimeTargetError(f'无法刷新绑定窗口客户区: {exc}') from exc

        off_top, off_bottom, off_left, off_right = _content_offsets(context)
        rect = (
            int(left + off_left),
            int(top + off_top),
            int((right - left) - off_left - off_right),
            int((bottom - top) - off_top - off_bottom),
        )
        if rect[2] <= 0 or rect[3] <= 0:
            raise RuntimeTargetError(f'裁剪后的工作区无效: {rect}')
        if getattr(context, 'window_rect', None) != rect:
            context.window_rect = rect
            getattr(context, 'variables', {})['window_rect'] = rect
        return rect

    rect = getattr(context, 'window_rect', None)
    getter = getattr(context, 'get_window_rect', None)
    if not rect and callable(getter) and not getattr(context, '_refresh_work_area_active', False):
        # Compatibility for node/test/plugin contexts that expose the original
        # get_window_rect contract without a public window_rect attribute.
        setattr(context, '_refresh_work_area_active', True)
        try:
            rect = getter()
        finally:
            try:
                delattr(context, '_refresh_work_area_active')
            except AttributeError:
                pass
    if rect and len(rect) == 4 and int(rect[2]) > 0 and int(rect[3]) > 0:
        return tuple(int(v) for v in rect)

    try:
        import pyautogui

        width, height = pyautogui.size()
    except Exception as exc:
        raise RuntimeTargetError(f'无法获取桌面尺寸: {exc}') from exc
    return (0, 0, int(width), int(height))


def normalize_reference_size(reference_size, current_size: tuple[int, int]) -> tuple[int, int]:
    if isinstance(reference_size, (list, tuple)) and len(reference_size) >= 2:
        try:
            width, height = int(reference_size[0]), int(reference_size[1])
            if width > 0 and height > 0:
                return width, height
        except (TypeError, ValueError):
            pass
    return current_size


def workspace_point(
    context,
    x: Any,
    y: Any,
    reference_size=None,
    current_work_area=None,
) -> tuple[int, int, int, int]:
    """工作区录制坐标 -> 当前工作区坐标与屏幕坐标。

    返回 ``(work_x, work_y, screen_x, screen_y)``。右/下边界不允许等于尺寸，
    防止合法性检查后仍点击到工作区外。
    """

    left, top, width, height = current_work_area or refresh_work_area(context)
    ref_w, ref_h = normalize_reference_size(reference_size, (width, height))
    work_x = int(round(_number(x, 'X坐标') * width / ref_w))
    work_y = int(round(_number(y, 'Y坐标') * height / ref_h))
    if not (0 <= work_x < width and 0 <= work_y < height):
        raise RuntimeTargetError(
            f'工作区坐标越界: ({work_x}, {work_y})，有效范围为 '
            f'0..{width - 1}, 0..{height - 1}'
        )
    return work_x, work_y, left + work_x, top + work_y


def workspace_rect(context, rect, reference_size=None, current_work_area=None) -> tuple[int, int, int, int]:
    """工作区 ``[x,y,w,h]`` -> 当前工作区 ``(x,y,w,h)``，并严格校验边界。"""

    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        raise RuntimeTargetError('区域必须是 [x, y, w, h]')
    _, _, current_w, current_h = current_work_area or refresh_work_area(context)
    ref_w, ref_h = normalize_reference_size(reference_size, (current_w, current_h))
    x = int(round(_number(rect[0], '区域X') * current_w / ref_w))
    y = int(round(_number(rect[1], '区域Y') * current_h / ref_h))
    width = int(round(_number(rect[2], '区域宽度') * current_w / ref_w))
    height = int(round(_number(rect[3], '区域高度') * current_h / ref_h))
    if width <= 0 or height <= 0:
        raise RuntimeTargetError(f'区域尺寸必须大于0: ({width}, {height})')
    if x < 0 or y < 0 or x + width > current_w or y + height > current_h:
        raise RuntimeTargetError(
            f'工作区区域越界: ({x}, {y}, {width}, {height})，当前工作区={current_w}x{current_h}'
        )
    return x, y, width, height


def workspace_to_android(context, work_x: int, work_y: int, current_work_area=None) -> tuple[int, int]:
    """当前工作区坐标 -> Android 当前显示坐标。"""

    _, _, work_w, work_h = current_work_area or refresh_work_area(context)
    raw_w = int(getattr(context, 'android_width', 0) or 0)
    raw_h = int(getattr(context, 'android_height', 0) or 0)
    if raw_w <= 0 or raw_h <= 0:
        raise RuntimeTargetError('未获取到Android显示分辨率')

    # wm size 在部分模拟器中返回自然方向尺寸；用当前工作区方向校正一次。
    if (work_w >= work_h) != (raw_w >= raw_h):
        raw_w, raw_h = raw_h, raw_w
    android_x = min(raw_w - 1, max(0, int(round(work_x * raw_w / work_w))))
    android_y = min(raw_h - 1, max(0, int(round(work_y * raw_h / work_h))))
    return android_x, android_y


def _capture_adb_workspace(context, size: tuple[int, int]) -> Image.Image:
    device_id = str(getattr(context, 'device_id', '') or '').strip()
    if not device_id:
        raise RuntimeTargetError('模拟器未绑定ADB设备，禁止回退桌面截图')
    try:
        result = subprocess.run(
            ['adb', '-s', device_id, 'exec-out', 'screencap', '-p'],
            capture_output=True,
            timeout=8,
        )
    except Exception as exc:
        raise RuntimeTargetError(f'ADB截图异常: {exc}') from exc
    if result.returncode != 0 or not result.stdout:
        detail = result.stderr.decode(errors='ignore').strip() if result.stderr else '无图像数据'
        raise RuntimeTargetError(f'ADB截图失败: {detail}')
    try:
        image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
        image.load()
    except Exception as exc:
        raise RuntimeTargetError(f'ADB截图数据无法解码: {exc}') from exc
    if image.size != size:
        image = image.resize(size, Image.Resampling.BILINEAR)
    return image


def _capture_bound_window(context, work_rect: tuple[int, int, int, int]) -> Image.Image:
    hwnd = getattr(context, 'window_hwnd', None)
    force_foreground = bool(getattr(context, '_capture_force_foreground', False))
    image, capture_info = (None, {
        'provider': 'none', 'capability': 'foreground_required', 'verified': False,
        'message': '该执行实例已判定后台捕获不可用',
    }) if force_foreground else screenshot_service.capture_window_with_info(hwnd)
    try:
        context._last_capture_info = dict(capture_info or {})
    except Exception:
        pass
    if image is None:
        return _capture_foreground_window(context, work_rect, capture_info)
    try:
        left, top, width, height = work_rect
        cropped = screenshot_service.crop_window_image(
            hwnd, image, (left, top, left + width, top + height),
        )
        extrema = cropped.convert('L').getextrema()
        if extrema and extrema[1] <= 2:
            capture_info = {
                **(capture_info or {}),
                'message': f'目标窗口{(capture_info or {}).get("provider") or "后台捕获"}返回全黑帧',
            }
            return _capture_foreground_window(context, work_rect, capture_info)
        return cropped
    except RuntimeTargetError:
        raise
    except ValueError as exc:
        # A provider can return client-only pixels while the recorded workspace
        # was based on the outer window (or vice versa).  A geometry mismatch is
        # a capture-capability failure, not a reason to abort before trying the
        # visible foreground tier.
        return _capture_foreground_window(context, work_rect, {
            **(capture_info or {}),
            'message': f'后台截图与工作区尺寸/DPI 不一致: {exc}',
        })
    except Exception as exc:
        raise RuntimeTargetError(f'后台窗口截图裁剪失败: {exc}') from exc


def _capture_foreground_window(context, work_rect, previous_info) -> Image.Image:
    """Last capture tier: visibly activate the bound window and capture screen pixels."""
    hwnd = getattr(context, 'window_hwnd', None)
    reason = (previous_info or {}).get('message') or '后台捕获不可用'
    attached = []
    try:
        import win32api
        import win32con
        import win32gui
        import win32process

        root = int(win32gui.GetAncestor(int(hwnd), getattr(win32con, 'GA_ROOT', 2)) or hwnd)
        current_thread = int(win32api.GetCurrentThreadId())
        target_thread = int(win32process.GetWindowThreadProcessId(root)[0])
        foreground_before = int(win32gui.GetForegroundWindow() or 0)
        foreground_thread = int(win32process.GetWindowThreadProcessId(foreground_before)[0]) if foreground_before else 0
        for other_thread in {target_thread, foreground_thread}:
            if other_thread and other_thread != current_thread:
                try:
                    win32process.AttachThreadInput(current_thread, other_thread, True)
                    attached.append((current_thread, other_thread))
                except Exception:
                    pass
        if win32gui.IsIconic(root):
            win32gui.ShowWindow(root, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(root, win32con.SW_SHOW)
        win32gui.BringWindowToTop(root)
        win32gui.SetForegroundWindow(root)
        time.sleep(0.03)
        foreground = int(win32gui.GetForegroundWindow() or 0)
        foreground_root = int(win32gui.GetAncestor(foreground, getattr(win32con, 'GA_ROOT', 2)) or foreground)
        if foreground_root != root:
            raise RuntimeTargetError('系统拒绝将目标窗口激活到前台')
        left, top, width, height = [int(value) for value in work_rect]
        image = screenshot_service.capture((left, top, left + width, top + height)).convert('RGB')
        extrema = image.convert('L').getextrema()
        if extrema and extrema[1] <= 2:
            raise RuntimeTargetError('前台 DXGI 仍返回全黑帧，目标可能启用了保护画面或独占全屏')
        info = {
            'provider': 'dxgi_foreground',
            'capability': 'foreground_required',
            'verified': True,
            'capture_duration_ms': 0.0,
            'message': f'{reason}；已激活目标窗口并使用前台 DXGI 捕获',
            'fallback_reasons': (previous_info or {}).get('fallback_reasons') or [],
        }
        context._last_capture_info = info
        context._capture_force_foreground = True
        if not getattr(context, '_foreground_capture_warning_emitted', False):
            context.log(f'[捕获降级] {info["message"]}；该实例不再具备后台多开能力', 'warning')
            context._foreground_capture_warning_emitted = True
        return image
    except RuntimeTargetError:
        raise
    except Exception as exc:
        raise RuntimeTargetError(f'{reason}；激活目标后截图仍失败: {exc}') from exc
    finally:
        if attached:
            try:
                import win32process

                for first, second in reversed(attached):
                    try:
                        win32process.AttachThreadInput(first, second, False)
                    except Exception:
                        pass
            except Exception:
                pass


def capture_workspace(context, work_rect=None) -> Image.Image:
    """捕获与输入目标相同的工作区画面；绑定失败时严格报错，不回退全屏。"""

    work_rect = work_rect or refresh_work_area(context)
    _, _, width, height = work_rect
    if bool(getattr(context, 'is_emulator', False)):
        return _capture_adb_workspace(context, (width, height))
    if getattr(context, 'window_hwnd', None):
        return _capture_bound_window(context, work_rect)
    left, top, _, _ = work_rect
    return screenshot_service.capture(region=(left, top, left + width, top + height)).convert('RGB')


def capture_workspace_region(context, rect=None, reference_size=None) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """捕获工作区区域，返回图片及区域在当前工作区中的 ``(x,y,w,h)``。"""

    work = refresh_work_area(context)
    if rect is None:
        relative = (0, 0, work[2], work[3])
    else:
        relative = workspace_rect(context, rect, reference_size, current_work_area=work)

    # 无绑定目标时保留直接区域截图，桌面模式无需先抓整屏；也便于测试明确截图契约。
    if not getattr(context, 'window_hwnd', None) and not bool(getattr(context, 'is_emulator', False)):
        left = work[0] + relative[0]
        top = work[1] + relative[1]
        image = screenshot_service.capture(
            region=(left, top, left + relative[2], top + relative[3])
        ).convert('RGB')
        return image, relative

    image = capture_workspace(context, work_rect=work)
    x, y, width, height = relative
    return image.crop((x, y, x + width, y + height)), relative
