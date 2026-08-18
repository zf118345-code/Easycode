# tests/test_uia_service.py
# UIA 控件服务测试：纯函数（信息提取/距离/匹配/查找）+ 执行器 UIA 链路（mock uiautomation）
import pytest


class FakeUiaElement:
    """模拟 uiautomation 元素（最小属性集）"""

    def __init__(self, name='', control_type='ButtonControl', automation_id='', class_name='',
                 rect=None, hwnd=0, enabled=True, children=None, invoke=None, value=None):
        self.Name = name
        self.ControlTypeName = control_type
        self.AutomationId = automation_id
        self.ClassName = class_name
        self._rect = rect or (0, 0, 10, 10)
        self.NativeWindowHandle = hwnd
        self.IsEnabled = enabled
        self._children = children or []
        self._invoke = invoke
        self._value = value

    @property
    def BoundingRectangle(self):
        class R:
            pass
        r = R()
        r.left, r.top, r.right, r.bottom = self._rect
        return r

    def GetParentControl(self):
        return getattr(self, '_parent', None)

    def GetFirstChildControl(self):
        return self._children[0] if self._children else None

    def GetChildren(self):
        return self._children

    def GetPattern(self, pattern_id):
        if pattern_id == 10000 and self._invoke is not None:  # InvokePattern
            return self._invoke
        if pattern_id == 10002 and self._value is not None:  # ValuePattern
            return self._value
        return None

    def GetClickablePoint(self):
        return ((self._rect[0] + self._rect[2]) // 2, (self._rect[1] + self._rect[3]) // 2)


class FakeInvokePattern:
    def __init__(self):
        self.calls = 0

    def Invoke(self):
        self.calls += 1


class FakeValuePattern:
    def __init__(self, value=''):
        self.Value = value  # 与真实 uiautomation ValuePattern.Value 对齐
        self.set_calls = []

    def SetValue(self, text):
        self.set_calls.append(text)
        self.Value = text


# ========== 信息提取 / 距离 ==========

def test_element_info_extraction():
    from core.services.uia_service import _element_info

    el = FakeUiaElement(name='确定', control_type='ButtonControl', automation_id='btn_1', class_name='Button',
                        rect=(10, 20, 110, 60), hwnd=555, enabled=True)
    info = _element_info(el)
    assert info['name'] == '确定'
    assert info['control_type'] == 'button'
    assert info['automation_id'] == 'btn_1'
    assert info['class_name'] == 'Button'
    assert info['rect'] == [10, 20, 110, 60]
    assert info['hwnd'] == 555
    assert info['is_enabled'] is True


# ========== 匹配 ==========

def test_element_matches():
    from core.services.uia_service import _element_matches

    el = FakeUiaElement(name='开始游戏', control_type='ButtonControl', automation_id='start_btn', class_name='Button')
    assert _element_matches(el, 'uia_name', '开始游戏') is True
    assert _element_matches(el, 'uia_name', '其他') is False
    assert _element_matches(el, 'uia_type', 'button') is True
    assert _element_matches(el, 'uia_type', 'BUTTON') is True  # 大小写不敏感
    assert _element_matches(el, 'uia_id', 'start_btn') is True
    assert _element_matches(el, 'uia_class', 'Button') is True
    assert _element_matches(el, 'uia_name', '') is False


# ========== 子树查找（BFS） ==========

def test_find_in_subtree_bfs():
    from core.services.uia_service import _find_in_subtree

    target = FakeUiaElement(name='深层按钮', control_type='ButtonControl')
    mid = FakeUiaElement(name='容器', control_type='PaneControl', children=[target])
    root = FakeUiaElement(name='根', control_type='WindowControl', children=[mid])

    found = _find_in_subtree(root, 'uia_name', '深层按钮')
    assert found is target
    assert _find_in_subtree(root, 'uia_name', '不存在') is None


def test_inspect_point_skips_self_highlight_window(monkeypatch):
    """防御：捕获时跳过自家全局高亮窗口"""
    import core.services.uia_service as uia_mod

    highlight = FakeUiaElement(name='EasycodeHighlight', control_type='PaneControl', hwnd=999)
    real = FakeUiaElement(name='确定', control_type='ButtonControl', hwnd=123)
    highlight._parent = real

    class FakeAuto:
        ControlFromPoint = staticmethod(lambda x, y: highlight)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_is_self_highlight_window', lambda el: el is highlight)

    result = uia_mod.inspect_point(50, 50)
    assert result['available'] is True
    assert result['control']['name'] == '确定'


# ========== 执行器 UIA 链路 ==========

class FakeCtx:
    def __init__(self, variables=None):
        self.variables = variables or {}
        self.logs = []

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)


