from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext import vnext_runtime
from core.vnext.player_bundle import vnext_player_bundle_manager


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def test_player_runtime_preflight_and_profiles_use_strict_api_contract(monkeypatch):
    monkeypatch.setattr(vnext_player_bundle_manager, 'available', lambda: True)
    monkeypatch.setattr(vnext_player_bundle_manager, 'preflight', lambda target_id='', profile_id='', profile_revision=None: {
        'ready': True, 'target_id': target_id or None, 'profile_id': profile_id or None, 'checked_at': '2026-08-29T00:00:00+00:00',
        'checks': [{'id': 'bundle', 'status': 'pass', 'message': 'ok'}],
    })
    monkeypatch.setattr(vnext_player_bundle_manager, 'profiles', lambda: {'profiles': []})
    monkeypatch.setattr(vnext_player_bundle_manager, 'save_profile', lambda profile_id, name, target_id, values, expected_revision=None: {
        'saved': True,
        'profile': {'profile_id': profile_id or 'profile_new', 'name': name, 'target_id': target_id, 'values': values, 'revision': (expected_revision or 0) + 1},
    })
    monkeypatch.setattr(vnext_player_bundle_manager, 'delete_profile', lambda profile_id: {
        'deleted': True, 'profile_id': profile_id,
    })
    client = _client()

    checked = client.get('/api/vnext/player/runtime/preflight?target_id=target_1')
    assert checked.status_code == 200
    assert checked.json()['target_id'] == 'target_1'
    checked_profile = client.get('/api/vnext/player/runtime/preflight?target_id=target_1&profile_id=profile_1&profile_revision=2')
    assert checked_profile.status_code == 200
    assert checked_profile.json()['profile_id'] == 'profile_1'
    assert client.get('/api/vnext/player/runtime/profiles').json() == {'profiles': []}
    saved = client.put('/api/vnext/player/runtime/profiles', json={
        'name': '常用方案', 'target_id': None, 'values': {'count': 2},
    })
    assert saved.status_code == 200
    assert saved.json()['profile']['profile_id'] == 'profile_new'
    rejected = client.put('/api/vnext/player/runtime/profiles', json={
        'name': '错误方案', 'values': {}, 'unexpected': True,
    })
    assert rejected.status_code == 422
    assert client.delete('/api/vnext/player/runtime/profiles/profile_new').json()['deleted'] is True


def test_player_dangerous_operation_confirmation_is_server_resolved_and_forwarded(monkeypatch):
    monkeypatch.setattr(vnext_player_bundle_manager, 'available', lambda: True)
    captured: dict[str, dict] = {}

    def requirements(payload):
        captured['requirements'] = payload
        return {
            'required': True,
            'operations': [{
                'confirmation_id': 'danger_1',
                'statement_id': 'stmt_delete',
                'function_id': 'project.main',
                'function_name': '主程序',
                'operation': 'directory.delete_tree',
                'path': 'D:/allowed/output',
                'message': '删除后无法恢复',
            }],
        }

    def start(payload):
        captured['start'] = payload
        return {'execution_id': 'execution_1', 'state': 'running'}

    monkeypatch.setattr(vnext_player_bundle_manager, 'dangerous_operation_requirements', requirements)
    monkeypatch.setattr(vnext_player_bundle_manager, 'start', start)
    client = _client()

    resolved = client.post('/api/vnext/player/runtime/dangerous-operations', json={
        'profile_id': 'profile_1',
        'profile_revision': 1,
        'dangerous_confirmations': [{'confirmation_id': 'client_forged', 'confirmed': True}],
    })
    assert resolved.status_code == 200
    assert resolved.json()['operations'][0]['confirmation_id'] == 'danger_1'
    # The resolution endpoint never trusts client-provided confirmation state.
    assert captured['requirements']['dangerous_confirmations'] == []

    started = client.post(
        '/api/vnext/player/runtime/run',
        headers={'Idempotency-Key': 'dangerous-run-1'},
        json={
            'profile_id': 'profile_1',
            'profile_revision': 1,
            'dangerous_confirmations': [{'confirmation_id': 'danger_1', 'confirmed': True}],
        },
    )
    assert started.status_code == 200
    assert captured['start']['dangerous_confirmations'] == [
        {'confirmation_id': 'danger_1', 'confirmed': True},
    ]

    rejected = client.post('/api/vnext/player/runtime/run', json={
        'dangerous_confirmations': [{'confirmation_id': 'danger_1', 'confirmed': False}],
    })
    assert rejected.status_code == 422


