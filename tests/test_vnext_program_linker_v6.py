from __future__ import annotations

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_compiler import compile_program_bundle
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
)
from core.vnext.program_types import (
    CallStatement,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    ResultBinding,
    ReturnStatement,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.pure_operations_v6 import (
    pure_operation_registry_hash,
    pure_operation_registry_payload,
)


def _parameter(function_id: str, name: str = 'message') -> ProgramParameter:
    return ProgramParameter(
        parameter_id=f'{function_id}.parameter.{name}',
        symbol_id=f'{function_id}.symbol.{name}',
        display_name='消息',
        value_type='string',
    )


def _helper(function_id: str = 'project.helper') -> ProgramDocument:
    parameter = _parameter(function_id)
    return ProgramDocument(
        document_id=f'document.{function_id}',
        function=ProgramFunction(
            function_id=function_id,
            display_name='辅助函数',
            parameters=(parameter,),
            return_type='string',
            statements=(
                CallStatement(
                    statement_id=f'{function_id}.statement.log',
                    function_id=LOG_OUTPUT_FUNCTION_ID,
                    arguments={
                        LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
                            value_id=f'{function_id}.value.message',
                            symbol_id=parameter.symbol_id,
                            value_type='string',
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


def _caller(
    function_id: str,
    callee_id: str,
    *,
    return_type: str = 'null',
) -> ProgramDocument:
    argument_id = f'{callee_id}.parameter.message'
    result = (
        ResultBinding(
            symbol_id=f'{function_id}.symbol.result',
            display_name='结果',
            value_type='string',
        )
        if return_type == 'null' else None
    )
    statements = [CallStatement(
        statement_id=f'{function_id}.statement.call',
        function_id=callee_id,
        arguments={argument_id: StringValue(
            value_id=f'{function_id}.value.argument', value='你好',
        )},
        result_binding=result,
    )]
    if return_type != 'null':
        statements.append(ReturnStatement(
            statement_id=f'{function_id}.statement.return',
            value=StringValue(value_id=f'{function_id}.value.return', value='完成'),
        ))
    return ProgramDocument(
        document_id=f'document.{function_id}',
        function=ProgramFunction(
            function_id=function_id,
            display_name=function_id,
            parameters=((_parameter(function_id),) if return_type != 'null' else ()),
            return_type=return_type,
            statements=tuple(statements),
        ),
    )


def test_linker_builds_main_helper_closure_with_stable_call_contract() -> None:
    helper = _helper()
    main = _caller('project.main', 'project.helper')
    first = compile_program_bundle(
        [helper, main], official_function_registry_v6,
        entry_function_id='project.main',
    )
    second = compile_program_bundle(
        [main, helper], official_function_registry_v6,
        entry_function_id='project.main',
    )
    assert first['valid'] is True
    assert first['ecir_revision'] == second['ecir_revision']
    assert first['ecir']['pure_operation_registry'] == {
        'registry_version': pure_operation_registry_payload()['registry_version'],
        'content_hash': pure_operation_registry_hash(),
    }
    assert [item['function_id'] for item in first['ecir']['functions']] == [
        'project.main', 'project.helper',
    ]
    call = first['ecir']['functions'][0]['instructions'][0]
    assert call['opcode'] == 'call.project'
    assert call['callee_function_id'] == 'project.helper'
    assert set(call['arguments']) == {'project.helper.parameter.message'}
    assert call['result_slot'] == 'project.main.symbol.result'


def test_linker_resolves_two_levels_and_omits_unreachable_documents() -> None:
    leaf = _helper('project.leaf')
    middle = _caller('project.middle', 'project.leaf', return_type='string')
    main = _caller('project.main', 'project.middle')
    unused = _helper('project.unused')
    result = compile_program_bundle(
        [unused, leaf, main, middle], official_function_registry_v6,
        entry_function_id='project.main',
    )
    assert result['valid'] is True
    assert [item['function_id'] for item in result['ecir']['functions']] == [
        'project.main', 'project.middle', 'project.leaf',
    ]
    assert result['ecir']['functions'][1]['instructions'][0]['callee_function_id'] == (
        'project.leaf'
    )


def test_linker_reports_missing_function_at_call_statement() -> None:
    main = _caller('project.main', 'project.missing')
    result = compile_program_bundle(
        [main], official_function_registry_v6, entry_function_id='project.main',
    )
    assert result['valid'] is False
    diagnostic = next(item for item in result['diagnostics'] if item['code'] == 'PGM-LINK-005')
    assert diagnostic['statement_id'] == 'project.main.statement.call'
    assert diagnostic['field_path'] == 'function_id'


def test_linker_rejects_project_call_cycles() -> None:
    first = _caller('project.first', 'project.second')
    second = _caller('project.second', 'project.first')
    result = compile_program_bundle(
        [first, second], official_function_registry_v6,
        entry_function_id='project.first',
    )
    assert result['valid'] is False
    diagnostic = next(item for item in result['diagnostics'] if item['code'] == 'PGM-LINK-006')
    assert diagnostic['function_id'] == 'project.second'
    assert diagnostic['statement_id'] == 'project.second.statement.call'


def test_linker_reports_signature_and_cross_document_id_errors() -> None:
    helper = _helper()
    bad_main = ProgramDocument(
        document_id='document.project.main',
        function=ProgramFunction(
            function_id='project.main',
            display_name='主程序',
            statements=(CallStatement(
                statement_id='shared.statement',
                function_id='project.helper',
                arguments={'project.helper.parameter.message': StringValue(
                    value_id='shared.value', value='消息',
                )},
                result_binding=ResultBinding(
                    symbol_id='main.result', display_name='结果', value_type='int64',
                ),
            ),),
        ),
    )
    helper_with_collision = helper.model_copy(update={
        'function': helper.function.model_copy(update={
            'statements': (
                helper.function.statements[0].model_copy(update={
                    'statement_id': 'shared.statement',
                }),
                helper.function.statements[1],
            ),
        }),
    })
    result = compile_program_bundle(
        [bad_main, helper_with_collision], official_function_registry_v6,
        entry_function_id='project.main',
    )
    assert result['valid'] is False
    assert {item['code'] for item in result['diagnostics']} >= {'PGM-LINK-004'}

    signature_only = compile_program_bundle(
        [bad_main, helper], official_function_registry_v6,
        entry_function_id='project.main',
    )
    assert signature_only['valid'] is False
    assert any(item['code'] == 'PGM-CALL-005' for item in signature_only['diagnostics'])