def make_node(params):
    from core.models import Node

    return Node(node_id='n', node_name='n', node_type='control', params=params)


def test_executor_uia_find_and_invoke(monkeypatch):
    """by=uia_name：走 UIA 查找，无 hwnd 元素点击走 Invoke（不占物理鼠标）"""
    from core.services import uia_service as uia_mod

    invoke = FakeInvokePattern()
    el = FakeUiaElement(name='开始', control_type='ButtonControl', rect=(10, 10, 110, 40), invoke=invoke)
    info = uia_mod._element_info(el)

    monkeypatch.setattr(uia_mod, 'find_control', lambda **kw: info)

    class FakeAuto:
        PatternId = type('P', (), {'InvokePattern': 10000, 'ValuePattern': 10002})
        ControlFromPoint = staticmethod(lambda x, y: el)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, 'available', lambda: True)

    from core.node_executors.base.control import ControlNodeExecutor

    ctx = FakeCtx()
    node = make_node({'action': 'click', 'by': 'uia_name', 'target': '开始'})
    result = ControlNodeExecutor().execute(node, ctx)
    assert result['success'] is True
    assert invoke.calls >= 1
    assert any('UIA' in log for log in ctx.logs)




def test_executor_uia_not_found_fails(monkeypatch):
    import core.node_executors.base.control as control_mod
    from core.services import uia_service as uia_mod

    monkeypatch.setattr(uia_mod, 'find_control', lambda **kw: None)

    ctx = FakeCtx()
    node = make_node({'action': 'click', 'by': 'uia_name', 'target': '不存在的按钮'})
    from core.node_executors.base.control import ControlNodeExecutor

    result = ControlNodeExecutor().execute(node, ctx)
    assert result['success'] is False
    assert any('未找到匹配控件' in log for log in ctx.logs)


# ========== 全局高亮服务 ==========

def test_highlight_render_calls_gdi(monkeypatch):
    """全局高亮：渲染调用 GDI 绘制（FillRect 清屏 + 每框 Rectangle，纯边框 2px 实线青色）"""
    import core.services.highlight_service as hs

    calls = {'fill': 0, 'rect': 0, 'pens': []}
    monkeypatch.setattr(hs.win32api, 'RGB', lambda r, g, b: (r, g, b))
    monkeypatch.setattr(hs.win32api, 'GetModuleHandle', lambda n: 12345)
    monkeypatch.setattr(hs.win32gui, 'CreateWindowEx', lambda *a, **k: 777)
    monkeypatch.setattr(hs.win32gui, 'SetLayeredWindowAttributes', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'ShowWindow', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'SetWindowPos', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'GetDC', lambda h: 1001)
    monkeypatch.setattr(hs.win32gui, 'ReleaseDC', lambda h, d: None)
    monkeypatch.setattr(hs.win32gui, 'CreateSolidBrush', lambda c: 1)
    monkeypatch.setattr(hs.win32gui, 'DeleteObject', lambda o: None)
    monkeypatch.setattr(hs.win32gui, 'FillRect', lambda dc, r, b: calls.update(fill=calls['fill'] + 1))
    monkeypatch.setattr(hs.win32gui, 'GetStockObject', lambda s: 2)
    monkeypatch.setattr(hs.win32gui, 'CreatePen', lambda style, w, c: calls['pens'].append((style, w, c)) or 3)
    monkeypatch.setattr(hs.win32gui, 'SelectObject', lambda dc, o: 0)
    monkeypatch.setattr(hs.win32gui, 'Rectangle', lambda dc, l, t, r, b: calls.update(rect=calls['rect'] + 1))

    service = hs.HighlightService()
    frames = [
        {'rect': [100, 100, 200, 140]},
        {'rect': [50, 50, 500, 400]},
    ]
    service.render(frames)

    assert calls['fill'] == 1
    assert calls['rect'] == 2
    assert calls['pens'][0][1] == 2          # 纯边框 2px
    assert calls['pens'][0][0] == 0          # PS_SOLID 实线
    assert calls['pens'][1] == calls['pens'][0]  # 所有框同一样式（无层级差异）


