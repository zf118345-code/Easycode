from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router


def _open(tmp_path: Path) -> tuple[TestClient, dict, dict[str, str]]:
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(tmp_path / 'program-lifecycle'),
        'initialize': True,
        'project_name': '函数生命周期',
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    workspace = payload['workspace']
    return client, payload, {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


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


def _create_program(client: TestClient, headers: dict[str, str], name: str) -> dict:
    response = client.post('/api/vnext/programs', headers=headers, json={
        'display_name': name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_program_history_can_restore_without_losing_the_current_version(tmp_path: Path) -> None:
    client, opened, headers = _open(tmp_path)
    function_id = opened['inspection']['entry_function_id']
    initial = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    changed = client.patch(
        f'/api/vnext/programs/{function_id}', headers=headers,
        json={'expected_revision': initial['revision'], 'display_name': '第二版主程序'},
    ).json()

    history_response = client.get(f'/api/vnext/programs/{function_id}/history', headers=headers)
    assert history_response.status_code == 200, history_response.text
    history = history_response.json()
    assert history['current_revision'] == changed['revision']
    assert history['items'][0]['display_name'] == '主程序'

    restored_response = client.post(
        f'/api/vnext/programs/{function_id}/history/restore', headers=headers,
        json={
            'expected_revision': changed['revision'],
            'history_id': history['items'][0]['history_id'],
        },
    )
    assert restored_response.status_code == 200, restored_response.text
    restored = restored_response.json()
    assert restored['document']['function']['display_name'] != '第二版主程序'
    history_after = client.get(f'/api/vnext/programs/{function_id}/history', headers=headers).json()
    assert any(item['display_name'] == '第二版主程序' for item in history_after['items'])


def test_program_signature_endpoint_persists_parameters_and_return_type(tmp_path: Path) -> None:
    client, opened, headers = _open(tmp_path)
    function_id = opened['inspection']['entry_function_id']
    revision = opened['programs'][0]['revision']

    response = client.put(
        f'/api/vnext/programs/{function_id}/signature',
        headers=headers,
        json={
            'expected_revision': revision,
            'parameters': [{
                'display_name': '最大战斗次数',
                'value_type': 'int64',
                'required': False,
                'default_value': {'value_id': 'value-default-max-battles', 'kind': 'int64', 'value': 20},
            }],
            'return_type': 'bool',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['document']['function']['return_type'] == 'bool'
    assert payload['document']['function']['parameters'][0]['display_name'] == '最大战斗次数'
    assert payload['document']['function']['parameters'][0]['default_value']['value'] == 20


def test_damaged_program_enters_explicit_preopen_recovery_instead_of_auto_repair(tmp_path: Path) -> None:
    client, opened, headers = _open(tmp_path)
    project_path = tmp_path / 'program-lifecycle'
    function_id = opened['inspection']['entry_function_id']
    current = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    changed = client.patch(
        f'/api/vnext/programs/{function_id}', headers=headers,
        json={'expected_revision': current['revision'], 'display_name': '产生恢复点'},
    ).json()
    source_path = project_path / 'program' / 'functions' / f'{function_id}.json'
    source_path.write_text('{broken', encoding='utf-8')

    failed_open = client.post('/api/vnext/workspaces/open', json={'path': str(project_path)})
    assert failed_open.status_code == 200, failed_open.text
    inspection = failed_open.json()['inspection']
    assert failed_open.json()['workspace'] is None
    assert inspection['status'] == 'recovery'
    damaged = inspection['damaged_programs'][0]
    assert damaged['function_id'] == function_id
    assert damaged['history']
    assert source_path.read_text(encoding='utf-8') == '{broken'

    recovered = client.post('/api/vnext/workspaces/recover-program', json={
        'path': str(project_path),
        'function_id': function_id,
        'history_id': damaged['history'][0]['history_id'],
        'expected_revision': damaged['current_revision'],
    })
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['inspection']['status'] == 'valid'
    reopened = client.post('/api/vnext/workspaces/open', json={'path': str(project_path)})
    assert reopened.json()['workspace'] is not None
    assert source_path.read_text(encoding='utf-8') != '{broken'
    assert changed['revision'] != reopened.json()['programs'][0]['revision']


def test_extract_statements_endpoint_creates_a_real_project_function(tmp_path: Path) -> None:
    client, opened, headers = _open(tmp_path)
    function_id = opened['inspection']['entry_function_id']
    revision = opened['programs'][0]['revision']
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_extract_http',
            'display_name': '待提取值', 'value_type': 'int64', 'declare': True,
        },
        'value': {'value_id': 'value_extract_http', 'kind': 'int64', 'value': 9},
    })

    response = client.post(
        f'/api/vnext/programs/{function_id}/extract',
        headers=headers,
        json={
            'expected_revision': inserted['revision'],
            'statement_ids': [inserted['selected_statement_id']],
            'display_name': '提取后的流程',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['document']['function']['statements'][0]['kind'] == 'call'
    extracted_id = payload['extracted_program']['function_id']
    loaded = client.get(f'/api/vnext/programs/{extracted_id}', headers=headers)
    assert loaded.status_code == 200
    assert loaded.json()['document']['function']['display_name'] == '提取后的流程'


def test_program_rename_is_revisioned_and_entry_delete_is_blocked(tmp_path: Path) -> None:
    client, opened, headers = _open(tmp_path)
    entry_id = opened['inspection']['entry_function_id']
    entry_revision = opened['programs'][0]['revision']
    created = _create_program(client, headers, '可复用流程')
    function_id = created['document']['function']['function_id']
    document_id = created['document']['document_id']

    renamed_response = client.patch(
        f'/api/vnext/programs/{function_id}',
        headers=headers,
        json={
            'expected_revision': created['revision'],
            'display_name': '领取奖励',
        },
    )
    assert renamed_response.status_code == 200, renamed_response.text
    renamed = renamed_response.json()
    assert renamed['document']['function']['display_name'] == '领取奖励'
    assert renamed['document']['function']['function_id'] == function_id
    assert renamed['document']['document_id'] == document_id
    assert renamed['can_undo'] is True

    stale = client.patch(
        f'/api/vnext/programs/{function_id}',
        headers=headers,
        json={
            'expected_revision': created['revision'],
            'display_name': '过期重命名',
        },
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'program_revision_conflict'

    undone = client.post(
        f'/api/vnext/programs/{function_id}/undo',
        headers=headers,
        json={'expected_revision': renamed['revision']},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()['document']['function']['display_name'] == '可复用流程'

    entry_delete = client.request(
        'DELETE',
        f'/api/vnext/programs/{entry_id}',
        headers=headers,
        json={'expected_revision': entry_revision},
    )
    assert entry_delete.status_code == 409
    assert entry_delete.json()['detail']['code'] == 'program_entry_delete_forbidden'
    assert entry_delete.json()['detail']['diagnostics'] == [{
        'function_id': entry_id,
        'kind': 'entry_function',
    }]


def test_project_function_display_names_are_unique_case_insensitively(
    tmp_path: Path,
) -> None:
    client, _opened, headers = _open(tmp_path)
    first = _create_program(client, headers, '领取奖励')
    duplicate_create = client.post('/api/vnext/programs', headers=headers, json={
        'display_name': '领取奖励',
    })
    assert duplicate_create.status_code == 422
    assert duplicate_create.json()['detail']['code'] == 'program_command_invalid'

    second = _create_program(client, headers, '返回主城')
    duplicate_rename = client.patch(
        f"/api/vnext/programs/{second['document']['function']['function_id']}",
        headers=headers,
        json={
            'expected_revision': second['revision'],
            'display_name': '领取奖励',
        },
    )
    assert duplicate_rename.status_code == 422
    assert duplicate_rename.json()['detail']['code'] == 'program_command_invalid'
    assert client.get(
        f"/api/vnext/programs/{first['document']['function']['function_id']}",
        headers=headers,
    ).status_code == 200


def test_program_delete_reports_exact_references_then_removes_atomically(
    tmp_path: Path,
) -> None:
    client, opened, headers = _open(tmp_path)
    entry_id = opened['inspection']['entry_function_id']
    entry_revision = opened['programs'][0]['revision']
    target = _create_program(client, headers, '被调用函数')
    target_id = target['document']['function']['function_id']

    inserted = _command(client, headers, entry_id, entry_revision, {
        'kind': 'insert_call',
        'function_id': target_id,
    })
    statement_id = inserted['selected_statement_id']

    blocked = client.request(
        'DELETE',
        f'/api/vnext/programs/{target_id}',
        headers=headers,
        json={'expected_revision': target['revision']},
    )
    assert blocked.status_code == 409
    detail = blocked.json()['detail']
    assert detail['code'] == 'program_referenced'
    assert detail['diagnostics'] == [{
        'kind': 'program_call',
        'function_id': entry_id,
        'function_name': '主程序',
        'statement_id': statement_id,
        'field': 'function_id',
    }]

    removed_call = _command(client, headers, entry_id, inserted['revision'], {
        'kind': 'delete_statement',
        'statement_id': statement_id,
    })
    assert removed_call['revision'] != inserted['revision']

    stale_delete = client.request(
        'DELETE',
        f'/api/vnext/programs/{target_id}',
        headers=headers,
        json={'expected_revision': 'sha256:' + ('0' * 64)},
    )
    assert stale_delete.status_code == 409
    assert stale_delete.json()['detail']['code'] == 'program_revision_conflict'

    deleted = client.request(
        'DELETE',
        f'/api/vnext/programs/{target_id}',
        headers=headers,
        json={'expected_revision': target['revision']},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['deleted_function_id'] == target_id
    assert all(
        item['function_id'] != target_id
        for item in deleted.json()['programs']
    )

    missing = client.get(f'/api/vnext/programs/{target_id}', headers=headers)
    assert missing.status_code == 404
    assert missing.json()['detail']['code'] == 'program_not_found'
