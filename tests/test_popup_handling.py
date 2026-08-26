# tests/test_popup_handling.py
# 随机弹窗旁路处理：显式 popup_handler 组、检查点循环与次数保护。
import pytest
from core.graph.builder import GraphBuilder
from core.models import Node, Task, TopologyMap


def _page(node_id, page_id, node_name, features=None, *, is_popup=False):
    node = Node(
        node_id=node_id, node_name=node_name, node_type='page_state',
        params={
            'page_id': page_id,
            'features': features or [{'condition_type': 'image_exists', 'image_source': 'x'}],
            'is_random_popup': is_popup,
        },
        delay_before=0, loop_count=1,
    )
    return node


def _op(node_id, node_name, node_type='click'):
    return Node(node_id=node_id, node_name=node_name, node_type=node_type,
                params={}, delay_before=0, loop_count=1)


def make_topology():
    """主图：A→B；弹窗组「弹窗处理」：弹窗C→关闭C→（无出口）"""
    main = Task(task_id='t_main', task_name='主流程', nodes=[_page('pA', 'pageA', '主页A'), _page('pB', 'pageB', '主页B')])
    popup = Task(task_id='t_popup', task_name='弹窗处理', role='popup_handler', nodes=[
        _page('pC', 'pageC', '弹窗C', is_popup=True), _op('closeC', '关闭弹窗C', 'click'),
    ])
    edges = [
        {'edge_id': 'e1', 'source_node': 'pA', 'target_node': 'pB', 'canvas': 'topology', 'source_port': 'success'},
        # 弹窗组对外连线（应被忽略）
        {'edge_id': 'e2', 'source_node': 'pC', 'target_node': 'pB', 'canvas': 'topology', 'source_port': 'success'},
        # 弹窗组内部边：弹窗C → 关闭C（关闭后由弹窗检查点外层循环复检）
        {'edge_id': 'e3', 'source_node': 'pC', 'target_node': 'closeC', 'canvas': 'topology', 'source_port': 'success'},
    ]
    return TopologyMap(tasks=[main, popup], edges=edges)


def test_main_graph_excludes_popup_group():
    """主图不含弹窗组节点，弹窗对外连线被忽略"""
    topo = make_topology()
    graph = GraphBuilder.build_topology_graph(topo)
    keys = {k for k, _, _ in graph.get_out_edges('pageA')}
    assert 'pageB' in keys  # 主图正常
    assert 'pageC' not in {n for n in graph.node_index_map}  # 弹窗页不在主图
    # 弹窗对外连线 e2 被忽略：pageC 不作为任何节点出边


def test_popup_graphs_built_per_group():
    """弹窗组子图：组内边保留，对外连线忽略"""
    topo = make_topology()
    popups = GraphBuilder.build_popup_graphs(topo)
    assert set(popups.keys()) == {'t_popup'}
    g = popups['t_popup']
    # pageC → closeC（弹窗→关闭动作边保留）
    out = g.get_out_edges('pageC')
    assert out and out[0][0] == 'closeC'
    # pageC 对外连线（e2 → 主图）被忽略
    targets = [t for t, _, _ in g.get_out_edges('pageC')]
    assert 'pageB' not in targets


def test_is_popup_task_uses_only_explicit_page_flag():
    assert GraphBuilder.is_popup_task(Task(task_id='t1', task_name='弹窗处理', nodes=[])) is False
    assert GraphBuilder.is_popup_task(Task(task_id='t2', task_name='主流程', nodes=[])) is False
    assert GraphBuilder.is_popup_task(Task(task_id='t3', task_name='广告弹窗拦截', nodes=[])) is False
    assert GraphBuilder.is_popup_task(Task(task_id='t4', task_name='系统旁路', role='popup_handler')) is False
    assert GraphBuilder.is_popup_task(Task(task_id='t6', task_name='页面地图', nodes=[_page('popup', 'popup', '弹窗', is_popup=True)])) is True


