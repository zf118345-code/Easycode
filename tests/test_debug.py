"""断点调试链路测试：executor 注入 DebugSession 后，断点/手动暂停/单步真实生效"""

import threading
import time

import pytest

import core.node_executors  # noqa: F401 - 副作用导入，注册执行器
from core.executor import GraphExecutor
from core.models import Edge, Node, Project, Task
from core.services.debug_service import DebugService, DebugSession


def make_project(node_ids=('n1', 'n2', 'n3')):
    """构造无副作用项目（wait 节点，秒数 0）"""
    nodes = [
        Node(
            node_id=nid,
            node_name=f'节点{i + 1}',
            node_type='wait',
            params={'seconds': 0},
            delay_before=0,
            loop_count=1,
        )
        for i, nid in enumerate(node_ids)
    ]
    task = Task(task_id='task_main', task_name='主任务', nodes=nodes)
    edges = []
    for i in range(len(nodes) - 1):
        edges.append(
            Edge(
                edge_id=f'e_{i}',
                source_node=nodes[i].node_id,
                target_node=nodes[i + 1].node_id,
                source_port='success',
                canvas='workflow',
            )
        )
    return Project(project_name='debug_test', tasks={'task_main': task}, edges=edges)


def wait_paused(session, timeout=5.0):
    """等待会话完全进入暂停态（_resume_event 已 clear、执行线程已阻塞在等待），返回暂停序号"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if session._paused_ready.is_set() and session._is_paused:
            return session._pause_count
        time.sleep(0.02)
    return -1


def wait_pause_count(session, min_count, timeout=5.0):
    """等待暂停序号达到 min_count（区分同一次暂停的残留与新的暂停）"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if session._pause_count >= min_count and session._paused_ready.is_set():
            return session._pause_count
        time.sleep(0.02)
    return -1


def wait_done(executor, timeout=5.0):
    """等待执行线程结束"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not executor._thread_alive():
            return True
        time.sleep(0.05)
    return False


def test_breakpoint_pauses_and_resumes():
    """断点命中 → 阻塞在断点节点 → resume 后继续到结束"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_1', executor, 'task_main')
    session.add_breakpoint('n2')
    executor.debug_session = session

    t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
    t.start()

    assert wait_paused(session) > 0, '断点未触发暂停'
    assert session._current_node_id == 'n2', f'应暂停在 n2，实际 {session._current_node_id}'
    assert session._pause_reason == 'breakpoint'
    assert session.get_state()['is_paused'] is True

    session.resume()
    t.join(timeout=5)
    assert not t.is_alive(), '恢复后执行未结束'
    assert executor.is_stopped is False


def test_manual_pause_at_next_node():
    """手动暂停：在下一个节点执行前生效（断点锚定后手动置位，恢复时在下一节点前暂停）"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_2', executor, 'task_main')
    session.add_breakpoint('n1')
    executor.debug_session = session

    t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
    t.start()
    c1 = wait_paused(session)
    assert c1 > 0, '断点 n1 未触发暂停'

    # 手动暂停置位，然后恢复执行——下一个节点前应因 manual 暂停
    session.pause()
    session.resume()
    c2 = wait_pause_count(session, c1 + 1)
    assert c2 > c1, '手动暂停未生效'
    assert session._pause_reason == 'manual'
    assert session._current_node_id == 'n2', f'手动暂停后应停在 n2 前，实际 {session._current_node_id}'

    session.resume()
    t.join(timeout=5)
    assert not t.is_alive(), '恢复后执行未结束'


def test_step_mode_pauses_after_one_node():
    """单步模式：执行一个节点后暂停（先用断点锚定，避免执行过快竞态）"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_3', executor, 'task_main')
    session.add_breakpoint('n1')
    executor.debug_session = session

    t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
    t.start()
    c1 = wait_paused(session)
    assert c1 > 0, '断点 n1 未触发暂停'
    assert session._current_node_id == 'n1'
    first_snapshot = session.get_state()['variables']

    # 单步：从暂停处继续，执行一个节点后在下一个节点前暂停（等待新的暂停序号）
    session.step()
    c2 = wait_pause_count(session, c1 + 1)
    assert c2 > c1, '单步未触发新暂停'
    assert session._pause_reason == 'step'
    assert session._current_node_id == 'n2', f'单步后应暂停在 n2，实际 {session._current_node_id}'

    # 上一节点快照轮换：第二次暂停的 prev_variables 应等于第一次暂停的 variables
    state2 = session.get_state()
    assert state2['prev_variables'] == first_snapshot, '上一节点变量快照未正确轮换'

    # 继续执行到结束
    session.resume()
    t.join(timeout=5)
    assert not t.is_alive(), '单步恢复后执行未结束'


def test_stop_releases_pause():
    """停止：释放暂停阻塞并终止执行"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_4', executor, 'task_main')
    session.add_breakpoint('n1')
    executor.debug_session = session

    t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
    t.start()
    assert wait_paused(session) > 0, '断点未触发暂停'

    session.stop()
    t.join(timeout=5)
    assert not t.is_alive(), '停止后执行未终止'
    assert executor.is_stopped is True


def test_debug_service_register_and_control():
    """DebugService 注册后：set_breakpoints / inspect_variables / step_session 可用"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_5', executor, 'task_main')
    executor.debug_session = session
    DebugService.register_session(session)

    # 批量设置断点
    r = DebugService.set_breakpoints('sess_5', ['n1', 'n3'])
    assert set(r['breakpoints']) == {'n1', 'n3'}
    # 变量接口
    assert 'variables' in DebugService.inspect_variables('sess_5')
    # 单步签名（2 参）
    assert DebugService.step_session('sess_5', 'over')['status'] == 'stepping'
    # 清理
    with DebugService._lock:
        DebugService._sessions.pop('sess_5', None)
