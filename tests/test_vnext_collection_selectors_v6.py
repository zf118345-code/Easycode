from __future__ import annotations

import time

import pytest

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_commands import StatementLocation, copy_statement
from core.vnext.program_compiler import compile_program_document
from core.vnext.player_bindings import (
    apply_player_bindings,
    build_player_binding_sources,
    player_type_fingerprint,
)
from core.vnext.program_contracts import LOG_OUTPUT_CONTENT_PARAMETER_ID, LOG_OUTPUT_FUNCTION_ID
from core.vnext.program_types import (
    BoolValue,
    CallStatement,
    ComparisonValue,
    IntValue,
    ListValue,
    ProgramDocument,
    ProgramFunction,
    PureOperationValue,
    SelectorBinding,
    SelectorValue,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.program_validation import validate_program_document
from core.vnext.runtime import RuntimeFailure, VNextRuntime


def _selector(
    value_id: str,
    *,
    item_type: str,
    result_type: str,
    expression,
    item_symbol: str = 'symbol_item',
    index_symbol: str = 'symbol_index',
) -> SelectorValue:
    return SelectorValue(
        value_id=value_id,
        bindings=(
            SelectorBinding(
                symbol_id=item_symbol, role='item', display_name='当前项',
                value_type=item_type,
            ),
            SelectorBinding(
                symbol_id=index_symbol, role='index', display_name='当前序号',
                value_type='int64',
            ),
        ),
        result_type=result_type,
        expression=expression,
    )


def _operation(value_id: str, operation_id: str, result_type: str, **inputs) -> PureOperationValue:
    return PureOperationValue(
        value_id=value_id,
        operation_id=operation_id,
        result_type=result_type,
        inputs={f'{operation_id}.input.{name}': value for name, value in inputs.items()},
    )


def _runtime_operation(operation_id: str, **inputs):
    return {
        'kind': 'operation',
        'operation_id': operation_id,
        'inputs': {f'{operation_id}.input.{name}': value for name, value in inputs.items()},
    }


def _list_selector(expression, *, item='item', index='index'):
    return {
        'kind': 'selector',
        'bindings': [
            {'symbol_id': item, 'role': 'item', 'value_type': 'int64'},
            {'symbol_id': index, 'role': 'index', 'value_type': 'int64'},
        ],
        'result_type': 'bool',
        'expression': expression,
    }


def _reference(symbol_id: str):
    return {'kind': 'reference', 'scope': 'local', 'symbol_id': symbol_id}


def _compare(operator: str, left, right):
    return {'kind': 'compare', 'operator': operator, 'left': left, 'right': right}


def test_selector_is_typed_lexical_and_compiles_to_ecir() -> None:
    item = SymbolReferenceValue(
        value_id='value_item_ref', symbol_id='symbol_item', value_type='int64',
    )
    predicate = _selector(
        'value_predicate', item_type='int64', result_type='bool',
        expression=ComparisonValue(
            value_id='value_compare', operator='gt', left=item,
            right=IntValue(value_id='value_limit', value=1),
        ),
    )
    filtered = _operation(
        'value_filtered', 'core.list_filter.v1', 'list<int64>',
        list=ListValue(
            value_id='value_numbers', item_type='int64',
            items=(IntValue(value_id='value_one', value=1), IntValue(value_id='value_two', value=2)),
        ),
        predicate=predicate,
    )
    statement = CallStatement(
        statement_id='statement_log', function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: filtered},
    )
    document = ProgramDocument(
        document_id='document_selector',
        function=ProgramFunction(
            function_id='project.selector', display_name='集合选择器', statements=(statement,),
        ),
    )

    assert validate_program_document(document, official_function_registry_v6) == ()
    compiled = compile_program_document(document, official_function_registry_v6, target_platform='no_target')
    assert compiled['valid'] is True, compiled['diagnostics']
    lowered = compiled['ecir']['functions'][0]['instructions'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]
    selector = lowered['inputs']['core.list_filter.v1.input.predicate']
    assert selector['kind'] == 'selector'
    assert [item['role'] for item in selector['bindings']] == ['item', 'index']
    assert selector['expression']['left']['symbol_id'] == 'symbol_item'
    slots = {item['value_id']: item for item in compiled['ecir']['value_override_slots']}
    assert set(slots) == {'value_numbers', 'value_limit'}
    assert slots['value_limit']['path'][-2:] == ['right'] or slots['value_limit']['path'][-1:] == ['right']

    catalog = build_player_binding_sources(compiled['ecir'])['sources']
    limit_source = next(item for item in catalog if item['binding'].get('value_id') == 'value_limit')
    assert '右侧值' in limit_source['label']
    form = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'page_main',
            'controls': [{
                'control_id': 'limit', 'type': 'number', 'label': '筛选下限',
                'source_type': 'int64',
                'type_fingerprint': player_type_fingerprint('int64', {}),
                'binding': limit_source['binding'],
            }],
        }],
    }
    applied = apply_player_bindings(compiled['ecir'], form, {'limit': 7})
    patched = applied['functions'][0]['instructions'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]
    assert patched['inputs']['core.list_filter.v1.input.predicate']['expression']['right'] == 7


