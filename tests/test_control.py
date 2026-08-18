# tests/test_control.py
# 控件节点：schema 断言 + 服务层选择器匹配 + 执行器（mock 控件服务，不依赖真实桌面）
import pytest

from core.params import ALL_PARAMS
from core.services.control_service import _class_type, matches


# ========== schema ==========

def test_schema_structure():
    ctrl = ALL_PARAMS['control']
    assert ctrl['label'] == '控件操作'
    assert ctrl['modes'] == ['workflow']  # 控件操作基于桌面应用，仅流程画布
    p = ctrl['params']
    assert set(p.keys()) == {'action', 'by', 'target', 'window_title', 'index', 'timeout', 'control_info'}
    assert p['action']['default'] == 'click'
    # 匹配成功操作精简为 点击/双击/悬停 三项
    assert [o['value'] for o in p['action']['options']] == ['click', 'double_click', 'hover']
    assert p['by']['default'] == 'uia_name'  # A1：默认 UIA 名称查找（与捕获工具一致）
    assert p['target']['type'] == 'capture_str'  # 只读 + 捕获/重置按钮
    assert p['control_info']['hidden'] is True   # 捕获完整信息存隐藏字段
    assert p['by']['hidden'] is True
    assert p['index']['default'] == 0
    assert p['timeout']['suffix'] == 'ms'


# ========== 服务层：类名 → 类型映射 ==========

@pytest.mark.parametrize('class_name,expected', [
    ('Button', 'button'),
    ('Edit', 'edit'),
    ('Static', 'text'),
    ('SysListView32', 'list'),
    ('ComboBoxEx32', 'combobox'),
    ('RICHEDIT50W', 'edit'),
    ('WindowsForms10.Button.app.0.378734a', 'button'),
    ('SomeCustomClass', 'somecustomclass'),  # 未知类名原样小写
])
def test_class_type_mapping(class_name, expected):
    assert _class_type(class_name) == expected


# ========== 服务层：选择器匹配（纯函数） ==========

INFO = {'class_name': 'Button', 'text': '确定', 'control_type': 'button', 'hwnd': 123}


@pytest.mark.parametrize('by,target,expected', [
    ('class_name', 'Button', True),
    ('class_name', 'Edit', False),
    ('text', '确定', True),
    ('text', ' 确定 ', True),   # target 与控件文本都 strip 后比较
    ('control_type', 'button', True),
    ('control_type', 'Button', True),   # 大小写不敏感
    ('hwnd', '123', True),
    ('class_name', '', False),   # 空 target 不匹配
    ('unknown_by', 'x', False),
])
def test_matches(by, target, expected):
    assert matches(INFO, by, target) is expected


def test_matches_text_trimming():
    # 控件文本首尾空白会 trim 后比较
    assert matches({'text': '  确定  '}, 'text', '确定') is True


# ========== 执行器 ==========

class FakeCtx:
    def __init__(self, variables=None):
        self.variables = variables or {}
        self.logs = []

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)


def make_node(params):
    from core.models import Node

    return Node(node_id='n', node_name='n', node_type='control', params=params)


def _executor():
    from core.node_executors.base.control import ControlNodeExecutor

    return ControlNodeExecutor()


def _fake_control(**overrides):
    info = {'hwnd': 1, 'class_name': 'Button', 'control_type': 'button', 'text': '确定', 'rect': [0, 0, 10, 10]}
    info.update(overrides)
    return info


def test_executor_no_target_skips():
    ctx = FakeCtx()
    result = _executor().execute(make_node({'action': 'click', 'by': 'class_name'}), ctx)
    assert result['success'] is True
    assert any('未配置控件名称' in log for log in ctx.logs)