def test_failure_frame_download_uses_runtime_guard(monkeypatch, tmp_path: Path):
    image = tmp_path / 'failure.png'
    image.write_bytes(b'\x89PNG\r\n\x1a\n')
    monkeypatch.setattr(vnext_runtime, 'failure_frame_path', lambda execution_id: str(image))

    response = _client().get('/api/vnext/runs/execution_test/failure-frame')

    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'
    assert response.content.startswith(b'\x89PNG')


def test_player_capture_routes_keep_full_destination_and_strict_results(monkeypatch):
    monkeypatch.setattr(vnext_player_bundle_manager, 'available', lambda: True)
    destination = {
        'product_id': 'project_1',
        'release_id': 'release_1',
        'profile_id': 'profile_1',
        'control_id': 'point',
        'action_id': 'pick-point',
        'profile_revision': 3,
        'target_id': 'target_1',
    }
    monkeypatch.setattr(
        vnext_player_bundle_manager,
        'terminal_action_availability',
        lambda profile_id, revision, target_id: {
            'platform': 'windows',
            'profile_id': profile_id,
            'profile_revision': revision,
            'blocked_reason': '',
            'actions': [{
                'control_id': 'point', 'action_id': 'pick-point',
                'platform': 'windows', 'capability': 'player.capture.point',
                'enabled': True, 'disabled_reason': '', 'destination': destination,
            }],
        },
    )
    monkeypatch.setattr(
        vnext_player_bundle_manager,
        'start_control_capture',
        lambda value, origin='': {
            'ok': True, 'capture_id': 'player_capture_1', 'state': 'capturing',
            'destination': value, 'origin': origin,
        },
    )
    monkeypatch.setattr(
        vnext_player_bundle_manager,
        'confirm_control_capture',
        lambda capture_id, value, result: {
            'ok': True, 'capture_id': capture_id, 'destination': value,
            'value': {'x': result['point'][0], 'y': result['point'][1]},
        },
    )
    monkeypatch.setattr(
        vnext_player_bundle_manager,
        'cancel_control_capture',
        lambda capture_id, value: {'ok': True, 'cancelled': True, 'capture_id': capture_id},
    )
    client = _client()

    available = client.get(
        '/api/vnext/player/runtime/actions?profile_id=profile_1&profile_revision=3&target_id=target_1'
    )
    assert available.status_code == 200
    assert available.json()['actions'][0]['destination'] == destination
    started = client.post('/api/vnext/player/runtime/capture/start', json={
        'destination': destination, 'origin': 'http://127.0.0.1:4173',
    })
    assert started.status_code == 200
    window_destination = {
        **destination,
        'control_id': 'window_binding',
        'action_id': 'capture-window',
    }
    window_started = client.post('/api/vnext/player/runtime/capture/start', json={
        'destination': window_destination, 'origin': 'http://127.0.0.1:4173',
    })
    assert window_started.status_code == 200
    assert window_started.json()['destination']['action_id'] == 'capture-window'
    confirmed = client.post('/api/vnext/player/runtime/capture/confirm', json={
        'capture_id': 'player_capture_1',
        'destination': destination,
        'result': {'kind': 'field_confirm', 'point': [8, 9]},
    })
    assert confirmed.status_code == 200
    assert confirmed.json()['value'] == {'x': 8, 'y': 9}
    file_destination = {
        **destination,
        'control_id': 'input_file',
        'action_id': 'choose-file-read',
        'target_id': '',
    }
    no_target_file = client.post('/api/vnext/player/runtime/capture/start', json={
        'destination': file_destination,
    })
    assert no_target_file.status_code == 200
    assert no_target_file.json()['destination']['target_id'] == ''
    rejected = client.post('/api/vnext/player/runtime/capture/start', json={
        'destination': {**destination, 'profile_revision': 0},
    })
    assert rejected.status_code == 422
