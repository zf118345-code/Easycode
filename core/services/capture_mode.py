# core/services/capture_mode.py
# ⚡ 桌面级控件捕获模式（零模态、零钩子、零轮询——终极简化版）
# 交互：
#   - 全局热键（可配置，默认 Ctrl+Shift+C）进入捕获模式：不拦截任何输入
#   - 鼠标停在任何位置 250ms → 自动识别该位置控件一次（高亮框 + 记录选中）；
#     鼠标移动后作废，新位置再停 250ms 才再次识别（同一位置停留再久也只识别一次）
#   - Ctrl+Shift+Enter（仅模式期间注册）→ 复制选择器 + 前端生成节点 + 自动取消高亮
#   - Esc（仅模式期间注册）→ 退出模式
#   - 高亮框由后端事件驱动渲染（全局高亮窗口，鼠标穿透）；前端经 SSE 消费事件（零轮询）
import collections
import json
import logging
import os
import queue
import threading
import time

import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

SETTINGS_FILE = 'settings.json'
HOTKEY_DEFAULTS = {
    'enter_capture': 'ctrl+shift+c',      # 进入捕获模式（常驻全局热键）
    'copy_generate': 'ctrl+shift+enter',  # 生成节点（仅模式期间注册）
    'exit_mode': 'esc',                   # 退出模式（仅模式期间注册）
}
HK_ENTER_ID = 1   # 进入捕获模式
HK_EXIT_ID = 2    # 退出捕获模式
HK_COPY_ID = 3    # 复制生成节点
WM_APP_APPLY = win32con.WM_APP + 1
WM_APP_DYN_HK = win32con.WM_APP + 2  # 投递到热键窗口线程：注册/注销模式期间热键（copy/exit）

# ---------------- 全局状态 ----------------

_state_lock = threading.Lock()
_active = False
_last_result = None          # {'ts': ms, 'event': 'select'|'copy', 'info': dict, 'selector': str}
_selected = None             # {'rect': [l,t,r,b], 'info': dict} 当前选中控件（锁保护）
_hotkey_ok = False
_hotkey_msg = ''             # 热键注册结果/冲突信息

_hotkey_window = None        # _HotkeyWindow 实例（热键消息窗口）
_hover_stop = None           # 悬停监控线程停止事件（模式期间存在）


def get_state() -> dict:
    hw = _hotkey_window
    if hw is not None:
        ok, msg = hw.hotkey_state()
    else:
        ok, msg = _hotkey_ok, _hotkey_msg
    with _state_lock:
        return {
            'active': _active,
            'last_result': _last_result,
            'hotkey_ok': ok,
            'hotkey_msg': msg,
        }


# ------------------------------------------------------------------ 快捷键配置持久化 / 组合键解析

# 项目根（固定路径，避免随启动目录漂移）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _settings_path() -> str:
    # ⚡ H1：固定到项目根（不依赖进程工作目录）；旧 cwd 位置存在时迁移
    legacy = os.path.join(os.getcwd(), SETTINGS_FILE)
    fixed = os.path.join(PROJECT_ROOT, SETTINGS_FILE)
    if os.path.exists(legacy) and not os.path.exists(fixed):
        try:
            with open(legacy, encoding='utf-8') as f:
                data = f.read()
            with open(fixed, 'w', encoding='utf-8') as f:
                f.write(data)
            os.remove(legacy)
            logger.info('快捷键配置已迁移到固定路径: %s', fixed)
        except Exception:
            pass
    return fixed


# 配置内存缓存：低级钩子回调内绝不允许读磁盘（LL 钩子超时会被系统移除）
_hotkeys_cache = None


def load_hotkeys() -> dict:
    global _hotkeys_cache
    if _hotkeys_cache is None:
        try:
            with open(_settings_path(), encoding='utf-8') as f:
                data = json.load(f)
            saved = data.get('hotkeys') or {}
            _hotkeys_cache = {**HOTKEY_DEFAULTS, **saved}
        except Exception:
            _hotkeys_cache = dict(HOTKEY_DEFAULTS)
    return _hotkeys_cache


