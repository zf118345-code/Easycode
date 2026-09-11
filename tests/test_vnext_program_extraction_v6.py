from __future__ import annotations

import pytest

from core.vnext.program_extraction_v6 import (
    ProgramExtractionError,
    extract_contiguous_statements,
)
from core.vnext.program_types import ProgramDocument


def _document(statements: list[dict], *, parameters: list[dict] | None = None) -> ProgramDocument:
    return ProgramDocument.model_validate({
        'schema_version': 1,
        'document_id': 'doc_main',
        'function': {
            'function_id': 'func_main',
            'display_name': '主流程',
            'parameters': parameters or [],
            'return_type': 'null',
            'statements': statements,
        },
    })


def _int(value_id: str, value: int) -> dict:
    return {'value_id': value_id, 'kind': 'int64', 'value': value}


def _symbol(value_id: str, symbol_id: str, value_type: str = 'int64') -> dict:
    return {
        'value_id': value_id,
        'kind': 'symbol_ref',
        'symbol_id': symbol_id,
        'value_type': value_type,
    }


def _assignment(statement_id: str, symbol_id: str, name: str, value: dict) -> dict:
    return {
        'statement_id': statement_id,
        'kind': 'assignment',
        'target': {
            'kind': 'local', 'symbol_id': symbol_id,
            'display_name': name, 'value_type': 'int64', 'declare': True,
        },
        'value': value,
        'step_label': None,
    }


def test_extract_lifts_external_input_and_returns_one_escaping_value() -> None:
    document = _document([
        _assignment('stmt_before', 'symbol_input', '基础值', _int('value_one', 1)),
        _assignment('stmt_selected', 'symbol_output', '计算结果', _symbol('value_input_ref', 'symbol_input')),
        {
            'statement_id': 'stmt_after',
            'kind': 'return',
            'value': _symbol('value_output_ref', 'symbol_output'),
            'step_label': None,
        },
    ])

    result = extract_contiguous_statements(document, ['stmt_selected'], '计算片段')

    extracted = result.extracted.function
    assert extracted.display_name == '计算片段'
    assert extracted.return_type == 'int64'
    assert len(extracted.parameters) == 1
    assert extracted.parameters[0].display_name == '基础值'
    assert extracted.parameters[0].symbol_id != 'symbol_input'
    assert extracted.statements[0].statement_id != 'stmt_selected'
    assert extracted.statements[-1].kind == 'return'

    source = result.source.function.statements
    assert [item.kind for item in source] == ['assignment', 'call', 'return']
    call = source[1]
    assert call.function_id == extracted.function_id
    assert call.result_binding is not None
    assert call.result_binding.symbol_id == 'symbol_output'
    assert next(iter(call.arguments.values())).symbol_id == 'symbol_input'


def test_extract_rejects_non_contiguous_selection() -> None:
    document = _document([
        _assignment('stmt_a', 'symbol_a', '甲', _int('value_a', 1)),
        _assignment('stmt_b', 'symbol_b', '乙', _int('value_b', 2)),
        _assignment('stmt_c', 'symbol_c', '丙', _int('value_c', 3)),
    ])
    with pytest.raises(ProgramExtractionError, match='连续'):
        extract_contiguous_statements(document, ['stmt_a', 'stmt_c'], '片段')


def test_extract_rejects_control_flow_that_depends_on_outer_loop() -> None:
    document = _document([{
        'statement_id': 'stmt_loop',
        'kind': 'loop',
        'mode': 'repeat',
        'source': _int('value_count', 2),
        'body': [{'statement_id': 'stmt_break', 'kind': 'break', 'step_label': None}],
        'item_binding': None,
        'index_binding': None,
        'key_binding': None,
        'value_binding': None,
        'step_label': None,
    }])
    with pytest.raises(ProgramExtractionError, match='外层循环'):
        extract_contiguous_statements(document, ['stmt_break'], '错误片段')

    result = extract_contiguous_statements(document, ['stmt_loop'], '完整循环')
    assert result.extracted.function.statements[0].kind == 'loop'


def test_extract_rejects_more_than_one_escaping_local() -> None:
    document = _document([
        _assignment('stmt_a', 'symbol_a', '甲', _int('value_a', 1)),
        _assignment('stmt_b', 'symbol_b', '乙', _int('value_b', 2)),
        {
            'statement_id': 'stmt_use',
            'kind': 'if',
            'condition': {
                'value_id': 'value_condition', 'kind': 'compare', 'operator': 'lt',
                'left': _symbol('value_a_ref', 'symbol_a'),
                'right': _symbol('value_b_ref', 'symbol_b'),
            },
            'then_statements': [], 'additional_branches': [], 'otherwise_statements': [],
            'step_label': None,
        },
    ])
    with pytest.raises(ProgramExtractionError, match='多个局部值'):
        extract_contiguous_statements(document, ['stmt_a', 'stmt_b'], '两个结果')
