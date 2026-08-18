# tests/test_capture_mode.py
# 控件捕获模式（零模态零钩子）：纯函数 + 悬停监控 + 事件队列 + 三热键 + 复制生成 + 快捷键配置
import threading
import time

import pytest
import win32con

from core.services import capture_mode


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    """复位全局状态；测试绝不触碰真实 settings.json"""
    capture_mode._last_result = None
    capture_mode._selected = None
    capture_mode._active = False
    capture_mode._hotkeys_cache = None
    capture_mode._event_deque.clear()
    capture_mode._event_running = False
    capture_mode._event_subscribers.clear()
    capture_mode._hover_stop = None
    capture_mode._cancel_auto_exit()
    capture_mode._hotkey_window = None
    capture_mode._hotkey_started = False
    # 配置读写隔离到临时目录
    monkeypatch.setattr(capture_mode, '_settings_path', lambda: str(tmp_path / 'settings.json'))
    # 兜底：高亮不创建真实窗口
    monkeypatch.setattr('core.services.highlight_service.highlight_service.render', lambda *a, **k: None)
    yield
    capture_mode._active = False
    capture_mode._selected = None
    capture_mode._last_result = None
    capture_mode._hotkeys_cache = None
    capture_mode._event_deque.clear()
    capture_mode._event_running = False
    capture_mode._event_subscribers.clear()
    capture_mode._hover_stop = None
    capture_mode._cancel_auto_exit()
    capture_mode._hotkey_window = None
    capture_mode._hotkey_started = False


def _wait_events_idle():
    """等待事件队列串行 worker 处理完毕"""
    deadline = time.time() + 3
    while capture_mode._event_running and time.time() < deadline:
        time.sleep(0.01)


# ========== 选择器 / 参数生成（纯函数） ==========

def test_build_selector_priority():
    assert capture_mode.build_selector({'name': '确定', 'control_type': 'button'}) == 'name="确定"'
    assert capture_mode.build_selector({'control_type': 'edit', 'automation_id': 'e1'}) == 'type="edit"'
    assert capture_mode.build_selector({'automation_id': 'e1', 'class_name': 'Edit'}) == 'id="e1"'
    assert capture_mode.build_selector({'class_name': 'Button'}) == 'class="Button"'
    assert capture_mode.build_selector({}) == ''
    assert capture_mode.build_selector(None) == ''


def test_build_control_params_priority():
    assert capture_mode.build_control_params({'name': '确定'}) == {'by': 'uia_name', 'target': '确定'}
    assert capture_mode.build_control_params({'control_type': 'button'}) == {'by': 'uia_type', 'target': 'button'}
    assert capture_mode.build_control_params({'automation_id': 'i1'}) == {'by': 'uia_id', 'target': 'i1'}
    assert capture_mode.build_control_params({'class_name': 'Button'}) == {'by': 'uia_class', 'target': 'Button'}
    assert capture_mode.build_control_params({}) == {'by': 'uia_name', 'target': ''}


# ========== 组合键解析 ==========

def test_parse_combo():
    mods, vk = capture_mode.parse_combo('ctrl+shift+c')
    assert mods == (win32con.MOD_CONTROL | win32con.MOD_SHIFT)
    assert vk == ord('C')
    assert capture_mode.parse_combo('esc') == (0, 0x1B)
    assert capture_mode.parse_combo('ctrl+alt+enter') == (win32con.MOD_CONTROL | win32con.MOD_ALT, 0x0D)
    assert capture_mode.parse_combo('f5') == (0, 0x74)
    assert capture_mode.parse_combo('bad??') is None
    assert capture_mode.parse_combo('') is None


def test_format_combo_roundtrip():
    for combo in ('ctrl+shift+c', 'esc', 'ctrl+alt+enter', 'f5', 'alt+f4'):
        parsed = capture_mode.parse_combo(combo)
        assert parsed is not None
        assert capture_mode.format_combo(*parsed) == combo