def save_hotkeys(hotkeys: dict) -> dict:
    global _hotkeys_cache
    merged = {**HOTKEY_DEFAULTS, **hotkeys}
    try:
        with open(_settings_path(), 'w', encoding='utf-8') as f:
            json.dump({'hotkeys': merged}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning('保存快捷键配置失败: %s', e)
    _hotkeys_cache = merged  # 同步内存缓存（钩子回调即时生效，无需重启）
    return merged


_VK_NAMES = {
    0x0D: 'enter', 0x1B: 'esc', 0x20: 'space', 0x09: 'tab', 0x08: 'backspace',
    0x2E: 'delete', 0x26: 'up', 0x28: 'down', 0x25: 'left', 0x27: 'right',
    0x24: 'home', 0x23: 'end', 0x21: 'pgup', 0x22: 'pgdn',
    0x70: 'f1', 0x71: 'f2', 0x72: 'f3', 0x73: 'f4', 0x74: 'f5', 0x75: 'f6',
    0x76: 'f7', 0x77: 'f8', 0x78: 'f9', 0x79: 'f10', 0x7A: 'f11', 0x7B: 'f12',
}
_VK_BY_NAME = {name: code for code, name in _VK_NAMES.items()}


def parse_combo(combo: str):
    """'ctrl+shift+c' → (mods, vk)；无效返回 None"""
    parts = [p.strip().lower() for p in (combo or '').split('+') if p.strip()]
    mods = 0
    vk = 0
    for p in parts:
        if p in ('ctrl', 'control'):
            mods |= win32con.MOD_CONTROL
        elif p == 'shift':
            mods |= win32con.MOD_SHIFT
        elif p == 'alt':
            mods |= win32con.MOD_ALT
        elif p == 'win':
            mods |= win32con.MOD_WIN
        elif len(p) == 1 and p.isalpha():
            vk = ord(p.upper())
        else:
            vk = _VK_BY_NAME.get(p, 0)
    if not vk:
        return None
    return mods, vk


def format_combo(mods: int, vk: int) -> str:
    parts = []
    if mods & win32con.MOD_CONTROL:
        parts.append('ctrl')
    if mods & win32con.MOD_SHIFT:
        parts.append('shift')
    if mods & win32con.MOD_ALT:
        parts.append('alt')
    if mods & win32con.MOD_WIN:
        parts.append('win')
    if vk in _VK_NAMES:
        parts.append(_VK_NAMES[vk])
    elif 0x41 <= vk <= 0x5A:
        parts.append(chr(vk).lower())
    else:
        parts.append(f'vk{vk}')
    return '+'.join(parts)


# ------------------------------------------------------------------ 选择器 / 参数生成（纯函数）

def build_selector(info: dict) -> str:
    """捕获信息 → 控件选择器（与控件操作节点的 UIA 查找方式对应）"""
    info = info or {}
    name = (info.get('name') or '').strip()
    if name:
        return f'name="{name}"'
    ctype = (info.get('control_type') or '').strip()
    if ctype:
        return f'type="{ctype}"'
    aid = (info.get('automation_id') or '').strip()
    if aid:
        return f'id="{aid}"'
    cls = (info.get('class_name') or '').strip()
    if cls:
        return f'class="{cls}"'
    return ''


def build_control_params(info: dict) -> dict:
    """捕获信息 → 控件操作节点查找参数（前端生成节点时自动填充）"""
    info = info or {}
    name = (info.get('name') or '').strip()
    if name:
        return {'by': 'uia_name', 'target': name}
    ctype = (info.get('control_type') or '').strip()
    if ctype:
        return {'by': 'uia_type', 'target': ctype}
    aid = (info.get('automation_id') or '').strip()
    if aid:
        return {'by': 'uia_id', 'target': aid}
    cls = (info.get('class_name') or '').strip()
    if cls:
        return {'by': 'uia_class', 'target': cls}
    return {'by': 'uia_name', 'target': ''}


# ------------------------------------------------------------------ 全局热键消息窗口

class _HotkeyWindow:
    """承载 RegisterHotKey 的隐藏消息窗口：三热键制。
    - enter（HK_ENTER_ID）常驻注册
    - copy（HK_COPY_ID）/ exit（HK_EXIT_ID）仅在捕获模式期间注册
      （常驻会全局吃掉 Ctrl+Shift+Enter / Esc，交互混乱元凶）"""

    def __init__(self):
        self._hwnd = None
        self._apply_pending = None
        self._apply_result = None
        self._hk_state = {}  # hk_id -> [combo, ok, msg]（锁保护）

    def run(self):
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = 'EasycodeHotkeyWindow'
        wc.lpfnWndProc = self._wnd_proc
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
        self._hwnd = win32gui.CreateWindow(
            'EasycodeHotkeyWindow', 'EasycodeHotkey', 0, 0, 0, 0, 0,
            None, None, hinst, None)
        hotkeys = load_hotkeys()
        self._do_register(HK_ENTER_ID, hotkeys.get('enter_capture', ''))
        while True:
            res = win32gui.GetMessage(self._hwnd, 0, 0)
            if res is None or res[0] == 0 or res[1][2] == win32con.WM_QUIT:
                break
            win32gui.TranslateMessage(res[1])
            win32gui.DispatchMessage(res[1])

    def _wnd_proc(self, h, m, w, l):
        if m == win32con.WM_HOTKEY:
            # ⚡ 三热键分发：按 wParam（热键 id）区分
            if w == HK_ENTER_ID:
                start_mode()
            elif w == HK_EXIT_ID:
                _enqueue('exit')  # 退出在事件 worker 执行（不阻塞热键窗口线程）
            elif w == HK_COPY_ID:
                _enqueue('copy')
            return 0
        if m == WM_APP_APPLY:
            self._apply()
            return 0
        if m == WM_APP_DYN_HK:
            # ⚡ 模式期间热键的注册/注销必须在本窗口线程执行（RegisterHotKey 跨线程会 1408 失败）
            if w:
                self._register_dynamic_hotkeys()
            else:
                self._unregister_dynamic_hotkeys()
            return 0
        if m == win32con.WM_CLOSE:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(h, m, w, l)

    def request_dynamic_hotkeys(self, enable: bool):
        """任意线程调用：投递到热键窗口线程注册/注销模式期间热键（copy+exit）"""
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, WM_APP_DYN_HK, 1 if enable else 0, 0)

    def _register_dynamic_hotkeys(self):
        hotkeys = load_hotkeys()
        for hk_id, key in ((HK_COPY_ID, 'copy_generate'), (HK_EXIT_ID, 'exit_mode')):
            self._do_register(hk_id, hotkeys.get(key, ''))

    def _unregister_dynamic_hotkeys(self):
        for hk_id in (HK_COPY_ID, HK_EXIT_ID):
            try:
                win32gui.UnregisterHotKey(self._hwnd, hk_id)
            except Exception:
                pass
            with _state_lock:
                self._hk_state.pop(hk_id, None)

    def _do_register(self, hk_id: int, combo: str):
        """注册单个全局热键（幂等重注册）；冲突检测独立记录，hotkey_ok 汇总所有键"""
        parsed = parse_combo(combo)
        if parsed is None:
            with _state_lock:
                self._hk_state[hk_id] = [combo, False, f'组合键格式无效: {combo}']
            return
        mods, vk = parsed
        try:
            win32gui.UnregisterHotKey(self._hwnd, hk_id)
        except Exception:
            pass
        try:
            win32gui.RegisterHotKey(self._hwnd, hk_id, mods, vk)
            with _state_lock:
                self._hk_state[hk_id] = [combo, True, '']
            logger.info('全局热键已注册 [%s]: %s', hk_id, combo or format_combo(mods, vk))
        except Exception as e:
            # ⚡ 冲突检测：RegisterHotKey 抛异常 = 组合键已被其他程序占用
            with _state_lock:
                self._hk_state[hk_id] = [combo, False, f'组合键已被其他软件占用: {combo}']
            logger.warning('注册热键冲突 [%s]: %s', hk_id, combo)

    def hotkey_state(self) -> tuple:
        """汇总所有全局热键注册状态 → (ok, message)"""
        with _state_lock:
            states = [list(v) for v in self._hk_state.values()]
        ok = all(s[1] for s in states) if states else True
        msg = '；'.join(s[2] for s in states if s[2])
        return ok, msg

    def apply_new(self, combo: str):
        """外部（API 线程）调用：投递到热键窗口线程重注册 + 冲突检测"""
        with _state_lock:
            self._apply_pending = combo
            self._apply_result = None
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, WM_APP_APPLY, 0, 0)

    def _apply(self):
        combo = self._apply_pending
        if not combo:
            return
        hotkeys = load_hotkeys()
        hotkeys['enter_capture'] = combo
        save_hotkeys(hotkeys)
        self._do_register(HK_ENTER_ID, combo)
        ok, msg = self.hotkey_state()
        with _state_lock:
            self._apply_result = {
                'ok': ok,
                'message': msg or f'已应用快捷键: {combo}',
                'combo': combo,
            }

    def get_apply_result(self) -> dict:
        with _state_lock:
            return dict(self._apply_result) if self._apply_result else None


