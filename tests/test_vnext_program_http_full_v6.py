from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext import vnext_runtime
from core.vnext.program_contracts import (
    LOG_OUTPUT_CATEGORY_PARAMETER_ID,
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
    LOG_OUTPUT_LEVEL_PARAMETER_ID,
    WAIT_DURATION_FUNCTION_ID,
    WAIT_DURATION_PARAMETER_ID,
)
from core.vnext.program_repository import ProgramDocumentRepository
from core.vnext.program_types import ProgramDocument


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> tuple[str, str, dict[str, str]]:
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project), 'initialize': True, 'project_name': '完整程序模型',
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    workspace = payload['workspace']
    return (
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


def _root_statement(payload: dict, statement_id: str) -> dict:
    return next(
        item for item in payload['document']['function']['statements']
        if item['statement_id'] == statement_id
    )


def _all_opcodes(instructions: list[dict]) -> list[str]:
    result: list[str] = []
    for instruction in instructions:
        result.append(str(instruction['opcode']))
        arguments = instruction.get('arguments') or {}
        for key in ('then', 'otherwise', 'body', 'finally'):
            result.extend(_all_opcodes(arguments.get(key) or []))
        for branch in arguments.get('additional_branches') or []:
            result.extend(_all_opcodes(branch.get('body') or []))
        for clause in arguments.get('catches') or []:
            result.extend(_all_opcodes(clause.get('body') or []))
    return result


def test_program_catalog_counts_nested_statements(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-nested-count')
    inserted_if = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_if_condition', 'kind': 'bool', 'value': True},
    })
    if_id = inserted_if['selected_statement_id']
    _command(client, headers, function_id, inserted_if['revision'], {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_nested',
            'display_name': '嵌套值', 'value_type': 'string',
        },
        'value': {'value_id': 'value_nested', 'kind': 'string', 'value': '测试'},
        'location': {'parent_statement_id': if_id, 'block': 'then'},
    })

    catalog = client.get('/api/vnext/programs', headers=headers)
    assert catalog.status_code == 200, catalog.text
    summary = next(item for item in catalog.json()['programs'] if item['function_id'] == function_id)
    assert summary['statement_count'] == 2


def test_atomic_command_batch_and_structural_clipboard_round_trip_over_http(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-batch-edit')
    first = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_wait_first', 'kind': 'duration', 'milliseconds': 1000,
        }},
    })
    second = _command(client, headers, function_id, first['revision'], {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_wait_second', 'kind': 'duration', 'milliseconds': 2000,
        }},
    })
    first_id = first['selected_statement_id']
    second_id = second['selected_statement_id']

    batch = client.post(
        f'/api/vnext/programs/{function_id}/commands/batch', headers=headers,
        json={'expected_revision': second['revision'], 'commands': [
            {
                'kind': 'update_argument', 'statement_id': first_id,
                'parameter_id': WAIT_DURATION_PARAMETER_ID,
                'value': {'value_id': 'value_wait_first', 'kind': 'duration', 'milliseconds': 3000},
            },
            {
                'kind': 'update_argument', 'statement_id': second_id,
                'parameter_id': WAIT_DURATION_PARAMETER_ID,
                'value': {'value_id': 'value_wait_second', 'kind': 'duration', 'milliseconds': 3000},
            },
        ]},
    )
    assert batch.status_code == 200, batch.text
    durations = [item['arguments'][WAIT_DURATION_PARAMETER_ID]['milliseconds']
                 for item in batch.json()['document']['function']['statements']]
    assert durations == [3000, 3000]

    undone = client.post(
        f'/api/vnext/programs/{function_id}/undo', headers=headers,
        json={'expected_revision': batch.json()['revision']},
    )
    assert undone.status_code == 200, undone.text
    durations = [item['arguments'][WAIT_DURATION_PARAMETER_ID]['milliseconds']
                 for item in undone.json()['document']['function']['statements']]
    assert durations == [1000, 2000]

    snapshot = undone.json()['document']['function']['statements']
    pasted = _command(client, headers, function_id, undone.json()['revision'], {
        'kind': 'paste_statements', 'statements': snapshot,
        'location': {'parent_statement_id': None, 'block': 'root', 'before_statement_id': None},
    })
    statement_ids = [item['statement_id'] for item in pasted['document']['function']['statements']]
    assert statement_ids[:2] == [first_id, second_id]
    assert len(statement_ids) == 4
    assert set(statement_ids[:2]).isdisjoint(statement_ids[2:])


