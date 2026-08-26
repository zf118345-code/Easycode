# core/services/screenshot_service.py
# ⚡ 统一截图服务（#1 技术债修复）：DXGI 前台捕获（dxcam，毫秒级）+ PrintWindow 后台窗口捕获
# 优先级：dxcam（区域/全屏，快 10-100 倍）→ pyautogui（Pillow GDI 兜底）
# 返回 PIL Image（与既有调用方 pyautogui.screenshot 的返回类型一致）
import logging
import threading
import time

logger = logging.getLogger(__name__)

_dxcam_lock = threading.Lock()
_dxcam = None


def _get_dxcam():
    """惰性创建 dxcam 实例（线程安全）；不可用返回 None"""
    global _dxcam
    if _dxcam is not None:
        return _dxcam
    with _dxcam_lock:
        if _dxcam is not None:
            return _dxcam
        try:
            import dxcam

            _dxcam = dxcam.create(output_color='RGB')
            return _dxcam
        except Exception as e:
            logger.warning('dxcam 不可用，回退 pyautogui 截图: %s', e)
            return None


def capture(region=None):
    """截取屏幕区域（默认全屏），返回 PIL Image。
    ⚡ dxcam 区域抓取只捕获指定区域（0-几 ms），不再全屏抓取后内存裁剪。
    ⚡ region 自动裁剪到屏幕边界内（窗口部分在屏幕外/负坐标时不再 500）；
    完全越界（如窗口被移到屏幕外/最小化）时回退全屏截图，保证调用方永远拿到图像。
    :param region: (left, top, right, bottom) 屏幕绝对坐标
    """
    if region:
        region = _clamp_region(region)
        if region is None:
            logger.warning('截图区域完全越出屏幕，回退全屏截图')
            region = None
    cam = _get_dxcam()
    if cam is not None:
        try:
            frame = cam.grab(region=region)
            if frame is not None and frame.size > 0:
                from PIL import Image

                return Image.fromarray(frame)
        except Exception as e:
            logger.warning('dxcam 抓取失败，回退 pyautogui: %s', e)
    # 回退：Pillow GDI（pyautogui 底层）
    import pyautogui

    if region:
        left, top, right, bottom = region
        return pyautogui.screenshot(region=(left, top, right - left, bottom - top))
    return pyautogui.screenshot()


def _clamp_region(region):
    """把区域裁剪到虚拟屏幕边界内（支持多显示器负坐标）；完全越界返回 None"""
    try:
        left, top, right, bottom = [int(v) for v in region]
    except (TypeError, ValueError):
        return None
    try:
        import win32api

        ox = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        oy = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        sw = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        sh = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    except Exception:
        try:
            import pyautogui

            sw, sh = pyautogui.size()
            ox = oy = 0
        except Exception:
            return None
    left = max(ox, min(left, ox + sw))
    right = max(ox, min(right, ox + sw))
    top = max(oy, min(top, oy + sh))
    bottom = max(oy, min(bottom, oy + sh))
    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)


def _capture_window_printwindow(hwnd):
    """后台窗口捕获（PrintWindow）：窗口被遮挡/最小化到桌面外也能截到内容。
    ⚡ 与后台点击（background_input）配套：多开场景窗口无需置前即可识别。
    失败（窗口已关闭等）返回 None。"""
    if not hwnd:
        return None
    try:
        import win32gui
        import win32ui

        rect = win32gui.GetWindowRect(hwnd)
        if rect is None or rect[2] <= rect[0] or rect[3] <= rect[1]:
            return None
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if w <= 0 or h <= 0 or w > 8192 or h > 8192:
            return None
        import ctypes
        from PIL import Image

        hwnd = int(hwnd)
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        try:
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            try:
                save_dc = mfc_dc.CreateCompatibleDC()
                try:
                    bitmap = win32ui.CreateBitmap()
                    old_bitmap = None
                    try:
                        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
                        old_bitmap = save_dc.SelectObject(bitmap)
                        # PW_RENDERFULLCONTENT=2：渲染完整内容（含被遮挡部分）
                        rendered = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
                        if not rendered:
                            logger.warning('PrintWindow 返回失败 hwnd=%s', hwnd)
                            return None
                        bmpinfo = bitmap.GetInfo()
                        bmpstr = bitmap.GetBitmapBits(True)  # 32bpp BGRA
                        return Image.frombuffer(
                            'RGB',
                            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                            bmpstr, 'raw', 'BGRX', 0, 1)
                    finally:
                        # 连续逐帧录制会高频进入此路径；每帧都必须释放 GDI bitmap，
                        # 否则几千帧后会耗尽进程 GDI 对象并导致截图静默失效。
                        if old_bitmap is not None:
                            try:
                                save_dc.SelectObject(old_bitmap)
                            except Exception:
                                pass
                        try:
                            win32gui.DeleteObject(bitmap.GetHandle())
                        except Exception:
                            pass
                finally:
                    save_dc.DeleteDC()
            finally:
                mfc_dc.DeleteDC()
        finally:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
    except Exception as e:
        logger.warning('PrintWindow 窗口捕获失败 hwnd=%s: %s', hwnd, e)
        return None