# ------------------------------------------------------------------ 事件订阅（SSE：前端零轮询，事件驱动推送）

_event_subscribers = []  # [queue.Queue]（SSE 长连接）
_sub_lock = threading.Lock()


def subscribe_events() -> 'queue.Queue':
    """注册事件订阅（SSE 端点调用），返回接收队列。
    ⚡ 新连接立即推送当前模式状态：SSE 不重放历史事件，否则悬浮窗/页面
    连上后不知道当前是否激活（悬浮窗"未运行也悬浮"的根因之一）。"""
    q = queue.Queue()
    with _state_lock:
        q.put_nowait({'event': 'mode', 'active': _active})
        _event_subscribers.append(q)
    return q


def unsubscribe_events(q):
    with _sub_lock:
        if q in _event_subscribers:
            _event_subscribers.remove(q)


def publish_event(payload: dict):
    """向所有 SSE 订阅者推送事件（选中/层级/取消/复制/模式状态）"""
    with _sub_lock:
        subs = list(_event_subscribers)
    for q in subs:
        try:
            q.put_nowait(payload)
        except Exception:
            pass


# ------------------------------------------------------------------ 捕获事件队列（单 worker 串行 + 同类合并）

# ⚡ 所有捕获事件（select/wheel/clear/copy）统一入队，由单个 worker 线程串行处理：
#   - 消除线程风暴：快速滚动一次会产生多个 WM_MOUSEWHEEL，曾经的"每事件一线程"
#     导致几十个并发 UIA 识别 + 渲染 → COM 压力爆炸 → 滚动卡死（本次根因）
#   - 消除并发 GDI：UIA 识别与高亮渲染全部单线程，杜绝跨线程窗口操作
#   - 同类合并：快速连发同类事件只保留最新意图（如连续滚轮只切到最终层级）

