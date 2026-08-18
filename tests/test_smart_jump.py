"""smart_jump（智能跳转）寻路与路径执行测试

覆盖：
1. 参数 schema 精简（target_page_id page_select + timeout）
2. 当前页面判定：变量有值 / 现场评估命中 / 全不匹配失败
3. 拓扑地图寻路：4321 环形流程最短路径；手操到中间页后从当前位置重算
4. 路径执行循环：逐节点执行（操作 + 页面确认）+ 每步位置监测
5. 手操/漂移触发重新寻路
6. 无路可达 / 节点失败 / 超时 → 失败
7. 日志播报：路径上每个拓扑节点均记录
"""

import time

from core.executor import GraphExecutor
from core.models import Node, Project, Task, TopologyMap
from core.node_executors.base.smart_jump import SmartJumpNodeExecutor
from core.params import ALL_PARAMS


# ========== 测试数据：4321 环形拓扑（页面4 → 操作 → 页面2 → 操作 → 页面1 → 操作 → 页面2） ==========

def make_topology():
    """拓扑地图：page4 --op_a--> page2 --op_b--> page1 --op_c--> page2（环形）"""
    return TopologyMap.from_dict(
        {
            'tasks': [
                {
                    'task_id': 'task_topology',
                    'task_name': '拓扑地图',
                    'nodes': [
                        {'node_id': 'page4', 'node_name': '页面4', 'node_type': 'page_state',
                         'params': {'page_id': 'page_4', 'features': [], 'feature_mode': 'and'}},
                        {'node_id': 'page2', 'node_name': '页面2', 'node_type': 'page_state',
                         'params': {'page_id': 'page_2', 'features': [], 'feature_mode': 'and'}},
                        {'node_id': 'page1', 'node_name': '页面1', 'node_type': 'page_state',
                         'params': {'page_id': 'page_1', 'features': [], 'feature_mode': 'and'}},
                        {'node_id': 'op_a', 'node_name': '点击A', 'node_type': 'click', 'params': {}},
                        {'node_id': 'op_b', 'node_name': '点击B', 'node_type': 'click', 'params': {}},
                        {'node_id': 'op_c', 'node_name': '点击C', 'node_type': 'click', 'params': {}},
                    ],
                }
            ],
            'edges': [
                {'source_node': 'page4', 'target_node': 'op_a'},
                {'source_node': 'op_a', 'target_node': 'page2'},
                {'source_node': 'page2', 'target_node': 'op_b'},
                {'source_node': 'op_b', 'target_node': 'page1'},
                {'source_node': 'page1', 'target_node': 'op_c'},
                {'source_node': 'op_c', 'target_node': 'page2'},
            ],
        }
    )


def make_project(target_page_id='page_1', timeout=3000):
    """工作流：单个 smart_jump 节点 + 上述拓扑地图"""
    sj_node = Node(
        node_id='sj',
        node_name='智能跳转',
        node_type='smart_jump',
        params={'target_page_id': target_page_id, 'timeout': timeout},
    )
    wf_task = Task(task_id='task_main', task_name='主任务', nodes=[sj_node])
    return Project(
        project_name='test_smart_jump',
        tasks={'task_main': wf_task},
        variables={},
        edges=[],
        topology=make_topology(),
    )


def make_executor(monkeypatch, current_page='', live_eval=None):
    """构造 GraphExecutor；monkeypatch 现场评估（不碰真实屏幕/鼠标）"""
    executor = GraphExecutor(make_project())
    if current_page:
        executor.variables['current_page_id'] = current_page
    if live_eval is not None:
        monkeypatch.setattr(executor, 'evaluate_current_page', live_eval)
    return executor


def install_fake_runner(executor, monkeypatch, page_sequence, run=None):
    """安装假节点执行器与假位置序列：
    - 节点执行记录到 calls（page_state 执行后更新 current_page_id；可自定义 run 注入失败）
    - page_sequence 每次现场评估弹出一个位置（模拟操作生效/手操/漂移）；耗尽后回退变量缓存
    @returns calls 列表
    """
    calls = []

    def fake_run(node):
        calls.append(node.node_id)
        if node.node_type == 'page_state':
            executor.variables['current_page_id'] = (node.params or {}).get('page_id', '')
        return run(node) if run is not None else {'success': True}

    monkeypatch.setattr(executor, '_execute_node_safely', fake_run)

    seq = list(page_sequence)

    def fake_eval():
        if seq:
            return seq.pop(0)
        return executor.variables.get('current_page_id', '')

    monkeypatch.setattr(executor, 'evaluate_current_page', fake_eval)
    return calls


