from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router


LOG_CONTENT = 'official.log.output.parameter.content'
LOG_CATEGORY = 'official.log.output.parameter.category'


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> tuple[dict[str, str], str]:
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project),
        'initialize': True,
        'project_name': 'Player Designer 闭环',
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    workspace = payload['workspace']
    return ({
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }, payload['inspection']['entry_function_id'])


def test_binding_catalog_and_preview_run_use_current_workspace_program(tmp_path: Path) -> None:
    client = _client()
    headers, entry_function_id = _open(client, tmp_path / 'player-designer')

    program = client.get(
        f'/api/vnext/programs/{entry_function_id}', headers=headers,
    )
    assert program.status_code == 200, program.text
    inserted = client.post(
        f'/api/vnext/programs/{entry_function_id}/commands',
        headers=headers,
        json={
            'expected_revision': program.json()['revision'],
            'command': {
                'kind': 'insert_call',
                'function_id': 'official.log.output',
                'arguments': {
                    LOG_CONTENT: {
                        'value_id': 'value_player_catalog_log',
                        'kind': 'string',
                        'value': 'Player 目录',
                    },
                },
                'location': {'block': 'root'},
            },
        },
    )
    assert inserted.status_code == 200, inserted.text

    contract = client.get('/api/vnext/player/binding-contract')
    assert contract.status_code == 200, contract.text
    assert contract.json()['schema_version'] == 3

    catalog = client.get('/api/vnext/player/binding-sources', headers=headers)
    assert catalog.status_code == 200, catalog.text
    sources = catalog.json()['sources']
    assert any(
        source['binding'] == {
            'kind': 'function_action',
            'function_id': entry_function_id,
        }
        for source in sources
    )
    assert all(source.get('binding') for source in sources)
    statement_sources = [
        source for source in sources
        if source['binding']['kind'] == 'statement_parameter'
    ]
    assert any(
        source['binding']['parameter_id'] == LOG_CONTENT
        for source in statement_sources
    )
    assert not any(
        source['binding']['parameter_id'] == LOG_CATEGORY
        for source in statement_sources
    )

    preview = client.post(
        '/api/vnext/player/preview-run',
        headers={**headers, 'Idempotency-Key': 'preview-empty-main'},
        json={
            'player_values': {},
            'action_control_id': '',
            'target_id': None,
        },
    )
    assert preview.status_code == 200, preview.text
    execution_id = preview.json()['execution_id']

    deadline = time.monotonic() + 3
    snapshot: dict = {}
    while time.monotonic() < deadline:
        status = client.get(f'/api/vnext/runs/{execution_id}')
        assert status.status_code == 200, status.text
        snapshot = status.json()
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            break
        time.sleep(0.01)
    assert snapshot['status'] == 'completed', snapshot


def test_preview_rejects_packaged_profile_identity_instead_of_ignoring_it(tmp_path: Path) -> None:
    client = _client()
    headers, _entry_function_id = _open(client, tmp_path / 'player-preview-profile')
    response = client.post(
        '/api/vnext/player/preview-run',
        headers={**headers, 'Idempotency-Key': 'preview-profile-rejected'},
        json={'profile_id': 'profile_external', 'player_values': {}},
    )
    assert response.status_code == 422, response.text
    assert response.json()['detail']['code'] == 'player_preview_profile_unsupported'
