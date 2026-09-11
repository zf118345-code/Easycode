# core/services/uia_service.py
# ⚡ Windows UI Automation 控件服务：元素级控件识别（穿透浏览器/自绘控件）
# 提供：鼠标下最深元素 + 父链（捕获工具高亮）、UIA 选择器查找与后台操作
# （Invoke / PostMessage / 物理兜底）。uiautomation 库不可用时 available()=False，
# 上层自动降级 Win32 窗口级识别。
import logging
import threading
import time

logger = logging.getLogger(__name__)

_MAX_FIND_WALK = 20000    # 查找遍历上限（Python BFS 兜底用；原生 COM 查找不依赖此预算）
# ⚡ 捕获轮询父链深度：只取最近 2 层父链（高亮画 1~2 条虚线框足够）。
# 曾经为 8 层：每层 7 个 COM 属性调用，150ms 轮询下单次识别 60+ 次 COM 往返 → 卡顿元凶之一
_ANCESTOR_DEPTH = 3
_HIGHLIGHT_WINDOW_TITLE = 'EasycodeHighlight'  # 全局高亮窗口标题（防御：捕获时跳过自家窗口）
_PHYSICAL_INPUT_LOCK = threading.Lock()

# UIA TreeScope 常量（原生 COM 接口使用）
_TREESCOPE_CHILDREN = 2
_TREESCOPE_SUBTREE = 4

# ⚡ COM 是线程关联的：executor/SSE 线程池里跑 UIA 查找必须先 CoInitialize，
# 否则报 [WinError -2147221008] 尚未调用 CoInitialize（控件查找全部失败）。
_com_tls = threading.local()


def _ensure_com():
    """确保当前线程已初始化 COM（Apartment 线程模型，与 uiautomation 线程 demo 一致）；
    每线程只初始化一次，无需配套 Uninitialize（线程池线程生命周期由进程管理）。"""
    if getattr(_com_tls, 'inited', False):
        return
    try:
        from uiautomation import InitializeUIAutomationInCurrentThread

        InitializeUIAutomationInCurrentThread()
        _com_tls.inited = True
    except Exception:
        # 初始化失败时下次仍重试（如 uiautomation 库缺失）
        _com_tls.inited = True


def _uia():
    """延迟导入 uiautomation；不可用返回 None。
    ⚡ 设置全局搜索超时：限制 UIA COM 搜索时长，避免在浏览器/复杂应用上挂起数秒。"""
    try:
        _ensure_com()
        import uiautomation as auto
        try:
            auto.SetGlobalSearchTimeout(1.0)
        except Exception:
            pass
        return auto
    except Exception:
        return None


def available() -> bool:
    return _uia() is not None


def _element_info(el, light: bool = False) -> dict:
    """从 UIA 元素提取通用信息（异常字段容错）。
    light=True：高频捕获轮询路径，只取选择器所需字段（跳过 hwnd/is_enabled 两个 COM 调用）；
    执行路径（find_control）用完整信息（含句柄/可用态）。"""
    def safe(getter, default=''):
        try:
            v = getter()
            return default if v is None else v
        except Exception:
            return default

    name = safe(lambda: el.Name)
    control_type = safe(lambda: (el.ControlTypeName or '').replace('Control', '').lower())
    aid = safe(lambda: el.AutomationId)
    cls = safe(lambda: el.ClassName)
    try:
        r = el.BoundingRectangle
        rect = [r.left, r.top, r.right, r.bottom]
    except Exception:
        rect = [0, 0, 0, 0]
    info = {
        'name': str(name),
        'control_type': str(control_type),
        'automation_id': str(aid),
        'class_name': str(cls),
        'rect': rect,
    }
    # ⚡ 顶层窗口标题：执行时作为查找作用域（避免全桌面 UIA 树遍历），
    # 随捕获信息存入节点隐藏字段 control_info，表单不展示但执行时使用
    try:
        top = el.GetTopLevelControl()
        info['window_title'] = str(top.Name) if top is not None else ''
    except Exception:
        info['window_title'] = ''
    if not light:
        info['hwnd'] = int(safe(lambda: el.NativeWindowHandle or 0, 0))
        info['is_enabled'] = bool(safe(lambda: el.IsEnabled, True))
    return info


# ------------------------------------------------------------------ 捕获（鼠标下元素 + 父链）

def _is_self_highlight_window(el) -> bool:
    """防御：跳过全局高亮窗口与捕获模式窗口（自家窗口不应出现在捕获结果中）"""
    try:
        hwnd = el.NativeWindowHandle or 0
        if not hwnd:
            return False
        import win32gui

        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        # 捕获模式窗口（全屏快照模态）与全局高亮窗口都属自家，需跳过
        return title in ('EasycodeHighlight', 'EasycodeCapture') or cls == 'EasycodeCaptureWindow'
    except Exception:
        return False


def inspect_point(x: int, y: int, with_ancestors: bool = False) -> dict:
    """捕获主入口：鼠标下最深元素（+可选父链）。
    ⚡ with_ancestors=False（悬停识别默认）：只取最深元素 5 个 COM 调用——
    父链提取每层 5 个调用 ×3 层，在浏览器/复杂应用上单次可达数秒，是"悬停识别超时"的主因。"""
    auto = _uia()
    if auto is None:
        return {'available': False, 'control': None, 'ancestors': []}
    try:
        el = auto.ControlFromPoint(int(x), int(y))
        # 防御：跳过自家高亮窗口（最多向上 4 层）
        for _ in range(4):
            if el is None:
                break
            if not _is_self_highlight_window(el):
                break
            try:
                el = el.GetParentControl()
            except Exception:
                el = None
        if el is None:
            return {'available': True, 'control': None, 'ancestors': []}
    except Exception as e:
        logger.warning('UIA ControlFromPoint 失败: %s', e)
        return {'available': False, 'control': None, 'ancestors': []}

    info = _element_info(el, light=True)

    ancestors = []
    if with_ancestors:
        parent = el
        for _ in range(_ANCESTOR_DEPTH):
            try:
                parent = parent.GetParentControl()
            except Exception:
                break
            if parent is None:
                break
            pinfo = _element_info(parent, light=True)
            pinfo['depth'] = len(ancestors)
            ancestors.append(pinfo)

    return {'available': True, 'control': info, 'ancestors': ancestors}