def test_executor_click_hit(monkeypatch):
    import core.node_executors.base.control as control_mod

    monkeypatch.setattr(control_mod, 'find_control', lambda **kw: _fake_control())
    monkeypatch.setattr(control_mod, 'perform_action', lambda info, action, text='': {'ok': True, 'message': '点击控件中心'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({'action': 'click', 'by': 'text', 'target': '确定'}), ctx)
    assert result['success'] is True
    assert any('命中控件' in log for log in ctx.logs)


def test_executor_not_found_fails(monkeypatch):
    import core.node_executors.base.control as control_mod

    monkeypatch.setattr(control_mod, 'find_control', lambda **kw: None)

    ctx = FakeCtx()
    result = _executor().execute(make_node({'action': 'click', 'by': 'text', 'target': '不存在的按钮'}), ctx)
    assert result['success'] is False
    assert any('未找到匹配控件' in log for log in ctx.logs)





def test_executor_action_failure_fails(monkeypatch):
    import core.node_executors.base.control as control_mod

    monkeypatch.setattr(control_mod, 'find_control', lambda **kw: _fake_control())
    monkeypatch.setattr(control_mod, 'perform_action', lambda info, action, text='': {'ok': False, 'message': '不支持的操作'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({'action': 'double_click', 'by': 'class_name', 'target': 'Button'}), ctx)
    assert result['success'] is False


def test_executor_template_vars_resolved(monkeypatch):
    import core.node_executors.base.control as control_mod

    captured = {}
    def fake_find(**kw):
        captured.update(kw)
        return _fake_control()
    monkeypatch.setattr(control_mod, 'find_control', fake_find)
    monkeypatch.setattr(control_mod, 'perform_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx({'btn_text': '开始游戏', 'title': '主窗口'})
    result = _executor().execute(
        make_node({'action': 'click', 'by': 'text', 'target': '$var{btn_text}', 'window_title': '$ctx{title}'}), ctx)
    assert result['success'] is True
    assert captured['target'] == '开始游戏'
    assert captured['window_title'] == '主窗口'


# ========== control_exists 条件判定（存在/不存在控件） ==========

class FakeCondCtx:
    def __init__(self):
        self.variables = {}
        self.last_match_score = 0.0


def test_control_exists_hit(monkeypatch):
    """存在控件：命中返回 True，且写入 branch 得分"""
    from core.conditions.handlers.control_exists import ControlExistsEvaluator
    from core.services import uia_service

    monkeypatch.setattr(uia_service, 'find_control',
                        lambda **kw: {'name': '开始游戏', 'control_type': 'button'})
    ctx = FakeCondCtx()
    result = ControlExistsEvaluator.evaluate(
        {'exist_mode': 'exists', 'by': 'uia_name', 'target': '开始游戏', 'timeout': 1000}, ctx)
    assert result is True
    assert ctx.last_match_score == 1.0


def test_control_exists_missing(monkeypatch):
    """不存在控件（存在模式未命中）：返回 False"""
    from core.conditions.handlers.control_exists import ControlExistsEvaluator
    from core.services import uia_service

    monkeypatch.setattr(uia_service, 'find_control', lambda **kw: None)
    ctx = FakeCondCtx()
    result = ControlExistsEvaluator.evaluate(
        {'exist_mode': 'exists', 'by': 'uia_name', 'target': '不存在的按钮', 'timeout': 1000}, ctx)
    assert result is False
    assert ctx.last_match_score == 0.0


def test_control_not_exists_mode(monkeypatch):
    """不存在模式：未命中 → True（判定"不存在控件"成立）"""
    from core.conditions.handlers.control_exists import ControlExistsEvaluator
    from core.services import uia_service

    monkeypatch.setattr(uia_service, 'find_control', lambda **kw: None)
    assert ControlExistsEvaluator.evaluate(
        {'exist_mode': 'not_exists', 'by': 'uia_name', 'target': 'x', 'timeout': 1000}, FakeCondCtx()) is True


def test_control_exists_infers_capture_format(monkeypatch):
    """捕获格式 name="x" 自动推断 UIA 查找方式（与执行器一致）"""
    from core.conditions.handlers.control_exists import ControlExistsEvaluator
    from core.services import uia_service

    captured = {}
    def fake_find(**kw):
        captured.update(kw)
        return {'name': '确定'}
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    assert ControlExistsEvaluator.evaluate(
        {'exist_mode': 'exists', 'by': 'class_name', 'target': 'name="确定"', 'timeout': 1000}, FakeCondCtx()) is True
    assert captured['by'] == 'uia_name'
    assert captured['target'] == '确定'


def test_control_exists_win32_by(monkeypatch):
    """非 UIA 查找方式走 control_service.find_control"""
    from core.conditions.handlers.control_exists import ControlExistsEvaluator
    from core.services import control_service

    captured = {}
    def fake_find(**kw):
        captured.update(kw)
        return {'class_name': 'Button'}
    monkeypatch.setattr(control_service, 'find_control', fake_find)
    assert ControlExistsEvaluator.evaluate(
        {'exist_mode': 'exists', 'by': 'class_name', 'target': 'Button', 'timeout': 1000}, FakeCondCtx()) is True
    assert captured['by'] == 'class_name'


# ========== 捕获信息（control_info 隐藏字段）执行时使用 ==========

def test_executor_uses_captured_window_title(monkeypatch):
    """params.window_title 为空时，取捕获存储的 control_info.window_title 作为查找作用域
    （节点表单只展示控件名称，但完整定位信息随捕获存储并参与执行）"""
    from core.services import uia_service

    captured = {}
    def fake_find(**kw):
        captured.update(kw)
        return _fake_control()
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({
        'action': 'click', 'by': 'uia_name', 'target': '最高',
        'control_info': {'name': '最高', 'control_type': 'combobox', 'window_title': '系统设置'}
    }), ctx)
    assert result['success'] is True
    assert captured['window_title'] == '系统设置'  # 窗口作用域自动生效（不再全桌面遍历）


def test_executor_captured_window_title_overridden_by_explicit(monkeypatch):
    """手动配置的 window_title 优先于捕获存储值"""
    from core.services import uia_service

    captured = {}
    def fake_find(**kw):
        captured.update(kw)
        return _fake_control()
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({
        'action': 'click', 'by': 'uia_name', 'target': '最高', 'window_title': '手动窗口',
        'control_info': {'window_title': '捕获窗口'}
    }), ctx)
    assert result['success'] is True
    assert captured['window_title'] == '手动窗口'


def test_executor_primary_miss_tries_captured_fallbacks(monkeypatch):
    """主选择器未命中 → 按捕获信息的 id/class/name/type 依次兜底重查（短超时、窗口作用域内）"""
    from core.services import uia_service

    calls = []
    def fake_find(**kw):
        calls.append(kw)
        if kw.get('by') == 'uia_class' and kw.get('target') == 'ComboBoxEx32':
            return _fake_control(automation_id='cb_1', class_name='ComboBoxEx32', name='最高')
        return None
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({
        'action': 'click', 'by': 'uia_name', 'target': '最高',
        'control_info': {'name': '最高', 'control_type': 'combobox', 'automation_id': 'cb_1',
                         'class_name': 'ComboBoxEx32', 'window_title': '系统设置'}
    }), ctx)
    assert result['success'] is True
    assert any('备选 uia_class=ComboBoxEx32' in log for log in ctx.logs)
    bys = [c['by'] for c in calls]
    assert bys == ['uia_name', 'uia_id', 'uia_class']  # 主查 name → 备选 id → 备选 class（命中即停）
    assert all(c['window_title'] == '系统设置' for c in calls)  # 兜底同样限定窗口作用域
    assert calls[1]['timeout_ms'] <= 1500  # 备选用短超时