def put_path(executor, target='page_1', timeout=3000):
    """写入 smart_jump 路径（模拟执行器已寻路）"""
    executor.variables['__smart_jump_path__'] = {
        'path': ['page_4', 'op_a', 'page_2', 'op_b', 'page_1'],
        'target_page_id': target,
        'timeout': timeout,
    }


# ========== 1. 参数 schema ==========

class TestParamsSchema:
    def test_smart_jump_params_simplified(self):
        cfg = ALL_PARAMS['smart_jump']
        assert cfg['modes'] == ['workflow']
        assert set(cfg['params'].keys()) == {'target_page_id', 'timeout'}
        assert cfg['params']['target_page_id']['type'] == 'page_select'
        assert cfg['params']['timeout']['default'] == 3000


# ========== 2. 执行器：当前页判定与寻路 ==========

class TestCurrentPageResolution:
    def test_current_page_from_variable(self, monkeypatch):
        """变量已有 current_page_id → 直接使用，不触发现场评估"""
        executor = make_executor(monkeypatch, current_page='page_4')
        node = executor.project.tasks['task_main'].nodes[0]

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is True
        path_info = executor.variables['__smart_jump_path__']
        assert path_info['target_page_id'] == 'page_1'
        # 混合图最短路径：页面4 → 点击A → 页面2 → 点击B → 页面1
        assert path_info['path'] == ['page_4', 'op_a', 'page_2', 'op_b', 'page_1']

    def test_current_page_live_eval(self, monkeypatch):
        """变量为空 → 现场评估命中并写回"""
        executor = make_executor(monkeypatch, current_page='', live_eval=lambda: 'page_2')
        node = executor.project.tasks['task_main'].nodes[0]

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is True
        assert executor.variables['current_page_id'] == 'page_2'
        assert executor.variables['__smart_jump_path__']['path'][0] == 'page_2'

    def test_current_page_unknown_fails(self, monkeypatch):
        """现场评估全不匹配 → 无法确定当前位置 → 失败"""
        executor = make_executor(monkeypatch, current_page='', live_eval=lambda: '')
        node = executor.project.tasks['task_main'].nodes[0]

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is False
        assert '无法确定当前页面' in (result.get('error') or '')

    def test_already_on_target_page(self, monkeypatch):
        """当前页 == 目标页 → 无需跳转直接成功"""
        executor = make_executor(monkeypatch, current_page='page_1')
        node = executor.project.tasks['task_main'].nodes[0]

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is True
        assert '__smart_jump_path__' not in executor.variables

    def test_no_route_fails(self, monkeypatch):
        """目标页面不存在（无路可达）→ 失败"""
        executor = make_executor(monkeypatch, current_page='page_4')
        node = executor.project.tasks['task_main'].nodes[0]
        node.params['target_page_id'] = 'page_x'

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is False
        assert '寻路失败' in (result.get('error') or '')

    def test_missing_target_fails(self, monkeypatch):
        executor = make_executor(monkeypatch, current_page='page_4')
        node = executor.project.tasks['task_main'].nodes[0]
        node.params['target_page_id'] = ''

        result = SmartJumpNodeExecutor().execute(node, executor)

        assert result['success'] is False
        assert '未配置目标页面' in (result.get('error') or '')


# ========== 3. 寻路正确性（4321 环形） ==========

class TestPathfinding:
    def test_shortest_path_4321(self, monkeypatch):
        executor = make_executor(monkeypatch, current_page='page_4')
        path = executor.find_path_to_page('page_1')
        assert path.success
        assert path.path == ['page_4', 'op_a', 'page_2', 'op_b', 'page_1']

    def test_manual_jump_to_page2_recomputes(self, monkeypatch):
        """用户手操到页面2 → 从页面2 直接计算到页面1 的最短路径"""
        executor = make_executor(monkeypatch, current_page='page_2')
        path = executor.find_path_to_page('page_1')
        assert path.success
        assert path.path == ['page_2', 'op_b', 'page_1']

    def test_ring_back_to_page2(self, monkeypatch):
        """环形：页面1 → 页面2（经点击C）"""
        executor = make_executor(monkeypatch, current_page='page_1')
        path = executor.find_path_to_page('page_2')
        assert path.success
        assert path.path == ['page_1', 'op_c', 'page_2']