def inspect_point_candidates(
    x: int,
    y: int,
    *,
    expected_hwnd: int = 0,
    exclude_process_ids: set[int] | None = None,
    max_depth: int = 20,
) -> list[dict]:
    """Resolve one Windows point into deepest-first UIA candidates.

    Unlike the legacy hover inspector this is a bounded, one-shot operation.
    It records a complete top-level-to-candidate path for every selectable
    ancestor and refuses elements outside the explicitly selected window.
    """

    if not expected_hwnd and exclude_process_ids:
        expected_hwnd = _window_at_point_excluding(
            int(x), int(y), {int(value) for value in exclude_process_ids if int(value) > 0},
        )
        if not expected_hwnd:
            return []

    auto = _uia()
    if auto is None:
        return []
    target_chain: list[object] = []
    cached_info: dict[int, dict] = {}
    try:
        if expected_hwnd and getattr(auto, 'ControlFromHandle', None) is not None:
            try:
                target_chain, cached_info = _cached_target_chain(
                    int(expected_hwnd), int(x), int(y), max_depth=max_depth,
                )
            except Exception as exc:
                logger.debug('UIA 批量缓存命中不可用，回退兼容遍历: %s', exc)
                root = auto.ControlFromHandle(int(expected_hwnd))
                if root is None:
                    return []
                target_chain = [root]
                cursor = root
                for _ in range(max(1, min(64, int(max_depth))) - 1):
                    try:
                        children = cursor.GetChildren()
                    except Exception:
                        break
                    containing = []
                    for child in children or []:
                        info = _element_info(child, light=True)
                        rect = info.get('rect') or []
                        if len(rect) != 4 or not (rect[0] <= x < rect[2] and rect[1] <= y < rect[3]):
                            continue
                        area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
                        containing.append((area, child))
                    if not containing:
                        break
                    cursor = min(containing, key=lambda item: item[0])[1]
                    target_chain.append(cursor)
            if not target_chain:
                return []
            current = target_chain[-1]
            top = target_chain[0]
        else:
            current = auto.ControlFromPoint(int(x), int(y))
            if current is None or _is_self_highlight_window(current):
                return []
            top = current.GetTopLevelControl()
            top_hwnd = int(getattr(top, 'NativeWindowHandle', 0) or 0) if top is not None else 0
            if expected_hwnd and top_hwnd != int(expected_hwnd):
                return []
    except Exception as exc:
        logger.warning('UIA 控件点选失败: %s', exc)
        return []

    chain: list[tuple[object, dict]] = []
    if target_chain:
        chain = [
            (element, cached_info.get(id(element)) or _element_info(element, light=True))
            for element in reversed(target_chain)
        ]
    else:
        cursor = current
        for _ in range(max(1, min(64, int(max_depth)))):
            if cursor is None:
                break
            info = _element_info(cursor, light=True)
            rect = info.get('rect') or []
            if len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1]:
                chain.append((cursor, info))
            if cursor is top or str(info.get('control_type') or '') == 'window':
                break
            try:
                cursor = cursor.GetParentControl()
            except Exception:
                break

    if not chain:
        return []
    top_to_leaf = [info for _, info in reversed(chain)]
    candidates: list[dict] = []
    for index, (_, info) in enumerate(chain):
        path_length = len(chain) - index
        item = dict(info)
        item['ancestor_path'] = [
            {
                'name': str(level.get('name') or ''),
                'automation_id': str(level.get('automation_id') or ''),
                'class_name': str(level.get('class_name') or ''),
                'control_type': str(level.get('control_type') or ''),
            }
            for level in top_to_leaf[:path_length]
        ]
        candidates.append(item)
    return candidates


def _window_at_point_excluding(x: int, y: int, excluded_process_ids: set[int]) -> int:
    """Return the first visible top-level window under a point, excluding hosts.

    The frozen-capture overlay is intentionally topmost. Hiding it before every
    UIA probe creates a visible flash and a fixed delay; resolving the first
    underlying top-level window in z-order keeps the overlay stable while still
    binding UIA traversal to the window represented by the frozen frame.
    """

    try:
        import win32con
        import win32gui
        import win32process
    except Exception:
        return 0

    result = 0

    def visit(hwnd: int, _extra: object) -> bool:
        nonlocal result
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            # IME/pen/tooltip surfaces can be technically visible and cover the
            # screen while deliberately passing pointer input through. They do
            # not represent the application shown in the frozen frame.
            ex_style = int(win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) or 0)
            if ex_style & int(win32con.WS_EX_TRANSPARENT):
                return True
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if int(process_id or 0) in excluded_process_ids:
                return True
            left, top, right, bottom = (int(value) for value in win32gui.GetWindowRect(hwnd))
            if right <= left or bottom <= top or not (left <= x < right and top <= y < bottom):
                return True
            result = int(hwnd)
            return False
        except Exception:
            return True

    try:
        # EnumWindows walks top-level windows in z-order (topmost first).
        win32gui.EnumWindows(visit, None)
    except Exception:
        return 0
    return result