def test_selector_cannot_escape_collection_input_and_copy_remaps_owned_ids() -> None:
    selector = _selector(
        'value_selector', item_type='int64', result_type='bool',
        expression=BoolValue(value_id='value_true', value=True),
    )
    escaped = ProgramDocument(
        document_id='document_escaped_selector',
        function=ProgramFunction(
            function_id='project.escaped_selector', display_name='非法选择器',
            statements=(CallStatement(
                statement_id='statement_escaped', function_id=LOG_OUTPUT_FUNCTION_ID,
                arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: selector},
            ),),
        ),
    )
    assert 'PGM-SELECTOR-001' in {
        item.code for item in validate_program_document(escaped, official_function_registry_v6)
    }

    operation = _operation(
        'value_filter', 'core.list_filter.v1', 'list<int64>',
        list=ListValue(value_id='value_list', item_type='int64'), predicate=selector,
    )
    document = ProgramDocument(
        document_id='document_copy_selector',
        function=ProgramFunction(
            function_id='project.copy_selector', display_name='复制选择器',
            statements=(CallStatement(
                statement_id='statement_source', function_id=LOG_OUTPUT_FUNCTION_ID,
                arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: operation},
            ),),
        ),
    )
    copied = copy_statement(
        document, 'statement_source',
        StatementLocation(parent_statement_id=None, block='root', before_statement_id=None),
    ).document
    first, second = copied.function.statements
    first_selector = first.arguments[LOG_OUTPUT_CONTENT_PARAMETER_ID].inputs['core.list_filter.v1.input.predicate']
    second_selector = second.arguments[LOG_OUTPUT_CONTENT_PARAMETER_ID].inputs['core.list_filter.v1.input.predicate']
    assert first_selector.value_id != second_selector.value_id
    assert {item.symbol_id for item in first_selector.bindings}.isdisjoint(
        {item.symbol_id for item in second_selector.bindings}
    )


def test_nested_selectors_shadow_display_names_by_stable_symbol_id() -> None:
    inner_item = SymbolReferenceValue(
        value_id='value_inner_item_ref', symbol_id='symbol_inner_item', value_type='int64',
    )
    inner = _selector(
        'value_inner_selector', item_type='int64', result_type='int64',
        expression=inner_item, item_symbol='symbol_inner_item', index_symbol='symbol_inner_index',
    )
    outer_item = SymbolReferenceValue(
        value_id='value_outer_item_ref', symbol_id='symbol_outer_item', value_type='list<int64>',
    )
    inner_map = _operation(
        'value_inner_map', 'core.list_map.v1', 'list<int64>',
        list=outer_item, transform=inner,
    )
    outer = _selector(
        'value_outer_selector', item_type='list<int64>', result_type='list<int64>',
        expression=inner_map, item_symbol='symbol_outer_item', index_symbol='symbol_outer_index',
    )
    mapped = _operation(
        'value_outer_map', 'core.list_map.v1', 'list<list<int64>>',
        list=ListValue(value_id='value_nested_list', item_type='list<int64>'),
        transform=outer,
    )
    document = ProgramDocument(
        document_id='document_nested_selectors',
        function=ProgramFunction(
            function_id='project.nested_selectors', display_name='嵌套逐项计算',
            statements=(CallStatement(
                statement_id='statement_nested', function_id=LOG_OUTPUT_FUNCTION_ID,
                arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: mapped},
            ),),
        ),
    )
    assert validate_program_document(document, official_function_registry_v6) == ()


def test_list_selector_runtime_semantics_are_deterministic_and_short_circuit() -> None:
    values = {'kind': 'list', 'items': [3, 1, 2, 1]}
    predicate = _list_selector(_compare('gt', _reference('item'), 1))
    assert VNextRuntime._value(_runtime_operation(
        'core.list_filter.v1', list=values, predicate=predicate,
    ), {}) == [3, 2]
    assert VNextRuntime._value(_runtime_operation(
        'core.list_find_first.v1', list=values, predicate=predicate,
    ), {}) == 3
    assert VNextRuntime._value(_runtime_operation(
        'core.list_count_match.v1', list=values, predicate=predicate,
    ), {}) == 2
    assert VNextRuntime._value(_runtime_operation(
        'core.list_any.v1', list=values, predicate=predicate,
    ), {}) is True
    assert VNextRuntime._value(_runtime_operation(
        'core.list_all.v1', list=values, predicate=predicate,
    ), {}) is False
    assert VNextRuntime._value(_runtime_operation(
        'core.list_all.v1', list={'kind': 'list', 'items': []}, predicate=predicate,
    ), {}) is True
    assert VNextRuntime._value(_runtime_operation(
        'core.list_find_first.v1', list={'kind': 'list', 'items': []}, predicate=predicate,
    ), {}) is None