def test_highlight_skips_unchanged_frames(monkeypatch):
    """性能：frames 无变化时跳过重绘"""
    import core.services.highlight_service as hs

    draws = []
    monkeypatch.setattr(hs.win32api, 'RGB', lambda r, g, b: (r, g, b))
    monkeypatch.setattr(hs.win32api, 'GetModuleHandle', lambda n: 1)
    monkeypatch.setattr(hs.win32gui, 'CreateWindowEx', lambda *a, **k: 777)
    monkeypatch.setattr(hs.win32gui, 'SetLayeredWindowAttributes', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'ShowWindow', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'SetWindowPos', lambda *a, **k: None)
    monkeypatch.setattr(hs.win32gui, 'GetDC', lambda h: 1)
    monkeypatch.setattr(hs.win32gui, 'ReleaseDC', lambda h, d: None)
    monkeypatch.setattr(hs.win32gui, 'CreateSolidBrush', lambda c: 1)
    monkeypatch.setattr(hs.win32gui, 'DeleteObject', lambda o: None)
    monkeypatch.setattr(hs.win32gui, 'FillRect', lambda dc, r, b: draws.append('fill'))
    monkeypatch.setattr(hs.win32gui, 'GetStockObject', lambda s: 2)
    monkeypatch.setattr(hs.win32gui, 'CreatePen', lambda *a: 3)
    monkeypatch.setattr(hs.win32gui, 'SelectObject', lambda dc, o: 0)
    monkeypatch.setattr(hs.win32gui, 'Rectangle', lambda dc, l, t, r, b: draws.append('rect'))

    service = hs.HighlightService()
    frames = [{'rect': [10, 10, 20, 20]}]

    service.render(frames)
    service.render(frames)  # 相同 → 跳过
    assert draws.count('fill') == 1
    assert draws.count('rect') == 1

    # 变化 → 重绘
    service.render([{'rect': [11, 10, 20, 20], 'active': True, 'depth': 0}])
    assert draws.count('rect') == 2

    # 清空 → 销毁窗口
    service.render([])
    assert service._hwnd is None




# ========== 窗口作用域查找（uiautomation 2.0 无 FindControl，自行遍历） ==========

def test_find_window_in_subtree():
    from core.services.uia_service import _find_window_in_subtree

    btn = FakeUiaElement(name='最高', control_type='ComboBoxControl')
    win = FakeUiaElement(name='系统设置', control_type='WindowControl', children=[btn])
    other = FakeUiaElement(name='其他窗口', control_type='WindowControl')
    root = FakeUiaElement(name='根', control_type='PaneControl', children=[other, win])

    assert _find_window_in_subtree(root, '系统设置') is win
    assert _find_window_in_subtree(root, '不存在的窗口') is None


def test_find_control_scoped_to_window(monkeypatch):
    """窗口标题 → 在窗口子树内查找（不再全桌面遍历）；窗口不存在 → 回退全桌面"""
    import core.services.uia_service as uia_mod

    btn = FakeUiaElement(name='最高', control_type='ComboBoxControl', automation_id='cb1')
    win = FakeUiaElement(name='系统设置', control_type='WindowControl', children=[btn])
    root = FakeUiaElement(name='根', control_type='PaneControl', children=[win])

    class FakeAuto:
        GetRootControl = staticmethod(lambda: root)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_native_client', lambda: None)  # 测试 fake 树，禁用原生 COM 路径
    info = uia_mod.find_control(window_title='系统设置', by='uia_name', target='最高', timeout_ms=500)
    assert info is not None
    assert info['name'] == '最高'
    assert info['automation_id'] == 'cb1'

    # 窗口不存在 → 回退全桌面仍能命中
    info2 = uia_mod.find_control(window_title='不存在的窗口', by='uia_name', target='最高', timeout_ms=500)
    assert info2 is not None and info2['name'] == '最高'


# ========== 祖先链定位（捕获记录路径 → 执行逐级下降） ==========