def test_structural_clipboard_pastes_across_project_functions_atomically(tmp_path: Path) -> None:
    client = _client()
    source_id, source_revision, headers = _open(client, tmp_path / 'program-cross-function-copy')
    source = _command(client, headers, source_id, source_revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_cross_function_wait', 'kind': 'duration', 'milliseconds': 1250,
        }},
    })
    source_statements = source['document']['function']['statements']
    created = client.post(
        '/api/vnext/programs', headers=headers, json={'display_name': '跨函数目标'},
    )
    assert created.status_code == 200, created.text
    destination = created.json()
    destination_id = destination['document']['function']['function_id']

    pasted = _command(client, headers, destination_id, destination['revision'], {
        'kind': 'paste_statements',
        'statements': source_statements,
        'location': {'parent_statement_id': None, 'block': 'root', 'before_statement_id': None},
    })

    copied = pasted['document']['function']['statements']
    assert len(copied) == 1
    assert copied[0]['statement_id'] != source_statements[0]['statement_id']
    assert copied[0]['arguments'][WAIT_DURATION_PARAMETER_ID]['value_id'] != (
        source_statements[0]['arguments'][WAIT_DURATION_PARAMETER_ID]['value_id']
    )
    assert copied[0]['arguments'][WAIT_DURATION_PARAMETER_ID]['milliseconds'] == 1250

    source_after = client.get(f'/api/vnext/programs/{source_id}', headers=headers)
    assert source_after.status_code == 200, source_after.text
    assert source_after.json()['revision'] == source['revision']
    assert source_after.json()['document']['function']['statements'] == source_statements

    undone = client.post(
        f'/api/vnext/programs/{destination_id}/undo', headers=headers,
        json={'expected_revision': pasted['revision']},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()['document']['function']['statements'] == []


def test_missing_call_arguments_are_repaired_atomically_over_http(tmp_path: Path) -> None:
    client = _client()
    project = tmp_path / 'program-repair-arguments'
    function_id, revision, headers = _open(client, project)
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call',
        'function_id': 'official.input.click',
        'arguments': {
            'official.input.click.parameter.position': {
                'value_id': 'value_click_position', 'kind': 'point', 'x': 12, 'y': 34,
            },
        },
    })
    repository = ProgramDocumentRepository(project)
    current = repository.load(function_id)
    raw = current.document.model_dump(mode='json')
    arguments = raw['function']['statements'][0]['arguments']
    position_id = arguments['official.input.click.parameter.position']['value_id']
    for parameter_id in (
        'official.input.click.parameter.button',
        'official.input.click.parameter.count',
        'official.input.click.parameter.hold',
        'official.input.click.parameter.interval',
    ):
        del arguments[parameter_id]
    incomplete = repository.save(
        ProgramDocument.model_validate(raw),
        expected_revision=current.revision,
    )

    repaired = _command(client, headers, function_id, incomplete.revision, {
        'kind': 'repair_missing_arguments',
        'statement_id': inserted['selected_statement_id'],
    })
    values = repaired['document']['function']['statements'][0]['arguments']
    assert values['official.input.click.parameter.position']['value_id'] == position_id
    assert values['official.input.click.parameter.button']['value'] == 'primary'
    assert values['official.input.click.parameter.count']['value'] == 1
    assert values['official.input.click.parameter.hold']['milliseconds'] == 0
    assert values['official.input.click.parameter.interval']['milliseconds'] == 80

    undone = client.post(
        f'/api/vnext/programs/{function_id}/undo', headers=headers,
        json={'expected_revision': repaired['revision']},
    )
    assert undone.status_code == 200, undone.text
    undone_values = undone.json()['document']['function']['statements'][0]['arguments']
    assert set(undone_values) == {'official.input.click.parameter.position'}


