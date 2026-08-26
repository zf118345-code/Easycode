# tests/test_player_service.py
# ⚡ Player 打包链路回归：运行入口（entry）路由 + context 合并 + $ctx 表达式变量
import pytest


@pytest.fixture()
def seed_cache(monkeypatch):
    """构造 PlayerService 内存缓存（blueprint/form_schema/user_config/context）"""
    from core.services import player_service as ps

    ps.PlayerService._MEMORY_CACHE['blueprint'] = {
        'variables': {'numrun': 0},
        'main_graph': {'graph_id': 'main', 'nodes': [{'node_id': 'n1', 'node_name': '节点A'}], 'edges': []},
        'functions': [],
        'function_folders': [],
        'page_map': {'schema_version': 3, 'nodes': [], 'edges': []},
    }
    ps.PlayerService._MEMORY_CACHE['form_schema'] = None
    ps.PlayerService._MEMORY_CACHE['user_config'] = {'vars': {'numrun': 5}, 'ctx': {'offset_top': 12}}
    ps.PlayerService._MEMORY_CACHE['templates'] = {}
    ps.PlayerService._MEMORY_CACHE['context'] = {'window_title': '任务管理器', 'offset_top': 0}
    ps.PlayerService._MEMORY_CACHE['license_info'] = {}
    ps.PlayerService._instances = {}
    yield ps
    ps.PlayerService._MEMORY_CACHE['blueprint'] = None
    ps.PlayerService._MEMORY_CACHE['form_schema'] = None
    ps.PlayerService._MEMORY_CACHE['user_config'] = None
    ps.PlayerService._MEMORY_CACHE['context'] = {}
    ps.PlayerService._instances = {}


def test_run_script_uses_configured_main_entry(seed_cache, monkeypatch):
    """Player 根入口只能是主流程中的明确节点。"""
    from core.services import player_service as ps

    seed_cache.PlayerService._MEMORY_CACHE['form_schema'] = {
        'entry': {'task_id': 'main', 'node_id': 'n1', 'node_name': '节点A'}
    }

    captured = {}

    def fake_run_task(project_path, task_id, start_node_id, blueprint_data, background_tasks, **kwargs):
        captured['task_id'] = task_id
        captured['start_node_id'] = start_node_id
        captured['blueprint'] = blueprint_data
        captured['project_path'] = project_path
        return {'execution_id': 'exec_1'}

    monkeypatch.setattr(ps.ExecutionService, 'run_task', staticmethod(fake_run_task))

    from fastapi import BackgroundTasks
    res = ps.PlayerService.run_script(BackgroundTasks())

    assert captured['task_id'] == 'main'
    assert captured['start_node_id'] == 'n1'
    assert res['execution_id'] == 'exec_1'
    assert res['entry']['node_name'] == '节点A'


def test_run_script_rejects_missing_entry(seed_cache):
    """当前密包必须声明明确入口。"""
    from core.services import player_service as ps
    from fastapi import HTTPException
    from fastapi import BackgroundTasks
    with pytest.raises(HTTPException, match='运行入口'):
        ps.PlayerService.run_script(BackgroundTasks())


def test_run_script_merges_context(seed_cache, monkeypatch):
    """ebp 内置 context + 客户 ctx 配置合并为 _player_context，且客户配置覆盖默认值"""
    from core.services import player_service as ps

    captured = {}

    seed_cache.PlayerService._MEMORY_CACHE['form_schema'] = {
        'entry': {'task_id': 'main', 'node_id': 'n1', 'node_name': '节点A'}
    }

    def fake_run_task(project_path, task_id, start_node_id, blueprint_data, background_tasks, **kwargs):
        captured['blueprint'] = blueprint_data
        return {'execution_id': 'exec_3'}

    monkeypatch.setattr(ps.ExecutionService, 'run_task', staticmethod(fake_run_task))

    from fastapi import BackgroundTasks
    ps.PlayerService.run_script(BackgroundTasks())

    ctx = captured['blueprint'].get('_player_context')
    assert ctx is not None
    assert ctx['window_title'] == '任务管理器'          # 来自 ebp 内置
    assert ctx['offset_top'] == 12                     # 客户配置覆盖
    # 变量倒灌仍然生效
    assert captured['blueprint']['variables']['numrun'] == 5


