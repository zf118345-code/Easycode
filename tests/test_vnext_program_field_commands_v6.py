from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router


def _open(tmp_path: Path) -> tuple[TestClient, str, str, dict[str, str]]:
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    opened = client.post('/api/vnext/workspaces/open', json={
        'path': str(tmp_path / 'program-fields'),
        'initialize': True,
        'project_name': '结构字段命令',
    })
    assert opened.status_code == 200, opened.text
    payload = opened.json()
    workspace = payload['workspace']
    return (
        client,
        payload['inspection']['entry_function_id'],
        payload['programs'][0]['revision'],
        {
            'X-Workspace-ID': workspace['workspace_id'],
            'X-Workspace-Generation': str(workspace['generation']),
        },
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


def _statement(payload: dict, statement_id: str) -> dict:
    return next(
        item
        for item in payload['document']['function']['statements']
        if item['statement_id'] == statement_id
    )


def test_whitelisted_structural_fields_round_trip_and_keep_stable_ids(
    tmp_path: Path,
) -> None:
    client, function_id, revision, headers = _open(tmp_path)

    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local',
            'symbol_id': 'symbol_counter',
            'display_name': '计数',
            'value_type': 'int64',
        },
        'value': {'value_id': 'value_counter', 'kind': 'int64', 'value': 1},
    })
    revision = inserted['revision']
    assignment_id = inserted['selected_statement_id']
    updated = _command(client, headers, function_id, revision, {
        'kind': 'update_assignment_value',
        'statement_id': assignment_id,
        'value': {'value_id': 'value_replacement', 'kind': 'int64', 'value': 2},
    })
    revision = updated['revision']
    assert _statement(updated, assignment_id)['value'] == {
        'value_id': 'value_counter', 'kind': 'int64', 'value': 2,
    }
    updated = _command(client, headers, function_id, revision, {
        'kind': 'update_assignment_target',
        'statement_id': assignment_id,
        'target': {
            'kind': 'local',
            'symbol_id': 'symbol_client_replacement',
            'display_name': '新的计数名称',
            'value_type': 'int64',
        },
    })
    revision = updated['revision']
    assert _statement(updated, assignment_id)['target']['symbol_id'] == 'symbol_counter'
    updated = _command(client, headers, function_id, revision, {
        'kind': 'update_assignment_target',
        'statement_id': assignment_id,
        'target': {
            'kind': 'local',
            'symbol_id': 'symbol_client_replacement',
            'display_name': '是否完成',
            'value_type': 'bool',
        },
        'value': {'value_id': 'value_client_replacement', 'kind': 'bool', 'value': False},
    })
    revision = updated['revision']
    assignment = _statement(updated, assignment_id)
    assert assignment['target'] == {
        'kind': 'local', 'symbol_id': 'symbol_counter', 'display_name': '是否完成',
        'value_type': 'bool', 'declare': True,
    }
    assert assignment['value'] == {
        'value_id': 'value_counter', 'kind': 'bool', 'value': False,
    }

    inserted_if = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_if', 'kind': 'bool', 'value': True},
    })
    revision = inserted_if['revision']
    if_id = inserted_if['selected_statement_id']
    branch = _command(client, headers, function_id, revision, {
        'kind': 'add_if_branch',
        'statement_id': if_id,
        'condition': {'value_id': 'value_else_if', 'kind': 'bool', 'value': False},
    })
    revision = branch['revision']
    branch_id = _statement(branch, if_id)['additional_branches'][0]['branch_id']
    updated_if = _command(client, headers, function_id, revision, {
        'kind': 'update_if_condition',
        'statement_id': if_id,
        'condition': {'value_id': 'value_new_if', 'kind': 'bool', 'value': False},
    })
    revision = updated_if['revision']
    assert _statement(updated_if, if_id)['condition']['value_id'] == 'value_if'
    updated_branch = _command(client, headers, function_id, revision, {
        'kind': 'update_if_condition',
        'statement_id': if_id,
        'branch_id': branch_id,
        'condition': {'value_id': 'value_new_else_if', 'kind': 'bool', 'value': True},
    })
    revision = updated_branch['revision']
    assert _statement(updated_branch, if_id)['additional_branches'][0][
        'condition'
    ]['value_id'] == 'value_else_if'
    removed_branch = _command(client, headers, function_id, revision, {
        'kind': 'remove_if_branch',
        'statement_id': if_id,
        'branch_id': branch_id,
    })
    revision = removed_branch['revision']
    assert _statement(removed_branch, if_id)['additional_branches'] == []

    loop = _command(client, headers, function_id, revision, {
        'kind': 'insert_loop',
        'mode': 'repeat',
        'source': {'value_id': 'value_loop_source', 'kind': 'int64', 'value': 2},
    })
    revision = loop['revision']
    loop_id = loop['selected_statement_id']
    updated_loop = _command(client, headers, function_id, revision, {
        'kind': 'update_loop',
        'statement_id': loop_id,
        'mode': 'while',
        'source': {'value_id': 'value_new_loop_source', 'kind': 'bool', 'value': False},
    })
    revision = updated_loop['revision']
    loop_payload = _statement(updated_loop, loop_id)
    assert loop_payload['mode'] == 'while'
    assert loop_payload['source']['value_id'] == 'value_loop_source'

    tried = _command(client, headers, function_id, revision, {
        'kind': 'insert_try',
        'retry_policy': {
            'max_retries': {'value_id': 'value_retry_count', 'kind': 'int64', 'value': 1},
            'interval': {
                'value_id': 'value_retry_interval',
                'kind': 'duration',
                'milliseconds': 5,
            },
            'transient_only': True,
        },
    })
    revision = tried['revision']
    try_id = tried['selected_statement_id']
    caught = _command(client, headers, function_id, revision, {
        'kind': 'add_catch_clause',
        'statement_id': try_id,
        'error_ids': ['target.offline'],
        'error_binding': {
            'symbol_id': 'symbol_error',
            'display_name': '异常',
            'value_type': 'error',
        },
    })
    revision = caught['revision']
    catch_id = _statement(caught, try_id)['catches'][0]['catch_id']
    updated_try = _command(client, headers, function_id, revision, {
        'kind': 'update_try_retry_policy',
        'statement_id': try_id,
        'retry_policy': {
            'max_retries': {
                'value_id': 'value_new_retry_count', 'kind': 'int64', 'value': 3,
            },
            'interval': {
                'value_id': 'value_new_retry_interval',
                'kind': 'duration',
                'milliseconds': 10,
            },
            'transient_only': True,
        },
    })
    revision = updated_try['revision']
    retry = _statement(updated_try, try_id)['retry_policy']
    assert retry['max_retries']['value_id'] == 'value_retry_count'
    assert retry['interval']['value_id'] == 'value_retry_interval'
    updated_catch = _command(client, headers, function_id, revision, {
        'kind': 'update_catch_clause',
        'statement_id': try_id,
        'catch_id': catch_id,
        'error_ids': ['target.offline', 'target.permission_denied'],
        'error_binding': {
            'symbol_id': 'symbol_client_error',
            'display_name': '捕获异常',
            'value_type': 'error',
        },
    })
    revision = updated_catch['revision']
    catch = _statement(updated_catch, try_id)['catches'][0]
    assert catch['error_binding']['symbol_id'] == 'symbol_error'
    assert catch['error_ids'] == ['target.offline', 'target.permission_denied']

    scope = _command(client, headers, function_id, revision, {
        'kind': 'insert_target_scope',
        'target': {
            'value_id': 'value_scope_target',
            'kind': 'target_ref',
            'target_id': 'target_one',
        },
    })
    revision = scope['revision']
    scope_id = scope['selected_statement_id']
    updated_scope = _command(client, headers, function_id, revision, {
        'kind': 'update_target_scope',
        'statement_id': scope_id,
        'target': {
            'value_id': 'value_new_scope_target',
            'kind': 'target_ref',
            'target_id': 'target_two',
        },
    })
    revision = updated_scope['revision']
    assert _statement(updated_scope, scope_id)['target']['value_id'] == 'value_scope_target'

    listened = _command(client, headers, function_id, revision, {
        'kind': 'insert_listen',
        'event_source': {
            'kind': 'message',
            'name': {'value_id': 'value_event_name', 'kind': 'string', 'value': '邀请'},
        },
        'receive_binding': {
            'symbol_id': 'symbol_message',
            'display_name': '消息',
            'value_type': 'received_message',
        },
        'handler_function_id': function_id,
        'condition': {'value_id': 'value_listen_condition', 'kind': 'bool', 'value': True},
    })
    revision = listened['revision']
    listen_id = listened['selected_statement_id']
    updated_listen = _command(client, headers, function_id, revision, {
        'kind': 'update_listen',
        'statement_id': listen_id,
        'event_source': {
            'kind': 'message',
            'name': {'value_id': 'value_new_event_name', 'kind': 'string', 'value': '新邀请'},
        },
        'receive_binding': {
            'symbol_id': 'symbol_client_message',
            'display_name': '收到的消息',
            'value_type': 'received_message',
        },
        'handler_function_id': function_id,
        'condition': {
            'value_id': 'value_new_listen_condition', 'kind': 'bool', 'value': False,
        },
    })
    revision = updated_listen['revision']
    listener = _statement(updated_listen, listen_id)
    assert listener['event_source']['name']['value_id'] == 'value_event_name'
    assert listener['condition']['value_id'] == 'value_listen_condition'
    assert listener['receive_binding']['symbol_id'] == 'symbol_message'

    returned = _command(client, headers, function_id, revision, {
        'kind': 'insert_return',
    })
    revision = returned['revision']
    return_id = returned['selected_statement_id']
    updated_return = _command(client, headers, function_id, revision, {
        'kind': 'update_return_value',
        'statement_id': return_id,
        'value': None,
    })
    assert _statement(updated_return, return_id)['value'] is None

    invalid = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': updated_return['revision'],
            'command': {
                'kind': 'update_target_scope',
                'statement_id': assignment_id,
                'target': {
                    'value_id': 'value_wrong_target',
                    'kind': 'target_ref',
                    'target_id': 'target_wrong',
                },
            },
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()['detail']['code'] == 'program_command_invalid'