def test_normalize_text_handles_inner_whitespace():
    from core.services.uia_service import _normalize_text

    assert _normalize_text(' 确定 ') == '确定'
    assert _normalize_text('开始\u00a0游戏') == '开始 游戏'      # \xa0 不间断空格
    assert _normalize_text('多行\n文本') == '多行 文本'
    assert _normalize_text('连续   空格') == '连续 空格'
    assert _normalize_text(None) == ''


def test_element_matches_uia_name_normalized():
    from core.services.uia_service import _element_matches

    el = FakeUiaElement(name='开始\u00a0游戏', control_type='ButtonControl')
    assert _element_matches(el, 'uia_name', '开始 游戏') is True  # 捕获值与运行值内部空白差异也能匹配
    assert _element_matches(el, 'uia_name', '开始游戏') is False


def test_find_in_subtree_matches_base_itself():
    """目标就是窗口/顶级元素本身时（BFS 起点）也能命中"""
    from core.services.uia_service import _find_in_subtree

    win = FakeUiaElement(name='系统设置', control_type='WindowControl')
    assert _find_in_subtree(win, 'uia_name', '系统设置') is win


def test_extract_ancestor_path_at(monkeypatch):
    """捕获时提取祖先链：控件 → 容器 → 顶层窗口，顶层在前"""
    import core.services.uia_service as uia_mod

    btn = FakeUiaElement(name='确定', control_type='ButtonControl', automation_id='btn_1')
    pane = FakeUiaElement(name='表单区', control_type='PaneControl', automation_id='pane_a')
    win = FakeUiaElement(name='主窗口', control_type='WindowControl', automation_id='win_1')
    btn._parent = pane
    pane._parent = win

    class FakeAuto:
        ControlFromPoint = staticmethod(lambda x, y: btn)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_is_self_highlight_window', lambda el: False)

    path = uia_mod.extract_ancestor_path_at(100, 100)
    assert path == [
        {'control_type': 'window', 'name': '主窗口', 'automation_id': 'win_1', 'class_name': ''},
        {'control_type': 'pane', 'name': '表单区', 'automation_id': 'pane_a', 'class_name': ''},
        {'control_type': 'button', 'name': '确定', 'automation_id': 'btn_1', 'class_name': ''},
    ]  # 顶层窗口在前，控件自身是末级（执行时逐级下降直到控件本身）


def test_extract_ancestor_path_skips_self_highlight(monkeypatch):
    """防御：ControlFromPoint 命中自家高亮窗口时向上跳过后再提取"""
    import core.services.uia_service as uia_mod

    btn = FakeUiaElement(name='确定', control_type='ButtonControl')
    hl = FakeUiaElement(name='EasycodeHighlight', control_type='PaneControl')
    win = FakeUiaElement(name='主窗口', control_type='WindowControl')
    btn._parent = win
    hl._parent = btn  # ControlFromPoint 命中覆盖层高亮窗口，向上跳过一层得到目标控件

    class FakeAuto:
        ControlFromPoint = staticmethod(lambda x, y: hl)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_is_self_highlight_window', lambda el: el is hl)

    path = uia_mod.extract_ancestor_path_at(100, 100)
    assert path and path[0]['control_type'] == 'window'
    assert path[0]['name'] == '主窗口'


def _path_tree():
    """构造 根→窗口→容器→按钮 的四层树，供逐级定位测试"""
    btn = FakeUiaElement(name='开始游戏', control_type='ButtonControl', automation_id='start_btn')
    pane = FakeUiaElement(name='主容器', control_type='PaneControl', automation_id='pane_a', children=[btn])
    win = FakeUiaElement(name='游戏窗口', control_type='WindowControl', children=[pane])
    root = FakeUiaElement(name='根', control_type='PaneControl', children=[win])
    return root, win, pane, btn


def test_find_control_by_path_hit(monkeypatch):
    """祖先链逐级下降：窗口→容器→按钮 命中"""
    import core.services.uia_service as uia_mod

    root, win, pane, btn = _path_tree()

    class FakeAuto:
        GetRootControl = staticmethod(lambda: root)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_native_client', lambda: None)  # 测试 fake 树，禁用原生 COM 路径

    path = [
        {'control_type': 'window', 'name': '游戏窗口', 'automation_id': '', 'class_name': ''},
        {'control_type': 'pane', 'name': '主容器', 'automation_id': 'pane_a', 'class_name': ''},
        {'control_type': 'button', 'name': '开始游戏', 'automation_id': 'start_btn', 'class_name': ''},
    ]
    info = uia_mod.find_control_by_path(path=path, timeout_ms=500)
    assert info is not None
    assert info['automation_id'] == 'start_btn'
    assert info['matched_by'] == 'path'