# ========== 状态机 ==========

def test_start_stop_state():
    r = capture_mode.start_mode()
    assert r['ok'] is True
    assert capture_mode.get_state()['active'] is True
    capture_mode.stop_mode()
    assert capture_mode.get_state()['active'] is False
    # 幂等
    capture_mode.stop_mode()
    assert capture_mode.get_state()['active'] is False


def test_start_mode_registers_dynamic_hotkeys(monkeypatch):
    """进入模式：经 PostMessage 投递注册模式期间热键（copy+exit）；退出注销"""
    calls = []
    class FakeHotkeyWindow:
        def __init__(self):
            self._apply_result = None
        def request_dynamic_hotkeys(self, enable):
            calls.append(enable)
        def hotkey_state(self):
            return True, ''
        def get_apply_result(self):
            return None
    capture_mode._hotkey_window = FakeHotkeyWindow()
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (100, 100))

    capture_mode.start_mode()
    assert calls == [True]
    capture_mode.stop_mode()
    assert calls == [True, False]


# ========== 悬停监控（静止 250ms 自动识别一次） ==========

def test_hover_monitor_stable_triggers_once(monkeypatch):
    """悬停：静止满 250ms 捕获一次；同一位置停留再久只捕获一次"""
    events = []
    monkeypatch.setattr(capture_mode, '_enqueue', lambda kind, payload=None: events.append((kind, payload)))
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (50, 50))
    stop = threading.Event()

    # 直接同步执行一次循环逻辑（monitor 是循环+等待，模拟三拍）
    capture_mode._hover_monitor.__wrapped__ = None  # no-op 标记（避免误用）
    # 使用短时间片实测：启动 monitor 线程 0.6s（包含静止 250ms + 轮询间隔）
    t = threading.Thread(target=capture_mode._hover_monitor, args=(stop,), daemon=True)
    t.start()
    time.sleep(0.7)
    stop.set()
    t.join(2)
    assert len(events) == 1            # ⚡ 只捕获一次（同位停留不再重复）
    assert events[0] == ('select', (50, 50))


def test_hover_monitor_resets_on_move(monkeypatch):
    """悬停：鼠标移动后旧捕获作废，新位置静止 250ms 再次捕获"""
    events = []
    monkeypatch.setattr(capture_mode, '_enqueue', lambda kind, payload=None: events.append((kind, payload)))
    pos = [{'cur': (50, 50)}]
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: pos[0]['cur'])
    stop = threading.Event()

    t = threading.Thread(target=capture_mode._hover_monitor, args=(stop,), daemon=True)
    t.start()
    time.sleep(0.4)          # 位置 1 静止 250ms → 捕获一次
    pos[0]['cur'] = (90, 90)  # 移动
    time.sleep(0.05)         # 不足 250ms
    assert len(events) == 1
    time.sleep(0.4)          # 位置 2 静止 250ms → 捕获第二次
    stop.set()
    t.join(2)
    assert len(events) == 2
    assert events[1] == ('select', (90, 90))


# ========== 全局热键（三热键分发：enter/copy/exit） ==========

def _make_hotkey_window():
    hw = capture_mode._HotkeyWindow()
    hw._hwnd = 12345
    return hw


def test_hotkey_window_dispatches_by_id(monkeypatch):
    """WM_HOTKEY 按 id 分发：enter→start_mode；exit→入队退出；copy→入队复制"""
    started = []
    monkeypatch.setattr(capture_mode, 'start_mode', lambda: started.append(1) or {'ok': True})
    events = []
    monkeypatch.setattr(capture_mode, '_enqueue', lambda kind, payload=None: events.append(kind))
    hw = _make_hotkey_window()

    hw._wnd_proc(0, win32con.WM_HOTKEY, capture_mode.HK_ENTER_ID, 0)
    assert started == [1]

    hw._wnd_proc(0, win32con.WM_HOTKEY, capture_mode.HK_EXIT_ID, 0)
    assert events == ['exit']

    hw._wnd_proc(0, win32con.WM_HOTKEY, capture_mode.HK_COPY_ID, 0)
    assert events == ['exit', 'copy']


