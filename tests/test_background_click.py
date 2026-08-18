# tests/test_background_click.py
# 多开/后台点击测试：所有 PC 点击优先向绑定窗口后台投递（PostMessage），
# 不占用物理鼠标；仅全桌面模式（无窗口句柄）回退物理点击。
import threading

import pytest


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

def test_click_background_when_window_bound(monkeypatch):
    """绑定窗口：点击走后台投递（窗口偏移 + 相对坐标），物理鼠标零调用"""
    import pyautogui
    import core.node_executors.base.click as click_mod

    bg_calls, phys_calls = [], []
    monkeypatch.setattr(
        click_mod, 'background_click',
        lambda hwnd, x, y, button='left', clicks=1: bg_calls.append((hwnd, x, y, clicks)) or {'ok': True, 'message': 'ok'})
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: phys_calls.append(a))

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=1001)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)

    assert result['success'] is True
    assert bg_calls == [(1001, 110, 70, 1)]  # 窗口偏移 (10,20) + 相对 (100,50)
    assert phys_calls == []


def test_click_falls_back_physical_in_desktop_mode(monkeypatch):
    """全桌面模式（无窗口句柄）：回退物理鼠标点击"""
    import pyautogui
    import core.node_executors.base.click as click_mod

    phys_calls = []
    monkeypatch.setattr(
        click_mod, 'background_click',
        lambda *a, **k: pytest.fail('桌面模式不应调用后台点击'))
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: phys_calls.append(a))

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=None)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)

    assert result['success'] is True
    assert len(phys_calls) == 1


def test_click_background_failure_fails_node(monkeypatch):
    """后台点击失败（窗口句柄失效等）→ 节点失败"""
    import core.node_executors.base.click as click_mod

    monkeypatch.setattr(
        click_mod, 'background_click',
        lambda *a, **k: {'ok': False, 'message': '后台点击失败'})

    from core.node_executors.base.click import ClickNodeExecutor

    ctx = FakeCtx(window_hwnd=1001)
    result = ClickNodeExecutor().execute(make_node('click', {'position': [100, 50]}), ctx)
    assert result['success'] is False


# ========== 2. 多开并发 ==========

def test_concurrent_sessions_no_physical_mouse(monkeypatch):
    """多开并发：两个会话同时点击各自窗口，物理鼠标零占用、后台互不干扰"""
    import pyautogui
    import core.node_executors.base.click as click_mod

    bg_calls, phys_calls = [], []
    monkeypatch.setattr(
        click_mod, 'background_click',
        lambda hwnd, x, y, button='left', clicks=1: bg_calls.append((hwnd, x, y)) or {'ok': True, 'message': 'ok'})
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: phys_calls.append(a))

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
    assert len(bg_calls) == 2
    assert {c[0] for c in bg_calls} == {2001, 2002}  # 各自绑定窗口
    assert phys_calls == []  # 物理鼠标零占用


# ========== 3. 后台输入服务 ==========

def test_background_input_service_coords(monkeypatch):
    """后台点击服务：屏幕坐标 → 客户区坐标打包 lParam，消息序列 down+up"""
    import win32con
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg.win32gui, 'ScreenToClient', lambda h, pt: (5, 6))
    monkeypatch.setattr(bg.win32gui, 'PostMessage', lambda h, m, w, l: posts.append((h, m, w, l)))

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


def test_background_double_click_sends_two_pairs(monkeypatch):
    import win32con
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg.win32gui, 'ScreenToClient', lambda h, pt: (0, 0))
    monkeypatch.setattr(bg.win32gui, 'PostMessage', lambda h, m, w, l: posts.append(m))

    result = bg.background_double_click(9, 10, 10)
    assert result['ok'] is True
    assert len(posts) == 6  # (MOVE+down+up) × 2
    assert posts[0] == win32con.WM_MOUSEMOVE
    assert posts[1] == win32con.WM_LBUTTONDOWN
    assert posts[2] == win32con.WM_LBUTTONUP
    assert posts[3] == win32con.WM_MOUSEMOVE
    assert posts[4] == win32con.WM_LBUTTONDBLCLK  # ⚡ 第二次按下用 DBLCK（真双击语义）
    assert posts[5] == win32con.WM_LBUTTONUP


def test_background_input_no_hwnd_fails():
    import core.services.background_input as bg

    result = bg.background_click(None, 10, 10)
    assert result['ok'] is False
    assert '窗口句柄' in result['message']


# ========== 4. 控件节点 / 图像识别点击 ==========

def test_control_node_click_uses_background(monkeypatch):
    """控件节点点击：直接向控件窗口后台投递，不移动物理鼠标"""
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg.win32gui, 'ScreenToClient', lambda h, pt: (3, 4))
    monkeypatch.setattr(bg.win32gui, 'PostMessage', lambda h, m, w, l: posts.append((h, m, w, l)))

    from core.services.control_service import perform_action

    info = {'hwnd': 77, 'rect': [10, 10, 110, 40]}  # 控件中心 (60, 25)
    result = perform_action(info, 'click')
    assert result['ok'] is True
    assert len(posts) == 3  # MOVE + DOWN + UP
    assert posts[0][0] == 77


def test_image_recognition_click_center_background(monkeypatch):
    """图像识别成功点击中心：绑定窗口时后台投递"""
    import core.services.background_input as bg

    posts = []
    monkeypatch.setattr(bg.win32gui, 'ScreenToClient', lambda h, pt: (0, 0))
    monkeypatch.setattr(bg.win32gui, 'PostMessage', lambda h, m, w, l: posts.append((h, m, w, l)))

    from core.node_executors.base.image_recognition import ImageRecognitionNodeExecutor

    ctx = FakeCtx(window_hwnd=3001)
    ImageRecognitionNodeExecutor._pc_click(500, 400, ctx)
    assert len(posts) == 3  # MOVE + DOWN + UP
    assert posts[0][0] == 3001
    assert any('后台点击' in log for log in ctx.logs)


def test_image_recognition_desktop_falls_back_physical(monkeypatch):
    """图像识别全桌面模式：物理点击回退"""
    import pyautogui
    import core.services.background_input as bg

    phys = []
    monkeypatch.setattr(pyautogui, 'click', lambda *a, **k: phys.append(a))

    from core.node_executors.base.image_recognition import ImageRecognitionNodeExecutor

    ctx = FakeCtx(window_hwnd=None)
    ImageRecognitionNodeExecutor._pc_click(500, 400, ctx)
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

    img2 = ss.capture(region=(10, 20, 110, 70))
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