def test_page_level_popup_flag_excludes_only_the_marked_page_from_navigation():
    popup_page = _page('popup', 'popup_page', '随机弹窗')
    popup_page.params['is_random_popup'] = True
    regular_page = _page('regular', 'regular_page', '普通页面')
    close = _op('close', '关闭')
    task = Task(task_id='pages', task_name='页面地图', nodes=[popup_page, close, regular_page])
    topology = TopologyMap(tasks=[task], edges=[
        {'edge_id': 'popup_close', 'source_node': 'popup', 'target_node': 'close', 'source_port': 'success'},
    ])

    assert GraphBuilder.is_popup_task(task) is True
    graph = GraphBuilder.build_topology_graph(topology)
    assert 'popup_page' not in graph.node_index_map
    assert 'regular_page' in graph.node_index_map
    assert 'pages' in GraphBuilder.build_popup_graphs(topology)


@pytest.mark.parametrize('node_type', ['log', 'variable_op', 'wait', 'set_window', 'script_call', 'call_task'])
def test_pure_logic_nodes_do_not_require_popup_check(node_type):
    """纯逻辑/等待/准备节点不得触发截图或弹窗页面扫描。"""
    from core.executor import GraphExecutor

    node = Node(node_id='n', node_name=node_type, node_type=node_type, params={})
    assert GraphExecutor._node_requires_popup_check(node) is False


@pytest.mark.parametrize('node_type', ['click', 'control', 'image_recognition', 'ocr_recognition', 'smart_jump', 'page_state'])
def test_screen_nodes_require_popup_check(node_type):
    """真正读取或操控界面的节点在执行前检查弹窗。"""
    from core.executor import GraphExecutor

    node = Node(node_id='n', node_name=node_type, node_type=node_type, params={})
    assert GraphExecutor._node_requires_popup_check(node) is True


def test_condition_nodes_only_check_popups_for_ui_conditions():
    from core.executor import GraphExecutor

    variable_logic = Node(
        node_id='var', node_name='变量判断', node_type='logic_check',
        params={'conditions': [{'condition_type': 'variable_check', 'variable_name': 'x'}]},
    )
    image_branch = Node(
        node_id='image', node_name='图片分支', node_type='branch',
        params={'candidates': [{'condition': {'condition_type': 'image_exists', 'image_source': 'asset://a'}}]},
    )
    assert GraphExecutor._node_requires_popup_check(variable_logic) is False
    assert GraphExecutor._node_requires_popup_check(image_branch) is True


def test_pure_workflow_never_scans_popups(monkeypatch):
    """日志 → 变量 → 日志的完整运行，包括自然结束时都不触发弹窗扫描。"""
    from core.executor import GraphExecutor
    from core.models import Project

    nodes = [
        Node(node_id='n1', node_name='日志1', node_type='log', params={'message': 'before'}, delay_before=0),
        Node(
            node_id='n2', node_name='变量', node_type='variable_op',
            params={'target_var': 'x', 'new_value': '1'}, delay_before=0,
        ),
        Node(node_id='n3', node_name='日志2', node_type='log', params={'message': 'after'}, delay_before=0),
    ]
    task = Task(task_id='t_main', task_name='纯逻辑流程', nodes=nodes)
    project = Project(project_name='pure', tasks={'t_main': task}, edges=[], topology=make_topology())
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    scans = []
    monkeypatch.setattr(executor, '_ensure_popups_clear', lambda *args, **kwargs: scans.append(1) or True)

    executor.run('t_main')

    assert scans == []


# ========== executor 弹窗检查点与分层评估 ==========

def _make_project_with_popup():
    """workflow: t_main(wait节点)；topology: 主图 A→B + 弹窗组 C→closeC→C"""
    from core.models import Project
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    topo = make_topology()
    return Project(project_name='popup_test', tasks={'t_main': main}, edges=[], topology=topo)


