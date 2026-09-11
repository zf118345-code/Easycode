from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.contracts.vnext import ProgramCommandRequest

REVISION = 'sha256:' + ('a' * 64)


def test_program_command_contract_is_discriminated_and_strict() -> None:
    request = ProgramCommandRequest.model_validate({
        'expected_revision': REVISION,
        'command': {
            'kind': 'insert_call',
            'function_id': 'official.log.output',
            'location': {'block': 'root'},
        },
    })

    assert request.command.kind == 'insert_call'
    assert request.command.location.block == 'root'

    with pytest.raises(ValidationError):
        ProgramCommandRequest.model_validate({
            'expected_revision': REVISION,
            'command': {
                'kind': 'insert_call',
                'function_id': 'official.log.output',
                'misspelled_location': {},
            },
        })


def test_program_update_argument_preserves_typed_value_payload() -> None:
    request = ProgramCommandRequest.model_validate({
        'expected_revision': REVISION,
        'command': {
            'kind': 'update_argument',
            'statement_id': 'stmt_1',
            'parameter_id': 'official.log.output.parameter.content',
            'value': {'value_id': 'value_1', 'kind': 'string', 'value': '测试'},
        },
    })

    assert request.command.value.kind == 'string'

    with pytest.raises(ValidationError):
        ProgramCommandRequest.model_validate({
            'expected_revision': 'stale',
            'command': request.command.model_dump(),
        })


@pytest.mark.parametrize('value', [
    {'value_id': 'value_unset', 'kind': 'unset', 'expected_type': 'string'},
    {'value_id': 'value_null', 'kind': 'null'},
    {'value_id': 'value_string', 'kind': 'string', 'value': '文本'},
    {'value_id': 'value_int', 'kind': 'int64', 'value': 7},
    {'value_id': 'value_float', 'kind': 'float64', 'value': 1.5},
    {'value_id': 'value_bool', 'kind': 'bool', 'value': True},
    {'value_id': 'value_date', 'kind': 'date', 'value': '2026-09-01'},
    {'value_id': 'value_datetime', 'kind': 'datetime', 'value': '2026-09-01T10:00:00+08:00'},
    {'value_id': 'value_time', 'kind': 'time', 'value': '10:00:00'},
    {'value_id': 'value_duration', 'kind': 'duration', 'milliseconds': 1000},
    {'value_id': 'value_point', 'kind': 'point', 'x': 1, 'y': 2},
    {'value_id': 'value_rect', 'kind': 'rect', 'x': 1, 'y': 2, 'width': 3, 'height': 4},
    {'value_id': 'value_path', 'kind': 'path', 'points': [{'x': 1, 'y': 2}]},
    {
        'value_id': 'value_symbol', 'kind': 'symbol_ref',
        'symbol_id': 'symbol_source', 'value_type': 'string',
    },
    {
        'value_id': 'value_project', 'kind': 'project_variable_ref',
        'variable_id': 'project_variable_name', 'value_type': 'string',
    },
    {'value_id': 'value_asset', 'kind': 'asset_ref', 'asset_id': 'asset_login'},
    {'value_id': 'value_target', 'kind': 'target_ref', 'target_id': 'target_main'},
    {
        'value_id': 'value_entity', 'kind': 'entity_ref',
        'reference_id': 'instance_main', 'reference_type': 'instance_ref',
    },
    {
        'value_id': 'value_member', 'kind': 'member_access',
        'source': {
            'value_id': 'value_record_source', 'kind': 'record', 'record_type': 'record.demo',
            'fields': {'record.demo.field.name': {
                'value_id': 'value_record_name', 'kind': 'string', 'value': '演示',
            }},
        },
        'field_id': 'record.demo.field.name', 'result_type': 'string',
    },
    {
        'value_id': 'value_list', 'kind': 'list', 'item_type': 'int64',
        'items': [{'value_id': 'value_list_item', 'kind': 'int64', 'value': 1}],
    },
    {
        'value_id': 'value_map', 'kind': 'map', 'key_type': 'string',
        'entry_value_type': 'int64', 'entries': [{
            'key': {'value_id': 'value_map_key', 'kind': 'string', 'value': 'a'},
            'value': {'value_id': 'value_map_item', 'kind': 'int64', 'value': 1},
        }],
    },
    {
        'value_id': 'value_record', 'kind': 'record', 'record_type': 'record.demo',
        'fields': {'record.demo.field.name': {
            'value_id': 'value_record_field', 'kind': 'string', 'value': '演示',
        }},
    },
    {'value_id': 'value_json', 'kind': 'json', 'payload': {'enabled': True}},
    {
        'value_id': 'value_operation', 'kind': 'operation',
        'operation_id': 'core.number_add.v1', 'result_type': 'int64',
        'inputs': {
            'core.number_add.v1.input.left': {
                'value_id': 'value_left', 'kind': 'int64', 'value': 1,
            },
            'core.number_add.v1.input.right': {
                'value_id': 'value_right', 'kind': 'int64', 'value': 2,
            },
        },
    },
    {
        'value_id': 'value_compare', 'kind': 'compare', 'operator': 'eq',
        'left': {'value_id': 'value_compare_left', 'kind': 'int64', 'value': 1},
        'right': {'value_id': 'value_compare_right', 'kind': 'int64', 'value': 1},
    },
    {
        'value_id': 'value_group', 'kind': 'condition_group', 'operator': 'all',
        'conditions': [{'value_id': 'value_group_item', 'kind': 'bool', 'value': True}],
    },
    {
        'value_id': 'value_not', 'kind': 'not',
        'condition': {'value_id': 'value_not_item', 'kind': 'bool', 'value': False},
    },
])
def test_program_http_contract_accepts_every_program_value_node(value: dict) -> None:
    request = ProgramCommandRequest.model_validate({
        'expected_revision': REVISION,
        'command': {
            'kind': 'insert_assignment',
            'target': {
                'kind': 'local', 'symbol_id': 'symbol_target',
                'display_name': '结果', 'value_type': 'any',
            },
            'value': value,
        },
    })

    assert request.command.value.kind == value['kind']