def test_executor_fallback_skips_primary_pair(monkeypatch):
    """捕获的 by/target 与主选择器相同（type 命中场景）时，兜底不重复查询自身"""
    import core.node_executors.base.control as control_mod
    from core.node_executors.base.control import _find_with_captured_fallbacks

    calls = []
    def fake_find(**kw):
        calls.append(kw)
        return None
    monkeypatch.setattr(control_mod, 'find_control', fake_find)

    result = _find_with_captured_fallbacks(
        control_mod, '系统设置', 'uia_type', 'combobox', 0, 3000,
        {'name': '', 'control_type': 'combobox', 'automation_id': 'cb_1', 'class_name': ''})
    assert result is None
    assert [c['by'] for c in calls] == ['uia_id']  # 只试 automation_id（type=combobox 是主查，name/class 为空）


def test_executor_prefers_ancestor_path(monkeypatch):
    """有 control_info.ancestor_path 时优先祖先链逐级定位（毫秒级），BFS 不再执行"""
    from core.services import uia_service

    path_calls = []
    def fake_path_find(**kw):
        path_calls.append(kw)
        info = _fake_control(automation_id='btn_1', name='开始游戏')
        info['matched_by'] = 'path'
        return info
    def fake_find(**kw):
        raise AssertionError('有祖先链时不应走 BFS')
    monkeypatch.setattr(uia_service, 'find_control_by_path', fake_path_find)
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({
        'action': 'click', 'by': 'uia_name', 'target': '开始游戏',
        'window_title': '游戏窗口',
        'control_info': {'window_title': '游戏窗口', 'ancestor_path': [
            {'control_type': 'window', 'name': '游戏窗口', 'automation_id': '', 'class_name': ''},
            {'control_type': 'button', 'name': '开始游戏', 'automation_id': 'btn_1', 'class_name': ''},
        ]}
    }), ctx)
    assert result['success'] is True
    assert path_calls and path_calls[0]['window_title'] == '游戏窗口'
    assert path_calls[0]['timeout_ms'] <= 1500  # 祖先链短超时
    assert any('祖先链定位' in log for log in ctx.logs)