def _prepare_popup_executor(ex):
    """弹窗状态机测试不依赖真实桌面截图/帧差。"""
    def capture():
        ex._step_screen = object()
        return True
    ex._capture_workspace_step = capture
    ex._frame_is_stable = lambda: True
    ex.settings.update({'popup_quiet_frames': 1, 'popup_quiet_window_ms': 0, 'popup_poll_ms': 30})


def test_check_popups_closes_and_recovers(monkeypatch):
    """弹窗命中 → 执行关闭动作（组内节点执行）→ 特征消失后停止；主流程节点照常执行"""
    from core.executor import GraphExecutor

    project = _make_project_with_popup()
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    logs = []
    ex.log = lambda msg, level='info', image=None: logs.append(msg)

    # 弹窗特征状态机：首次命中，关闭后下一帧消失。
    calls = {'n': 0}

    def fake_execute(page_node, ctx):
        from core.node_executors.base.page_state import PageStateNodeExecutor
        # 只有弹窗页 C 命中，且只命中前 2 次
        if (page_node.params or {}).get('page_id') == 'pageC':
            calls['n'] += 1
            if calls['n'] == 1:
                return {'success': True}
        return {'success': False}

    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor', type('FakePE', (), {'execute': staticmethod(fake_execute)}))
    # 关闭动作（click 节点）执行：真实执行会点屏幕——替换 _execute_node_safely
    executed = []
    def fake_safe(node):
        executed.append(getattr(node, 'node_name', ''))
        return {'success': True}
    ex._execute_node_safely = fake_safe

    assert ex._ensure_popups_clear()

    assert 'closeC' in executed or '关闭弹窗C' in [str(e) for e in executed]
    handled_logs = [l for l in logs if '弹窗处理' in l]
    assert any('执行关闭流程' in l for l in handled_logs), logs
    # 无互弹死锁错误
    assert not any('互弹' in l for l in logs)


def test_popup_deadlock_protection(monkeypatch):
    """弹窗持续存在时清场失败并阻止主流程，不得静默放行。"""
    from core.executor import GraphExecutor

    project = _make_project_with_popup()
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    ex.POPUP_COOLDOWN_MS = 0
    ex.MAX_POPUP_HANDLES = 3
    logs = []
    ex.log = lambda msg, level='info', image=None: logs.append(msg)

    def fake_execute(page_node, ctx):
        if (page_node.params or {}).get('page_id') == 'pageC':
            return {'success': True}
        return {'success': False}

    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor', type('FakePE', (), {'execute': staticmethod(fake_execute)}))
    ex._execute_node_safely = lambda node: {'success': True}

    clear = ex._ensure_popups_clear()
    assert clear is False
    assert ex._last_popup_result['status'] == 'error'
    assert '仍未清除' in ex._last_popup_result['error']
    close_count = sum(1 for l in logs if '执行关闭流程' in l)
    assert close_count == ex.MAX_POPUP_HANDLES, close_count