def test_hotkey_register_multiple(monkeypatch):
    """enter 常驻 + copy/exit 模式期间动态注册；状态汇总为 ok"""
    registered = []
    monkeypatch.setattr(capture_mode.win32gui, 'RegisterHotKey',
                        lambda h, hid, mods, vk: registered.append(hid) or None)
    monkeypatch.setattr(capture_mode.win32gui, 'UnregisterHotKey', lambda *a: None)
    hw = _make_hotkey_window()

    hw._do_register(capture_mode.HK_ENTER_ID, 'ctrl+shift+c')
    hw._register_dynamic_hotkeys()
    assert registered == [capture_mode.HK_ENTER_ID, capture_mode.HK_COPY_ID, capture_mode.HK_EXIT_ID]
    ok, msg = hw.hotkey_state()
    assert ok is True and msg == ''

    # 注销动态热键后状态只剩 enter
    hw._unregister_dynamic_hotkeys()
    ok2, _ = hw.hotkey_state()
    assert ok2 is True
    assert capture_mode.HK_COPY_ID not in hw._hk_state


def test_hotkey_conflict_marks_state(monkeypatch):
    """某个热键被占用 → hotkey_state 汇总为失败并给出冲突信息"""
    def fake_register(h, hid, mods, vk):
        if hid == capture_mode.HK_COPY_ID:
            raise Exception('already in use')
    monkeypatch.setattr(capture_mode.win32gui, 'RegisterHotKey', fake_register)
    monkeypatch.setattr(capture_mode.win32gui, 'UnregisterHotKey', lambda *a: None)
    hw = _make_hotkey_window()

    hw._do_register(capture_mode.HK_ENTER_ID, 'ctrl+shift+c')
    hw._register_dynamic_hotkeys()
    ok, msg = hw.hotkey_state()
    assert ok is False
    assert '占用' in msg


# ========== 选中 worker（悬停识别） ==========

def test_select_worker_selects_and_highlights(monkeypatch):
    """悬停识别：选中 + 记录 select 事件 + 渲染选中框（纯边框，无标签）"""
    from core.services import uia_service

    rendered = []
    monkeypatch.setattr(
        uia_service, 'inspect_point',
        lambda x, y: {'available': True,
                      'control': {'name': '确定', 'control_type': 'button', 'rect': [0, 0, 100, 40]},
                      'ancestors': []})
    monkeypatch.setattr(
        'core.services.highlight_service.highlight_service.render',
        lambda frames: rendered.append(frames))
    # ⚡ 识别期间鼠标位置校验：mock 鼠标仍在识别点
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (50, 50))

    capture_mode._select_worker(50, 50)

    state = capture_mode.get_state()
    assert state['last_result']['event'] == 'select'
    assert state['last_result']['selector'] == 'name="确定"'
    assert capture_mode._selected['info']['name'] == '确定'
    assert len(rendered) == 1
    assert rendered[0][0]['rect'] == [0, 0,100, 40]  # ⚡ 纯边框（无 active/label 字段）


def test_select_worker_discards_stale_result(monkeypatch):
    """识别期间鼠标已移走：丢弃过期结果（框永远聚焦当下位置）"""
    from core.services import uia_service

    monkeypatch.setattr(
        uia_service, 'inspect_point',
        lambda x, y: {'available': True,
                      'control': {'name': '确定', 'control_type': 'button', 'rect': [0, 0, 100, 40]},
                      'ancestors': []})
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (999, 999))  # 鼠标已移走

    capture_mode._select_worker(50, 50)

    assert capture_mode.get_state()['last_result'] is None
    assert capture_mode._selected is None


