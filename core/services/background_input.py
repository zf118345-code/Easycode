# core/services/background_input.py
# ⚡ 后台输入服务：不抢占物理鼠标/键盘的多开友好输入
# 原理：将屏幕坐标换算为目标窗口客户区坐标后，直接向窗口消息队列投递
#       WM_MOUSEMOVE → WM_LBUTTONDOWN → WM_LBUTTONUP（PostMessage 异步），
#       全程不移动物理鼠标、不占用光标，多个窗口会话可并行互不干扰。
# ⚡ 可靠性要点（成熟方案）：
#   - 先发 WM_MOUSEMOVE：部分自绘/WebView 控件要求先收到移动消息才响应点击
#   - 双击第二次按下用 WM_LBUTTONDBLCLK：依赖双击语义的控件（列表展开/桌面图标）才触发
#   - 后台滚轮 WM_MOUSEWHEEL：delta 按格（WHEEL_DELTA=120）投递
#   - SendInput 键盘：物理键盘注入（真实按键事件，兼容需要真实输入的场景）
import logging

import win32con
import win32gui

logger = logging.getLogger(__name__)


def screen_to_client(hwnd, x: int, y: int):
    """屏幕坐标 → 窗口客户区坐标；失败（窗口已关闭等）返回 None"""
    try:
        return win32gui.ScreenToClient(hwnd, (int(x), int(y)))
    except Exception:
        return None


def _lparam(cx, cy):
    """lParam 低位 = x，高位 = y（客户区坐标；负数按 16 位无符号打包）"""
    return ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)


def _post(hwnd, msg, wparam, lparam):
    try:
        win32gui.PostMessage(hwnd, msg, wparam, lparam)
        return True
    except Exception as e:
        logger.warning('PostMessage(%s) 失败 hwnd=%s: %s', msg, hwnd, e)
        return False


def background_click(hwnd, screen_x: int, screen_y: int, button: str = 'left', clicks: int = 1) -> dict:
    """向指定窗口投递后台点击（默认左键，clicks=2 即双击），不移动物理鼠标。

    ⚡ 点击序列：WM_MOUSEMOVE → WM_LBUTTONDOWN → WM_LBUTTONUP（自绘/WebView 控件
    要求先收到移动消息才响应点击，直接 DOWN/UP 会被忽略）；
    双击时第二次按下使用 WM_LBUTTONDBLCLK（依赖双击语义的控件才触发）。

    :param hwnd: 目标窗口句柄（set_window 设置的 context.window_hwnd，或控件句柄）
    :param screen_x/screen_y: 屏幕绝对坐标
    :return: {'ok': bool, 'message': str}
    """
    if not hwnd:
        return {'ok': False, 'message': '缺少目标窗口句柄，无法后台点击（请先使用「窗口设置」绑定窗口）'}
    pt = screen_to_client(hwnd, screen_x, screen_y)
    if pt is None:
        return {'ok': False, 'message': '屏幕坐标转客户区失败，目标窗口可能已关闭'}
    cx, cy = pt
    lparam = _lparam(cx, cy)
    try:
        count = max(1, int(clicks or 1))
        down_msg = win32con.WM_LBUTTONDOWN
        for i in range(count):
            _post(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)  # ⚡ 移动消息前置
            _post(hwnd, down_msg, win32con.MK_LBUTTON, lparam)
            _post(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            down_msg = win32con.WM_LBUTTONDBLCLK  # ⚡ 第二次按下用 DBLCK（真双击语义）
        return {'ok': True, 'message': f'后台点击窗口(#{hwnd}) 屏幕({screen_x},{screen_y}) -> 客户区({cx},{cy})'}
    except Exception as e:
        logger.warning('后台点击失败 hwnd=%s: %s', hwnd, e)
        return {'ok': False, 'message': f'后台点击失败: {e}'}


def background_double_click(hwnd, screen_x: int, screen_y: int) -> dict:
    """后台双击（第二次按下投递 WM_LBUTTONDBLCLK，触发真实双击语义）"""
    return background_click(hwnd, screen_x, screen_y, clicks=2)


def background_scroll(hwnd, screen_x: int, screen_y: int, delta_ticks: int = 1) -> dict:
    """向指定窗口投递后台滚轮（WM_MOUSEWHEEL），不移动物理鼠标。

    :param delta_ticks: 滚动格数（正=向上，负=向下；每格 = WHEEL_DELTA 120）
    """
    if not hwnd:
        return {'ok': False, 'message': '缺少目标窗口句柄，无法后台滚轮'}
    pt = screen_to_client(hwnd, screen_x, screen_y)
    if pt is None:
        return {'ok': False, 'message': '屏幕坐标转客户区失败，目标窗口可能已关闭'}
    ticks = max(-100, min(100, int(delta_ticks or 0)))
    if ticks == 0:
        return {'ok': True, 'message': '滚动格数为 0，跳过'}
    delta = ticks * win32con.WHEEL_DELTA
    # WM_MOUSEWHEEL：wParam 高位 = delta（有符号），lParam = 屏幕坐标
    wparam = (delta & 0xFFFF) << 16
    lparam = _lparam(int(screen_x), int(screen_y))
    try:
        _post(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
        return {'ok': True, 'message': f'后台滚轮窗口(#{hwnd}) 格数={ticks}'}
    except Exception as e:
        logger.warning('后台滚轮失败 hwnd=%s: %s', hwnd, e)
        return {'ok': False, 'message': f'后台滚轮失败: {e}'}


def send_key_input(*key_codes, key_up=True):
    """SendInput 键盘注入（物理键盘事件，兼容需要真实输入的控件）。

    :param key_codes: 虚拟键码序列（可配合修饰键 VK_CONTROL/VK_SHIFT 等）
    :param key_up: 是否在按下后发送抬起（组合键场景可先全部按下再统一抬起）
    """
    import win32api

    try:
        for code in key_codes:
            win32api.keybd_event(int(code), 0, 0, 0)
        if key_up:
            for code in reversed(key_codes):
                win32api.keybd_event(int(code), 0, win32con.KEYEVENTF_KEYUP, 0)
        return {'ok': True, 'message': f'SendInput 键盘注入: {list(key_codes)}'}
    except Exception as e:
        logger.warning('键盘注入失败: %s', e)
        return {'ok': False, 'message': f'键盘注入失败: {e}'}
