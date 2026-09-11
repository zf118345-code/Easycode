# tests/test_background_click.py
# 点击分发测试：严格后台优先、模拟器强制 ADB、物理回退必须项目授权。
import threading

class FakeCtx:
    """模拟 set_window 之后的执行上下文"""

    def __init__(self, variables=None, window_hwnd=1001):
        self.variables = variables or {}
        self.logs = []
        self.window_hwnd = window_hwnd
        self.window_rect = (10, 20, 310, 220)

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)

    def is_window_mode(self):
        return True

    def get_window_rect(self):
        return self.window_rect

    def get_setting(self, key, default=None):
        return self.variables.get(key, default)

    @property
    def is_emulator(self):
        return False

    @property
    def device_id(self):
        return None


def make_node(node_type, params):
    from core.models import Node

    return Node(node_id='n', node_name='n', node_type=node_type, params=params)


# ========== 1. click 节点 ==========

def test_click_uses_unified_workspace_dispatch(monkeypatch):
    """点击节点只把工作区坐标交给统一输入路由。"""
    import core.node_executors.base.click as click_mod

    dispatch_calls = []
    monkeypatch.setattr(click_mod, 'click_workspace', lambda ctx, x, y, **kwargs:
                        dispatch_calls.append((ctx.window_hwnd, x, y, kwargs))
                        or {'ok': True, 'method': 'background', 'message': 'ok', 'workspace_point': [x, y]})

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=1001)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)

    assert result['success'] is True
    assert dispatch_calls[0][0:3] == (1001, 100, 50)
    assert dispatch_calls[0][3]['requested_mode'] == 'background'


def test_click_desktop_strict_mode_fails_without_silent_physical_fallback(monkeypatch):
    """全桌面模式没有后台后端时明确失败，不偷偷移动鼠标。"""
    import core.node_executors.base.click as click_mod

    monkeypatch.setattr(click_mod, 'click_workspace', lambda *args, **kwargs:
                        {'ok': False, 'method': 'background', 'message': '未绑定窗口'})

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=None)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)

    assert result['success'] is False


def test_click_background_failure_fails_node(monkeypatch):
    """后台点击失败（窗口句柄失效等）→ 节点失败"""
    import core.node_executors.base.click as click_mod

    monkeypatch.setattr(click_mod, 'click_workspace',
                        lambda *a, **k: {'ok': False, 'method': 'background', 'message': '后台点击失败'})

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=1001)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)
    assert result['success'] is False


# ========== 2. 多开并发 ==========

def test_concurrent_sessions_no_physical_mouse(monkeypatch):
    """多开并发：两个会话同时点击各自窗口，物理鼠标零占用、后台互不干扰"""
    import core.node_executors.base.click as click_mod

    dispatch_calls = []
    monkeypatch.setattr(click_mod, 'click_workspace', lambda ctx, x, y, **kwargs:
                        dispatch_calls.append((ctx.window_hwnd, x, y, kwargs.get('requested_mode')))
                        or {'ok': True, 'method': 'background', 'message': 'ok', 'workspace_point': [x, y]})

    from core.node_executors.base.click import ClickNodeExecutor

    results = []

    def run_session(hwnd, pos):
        ctx = FakeCtx(window_hwnd=hwnd)
        r = ClickNodeExecutor().execute(make_node('click', {'position': pos}), ctx)
        results.append((hwnd, r['success']))

    threads = [
        threading.Thread(target=run_session, args=(2001, [50, 60])),
        threading.Thread(target=run_session, args=(2002, [70, 80])),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert all(ok for _, ok in results)
    assert len(dispatch_calls) == 2
    assert {c[0] for c in dispatch_calls} == {2001, 2002}  # 各自绑定窗口


def test_auto_dispatch_never_uses_physical_mouse_for_foreground_window(monkeypatch):
    """目标在前台也仍走后台；前台状态不再触发隐式物理点击。"""
    import pyautogui
    import core.services.background_input as bg

    physical_calls = []
    monkeypatch.setattr(bg, 'background_click', lambda *a, **k:
                        {'ok': True, 'method': 'background', 'message': 'queued'})
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: physical_calls.append((a, k)))

    result = bg.dispatch_click(1001, 757, 809, mode='auto')

    assert result['ok'] is True
    assert result['method'] == 'background'
    assert result['delivery'] == 'delivered_unverified'
    assert physical_calls == []


# ========== 3. 后台输入服务 ==========