def test_loader_extracts_context_from_ebp(tmp_path):
    """loader 从密包 zip 中提取 context.json"""
    import io
    import zipfile
    from core.player.loader import PlayerAssetLoader

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        zf.writestr('blueprint.json', '{"tasks": []}')
        zf.writestr('form_schema.json', '{"form_title": "t"}')
        zf.writestr('context.json', '{"window_title": "计算器", "offset_top": 5}')

    ebp = tmp_path / 'assets.ebp'
    ebp.write_bytes(PlayerAssetLoader.DEFAULT_MASTER_KEY[:16] + b'\x00' * 16)  # 占位，下面用真加密
    # 用真实加密替换
    from core.services.export_service import ExportService
    # 直接构造加密流：AES-CBC 加密 zip
    from cryptography.hazmat.primitives import padding as sym_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    raw = zip_buf.getvalue()
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()
    iv = b'\x11' * 16
    cipher = Cipher(algorithms.AES(PlayerAssetLoader.DEFAULT_MASTER_KEY), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor().update(padded) + cipher.encryptor().finalize()
    ebp.write_bytes(iv + enc)

    blueprint, form_schema, user_config, templates, context = PlayerAssetLoader.load_bundle_from_ebp(str(ebp))
    assert context.get('window_title') == '计算器'
    assert context.get('offset_top') == 5


def test_apply_context_writes_ctx_variables(monkeypatch):
    """_apply_context 把上下文字段写入 variables 裸键（$ctx{} 表达式可解析），全桌面模式也写入"""
    from core.executor import GraphExecutor
    from core.models import Node, Task, Project

    project = Project(
        project_name='ctx_test',
        tasks={'t1': Task(task_id='t1', task_name='组1', nodes=[
            Node(node_id='n1', node_name='节点A', node_type='wait', params={'duration_ms': 0}, delay_before=0, loop_count=1),
        ])},
        edges=[],
    )
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    import win32gui
    import win32process

    monkeypatch.setattr(win32gui, 'EnumWindows', lambda callback, extra: callback(101, extra))
    monkeypatch.setattr(win32gui, 'IsWindow', lambda hwnd: hwnd == 101)
    monkeypatch.setattr(win32gui, 'IsWindowVisible', lambda hwnd: True)
    monkeypatch.setattr(win32gui, 'GetWindowText', lambda hwnd: '计算器')
    monkeypatch.setattr(win32gui, 'GetClassName', lambda hwnd: 'ApplicationFrameWindow')
    monkeypatch.setattr(win32gui, 'GetWindowRect', lambda hwnd: (100, 100, 916, 739))
    monkeypatch.setattr(win32gui, 'GetClientRect', lambda hwnd: (0, 0, 800, 600))
    monkeypatch.setattr(win32gui, 'ClientToScreen', lambda hwnd, point: (100 + point[0], 100 + point[1]))
    monkeypatch.setattr(win32gui, 'SetWindowPos', lambda *args: True)
    monkeypatch.setattr(win32process, 'GetWindowThreadProcessId', lambda hwnd: (1, 2024))
    ex._apply_context({
        'window_title': '计算器',
        'offset_top': 3,
        'offset_bottom': 4,
        'target_content_width': 800,
        'target_content_height': 600,
        'max_retry': 3,
    })
    assert ex.variables['title'] == '计算器'
    assert ex.variables['work_mode'] == 'window'
    assert ex.variables['content_offset']['top'] == 3
    assert ex.variables['target_content_size'] == [800, 600]
    assert ex.variables['max_retry'] == 3  # 自定义 ctx 键也写入

    # 全桌面模式（无窗口）：$ctx 变量仍可解析
    ex2 = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    ex2._apply_context({'offset_top': 1})
    assert ex2.variables['work_mode'] == 'desktop'
    assert ex2.variables['title'] == ''


def test_player_runtime_overrides_only_declared_settings_and_node_fields():
    from core.services.player_service import PlayerService

    blueprint = {
        'settings': {'max_logs': 500},
        'main_graph': {'graph_id': 'main', 'nodes': [{
            'node_id': 'n1', 'node_type': 'wait', 'delay_before': 0, 'loop_count': 1,
            'params': {'duration_ms': 100},
        }], 'edges': []},
        'functions': [],
    }
    schema = {'groups': [{'fields': [
        {'target': '$settings.max_logs', 'ui_type': 'number'},
        {'target': '$node.n1.params.duration_ms', 'ui_type': 'number'},
        {'target': '$node.n1.loop_count', 'ui_type': 'number'},
    ]}]}
    config = {'overrides': {
        '$settings.max_logs': 900,
        '$node.n1.params.duration_ms': 250,
        '$node.n1.loop_count': 4,
        '$settings.undeclared': 1,
    }}

    PlayerService._apply_runtime_overrides(blueprint, schema, config, {})
    assert blueprint['settings']['max_logs'] == 900
    assert blueprint['main_graph']['nodes'][0]['params']['duration_ms'] == 250
    assert blueprint['main_graph']['nodes'][0]['loop_count'] == 4
    assert 'undeclared' not in blueprint['settings']


def test_player_runtime_override_updates_nested_page_feature_leaf():
    from core.services.player_service import PlayerService

    blueprint = {
        'settings': {},
        'main_graph': {'graph_id': 'main', 'nodes': [], 'edges': []},
        'functions': [],
        'page_map': {'nodes': [{
            'node_id': 'page_login',
            'node_type': 'page_state',
            'params': {
                'page_id': 'page_login_stable',
                'features': [{'condition_type': 'image_exists', 'image_source': 'asset://original'}],
            },
        }], 'edges': []},
    }
    target = '$node.page_login.params.features.0.image_source'
    schema = {'groups': [{'fields': [{'target': target, 'ui_type': 'image_asset'}]}]}
    config = {'overrides': {target: 'asset://replacement'}}

    PlayerService._apply_runtime_overrides(blueprint, schema, config, {})

    assert blueprint['page_map']['nodes'][0]['params']['features'][0]['image_source'] == 'asset://replacement'