def _cached_target_chain(
    hwnd: int,
    x: int,
    y: int,
    *,
    max_depth: int,
) -> tuple[list[object], dict[int, dict]]:
    """Descend an explicit UIA root with one cached property batch per level.

    ``uiautomation.Control.GetChildren`` followed by five Python properties per
    child turns every level into many provider COM round trips. The native UIA
    ``FindAllBuildCache`` call returns the same direct children with the minimal
    selector fields already cached. A compatibility fallback remains in the
    caller for providers or library builds that do not expose build-cache APIs.
    """

    import uiautomation.uiautomation as native

    client = native._AutomationClient.instance()
    request = client.IUIAutomation.CreateCacheRequest()
    request.TreeScope = 1  # TreeScope_Element: cache only each returned element.
    for property_id in (
        native.PropertyId.BoundingRectangleProperty,
        native.PropertyId.ControlTypeProperty,
        native.PropertyId.NameProperty,
        native.PropertyId.AutomationIdProperty,
        native.PropertyId.ClassNameProperty,
        native.PropertyId.NativeWindowHandleProperty,
    ):
        request.AddProperty(property_id)
    condition = client.IUIAutomation.CreateTrueCondition()
    root = client.IUIAutomation.ElementFromHandleBuildCache(int(hwnd), request)
    if root is None:
        return [], {}

    def info(element, window_title: str = '') -> dict:
        rect = element.CachedBoundingRectangle
        control_id = int(element.CachedControlType or 0)
        return {
            'name': str(element.CachedName or ''),
            'control_type': str(native.ControlTypeNames.get(control_id, '')).replace('Control', '').lower(),
            'automation_id': str(element.CachedAutomationId or ''),
            'class_name': str(element.CachedClassName or ''),
            'rect': [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)],
            'window_title': window_title,
        }

    root_info = info(root)
    root_info['window_title'] = root_info['name']
    chain: list[object] = [root]
    infos: dict[int, dict] = {id(root): root_info}
    cursor = root
    for _ in range(max(1, min(64, int(max_depth))) - 1):
        children = cursor.FindAllBuildCache(_TREESCOPE_CHILDREN, condition, request)
        containing: list[tuple[int, object, dict]] = []
        for index in range(int(children.Length or 0)):
            child = children.GetElement(index)
            child_info = info(child, root_info['name'])
            rect = child_info['rect']
            if not (rect[0] <= x < rect[2] and rect[1] <= y < rect[3]):
                continue
            area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
            containing.append((area, child, child_info))
        if not containing:
            break
        _, cursor, cursor_info = min(containing, key=lambda item: item[0])
        chain.append(cursor)
        infos[id(cursor)] = cursor_info
    return chain, infos


# ------------------------------------------------------------------ UIA 选择器查找

def _normalize_text(s) -> str:
    """比较前归一化：\xa0/换行/制表/连续空格 → 单空格（控件名常含这些字符，精确比较必失配）"""
    return ' '.join(str(s or '').split())


def _element_matches(el, by: str, target: str) -> bool:
    if by == 'uia_name':
        return _normalize_text(el.Name) == _normalize_text(target)
    if by == 'uia_type':
        t = (el.ControlTypeName or '').replace('Control', '').strip().lower()
        return t == target.strip().lower()
    if by == 'uia_id':
        return (el.AutomationId or '').strip() == target
    if by == 'uia_class':
        return (el.ClassName or '').strip() == target
    return False


def _find_in_subtree(base, by: str, target: str, deadline: float | None = None, index: int = 0):
    """BFS 遍历单次树快照并返回第 index 个匹配元素；先检查 base 自身。
    ⚡ deadline 感知：遍历中每 200 节点检查一次，超时立即中断（超时严格生效，
    单轮遍历不再拖过 deadline —— 修复"超时 5000ms 实际 24s"问题）。"""
    def _expired():
        return deadline is not None and time.time() > deadline

    wanted = max(0, int(index or 0))
    seen = 0
    try:
        if _element_matches(base, by, target):
            if seen == wanted:
                return base
            seen += 1
    except Exception:
        pass
    queue = [base]
    visited = 0
    while queue and visited < _MAX_FIND_WALK:
        if visited % 200 == 0 and _expired():
            return None
        node = queue.pop(0)
        visited += 1
        try:
            children = node.GetChildren()
        except Exception:
            continue
        for child in children:
            try:
                if _element_matches(child, by, target):
                    if seen == wanted:
                        return child
                    seen += 1
            except Exception:
                pass
            queue.append(child)
    return None


def _find_window_in_subtree(base, window_title: str, deadline: float | None = None):
    """BFS 找名称匹配的顶层元素（不限定 WindowControl：任务栏等自绘顶层是 Pane"桌面 1"；
    deadline 感知防单轮拖过超时）"""
    queue = [base]
    visited = 0
    while queue and visited < _MAX_FIND_WALK:
        if visited % 200 == 0 and deadline is not None and time.time() > deadline:
            return None
        node = queue.pop(0)
        visited += 1
        try:
            children = node.GetChildren()
        except Exception:
            continue
        for child in children:
            try:
                if (child.Name or '').strip() == window_title:
                    return child
            except Exception:
                pass
            queue.append(child)
    return None