def test_background_input_service_coords(monkeypatch):
    """后台点击服务：屏幕坐标 → 客户区坐标打包 lParam，消息序列 down+up"""
    import win32con
    import core.services.background_input as bg

    posts = []
    sleeps = []
    monkeypatch.setattr(bg, '_message_target_at_point', lambda h, x, y: (h, (5, 6)))
    monkeypatch.setattr(bg, '_send_mouse_message', lambda h, m, w, l: posts.append((h, m, w, l)) or True)
    monkeypatch.setattr(bg.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = bg.background_click(42, 100, 100)
    assert result['ok'] is True
    assert len(posts) == 3  # MOVE + DOWN + UP（#10：移动消息前置，自绘控件才响应）
    h, m, w, l = posts[0]
    assert h == 42
    assert m == win32con.WM_MOUSEMOVE  # ⚡ 先投递移动消息
    assert posts[1][1] == win32con.WM_LBUTTONDOWN
    assert posts[1][2] == win32con.MK_LBUTTON
    assert posts[1][3] == (6 << 16) | 5  # 客户区 (5,6)：低位 x，高位 y
    assert posts[2][1] == win32con.WM_LBUTTONUP
    assert posts[2][3] == (6 << 16) | 5
    assert sleeps == [bg._DEFAULT_CLICK_PRESS_SECONDS]


def test_background_double_click_sends_two_pairs(monkeypatch):
    import win32con
    import core.services.background_input as bg

    posts = []
    sleeps = []
    monkeypatch.setattr(bg, '_message_target_at_point', lambda h, x, y: (h, (0, 0)))
    monkeypatch.setattr(bg, '_send_mouse_message', lambda h, m, w, l: posts.append(m) or True)
    monkeypatch.setattr(bg.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = bg.background_double_click(9, 10, 10)
    assert result['ok'] is True
    assert len(posts) == 6  # (MOVE+down+up) × 2
    assert posts[0] == win32con.WM_MOUSEMOVE
    assert posts[1] == win32con.WM_LBUTTONDOWN
    assert posts[2] == win32con.WM_LBUTTONUP
    assert posts[3] == win32con.WM_MOUSEMOVE
    assert posts[4] == win32con.WM_LBUTTONDBLCLK  # ⚡ 第二次按下用 DBLCK（真双击语义）
    assert posts[5] == win32con.WM_LBUTTONUP
    assert sleeps == [bg._DEFAULT_CLICK_PRESS_SECONDS, bg._DEFAULT_CLICK_PRESS_SECONDS]


def test_background_input_no_hwnd_fails():
    import core.services.background_input as bg

    result = bg.background_click(None, 10, 10)
    assert result['ok'] is False
    assert '窗口句柄' in result['message']


def test_background_horizontal_scroll_uses_mouse_hwheel(monkeypatch):
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg, '_message_target_at_point', lambda *_args: (52, (8, 9)))
    monkeypatch.setattr(
        bg,
        '_send_mouse_message',
        lambda hwnd, message, wparam, lparam: posts.append(
            (hwnd, message, wparam, lparam)
        ) or True,
    )

    result = bg.background_scroll(42, 100, 200, -3, horizontal=True)

    assert result['ok'] is True
    assert posts[0][0] == 52
    assert posts[0][1] == getattr(bg.win32con, 'WM_MOUSEHWHEEL', 0x020E)
    assert posts[0][2] == (((-3 * bg.win32con.WHEEL_DELTA) & 0xFFFF) << 16)
    assert '水平' in result['message']


def test_background_drag_uses_bounded_targeted_messages(monkeypatch):
    import core.services.background_input as bg

    messages = []
    monkeypatch.setattr(bg, '_message_target_at_point', lambda *_args: (52, (1, 2)))
    monkeypatch.setattr(bg.win32gui, 'ScreenToClient', lambda _hwnd, point: point)
    monkeypatch.setattr(
        bg,
        '_send_mouse_message',
        lambda hwnd, message, wparam, lparam: messages.append((hwnd, message, wparam, lparam)) or True,
    )

    result = bg.background_drag(42, (10, 20), (30, 40), duration_ms=0, steps=2)

    assert result['ok'] is True
    assert result['delivery'] == 'delivered_unverified'
    assert all(item[0] == 52 for item in messages)
    assert messages[0][1] == bg.win32con.WM_MOUSEMOVE
    assert messages[1][1] == bg.win32con.WM_LBUTTONDOWN
    assert messages[-1][1] == bg.win32con.WM_LBUTTONUP


# ========== 4. 控件节点 / 图像识别点击 ==========

def test_control_node_click_uses_background(monkeypatch):
    """控件节点点击：直接向控件窗口后台投递，不移动物理鼠标"""
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg, '_message_target_at_point', lambda h, x, y: (h, (3, 4)))
    monkeypatch.setattr(bg, '_send_mouse_message', lambda h, m, w, l: posts.append((h, m, w, l)) or True)

    from core.services.control_service import perform_action

    info = {'hwnd': 77, 'rect': [10, 10, 110, 40]}  # 控件中心 (60, 25)
    result = perform_action(info, 'click')
    assert result['ok'] is True
    assert len(posts) == 3  # MOVE + DOWN + UP
    assert posts[0][0] == 77


