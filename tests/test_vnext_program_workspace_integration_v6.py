from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.runtime import vnext_runtime


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def _headers(workspace: dict) -> dict[str, str]:
    return {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def _command(client: TestClient, headers: dict[str, str], function_id: str, payload: dict) -> dict:
    response = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_format6_program_api_closes_initialize_edit_compile_and_run_slice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client()
    project_path = tmp_path / 'format6-project'
    opened_response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project_path),
        'initialize': True,
        'project_name': '格式6垂直切片',
    })
    assert opened_response.status_code == 200, opened_response.text
    opened = opened_response.json()
    workspace = opened['workspace']
    headers = _headers(workspace)
    function_id = opened['inspection']['entry_function_id']

    assert opened['inspection']['format_version'] == 6
    assert opened['programs'][0]['function_id'] == function_id
    assert not (project_path / 'src').exists()
    assert list(project_path.rglob('*.easy')) == []
    assert (project_path / 'program' / 'functions' / f'{function_id}.json').is_file()
    retired = client.post('/api/vnext/analyze', headers=headers, json={
        'document_id': 'src/main.easy',
        'source': '',
    })
    assert retired.status_code == 410
    assert retired.json()['detail']['code'] == 'source_api_retired'

    catalog = client.get('/api/vnext/functions').json()['functions']
    catalog_names = [item['qualified_name'] for item in catalog]
    assert {'日志.输出', '等待.持续'} <= set(catalog_names)
    assert len(catalog_names) == len(set(catalog_names))
    image_wait = next(item for item in catalog if item['function_id'] == 'official.image.wait_visible')
    assert image_wait['schema_version'] == 4
    assert image_wait['statement_summary'] == {
        'schema_version': 1,
        'parts': [
            {'kind': 'text', 'text': '等待图像'},
            {
                'kind': 'parameter',
                'parameter_id': 'official.image.wait_visible.parameter.image',
                'parameter_name': 'image',
                'role': 'object',
                'presentation': 'auto',
            },
            {'kind': 'text', 'text': '出现'},
        ],
    }

    created_response = client.post(
        '/api/vnext/programs',
        headers=headers,
        json={'display_name': '可复用流程'},
    )
    assert created_response.status_code == 200, created_response.text
    created = created_response.json()
    listed = client.get('/api/vnext/programs', headers=headers)
    assert listed.status_code == 200, listed.text
    assert {item['function_id'] for item in listed.json()['programs']} == {
        function_id,
        created['document']['function']['function_id'],
    }

    loaded = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    inserted_log = _command(client, headers, function_id, {
        'expected_revision': loaded['revision'],
        'command': {'kind': 'insert_call', 'function_id': 'official.log.output'},
    })
    log_statement = inserted_log['document']['function']['statements'][0]
    configured_log = _command(client, headers, function_id, {
        'expected_revision': inserted_log['revision'],
        'command': {
            'kind': 'update_argument',
            'statement_id': log_statement['statement_id'],
            'parameter_id': 'official.log.output.parameter.content',
            'value': {'value_id': 'client_value', 'kind': 'string', 'value': 'format 6 works'},
        },
    })
    configured_level = _command(client, headers, function_id, {
        'expected_revision': configured_log['revision'],
        'command': {
            'kind': 'update_argument',
            'statement_id': log_statement['statement_id'],
            'parameter_id': 'official.log.output.parameter.level',
            'value': {'value_id': 'client_value', 'kind': 'string', 'value': 'warning'},
        },
    })
    configured_category = _command(client, headers, function_id, {
        'expected_revision': configured_level['revision'],
        'command': {
            'kind': 'update_argument',
            'statement_id': log_statement['statement_id'],
            'parameter_id': 'official.log.output.parameter.category',
            'value': {'value_id': 'client_value', 'kind': 'string', 'value': 'demo'},
        },
    })
    inserted_wait = _command(client, headers, function_id, {
        'expected_revision': configured_category['revision'],
        'command': {'kind': 'insert_call', 'function_id': 'official.wait.duration'},
    })
    wait_statement = inserted_wait['document']['function']['statements'][1]
    _command(client, headers, function_id, {
        'expected_revision': inserted_wait['revision'],
        'command': {
            'kind': 'update_argument',
            'statement_id': wait_statement['statement_id'],
            'parameter_id': 'official.wait.duration.parameter.duration',
            'value': {'value_id': 'client_value', 'kind': 'duration', 'milliseconds': 5},
        },
    })

    compiled_response = client.post(
        f'/api/vnext/programs/{function_id}/compile',
        headers=headers,
        json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is True
    instructions = compiled['ecir']['functions'][0]['instructions']
    assert set(instructions[0]['arguments']) == {
        'official.log.output.parameter.content',
        'official.log.output.parameter.level',
        'official.log.output.parameter.category',
    }
    assert set(instructions[1]['arguments']) == {'official.wait.duration.parameter.duration'}
    assert json.loads((project_path / 'project.json').read_text(encoding='utf-8'))['format_version'] == 6

    monkeypatch.setattr(vnext_runtime, '_use_worker_process', False)
    monkeypatch.setattr(vnext_runtime, '_persist_event_log', False)
    run_response = client.post(
        f'/api/vnext/programs/{function_id}/run',
        headers=headers,
        json={'debug': {}},
    )
    assert run_response.status_code == 200, run_response.text
    execution_id = run_response.json()['execution_id']
    terminal = None
    for _ in range(100):
        terminal_response = client.get(f'/api/vnext/runs/{execution_id}')
        assert terminal_response.status_code == 200, terminal_response.text
        terminal = terminal_response.json()
        if terminal['status'] in {'completed', 'failed', 'cancelled'}:
            break
        time.sleep(0.01)
    assert terminal is not None
    assert terminal['status'] == 'completed', terminal
    matching_event = next(item for item in terminal['events'] if item['message'] == 'format 6 works')
    assert matching_event['level'] == 'warning'
    assert matching_event['category'] == 'demo'

    # Create one newer revision before submitting the deliberately stale command.
    current = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    newer = _command(client, headers, function_id, {
        'expected_revision': current['revision'],
        'command': {'kind': 'insert_call', 'function_id': 'official.wait.duration'},
    })
    stale = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': current['revision'],
            'command': {'kind': 'delete_statement', 'statement_id': log_statement['statement_id']},
        },
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'program_revision_conflict'
    after_conflict = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    assert after_conflict['revision'] == newer['revision']


def test_format5_project_is_explicitly_unsupported(tmp_path: Path) -> None:
    project = tmp_path / 'format5'
    project.mkdir()
    (project / 'project.json').write_text(json.dumps({
        'format_version': 5,
        'project_id': 'old',
        'name': 'old',
        'entry_source': 'src/main.easy',
    }), encoding='utf-8')

    response = _client().post('/api/vnext/workspaces/inspect', json={'path': str(project)})

    assert response.status_code == 200
    assert response.json()['status'] == 'unsupported'
    assert response.json()['valid'] is False
