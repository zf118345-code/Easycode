from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from core.builder import compiler_service
from core.services import process_lifecycle


class FakeProcess:
    def __init__(self, pid: int = 4242):
        self.pid = pid
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = -1
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_windows_process_cleanup_targets_exact_pid_tree(monkeypatch):
    process = FakeProcess(7311)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, '', '')

    monkeypatch.setattr(process_lifecycle.subprocess, 'run', fake_run)
    result = process_lifecycle.terminate_process_tree(process)

    assert calls[0][0] == ['taskkill', '/PID', '7311', '/T', '/F']
    assert calls[0][1]['check'] is False
    assert calls[0][1].get('shell') is None
    assert result == {'terminated': True, 'pid': 7311, 'tree_kill': True}


def test_compiler_timeout_terminates_tree_and_removes_snapshot(monkeypatch, tmp_path: Path):
    from core.services.build_snapshot_service import BuildSnapshotService
    from core.services.export_service import ExportService
    from core.services.preflight_service import PreflightService

    fake_process = FakeProcess(8442)
    removed = []
    terminated = []

    def communicate(timeout):
        raise subprocess.TimeoutExpired('build-player', timeout)

    fake_process.communicate = communicate
    monkeypatch.setattr(PreflightService, 'check', lambda *_args, **_kwargs: {'counts': {'error': 0}})
    monkeypatch.setattr(ExportService, 'get_form_schema', lambda _path: {})
    monkeypatch.setattr(BuildSnapshotService, 'create', lambda _path: {
        'path': str(tmp_path / 'snapshot'), 'project_id': 'project-1', 'revision': 'revision-1',
    })
    monkeypatch.setattr(BuildSnapshotService, 'remove', lambda snapshot: removed.append(snapshot))
    monkeypatch.setattr(compiler_service.subprocess, 'Popen', lambda *_args, **_kwargs: fake_process)

    def terminate(process):
        terminated.append(process.pid)
        process.returncode = -9
        return {'terminated': True, 'pid': process.pid, 'tree_kill': True}

    monkeypatch.setattr(compiler_service, 'terminate_process_tree', terminate)

    with pytest.raises(HTTPException) as captured:
        compiler_service.CompilerService.compile_player_exe(str(tmp_path))

    assert captured.value.status_code == 504
    assert '已终止 PyInstaller 进程树' in str(captured.value.detail)
    assert terminated == [8442]
    assert len(removed) == 1