def test_structural_clipboard_rejects_unknown_function_without_mutating_program(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-invalid-clipboard')
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_wait', 'kind': 'duration', 'milliseconds': 1000,
        }},
    })
    snapshot = inserted['document']['function']['statements'][0]
    snapshot['function_id'] = 'missing.extension.function'

    rejected = client.post(
        f'/api/vnext/programs/{function_id}/commands', headers=headers,
        json={
            'expected_revision': inserted['revision'],
            'command': {
                'kind': 'paste_statements', 'statements': [snapshot],
                'location': {
                    'parent_statement_id': None,
                    'block': 'root',
                    'before_statement_id': None,
                },
            },
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'program_command_invalid'

    current = client.get(f'/api/vnext/programs/{function_id}', headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()['revision'] == inserted['revision']
    assert len(current.json()['document']['function']['statements']) == 1


def test_command_batch_rolls_back_every_edit_when_one_command_is_invalid(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-batch-rollback')
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_wait', 'kind': 'duration', 'milliseconds': 1000,
        }},
    })
    statement_id = inserted['selected_statement_id']
    rejected = client.post(
        f'/api/vnext/programs/{function_id}/commands/batch', headers=headers,
        json={'expected_revision': inserted['revision'], 'commands': [
            {
                'kind': 'update_argument', 'statement_id': statement_id,
                'parameter_id': WAIT_DURATION_PARAMETER_ID,
                'value': {'value_id': 'value_wait', 'kind': 'duration', 'milliseconds': 9000},
            },
            {
                'kind': 'update_argument', 'statement_id': statement_id,
                'parameter_id': 'missing_parameter',
                'value': {'value_id': 'value_missing', 'kind': 'string', 'value': '无效'},
            },
        ]},
    )
    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'program_command_invalid'

    current = client.get(f'/api/vnext/programs/{function_id}', headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()['revision'] == inserted['revision']
    value = current.json()['document']['function']['statements'][0]['arguments'][WAIT_DURATION_PARAMETER_ID]
    assert value['milliseconds'] == 1000


def test_complete_program_commands_round_trip_over_http(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-http')
    variables = client.get('/api/vnext/project-variables', headers=headers)
    assert variables.status_code == 200, variables.text
    created_variable = client.post('/api/vnext/project-variables', headers=headers, json={
        'expected_revision': variables.json()['revision'],
        'display_name': '分支名称',
        'value_type': 'string',
        'default_value': {
            'value_id': 'value_branch_name_default', 'kind': 'string', 'value': '',
        },
    })
    assert created_variable.status_code == 200, created_variable.text
    branch_variable_id = created_variable.json()['selected_variable_id']

    assigned = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_numbers',
            'display_name': '数字列表', 'value_type': 'list<int64>',
        },
        'value': {
            'value_id': 'value_numbers', 'kind': 'list', 'item_type': 'int64',
            'items': [
                {'value_id': 'value_number_one', 'kind': 'int64', 'value': 1},
                {'value_id': 'value_number_two', 'kind': 'int64', 'value': 2},
            ],
        },
    })
    revision = assigned['revision']
    assert assigned['created_ids']

    inserted_if = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_if_condition', 'kind': 'bool', 'value': True},
    })
    revision = inserted_if['revision']
    if_id = inserted_if['selected_statement_id']

    branched = _command(client, headers, function_id, revision, {
        'kind': 'add_if_branch', 'statement_id': if_id,
        'condition': {'value_id': 'value_branch_condition', 'kind': 'bool', 'value': False},
    })
    revision = branched['revision']
    branch_id = _root_statement(branched, if_id)['additional_branches'][0]['branch_id']
    assert branch_id in branched['created_ids']

    then_marker = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_then_marker',
            'display_name': '分支标记', 'value_type': 'string',
        },
        'value': {'value_id': 'value_then_marker', 'kind': 'string', 'value': '开始'},
        'location': {'parent_statement_id': if_id, 'block': 'then'},
    })
    revision = then_marker['revision']

    loop = _command(client, headers, function_id, revision, {
        'kind': 'insert_loop', 'mode': 'for_each',
        'source': {
            'value_id': 'value_numbers_reference', 'kind': 'symbol_ref',
            'symbol_id': 'symbol_numbers', 'value_type': 'list<int64>',
        },
        'item_binding': {
            'symbol_id': 'symbol_loop_item', 'display_name': '当前数字',
            'value_type': 'int64',
        },
        'location': {
            'parent_statement_id': if_id, 'block': 'then',
            'before_statement_id': then_marker['selected_statement_id'],
        },
    })
    revision = loop['revision']
    loop_id = loop['selected_statement_id']

    loop_log = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {
            LOG_OUTPUT_CONTENT_PARAMETER_ID: {
                'value_id': 'value_loop_item_reference', 'kind': 'symbol_ref',
                'symbol_id': 'symbol_loop_item', 'value_type': 'int64',
            },
            LOG_OUTPUT_LEVEL_PARAMETER_ID: {
                'value_id': 'value_loop_log_level', 'kind': 'string', 'value': 'info',
            },
            LOG_OUTPUT_CATEGORY_PARAMETER_ID: {
                'value_id': 'value_loop_log_category', 'kind': 'string', 'value': 'loop',
            },
        },
        'location': {'parent_statement_id': loop_id, 'block': 'body'},
    })
    revision = loop_log['revision']
    labelled_loop_log = _command(client, headers, function_id, revision, {
        'kind': 'set_step_label',
        'statement_id': loop_log['selected_statement_id'],
        'label': '  记录当前数字  ',
    })
    revision = labelled_loop_log['revision']

    branch_assignment = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'project_variable', 'variable_id': branch_variable_id,
            'value_type': 'string',
        },
        'value': {'value_id': 'value_branch_text', 'kind': 'string', 'value': '备用分支'},
        'location': {
            'parent_statement_id': if_id, 'block': 'additional_branch',
            'clause_id': branch_id,
        },
    })
    revision = branch_assignment['revision']
    returned = _command(client, headers, function_id, revision, {
        'kind': 'insert_return',
        'location': {'parent_statement_id': if_id, 'block': 'otherwise'},
    })
    revision = returned['revision']

    tried = _command(client, headers, function_id, revision, {
        'kind': 'insert_try',
        'retry_policy': {
            'max_retries': {'value_id': 'value_retry_count', 'kind': 'int64', 'value': 2},
            'interval': {
                'value_id': 'value_retry_interval', 'kind': 'duration', 'milliseconds': 5,
            },
            'transient_only': True,
        },
    })
    revision = tried['revision']
    try_id = tried['selected_statement_id']
    caught = _command(client, headers, function_id, revision, {
        'kind': 'add_catch_clause', 'statement_id': try_id,
        'error_ids': ['target.offline'],
        'error_binding': {
            'symbol_id': 'symbol_caught_error', 'display_name': '异常', 'value_type': 'error',
        },
    })
    revision = caught['revision']
    catch_id = _root_statement(caught, try_id)['catches'][0]['catch_id']
    assert catch_id in caught['created_ids']

    try_wait = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_try_wait', 'kind': 'duration', 'milliseconds': 1,
        }},
        'location': {'parent_statement_id': try_id, 'block': 'body'},
    })
    revision = try_wait['revision']
    wait_statement_id = try_wait['selected_statement_id']
    wait_value_id = _root_statement(try_wait, try_id)['body'][0]['arguments'][
        WAIT_DURATION_PARAMETER_ID
    ]['value_id']
    updated_wait = _command(client, headers, function_id, revision, {
        'kind': 'update_argument', 'statement_id': wait_statement_id,
        'parameter_id': WAIT_DURATION_PARAMETER_ID,
        'value': {'value_id': 'value_client_replacement', 'kind': 'duration', 'milliseconds': 2},
    })
    revision = updated_wait['revision']
    assert _root_statement(updated_wait, try_id)['body'][0]['arguments'][
        WAIT_DURATION_PARAMETER_ID
    ]['value_id'] == wait_value_id

    catch_assignment = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_catch_text',
            'display_name': '捕获结果', 'value_type': 'string',
        },
        'value': {'value_id': 'value_catch_text', 'kind': 'string', 'value': '已捕获'},
        'location': {
            'parent_statement_id': try_id, 'block': 'catch', 'clause_id': catch_id,
        },
    })
    revision = catch_assignment['revision']
    finally_assignment = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_finally_text',
            'display_name': '最终结果', 'value_type': 'string',
        },
        'value': {'value_id': 'value_finally_text', 'kind': 'string', 'value': '已结束'},
        'location': {'parent_statement_id': try_id, 'block': 'finally'},
    })
    revision = finally_assignment['revision']

    target_scope = _command(client, headers, function_id, revision, {
        'kind': 'insert_target_scope',
        'target': {'value_id': 'value_target_main', 'kind': 'target_ref', 'target_id': 'target_main'},
    })
    revision = target_scope['revision']
    target_scope_id = target_scope['selected_statement_id']
    target_wait = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': WAIT_DURATION_FUNCTION_ID,
        'arguments': {WAIT_DURATION_PARAMETER_ID: {
            'value_id': 'value_target_wait', 'kind': 'duration', 'milliseconds': 1,
        }},
        'location': {'parent_statement_id': target_scope_id, 'block': 'body'},
    })
    revision = target_wait['revision']

    listened = _command(client, headers, function_id, revision, {
        'kind': 'insert_listen',
        'event_source': {
            'kind': 'message',
            'name': {'value_id': 'value_event_name', 'kind': 'string', 'value': '组队邀请'},
        },
        'receive_binding': {
            'symbol_id': 'symbol_received_message', 'display_name': '收到的消息',
            'value_type': 'received_message',
        },
        'handler_function_id': function_id,
        'condition': {'value_id': 'value_event_condition', 'kind': 'bool', 'value': True},
        'handler_arguments': {},
    })
    revision = listened['revision']

    time_call = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': 'official.time.now',
    })
    revision = time_call['revision']
    time_statement_id = time_call['selected_statement_id']
    bound = _command(client, headers, function_id, revision, {
        'kind': 'set_result_binding', 'statement_id': time_statement_id,
        'binding': {
            'symbol_id': 'symbol_current_time', 'display_name': '当前时间',
            'value_type': 'datetime', 'declare': True,
        },
    })
    revision_before_label = bound['revision']
    labelled = _command(client, headers, function_id, revision_before_label, {
        'kind': 'set_step_label', 'statement_id': time_statement_id, 'label': '读取当前时间',
    })

    stale = client.post(
        f'/api/vnext/programs/{function_id}/commands', headers=headers,
        json={
            'expected_revision': revision_before_label,
            'command': {
                'kind': 'set_step_label', 'statement_id': time_statement_id, 'label': '过期命令',
            },
        },
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'program_revision_conflict'

    invalid_location = client.post(
        f'/api/vnext/programs/{function_id}/commands', headers=headers,
        json={
            'expected_revision': labelled['revision'],
            'command': {
                'kind': 'insert_return',
                'location': {'parent_statement_id': if_id, 'block': 'additional_branch'},
            },
        },
    )
    assert invalid_location.status_code == 422
    assert invalid_location.json()['detail']['code'] == 'program_command_invalid'

    undone_response = client.post(
        f'/api/vnext/programs/{function_id}/undo', headers=headers,
        json={'expected_revision': labelled['revision']},
    )
    assert undone_response.status_code == 200, undone_response.text
    undone = undone_response.json()
    assert _root_statement(undone, time_statement_id)['step_label'] is None
    redone_response = client.post(
        f'/api/vnext/programs/{function_id}/redo', headers=headers,
        json={'expected_revision': undone['revision']},
    )
    assert redone_response.status_code == 200, redone_response.text
    redone = redone_response.json()
    assert _root_statement(redone, time_statement_id)['step_label'] == '读取当前时间'
    assert _root_statement(redone, if_id)['statement_id'] == if_id

    compiled_response = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is False
    assert {'PGM-LINK-006'} <= {
        item['code'] for item in compiled['diagnostics']
    }

    run_response = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={},
    )
    assert run_response.status_code == 409, run_response.text
    assert run_response.json()['detail']['code'] == 'program_compile_failed'
    assert {'PGM-LINK-006'} <= {
        item['code'] for item in run_response.json()['detail']['diagnostics']
    }