def test_find_control_by_path_middle_missing_returns_none(monkeypatch):
    """中间层级缺失（UI 结构变化）→ 返回 None，由调用方回退 BFS"""
    import core.services.uia_service as uia_mod

    root, win, pane, btn = _path_tree()

    class FakeAuto:
        GetRootControl = staticmethod(lambda: root)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_native_client', lambda: None)  # 测试 fake 树，禁用原生 COM 路径

    path = [
        {'control_type': 'window', 'name': '游戏窗口', 'automation_id': '', 'class_name': ''},
        {'control_type': 'pane', 'name': '不存在的容器', 'automation_id': '', 'class_name': ''},
        {'control_type': 'button', 'name': '开始游戏', 'automation_id': '', 'class_name': ''},
    ]
    assert uia_mod.find_control_by_path(path=path, timeout_ms=500) is None


def test_find_control_by_path_window_title_priority(monkeypatch):
    """显式 window_title 优先于 path 首级窗口名"""
    import core.services.uia_service as uia_mod

    root, win, pane, btn = _path_tree()
    other = FakeUiaElement(name='其他窗口', control_type='WindowControl', children=[FakeUiaElement(name='x', control_type='ButtonControl')])
    root._children = [other, win]

    class FakeAuto:
        GetRootControl = staticmethod(lambda: root)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    monkeypatch.setattr(uia_mod, '_native_client', lambda: None)  # 测试 fake 树，禁用原生 COM 路径

    path = [
        {'control_type': 'window', 'name': '游戏窗口', 'automation_id': '', 'class_name': ''},
        {'control_type': 'button', 'name': '开始游戏', 'automation_id': 'start_btn', 'class_name': ''},
    ]
    info = uia_mod.find_control_by_path(window_title='其他窗口', path=path, timeout_ms=500)
    assert info is None  # 显式窗口里没有该路径 → 定位失败（不跨窗口错配）


# ========== 原生 UIA COM 查找（成熟 RPA 方案） ==========

class FakeNativeCond:
    """模拟原生 PropertyCondition（记录属性 ID 与值）"""
    def __init__(self, prop, value):
        self.prop = prop
        self.value = value


class FakeAndCond:
    """模拟 AndCondition（两个子条件都满足才匹配）"""
    def __init__(self, a, b):
        self.a = a
        self.b = b


class FakeNativeElement:
    """模拟原生 IUIAutomationElement（FindFirst/FindAll 按条件匹配子元素）"""
    def __init__(self, name='', aid='', cls='', ctype=0, children=None):
        self._name = name
        self._aid = aid
        self._cls = cls
        self._ctype = ctype
        self._children = children or []

    def FindFirst(self, scope, cond):
        if scope == 2:  # Children
            for c in self._children:
                if _native_cond_matches(c, cond):
                    return c
            return None
        # Subtree：BFS
        queue = list(self._children)
        while queue:
            node = queue.pop(0)
            if _native_cond_matches(node, cond):
                return node
            queue.extend(node._children)
        return None

    def FindAll(self, scope, cond):
        found = []
        queue = list(self._children)
        while queue:
            node = queue.pop(0)
            if _native_cond_matches(node, cond):
                found.append(node)
            queue.extend(node._children)
        class FakeArr:
            pass
        arr = FakeArr()
        arr.Length = len(found)
        arr.GetElement = lambda i: found[i] if i < len(found) else None
        return arr


def _native_cond_matches(el, cond):
    if isinstance(cond, FakeAndCond):
        return _native_cond_matches(el, cond.a) and _native_cond_matches(el, cond.b)
    if cond.prop == 30005:
        return el._name == cond.value
    if cond.prop == 30011:
        return el._aid == cond.value
    if cond.prop == 30012:
        return el._cls == cond.value
    if cond.prop == 30003:
        return el._ctype == cond.value
    return False