def test_control_click_physical_fallback_is_explicit(monkeypatch):
    """控件后台投递失败时，只有项目显式授权才可回退物理鼠标。"""
    import pyautogui
    import core.services.background_input as bg
    from core.services.control_service import perform_action

    monkeypatch.setattr(bg, 'background_click', lambda *a, **k:
                        {'ok': False, 'method': 'background', 'message': 'unsupported'})
    physical = []
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: physical.append((a, k)))
    info = {'hwnd': 77, 'rect': [10, 10, 110, 40]}

    blocked = perform_action(info, 'click')
    assert blocked['ok'] is False
    assert blocked['delivery'] == 'blocked'
    assert physical == []

    allowed = perform_action(info, 'click', allow_physical_fallback=True)
    assert allowed['ok'] is True
    assert allowed['method'] == 'physical'
    assert len(physical) == 1


def test_unified_dispatch_reports_background_delivery_unverified(monkeypatch):
    """PostMessage 入队只报告 delivered_unverified，不伪装效果已验证。"""
    import core.services.input_dispatcher as dispatcher

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *a, **k: (50, 60, 500, 400))
    monkeypatch.setattr(dispatcher, 'background_click', lambda *a, **k:
                        {'ok': True, 'method': 'background', 'message': 'queued'})
    result = dispatcher.click_workspace(FakeCtx(window_hwnd=3001), 50, 60)
    assert result['ok'] is True
    assert result['delivery'] == 'delivered_unverified'
    assert result['verified'] is False


def test_desktop_physical_fallback_defaults_off_and_requires_project_switch(monkeypatch):
    """物理兜底默认关闭；只有项目显式授权后才允许真实鼠标输入。"""
    import pyautogui
    import core.services.input_dispatcher as dispatcher

    phys = []
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: phys.append(a))

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *a, **k: (50, 60, 500, 400))
    blocked = dispatcher.click_workspace(FakeCtx(window_hwnd=None), 50, 60)
    assert blocked['ok'] is False
    assert len(phys) == 0

    allowed = dispatcher.click_workspace(
        FakeCtx({'allow_physical_fallback': True}, window_hwnd=None), 50, 60,
    )
    assert allowed['ok'] is True
    assert allowed['method'] == 'physical'
    assert len(phys) == 1


# ========== #1 统一截图服务 ==========

def test_screenshot_service_falls_back_to_pyautogui(monkeypatch):
    """dxcam 不可用时回退 pyautogui（Pillow GDI），返回 PIL Image"""
    from core.services import screenshot_service as ss

    class FakeImg:
        size = 100
        def __init__(self):
            pass

    monkeypatch.setattr(ss, '_get_dxcam', lambda: None)
    calls = []
    import pyautogui as real_pyautogui

    def fake_shot(region=None):
        calls.append(region)
        return FakeImg()
    monkeypatch.setattr(real_pyautogui, 'screenshot', fake_shot)

    img = ss.capture()
    assert img is not None
    assert calls == [None]

    ss.capture(region=(10, 20, 110, 70))
    assert calls[-1] == (10, 20, 100, 50)  # 转成 (left, top, w, h)


def test_screenshot_service_dxcam_region(monkeypatch):
    """dxcam 可用：区域抓取直达（不再全屏抓取后裁剪）"""
    import numpy as np
    from core.services import screenshot_service as ss

    class FakeCam:
        def __init__(self):
            self.regions = []

        def grab(self, region=None):
            self.regions.append(region)
            return np.zeros((50, 100, 3), dtype=np.uint8)

    cam = FakeCam()
    monkeypatch.setattr(ss, '_get_dxcam', lambda: cam)

    img = ss.capture(region=(10, 20, 110, 70))
    assert img is not None
    assert cam.regions == [(10, 20, 110, 70)]  # 直接区域抓取
    assert img.size[0] == 100 and img.size[1] == 50


def test_screenshot_service_dxcam_failure_falls_back(monkeypatch):
    """dxcam 抓取失败（返回 None）→ 回退 pyautogui"""
    from core.services import screenshot_service as ss

    class FakeCam:
        def grab(self, region=None):
            return None

    monkeypatch.setattr(ss, '_get_dxcam', lambda: FakeCam())
    import pyautogui as real_pyautogui

    class FakeImg:
        size = 10
    monkeypatch.setattr(real_pyautogui, 'screenshot', lambda region=None: FakeImg())

    img = ss.capture()
    assert img is not None


def test_screenshot_service_oob_region_falls_back_fullscreen(monkeypatch):
    """region 完全越出屏幕（窗口被移到屏幕外/最小化）→ 回退全屏，不再返回 None 导致调用方 500"""
    import numpy as np
    from core.services import screenshot_service as ss

    class FakeCam:
        def __init__(self):
            self.regions = []

        def grab(self, region=None):
            self.regions.append(region)
            return np.zeros((10, 10, 3), dtype=np.uint8)

    cam = FakeCam()
    monkeypatch.setattr(ss, '_get_dxcam', lambda: cam)

    img = ss.capture(region=(-50000, -50000, -40000, -40000))
    assert img is not None
    assert cam.regions[-1] is None  # 已回退为全屏抓取
