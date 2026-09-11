from __future__ import annotations

import gc
import json
import os
import time
import tracemalloc
from collections import deque
from pathlib import Path

import pytest
import psutil
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.execution_worker import VNextWorkerProxy
from core.vnext.program_commands import StatementLocation, insert_call, insert_loop
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import DurationValue, IntValue, StringValue, create_program_document
from core.vnext.runtime import RuntimeFailure, RuntimeSession, VNextRuntime, vnext_runtime

TERMINAL = {'completed', 'failed', 'cancelled'}


def test_player_instance_persists_recent_failure_diagnostic_without_recording(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance_root = tmp_path / 'instance'
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(instance_root))
    runtime = VNextRuntime(use_worker_process=False)
    session = RuntimeSession(
        execution_id='execution_support',
        status='failed',
        error='目标操作失败',
        error_id='runtime.test_failure',
    )

    runtime._prepare_event_log(session)
    runtime._event(session, 'error', 'runtime', '目标操作失败')
    runtime._close_event_log(session)
    runtime._create_diagnostics(session, None)

    expected = instance_root / 'runtime' / 'diagnostics' / 'execution_support' / 'diagnostic.zip'
    assert Path(session.diagnostic_bundle) == expected
    assert expected.is_file()
    runtime._safe_remove_session_artifacts(session)
    assert expected.is_file(), '最近失败诊断必须在 Runtime 会话过期后仍可由控制台导出'


def test_worker_proxy_cleanup_is_idempotent_after_process_handle_close():
    class FakeProcess:
        pid = 0

        def __init__(self) -> None:
            self.closed = False

        def is_alive(self):
            if self.closed:
                raise ValueError('process object is closed')
            return False

        def join(self, timeout=None):
            if self.closed:
                raise OSError(6, 'invalid handle')

        def close(self):
            self.closed = True

    class FakeQueue:
        _reader = None
        _writer = None

        def close(self):
            return None

        def join_thread(self):
            return None

    proxy = VNextWorkerProxy(FakeProcess(), FakeQueue(), FakeQueue())
    proxy.close()
    proxy.join(timeout=0)
    proxy.terminate_tree()
    proxy.close()
    assert proxy.is_alive() is False


def compiled_logs(count: int, project_path: Path) -> dict:
    project_path.mkdir(parents=True, exist_ok=True)
    document = create_program_document('主程序')
    loop = insert_loop(
        document,
        'repeat',
        IntValue(value_id='value_repeat_count', value=count),
    )
    statement_id = loop.selected_statement_id
    document = insert_call(
        loop.document,
        official_function_registry_v6,
        'official.log.output',
        location=StatementLocation(parent_statement_id=statement_id, block='body'),
        arguments={
            'official.log.output.parameter.content': StringValue(
                value_id='value_log_content', value='事件',
            ),
        },
    ).document
    compiled = compile_program_document(document, official_function_registry_v6)
    assert compiled['valid'], compiled['diagnostics']
    return adapt_program_ecir_for_runtime(compiled['ecir'], project_path=str(project_path))


def compiled_wait(milliseconds: int, project_path: Path) -> dict:
    project_path.mkdir(parents=True, exist_ok=True)
    document = create_program_document('主程序')
    document = insert_call(
        document,
        official_function_registry_v6,
        'official.wait.duration',
        arguments={
            'official.wait.duration.parameter.duration': DurationValue(
                value_id='value_wait_duration', milliseconds=milliseconds,
            ),
        },
    ).document
    compiled = compile_program_document(document, official_function_registry_v6)
    assert compiled['valid'], compiled['diagnostics']
    return adapt_program_ecir_for_runtime(compiled['ecir'], project_path=str(project_path))


def wait_terminal(runtime: VNextRuntime, execution_id: str) -> dict:
    deadline = time.monotonic() + 5
    snapshot = runtime.snapshot(execution_id)
    while snapshot['status'] not in TERMINAL and time.monotonic() < deadline:
        time.sleep(0.01)
        snapshot = runtime.snapshot(execution_id)
    assert snapshot['status'] in TERMINAL, snapshot
    return snapshot


def test_runtime_snapshot_projects_stable_ids_to_user_facing_current_values() -> None:
    session = RuntimeSession(
        execution_id='execution-values',
        current_source={'function_id': 'function.main', 'statement_id': 'stmt.assign'},
        variables={'symbol.health': 86, 'symbol.other-function': 99},
        project_variables={'variable.minimum': 18},
        local_variable_definitions={
            'symbol.health': {
                'function_id': 'function.main', 'display_name': '当前体力',
                'value_type': 'int64', 'kind': 'local',
            },
            'symbol.other-function': {
                'function_id': 'function.other', 'display_name': '其他函数的值',
                'value_type': 'int64', 'kind': 'local',
            },
        },
        project_variable_definitions={
            'variable.minimum': {
                'display_name': '最低体力', 'value_type': 'int64',
            },
        },
    )

    snapshot = session.snapshot()

    assert snapshot['value_entries']['local'] == [{
        'id': 'symbol.health', 'display_name': '当前体力', 'value_type': 'int64',
        'kind': 'local', 'value': 86,
    }]
    assert snapshot['value_entries']['project'][0]['display_name'] == '最低体力'