def test_select_worker_no_control_ignores(monkeypatch):
    """识别不到有效控件：忽略并保持原选中"""
    from core.services import uia_service

    monkeypatch.setattr(uia_service, 'inspect_point',
                        lambda x, y: {'available': True, 'control': {}, 'ancestors': []})
    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (50, 50))
    capture_mode._selected = {'rect': [0, 0, 10, 10], 'info': {'name': '旧控件'}}

    capture_mode._select_worker(50, 50)

    assert capture_mode._selected['info']['name'] == '旧控件'  # 保持原选中
    assert capture_mode.get_state()['last_result'] is None


# ========== 事件队列 / SSE ==========

def test_publish_event_subscribers(monkeypatch):
    """SSE 订阅：新连接立即收到当前模式状态，随后 publish 推送给所有订阅者"""
    q1 = capture_mode.subscribe_events()
    q2 = capture_mode.subscribe_events()
    assert q1.get_nowait() == {'event': 'mode', 'active': False}
    assert q2.get_nowait() == {'event': 'mode', 'active': False}

    capture_mode.publish_event({'event': 'copy'})
    assert q1.get_nowait() == {'event': 'copy'}
    assert q2.get_nowait() == {'event': 'copy'}
    capture_mode.unsubscribe_events(q1)
    capture_mode.publish_event({'event': 'select', 'info': {'name': 'x'}})
    assert q2.get_nowait()['event'] == 'select'
    try:
        q1.get_nowait()
        raise AssertionError('已退订订阅者不应收到事件')
    except Exception:
        pass


def test_event_queue_replaces_pending(monkeypatch):
    """事件队列：新事件替换待处理事件；done_event 通知完成"""
    processed = []
    monkeypatch.setattr(capture_mode, '_select_worker', lambda *a: processed.append('select'))
    monkeypatch.setattr(capture_mode, '_invoke_copy_generate_worker', lambda: processed.append('copy'))

    capture_mode._enqueue('select', (1, 2))
    capture_mode._enqueue('copy')
    _wait_events_idle()
    assert 'copy' in processed

    done = threading.Event()
    capture_mode._enqueue('select', (3, 4), done_event=done)
    assert done.wait(2) is True


# ========== 复制 + 生成节点（生成后自动取消高亮） ==========

def test_invoke_copy_generate(monkeypatch):
    """Ctrl+Shift+Enter（未选中时）：实时识别鼠标下控件 → 复制 + 记录结果 + 清高亮"""
    import win32clipboard
    from core.services import uia_service

    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (100, 100))
    monkeypatch.setattr(
        uia_service, 'inspect_point',
        lambda x, y: {'available': True, 'control': {'name': '确定', 'control_type': 'button'},
                      'ancestors': []})

    fake_clip = []
    for name, fn in [
        ('OpenClipboard', lambda h: None),
        ('EmptyClipboard', lambda: None),
        ('SetClipboardText', lambda t, f: fake_clip.append(t)),
        ('CloseClipboard', lambda: None),
    ]:
        monkeypatch.setattr(win32clipboard, name, fn)

    capture_mode._invoke_copy_generate()
    _wait_events_idle()
    assert fake_clip == ['name="确定"']
    state = capture_mode.get_state()
    assert state['last_result'] is not None
    assert state['last_result']['selector'] == 'name="确定"'
    assert state['last_result']['event'] == 'copy'
    assert capture_mode._selected is None  # ⚡ 捕获成功即取消选中


