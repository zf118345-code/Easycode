from __future__ import annotations

import time
from typing import Any

import pytest

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_compiler import compile_program_bundle
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
    LOG_OUTPUT_LEVEL_PARAMETER_ID,
    WAIT_DURATION_FUNCTION_ID,
    WAIT_DURATION_PARAMETER_ID,
)
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    DurationValue,
    IntValue,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    ResultBinding,
    ReturnStatement,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.runtime import VNextRuntime


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


def _parameter(function_id: str) -> ProgramParameter:
    return ProgramParameter(
        parameter_id=f'{function_id}.parameter.message',
        symbol_id=f'{function_id}.symbol.message',
        display_name='消息',
        value_type='string',
    )


def _identity(function_id: str, *, log_level: str = 'info') -> ProgramDocument:
    parameter = _parameter(function_id)
    return ProgramDocument(
        document_id=f'document.{function_id}',
        function=ProgramFunction(
            function_id=function_id,
            display_name=function_id,
            parameters=(parameter,),
            return_type='string',
            statements=(
                CallStatement(
                    statement_id=f'{function_id}.statement.log',
                    function_id=LOG_OUTPUT_FUNCTION_ID,
                    arguments={
                        LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
                            value_id=f'{function_id}.value.log',
                            symbol_id=parameter.symbol_id,
                            value_type='string',
                        ),
                        LOG_OUTPUT_LEVEL_PARAMETER_ID: StringValue(
                            value_id=f'{function_id}.value.level', value=log_level,
                        ),
                    },
                ),
                ReturnStatement(
                    statement_id=f'{function_id}.statement.return',
                    value=SymbolReferenceValue(
                        value_id=f'{function_id}.value.return',
                        symbol_id=parameter.symbol_id,
                        value_type='string',
                    ),
                ),
            ),
        ),
    )


def _calling_function(function_id: str, callee_id: str) -> ProgramDocument:
    parameter = _parameter(function_id)
    result_symbol = f'{function_id}.symbol.result'
    return ProgramDocument(
        document_id=f'document.{function_id}',
        function=ProgramFunction(
            function_id=function_id,
            display_name=function_id,
            parameters=(parameter,),
            return_type='string',
            statements=(
                CallStatement(
                    statement_id=f'{function_id}.statement.call',
                    function_id=callee_id,
                    arguments={
                        f'{callee_id}.parameter.message': SymbolReferenceValue(
                            value_id=f'{function_id}.value.argument',
                            symbol_id=parameter.symbol_id,
                            value_type='string',
                        ),
                    },
                    result_binding=ResultBinding(
                        symbol_id=result_symbol,
                        display_name='结果',
                        value_type='string',
                    ),
                ),
                ReturnStatement(
                    statement_id=f'{function_id}.statement.return',
                    value=SymbolReferenceValue(
                        value_id=f'{function_id}.value.return',
                        symbol_id=result_symbol,
                        value_type='string',
                    ),
                ),
            ),
        ),
    )


def _entry(callee_id: str, *, text: str = '你好') -> ProgramDocument:
    result_symbol = 'project.main.symbol.result'
    return ProgramDocument(
        document_id='document.project.main',
        function=ProgramFunction(
            function_id='project.main',
            display_name='主程序',
            statements=(
                CallStatement(
                    statement_id='project.main.statement.call',
                    function_id=callee_id,
                    arguments={f'{callee_id}.parameter.message': StringValue(
                        value_id='project.main.value.argument', value=text,
                    )},
                    result_binding=ResultBinding(
                        symbol_id=result_symbol,
                        display_name='返回值',
                        value_type='string',
                    ),
                ),
                CallStatement(
                    statement_id='project.main.statement.log',
                    function_id=LOG_OUTPUT_FUNCTION_ID,
                    arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
                        value_id='project.main.value.result',
                        symbol_id=result_symbol,
                        value_type='string',
                    )},
                ),
            ),
        ),
    )