class FakeNativeClient:
    """模拟原生 IUIAutomation：根元素 + 条件工厂"""
    def __init__(self, root):
        self._root = root

    def GetRootElement(self):
        return self._root

    def CreatePropertyCondition(self, prop, value):
        return FakeNativeCond(prop, value)

    def CreateAndCondition(self, c1, c2):
        return FakeAndCond(c1, c2)


def test_find_control_native_hit(monkeypatch):
    """原生查找：窗口作用域 + PropertyCondition 命中（不依赖 Python BFS）"""
    import core.services.uia_service as uia_mod
    from uiautomation import ControlType, PropertyId

    btn = FakeNativeElement(name='文件资源管理器 已固定', aid='Appid: Microsoft.Windows.Explorer', ctype=ControlType.ButtonControl)
    win = FakeNativeElement(name='任务栏', ctype=ControlType.WindowControl, children=[btn])
    root = FakeNativeElement(name='根', children=[win])

    client = FakeNativeClient(root)
    monkeypatch.setattr(uia_mod, '_native_client', lambda: client)
    monkeypatch.setattr(uia_mod, '_native_wrap', lambda el: _FakeCtrlWrap(el))

    info = uia_mod.find_control_native(window_title='任务栏', by='uia_name', target='文件资源管理器 已固定', timeout_ms=500)
    assert info is not None
    assert info['matched_by'] == 'native'


class _FakeCtrlWrap:
    """模拟 Control 包装（_element_info 的属性访问）"""
    def __init__(self, el):
        self._el = el

    @property
    def Name(self):
        return self._el._name

    @property
    def ControlTypeName(self):
        return 'ButtonControl'

    @property
    def AutomationId(self):
        return self._el._aid

    @property
    def ClassName(self):
        return self._el._cls

    @property
    def BoundingRectangle(self):
        class R:
            left, top, right, bottom = 0, 0, 10, 10
        return R()

    @property
    def NativeWindowHandle(self):
        return 0

    @property
    def IsEnabled(self):
        return True


def test_find_control_native_index_via_findall(monkeypatch):
    """原生查找：index>0 走 FindAll 取第 N 个"""
    import core.services.uia_service as uia_mod
    from uiautomation import ControlType

    b1 = FakeNativeElement(name='a', ctype=ControlType.ButtonControl)
    b2 = FakeNativeElement(name='a', ctype=ControlType.ButtonControl)
    root = FakeNativeElement(children=[b1, b2])

    client = FakeNativeClient(root)
    monkeypatch.setattr(uia_mod, '_native_client', lambda: client)
    monkeypatch.setattr(uia_mod, '_native_wrap', lambda el: _FakeCtrlWrap(el))

    info = uia_mod.find_control_native(by='uia_type', target='button', index=1, timeout_ms=500)
    assert info is not None and info['matched_by'] == 'native'


def test_find_control_prefers_native_then_bfs_fallback(monkeypatch):
    """find_control：原生命中直接返回；原生失败回退 Python BFS（fake 树）"""
    import core.services.uia_service as uia_mod
    from uiautomation import ControlType

    btn = FakeNativeElement(name='确定', ctype=ControlType.ButtonControl)
    root = FakeNativeElement(children=[btn])

    # 原生返回 None（找不到）→ 回退 Python BFS（fake uia 树命中）
    monkeypatch.setattr(uia_mod, 'find_control_native', lambda **kw: None)
    btn2 = FakeUiaElement(name='确定', control_type='ButtonControl')
    tree_root = FakeUiaElement(name='根', control_type='PaneControl', children=[btn2])

    class FakeAuto:
        GetRootControl = staticmethod(lambda: tree_root)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    info = uia_mod.find_control(by='uia_name', target='确定', timeout_ms=500)
    assert info is not None and info['name'] == '确定'