_event_deque = collections.deque()  # [(kind, payload, done_event)]，防堆积（新事件替换待处理）
_event_running = False
_event_lock = threading.Lock()


def _enqueue(kind: str, payload=None, done_event=None):
    global _event_running
    with _event_lock:
        # 防堆积：worker 正在处理时，新事件替换队列中所有待处理事件（只保留最新意图）
        _event_deque.clear()
        _event_deque.append((kind, payload, done_event))
        if not _event_running:
            _event_running = True
            threading.Thread(target=_event_loop, daemon=True, name='capture-events').start()


def _event_loop():
    """捕获事件串行执行循环：UIA 识别 + 高亮渲染全在本线程"""
    global _event_running
    while True:
        with _event_lock:
            if not _event_deque:
                _event_running = False
                return
            kind, payload, done_event = _event_deque.popleft()
        try:
            if kind == 'select':
                _select_worker(*payload)
            elif kind == 'copy':
                _invoke_copy_generate_worker()
            elif kind == 'exit':
                stop_mode()
        except Exception as e:
            logger.error('捕获事件处理异常(%s): %s', kind, e)
        finally:
            if done_event:
                done_event.set()


def _render_selection(info: dict, ancestors: list):
    """后端直接驱动全局高亮：只画当前选中控件（纯边框，无任何标签/文字）。"""
    try:
        from core.services.highlight_service import highlight_service

        frames = []
        rect = info.get('rect') or []
        if len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1]:
            frames.append({'rect': rect})
        highlight_service.render(frames)
    except Exception as e:
        logger.warning('渲染选中高亮失败: %s', e)


