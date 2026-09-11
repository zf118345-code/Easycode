from __future__ import annotations

import time
from typing import Any

import pytest

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_commands import (
    ProgramCommandError,
    StatementLocation,
    insert_break,
    insert_continue,
    insert_fail,
    insert_loop,
    update_fail,
)
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    BreakStatement,
    ContinueStatement,
    FailStatement,
    IntValue,
    JsonValue,
    LoopStatement,
    ProgramDocument,
    ProgramFunction,
    StringValue,
    TryStatement,
)
from core.vnext.program_validation import validate_program_document
from core.vnext.runtime import VNextRuntime


def _instruction(instruction_id: str, opcode: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        'instruction_id': instruction_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': None,
        'source': {},
        'capabilities': [],
    }


def _log(instruction_id: str, content: str) -> dict[str, Any]:
    return _instruction(instruction_id, 'log.write', {
        'official.log.output.parameter.content': content,
        'official.log.output.parameter.level': 'info',
        'official.log.output.parameter.category': 'flow-test',
    })


def _plan(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'entry_function_id': 'function.main',
        'project_variables': [],
        'functions': [{
            'function_id': 'function.main',
            'name': '主程序',
            'parameters': [],
            'parameter_definitions': [],
            'return_type': 'null',
            'instructions': instructions,
        }],
    }


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


def test_loop_control_is_lexical_and_commands_reject_root_insertion() -> None:
    document = ProgramDocument(
        document_id='document.flow',
        function=ProgramFunction(function_id='function.flow', display_name='流程'),
    )
    with pytest.raises(ProgramCommandError, match='循环体内'):
        insert_break(document)

    loop_result = insert_loop(
        document,
        'repeat',
        IntValue(value_id='value.repeat_count', value=2),
    )
    loop_id = loop_result.selected_statement_id
    break_result = insert_break(
        loop_result.document,
        location=StatementLocation(parent_statement_id=loop_id, block='body'),
    )
    continue_result = insert_continue(
        break_result.document,
        location=StatementLocation(parent_statement_id=loop_id, block='body'),
    )
    assert validate_program_document(continue_result.document, official_function_registry_v6) == ()

    compiled = compile_program_document(
        continue_result.document,
        official_function_registry_v6,
    )
    assert compiled['valid'] is True
    body = compiled['ecir']['functions'][0]['instructions'][0]['arguments']['body']
    assert [item['opcode'] for item in body] == ['control.break', 'control.continue']
    adapt_program_ecir_for_runtime(compiled['ecir'])


def test_validator_rejects_loop_control_outside_loop_even_through_try() -> None:
    document = ProgramDocument(
        document_id='document.invalid_flow',
        function=ProgramFunction(
            function_id='function.invalid_flow',
            display_name='错误流程',
            statements=(
                BreakStatement(statement_id='statement.break'),
                TryStatement(
                    statement_id='statement.try',
                    body=(ContinueStatement(statement_id='statement.continue'),),
                ),
            ),
        ),
    )
    diagnostics = validate_program_document(document, official_function_registry_v6)
    assert [(item.code, item.statement_id) for item in diagnostics] == [
        ('PGM-FLOW-001', 'statement.break'),
        ('PGM-FLOW-001', 'statement.continue'),
    ]


def test_break_continue_and_finally_execute_with_nearest_loop_semantics() -> None:
    runtime = VNextRuntime(persist_event_log=False)
    repeat_with_continue = _instruction('loop.continue', 'control.repeat', {
        'source': 2,
        'bindings': {},
        'body': [
            _instruction('try.continue', 'control.try', {
                'body': [_log('log.before_continue', '本轮开始'), _instruction('continue', 'control.continue', {})],
                'retry_policy': None,
                'catches': [],
                'finally': [_log('log.finally', '完成清理')],
            }),
            _log('log.skipped', '不应执行'),
        ],
    })
    repeat_with_break = _instruction('loop.break', 'control.repeat', {
        'source': 5,
        'bindings': {},
        'body': [_log('log.before_break', '准备退出'), _instruction('break', 'control.break', {})],
    })
    result = _terminal(runtime, runtime.start(_plan([
        repeat_with_continue,
        repeat_with_break,
        _log('log.after', '循环之后'),
    ]))['execution_id'])
    assert result['status'] == 'completed'
    messages = [item['message'] for item in result['events'] if item['category'] == 'flow-test']
    assert messages == ['本轮开始', '完成清理', '本轮开始', '完成清理', '准备退出', '循环之后']


def test_explicit_failure_is_permanent_catchable_and_keeps_safe_details() -> None:
    document = ProgramDocument(
        document_id='document.failure',
        function=ProgramFunction(function_id='function.failure', display_name='失败流程'),
    )
    inserted = insert_fail(
        document,
        'project.login_failed',
        StringValue(value_id='value.failure_message', value='登录条件不满足'),
        details=JsonValue(value_id='value.failure_details', payload={'attempt': 2}),
    )
    assert isinstance(inserted.document.function.statements[0], FailStatement)
    updated = update_fail(
        inserted.document,
        inserted.selected_statement_id,
        error_id='project.login_failed',
        message=StringValue(value_id='value.replacement_message', value='仍未登录'),
        details=JsonValue(value_id='value.replacement_details', payload={'password': 'secret', 'attempt': 3}),
        registry=official_function_registry_v6,
    )
    statement = updated.document.function.statements[0]
    assert isinstance(statement, FailStatement)
    assert statement.message.value_id == 'value.failure_message'
    assert statement.details is not None and statement.details.value_id == 'value.failure_details'

    compiled = compile_program_document(updated.document, official_function_registry_v6)
    assert compiled['valid'] is True
    instruction = compiled['ecir']['functions'][0]['instructions'][0]
    assert instruction['opcode'] == 'control.fail'

    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_plan([instruction]))['execution_id'])
    assert result['status'] == 'failed'
    assert result['error_id'] == 'project.login_failed'
    assert result['error'] == '仍未登录'
    assert result['error_details'] == {'password': '<已隐藏>', 'attempt': 3}
