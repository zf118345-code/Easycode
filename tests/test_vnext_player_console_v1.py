from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.player_app import create_player_app, create_player_console_app
from core.vnext.player_console_v1 import PlayerConsoleV1
from core.vnext.schedule_v6 import ScheduleError
import core.vnext.player_console_v1 as player_console_module
import player


CONSOLE_OPERATIONS = {
    ('GET', '/api/vnext/player-console'),
    ('GET', '/api/vnext/player-console/lifecycle/close-status'),
    ('POST', '/api/vnext/player-console/lifecycle/prepare-close'),
    ('POST', '/api/vnext/player-console/instances'),
    ('DELETE', '/api/vnext/player-console/instances/{instance_id}'),
    ('POST', '/api/vnext/player-console/instances/{instance_id}/connect'),
    ('GET', '/api/vnext/player-console/instances/{instance_id}/state'),
    ('GET', '/api/vnext/player-console/instances/{instance_id}/diagnostics'),
    ('POST', '/api/vnext/player-console/instances/{instance_id}/pause'),
    ('POST', '/api/vnext/player-console/instances/{instance_id}/resume'),
    ('POST', '/api/vnext/player-console/instances/{instance_id}/stop'),
    ('POST', '/api/vnext/player-console/instances/{instance_id}/restart'),
}


def _operations(app) -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, value in app.openapi()['paths'].items()
        for method in value
        if method in {'get', 'post', 'put', 'patch', 'delete'}
    }


def test_console_app_is_a_small_loopback_only_surface(tmp_path: Path) -> None:
    (tmp_path / 'console.html').write_text('<main>console</main>', encoding='utf-8')
    app = create_player_console_app(tmp_path)
    assert _operations(app) == CONSOLE_OPERATIONS
    with TestClient(app) as client:
        page = client.get('/console.html')
        assert page.status_code == 200
        assert "frame-src http://127.0.0.1:*" in page.headers['content-security-policy']
        assert page.headers['x-frame-options'] == 'DENY'
        assert client.get('/api/vnext/workspaces/active').status_code == 404


def test_normal_player_rejects_frames_and_console_worker_allows_only_current_origin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / 'player.html').write_text('<main>player</main>', encoding='utf-8')
    origin_file = tmp_path / 'console-origin.txt'
    with TestClient(create_player_app(tmp_path)) as client:
        response = client.get('/player.html')
        assert response.headers['x-frame-options'] == 'DENY'
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']

    origin_file.write_text('http://127.0.0.1:43127\n', encoding='utf-8')
    monkeypatch.setenv('EASYCODE_PLAYER_CONSOLE_ORIGIN_FILE', str(origin_file))
    with TestClient(create_player_app(tmp_path)) as client:
        response = client.get('/player.html')
        assert 'x-frame-options' not in response.headers
        assert 'frame-ancestors http://127.0.0.1:43127' in response.headers['content-security-policy']

    origin_file.write_text('https://attacker.example\n', encoding='utf-8')
    with TestClient(create_player_app(tmp_path)) as client:
        response = client.get('/player.html')
        assert response.headers['x-frame-options'] == 'DENY'


class _Process:
    pid = 4321

    @staticmethod
    def poll():
        return None


class _Registry:
    def __init__(self, root: Path) -> None:
        self.instance = {
            'instance_id': 'instance_a',
            'installation_id': 'install_a',
            'product_id': 'product_a',
            'display_name': '账号 A',
            'data_root': str(root),
            'enabled': True,
            'status': 'ready',
            'installation': {'display_name': '测试产品'},
        }

    def get_instance(self, _instance_id: str, *, include_profiles: bool):
        return dict(self.instance)

    def list_instances(self, *, include_profiles: bool):
        return [dict(self.instance)]

    @staticmethod
    def list_installations(*, include_profiles: bool):
        return [{'installation_id': 'install_a', 'product_id': 'product_a', 'display_name': '测试产品', 'release_id': 'r1', 'enabled': True}]

    @staticmethod
    def create_instance(*_args, **_kwargs):
        return {}

    def launch_instance_console_worker(
        self,
        instance_id: str,
        *,
        descriptor_path: Path,
        console_origin_path: Path,
        console_origin: str,
        console_parent_pid: int,
    ):
        Path(descriptor_path).write_text(json.dumps({
            'schema_version': 1,
            'instance_id': instance_id,
            'process_id': _Process.pid,
            'port': 43210,
        }), encoding='utf-8')
        assert Path(console_origin_path).read_text(encoding='utf-8').strip() == console_origin
        assert console_parent_pid > 0
        return _Process()


