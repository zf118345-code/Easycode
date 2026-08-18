# core/services/control_service.py
# ⚡ 控件操作服务（Win32 原生控件树，仅依赖 pywin32，无第三方控件库）
# 提供三大能力：
#   1. control_from_point：控件捕获（鼠标坐标下的最深层控件信息，供捕获工具轮询）
#   2. find_control：按选择器查找控件（class_name / text / control_type，支持序号与超时轮询）
#   3. perform_action：控件操作（点击/双击/悬停/输入文本/读取文本）
import logging
import time

import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

# 常见 Win32 控件类名 → 语义类型（供 by=control_type 匹配与面板展示）
CLASS_TYPE_MAP = {
    'Button': 'button',
    'Edit': 'edit',
    'Static': 'text',
    'ComboBox': 'combobox',
    'ComboBoxEx32': 'combobox',
    'ListBox': 'list',
    'SysListView32': 'list',
    'ListView20WndClass': 'list',
    'TreeView': 'tree',
    'SysTreeView32': 'tree',
    'ToolbarWindow32': 'toolbar',
    'StatusBar': 'statusbar',
    'msctls_statusbar32': 'statusbar',
    'ScrollBar': 'scrollbar',
    'SysTabControl32': 'tab',
    'TabWindowClass': 'tab',
    'RichEdit': 'edit',
    'RICHEDIT50W': 'edit',
    'SysDateTimePick32': 'datetime',
    'SysMonthCal32': 'calendar',
    'WindowsForms10.Button.app.0.378734a': 'button',
    'WindowsForms10.EDIT.app.0.378734a': 'edit',
    'WindowsForms10.COMBOBOX.app.0.378734a': 'combobox',
    'WindowsForms10.STATIC.app.0.378734a': 'text',
}


def _safe_window_text(hwnd) -> str:
    try:
        return win32gui.GetWindowText(hwnd) or ''
    except Exception:
        return ''


def _safe_class_name(hwnd) -> str:
    try:
        return win32gui.GetClassName(hwnd) or ''
    except Exception:
        return ''


def _safe_window_rect(hwnd):
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None


def _class_type(class_name: str) -> str:
    """控件类名 → 语义类型；已知表命中返回小写类型，未知类名原样小写"""
    cls = (class_name or '').strip()
    if cls in CLASS_TYPE_MAP:
        return CLASS_TYPE_MAP[cls]
    if cls.startswith('WindowsForms10.'):
        return cls.split('.')[2].lower() if len(cls.split('.')) > 2 else 'window'
    if cls.startswith(('Chrome_WidgetWin', 'ApplicationFrameWindow', 'Qt')):
        return 'window'
    return cls.lower() or 'unknown'


def build_control_info(hwnd) -> dict:
    """从句柄提取控件信息（控件捕获与查找共用）"""
    rect = _safe_window_rect(hwnd) or (0, 0, 0, 0)
    class_name = _safe_class_name(hwnd)
    return {
        'hwnd': hwnd,
        'class_name': class_name,
        'control_type': _class_type(class_name),
        'text': _safe_window_text(hwnd),
        'rect': list(rect),
        'width': rect[2] - rect[0],
        'height': rect[3] - rect[1],
    }


def control_from_point(x: int, y: int) -> dict | None:
    """返回坐标下最深层（面积最小）的控件信息，附带所属顶层窗口"""
    try:
        hwnd = win32gui.WindowFromPoint((int(x), int(y)))
    except Exception:
        return None
    if not hwnd:
        return None

    best_hwnd = hwnd
    best_area = None

    def _enum(h, _unused):
        nonlocal best_hwnd, best_area
        r = _safe_window_rect(h)
        if not r:
            return True
        if not (r[0] <= x <= r[2] and r[1] <= y <= r[3]):
            return True
        area = (r[2] - r[0]) * (r[3] - r[1])
        if best_area is None or area < best_area:
            best_area = area
            best_hwnd = h
        return True

    try:
        win32gui.EnumChildWindows(hwnd, _enum, None)
    except Exception:
        pass

    info = build_control_info(best_hwnd)
    info['top_level_window'] = build_control_info(hwnd)
    return info


def matches(info: dict, by: str, target: str) -> bool:
    """控件信息与查找选择器匹配（纯函数，便于单元测试）。
    ⚡ 文本比较做空白归一化（\xa0/换行/多空格 → 单空格），修复真实窗口文本匹配失配"""
    target = _normalize_text(target)
    if not target:
        return False
    if by == 'class_name':
        return _normalize_text(info.get('class_name')) == target
    if by == 'text':
        return _normalize_text(info.get('text')) == target
    if by == 'control_type':
        return _normalize_text(info.get('control_type')).lower() == target.lower()
    if by == 'hwnd':
        return str(info.get('hwnd')) == target
    return False