def test_runtime_adapter_attaches_statement_source_for_debug_navigation(tmp_path: Path) -> None:
    plan = compiled_wait(1, tmp_path)
    instruction = plan['functions'][0]['instructions'][0]

    assert instruction['source']['statement_id'] == instruction['instruction_id']
    assert instruction['source']['function_id'] == plan['entry_function_id']


def test_active_runtime_snapshots_are_project_scoped_and_newest_first(tmp_path: Path) -> None:
    runtime = VNextRuntime(persist_event_log=False)
    project = tmp_path / 'active-project'
    other_project = tmp_path / 'other-project'
    project.mkdir()
    other_project.mkdir()
    runtime._sessions.update({
        'execution-older': RuntimeSession(
            'execution-older', status='paused', started_at='2026-09-10T01:00:00+00:00',
            project_path=str(project),
        ),
        'execution-newer': RuntimeSession(
            'execution-newer', status='running', started_at='2026-09-10T02:00:00+00:00',
            project_path=str(project),
        ),
        'execution-finished': RuntimeSession(
            'execution-finished', status='completed', started_at='2026-09-10T03:00:00+00:00',
            project_path=str(project),
        ),
        'execution-other': RuntimeSession(
            'execution-other', status='running', started_at='2026-09-10T04:00:00+00:00',
            project_path=str(other_project),
        ),
    })

    snapshots = runtime.active_snapshots(str(project / '.'))

    assert [item['execution_id'] for item in snapshots] == [
        'execution-newer', 'execution-older',
    ]
    assert [item['status'] for item in snapshots] == ['running', 'paused']


def test_active_runs_http_endpoint_uses_workspace_identity(tmp_path: Path) -> None:
    project = tmp_path / 'http-active-run'
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    opened = client.post('/api/vnext/workspaces/open', json={
        'path': str(project), 'initialize': True, 'project_name': '刷新恢复项目',
    })
    assert opened.status_code == 200, opened.text
    workspace = opened.json()['workspace']
    headers = {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }
    execution_id = 'execution-http-refresh-recovery'
    vnext_runtime._sessions[execution_id] = RuntimeSession(
        execution_id,
        status='paused',
        started_at='2026-09-10T05:00:00+00:00',
        project_path=str(project.resolve()),
    )
    try:
        response = client.get('/api/vnext/runs/active', headers=headers)
    finally:
        vnext_runtime._sessions.pop(execution_id, None)

    assert response.status_code == 200, response.text
    assert [(item['execution_id'], item['status']) for item in response.json()['runs']] == [
        (execution_id, 'paused'),
    ]


