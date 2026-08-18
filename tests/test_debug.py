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


def test_stop_execution_releases_breakpoint_pause():
    """ExecutionService.stop_execution：断点暂停中停止 → 释放阻塞并终止执行（无需先 resume）"""
    from core.services import execution_service as es_mod
    from core.services.execution_service import ExecutionService

    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_stop', executor, 'task_main')
    session.add_breakpoint('n1')
    executor.debug_session = session
    DebugService.register_session(session)
    with es_mod._status_lock:
        es_mod._active_executors['sess_stop'] = executor

    try:
        t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
        t.start()
        assert wait_paused(session) > 0, '断点 n1 未触发暂停'
        assert session._current_node_id == 'n1'

        # 模拟前端 /stop：仅置停止标志 + 释放暂停阻塞，不 resume 执行
        r = ExecutionService.stop_execution('sess_stop')
        assert r['status'] == 'success'

        t.join(timeout=5)
        assert not t.is_alive(), '停止后执行未终止（断点阻塞未被释放）'
        assert executor.is_stopped is True
    finally:
        with es_mod._status_lock:
            es_mod._active_executors.pop('sess_stop', None)
        with DebugService._lock:
            DebugService._sessions.pop('sess_stop', None)


def test_dynamic_breakpoint_added_while_paused():
    """暂停期间动态修改断点（移除 n1、新增 n3）→ 恢复后在新断点 n3 前再次暂停"""
    project = make_project()
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    session = DebugSession('sess_dyn', executor, 'task_main')
    session.add_breakpoint('n1')
    executor.debug_session = session

    t = threading.Thread(target=executor.run, args=('task_main',), daemon=True)
    t.start()
    c1 = wait_paused(session)
    assert c1 > 0, '断点 n1 未触发暂停'
    assert session._current_node_id == 'n1'

    # 暂停期间覆盖断点集合：移除 n1、新增 n3（等价前端 setBreakpoints(['n3'])）
    session.remove_breakpoint('n1')
    session.add_breakpoint('n3')
    session.resume()

    c2 = wait_pause_count(session, c1 + 1)
    assert c2 > c1, '动态断点 n3 未生效'
    assert session._pause_reason == 'breakpoint'
    assert session._current_node_id == 'n3', f'应暂停在 n3，实际 {session._current_node_id}'

    session.resume()
    t.join(timeout=5)
    assert not t.is_alive(), '恢复后执行未结束'


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


# ========== #7 执行记录持久化与日志上限 ==========

def test_executor_logs_capped(monkeypatch, tmp_path):
    """executor.logs 条数上限：超限裁剪保留最近 N 条（防 base64 图片日志撑爆内存）"""
    from core.executor import GraphExecutor

    ex = GraphExecutor.__new__(GraphExecutor)
    import threading
    ex._logs_lock = threading.Lock()
    ex.logs = []
    ex.max_logs = 50
    ex.variables = {}
    # log() 内 resolve_template_string 需要变量
    from core.utils import resolve_template_string
    monkeypatch.setattr('core.executor.resolve_template_string', lambda s, ctx: str(s))

    for i in range(120):
        ex.log(f'日志第{i}条')
    assert len(ex.logs) == 50
    assert ex.logs[0]['message'] == '日志第70条'  # 裁剪保留最近 50 条
    assert ex.logs[-1]['message'] == '日志第119条'


def test_execution_db_persists_logs(tmp_path, monkeypatch):
    """ExecutionDB 落盘：创建执行 → 写日志 → 查询带回（#7 SQLite 接回）"""
    import os
    import core.db as db_mod
    from core.services.execution_db import ExecutionDB

    db_path = str(tmp_path / 'exec.db')
    monkeypatch.setenv('EASYCODE_DB_PATH', db_path)
    monkeypatch.setattr(db_mod, 'get_db_path', lambda: db_path)
    monkeypatch.setattr(db_mod, 'DB_PATH', db_path)
    monkeypatch.setattr(db_mod, 'DB_DIR', str(tmp_path))
    ExecutionDB._ensure_db()

    eid = 'task_test_1'
    assert ExecutionDB.create_execution(eid, 'D:/proj', 'task_test') is True
    assert ExecutionDB.update_status(eid, 'success', '执行完成') is True
    assert ExecutionDB.add_logs(eid, [
        {'time': '10:00:00', 'message': '第一条', 'level': 'info', 'image': None},
        {'time': '10:00:01', 'message': '第二条', 'level': 'warning', 'image': None},
    ]) is True

    status = ExecutionDB.get_status(eid)
    assert status['status']['status'] == 'success'  # 嵌套结构：{status: {status, message}, logs}
    assert status['status']['message'] == '执行完成'
    logs = ExecutionDB.get_logs(eid)
    assert [l['message'] for l in logs] == ['第一条', '第二条']

    # 变量快照
    assert ExecutionDB.save_variable(eid, 'count', 42, 'int') is True
    vars_ = ExecutionDB.get_variables(eid)
    assert vars_.get('count') == 42

    # 清理
    assert ExecutionDB.delete_execution(eid) is True
    assert ExecutionDB.get_status(eid) is None
    if os.path.exists(db_path):
        os.remove(db_path)