def test_update_command_is_strict_and_revision_conflicts_are_not_retried(
    tmp_path: Path,
) -> None:
    client, function_id, revision, headers = _open(tmp_path)
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_condition', 'kind': 'bool', 'value': True},
    })
    command = {
        'kind': 'update_if_condition',
        'statement_id': inserted['selected_statement_id'],
        'condition': {'value_id': 'value_replacement', 'kind': 'bool', 'value': False},
    }
    first = _command(
        client, headers, function_id, inserted['revision'], command,
    )

    stale = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={'expected_revision': inserted['revision'], 'command': command},
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'program_revision_conflict'

    extra = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': first['revision'],
            'command': {**command, 'arbitrary_path': 'function.return_type'},
        },
    )
    assert extra.status_code == 422
    assert any(
        item['loc'][-1] == 'arbitrary_path'
        for item in extra.json()['detail']
    )


def test_non_empty_else_if_branch_cannot_be_removed_implicitly(tmp_path: Path) -> None:
    client, function_id, revision, headers = _open(tmp_path)
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_condition', 'kind': 'bool', 'value': False},
    })
    branch = _command(client, headers, function_id, inserted['revision'], {
        'kind': 'add_if_branch',
        'statement_id': inserted['selected_statement_id'],
        'condition': {'value_id': 'value_else_if', 'kind': 'bool', 'value': True},
    })
    branch_id = _statement(branch, inserted['selected_statement_id'])['additional_branches'][0]['branch_id']
    nested = _command(client, headers, function_id, branch['revision'], {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_nested',
            'display_name': '分支结果', 'value_type': 'string',
        },
        'value': {'value_id': 'value_nested', 'kind': 'string', 'value': '已执行'},
        'location': {
            'parent_statement_id': inserted['selected_statement_id'],
            'block': 'additional_branch',
            'clause_id': branch_id,
        },
    })

    rejected = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': nested['revision'],
            'command': {
                'kind': 'remove_if_branch',
                'statement_id': inserted['selected_statement_id'],
                'branch_id': branch_id,
            },
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'program_command_invalid'
    assert '请先处理分支内语句' in rejected.json()['detail']['message']