def test_list_transform_group_sort_flatten_zip_and_duplicate_index() -> None:
    values = {'kind': 'list', 'items': [3, 1, 2, 1]}
    identity = _list_selector(_reference('item'))
    identity['result_type'] = 'int64'
    sorted_values = VNextRuntime._value(_runtime_operation(
        'core.list_sort_by.v1', list=values, key_selector=identity, descending=False,
    ), {})
    assert sorted_values == [1, 1, 2, 3]
    same_key = {**identity, 'expression': 0}
    assert VNextRuntime._value(_runtime_operation(
        'core.list_sort_by.v1', list=values, key_selector=same_key, descending=True,
    ), {}) == values['items']
    grouped = VNextRuntime._value(_runtime_operation(
        'core.list_group_by.v1', list=values, key_selector=identity,
    ), {})
    assert grouped == {3: [3], 1: [1, 1], 2: [2]}
    transformed = VNextRuntime._value(_runtime_operation(
        'core.list_map.v1', list=values, transform=identity,
    ), {})
    assert transformed == values['items'] and transformed is not values['items']
    assert VNextRuntime._value(_runtime_operation(
        'core.list_flatten.v1', list={'kind': 'list', 'items': [[1, 2], [], [3]]},
    ), {}) == [1, 2, 3]
    assert VNextRuntime._value(_runtime_operation(
        'core.list_zip.v1', list={'kind': 'list', 'items': [1, 2]},
        other={'kind': 'list', 'items': ['a']},
    ), {}) == [{'zip_pair.field.left': 1, 'zip_pair.field.right': 'a'}]
    with pytest.raises(RuntimeFailure) as error:
        VNextRuntime._value(_runtime_operation(
            'core.list_index_by.v1', list=values, key_selector=identity,
        ), {})
    assert error.value.error_id == 'runtime.map_duplicate_key'


def test_map_selectors_preserve_snapshot_and_entry_identity() -> None:
    source = {'kind': 'map', 'entries': [
        {'key': 'a', 'value': 1}, {'key': 'b', 'value': 2}, {'key': 'c', 'value': 1},
    ]}
    predicate = {
        'kind': 'selector',
        'bindings': [
            {'symbol_id': 'key', 'role': 'key'},
            {'symbol_id': 'value', 'role': 'value'},
        ],
        'result_type': 'bool',
        'expression': _compare('gt', _reference('value'), 1),
    }
    assert VNextRuntime._value(_runtime_operation(
        'core.map_filter.v1', map=source, predicate=predicate,
    ), {}) == {'b': 2}
    identity = {**predicate, 'result_type': 'int64', 'expression': _reference('value')}
    assert VNextRuntime._value(_runtime_operation(
        'core.map_map_values.v1', map=source, transform=identity,
    ), {}) == {'a': 1, 'b': 2, 'c': 1}
    grouped = VNextRuntime._value(_runtime_operation(
        'core.map_group_by.v1', map=source, key_selector=identity,
    ), {})
    assert grouped[1] == [
        {'map_entry.field.key': 'a', 'map_entry.field.value': 1},
        {'map_entry.field.key': 'c', 'map_entry.field.value': 1},
    ]


def test_json_schema_validation_reports_precise_path() -> None:
    schema = {
        'type': 'object', 'required': ['name'],
        'properties': {'name': {'type': 'string'}},
        'additionalProperties': False,
    }
    valid = VNextRuntime._value(_runtime_operation(
        'core.json_validate_schema.v1', json={'kind': 'json', 'value': {'name': 'EasyCode'}},
        schema={'kind': 'json', 'value': schema},
    ), {})
    assert valid == {'name': 'EasyCode'}
    with pytest.raises(RuntimeFailure) as error:
        VNextRuntime._value(_runtime_operation(
            'core.json_validate_schema.v1', json={'kind': 'json', 'value': {'name': 7}},
            schema={'kind': 'json', 'value': schema},
        ), {})
    assert error.value.error_id == 'runtime.json_schema_invalid'
    assert '.name' in str(error.value)


def test_ten_thousand_items_stay_bounded_and_are_cancellable() -> None:
    values = {'kind': 'list', 'items': list(range(10_000))}
    predicate = _list_selector(_compare('gte', _reference('item'), 5_000))
    started = time.perf_counter()
    result = VNextRuntime._value(_runtime_operation(
        'core.list_filter.v1', list=values, predicate=predicate,
    ), {})
    assert result[0] == 5_000 and len(result) == 5_000
    assert time.perf_counter() - started < 3.0

    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    with pytest.raises(RuntimeFailure) as error:
        VNextRuntime._value(_runtime_operation(
            'core.list_filter.v1', list=values, predicate=predicate,
        ), {'__cancel_check__': cancelled})
    assert error.value.error_id == 'runtime.cancelled'

    with pytest.raises(RuntimeFailure) as budget_error:
        VNextRuntime._value(_runtime_operation(
            'core.list_filter.v1',
            list={'kind': 'list', 'items': list(range(100_001))},
            predicate=predicate,
        ), {})
    assert budget_error.value.error_id == 'runtime.collection_budget'
