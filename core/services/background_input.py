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
import time
from collections.abc import Callable

import win32con
import win32gui

logger = logging.getLogger(__name__)


def screen_to_client(hwnd, x: int, y: int):
    """屏幕坐标 → 窗口客户区坐标；失败（窗口已关闭等）返回 None"""
    try:
        return win32gui.ScreenToClient(hwnd, (int(x), int(y)))
    except Exception:
        return None


def is_foreground_window(hwnd) -> bool:
    """目标句柄是否属于当前前台顶层窗口。

    GetForegroundWindow 返回的是顶层窗口，而调用方有时传入客户区子句柄，
    因此需要把两者都归一到根窗口后再比较。
    """
    if not hwnd:
        return False
    try:
        foreground = win32gui.GetForegroundWindow()
        if not foreground:
            return False
        get_ancestor = getattr(win32gui, 'GetAncestor', None)
        if get_ancestor is None:
            return int(foreground) == int(hwnd)
        ga_root = getattr(win32con, 'GA_ROOT', 2)
        return int(get_ancestor(foreground, ga_root) or foreground) == int(get_ancestor(hwnd, ga_root) or hwnd)
    except Exception:
        return False


def _lparam(cx, cy):
    """lParam 低位 = x，高位 = y（客户区坐标；负数按 16 位无符号打包）"""
    return ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)