def test_console_connects_one_isolated_worker_and_reuses_its_frame(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = _Registry(tmp_path / 'instance-a')
    hub = SimpleNamespace(registry=registry)
    monkeypatch.setattr(
        'core.vnext.player_console_v1._request_json',
        lambda *_args, **_kwargs: {
            'instance_id': 'instance_a',
            'instance_name': '账号 A',
            'execution': None,
        },
    )
    console = PlayerConsoleV1(hub=hub, startup_timeout=1)

    first = console.connect('instance_a', 'http://127.0.0.1:41000')
    second = console.connect('instance_a', 'http://127.0.0.1:41000')

    assert first['process_id'] == 4321
    assert first['frame_url'] == 'http://127.0.0.1:43210/player.html?embedded=1'
    assert second['process_id'] == first['process_id']
    assert (tmp_path / 'instance-a' / 'console' / 'owner.pid').is_file()
    assert (tmp_path / 'instance-a' / 'console' / 'console-origin.txt').read_text(encoding='utf-8').strip() == 'http://127.0.0.1:41000'


def test_console_support_bundle_survives_unreachable_worker(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'instance-a'
    registry = _Registry(root)
    registry.instance['installation'] = {'display_name': '超能世界', 'release_id': 'release-1'}
    console_dir = root / 'console'
    console_dir.mkdir(parents=True)
    (console_dir / 'worker.json').write_text(json.dumps({
        'schema_version': 1,
        'instance_id': 'instance_a',
        'instance_name': '账号 A',
        'process_id': 4321,
        'port': 43210,
        'started_at': '2026-09-11T20:00:00+08:00',
    }), encoding='utf-8')
    logs = root / 'logs'
    logs.mkdir()
    (logs / 'player.log').write_text('worker started\nlast useful error\n', encoding='utf-8')
    (root / 'secret-profile.json').write_text('{"password":"must-not-export"}', encoding='utf-8')

    def unreachable(*_args, **_kwargs):
        raise ScheduleError(
            '无法连接该 Player 实例工作进程',
            error_id='schedule.instance_worker_unreachable',
            transient=True,
        )

    monkeypatch.setattr(player_console_module, '_request_json', unreachable)
    bundle = PlayerConsoleV1(hub=SimpleNamespace(registry=registry)).create_support_bundle('instance_a')

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        summary = json.loads(archive.read('summary.json').decode('utf-8'))
        combined = b'\n'.join(archive.read(name) for name in names)
    assert summary['worker']['reachable'] is False
    assert summary['worker']['connection_error'].startswith('schedule.instance_worker_unreachable:')
    assert 'logs/instance-player.log' in names
    assert 'privacy.json' in names
    assert b'must-not-export' not in combined


def test_console_owner_lease_atomic_refresh_retries_windows_file_contention(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / 'owner.pid'
    original = os.replace
    attempts = 0

    def briefly_blocked(source, target):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, 'temporarily locked')
        return original(source, target)

    monkeypatch.setattr(player_console_module.os, 'replace', briefly_blocked)
    player_console_module._atomic_text(path, '1234\n')
    assert attempts == 3
    assert path.read_text(encoding='utf-8') == '1234\n'


def test_console_worker_owner_lease_tolerates_blocked_pid_probe(tmp_path: Path, monkeypatch) -> None:
    owner = tmp_path / 'owner.pid'
    owner.write_text('1234\n', encoding='utf-8')
    monkeypatch.setattr(player, '_pid_alive', lambda _pid: False)
    assert player._owner_lease_alive(owner, grace_seconds=2) is True
    old = time.time() - 10
    os.utime(owner, (old, old))
    assert player._owner_lease_alive(owner, grace_seconds=2) is False


def test_console_close_requires_confirmation_and_then_stops_every_worker(monkeypatch) -> None:
    console = PlayerConsoleV1(hub=SimpleNamespace())
    status = {
        'schema_version': 1,
        'active_count': 2,
        'active_instances': [
            {'instance_id': 'a', 'instance_name': '账号 A', 'status': 'running'},
            {'instance_id': 'b', 'instance_name': '账号 B', 'status': 'paused'},
        ],
    }
    monkeypatch.setattr(console, 'close_status', lambda: status)
    console._workers.update({'a': object(), 'b': object()})
    controls: list[tuple[str, str]] = []
    stopped: list[tuple[str, bool]] = []
    monkeypatch.setattr(console, 'control', lambda instance_id, action: controls.append((instance_id, action)))
    monkeypatch.setattr(
        console,
        'stop_worker',
        lambda instance_id, allow_active=False: stopped.append((instance_id, allow_active)),
    )

    blocked = console.prepare_close(stop_active=False)
    assert blocked['ready'] is False
    assert blocked['requires_confirmation'] is True
    assert controls == []
    assert stopped == []

    ready = console.prepare_close(stop_active=True)
    assert ready['ready'] is True
    assert controls == [('a', 'stop'), ('b', 'stop')]
    assert stopped == [('a', True), ('b', True)]


def test_frozen_visible_player_uses_final_process_exit_after_orderly_shutdown() -> None:
    source = Path(player.__file__).read_text(encoding='utf-8')
    assert "if args.mode == 'prod':" in source
    assert 'server_thread.join(timeout=10)' in source


def test_console_parent_probe_distinguishes_exited_windows_process() -> None:
    process = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(10)'],
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    try:
        assert player._pid_alive(process.pid) is True
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert player._pid_alive(process.pid) is False


def test_direct_packaged_entry_registers_and_opens_console_for_product(
    tmp_path: Path,
    monkeypatch,
) -> None:
    release = tmp_path / 'release'
    release.mkdir()
    for path in (
        tmp_path / 'EasycodePlayer.exe',
        tmp_path / 'build_manifest.json',
        release / 'project.ecplayer',
        release / 'trust-root.json',
    ):
        path.write_bytes(b'boundary')
    registered: list[Path] = []
    shutdown = []
    registry = SimpleNamespace(register_distribution=lambda root, **_kwargs: (
        registered.append(Path(root)) or {'product_id': 'product_game'}
    ))
    monkeypatch.setattr(player, '_application_directory', lambda: tmp_path)
    monkeypatch.setattr(
        'core.vnext.schedule_hub_v6.get_player_hub_v6',
        lambda: SimpleNamespace(registry=registry),
    )
    monkeypatch.setattr(
        'core.vnext.schedule_hub_v6.shutdown_player_hub_v6',
        lambda: shutdown.append(True),
    )

    arguments = player._default_packaged_arguments([])

    assert registered == [tmp_path]
    assert shutdown == [True]
    assert arguments == [
        '--mode', 'prod', '--port', '0', '--player-console',
        '--select-product', 'product_game',
    ]


def test_direct_packaged_entry_falls_back_to_single_player_when_registration_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    release = tmp_path / 'release'
    release.mkdir()
    for path in (
        tmp_path / 'EasycodePlayer.exe',
        tmp_path / 'build_manifest.json',
        release / 'project.ecplayer',
        release / 'trust-root.json',
    ):
        path.write_bytes(b'boundary')
    monkeypatch.setattr(player, '_application_directory', lambda: tmp_path)
    monkeypatch.setattr(
        'core.vnext.schedule_hub_v6.get_player_hub_v6',
        lambda: SimpleNamespace(registry=SimpleNamespace(
            register_distribution=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('registry busy')),
        )),
    )
    monkeypatch.setattr('core.vnext.schedule_hub_v6.shutdown_player_hub_v6', lambda: None)

    assert player._default_packaged_arguments([]) == []
    assert '已回退单实例 Player' in player._DEFAULT_ENTRY_WARNING
