"""节点循环与调用流程重复的可信语义回归测试。"""

import pytest

from core.executor import GraphExecutor
from core.models import Edge, Node, Project, Task
from core.registry import NodeExecutorRegistry


class CountingExecutor:
    calls = 0
    fail_at = None

    def execute(self, node, executor):
        type(self).calls += 1
        success = type(self).fail_at is None or type(self).calls < type(self).fail_at
        return {'success': success}


def _node(loop_count=1):
    return Node(
        node_id='n1',
        node_name='计数节点',
        node_type='test_counting',
        params={},
        delay_before=0,
        loop_count=loop_count,
    )


def _executor(monkeypatch, *, node_loop=1, edges=None):
    monkeypatch.setitem(NodeExecutorRegistry._executors, 'test_counting', CountingExecutor)
    CountingExecutor.calls = 0
    CountingExecutor.fail_at = None
    task = Task(
        task_id='main',
        task_name='主任务',
        nodes=[_node(node_loop)],
    )
    project = Project(project_name='loop-test', tasks={'main': task}, edges=edges or [])
    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    executor.log = lambda *args, **kwargs: None
    return executor


def test_finite_node_loop_executes_every_success(monkeypatch):
    executor = _executor(monkeypatch, node_loop=3)

    executor.run('main')

    assert CountingExecutor.calls == 3


def test_node_loop_stops_on_first_failure(monkeypatch):
    executor = _executor(monkeypatch, node_loop=5)
    CountingExecutor.fail_at = 3

    with pytest.raises(RuntimeError, match='执行失败'):
        executor.run('main')

    assert CountingExecutor.calls == 3


def test_missing_start_node_is_an_error(monkeypatch):
    executor = _executor(monkeypatch)

    try:
        executor.run('main', 'missing')
    except ValueError as exc:
        assert '不存在起始节点' in str(exc)
    else:
        raise AssertionError('缺失起始节点不应被静默回退到第一个节点')