def _message_target_at_point(hwnd, screen_x: int, screen_y: int):
    """解析目标窗口内部最深子句柄，并返回该句柄客户区坐标。

    PostMessage 不会像真实鼠标那样自动把顶层窗口消息命中到渲染子窗口；
    因此必须在目标进程树内逐级命中，避免把消息只投给外壳窗口。
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return None
    target = int(hwnd)
    try:
        root_point = win32gui.ScreenToClient(target, (int(screen_x), int(screen_y)))
        client = win32gui.GetClientRect(target)
        if not (client[0] <= root_point[0] < client[2] and client[1] <= root_point[1] < client[3]):
            return None
        finder = getattr(win32gui, 'ChildWindowFromPointEx', None)
        if finder is not None:
            flags = (
                getattr(win32con, 'CWP_SKIPINVISIBLE', 0x0001)
                | getattr(win32con, 'CWP_SKIPDISABLED', 0x0002)
                | getattr(win32con, 'CWP_SKIPTRANSPARENT', 0x0004)
            )
            for _ in range(16):
                local = win32gui.ScreenToClient(target, (int(screen_x), int(screen_y)))
                child = finder(target, local, flags)
                if not child or int(child) == target:
                    break
                target = int(child)
        local = win32gui.ScreenToClient(target, (int(screen_x), int(screen_y)))
        return target, (int(local[0]), int(local[1]))
    except Exception:
        point = screen_to_client(hwnd, screen_x, screen_y)
        return (int(hwnd), point) if point is not None else None


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
    resolved = _message_target_at_point(hwnd, screen_x, screen_y)
    if resolved is None:
        return {'ok': False, 'method': 'background', 'message': '点击坐标不在目标窗口客户区内或目标已关闭'}
    target_hwnd, pt = resolved
    cx, cy = pt
    lparam = _lparam(cx, cy)
    button = str(button or 'left').lower()
    message_map = {
        'left': (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON),
        'right': (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.WM_RBUTTONDBLCLK, win32con.MK_RBUTTON),
        'middle': (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.WM_MBUTTONDBLCLK, win32con.MK_MBUTTON),
    }
    if button not in message_map:
        return {'ok': False, 'message': f'不支持的鼠标按键: {button}'}
    down_msg, up_msg, double_msg, down_wparam = message_map[button]
    try:
        count = max(1, int(clicks or 1))
        posted = True
        for _ in range(count):
            posted = _post(target_hwnd, win32con.WM_MOUSEMOVE, 0, lparam) and posted  # 移动消息前置
            posted = _post(target_hwnd, down_msg, down_wparam, lparam) and posted
            posted = _post(target_hwnd, up_msg, 0, lparam) and posted
            down_msg = double_msg  # 第二次按下使用对应按键的双击消息
        if not posted:
            return {'ok': False, 'method': 'background', 'message': '至少一条鼠标消息投递失败'}
        return {
            'ok': True,
            'method': 'background',
            'message': f'后台消息投递到窗口(#{target_hwnd}) 屏幕({screen_x},{screen_y}) -> 客户区({cx},{cy})',
        }
    except Exception as e:
        logger.warning('后台点击失败 hwnd=%s: %s', hwnd, e)
        return {'ok': False, 'message': f'后台点击失败: {e}'}


def dispatch_click(
    hwnd,
    screen_x: int,
    screen_y: int,
    *,
    button: str = 'left',
    clicks: int = 1,
    mode: str = 'background',
    allow_physical_fallback: bool = False,
) -> dict:
    """兼容入口：后台优先，只有显式授权时才允许物理输入。

    新节点应使用 ``input_dispatcher.click_workspace``。此函数保留给旧调用方，
    但 ``auto`` 已不再根据前台状态偷偷选择物理鼠标。
    """
    normalized = str(mode or 'auto').strip().lower()
    if normalized in {'foreground', 'physical', 'mouse'}:
        if not allow_physical_fallback:
            return {'ok': False, 'method': 'physical', 'delivery': 'blocked',
                    'message': '项目未授权物理输入'}
        use_physical = True
    elif normalized in {'auto', 'background', 'post_message', 'postmessage'}:
        use_physical = False
    else:
        return {'ok': False, 'message': f'不支持的点击投递模式: {mode}'}

    if not use_physical:
        result = background_click(hwnd, screen_x, screen_y, button=button, clicks=clicks)
        result.setdefault('delivery', 'delivered_unverified' if result.get('ok') else 'failed')
        result.setdefault('verified', False)
        if result.get('ok') or not allow_physical_fallback:
            return result
        # 只有后台后端明确报错时才允许回退；入队成功但效果未知时不重复点击。

    try:
        import pyautogui

        pyautogui.click(int(screen_x), int(screen_y), clicks=max(1, int(clicks or 1)), button=str(button or 'left'))
        return {
            'ok': True,
            'method': 'physical',
            'message': f'真实鼠标点击 屏幕({int(screen_x)},{int(screen_y)})',
        }
    except Exception as exc:
        return {'ok': False, 'method': 'physical', 'message': f'真实鼠标点击失败: {exc}'}


def background_double_click(hwnd, screen_x: int, screen_y: int) -> dict:
    """后台双击（第二次按下投递 WM_LBUTTONDBLCLK，触发真实双击语义）"""
    return background_click(hwnd, screen_x, screen_y, clicks=2)


def background_hover(hwnd, screen_x: int, screen_y: int) -> dict:
    """向目标窗口投递鼠标移动，不改变物理光标位置。"""
    if not hwnd:
        return {'ok': False, 'method': 'background', 'message': '缺少目标窗口句柄，无法后台悬停'}
    resolved = _message_target_at_point(hwnd, screen_x, screen_y)
    if resolved is None:
        return {'ok': False, 'method': 'background', 'message': '悬停坐标转客户区失败'}
    target_hwnd, point = resolved
    if not _post(target_hwnd, win32con.WM_MOUSEMOVE, 0, _lparam(point[0], point[1])):
        return {'ok': False, 'method': 'background', 'message': '鼠标移动消息投递失败'}
    return {
        'ok': True,
        'method': 'background',
        'delivery': 'delivered_unverified',
        'verified': False,
        'message': f'后台悬停投递到窗口(#{target_hwnd}) 屏幕({screen_x},{screen_y}) -> 客户区{point}，效果未验证',
    }


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
        if not _post(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam):
            return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '后台滚轮消息投递失败'}
        return {
            'ok': True,
            'method': 'background',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'后台滚轮窗口(#{hwnd}) 格数={ticks}，效果未验证',
        }
    except Exception as e:
        logger.warning('后台滚轮失败 hwnd=%s: %s', hwnd, e)
        return {'ok': False, 'message': f'后台滚轮失败: {e}'}


def background_drag(
    hwnd,
    start_screen: tuple[int, int],
    end_screen: tuple[int, int],
    *,
    button: str = 'left',
    duration_ms: int = 300,
    hold_before_ms: int = 0,
    hold_after_ms: int = 0,
    steps: int = 12,
    stop_check: Callable[[], bool] | None = None,
) -> dict:
    """向一个已绑定窗口投递完整的后台拖拽手势。

    消息始终发往按下时命中的子窗口，等价于真实鼠标的 capture
    语义，避免路径经过其他子控件时中途丢失。``hold_after_ms`` 在终点
    保持按下，可用于抑制触摸滚动的惯性。
    """
    if not hwnd:
        return {'ok': False, 'method': 'background', 'message': '缺少目标窗口句柄，无法后台拖拽'}
    start_x, start_y = (int(start_screen[0]), int(start_screen[1]))
    end_x, end_y = (int(end_screen[0]), int(end_screen[1]))
    resolved = _message_target_at_point(hwnd, start_x, start_y)
    if resolved is None:
        return {'ok': False, 'method': 'background', 'message': '拖拽起点不在目标窗口内或目标已关闭'}
    target_hwnd, start_client = resolved
    button = str(button or 'left').lower()
    message_map = {
        'left': (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON),
        'right': (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON),
        'middle': (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON),
    }
    if button not in message_map:
        return {'ok': False, 'method': 'background', 'message': f'不支持的鼠标按键: {button}'}
    down_msg, up_msg, down_mask = message_map[button]
    move_count = max(1, min(240, int(steps or 1)))
    duration_s = max(0, int(duration_ms or 0)) / 1000.0
    step_delay = duration_s / move_count if move_count else 0

    def interrupted() -> bool:
        return bool(stop_check and stop_check())

    def wait_interruptibly(milliseconds: int) -> bool:
        deadline = time.monotonic() + max(0, int(milliseconds or 0)) / 1000.0
        while time.monotonic() < deadline:
            if interrupted():
                return False
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        return not interrupted()

    posted = _post(target_hwnd, win32con.WM_MOUSEMOVE, 0, _lparam(*start_client))
    posted = _post(target_hwnd, down_msg, down_mask, _lparam(*start_client)) and posted
    if not posted:
        return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '拖拽按下消息投递失败'}
    try:
        if not wait_interruptibly(hold_before_ms):
            return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽在按下阶段被停止'}
        for index in range(1, move_count + 1):
            if interrupted():
                return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
            ratio = index / move_count
            screen_x = round(start_x + (end_x - start_x) * ratio)
            screen_y = round(start_y + (end_y - start_y) * ratio)
            try:
                client_x, client_y = win32gui.ScreenToClient(target_hwnd, (screen_x, screen_y))
            except Exception as exc:
                return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': f'拖拽途中目标失效: {exc}'}
            if not _post(target_hwnd, win32con.WM_MOUSEMOVE, down_mask, _lparam(client_x, client_y)):
                return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '拖拽移动消息投递失败'}
            if step_delay:
                time.sleep(step_delay)
        if not wait_interruptibly(hold_after_ms):
            return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽在终点保持阶段被停止'}
        return {
            'ok': True,
            'method': 'background',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'后台拖拽已投递到窗口(#{target_hwnd}) {start_screen} -> {end_screen}，效果未验证',
        }
    finally:
        try:
            final_client = win32gui.ScreenToClient(target_hwnd, (end_x, end_y))
            _post(target_hwnd, up_msg, 0, _lparam(*final_client))
        except Exception:
            pass


def background_drag_path(
    hwnd,
    path_points: list[dict],
    *,
    button: str = 'left',
    easing: str = 'linear',
    stop_check: Callable[[], bool] | None = None,
) -> dict:
    """连续按住鼠标沿多段路径移动；整条路径只按下和松开一次。"""
    if not hwnd:
        return {'ok': False, 'method': 'background', 'message': '缺少目标窗口句柄，无法后台拖拽'}
    if not isinstance(path_points, list) or not path_points:
        return {'ok': False, 'method': 'background', 'message': '拖拽路径为空'}
    normalized = []
    for index, item in enumerate(path_points[:32]):
        point = item.get('point') if isinstance(item, dict) else None
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return {'ok': False, 'method': 'background', 'message': f'拖拽路径第{index + 1}个点无效'}
        normalized.append({
            'point': (int(point[0]), int(point[1])),
            'move_ms': max(0, int(item.get('move_ms', 0) or 0)),
            'hold_ms': max(0, int(item.get('hold_ms', 0) or 0)),
        })
    start_x, start_y = normalized[0]['point']
    resolved = _message_target_at_point(hwnd, start_x, start_y)
    if resolved is None:
        return {'ok': False, 'method': 'background', 'message': '拖拽起点不在目标窗口内或目标已关闭'}
    target_hwnd, start_client = resolved
    button = str(button or 'left').lower()
    message_map = {
        'left': (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON),
        'right': (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON),
        'middle': (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON),
    }
    if button not in message_map:
        return {'ok': False, 'method': 'background', 'message': f'不支持的鼠标按键: {button}'}
    down_msg, up_msg, down_mask = message_map[button]

    def interrupted() -> bool:
        return bool(stop_check and stop_check())

    def wait_interruptibly(milliseconds: int) -> bool:
        deadline = time.monotonic() + max(0, milliseconds) / 1000.0
        while time.monotonic() < deadline:
            if interrupted():
                return False
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        return not interrupted()

    def curve(value: float) -> float:
        if easing == 'ease_in_out':
            return value * value * (3 - 2 * value)
        return value

    posted = _post(target_hwnd, win32con.WM_MOUSEMOVE, 0, _lparam(*start_client))
    posted = _post(target_hwnd, down_msg, down_mask, _lparam(*start_client)) and posted
    if not posted:
        return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '拖拽按下消息投递失败'}
    final_point = normalized[-1]['point']
    try:
        if not wait_interruptibly(normalized[0]['hold_ms']):
            return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽在起点保持阶段被停止'}
        previous = normalized[0]['point']
        for segment in normalized[1:]:
            target = segment['point']
            move_ms = segment['move_ms']
            count = max(1, min(240, round(max(16, move_ms) / 16)))
            delay = move_ms / 1000.0 / count if move_ms else 0
            for index in range(1, count + 1):
                if interrupted():
                    return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
                ratio = curve(index / count)
                screen_x = round(previous[0] + (target[0] - previous[0]) * ratio)
                screen_y = round(previous[1] + (target[1] - previous[1]) * ratio)
                try:
                    client_x, client_y = win32gui.ScreenToClient(target_hwnd, (screen_x, screen_y))
                except Exception as exc:
                    return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': f'拖拽途中目标失效: {exc}'}
                if not _post(target_hwnd, win32con.WM_MOUSEMOVE, down_mask, _lparam(client_x, client_y)):
                    return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '拖拽移动消息投递失败'}
                if delay:
                    time.sleep(delay)
            if not wait_interruptibly(segment['hold_ms']):
                return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '拖拽在途径点保持阶段被停止'}
            previous = target
        return {
            'ok': True,
            'method': 'background',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'后台拖拽已连续投递 {len(normalized)} 个路径点，效果未验证',
        }
    finally:
        try:
            final_client = win32gui.ScreenToClient(target_hwnd, final_point)
            _post(target_hwnd, up_msg, 0, _lparam(*final_client))
        except Exception:
            pass


def background_text(
    hwnd,
    text: str,
    *,
    screen_point: tuple[int, int] | None = None,
    clear_before: bool = False,
    interval_ms: int = 0,
    submit_key: str = 'none',
    stop_check: Callable[[], bool] | None = None,
) -> dict:
    """使用定向 Win32 消息输入 Unicode 文本，不占用物理键盘。

    这是投递型后端；自绘/DirectX 窗口可能不接受 WM_CHAR，调用方
    必须将结果保持为 ``delivered_unverified`` 而不得伪报界面已改变。
    """
    if not hwnd:
        return {'ok': False, 'method': 'background', 'message': '缺少目标窗口句柄，无法后台输入'}
    target_hwnd = int(hwnd)
    if screen_point is not None:
        resolved = _message_target_at_point(hwnd, int(screen_point[0]), int(screen_point[1]))
        if resolved is None:
            return {'ok': False, 'method': 'background', 'message': '文本输入位置不在目标窗口内'}
        target_hwnd = int(resolved[0])
    if not win32gui.IsWindow(target_hwnd):
        return {'ok': False, 'method': 'background', 'message': '文本输入目标窗口已失效'}

    try:
        _post(target_hwnd, win32con.WM_SETFOCUS, 0, 0)
        if clear_before:
            _post(target_hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
            _post(target_hwnd, win32con.WM_KEYDOWN, ord('A'), 0)
            _post(target_hwnd, win32con.WM_KEYUP, ord('A'), 0)
            _post(target_hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
            _post(target_hwnd, win32con.WM_KEYDOWN, win32con.VK_BACK, 0)
            _post(target_hwnd, win32con.WM_KEYUP, win32con.VK_BACK, 0)
        delay = max(0, min(1000, int(interval_ms or 0))) / 1000.0
        for char in str(text or ''):
            if stop_check and stop_check():
                return {'ok': False, 'method': 'background', 'delivery': 'cancelled', 'message': '文本输入已被停止'}
            if not _post(target_hwnd, win32con.WM_CHAR, ord(char), 0):
                return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': '文本字符投递失败'}
            if delay:
                time.sleep(delay)
        key_map = {'enter': win32con.VK_RETURN, 'tab': win32con.VK_TAB, 'escape': win32con.VK_ESCAPE}
        submit = str(submit_key or 'none').lower()
        if submit in key_map:
            _post(target_hwnd, win32con.WM_KEYDOWN, key_map[submit], 0)
            _post(target_hwnd, win32con.WM_KEYUP, key_map[submit], 0)
        return {
            'ok': True,
            'method': 'background',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'后台文本已投递到窗口(#{target_hwnd})，长度={len(str(text or ""))}，效果未验证',
        }
    except Exception as exc:
        logger.warning('后台文本输入失败 hwnd=%s: %s', target_hwnd, exc)
        return {'ok': False, 'method': 'background', 'delivery': 'failed', 'message': f'后台文本输入失败: {exc}'}


def send_key_input(*key_codes, key_up=True, allow_physical_input=False):
    """SendInput 键盘注入（物理键盘事件，兼容需要真实输入的控件）。

    :param key_codes: 虚拟键码序列（可配合修饰键 VK_CONTROL/VK_SHIFT 等）
    :param key_up: 是否在按下后发送抬起（组合键场景可先全部按下再统一抬起）
    """
    if not allow_physical_input:
        return {
            'ok': False,
            'method': 'physical',
            'delivery': 'blocked',
            'message': '项目未显式授权物理键盘输入',
        }

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