def test_runtime_uses_bounded_event_window_and_full_jsonl_log(tmp_path: Path):
    runtime = VNextRuntime(event_buffer_size=10)
    started = runtime.start(compiled_logs(30, tmp_path))
    snapshot = wait_terminal(runtime, started['execution_id'])

    assert len(snapshot['events']) == 10
    assert snapshot['events'][0]['sequence'] > 1
    assert snapshot['event_cursor'] == 32  # start + 30 script lines + completed
    log_path = tmp_path / '.easycode' / 'runtime-logs' / f'{started["execution_id"]}.jsonl'
    rows = [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 32
    assert [item['sequence'] for item in rows] == list(range(1, 33))

    incremental = runtime.snapshot(started['execution_id'], after_sequence=30)
    assert [item['sequence'] for item in incremental['events']] == [31, 32]
    assert incremental['events_truncated'] is False
    truncated = runtime.snapshot(started['execution_id'], after_sequence=1)
    assert truncated['events_truncated'] is True


def test_runtime_prunes_old_terminal_sessions_and_artifacts(tmp_path: Path):
    runtime = VNextRuntime(event_buffer_size=10, max_sessions=2)
    executions = []
    for index in range(3):
        started = runtime.start(compiled_logs(1, tmp_path / f'project-{index}'))
        wait_terminal(runtime, started['execution_id'])
        executions.append(started['execution_id'])

    with pytest.raises(RuntimeFailure, match='运行会话不存在'):
        runtime.snapshot(executions[0])
    assert runtime.snapshot(executions[1])['status'] == 'completed'
    assert runtime.snapshot(executions[2])['status'] == 'completed'


def test_virtual_twenty_four_hour_event_volume_has_a_flat_bounded_memory_curve():
    """Model one event per second for 24 hours without a 24-hour PTY."""

    runtime = VNextRuntime(event_buffer_size=128, max_sessions=12, persist_event_log=False)
    session = RuntimeSession('execution_virtual_soak')
    session.events = deque(maxlen=128)

    tracemalloc.start()
    try:
        for index in range(12 * 60 * 60):
            runtime._event(session, 'info', 'soak', f'virtual-second-{index}')
        gc.collect()
        midpoint, _midpoint_peak = tracemalloc.get_traced_memory()

        for index in range(12 * 60 * 60, 24 * 60 * 60):
            runtime._event(session, 'info', 'soak', f'virtual-second-{index}')
        gc.collect()
        endpoint, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert session.next_event_sequence == 24 * 60 * 60
    assert len(session.events) == 128
    assert endpoint - midpoint < 512 * 1024
    assert peak < 4 * 1024 * 1024

    now = time.monotonic()
    for index in range(8 * 60):
        terminal = RuntimeSession(
            f'execution_virtual_{index}',
            status='completed',
            finished_at='virtual',
            finished_monotonic=now + index,
        )
        runtime._sessions[terminal.execution_id] = terminal
        runtime._prune_sessions()
    assert len(runtime._sessions) == 12


def test_sse_event_stream_replays_then_ends(tmp_path: Path):
    started = vnext_runtime.start(compiled_logs(2, tmp_path))
    wait_terminal(vnext_runtime, started['execution_id'])
    app = FastAPI()
    app.include_router(create_vnext_router())

    response = TestClient(app).get(f'/api/vnext/runs/{started["execution_id"]}/events?after_sequence=0')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    payload = response.content.decode('utf-8')
    assert 'event: runtime' in payload
    assert 'event: end' in payload
    assert payload.count('event: runtime') == 4


def test_worker_crash_isolated_from_another_execution(tmp_path: Path):
    runtime = VNextRuntime(use_worker_process=True)
    try:
        long_ecir = compiled_wait(2_000, tmp_path / 'long')
        short_ecir = compiled_wait(20, tmp_path / 'short')

        first = runtime.start(long_ecir)
        second = runtime.start(short_ecir)
        runtime._sessions[first['execution_id']]._worker_proxy.terminate_tree()

        failed = wait_terminal(runtime, first['execution_id'])
        completed = wait_terminal(runtime, second['execution_id'])
        assert failed['status'] == 'failed'
        assert 'Worker' in failed['error']
        assert completed['status'] == 'completed', completed
    finally:
        runtime.shutdown()


def test_worker_hard_timeout_terminates_stuck_execution(tmp_path: Path):
    runtime = VNextRuntime(use_worker_process=True)
    try:
        ecir = compiled_wait(5_000, tmp_path)
        started = runtime.start(ecir, debug={'hard_timeout_ms': 500})
        snapshot = wait_terminal(runtime, started['execution_id'])
        assert snapshot['status'] == 'failed'
        assert '硬超时' in snapshot['error']
    finally:
        runtime.shutdown()


def test_worker_cancel_finishes_without_leaving_child_alive(tmp_path: Path):
    runtime = VNextRuntime(use_worker_process=True)
    try:
        ecir = compiled_wait(5_000, tmp_path)
        started = runtime.start(ecir)
        execution_id = started['execution_id']
        deadline = time.monotonic() + 5
        while not runtime.snapshot(execution_id)['worker']['started'] and time.monotonic() < deadline:
            time.sleep(0.01)
        runtime.cancel(execution_id)
        snapshot = wait_terminal(runtime, execution_id)
        assert snapshot['status'] == 'cancelled', snapshot
        worker_pid = runtime._sessions[execution_id].worker_pid
        deadline = time.monotonic() + 2
        while psutil.pid_exists(worker_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert psutil.pid_exists(worker_pid) is False
        deadline = time.monotonic() + 2
        while runtime._sessions[execution_id]._worker_proxy is not None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runtime._sessions[execution_id]._worker_proxy is None
    finally:
        runtime.shutdown()


@pytest.mark.skipif(os.name != 'nt', reason='Windows handle-count regression')
def test_completed_workers_release_parent_process_handles(tmp_path: Path):
    process = psutil.Process()
    runtime = VNextRuntime(use_worker_process=True, persist_event_log=False)
    try:
        # The first spawn initializes multiprocessing's process-wide tracker.
        warmup = runtime.start(compiled_logs(1, tmp_path / 'worker-warmup'))
        assert wait_terminal(runtime, warmup['execution_id'])['status'] == 'completed'
        baseline = process.num_handles()
        for index in range(8):
            started = runtime.start(compiled_logs(1, tmp_path / f'worker-{index}'))
            execution_id = started['execution_id']
            assert wait_terminal(runtime, execution_id)['status'] == 'completed'
            deadline = time.monotonic() + 2
            while runtime._sessions[execution_id]._worker_proxy is not None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert runtime._sessions[execution_id]._worker_proxy is None
        time.sleep(0.1)
        # Runtime-only synchronization primitives are released at every
        # execution boundary. The test must not need external collection to
        # make this assertion pass.
        assert process.num_handles() - baseline <= 4
        assert all(
            runtime._sessions[item]._resume_gate is None
            for item in runtime._sessions
            if item != warmup['execution_id']
        )
    finally:
        runtime.shutdown()