def _compile_and_adapt(documents: list[ProgramDocument]) -> dict[str, Any]:
    compiled = compile_program_bundle(
        documents,
        official_function_registry_v6,
        entry_function_id='project.main',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    return adapt_program_ecir_for_runtime(compiled['ecir'])


def test_bundle_adapter_runtime_calls_helper_with_parameter_and_return() -> None:
    plan = _compile_and_adapt([_entry('project.helper'), _identity('project.helper')])
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'completed', result['error']
    script = [item for item in result['events'] if item['category'] == 'script']
    assert [(item['message'], item['instruction_id']) for item in script] == [
        ('你好', 'project.helper.statement.log'),
        ('你好', 'project.main.statement.log'),
    ]


@pytest.mark.parametrize(
    ('value_type', 'literal', 'expected_message'),
    (
        ('int64', IntValue(value_id='value.integer', value=7), '7'),
        (
            'duration',
            DurationValue(value_id='value.duration', milliseconds=25),
            '25',
        ),
    ),
)
def test_format6_project_function_parameters_use_format6_runtime_types(
    value_type: str,
    literal: IntValue | DurationValue,
    expected_message: str,
) -> None:
    parameter = ProgramParameter(
        parameter_id='project.helper.parameter.value',
        symbol_id='project.helper.symbol.value',
        display_name='值',
        value_type=value_type,
    )
    helper = ProgramDocument(
        document_id='document.project.helper',
        function=ProgramFunction(
            function_id='project.helper',
            display_name='返回原值',
            parameters=(parameter,),
            return_type=value_type,
            statements=(ReturnStatement(
                statement_id='project.helper.statement.return',
                value=SymbolReferenceValue(
                    value_id='project.helper.value.return',
                    symbol_id=parameter.symbol_id,
                    value_type=value_type,
                ),
            ),),
        ),
    )
    result_symbol = 'project.main.symbol.result'
    entry = ProgramDocument(
        document_id='document.project.main',
        function=ProgramFunction(
            function_id='project.main',
            display_name='主程序',
            statements=(
                CallStatement(
                    statement_id='project.main.statement.call',
                    function_id='project.helper',
                    arguments={parameter.parameter_id: literal},
                    result_binding=ResultBinding(
                        symbol_id=result_symbol,
                        display_name='结果',
                        value_type=value_type,
                    ),
                ),
                CallStatement(
                    statement_id='project.main.statement.log',
                    function_id=LOG_OUTPUT_FUNCTION_ID,
                    arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
                        value_id='project.main.value.result',
                        symbol_id=result_symbol,
                        value_type=value_type,
                    )},
                ),
            ),
        ),
    )
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(_compile_and_adapt([entry, helper]))['execution_id'],
    )
    assert result['status'] == 'completed', result['error']
    assert any(
        event['message'] == expected_message
        and event['instruction_id'] == 'project.main.statement.log'
        for event in result['events']
    )


def test_bundle_adapter_runtime_calls_two_project_levels() -> None:
    plan = _compile_and_adapt([
        _entry('project.middle'),
        _calling_function('project.middle', 'project.leaf'),
        _identity('project.leaf'),
    ])
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'completed', result['error']
    assert any(
        item['instruction_id'] == 'project.leaf.statement.log'
        and item['message'] == '你好'
        for item in result['events']
    )


def test_project_call_failure_reports_inner_instruction() -> None:
    plan = _compile_and_adapt([
        _entry('project.helper'),
        _identity('project.helper'),
    ])
    # Compile-time enum validation prevents authors from saving this value.
    # Mutating the transport plan verifies the Runtime still defends against a
    # damaged or hostile package and reports the inner stable instruction.
    helper = next(item for item in plan['functions'] if item['function_id'] == 'project.helper')
    helper['instructions'][0]['arguments'][LOG_OUTPUT_LEVEL_PARAMETER_ID] = 'invalid'
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'failed'
    assert result['current_instruction_id'] == 'project.helper.statement.log'
    assert any(
        item['level'] == 'error'
        and item['instruction_id'] == 'project.helper.statement.log'
        for item in result['events']
    )


def test_project_call_cancellation_keeps_inner_wait_location() -> None:
    helper = ProgramDocument(
        document_id='document.project.helper',
        function=ProgramFunction(
            function_id='project.helper',
            display_name='等待',
            parameters=(_parameter('project.helper'),),
            return_type='string',
            statements=(
                CallStatement(
                    statement_id='project.helper.statement.wait',
                    function_id=WAIT_DURATION_FUNCTION_ID,
                    arguments={WAIT_DURATION_PARAMETER_ID: DurationValue(
                        value_id='project.helper.value.duration', milliseconds=5000,
                    )},
                ),
                ReturnStatement(
                    statement_id='project.helper.statement.return',
                    value=SymbolReferenceValue(
                        value_id='project.helper.value.return',
                        symbol_id='project.helper.symbol.message',
                        value_type='string',
                    ),
                ),
            ),
        ),
    )
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(_compile_and_adapt([_entry('project.helper'), helper]))[
        'execution_id'
    ]
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if runtime.snapshot(execution_id)['current_instruction_id'] == (
            'project.helper.statement.wait'
        ):
            break
        time.sleep(0.01)
    runtime.cancel(execution_id)
    result = _terminal(runtime, execution_id)
    assert result['status'] == 'cancelled'
    assert result['current_instruction_id'] == 'project.helper.statement.wait'
    assert any(
        item['instruction_id'] == 'project.helper.statement.wait'
        and item['message'] == '任务已取消'
        for item in result['events']
    )


@pytest.mark.parametrize(
    ('mutation', 'error_id'),
    (
        ('missing', 'runtime.argument_missing'),
        ('unknown', 'runtime.argument_unknown'),
        ('wrong_type', 'runtime.argument_type'),
    ),
)
def test_project_call_runtime_strictly_checks_stable_arguments(
    mutation: str,
    error_id: str,
) -> None:
    plan = _compile_and_adapt([_entry('project.helper'), _identity('project.helper')])
    call = plan['functions'][0]['instructions'][0]
    parameter_id = 'project.helper.parameter.message'
    if mutation == 'missing':
        call['arguments'].pop(parameter_id)
    elif mutation == 'unknown':
        call['arguments']['project.helper.parameter.unknown'] = 'extra'
    else:
        call['arguments'][parameter_id] = 123
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'failed'
    assert result['error_id'] == error_id
    assert result['current_instruction_id'] == 'project.main.statement.call'