def test_invoke_copy_generate_keeps_mode_active(monkeypatch):
    """⚡ 捕获成功后模式保持激活（顶部「控件捕获模式」连续捕获：
    每按一次 Ctrl+Shift+Enter 生成一个节点，不退出；一次性退出由前端填充完成后发起）"""
    import win32clipboard
    from core.services import uia_service

    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (100, 100))
    monkeypatch.setattr(
        uia_service, 'inspect_point',
        lambda x, y: {'available': True, 'control': {'name': '确定', 'control_type': 'button'},
                      'ancestors': []})
    for name, fn in [
        ('OpenClipboard', lambda h: None),
        ('EmptyClipboard', lambda: None),
        ('SetClipboardText', lambda t, f: None),
        ('CloseClipboard', lambda: None),
    ]:
        monkeypatch.setattr(win32clipboard, name, fn)

    capture_mode._active = True  # 模拟捕获模式运行中
    q = capture_mode.subscribe_events()
    capture_mode._invoke_copy_generate()
    _wait_events_idle()

    assert capture_mode.get_state()['active'] is True  # ⚡ 连续捕获：模式保持激活
    assert capture_mode._selected is None  # 每次捕获完成取消选中（下次悬停重新识别）
    evs = []
    while True:
        try:
            evs.append(q.get_nowait())
        except Exception:
            break
    assert not any(e.get('event') == 'mode' and not e.get('active') for e in evs), '连续捕获不应发布 mode:false'


def test_invoke_copy_generate_uses_selection(monkeypatch):
    """复制基于当前选中控件（所见即所得）：不重新识别，完成后取消选中"""
    import win32clipboard
    from core.services import uia_service

    inspect_calls = []
    monkeypatch.setattr(uia_service, 'inspect_point', lambda x, y: inspect_calls.append(1))
    fake_clip = []
    for name, fn in [
        ('OpenClipboard', lambda h: None),
        ('EmptyClipboard', lambda: None),
        ('SetClipboardText', lambda t, f: fake_clip.append(t)),
        ('CloseClipboard', lambda: None),
    ]:
        monkeypatch.setattr(win32clipboard, name, fn)

    capture_mode._selected = {'rect': [0, 0, 100, 40], 'info': {'name': '关闭按钮', 'control_type': 'button'}}
    capture_mode._invoke_copy_generate()
    _wait_events_idle()

    assert fake_clip == ['name="关闭按钮"']
    assert inspect_calls == []  # 未重新识别（复用选中信息）
    assert capture_mode.get_state()['last_result']['event'] == 'copy'
    assert capture_mode._selected is None  # ⚡ 生成后自动取消选中


def test_invoke_copy_generate_empty_skips(monkeypatch):
    """识别不到有效信息时不复制"""
    from core.services import uia_service

    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (100, 100))
    monkeypatch.setattr(uia_service, 'inspect_point', lambda x, y: {'available': True, 'control': {}, 'ancestors': []})
    capture_mode._invoke_copy_generate()
    _wait_events_idle()
    assert capture_mode.get_state()['last_result'] is None


# ========== 快捷键配置 / 冲突检测 API ==========

def test_hotkeys_get_api():
    from fastapi.testclient import TestClient
    from api.app import app

    r = TestClient(app).get('/api/settings/hotkeys')
    d = r.json()
    assert d['success'] is True
    assert d['hotkeys']['enter_capture'] == 'ctrl+shift+c'
    assert 'registration' in d


def test_hotkeys_put_api(monkeypatch):
    """更新快捷键：返回注册结果（冲突检测通过 mock 模拟占用失败）"""
    from fastapi.testclient import TestClient
    from api.app import app

    apply_called = []
    monkeypatch.setattr(capture_mode, 'apply_enter_hotkey', lambda c: apply_called.append(c) or {'ok': True})
    monkeypatch.setattr(capture_mode, 'get_hotkey_apply_result', lambda: {'ok': True, 'message': '已应用', 'combo': 'ctrl+shift+x'})
    # 不真的落盘 settings.json（避免污染 GET 测试与其他用例）
    monkeypatch.setattr(capture_mode, 'save_hotkeys', lambda hotkeys: {**capture_mode.HOTKEY_DEFAULTS, **hotkeys})

    c = TestClient(app)
    r = c.put('/api/settings/hotkeys', json={'hotkeys': {'enter_capture': 'ctrl+shift+x'}})
    d = r.json()
    assert apply_called == ['ctrl+shift+x']
    assert d['ok'] is True
    assert d['hotkeys']['enter_capture'] == 'ctrl+shift+x'

    # 冲突场景：注册失败
    monkeypatch.setattr(capture_mode, 'get_hotkey_apply_result', lambda: {'ok': False, 'message': '组合键已被其他软件占用', 'combo': 'ctrl+alt+x'})
    r2 = c.put('/api/settings/hotkeys', json={'hotkeys': {'enter_capture': 'ctrl+alt+x'}})
    d2 = r2.json()
    assert d2['ok'] is False
    assert '占用' in d2['message']


