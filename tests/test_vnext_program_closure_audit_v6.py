from __future__ import annotations

import time

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_contracts import LOG_OUTPUT_CONTENT_PARAMETER_ID, LOG_OUTPUT_FUNCTION_ID
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    BoolValue,
    CallStatement,
    EntityReferenceValue,
    IntValue,
    JsonValue,
    ListenStatement,
    ListValue,
    LoopBinding,
    MessageEventSource,
    ProgramDocument,
    ProgramFunction,
    PureOperationValue,
    StringValue,
    TargetReferenceValue,
    TargetScopeStatement,
)
from core.vnext.program_validation import validate_program_document
from core.vnext.runtime import VNextRuntime


def _operation(value_id: str, operation_id: str, result_type: str, **inputs):
    return PureOperationValue(
        value_id=value_id,
        operation_id=operation_id,
        result_type=result_type,
        inputs={
            f'{operation_id}.input.{name}': value
            for name, value in inputs.items()
        },
    )


def _log(statement_id: str, value) -> CallStatement:
    return CallStatement(
        statement_id=statement_id,
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: value},
    )


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('runtime did not terminate')


def test_nested_list_map_json_operations_compile_and_execute() -> None:
    numbers = ListValue(
        value_id='value_numbers',
        item_type='int64',
        items=(IntValue(value_id='value_one', value=1), IntValue(value_id='value_two', value=2)),
    )
    appended = _operation(
        'value_appended', 'core.list_append.v1', 'list<int64>',
        list=numbers, value=IntValue(value_id='value_three', value=3),
    )
    total = _operation(
        'value_total', 'core.list_sum.v1', 'int64', list=appended,
    )
    json_get = _operation(
        'value_json_get', 'core.json_path_get.v1', 'optional<json_value>',
        json=JsonValue(value_id='value_json', payload={'nested': {'count': 7}}),
        path=ListValue(
            value_id='value_path', item_type='string',
            items=(
                StringValue(value_id='value_path_nested', value='nested'),
                StringValue(value_id='value_path_count', value='count'),
            ),
        ),
    )
    document = ProgramDocument(
        document_id='document_operations',
        function=ProgramFunction(
            function_id='project.operations',
            display_name='集合闭环',
            statements=(
                _log('statement_total', total),
                _log('statement_json', json_get),
            ),
        ),
    )
    compiled = compile_program_document(
        document, official_function_registry_v6, target_platform='no_target',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    plan = adapt_program_ecir_for_runtime(compiled['ecir'])
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert snapshot['status'] == 'completed', snapshot['error']
    messages = [item['message'] for item in snapshot['events'] if item['category'] == 'script']
    assert messages == ['6', '7']


def test_unknown_and_malformed_operations_are_stably_rejected() -> None:
    unknown = _operation(
        'value_unknown', 'core.not_registered.v1', 'int64',
        value=IntValue(value_id='value_unknown_input', value=1),
    )
    unknown_document = ProgramDocument(
        document_id='document_unknown_operation',
        function=ProgramFunction(
            function_id='project.unknown_operation', display_name='未知操作',
            statements=(_log('statement_unknown', unknown),),
        ),
    )
    assert any(
        item.code == 'PGM-OP-001'
        for item in validate_program_document(unknown_document, official_function_registry_v6)
    )

    malformed = _operation(
        'value_file_child', 'core.file_ref_child.v1', 'file_ref<write>',
    )
    malformed_document = ProgramDocument(
        document_id='document_malformed_file_operation',
        function=ProgramFunction(
            function_id='project.malformed_file_operation', display_name='输入不完整操作',
            statements=(_log('statement_malformed_file', malformed),),
        ),
    )
    compiled = compile_program_document(malformed_document, official_function_registry_v6)
    assert compiled['valid'] is False
    assert any(item['code'] == 'PGM-OP-003' for item in compiled['diagnostics'])


def test_operation_input_contract_and_host_dependent_statements_block_before_ecir() -> None:
    malformed = PureOperationValue(
        value_id='value_malformed',
        operation_id='core.number_add.v1',
        result_type='int64',
        inputs={
            'core.number_add.v1.input.left': StringValue(value_id='value_left', value='1'),
        },
    )
    malformed_document = ProgramDocument(
        document_id='document_malformed_operation',
        function=ProgramFunction(
            function_id='project.malformed_operation', display_name='错误输入',
            statements=(_log('statement_malformed', malformed),),
        ),
    )
    assert any(
        item.code == 'PGM-OP-003'
        for item in validate_program_document(malformed_document, official_function_registry_v6)
    )
    assert any(
        item.code == 'PGM-OP-004'
        for item in validate_program_document(malformed_document, official_function_registry_v6)
    )

    scoped = TargetScopeStatement(
        statement_id='statement_scope',
        target=TargetReferenceValue(value_id='value_target', target_id='target_one'),
    )
    listened = ListenStatement(
        statement_id='statement_listen',
        event_source=MessageEventSource(
            name=StringValue(value_id='value_message_name', value='invite'),
        ),
        receive_binding=LoopBinding(
            symbol_id='symbol_message', display_name='消息', value_type='received_message',
        ),
        handler_function_id='project.handler',
        handler_arguments={
            'project.handler.parameter.message': EntityReferenceValue(
                value_id='value_handler_argument',
                reference_id='message_placeholder',
                reference_type='received_message',
            ),
        },
    )
    host_document = ProgramDocument(
        document_id='document_host_statements',
        function=ProgramFunction(
            function_id='project.host_statements', display_name='宿主语句',
            statements=(scoped, listened),
        ),
    )
    compiled = compile_program_document(host_document, official_function_registry_v6)
    assert compiled['valid'] is False
    assert {'PGM-TARGET-001', 'PGM-LISTEN-002'} <= {
        item['code'] for item in compiled['diagnostics']
    }


def test_pure_operation_runtime_error_remains_structured_and_located() -> None:
    division = _operation(
        'value_division', 'core.number_divide.v1', 'float64',
        left=IntValue(value_id='value_dividend', value=10),
        right=IntValue(value_id='value_divisor', value=0),
    )
    document = ProgramDocument(
        document_id='document_division_error',
        function=ProgramFunction(
            function_id='project.division_error', display_name='除零错误',
            statements=(_log('statement_division', division),),
        ),
    )
    compiled = compile_program_document(
        document, official_function_registry_v6, target_platform='no_target',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(
        runtime,
        runtime.start(adapt_program_ecir_for_runtime(compiled['ecir']))['execution_id'],
    )
    assert snapshot['status'] == 'failed'
    assert snapshot['error_id'] == 'runtime.divide_by_zero'
    assert snapshot['current_instruction_id'] == 'statement_division'


def test_select_and_optional_default_do_not_evaluate_unused_error_branch() -> None:
    failing_default = _operation(
        'value_failing_default', 'core.number_divide.v1', 'float64',
        left=IntValue(value_id='value_default_dividend', value=10),
        right=IntValue(value_id='value_default_divisor', value=0),
    )
    selected = _operation(
        'value_selected', 'core.select.v1', 'float64',
        condition=BoolValue(value_id='value_true', value=True),
        when_true=_operation(
            'value_true_number', 'core.number_to_float.v1', 'float64',
            value=IntValue(value_id='value_five', value=5),
        ),
        when_false=failing_default,
    )
    document = ProgramDocument(
        document_id='document_lazy_select',
        function=ProgramFunction(
            function_id='project.lazy_select', display_name='惰性分支',
            statements=(_log('statement_selected', selected),),
        ),
    )
    compiled = compile_program_document(
        document, official_function_registry_v6, target_platform='no_target',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    plan = adapt_program_ecir_for_runtime(compiled['ecir'])
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert snapshot['status'] == 'completed', snapshot['error']
    messages = [item['message'] for item in snapshot['events'] if item['category'] == 'script']
    assert messages == ['5.0']