def test_bfs_deadline_interrupts(monkeypatch):
    """BFS 遍历超时立即中断（单轮遍历不再拖过 deadline —— 超时严格生效）"""
    import core.services.uia_service as uia_mod

    # 构造一个大 fake 树（目标在末尾）
    nodes = [FakeUiaElement(name=f'n{i}', control_type='PaneControl') for i in range(500)]
    for i, n in enumerate(nodes[:-1]):
        n._children = [nodes[i + 1]]
    target = FakeUiaElement(name='目标', control_type='ButtonControl')
    nodes[-1]._children = [target]

    import time
    t0 = time.time()
    # deadline 已过期 → BFS 应立即返回 None（不遍历整棵树）
    result = uia_mod._find_in_subtree(nodes[0], 'uia_name', '目标', deadline=time.time() - 1)
    assert result is None
    assert time.time() - t0 < 1.0  # 立即中断，没有全树遍历


# ========== 点击链路：身份校验 + 无 hwnd 物理兜底 ==========

def test_perform_action_identity_mismatch_uses_physical_click(monkeypatch):
    """重新定位元素与目标不一致（点到了错误元素）→ 不再用错误元素的 pattern，改物理点击"""
    import core.services.uia_service as uia_mod

    wrong = FakeUiaElement(name='别的按钮', control_type='ButtonControl', invoke=FakeInvokePattern())
    info = {'name': '目标按钮', 'automation_id': 'target_1', 'rect': [10, 10, 110, 40]}

    class FakeAuto:
        PatternId = type('P', (), {'InvokePattern': 10000, 'ValuePattern': 10002})
        ControlFromPoint = staticmethod(lambda x, y: wrong)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    clicked = []
    import pyautogui as real_pyautogui
    monkeypatch.setattr(real_pyautogui, 'click', lambda x, y, clicks=1: clicked.append((x, y, clicks)))

    result = uia_mod.perform_uia_action(info, 'click')
    assert result['ok'] is True
    assert '物理点击' in result['message']
    assert clicked == [(60, 25, 1)]  # rect 中心 (60, 25)，未使用错误元素的 Invoke


def test_perform_action_no_hwnd_falls_back_to_physical(monkeypatch):
    """无原生句柄（自绘/WinUI）且 Invoke 不可用 → 直接物理点击（不投递无效的顶层窗口 PostMessage）"""
    import core.services.uia_service as uia_mod

    el = FakeUiaElement(name='任务栏按钮', control_type='ButtonControl', rect=(10, 10, 50, 40))  # invoke=None → 无 InvokePattern
    info = {'name': '任务栏按钮', 'automation_id': '', 'hwnd': 0, 'rect': [10, 10, 50, 40]}

    class FakeAuto:
        PatternId = type('P', (), {'InvokePattern': 10000, 'ValuePattern': 10002})
        ControlFromPoint = staticmethod(lambda x, y: el)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    clicked = []
    import pyautogui as real_pyautogui
    monkeypatch.setattr(real_pyautogui, 'click', lambda x, y, clicks=1: clicked.append((x, y, clicks)))

    result = uia_mod.perform_uia_action(info, 'click')
    assert result['ok'] is True
    assert '物理点击' in result['message']
    assert clicked == [(30, 25, 1)]
    # 未调用 PostMessage（background_click 不应被调用）
    from core.services import background_input
    monkeypatch.setattr(background_input, 'background_click', lambda *a, **k: (_ for _ in ()).throw(AssertionError('不应走 PostMessage')))


def test_perform_action_hwnd_keeps_postmessage(monkeypatch):
    """有原生句柄且 Invoke 不可用 → 保留后台 PostMessage（传统 Win32 控件，多开友好）"""
    import core.services.uia_service as uia_mod

    el = FakeUiaElement(name='确定', control_type='ButtonControl', rect=(10, 10, 110, 40))
    info = {'name': '确定', 'automation_id': '', 'hwnd': 12345, 'rect': [10, 10, 110, 40]}

    class FakeAuto:
        PatternId = type('P', (), {'InvokePattern': 10000, 'ValuePattern': 10002})
        ControlFromPoint = staticmethod(lambda x, y: el)

    monkeypatch.setattr(uia_mod, '_uia', lambda: FakeAuto())
    calls = []
    from core.services import background_input
    monkeypatch.setattr(
        background_input, 'background_click',
        lambda hwnd, x, y, clicks=1: calls.append((hwnd, x, y, clicks)) or {'ok': True, 'message': '后台点击窗口'})

    result = uia_mod.perform_uia_action(info, 'click')
    assert result['ok'] is True
    assert calls and calls[0][0] == 12345  # 用了控件句柄