def _clear_highlight():
    """清空高亮（内部：捕获完成/退出时调用）"""
    try:
        from core.services.highlight_service import highlight_service

        highlight_service.render([])
    except Exception as e:
        logger.warning('清除高亮失败: %s', e)


# ------------------------------------------------------------------ 悬停监控（鼠标静止 250ms 自动识别一次）

HOVER_STABLE_MS = 250    # 鼠标静止多久触发识别
HOVER_POLL_MS = 100      # 位置轮询间隔（纯 GetCursorPos，零开销）


def _hover_monitor(stop: threading.Event):
    """（模式期间守护线程）跟踪鼠标位置：
    - 位置变化 → 重置计时，并**立即取消旧框选**（框只聚焦当下位置，之前的高亮马上消失）
    - 静止满 250ms 且该位置未捕获过 → 入队一次 select（携带坐标）
    - 同一位置停留再久也只捕获一次（鼠标移开再回来才重新捕获）"""
    global _selected
    pos = None
    stable_since = None
    captured_pos = None
    while not stop.is_set():
        try:
            cur = win32api.GetCursorPos()
        except Exception:
            time.sleep(HOVER_POLL_MS / 1000.0)
            continue
        now = time.time()
        if cur != pos:
            pos = cur
            stable_since = now
            captured_pos = None
            # ⚡ 鼠标移动：旧框立即取消（框聚焦当下位置，之前的高亮不再滞留）
            with _state_lock:
                had_selection = _selected is not None
                _selected = None
            if had_selection:
                _clear_highlight()
        elif stable_since is not None and now - stable_since >= HOVER_STABLE_MS / 1000.0 \
                and captured_pos != cur:
            captured_pos = cur
            _enqueue('select', cur)
        stop.wait(HOVER_POLL_MS / 1000.0)


# ⚡ UIA 调用超时保护：uiautomation 的 COM 调用在个别应用（浏览器/自绘控件）上可能挂起数秒，
# 共享线程池会被卡死的调用占满（后续识别全部排队超时 → "悬停永远不更新"的根因）。
# 改为每次调用独立 daemon 线程 + 短超时：卡死的线程被遗弃（识别频率低，泄漏可忽略），
# 后续识别不再受影响。
def _uia_call(fn, timeout=3.0):
    result_holder = {}
    def runner():
        try:
            result_holder['ok'] = True
            result_holder['value'] = fn()
        except Exception as e:
            result_holder['ok'] = False
            result_holder['value'] = e
    t = threading.Thread(target=runner, daemon=True, name='uia-call')
    t.start()
    t.join(timeout)
    if not result_holder.get('ok'):
        logger.warning('UIA 调用超时/失败: %s', result_holder.get('value'))
        return None
    return result_holder.get('value')