def test_duplicate_page_id_warns():
    """page_id 重复 → 构建拓扑索引时警告"""
    from core.executor import GraphExecutor
    from core.models import Project

    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    topo = TopologyMap(tasks=[
        Task(task_id='t1', task_name='组1', nodes=[
            _page('pA', 'pageX', '页面A'), _page('pB', 'pageX', '页面B'),
        ]),
    ], edges=[])
    project = Project(project_name='dup_test', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    logs = []
    ex.log = lambda msg, level='info', image=None: logs.append(msg)
    ex._build_topology_index()
    assert any('page_id 重复' in l for l in logs), logs


def test_layered_evaluation_orders_neighbors_first(monkeypatch):
    """分层评估：当前页已知时，邻接页先于远页被评估"""
    from core.executor import GraphExecutor
    from core.models import Project

    # 拓扑：A→B→C（链）；当前页=A
    topo = TopologyMap(tasks=[
        Task(task_id='t1', task_name='组1', nodes=[
            _page('pA', 'pageA', '页面A'), _page('pB', 'pageB', '页面B'), _page('pC', 'pageC', '页面C'),
        ]),
    ], edges=[
        {'edge_id': 'e1', 'source_node': 'pA', 'target_node': 'pB', 'canvas': 'topology', 'source_port': 'success'},
        {'edge_id': 'e2', 'source_node': 'pB', 'target_node': 'pC', 'canvas': 'topology', 'source_port': 'success'},
    ])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='layer_test', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    ex.variables['current_page_id'] = 'pageA'
    ex._capture_workspace_step = lambda: None
    ex._step_screen = 'FAKE_SCREEN'

    evaluated = []
    from core.node_executors.base.page_state import PageStateNodeExecutor
    def fake_execute(page_node, ctx):
        evaluated.append((page_node.params or {}).get('page_id'))
        return {'success': False}
    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor', type('FakePE2', (), {'execute': staticmethod(fake_execute)}))

    ex.evaluate_current_page()
    # 邻接 B 先于远页 C 评估；A 是当前页本身不评估（或最后）
    assert evaluated[0] == 'pageB', evaluated
    assert 'pageC' in evaluated


def test_page_evaluation_reports_ambiguous_matches_and_chooses_specific_page(monkeypatch):
    """同一帧多个页面命中时不得静默取遍历首项，应输出候选并选更具体页面。"""
    from core.executor import GraphExecutor
    from core.models import Project

    generic = _page('pA', 'pageA', '通用页面')
    specific = _page('pB', 'pageB', '具体页面')
    specific.params['features'] = [{}, {}]
    topo = TopologyMap(tasks=[Task(task_id='t1', task_name='组1', nodes=[generic, specific])], edges=[])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='ambiguity_test', tasks={'t_main': main}, edges=[], topology=topo)
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    executor._step_screen = 'FAKE_SCREEN'
    logs = []
    executor.log = lambda message, level='info', image=None: logs.append(str(message))

    def fake_execute(page_node, context):
        context.last_match_score = 0.8
        return {'success': True}

    monkeypatch.setattr(
        'core.node_executors.base.page_state.PageStateNodeExecutor',
        type('AmbiguousPageExecutor', (), {'execute': staticmethod(fake_execute)}),
    )

    assert executor.evaluate_current_page() == 'pageB'
    assert executor.variables['current_page_id'] == 'pageB'
    assert any('同一帧同时命中 2 个候选' in item for item in logs)


def test_popup_close_follows_exit_port_edges(monkeypatch):
    """弹窗组内「页面→操作」连线端口是 exit_0（拓扑出口）——关闭流程必须沿任意端口边走"""
    from core.executor import GraphExecutor
    from core.models import Project

    popup = Task(task_id='t_popup', task_name='弹窗', role='popup_handler', nodes=[
        _page('pC', 'pageC', '广告弹窗', is_popup=True), _op('closeC', '关闭弹窗', 'click'),
    ])
    topo = TopologyMap(tasks=[popup], edges=[
        # ⚡ 端口为 exit_0（用户拓扑实际端口）
        {'edge_id': 'e1', 'source_node': 'pC', 'target_node': 'closeC', 'canvas': 'topology', 'source_port': 'exit_0'},
    ])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='exit_port_test', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    logs = []
    ex.log = lambda msg, level='info', image=None: logs.append(msg)

    def fake_execute(page_node, ctx):
        if (page_node.params or {}).get('page_id') == 'pageC':
            return {'success': True}
        return {'success': False}
    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor',
                        type('FakePE3', (), {'execute': staticmethod(fake_execute)}))

    executed = []
    ex._execute_node_safely = lambda node: (executed.append(getattr(node, 'node_name', '')), {'success': True})[1]

    result = ex._execute_popup_close('t_popup', popup.nodes[0])
    assert result['success'] is True
    assert '关闭弹窗' in executed, f'关闭动作未执行: {executed}'
    # 弹窗特征在第 2 次评估时消失（fake 恒命中 → 但关闭动作执行后循环应继续到第 2 次仍命中）
    # 这里 fake 恒命中，验证的是关闭动作确实被调用了
    assert any('执行关闭动作' in l for l in logs), logs


