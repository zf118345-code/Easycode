# core/services/screenshot_service.py
# ⚡ 统一截图服务（#1 技术债修复）：DXGI 前台捕获（dxcam，毫秒级）+ PrintWindow 后台窗口捕获
# 优先级：dxcam（区域/全屏，快 10-100 倍）→ pyautogui（Pillow GDI 兜底）
# 返回 PIL Image（与既有调用方 pyautogui.screenshot 的返回类型一致）
import logging
import threading

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


def capture_window(hwnd):
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
                    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
                    save_dc.SelectObject(bitmap)
                    # PW_RENDERFULLCONTENT=2：渲染完整内容（含被遮挡部分）
                    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
                    bmpinfo = bitmap.GetInfo()
                    bmpstr = bitmap.GetBitmapBits(True)  # 32bpp BGRA
                    return Image.frombuffer(
                        'RGB',
                        (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                        bmpstr, 'raw', 'BGRX', 0, 1)
                finally:
                    save_dc.DeleteDC()
            finally:
                mfc_dc.DeleteDC()
        finally:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
    except Exception as e:
        logger.warning('PrintWindow 窗口捕获失败 hwnd=%s: %s', hwnd, e)
        return None
