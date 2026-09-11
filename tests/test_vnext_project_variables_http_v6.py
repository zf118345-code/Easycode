from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext import vnext_runtime
from core.vnext.player_bindings import apply_player_bindings, player_type_fingerprint
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> tuple[str, dict[str, str], dict]:
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project), 'initialize': True, 'project_name': '项目变量纵向测试',
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    workspace = payload['workspace']
    assert payload['project_variables']['variables'] == []
    return (
        payload['inspection']['entry_function_id'],
        {
            'X-Workspace-ID': workspace['workspace_id'],
            'X-Workspace-Generation': str(workspace['generation']),
        },
        payload,
    )


def _command(
    client: TestClient,
    headers: dict[str, str],
    function_id: str,
    revision: str,
    command: dict,
) -> dict:
    response = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={'expected_revision': revision, 'command': command},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _terminal(client: TestClient, execution_id: str) -> dict:
    for _ in range(200):
        response = client.get(f'/api/vnext/runs/{execution_id}')
        assert response.status_code == 200, response.text
        snapshot = response.json()
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('execution did not finish')


def test_project_variable_crud_conflict_references_and_delete_http(tmp_path: Path) -> None:
    client = _client()
    function_id, headers, opened = _open(client, tmp_path / 'variables-http')
    initial_revision = opened['project_variables']['revision']
    created_response = client.post('/api/vnext/project-variables', headers=headers, json={
        'expected_revision': initial_revision,
        'display_name': '执行次数',
        'value_type': 'int64',
        'default_value': {'value_id': 'value_count_default', 'kind': 'int64', 'value': 1},
        'constraints': {'minimum': 0, 'maximum': 10, 'step': 1},
    })
    assert created_response.status_code == 200, created_response.text
    created = created_response.json()
    variable_id = created['selected_variable_id']

    stale = client.post('/api/vnext/project-variables', headers=headers, json={
        'expected_revision': initial_revision,
        'display_name': '过期变量',
        'value_type': 'string',
        'default_value': {'value_id': 'value_stale', 'kind': 'string', 'value': 'x'},
    })
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'project_variable_revision_conflict'

    updated_response = client.patch(
        f'/api/vnext/project-variables/{variable_id}', headers=headers, json={
            'expected_revision': created['revision'],
            'display_name': '本轮执行次数',
            'default_value': {'value_id': 'discarded_value_id', 'kind': 'int64', 'value': 2},
        },
    )
    assert updated_response.status_code == 200, updated_response.text
    updated = updated_response.json()
    assert updated['variables'][0]['default_value']['value_id'] == 'value_count_default'

    program = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    assigned = _command(client, headers, function_id, program['revision'], {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'project_variable',
            'variable_id': variable_id,
            'value_type': 'int64',
        },
        'value': {'value_id': 'value_count_assignment', 'kind': 'int64', 'value': 3},
    })
    statement_id = assigned['selected_statement_id']
    references_response = client.get(
        f'/api/vnext/project-variables/{variable_id}/references', headers=headers,
    )
    assert references_response.status_code == 200, references_response.text
    assert any(
        item.get('statement_id') == statement_id
        and item['kind'] == 'program_assignment'
        for item in references_response.json()['references']
    )

    blocked = client.request(
        'DELETE', f'/api/vnext/project-variables/{variable_id}', headers=headers,
        json={'expected_revision': updated['revision']},
    )
    assert blocked.status_code == 409
    assert blocked.json()['detail']['code'] == 'project_variable_referenced'
    assert any(
        item.get('statement_id') == statement_id
        for item in blocked.json()['detail']['diagnostics']
    )

    missing = client.get('/api/vnext/project-variables/variable_missing/references', headers=headers)
    assert missing.status_code == 404
    assert missing.json()['detail']['code'] == 'project_variable_not_found'