def test_popup_handling_restores_current_page(monkeypatch):
    """弹窗处理不污染主流程 current_page_id（弹窗页评估会写该变量，处理后必须恢复）"""
    from core.executor import GraphExecutor
    from core.models import Project

    popup = Task(task_id='t_popup', task_name='弹窗', role='popup_handler', nodes=[
        _page('pC', 'pageC', '广告弹窗', is_popup=True), _op('closeC', '关闭弹窗', 'click'),
    ])
    topo = TopologyMap(tasks=[popup], edges=[
        {'edge_id': 'e1', 'source_node': 'pC', 'target_node': 'closeC', 'canvas': 'topology', 'source_port': 'exit_0'},
    ])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='restore_test', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    ex.variables['current_page_id'] = 'pageA'  # 主流程位置
    ex._execute_node_safely = lambda node: {'success': True}

    calls = {'n': 0}

    def fake_execute(page_node, ctx):
        # 弹窗页评估命中，且模拟其写入 current_page_id 的副作用
        ctx.variables['current_page_id'] = 'pageC'
        calls['n'] += 1
        if (page_node.params or {}).get('page_id') == 'pageC':
            return {'success': calls['n'] == 1}  # 第 1 次命中（触发关闭），之后消失
        return {'success': False}

    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor',
                        type('FakePE4', (), {'execute': staticmethod(fake_execute)}))
    assert ex._ensure_popups_clear()
    assert ex.variables['current_page_id'] == 'pageA', ex.variables['current_page_id']


def test_popup_cooldown_prevents_repeat_handling(monkeypatch):
    """冷却窗口内弹窗仍命中时保持阻塞，绝不能误判为已清场。"""
    from core.executor import GraphExecutor
    from core.models import Project

    popup = Task(task_id='t_popup', task_name='弹窗', role='popup_handler', nodes=[
        _page('pC', 'pageC', '广告弹窗', is_popup=True), _op('closeC', '关闭弹窗', 'click'),
    ])
    topo = TopologyMap(tasks=[popup], edges=[
        {'edge_id': 'e1', 'source_node': 'pC', 'target_node': 'closeC', 'canvas': 'topology', 'source_port': 'exit_0'},
    ])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'duration_ms': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='cooldown_test', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    logs = []
    ex.log = lambda msg, level='info', image=None: logs.append(msg)
    ex.POPUP_COOLDOWN_MS = 800
    ex.settings['popup_total_timeout_ms'] = 500

    def fake_execute(page_node, ctx):
        # 弹窗特征恒命中（模拟关闭后响应延迟期间特征残留）
        if (page_node.params or {}).get('page_id') == 'pageC':
            return {'success': True}
        return {'success': False}
    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor',
                        type('FakePE5', (), {'execute': staticmethod(fake_execute)}))

    executed = []
    ex._execute_node_safely = lambda node: (executed.append(1), {'success': True})[1]

    result = ex._drain_popups()
    assert len(executed) == 1, f'首次应处理一次: {len(executed)}'
    assert 'pageC' in ex._popup_last_handled
    assert result['status'] == 'error'
    assert any('冷却中' in l for l in logs), logs