def _select_worker(x: int, y: int):
    """（事件 worker）悬停静止 250ms → 识别该位置最深控件 → 选中 + 高亮 + 记录结果。
    ⚡ 识别期间鼠标已移走则丢弃结果（不画过期框——框永远聚焦当下位置）。"""
    global _selected, _last_result
    from core.services import uia_service

    result = _uia_call(lambda: uia_service.inspect_point(x, y))
    # 识别耗时期间鼠标可能已移动：旧位置的结果无意义，丢弃
    try:
        if win32api.GetCursorPos() != (x, y):
            return
    except Exception:
        pass
    if result is None:
        logger.warning('悬停识别超时/失败（point=%s, %s）', x, y)
        return
    info = (result or {}).get('control') or {}
    if not info or not info.get('rect'):
        logger.warning('悬停未识别到有效控件（point=%s, %s），忽略', x, y)
        return
    selector = build_selector(info)
    with _state_lock:
        _selected = {'rect': list(info['rect']), 'info': info}
        _last_result = {'ts': int(time.time() * 1000), 'event': 'select', 'info': info, 'selector': selector}
    _render_selection(info, [])
    publish_event({'event': 'select', 'info': info, 'selector': selector})
    logger.info('控件已选中: %s', selector or info.get('name', ''))


# ------------------------------------------------------------------ 复制 + 生成节点（Ctrl+Shift+Enter，模式期间热键）

def _invoke_copy_generate():
    """Ctrl+Shift+Enter：复制「当前选中控件」→ 入队"""
    _enqueue('copy')


