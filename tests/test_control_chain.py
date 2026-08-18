# tests/test_control_chain.py
# ⚡ 控件链路端到端冒烟（A→D→G 串联）：
#   A schema 加载（/api/params 真实返回）→ 按 schema 默认值构造节点（等价前端 buildNodeDefaultParams）
#   → D 执行器查找/操作（mock UIA 服务）→ G 捕获生成参数与 schema by 选项对齐（闭环）
import pytest

from core.services import capture_mode


class FakeCtx:
    def __init__(self, variables=None):
        self.variables = variables or {}
        self.logs = []

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)


def _make_node(params):
    from core.models import Node

    return Node(node_id='n', node_name='n', node_type='control', params=params)


def _control_schema():
    """A：真实 /api/params 返回的 control 定义"""
    from fastapi.testclient import TestClient
    from api.app import app

    defs = TestClient(app).get('/api/params').json()
    defs = defs.get('definitions') or defs
    return defs['control']


def _defaults_from_schema(schema):
    """等价前端 buildNodeDefaultParams：取 schema default（隐藏字段跳过）"""
    params = {}
    for key, cfg in schema['params'].items():
        if cfg.get('hidden'):
            continue
        if 'default' in cfg:
            params[key] = cfg['default']
    return params


def test_chain_schema_loads_and_defaults():
    """A：schema 完整（label/modes/关键字段/默认值）"""
    ctrl = _control_schema()
    assert ctrl['label'] == '控件操作'
    assert ctrl['modes'] == ['workflow']
    p = ctrl['params']
    assert set(p.keys()) >= {'action', 'by', 'target', 'window_title', 'index', 'timeout', 'control_info'}
    assert p['by']['default'] == 'uia_name'  # A1：默认 UIA 名称查找
    assert p['timeout']['default'] == 3000

    defaults = _defaults_from_schema(ctrl)
    assert defaults['action'] == 'click'
    assert defaults['timeout'] == 3000
    # ⚡ by 为隐藏字段（捕获时自动填充），默认值来自 schema 隐藏字段
    assert ctrl['params']['by']['default'] == 'uia_name'


def test_chain_capture_params_align_with_schema(monkeypatch):
    """G：捕获生成的 by/target 必须落在 schema by 选项内（闭环一致性）"""
    ctrl = _control_schema()
    by_opts = {o['value'] for o in ctrl['params']['by']['options']}

    cases = [
        {'name': '确定', 'control_type': 'button'},
        {'control_type': 'edit'},
        {'automation_id': 'e1'},
        {'class_name': 'Button'},
    ]
    for info in cases:
        gen = capture_mode.build_control_params(info)
        assert gen['by'] in by_opts, f'捕获生成 by 不在 schema 选项内: {gen}'
        assert gen['target']

    # 空信息 → 默认 uia_name + 空 target（前端会拦截并提示）
    empty = capture_mode.build_control_params({})
    assert empty == {'by': 'uia_name', 'target': ''}


def test_chain_execute_with_captured_params(monkeypatch):
    """D：用「捕获生成参数 + schema 默认值」构造节点执行 → 成功且命中日志"""
    from core.node_executors.base.control import ControlNodeExecutor
    from core.services import uia_service as uia_mod

    ctrl = _control_schema()
    defaults = _defaults_from_schema(ctrl)
    captured = capture_mode.build_control_params({'name': '开始游戏', 'control_type': 'button'})
    params = {**defaults, **captured, 'action': 'click'}

    # mock UIA 查找与操作（不碰真实桌面）
    monkeypatch.setattr(
        uia_mod, 'find_control',
        lambda **kw: {'name': '开始游戏', 'control_type': 'button', 'rect': [0, 0, 100, 40]})
    monkeypatch.setattr(
        uia_mod, 'perform_uia_action',
        lambda info, action, text='': {'ok': True, 'message': 'UIA Invoke 触发控件'})

    ctx = FakeCtx()
    result = ControlNodeExecutor().execute(_make_node(params), ctx)
    assert result['success'] is True
    logs = '\n'.join(ctx.logs)
    assert '查找控件' in logs and '方式: uia_name' in logs
    assert '命中 UIA 元素' in logs


def test_chain_paste_format_inferred(monkeypatch):
    """G→D：捕获复制格式 name="x" 粘贴到节点（by 仍为 Win32）→ 自动推断 UIA 查找执行成功"""
    from core.node_executors.base.control import ControlNodeExecutor
    from core.services import uia_service as uia_mod

    ctrl = _control_schema()
    defaults = _defaults_from_schema(ctrl)
    # 用户手动建节点：默认 class_name（Win32），但 target 粘贴了捕获格式
    params = {**defaults, 'by': 'class_name', 'target': 'name="开始游戏"', 'action': 'click'}

    monkeypatch.setattr(
        uia_mod, 'find_control',
        lambda **kw: {'name': '开始游戏', 'control_type': 'button', 'rect': [0, 0, 100, 40]})
    monkeypatch.setattr(
        uia_mod, 'perform_uia_action',
        lambda info, action, text='': {'ok': True, 'message': 'ok'})

    ctx = FakeCtx()
    result = ControlNodeExecutor().execute(_make_node(params), ctx)
    assert result['success'] is True
    assert any('方式: uia_name' in log for log in ctx.logs)  # 已自动推断


def test_chain_not_found_fails_through_failure_port(monkeypatch):
    """D：查找不到 → 失败口（on_failure 跳转）"""
    from core.node_executors.base.control import ControlNodeExecutor
    from core.services import uia_service as uia_mod

    ctrl = _control_schema()
    defaults = _defaults_from_schema(ctrl)
    params = {**defaults, 'target': '不存在的按钮', 'action': 'click'}

    monkeypatch.setattr(uia_mod, 'find_control', lambda **kw: None)

    ctx = FakeCtx()
    node = _make_node(params)
    node.params['on_failure'] = {'target_node': 'fail_node'}
    result = ControlNodeExecutor().execute(node, ctx)
    assert result['success'] is False
    assert result.get('jump', {}).get('target_node') == 'fail_node'