def test_http_compile_and_run_preserve_structured_diagnostics(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-diagnostics')
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID,
    })

    compiled_response = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is False
    diagnostic = next(item for item in compiled['diagnostics'] if item['code'] == 'PGM-VALUE-001')
    assert diagnostic['statement_id'] == inserted['selected_statement_id']
    assert diagnostic['value_id']
    assert diagnostic['field_path'].endswith(LOG_OUTPUT_CONTENT_PARAMETER_ID)

    run_response = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={},
    )
    assert run_response.status_code == 409, run_response.text
    assert run_response.json()['detail']['code'] == 'program_compile_failed'
    assert any(
        item['code'] == 'PGM-VALUE-001'
        for item in run_response.json()['detail']['diagnostics']
    )

    missing = client.get('/api/vnext/programs/function_missing', headers=headers)
    assert missing.status_code == 404
    assert missing.json()['detail']['code'] == 'program_not_found'


def test_http_no_target_rejects_calls_that_require_an_operation_target(tmp_path: Path) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-no-target')
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': 'official.target.capture_frame',
    })

    compiled_response = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is False
    diagnostic = next(
        item for item in compiled['diagnostics']
        if item['code'] == 'PGM-PLATFORM-001'
    )
    assert diagnostic['statement_id'] == inserted['selected_statement_id']
    assert '需要操作目标' in diagnostic['message']

    run_response = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={},
    )
    assert run_response.status_code == 409, run_response.text
    assert run_response.json()['detail']['code'] == 'program_compile_failed'