def test_executor_path_miss_falls_back_to_bfs(monkeypatch):
    """祖先链定位失败（UI 结构变化）→ 回退主选择器 BFS"""
    from core.services import uia_service

    def fake_path_find(**kw):
        return None
    bfscalls = []
    def fake_find(**kw):
        bfscalls.append(kw)
        return _fake_control(name='开始游戏')
    monkeypatch.setattr(uia_service, 'find_control_by_path', fake_path_find)
    monkeypatch.setattr(uia_service, 'find_control', fake_find)
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = _executor().execute(make_node({
        'action': 'click', 'by': 'uia_name', 'target': '开始游戏',
        'control_info': {'ancestor_path': [{'control_type': 'window', 'name': '游戏窗口', 'automation_id': '', 'class_name': ''}]}
    }), ctx)
    assert result['success'] is True
    assert bfscalls and bfscalls[0]['target'] == '开始游戏'


# ========== #9 Win32 回退路径：匹配归一化 + 顶层窗口缓存 ==========

def test_matches_text_normalized():
    """Win32 文本匹配空白归一化（\xa0/多空格/换行）"""
    from core.services.control_service import matches

    info = {'text': '开始\u00a0游戏', 'class_name': 'Button'}
    assert matches(info, 'text', '开始 游戏') is True
    assert matches(info, 'text', '开始游戏') is False
    assert matches({'class_name': ' Button '}, 'class_name', 'Button') is True
    assert matches({'control_type': 'BUTTON'}, 'control_type', 'button') is True


def test_collect_windows_uses_tops_cache(monkeypatch):
    """空标题场景复用顶层窗口缓存：EnumWindows 只调用一次，子控件每轮实时枚举"""
    from core.services import control_service as cs

    enum_calls = {'tops': 0, 'children': 0}

    def fake_enum_windows(cb, _):
        enum_calls['tops'] += 1
        cb(100, None)
        return None

    def fake_enum_children(hwnd, cb, _):
        enum_calls['children'] += 1
        cb(hwnd + 1, None)
        return None

    monkeypatch.setattr(cs.win32gui, 'EnumWindows', fake_enum_windows)
    monkeypatch.setattr(cs.win32gui, 'EnumChildWindows', fake_enum_children)

    tops = cs._collect_top_windows()
    assert enum_calls['tops'] == 1
    # 两轮收集复用 tops，不再 EnumWindows
    r1 = cs._collect_windows('', tops)
    r2 = cs._collect_windows('', tops)
    assert enum_calls['tops'] == 1
    assert enum_calls['children'] == 2  # 每轮都实时枚举子控件
    assert r1 == [100, 101] and r2 == [100, 101]