def find_control(
    window_title: str = '',
    by: str = 'uia_name',
    target: str = '',
    index: int = 0,
    timeout_ms: int = 3000,
) -> dict | None:
    """UIA 查找：按窗口名定位窗口后子树匹配（by 支持 uia_name/uia_type/uia_id/uia_class），取第 index 个。
    ⚡ 原生 COM 优先（PropertyCondition + FindFirst，毫秒级）；不支持的属性/归一化特殊场景回退 Python BFS；
    总耗时严格 ≤ timeout_ms（Python 兜底使用剩余预算）。"""
    target = (target or '').strip()
    if not target:
        return None
    t0 = time.time()
    # 原生路径优先（成熟 RPA 同款，一次 COM 调用）
    info = find_control_native(
        window_title=window_title, by=by, target=target, index=index, timeout_ms=timeout_ms
    )
    if info is not None:
        return info
    # Python BFS 兜底（原生不可用 / 属性未映射 / 名称内部空白等精确匹配失配场景；剩余预算）
    remaining_ms = max(0, int(timeout_ms or 0) - int((time.time() - t0) * 1000))
    if remaining_ms <= 0:
        return None
    auto = _uia()
    if auto is None:
        return None
    try:
        index = max(0, int(index or 0))
    except (TypeError, ValueError):
        index = 0
    deadline = time.time() + remaining_ms / 1000.0
    while time.time() < deadline:
        try:
            root = auto.GetRootControl()
            if window_title:
                base = _find_window_in_subtree(root, window_title, deadline)
                if base is None:
                    return None
            else:
                base = root
            match = _find_in_subtree(base, by, target, deadline, index=index)
            if match is not None:
                info = _element_info(match)
                info['match_index'] = index
                return info
        except Exception as e:
            logger.warning('UIA 查找异常: %s', e)
        time.sleep(0.05)
    return None


# ------------------------------------------------------------------ 原生 UIA COM 查找（成熟 RPA 同款方案）
# 借鉴 UiPath/影刀/UiBot 的 UIA 模式底层：PropertyCondition + FindFirst/FindAll。
# 树遍历与属性匹配在 UIA 内部 C++ 层完成，一次 COM 调用返回结果（全桌面通常 <100ms），
# 而非 Python 逐节点 BFS（每节点 2~4 次 COM 往返，数万次往返 = 数十秒）。

def _native_client():
    """原生 IUIAutomation COM 接口（uiautomation 库底层即 comtypes 直调，直接复用）"""
    try:
        _ensure_com()
        from uiautomation.uiautomation import _AutomationClient

        return _AutomationClient.instance().IUIAutomation
    except Exception:
        return None


def _native_wrap(el):
    """原生元素指针 → 现有 Control 包装（复用 _element_info 的属性提取）"""
    try:
        from uiautomation import Control

        return Control.CreateControlFromElement(el)
    except Exception:
        return None


# 常用 ControlType 字符串 → UIA ControlType 枚举值（不足的走 Python BFS 兜底）
_CONTROL_TYPE_IDS = None


def _control_type_id(ctype_str: str):
    global _CONTROL_TYPE_IDS
    t = (ctype_str or '').strip().lower()
    if not t:
        return None
    if _CONTROL_TYPE_IDS is None:
        try:
            from uiautomation import ControlType

            _CONTROL_TYPE_IDS = {
                'button': ControlType.ButtonControl,
                'checkbox': ControlType.CheckBoxControl,
                'combobox': ControlType.ComboBoxControl,
                'custom': ControlType.CustomControl,
                'edit': ControlType.EditControl,
                'group': ControlType.GroupControl,
                'list': ControlType.ListControl,
                'listitem': ControlType.ListItemControl,
                'menuitem': ControlType.MenuItemControl,
                'pane': ControlType.PaneControl,
                'radiobutton': ControlType.RadioButtonControl,
                'splitbutton': ControlType.SplitButtonControl,
                'tab': ControlType.TabControl,
                'text': ControlType.TextControl,
                'tree': ControlType.TreeControl,
                'window': ControlType.WindowControl,
            }
        except Exception:
            _CONTROL_TYPE_IDS = {}
    return _CONTROL_TYPE_IDS.get(t)


def _property_condition(iuia, by: str, target: str):
    """by → UIA 属性条件（uia_name/uia_id/uia_class/uia_type）；不支持的返回 None"""
    try:
        from uiautomation import PropertyId
    except Exception:
        return None
    if by == 'uia_name':
        return iuia.CreatePropertyCondition(PropertyId.NameProperty, target)
    if by == 'uia_id':
        return iuia.CreatePropertyCondition(PropertyId.AutomationIdProperty, target)
    if by == 'uia_class':
        return iuia.CreatePropertyCondition(PropertyId.ClassNameProperty, target)
    if by == 'uia_type':
        type_id = _control_type_id(target)
        if type_id is None:
            return None
        return iuia.CreatePropertyCondition(PropertyId.ControlTypeProperty, type_id)
    return None


def find_control_native(
    window_title: str = '',
    by: str = 'uia_name',
    target: str = '',
    index: int = 0,
    timeout_ms: int = 3000,
) -> dict | None:
    """原生 UIA COM 查找（成熟 RPA 同款）：PropertyCondition + FindFirst/FindAll。
    窗口作用域一次定位（找不到回退全桌面并记日志），目标查找一次 COM 调用；
    deadline 严格生效（每次调用毫秒级，超时循环重试）。"""
    iuia = _native_client()
    if iuia is None:
        return None
    target = (target or '').strip()
    if not target:
        return None
    cond = _property_condition(iuia, by, target)
    if cond is None:
        return None  # 不支持的属性/类型 → 交给 Python BFS 兜底
    try:
        index = max(0, int(index or 0))
    except (TypeError, ValueError):
        index = 0
    deadline = time.time() + max(0, float(timeout_ms or 0)) / 1000.0
    while time.time() < deadline:
        try:
            root = iuia.GetRootElement()
            base = root
            if window_title:
                try:
                    from uiautomation import ControlType, PropertyId

                    # ⚡ 顶层元素定位用 Children 作用域（窗口/任务栏/桌面都是根的直接子级，
                    # 不递归遍历子树 —— 全桌面 Subtree 会被慢提供方（如任务栏）拖到数秒）
                    wcond = iuia.CreateAndCondition(
                        iuia.CreatePropertyCondition(PropertyId.ControlTypeProperty, ControlType.WindowControl),
                        iuia.CreatePropertyCondition(PropertyId.NameProperty, window_title),
                    )
                    w = root.FindFirst(_TREESCOPE_CHILDREN, wcond)
                    if w is None:
                        w = root.FindFirst(_TREESCOPE_CHILDREN,
                                           iuia.CreatePropertyCondition(PropertyId.NameProperty, window_title))
                    if w:
                        base = w
                    else:
                        # ⚡ 窗口未找到：不再回退全桌面原生查找（交由 Python BFS 兜底，deadline 中断）
                        logger.warning('指定窗口 [%s] 未找到，交由 Python BFS 兜底', window_title)
                        return None
                except Exception as e:
                    logger.warning('窗口作用域定位异常: %s', e)
                    return None
            if index == 0:
                el = base.FindFirst(_TREESCOPE_SUBTREE, cond)
            else:
                el = None
                try:
                    arr = base.FindAll(_TREESCOPE_SUBTREE, cond)
                    if arr and arr.Length > index:
                        el = arr.GetElement(index)
                except Exception as e:
                    logger.warning('FindAll 取第 %d 个失败: %s', index, e)
            if el:
                ctrl = _native_wrap(el)
                if ctrl is not None:
                    info = _element_info(ctrl, light=False)
                    info['matched_by'] = 'native'
                    return info
        except Exception as e:
            logger.warning('UIA 原生查找异常: %s', e)
        time.sleep(0.05)
    return None