def test_popup_cooldown_expired_rehandles(monkeypatch):
    """无冷却且弹窗持续存在时有限重试，达到上限后失败。"""
    from core.executor import GraphExecutor
    from core.models import Project

    popup = Task(task_id='t_popup', task_name='弹窗', role='popup_handler', nodes=[
        _page('pC', 'pageC', '广告弹窗', is_popup=True), _op('closeC', '关闭弹窗', 'click'),
    ])
    topo = TopologyMap(tasks=[popup], edges=[
        {'edge_id': 'e1', 'source_node': 'pC', 'target_node': 'closeC', 'canvas': 'topology', 'source_port': 'exit_0'},
    ])
    main = Task(task_id='t_main', task_name='主流程', nodes=[
        Node(node_id='n1', node_name='等待', node_type='wait', params={'seconds': 0}, delay_before=0, loop_count=1),
    ])
    project = Project(project_name='cooldown2', tasks={'t_main': main}, edges=[], topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    ex.POPUP_COOLDOWN_MS = 0
    ex.MAX_POPUP_HANDLES = 2

    def fake_execute(page_node, ctx):
        if (page_node.params or {}).get('page_id') == 'pageC':
            return {'success': True}
        return {'success': False}
    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor',
                        type('FakePE6', (), {'execute': staticmethod(fake_execute)}))

    executed = []
    ex._execute_node_safely = lambda node: (executed.append(1), {'success': True})[1]

    result = ex._drain_popups()
    assert len(executed) == 2
    assert result['status'] == 'error'


def test_layered_popups_are_drained_before_main_flow(monkeypatch):
    """关闭第一层后出现第二层时必须继续清场，直到稳定无弹窗。"""
    from core.executor import GraphExecutor
    from core.models import Project

    popup = Task(task_id='t_popup', task_name='弹窗', role='popup_handler', nodes=[
        _page('p1', 'popup1', '第一层', is_popup=True), _op('c1', '关闭第一层'),
        _page('p2', 'popup2', '第二层', is_popup=True), _op('c2', '关闭第二层'),
    ])
    topo = TopologyMap(tasks=[popup], edges=[
        {'source_node': 'p1', 'target_node': 'c1', 'source_port': 'success'},
        {'source_node': 'p2', 'target_node': 'c2', 'source_port': 'success'},
    ])
    project = Project(project_name='layers', tasks={}, topology=topo)
    ex = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    _prepare_popup_executor(ex)
    ex.POPUP_COOLDOWN_MS = 0
    layer = {'value': 'popup1'}

    def evaluate(page_node, ctx):
        return {'success': (page_node.params or {}).get('page_id') == layer['value']}

    monkeypatch.setattr('core.node_executors.base.page_state.PageStateNodeExecutor',
                        type('LayerEvaluator', (), {'execute': staticmethod(evaluate)}))
    executed = []

    def close(node):
        executed.append(node.node_name)
        layer['value'] = 'popup2' if node.node_id == 'c1' else ''
        return {'success': True}

    ex._execute_node_safely = close
    result = ex._drain_popups()
    assert result == {'status': 'clear', 'handled_count': 2}
    assert executed == ['关闭第一层', '关闭第二层']


def test_full_page_miss_triggers_fresh_popup_rescan(monkeypatch):
    """普通页面全图未命中后再扫一次弹窗，再继续页面识别。"""
    from core.executor import GraphExecutor
    from core.models import Project

    ex = GraphExecutor(Project(project_name='rescan'), text_log_enabled=False, image_log_enabled=False)
    ex._capture_workspace_step = lambda: setattr(ex, '_step_screen', object()) or True
    ex._frame_is_stable = lambda: True
    ex.settings.update({'frame_stable_frames': 1, 'page_load_poll_ms': 50})
    popup_scans = {'count': 0}

    def clear(_deadline=None):
        popup_scans['count'] += 1
        handled = 1 if popup_scans['count'] == 2 else 0
        ex._last_popup_result = {'status': 'clear', 'handled_count': handled}
        return True

    page_scans = {'count': 0}

    def page():
        page_scans['count'] += 1
        return 'pageA' if page_scans['count'] >= 2 else ''

    monkeypatch.setattr(ex, '_ensure_popups_clear', clear)
    monkeypatch.setattr(ex, 'evaluate_current_page', page)
    assert ex._resolve_current_page_with_load_wait(1000) == 'pageA'
    assert popup_scans['count'] >= 3