def _normalize_text(s) -> str:
    """空白归一化：\xa0/换行/制表/连续空格 → 单空格"""
    return ' '.join(str(s or '').split())


# ------------------------------------------------------------------ 窗口/控件枚举

def _find_top_window(window_title: str):
    """按标题精确匹配顶层窗口，返回第一个匹配句柄"""
    title = (window_title or '').strip()
    found = []

    def _top(h, _):
        if _safe_window_text(h).strip() == title:
            found.append(h)
        return True

    try:
        win32gui.EnumWindows(_top, None)
    except Exception:
        return None
    return found[0] if found else None


def _enumerate_children(hwnd) -> list:
    children = []

    def _enum(h, _):
        children.append(h)
        return True

    try:
        win32gui.EnumChildWindows(hwnd, _enum, None)
    except Exception:
        pass
    return children


def _collect_top_windows() -> list:
    """枚举全部顶层窗口（空标题场景复用：窗口列表在超时轮询内稳定，只枚举一次）"""
    tops = []

    def _top(h, _):
        tops.append(h)
        return True

    try:
        win32gui.EnumWindows(_top, None)
    except Exception:
        pass
    return tops


def _collect_windows(window_title: str, tops_cache: list | None = None) -> list:
    """收集候选窗口/控件句柄列表（目标窗口 + 其所有后代；或全桌面所有窗口）。
    ⚡ tops_cache：空标题场景复用顶层窗口列表（首轮枚举一次，轮询期间不再全桌面 EnumWindows）；
    子控件（EnumChildWindows）每轮实时枚举（控件延迟创建仍可被捕获）。"""
    if window_title:
        root = _find_top_window(window_title)
        if root is None:
            return []
        return [root] + _enumerate_children(root)

    tops = tops_cache if tops_cache is not None else _collect_top_windows()
    result = []
    for top in tops:
        result.append(top)
        result.extend(_enumerate_children(top))
    return result


def find_control(
    window_title: str = '',
    by: str = 'class_name',
    target: str = '',
    index: int = 0,
    timeout_ms: int = 3000,
) -> dict | None:
    """按选择器在目标窗口（或全桌面）内查找第 index 个匹配控件；超时轮询控件延迟创建"""
    try:
        index = max(0, int(index or 0))
    except (TypeError, ValueError):
        index = 0
    deadline = time.time() + max(0, float(timeout_ms or 0)) / 1000.0
    seen = 0
    tops_cache = None if window_title else _collect_top_windows()  # ⚡ 顶层窗口列表只枚举一次
    while time.time() < deadline:
        for hwnd in _collect_windows(window_title, tops_cache):
            info = build_control_info(hwnd)
            if matches(info, by, target):
                if seen == index:
                    info['match_index'] = seen
                    return info
                seen += 1
        time.sleep(0.05)
    return None


# ------------------------------------------------------------------ 控件操作

def perform_action(info: dict, action: str, text: str = '') -> dict:
    """对控件执行操作；返回 {ok, value?, message}"""
    hwnd = info.get('hwnd')
    rect = info.get('rect') or [0, 0, 0, 0]
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2

    if action in ('click', 'double_click'):
        # ⚡ 多开友好：直接向控件窗口投递后台点击，不移动物理鼠标、不抢占光标
        from core.services.background_input import background_click

        clicks = 2 if action == 'double_click' else 1
        result = background_click(hwnd, cx, cy, clicks=clicks)
        if not result.get('ok'):
            return {'ok': False, 'message': result.get('message', '后台点击失败')}
        return {'ok': True, 'message': f'{"双击" if clicks == 2 else "点击"}控件中心 ({cx}, {cy})'}
    if action == 'hover':
        win32api.SetCursorPos((cx, cy))
        return {'ok': True, 'message': f'悬停至控件中心 ({cx}, {cy})'}
    if action in ('get_text', 'get_value'):
        value = _safe_window_text(hwnd)
        return {'ok': True, 'value': value, 'message': f'读取控件文本: {value!r}'}
    if action == 'input_text':
        _set_control_text(hwnd, text)
        return {'ok': True, 'message': f'向控件输入文本: {text!r}'}
    return {'ok': False, 'message': f'不支持的操作: {action}'}


def _set_control_text(hwnd, text: str):
    """聚焦控件并写入文本（WM_SETTEXT，对标准 Edit/ComboBox 生效）"""
    try:
        win32gui.SetFocus(hwnd)
    except Exception:
        pass
    try:
        win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, text or '')
    except Exception as e:
        logger.warning('控件输入失败 hwnd=%s: %s', hwnd, e)