def test_hotkeys_put_rejects_duplicate(monkeypatch):
    """三个功能快捷键不允许相同"""
    from fastapi.testclient import TestClient
    from api.app import app

    monkeypatch.setattr(capture_mode, 'save_hotkeys', lambda hotkeys: {**capture_mode.HOTKEY_DEFAULTS, **hotkeys})
    r = TestClient(app).put('/api/settings/hotkeys', json={
        'hotkeys': {'exit_mode': 'ctrl+shift+c'}
    })
    d = r.json()
    assert d['ok'] is False
    assert '相同' in d['message']


def test_copy_attaches_ancestor_path(monkeypatch):
    """Ctrl+Shift+Enter 复制时给控件信息附加祖先链（执行时逐级定位用）"""
    import win32clipboard
    from core.services import uia_service

    monkeypatch.setattr(capture_mode.win32api, 'GetCursorPos', lambda: (100, 100))
    monkeypatch.setattr(
        uia_service, 'inspect_point',
        lambda x, y: {'available': True, 'control': {'name': '确定', 'control_type': 'button', 'rect': [90, 90, 110, 110]},
                      'ancestors': []})
    monkeypatch.setattr(
        uia_service, 'extract_ancestor_path_at',
        lambda x, y: [{'control_type': 'window', 'name': '主窗口', 'automation_id': '', 'class_name': ''}])
    fake_clip = []
    for name, fn in [
        ('OpenClipboard', lambda h: None),
        ('EmptyClipboard', lambda: None),
        ('SetClipboardText', lambda t, f: fake_clip.append(t)),
        ('CloseClipboard', lambda: None),
    ]:
        monkeypatch.setattr(win32clipboard, name, fn)

    capture_mode._invoke_copy_generate()
    _wait_events_idle()

    info = capture_mode.get_state()['last_result']['info']
    assert info['ancestor_path'] == [{'control_type': 'window', 'name': '主窗口', 'automation_id': '', 'class_name': ''}]
    assert fake_clip == ['name="确定"']  # 祖先链不影响选择器生成（name 优先）


def test_copy_attaches_path_from_selection_rect(monkeypatch):
    """选中控件复用（所见即所得）：以选中 rect 中心提取祖先链"""
    import win32clipboard
    from core.services import uia_service

    extract_calls = []
    def fake_extract(x, y):
        extract_calls.append((x, y))
        return [{'control_type': 'window', 'name': '主窗口', 'automation_id': '', 'class_name': ''}]
    monkeypatch.setattr(uia_service, 'extract_ancestor_path_at', fake_extract)
    monkeypatch.setattr(uia_service, 'inspect_point', lambda x, y: {'available': True, 'control': {}, 'ancestors': []})
    fake_clip = []
    for name, fn in [
        ('OpenClipboard', lambda h: None),
        ('EmptyClipboard', lambda: None),
        ('SetClipboardText', lambda t, f: fake_clip.append(t)),
        ('CloseClipboard', lambda: None),
    ]:
        monkeypatch.setattr(win32clipboard, name, fn)

    capture_mode._selected = {'rect': [100, 100, 200, 200], 'info': {'name': '关闭按钮', 'control_type': 'button', 'rect': [100, 100, 200, 200]}}
    capture_mode._invoke_copy_generate()
    _wait_events_idle()

    assert extract_calls == [(150, 150)]  # rect 中心
    info = capture_mode.get_state()['last_result']['info']
    assert info['ancestor_path'][0]['name'] == '主窗口'