def test_explicit_no_target_does_not_inherit_the_project_default_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-explicit-no-target')
    targets = client.get('/api/vnext/targets', headers=headers).json()
    saved = client.put('/api/vnext/targets', headers=headers, json={
        'expected_revision': targets['revision'],
        'targets': [{
            'target_id': 'target_default_window',
            'name': '默认窗口',
            'type': 'windows',
            'window_title': 'A window that must not be resolved',
            'window_match': 'exact',
            'work_area': {'mode': 'client'},
            'allow_physical_fallback': True,
        }],
        'default_target_id': 'target_default_window',
    })
    assert saved.status_code == 200, saved.text
    inserted = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {LOG_OUTPUT_CONTENT_PARAMETER_ID: {
            'value_id': 'value_no_target_log', 'kind': 'string',
            'value': 'pure task',
        }},
    })

    compiled = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers,
        json={'target_platform': 'no_target'},
    )
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()['valid'] is True
    assert compiled.json()['ecir']['target_platform'] == 'no_target'
    assert compiled.json()['ecir']['default_target_id'] is None

    monkeypatch.setattr(vnext_runtime, '_use_worker_process', False)
    monkeypatch.setattr(vnext_runtime, '_persist_event_log', False)
    run = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers,
        json={'target_platform': 'no_target'},
    )
    assert run.status_code == 200, run.text
    execution_id = run.json()['execution_id']
    terminal = None
    for _ in range(100):
        terminal = client.get(f'/api/vnext/runs/{execution_id}').json()
        if terminal['status'] in {'completed', 'failed', 'cancelled'}:
            break
        time.sleep(0.01)
    assert terminal is not None
    assert terminal['status'] == 'completed', terminal
    assert any(item['message'] == 'pure task' for item in terminal['events'])


