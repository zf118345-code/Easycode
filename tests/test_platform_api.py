import json
import os
import subprocess
import sys
from pathlib import Path

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService


def _open_project(client, root):
    root.mkdir()
    for filename, document in new_project_documents('平台测试').items():
        (root / filename).write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    AssetService.ensure_structure(str(root))
    response = client.post('/api/workspaces/open', json={'path': str(root)})
    assert response.status_code == 200, response.text
    workspace = response.json()['workspace']
    return {
        'X-Workspace-Id': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def test_platform_state_message_lease_and_schedule_roundtrip(client, tmp_path):
    headers = _open_project(client, tmp_path / 'project')

    response = client.put('/api/platform/state/progress', params={'namespace': 'account-a'}, json={'page': 3}, headers=headers)
    assert response.status_code == 200
    assert client.get('/api/platform/state/progress', params={'namespace': 'account-a'}, headers=headers).json()['value'] == {'page': 3}

    published = client.post('/api/platform/messages', json={'channel': 'team', 'payload': {'code': '123'}}, headers=headers).json()
    claimed = client.post('/api/platform/messages/claim', json={'channel': 'team', 'consumer': 'player-b'}, headers=headers).json()['messages']
    assert [item['id'] for item in claimed] == [published['id']]
    assert client.post(f"/api/platform/messages/{published['id']}/ack", json={'consumer': 'player-b'}, headers=headers).json()['acked'] is True

    lease = client.post('/api/platform/leases/acquire', json={'resource_key': 'emulator-1', 'owner': 'player-a'}, headers=headers).json()
    renewed = client.post('/api/platform/leases/renew', json={
        'resource_key': 'emulator-1', 'owner': 'player-a', 'token': lease['token'], 'ttl_seconds': 60,
    }, headers=headers)
    assert renewed.json()['renewed'] is True
    assert client.post('/api/platform/leases/release', json={
        'resource_key': 'emulator-1', 'owner': 'player-a', 'token': lease['token'],
    }, headers=headers).json()['released'] is True

    saved = client.post('/api/platform/schedules', json={
        'name': '每分钟任务', 'schedule_type': 'interval', 'schedule_value': '60',
        'payload': {'task_id': 'task-a', 'node_id': 'node-a'}, 'enabled': True,
    }, headers=headers)
    assert saved.status_code == 200, saved.text
    listed = client.get('/api/platform/schedules', headers=headers).json()['schedules']
    assert listed[0]['payload']['node_id'] == 'node-a'
    assert client.delete(f"/api/platform/schedules/{saved.json()['id']}", headers=headers).json()['deleted'] is True


def test_coordinator_requires_token_and_supports_message_lifecycle(client, tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local-app-data'))
    monkeypatch.setenv('EASYCODE_COORDINATOR_TOKEN', 'test-secret')
    assert client.post('/api/platform/coord/messages', json={'channel': 'x', 'payload': 1}).status_code == 401
    headers = {'X-EasyCode-Token': 'test-secret'}
    published = client.post('/api/platform/coord/messages', json={'channel': 'x', 'payload': {'value': 1}}, headers=headers)
    assert published.status_code == 200
    claimed = client.post('/api/platform/coord/messages/claim', json={
        'channel': 'x', 'consumer': 'pc-b', 'lease_seconds': 10,
    }, headers=headers).json()['messages']
    assert claimed[0]['payload'] == {'value': 1}
    acked = client.post(f"/api/platform/coord/messages/{claimed[0]['id']}/ack", json={'consumer': 'pc-b'}, headers=headers)
    assert acked.json()['acked'] is True

    lease = client.post('/api/platform/coord/leases/acquire', json={
        'resource_key': 'account-1', 'owner': 'pc-a', 'ttl_seconds': 30,
    }, headers=headers).json()
    renewed = client.post('/api/platform/coord/leases/renew', json={
        'resource_key': 'account-1', 'owner': 'pc-a', 'token': lease['token'], 'ttl_seconds': 60,
    }, headers=headers)
    assert renewed.json()['renewed'] is True
    released = client.post('/api/platform/coord/leases/release', json={
        'resource_key': 'account-1', 'owner': 'pc-a', 'token': lease['token'],
    }, headers=headers)
    assert released.json()['released'] is True


def test_api_cli_refuses_lan_binding_without_coordinator_token():
    environment = dict(os.environ)
    environment.pop('EASYCODE_COORDINATOR_TOKEN', None)
    result = subprocess.run(
        [sys.executable, 'api.py', '--host', '0.0.0.0', '--port', '8765'],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=environment,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=20,
    )
    assert result.returncode == 2
    assert 'EASYCODE_COORDINATOR_TOKEN' in result.stderr