# ------------------------------------------------------------------ 祖先链定位（捕获时记录路径，执行时逐级下降）

_ANCESTOR_PATH_MAX = 20   # 祖先链最长深度（顶层窗口 → 控件）

def extract_ancestor_path_at(x: int, y: int, max_depth: int = _ANCESTOR_PATH_MAX) -> list:
    """捕获时提取鼠标下控件的祖先链（顶层窗口 → 控件，逐级 {name/control_type/automation_id/class_name}）。
    执行时沿链逐级下降定位：O(深度 × 每级子节点数)，毫秒级且不会错位到同名控件。
    copy 一次性操作（非悬停轮询路径），几十~几百毫秒可接受。"""
    auto = _uia()
    if auto is None:
        return []
    try:
        el = auto.ControlFromPoint(int(x), int(y))
        # 防御：跳过自家高亮窗口（覆盖层会被 ControlFromPoint 命中）
        for _ in range(4):
            if el is None:
                return []
            if not _is_self_highlight_window(el):
                break
            try:
                el = el.GetParentControl()
            except Exception:
                el = None
        if el is None:
            return []
    except Exception:
        return []

    path = []
    cur = el
    for _ in range(max_depth):
        # ⚡ 首级是控件自身（父链 + 自身 = 完整路径；缺失自身级时逐级定位会停在容器上）
        try:
            level = {
                'control_type': (cur.ControlTypeName or '').replace('Control', '').strip().lower(),
                'name': str(cur.Name or ''),
                'automation_id': str(cur.AutomationId or ''),
                'class_name': str(cur.ClassName or ''),
            }
        except Exception:
            break
        path.append(level)
        if level['control_type'] == 'window':
            break  # 收集到顶层窗口为止
        try:
            parent = cur.GetParentControl()
        except Exception:
            break
        if parent is None:
            break
        cur = parent
    path.reverse()  # 顶层窗口在前
    return path


def _match_best_child(children, level: dict):
    """在子节点中按 自动化ID → 类名 → 名称 匹配目标层级（归一化比较）；
    仅当该级没有任何身份属性（id/class/name 全空）时才用类型兜底，
    避免 name 不匹配时错配到任意同类型兄弟节点。"""
    want_id = _normalize_text(level.get('automation_id'))
    want_cls = _normalize_text(level.get('class_name'))
    want_name = _normalize_text(level.get('name'))
    want_type = _normalize_text(level.get('control_type'))
    for child in children:
        try:
            if want_id and _normalize_text(child.AutomationId) == want_id:
                return child
        except Exception:
            pass
    for child in children:
        try:
            if want_cls and _normalize_text(child.ClassName) == want_cls:
                return child
        except Exception:
            pass
    for child in children:
        try:
            if want_name and _normalize_text(child.Name) == want_name:
                return child
        except Exception:
            pass
    if not (want_id or want_cls or want_name) and want_type:
        for child in children:
            try:
                ctype = (child.ControlTypeName or '').replace('Control', '').strip().lower()
                if _normalize_text(ctype) == want_type:
                    return child
            except Exception:
                pass
    return None


def _find_level_native(iuia, parent_el, level: dict):
    """祖先链单级定位：子节点 FindFirst(Children, 单属性条件)。
    属性优先级 自动化ID → 类名 → 名称 → 类型（id/class 最稳定，避免动态 name 失配）；
    一次 COM 调用命中本级。"""
    try:
        from uiautomation import PropertyId
    except Exception:
        return None
    aid = _normalize_text(level.get('automation_id'))
    if aid:
        return parent_el.FindFirst(_TREESCOPE_CHILDREN, iuia.CreatePropertyCondition(PropertyId.AutomationIdProperty, aid))
    cls = _normalize_text(level.get('class_name'))
    if cls:
        return parent_el.FindFirst(_TREESCOPE_CHILDREN, iuia.CreatePropertyCondition(PropertyId.ClassNameProperty, cls))
    name = _normalize_text(level.get('name'))
    if name:
        return parent_el.FindFirst(_TREESCOPE_CHILDREN, iuia.CreatePropertyCondition(PropertyId.NameProperty, name))
    type_id = _control_type_id(level.get('control_type'))
    if type_id:
        return parent_el.FindFirst(_TREESCOPE_CHILDREN, iuia.CreatePropertyCondition(PropertyId.ControlTypeProperty, type_id))
    return None