def capture_window_with_info(hwnd, *, prefer_wgc=True, wgc_timeout_s=0.45):
    """Capture one window and report the real provider/capability tier.

    WGC is the preferred persistent GPU-backed path. PrintWindow remains a
    compatibility tier for standard Win32 controls; it is explicitly marked
    unverified because a successful API return can still contain stale pixels
    for GPU/custom-rendered applications.
    """
    started = time.perf_counter()
    errors = []
    if hwnd:
        try:
            import win32gui

            if not win32gui.IsWindow(int(hwnd)):
                try:
                    from core.services.wgc_capture import wgc_sessions

                    wgc_sessions.discard(int(hwnd))
                except Exception:
                    pass
                return None, {
                    'provider': 'none', 'capability': 'unsupported', 'verified': False,
                    'capture_duration_ms': round((time.perf_counter() - started) * 1000, 2),
                    'message': '目标窗口已关闭或句柄已失效',
                }
            if win32gui.IsIconic(int(hwnd)):
                return None, {
                    'provider': 'none', 'capability': 'foreground_required', 'verified': False,
                    'capture_duration_ms': round((time.perf_counter() - started) * 1000, 2),
                    'message': '目标窗口已最小化，禁止复用可能过期的后台帧；请先还原窗口',
                }
        except ImportError:
            pass
    if prefer_wgc and hwnd:
        try:
            from core.services.wgc_capture import WgcWindowSession, wgc_sessions

            available, detail = WgcWindowSession.available()
            if available:
                packet = wgc_sessions.get(int(hwnd)).latest(timeout_s=wgc_timeout_s)
                return packet.image.copy(), {
                    'provider': 'windows_graphics_capture',
                    'capability': 'background_fresh',
                    'verified': True,
                    'sequence': packet.sequence,
                    'frame_age_ms': round((time.monotonic_ns() - packet.captured_at_ns) / 1_000_000, 2),
                    'capture_duration_ms': round((time.perf_counter() - started) * 1000, 2),
                    'message': 'Windows Graphics Capture 后台帧',
                }
            errors.append(detail)
        except Exception as exc:
            errors.append(str(exc))

    image = _capture_window_printwindow(hwnd)
    if image is not None:
        return image, {
            'provider': 'print_window',
            'capability': 'background_unverified',
            'verified': False,
            'capture_duration_ms': round((time.perf_counter() - started) * 1000, 2),
            'message': 'PrintWindow 已返回画面，GPU/自绘窗口仍需视觉验证',
            'fallback_reasons': errors,
        }
    return None, {
        'provider': 'none',
        'capability': 'foreground_required',
        'verified': False,
        'capture_duration_ms': round((time.perf_counter() - started) * 1000, 2),
        'message': '后台捕获不可用，需要激活窗口后使用 DXGI 桌面捕获',
        'fallback_reasons': errors,
    }


def capture_window(hwnd):
    """Backward-compatible image-only window capture API."""
    image, _ = capture_window_with_info(hwnd)
    return image


def crop_window_image(hwnd, image, screen_box):
    """Map an absolute screen rectangle into a WGC/PrintWindow image safely.

    Providers may expose either extended-window or client-area pixels. The
    returned texture dimensions identify the correct origin and avoid DPI/title
    bar offsets leaking into workspace coordinates.
    """
    import win32gui

    left, top, right, bottom = [int(value) for value in screen_box]
    width, height = right - left, bottom - top
    outer_left, outer_top, outer_right, outer_bottom = win32gui.GetWindowRect(hwnd)
    client = win32gui.GetClientRect(hwnd)
    client_left, client_top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
    client_right, client_bottom = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
    origins = [
        (outer_left, outer_top, outer_right - outer_left, outer_bottom - outer_top),
        (client_left, client_top, client_right - client_left, client_bottom - client_top),
    ]
    origins.sort(key=lambda item: abs(item[2] - image.width) + abs(item[3] - image.height))
    origin_left, origin_top, _, _ = origins[0]
    crop = (left - origin_left, top - origin_top, right - origin_left, bottom - origin_top)
    if crop[0] < 0 or crop[1] < 0 or crop[2] > image.width or crop[3] > image.height:
        if image.size == (width, height):
            crop = (0, 0, width, height)
        else:
            raise ValueError(f'后台截图裁剪区超出窗口图像: {crop}, image={image.size}')
    return image.crop(crop).convert('RGB')