def test_project_variable_defaults_overrides_mutation_and_runs_are_isolated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client()
    function_id, headers, opened = _open(client, tmp_path / 'variables-runtime')
    created_response = client.post('/api/vnext/project-variables', headers=headers, json={
        'expected_revision': opened['project_variables']['revision'],
        'display_name': '计数器',
        'value_type': 'int64',
        'default_value': {'value_id': 'value_counter_default', 'kind': 'int64', 'value': 1},
        'constraints': {'minimum': 0, 'maximum': 10},
    })
    assert created_response.status_code == 200, created_response.text
    variable_id = created_response.json()['selected_variable_id']
    program = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()

    first_log = _command(client, headers, function_id, program['revision'], {
        'kind': 'insert_call',
        'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {LOG_OUTPUT_CONTENT_PARAMETER_ID: {
            'value_id': 'value_counter_before',
            'kind': 'project_variable_ref',
            'variable_id': variable_id,
            'value_type': 'int64',
        }},
    })
    assigned = _command(client, headers, function_id, first_log['revision'], {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'project_variable', 'variable_id': variable_id, 'value_type': 'int64',
        },
        'value': {'value_id': 'value_counter_nine', 'kind': 'int64', 'value': 9},
    })
    second_log = _command(client, headers, function_id, assigned['revision'], {
        'kind': 'insert_call',
        'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {LOG_OUTPUT_CONTENT_PARAMETER_ID: {
            'value_id': 'value_counter_after',
            'kind': 'project_variable_ref',
            'variable_id': variable_id,
            'value_type': 'int64',
        }},
    })

    compiled_response = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is True, compiled['diagnostics']
    assert compiled['ecir']['project_variables'][0]['variable_id'] == variable_id
    assert compiled['ecir']['project_variables'][0]['default_value'] == 1

    form = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'main', 'title': '设置',
            'controls': [{
                'control_id': 'counter', 'type': 'number', 'label': '计数器',
                'source_type': 'int64',
                'type_fingerprint': player_type_fingerprint(
                    'int64', {'minimum': 0, 'maximum': 10},
                ),
                'binding': {'kind': 'project_variable', 'variable_id': variable_id},
            }],
        }],
    }
    player_plan = apply_player_bindings(compiled['ecir'], form, {'counter': 4})
    assert player_plan['project_variable_overrides'] == {variable_id: 4}

    monkeypatch.setattr(vnext_runtime, '_use_worker_process', False)
    monkeypatch.setattr(vnext_runtime, '_persist_event_log', False)

    override_run = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={
            'variable_overrides': {variable_id: {
                'value_id': 'value_player_override', 'kind': 'int64', 'value': 5,
            }},
        },
    )
    assert override_run.status_code == 200, override_run.text
    override_result = _terminal(client, override_run.json()['execution_id'])
    assert override_result['status'] == 'completed', override_result
    override_messages = [
        item['message'] for item in override_result['events'] if item['category'] == 'script'
    ]
    assert override_messages == ['5', '9']
    assert override_result['project_variables'] == {variable_id: 9}

    default_run = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={},
    )
    assert default_run.status_code == 200, default_run.text
    default_result = _terminal(client, default_run.json()['execution_id'])
    default_messages = [
        item['message'] for item in default_result['events'] if item['category'] == 'script'
    ]
    assert default_messages == ['1', '9']
    assert default_result['project_variables'] == {variable_id: 9}

    persisted = client.get('/api/vnext/project-variables', headers=headers).json()
    assert persisted['variables'][0]['default_value']['value'] == 1

    wrong_type = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={
            'variable_overrides': {variable_id: {
                'value_id': 'value_wrong_override', 'kind': 'string', 'value': '5',
            }},
        },
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()['detail']['code'] == 'project_variable_invalid'

    over_limit = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={
            'variable_overrides': {variable_id: {
                'value_id': 'value_limit_override', 'kind': 'int64', 'value': 11,
            }},
        },
    )
    assert over_limit.status_code == 422
    assert over_limit.json()['detail']['code'] == 'project_variable_invalid'
    assert second_log['document']['function']['statements'][-1]['statement_id'] == (
        second_log['selected_statement_id']
    )
