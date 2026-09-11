from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.adb_discovery_v6 import (
    AdbCommandResult,
    discover_adb_candidates,
    parse_adb_devices,
)


def test_adb_device_parser_preserves_all_states_without_selecting_them() -> None:
    devices = parse_adb_devices(
        'List of devices attached\n'
        'emulator-5554 device product:sdk_phone_x86 model:Pixel_8 transport_id:1\n'
        'R5CT1234 unauthorized usb:1-2 product:phone model:Galaxy_S23 transport_id:2\n'
        '192.168.1.9:5555 offline transport_id:3\n'
    )
    assert [item['serial'] for item in devices] == [
        'emulator-5554', 'R5CT1234', '192.168.1.9:5555',
    ]
    assert devices[0] == {
        'serial': 'emulator-5554', 'state': 'device', 'selectable': True,
        'model': 'Pixel 8', 'product': 'sdk phone x86', 'transport_id': '1',
        'display_name': 'Pixel 8',
    }
    assert devices[1]['selectable'] is False
    assert devices[1]['state'] == 'unauthorized'
    assert devices[2]['selectable'] is False


def test_adb_discovery_returns_host_states_as_normal_results() -> None:
    failed = discover_adb_candidates(
        adb_path='adb-test',
        runner=lambda _command, _timeout: AdbCommandResult(1, '', 'server unavailable'),
    )
    assert failed == {
        'available': False,
        'code': 'adb_scan_failed',
        'message': 'ADB 扫描失败：server unavailable',
        'candidates': [],
    }

    def timeout(_command, timeout_seconds):
        raise subprocess.TimeoutExpired('adb', timeout_seconds)

    timed_out = discover_adb_candidates(adb_path='adb-test', runner=timeout)
    assert timed_out['available'] is False
    assert timed_out['code'] == 'adb_scan_timeout'


def test_adb_discovery_never_mutates_or_auto_selects_a_candidate() -> None:
    result = discover_adb_candidates(
        adb_path='adb-test',
        runner=lambda command, timeout: AdbCommandResult(
            0,
            'List of devices attached\nemulator-5556 device model:LDPlayer transport_id:7\n',
            '',
        ),
    )
    assert result['available'] is True
    assert result['message'] == ''
    assert result['candidates'][0]['serial'] == 'emulator-5556'
    assert 'selected' not in result
    assert 'target_id' not in result


def test_adb_candidate_endpoint_is_workspace_scoped_and_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    assert client.get('/api/vnext/targets/adb-candidates').status_code == 422

    opened = client.post('/api/vnext/workspaces/open', json={
        'path': str(tmp_path / 'adb-candidates'),
        'initialize': True,
        'project_name': 'ADB candidates',
    }).json()
    workspace = opened['workspace']
    headers = {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }
    monkeypatch.setattr(
        'core.vnext.workspace.discover_adb_candidates',
        lambda: {
            'available': True, 'code': 'ok', 'message': '',
            'candidates': [{
                'serial': 'emulator-5580', 'state': 'device', 'selectable': True,
                'model': 'Test', 'product': '', 'transport_id': '8',
                'display_name': 'Test',
            }],
        },
    )
    before = client.get('/api/vnext/targets', headers=headers).json()
    response = client.get('/api/vnext/targets/adb-candidates', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['candidates'][0]['serial'] == 'emulator-5580'
    after = client.get('/api/vnext/targets', headers=headers).json()
    assert after == before