def find_control_by_rect(rect, expect_name: str = '', expect_aid: str = '', expect_type: str = '') -> dict | None:
    """位置锚点定位：rect 中心 ControlFromPoint 命中 + 身份校验（name/automation_id/type 任一归一化匹配）。
    ⚡ 对固定位置控件（任务栏/桌面图标等 UIA 提供方慢、树遍历不可靠的场景）绕开树遍历，
    一次 COM 调用毫秒级；窗口移动/控件变化导致身份不匹配时返回 None（由调用方回退树查找）。"""
    if not rect or len(rect) != 4:
        return None
    auto = _uia()
    if auto is None:
        return None
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    try:
        el = auto.ControlFromPoint(cx, cy)
        if el is None:
            return None
        el_name = _normalize_text(el.Name)
        el_aid = _normalize_text(el.AutomationId)
        matched = False
        if expect_name and el_name and _normalize_text(expect_name) == el_name:
            matched = True
        elif expect_aid and el_aid and _normalize_text(expect_aid) == el_aid:
            matched = True
        elif expect_type:
            t = (el.ControlTypeName or '').replace('Control', '').strip().lower()
            if t == str(expect_type).strip().lower():
                matched = True
        if not matched:
            return None
        info = _element_info(el, light=False)
        info['matched_by'] = 'rect'
        return info
    except Exception as e:
        logger.warning('位置锚点定位失败: %s', e)
        return None


def find_control_by_path(window_title: str = '', path: list | None = None, timeout_ms: int = 1500) -> dict | None:
    """沿祖先链逐级下降定位（捕获时记录的 path：顶层窗口 → 控件）。
    原生优先：窗口 FindFirst(Subtree) + 每级 FindFirst(Children) —— O(深度) 次 COM 调用，毫秒级；
    原生不可用时回退 Python 子节点扫描；任一级缺失即失败（调用方回退 BFS）。"""
    if not path:
        return None
    deadline = time.time() + max(0, float(timeout_ms or 0)) / 1000.0

    # ---- 原生路径（成熟 RPA 同款：逐级 FindFirst） ----
    iuia = _native_client()
    if iuia is not None:
        try:
            from uiautomation import PropertyId

            root = iuia.GetRootElement()
            cur = None
            wname = window_title or path[0].get('name', '')
            if wname:
                # ⚡ 顶层元素用 Children 作用域（根的直接子级，不递归遍历全桌面）：
                # 先试 And(Window, Name)，失败再 Name-only（任务栏等自绘顶层是 Pane"桌面 1"）
                try:
                    from uiautomation import ControlType

                    wcond = iuia.CreateAndCondition(
                        iuia.CreatePropertyCondition(PropertyId.ControlTypeProperty, ControlType.WindowControl),
                        iuia.CreatePropertyCondition(PropertyId.NameProperty, wname),
                    )
                    cur = root.FindFirst(_TREESCOPE_CHILDREN, wcond)
                except Exception:
                    cur = None
                if cur is None:
                    cur = root.FindFirst(_TREESCOPE_CHILDREN,
                                         iuia.CreatePropertyCondition(PropertyId.NameProperty, wname))
            if cur is None:
                logger.warning('祖先链顶层元素 [%s] 定位失败，回退 Python 实现', wname)
            else:
                ok = True
                for level in path[1:]:
                    nxt = _find_level_native(iuia, cur, level)
                    if nxt is None:
                        ok = False
                        break
                    cur = nxt
                if ok:
                    ctrl = _native_wrap(cur)
                    if ctrl is not None:
                        info = _element_info(ctrl, light=False)
                        info['matched_by'] = 'path'
                        return info
        except Exception as e:
            logger.warning('祖先链原生定位异常，回退 Python 实现: %s', e)

    # ---- Python 回退（逐级子节点扫描，deadline 感知） ----
    auto = _uia()
    if auto is None:
        return None
    while time.time() < deadline:
        try:
            root = auto.GetRootControl()
            cur = None
            if window_title:
                cur = _find_window_in_subtree(root, window_title, deadline)
            if cur is None and path:
                cur = _find_window_in_subtree(root, path[0].get('name', ''), deadline)
            if cur is None:
                return None  # 顶层窗口都定位不到：结构已变，交给 BFS 兜底
            ok = True
            for level in path[1:]:
                try:
                    children = cur.GetChildren()
                except Exception:
                    ok = False
                    break
                nxt = _match_best_child(children, level)
                if nxt is None:
                    ok = False
                    break
                cur = nxt
            if ok:
                info = _element_info(cur)
                info['matched_by'] = 'path'
                return info
        except Exception as e:
            logger.warning('UIA 祖先链定位异常: %s', e)
        time.sleep(0.05)
    return None


# ------------------------------------------------------------------ UIA 后台操作

def _resolve_action_element(info: dict, auto):
    """从目标窗口树重新取得元素引用，不依赖会被遮挡窗口劫持的 ControlFromPoint。"""
    deadline = time.time() + 1.5
    hwnd = int(info.get('hwnd') or 0)
    if hwnd:
        try:
            control_from_handle = getattr(auto, 'ControlFromHandle', None)
            if control_from_handle is not None:
                element = control_from_handle(hwnd)
                if element is not None:
                    return element
        except Exception:
            pass

    try:
        root = auto.GetRootControl()
    except Exception:
        return None
    path = info.get('_ancestor_path') or []
    if isinstance(path, list) and path:
        current = _find_window_in_subtree(root, path[0].get('name', ''), deadline)
        if current is not None:
            for level in path[1:]:
                try:
                    current = _match_best_child(current.GetChildren(), level)
                except Exception:
                    current = None
                if current is None:
                    break
            if current is not None:
                return current

    window_title = str(info.get('window_title') or '').strip()
    if not window_title:
        return None
    base = _find_window_in_subtree(root, window_title, deadline)
    if base is None:
        return None
    for by, value in (
        ('uia_id', info.get('automation_id')),
        ('uia_class', info.get('class_name')),
        ('uia_name', info.get('name')),
        ('uia_type', info.get('control_type')),
    ):
        value = str(value or '').strip()
        if value:
            # AutomationId / class 通常是实例级定位，不应沿用名称搜索产生的同名序号。
            index = 0 if by in ('uia_id', 'uia_class') else int(info.get('match_index') or 0)
            element = _find_in_subtree(base, by, value, deadline, index=index)
            if element is not None:
                return element
    return None