def test_verified_structured_program_runs_through_http(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client()
    function_id, revision, headers = _open(client, tmp_path / 'program-runtime')
    assigned = _command(client, headers, function_id, revision, {
        'kind': 'insert_assignment',
        'target': {
            'kind': 'local', 'symbol_id': 'symbol_runtime_numbers',
            'display_name': '运行数字', 'value_type': 'list<int64>',
        },
        'value': {
            'value_id': 'value_runtime_numbers', 'kind': 'list', 'item_type': 'int64',
            'items': [
                {'value_id': 'value_runtime_one', 'kind': 'int64', 'value': 1},
                {'value_id': 'value_runtime_two', 'kind': 'int64', 'value': 2},
            ],
        },
    })
    revision = assigned['revision']
    loop = _command(client, headers, function_id, revision, {
        'kind': 'insert_loop', 'mode': 'for_each',
        'source': {
            'value_id': 'value_runtime_numbers_ref', 'kind': 'symbol_ref',
            'symbol_id': 'symbol_runtime_numbers', 'value_type': 'list<int64>',
        },
        'item_binding': {
            'symbol_id': 'symbol_runtime_item', 'display_name': '运行项',
            'value_type': 'int64',
        },
    })
    revision = loop['revision']
    loop_log = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {LOG_OUTPUT_CONTENT_PARAMETER_ID: {
            'value_id': 'value_runtime_item_ref', 'kind': 'symbol_ref',
            'symbol_id': 'symbol_runtime_item', 'value_type': 'int64',
        }},
        'location': {
            'parent_statement_id': loop['selected_statement_id'], 'block': 'body',
        },
    })
    revision = loop_log['revision']
    selected_if = _command(client, headers, function_id, revision, {
        'kind': 'insert_if',
        'condition': {'value_id': 'value_runtime_false', 'kind': 'bool', 'value': False},
    })
    revision = selected_if['revision']
    if_id = selected_if['selected_statement_id']
    branched = _command(client, headers, function_id, revision, {
        'kind': 'add_if_branch', 'statement_id': if_id,
        'condition': {'value_id': 'value_runtime_true', 'kind': 'bool', 'value': True},
    })
    revision = branched['revision']
    branch_id = _root_statement(branched, if_id)['additional_branches'][0]['branch_id']
    branch_log = _command(client, headers, function_id, revision, {
        'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {LOG_OUTPUT_CONTENT_PARAMETER_ID: {
            'value_id': 'value_runtime_branch_text', 'kind': 'string', 'value': 'elseif',
        }},
        'location': {
            'parent_statement_id': if_id,
            'block': 'additional_branch',
            'clause_id': branch_id,
        },
    })

    monkeypatch.setattr(vnext_runtime, '_use_worker_process', False)
    monkeypatch.setattr(vnext_runtime, '_persist_event_log', False)
    run_response = client.post(
        f'/api/vnext/programs/{function_id}/run', headers=headers, json={},
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
    messages = [item['message'] for item in terminal['events']]
    assert messages.count('1') == 1
    assert messages.count('2') == 1
    assert messages.count('elseif') == 1
    assert branch_log['document']['function']['statements'][-1]['statement_id'] == if_id


def test_project_program_catalog_call_bundle_and_runtime_round_trip_http(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client()
    entry_id, entry_revision, headers = _open(client, tmp_path / 'program-project-call')

    helper_response = client.post(
        '/api/vnext/programs', headers=headers, json={'display_name': '记录辅助函数'},
    )
    assert helper_response.status_code == 200, helper_response.text
    helper = helper_response.json()
    helper_id = helper['document']['function']['function_id']
    helper = _command(client, headers, helper_id, helper['revision'], {
        'kind': 'insert_call',
        'function_id': LOG_OUTPUT_FUNCTION_ID,
        'arguments': {
            LOG_OUTPUT_CONTENT_PARAMETER_ID: {
                'value_id': 'value_helper_message',
                'kind': 'string',
                'value': '来自项目函数',
            },
        },
    })

    unused_response = client.post(
        '/api/vnext/programs', headers=headers, json={'display_name': '不可达函数'},
    )
    assert unused_response.status_code == 200, unused_response.text
    unused_id = unused_response.json()['document']['function']['function_id']

    entry = _command(client, headers, entry_id, entry_revision, {
        'kind': 'insert_call',
        'function_id': helper_id,
    })
    assert entry['diagnostics'] == []

    catalog_response = client.get('/api/vnext/programs', headers=headers)
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = {item['function_id']: item for item in catalog_response.json()['programs']}
    assert {entry_id, helper_id, unused_id} <= catalog.keys()
    assert catalog[helper_id]['display_name'] == '记录辅助函数'
    assert catalog[helper_id]['parameters'] == []
    assert catalog[helper_id]['return_type'] == 'null'
    assert catalog[helper_id]['contract_version'] == 'project-v1'
    assert catalog[helper_id]['contract_fingerprint'].startswith('sha256:')

    compiled_response = client.post(
        f'/api/vnext/programs/{entry_id}/compile', headers=headers, json={},
    )
    assert compiled_response.status_code == 200, compiled_response.text
    compiled = compiled_response.json()
    assert compiled['valid'] is True, compiled['diagnostics']
    linked_ids = {item['function_id'] for item in compiled['ecir']['functions']}
    assert linked_ids == {entry_id, helper_id}
    assert unused_id not in linked_ids

    monkeypatch.setattr(vnext_runtime, '_use_worker_process', False)
    monkeypatch.setattr(vnext_runtime, '_persist_event_log', False)
    run_response = client.post(
        f'/api/vnext/programs/{entry_id}/run', headers=headers, json={},
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
    assert any(
        item['instruction_id'] == helper['selected_statement_id']
        and item['message'] == '来自项目函数'
        for item in terminal['events']
    )