def _attach_ancestor_path(info: dict) -> dict:
    """给捕获信息附加祖先链（rect 中心重新取元素并向上收集到顶层窗口）。
    执行时沿链逐级下降定位（毫秒级），是"录入后找不到"的核心解法；
    提取失败（结构异常等）不影响主流程，返回原 info。"""
    if not isinstance(info, dict) or info.get('ancestor_path'):
        return info
    rect = info.get('rect') or []
    if len(rect) != 4:
        return info
    try:
        from core.services import uia_service

        path = uia_service.extract_ancestor_path_at((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        if path:
            info = dict(info)
            info['ancestor_path'] = path
    except Exception as e:
        logger.warning('提取控件祖先链失败: %s', e)
    return info


def _invoke_copy_generate_worker():
    """（事件 worker）复制「当前选中控件」选择器 + 记录结果（前端据此生成节点）。
    ⚡ 生成完成后自动取消选中 + 清空高亮（捕获成功即清，用户明确要求）；
    模式保持激活（顶部「控件捕获模式」= 连续捕获，每按一次 Ctrl+Shift+Enter 生成一个节点；
    节点表单「捕获控件」的一次性退出由前端在填充完成后调用 stop_mode 实现）。
    未选中时回退鼠标位置实时识别（兼容刚进入模式直接按快捷键的场景）。"""
    global _selected, _last_result
    with _state_lock:
        sel = dict(_selected) if _selected else None
    from core.services import uia_service

    if sel:
        # ⚡ 所见即所得：复制当前高亮选中的控件（无需重新识别）
        info = sel['info']
    else:
        try:
            x, y = win32api.GetCursorPos()
        except Exception:
            return
        result = _uia_call(lambda: uia_service.inspect_point(x, y))
        if result is None:
            logger.warning('生成节点前识别超时')
            return
        info = (result or {}).get('control') or {}
    # ⚡ 先清高亮再提取祖先链：高亮框是覆盖层，ControlFromPoint 会先命中它，
    # 导致跳过防御后拿到的是桌面根而非真实控件（祖先链提取失败的主因）
    _clear_highlight()
    info = _attach_ancestor_path(info)  # ⚡ 祖先链随控件信息存入节点，执行时逐级定位
    selector = build_selector(info)
    if not selector:
        return
    try:
        import win32clipboard

        win32clipboard.OpenClipboard(0)
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(selector, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception as e:
        logger.warning('写入剪贴板失败: %s', e)
        return
    with _state_lock:
        _selected = None  # ⚡ 捕获成功：取消选中
        _last_result = {'ts': int(time.time() * 1000), 'event': 'copy', 'info': info, 'selector': selector}
    _clear_highlight()  # ⚡ 捕获完成即清高亮
    publish_event({'event': 'copy', 'info': info, 'selector': selector})
    logger.info('控件捕获结果已复制: %s', selector)


# ------------------------------------------------------------------ 模式控制

AUTO_EXIT_SECONDS = 300  # 模式最长 5 分钟自动退出（释放模式期间热键）
_auto_exit_timer = None


def _schedule_auto_exit():
    """模式自动退出兜底（防用户忘记退出导致 Esc/Ctrl+Shift+Enter 被长期占用）"""
    global _auto_exit_timer
    _cancel_auto_exit()
    _auto_exit_timer = threading.Timer(AUTO_EXIT_SECONDS, stop_mode)
    _auto_exit_timer.daemon = True
    _auto_exit_timer.start()


def _cancel_auto_exit():
    global _auto_exit_timer
    if _auto_exit_timer:
        _auto_exit_timer.cancel()
        _auto_exit_timer = None


def start_mode() -> dict:
    """启动捕获模式（零模态、零钩子；幂等）。"""
    global _hover_stop, _last_result, _selected, _active
    with _state_lock:
        if _active:
            return {'ok': True, 'message': '捕获模式已运行'}
        _active = True
        _last_result = None
        _selected = None
        _hover_stop = threading.Event()
        stop = _hover_stop
    threading.Thread(target=_hover_monitor, args=(stop,), daemon=True, name='capture-hover').start()
    _schedule_auto_exit()
    # ⚡ 模式期间热键（copy+exit）动态注册：经 PostMessage 投递到热键窗口线程执行
    # （RegisterHotKey 跨线程调用会 1408 失败；常驻注册会全局吃掉 Esc/Ctrl+Shift+Enter）
    if _hotkey_window is not None:
        _hotkey_window.request_dynamic_hotkeys(True)
    publish_event({'event': 'mode', 'active': True})
    return {'ok': True, 'message': '捕获模式已启动（鼠标悬停自动识别控件）'}


def stop_mode():
    """退出捕获模式（幂等）：停悬停监控，清选中与高亮，释放模式期间热键"""
    global _hover_stop, _selected, _active
    with _state_lock:
        if not _active and _hover_stop is None:
            return
        _active = False
        _selected = None
        stop = _hover_stop
        _hover_stop = None
    if stop:
        stop.set()
    _cancel_auto_exit()
    # ⚡ 注销模式期间热键（Esc/Ctrl+Shift+Enter 交还系统）
    if _hotkey_window is not None:
        _hotkey_window.request_dynamic_hotkeys(False)
    _clear_highlight()  # ⚡ 退出即清空所有框
    publish_event({'event': 'mode', 'active': False})


# ------------------------------------------------------------------ 热键窗口线程

_hotkey_started = False


def ensure_hotkey_thread():
    """启动全局热键消息窗口线程（幂等；由路由创建时调用）"""
    global _hotkey_started, _hotkey_window
    with _state_lock:
        if _hotkey_started:
            return
        _hotkey_started = True
    window = _HotkeyWindow()
    with _state_lock:
        _hotkey_window = window
    threading.Thread(target=window.run, daemon=True, name='capture-hotkey').start()


def apply_enter_hotkey(combo: str) -> dict:
    """动态修改「进入捕获」快捷（带冲突检测）；幂等"""
    if _hotkey_window is not None:
        _hotkey_window.apply_new(combo)
    return {'ok': True, 'pending': True}


def get_hotkey_apply_result():
    """返回最近一次热键重注册结果（apply_new 后由热键窗口线程填充）；无则 None"""
    hw = _hotkey_window
    return hw.get_apply_result() if hw else None


def get_hotkeys_state() -> dict:
    with _state_lock:
        return {'hotkey_ok': _hotkey_ok, 'hotkey_msg': _hotkey_msg, 'hotkeys': load_hotkeys()}