def perform_uia_action(info: dict, action: str, text: str = '', allow_physical_fallback: bool = False) -> dict:
    """对 UIA 元素执行操作（Invoke / 后台消息优先，物理回退必须显式授权）
    元素引用通过 rect 中心重新定位获得（info 是序列化信息）。"""
    auto = _uia()
    if auto is None:
        return {'ok': False, 'message': 'UIA 不可用'}
    rect = info.get('rect') or [0, 0, 0, 0]
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2

    if action == 'exists':
        return {'ok': True, 'message': '控件存在'}

    def _physical_click(cx, cy, clicks=1) -> dict:
        """真实鼠标点击；仅在项目显式授权后调用。"""
        if not _PHYSICAL_INPUT_LOCK.acquire(timeout=0.5):
            return {'ok': False, 'method': 'physical', 'message': '物理输入通道正被其他任务占用'}
        try:
            import pyautogui
            import win32con
            import win32gui

            original = pyautogui.position()
            hwnd = int(info.get('hwnd') or 0)
            if hwnd:
                root = int(win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd)
                if win32gui.IsIconic(root):
                    win32gui.ShowWindow(root, win32con.SW_RESTORE)
                if win32gui.GetForegroundWindow() != root:
                    win32gui.BringWindowToTop(root)
                    win32gui.SetForegroundWindow(root)
            try:
                pyautogui.click(int(cx), int(cy), clicks=clicks)
            finally:
                pyautogui.moveTo(int(original[0]), int(original[1]))
            return {
                'ok': True, 'method': 'physical',
                'message': f'物理点击 ({int(cx)}, {int(cy)})，已恢复鼠标位置',
            }
        except Exception as e:
            return {'ok': False, 'method': 'physical', 'message': f'物理点击失败: {e}'}
        finally:
            _PHYSICAL_INPUT_LOCK.release()

    el = _resolve_action_element(info, auto)
    if el is None:
        if action in ('click', 'double_click') and allow_physical_fallback:
            return _physical_click(cx, cy, 2 if action == 'double_click' else 1)
        return {'ok': False, 'message': '无法在绑定窗口的UIA树中重新定位目标元素，严格后台模式已阻止操作'}

    def _identity_matches(el, info: dict) -> bool:
        """重新定位元素与目标控件身份校验（name/automation_id 任一归一化匹配即视为一致；
        都不匹配说明 ControlFromPoint 点到了错误元素，不能继续用它的 pattern/句柄）"""
        try:
            el_name = _normalize_text(el.Name)
            el_aid = _normalize_text(el.AutomationId)
        except Exception:
            return True  # 属性读取失败不阻断（可能是受限元素）
        info_name = _normalize_text(info.get('name'))
        info_aid = _normalize_text(info.get('automation_id'))
        if info_name and el_name and info_name == el_name:
            return True
        if info_aid and el_aid and info_aid == el_aid:
            return True
        if info_name and el_name and info_name != el_name:
            return False
        if info_aid and el_aid and info_aid != el_aid:
            return False
        return True  # 双方都无有效身份信息时放行（避免误判）

    if action in ('click', 'double_click'):
        clicks = 2 if action == 'double_click' else 1
        if not _identity_matches(el, info):
            logger.warning(
                '重新定位元素与目标不一致（期望 name=%r aid=%r）',
                info.get('name'), info.get('automation_id'))
            if allow_physical_fallback:
                return _physical_click(cx, cy, clicks)
            return {'ok': False, 'message': '重新定位到的UIA元素与目标不一致，严格后台模式已阻止物理点击'}
        # 1) InvokePattern：UIA 注入，不占物理鼠标（任务栏/回收站等自绘控件的最佳方式）
        try:
            pat = el.GetPattern(auto.PatternId.InvokePattern)
            if pat is not None:
                pat.Invoke()
                if action == 'double_click':
                    pat.Invoke()
                return {'ok': True, 'message': f'UIA Invoke 触发控件 ({cx}, {cy})'}
            logger.warning('元素无 InvokePattern（%s），降级点击', _normalize_text(el.Name) or el.ControlTypeName or '?')
        except Exception as e:
            logger.warning('InvokePattern 获取/触发失败（%s）: %s', _normalize_text(el.Name) or '?', e)
        # 2) 有原生句柄 → 后台 PostMessage（传统 Win32 控件，多开友好）
        hwnd = info.get('hwnd') or 0
        if hwnd:
            from core.services.background_input import background_click

            result = background_click(hwnd, cx, cy, clicks=clicks)
            if result.get('ok'):
                return result
        # 3) 无原生句柄（自绘/WinUI/浏览器内元素）：PostMessage 到顶层窗口对这类控件
        #    基本无效（不处理合成鼠标消息，任务栏点不开的根因）→ 真实物理点击确保生效
        if not hwnd and allow_physical_fallback:
            result = _physical_click(cx, cy, clicks)
            if result.get('ok'):
                return result
        # 4) 有句柄但控件级点击失败 → 顶层窗口后台点击（传统应用多开兜底）
        try:
            top = el.GetTopLevelControl()
            top_hwnd = top.NativeWindowHandle if top else 0
        except Exception:
            top_hwnd = 0
        if top_hwnd:
            from core.services.background_input import background_click

            result = background_click(top_hwnd, cx, cy, clicks=clicks)
            if result.get('ok'):
                result['message'] = f'窗口后台点击兜底 ({cx}, {cy})；{result.get("message", "效果未验证")}'
                return result
        # 5) 最后手段：物理点击
        if allow_physical_fallback:
            try:
                clickable = el.GetClickablePoint()
                return _physical_click(int(clickable[0]), int(clickable[1]), clicks)
            except Exception as e:
                return {'ok': False, 'message': f'点击失败: {e}'}
        return {'ok': False, 'message': '控件不支持UIA Invoke或可靠后台消息，严格后台模式已阻止物理点击'}

    if action in ('get_text', 'get_value'):
        try:
            pat = el.GetPattern(auto.PatternId.ValuePattern)
            if pat is not None:
                val = pat.Value
                return {'ok': True, 'value': str(val), 'message': f'UIA 读取控件值: {val!r}'}
        except Exception:
            pass
        return {'ok': True, 'value': el.Name or '', 'message': f'UIA 读取控件名: {el.Name!r}'}

    if action == 'get_status':
        def _property(name: str):
            try:
                return getattr(el, name)
            except Exception:
                return None

        def _pattern(pattern_name: str):
            try:
                pattern_id = getattr(auto.PatternId, pattern_name)
                return el.GetPattern(pattern_id)
            except Exception:
                return None

        value_pattern = _pattern('ValuePattern')
        toggle_pattern = _pattern('TogglePattern')
        selection_pattern = _pattern('SelectionItemPattern')
        current_value = None
        editable = None
        if value_pattern is not None:
            try:
                current_value = str(value_pattern.Value)
            except Exception:
                pass
            try:
                editable = not bool(value_pattern.IsReadOnly)
            except Exception:
                editable = None
        if current_value is None:
            try:
                current_value = str(el.Name or '') or None
            except Exception:
                current_value = None
        checked = None
        if toggle_pattern is not None:
            try:
                # UIA ToggleState: 0=Off, 1=On, 2=Indeterminate.
                state = int(toggle_pattern.ToggleState)
                checked = True if state == 1 else False if state == 0 else None
            except Exception:
                pass
        selected = None
        if selection_pattern is not None:
            try:
                selected = bool(selection_pattern.IsSelected)
            except Exception:
                pass
        current_rect = _property('BoundingRectangle')
        if current_rect is not None:
            try:
                left, top, right, bottom = (
                    int(current_rect.left), int(current_rect.top),
                    int(current_rect.right), int(current_rect.bottom),
                )
            except Exception:
                left, top, right, bottom = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
        else:
            left, top, right, bottom = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
        offscreen = _property('IsOffscreen')
        return {
            'ok': True,
            'value': {
                'control_status.field.enabled': _property('IsEnabled'),
                'control_status.field.visible': None if offscreen is None else not bool(offscreen),
                'control_status.field.checked': checked,
                'control_status.field.selected': selected,
                'control_status.field.editable': editable,
                'control_status.field.focusable': _property('IsKeyboardFocusable'),
                'control_status.field.focused': _property('HasKeyboardFocus'),
                'control_status.field.current_value': current_value,
                'control_status.field.rect': {
                    'kind': 'rect', 'x': left, 'y': top,
                    'width': max(0, right - left), 'height': max(0, bottom - top),
                },
            },
            'message': '已读取控件状态',
        }

    if action == 'focus':
        try:
            el.SetFocus()
            return {'ok': True, 'message': '已聚焦控件'}
        except Exception as exc:
            return {'ok': False, 'message': f'该控件不支持聚焦: {exc}'}

    if action in ('set_value', 'select', 'toggle', 'scroll_into_view'):
        pattern_names = {
            'set_value': 'ValuePattern',
            'select': 'SelectionItemPattern',
            'toggle': 'TogglePattern',
            'scroll_into_view': 'ScrollItemPattern',
        }
        method_names = {
            'set_value': 'SetValue',
            'select': 'Select',
            'toggle': 'Toggle',
            'scroll_into_view': 'ScrollIntoView',
        }
        labels = {
            'set_value': '设置值',
            'select': '选择项目',
            'toggle': '切换开关',
            'scroll_into_view': '滚动到控件',
        }
        try:
            pattern_id = getattr(auto.PatternId, pattern_names[action])
            pattern = el.GetPattern(pattern_id)
            if pattern is None:
                return {'ok': False, 'message': f'该控件不支持{labels[action]}'}
            method = getattr(pattern, method_names[action])
            if action == 'set_value':
                method(text or '')
            else:
                method()
            return {'ok': True, 'message': f'已{labels[action]}'}
        except Exception as exc:
            return {'ok': False, 'message': f'{labels[action]}失败: {exc}'}

    if action == 'input_text':
        try:
            pat = el.GetPattern(auto.PatternId.ValuePattern)
            if pat is not None:
                pat.SetValue(text or '')
                return {'ok': True, 'message': f'UIA 写入文本: {text!r}'}
        except Exception:
            pass
        hwnd = info.get('hwnd') or 0
        if hwnd:
            from core.services.control_service import _set_control_text

            _set_control_text(hwnd, text or '')
            return {'ok': True, 'message': f'WM_SETTEXT 写入: {text!r}'}
        return {'ok': False, 'message': '该控件不支持文本输入'}

    if action == 'hover':
        from core.services.background_input import background_hover

        hwnd = info.get('hwnd') or 0
        result = background_hover(hwnd, cx, cy)
        if result.get('ok') or not allow_physical_fallback:
            return result
        import pyautogui

        pyautogui.moveTo(cx, cy)
        return {'ok': True, 'method': 'physical', 'message': f'后台悬停失败，已回退物理悬停 ({cx}, {cy})'}

    return {'ok': False, 'message': f'不支持的操作: {action}'}