# ========== 4. 路径执行循环 ==========

class TestPathExecution:
    def test_full_path_success(self, monkeypatch):
        """4→2→1 全链路：操作执行 + 页面确认 + 到达目标"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor)
        # 位置序列：起点 page_4；op_a 后到 page_2、page2 确认后仍在 page_2、op_b 后到 page_1
        calls = install_fake_runner(executor, monkeypatch, ['page_4', 'page_2', 'page_2', 'page_1', 'page_1'])

        assert executor._execute_smart_jump_path() is True

        # 逐节点执行：点击A → 页面2(确认) → 点击B；op_b 后现场识别已在目标页，page1 节点无需再执行
        assert calls == ['op_a', 'page2', 'op_b']
        # 路径变量已清理
        assert '__smart_jump_path__' not in executor.variables

    def test_manual_intervention_reroutes(self, monkeypatch):
        """执行中用户手操回退到页面4 → 位置偏离路径 → 重新寻路 → 最终成功"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor)
        # 第一轮：起点 page_4；op_a 后到 page_2；page_2 确认后用户手操回退到 page_4（不在剩余路径）
        # 第二轮：重新寻路后 op_a → page_2 → op_b → page_1
        calls = install_fake_runner(
            executor, monkeypatch,
            ['page_4', 'page_2', 'page_4', 'page_4', 'page_2', 'page_2', 'page_1', 'page_1']
        )

        assert executor._execute_smart_jump_path() is True

        # 两轮执行：第一轮 op_a、page2(确认后手操回退)；第二轮 op_a、page2、op_b（识别到目标后结束）
        assert calls == ['op_a', 'page2', 'op_a', 'page2', 'op_b']
        # 日志记录了重新寻路
        assert any('重新寻路' in (m.get('message') or '') for m in executor.logs)

    def test_path_node_failure_fails(self, monkeypatch):
        """路径中操作节点执行失败 → 跳转失败（重试后仍失败）"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor)

        def failing_run(node):
            if node.node_id == 'op_b':
                return {'success': False, 'error': '匹配失败'}
            return {'success': True}

        # 位置正常推进：轮1 起点 page_4 → op_a 后 page_2 → page_2 确认后 page_2（队列耗尽回退变量）
        install_fake_runner(executor, monkeypatch, ['page_4', 'page_2', 'page_2'], run=failing_run)

        assert executor._execute_smart_jump_path() is False
        assert any('匹配失败' in (m.get('message') or '') for m in executor.logs)

    def test_no_route_after_reroute_fails(self, monkeypatch):
        """位置漂移到无路可达的页面 → 重试后失败"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor)
        # 轮1：起点 page_4，op_a 后漂移到 page_3（无路）；之后每轮起点/执行后均 page_3
        install_fake_runner(executor, monkeypatch, ['page_4', 'page_3', 'page_3', 'page_3', 'page_3'])

        assert executor._execute_smart_jump_path() is False
        assert any('无路可达' in (m.get('message') or '') for m in executor.logs)

    def test_timeout_fails(self, monkeypatch):
        """整体超时 → 失败"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor, timeout=100)  # 100ms 极短超时

        def slow_run(node):
            time.sleep(0.15)  # 单步即超时
            return {'success': True}

        install_fake_runner(executor, monkeypatch, ['page_4'], run=slow_run)

        assert executor._execute_smart_jump_path() is False
        assert any('超时' in (m.get('message') or '') for m in executor.logs)


# ========== 5. 日志播报 ==========

class TestPathLogging:
    def test_every_topology_node_logged(self, monkeypatch):
        """路径上每个拓扑节点（操作与页面）均播报日志，含节点名"""
        executor = make_executor(monkeypatch, current_page='page_4')
        put_path(executor)
        install_fake_runner(executor, monkeypatch, ['page_4', 'page_2', 'page_2', 'page_1', 'page_1'])

        assert executor._execute_smart_jump_path() is True

        messages = [m.get('message') or '' for m in executor.logs]
        path_msgs = [m for m in messages if '路径节点' in m]
        # 执行了 3 个节点（op_b 后识别到目标页，page1 节点无需执行）
        assert len(path_msgs) == 3
        for node_name in ('点击A', '页面2', '点击B'):
            assert any(node_name in m for m in path_msgs), f'缺少节点日志: {node_name}'
        # 起止日志
        assert any('开始执行跳转' in m for m in messages)
        assert any('跳转成功' in m for m in messages)
