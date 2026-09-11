"""Semantics-preserving extraction of contiguous statements into a project function."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .program_types import ProgramDocument, new_stable_id


class ProgramExtractionError(ValueError):
    """The selected statements cannot be extracted without changing meaning."""


@dataclass(frozen=True, slots=True)
class ProgramExtractionResult:
    source: ProgramDocument
    extracted: ProgramDocument
    call_statement_id: str


def _child_blocks(statement: dict[str, Any]) -> list[list[dict[str, Any]]]:
    kind = statement.get('kind')
    if kind == 'if':
        return [
            statement.get('then_statements') or [],
            *[
                branch.get('statements') or []
                for branch in statement.get('additional_branches') or []
            ],
            statement.get('otherwise_statements') or [],
        ]
    if kind in {'loop', 'target_scope'}:
        return [statement.get('body') or []]
    if kind == 'try':
        return [
            statement.get('body') or [],
            *[clause.get('statements') or [] for clause in statement.get('catches') or []],
            statement.get('finally_statements') or [],
        ]
    return []


def _find_container(
    statements: list[dict[str, Any]],
    statement_id: str,
) -> tuple[list[dict[str, Any]], int] | None:
    for index, statement in enumerate(statements):
        if statement.get('statement_id') == statement_id:
            return statements, index
        for block in _child_blocks(statement):
            found = _find_container(block, statement_id)
            if found is not None:
                return found
    return None


def _walk_objects(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _walk_objects(item)
        return
    if not isinstance(value, dict):
        return
    yield value
    for item in value.values():
        yield from _walk_objects(item)


def _symbol_catalog(raw_document: dict[str, Any]) -> dict[str, tuple[str, str]]:
    catalog: dict[str, tuple[str, str]] = {}
    for parameter in raw_document['function'].get('parameters') or []:
        catalog[str(parameter['symbol_id'])] = (
            str(parameter['display_name']), str(parameter['value_type']),
        )
    for node in _walk_objects(raw_document['function'].get('statements') or []):
        candidates: list[dict[str, Any]] = []
        binding = node.get('result_binding')
        if isinstance(binding, dict) and binding.get('declare', True):
            candidates.append(binding)
        target = node.get('target')
        if (
            node.get('kind') == 'assignment'
            and isinstance(target, dict)
            and target.get('kind') == 'local'
            and target.get('declare', True)
        ):
            candidates.append(target)
        for name in (
            'item_binding', 'index_binding', 'key_binding', 'value_binding',
            'error_binding', 'receive_binding',
        ):
            candidate = node.get(name)
            if isinstance(candidate, dict):
                candidates.append(candidate)
        if node.get('kind') == 'selector':
            candidates.extend(
                item for item in node.get('bindings') or [] if isinstance(item, dict)
            )
        for candidate in candidates:
            symbol_id = str(candidate.get('symbol_id') or '')
            if symbol_id:
                catalog[symbol_id] = (
                    str(candidate.get('display_name') or '输入值'),
                    str(candidate.get('value_type') or 'any'),
                )
    return catalog


def _declared_symbols(statements: list[dict[str, Any]]) -> set[str]:
    wrapper = {'function': {'parameters': [], 'statements': statements}}
    return set(_symbol_catalog(wrapper))


def _referenced_symbols(value: Any) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for node in _walk_objects(value):
        if node.get('kind') != 'symbol_ref':
            continue
        symbol_id = str(node.get('symbol_id') or '')
        if symbol_id and symbol_id not in seen:
            seen.add(symbol_id)
            result.append((symbol_id, str(node.get('value_type') or 'any')))
    return result


def _assert_control_flow_is_self_contained(
    statements: list[dict[str, Any]],
    *,
    loop_depth: int = 0,
) -> None:
    for statement in statements:
        kind = statement.get('kind')
        if kind == 'return':
            raise ProgramExtractionError('所选语句包含“返回”，提取后会改变原函数的结束位置')
        if kind in {'break', 'continue'} and loop_depth == 0:
            raise ProgramExtractionError('所选语句依赖外层循环，不能单独提取为项目函数')
        child_depth = loop_depth + 1 if kind == 'loop' else loop_depth
        for block in _child_blocks(statement):
            _assert_control_flow_is_self_contained(block, loop_depth=child_depth)


def _assert_no_outer_local_mutation(
    statements: list[dict[str, Any]],
    internal_symbols: set[str],
) -> None:
    for node in _walk_objects(statements):
        target = node.get('target')
        if (
            node.get('kind') == 'assignment'
            and isinstance(target, dict)
            and target.get('kind') == 'local'
            and not target.get('declare', True)
            and str(target.get('symbol_id') or '') not in internal_symbols
        ):
            raise ProgramExtractionError('所选语句会修改外部局部变量，当前不能无损提取')
        binding = node.get('result_binding')
        if (
            isinstance(binding, dict)
            and not binding.get('declare', True)
            and str(binding.get('symbol_id') or '') not in internal_symbols
        ):
            raise ProgramExtractionError('所选调用会覆盖外部局部变量，当前不能无损提取')


def extract_contiguous_statements(
    document: ProgramDocument,
    statement_ids: list[str] | tuple[str, ...],
    display_name: str,
) -> ProgramExtractionResult:
    """Create a new function and replace one contiguous selection with its call.

    External local values become typed parameters.  At most one local value may
    escape the selection; it becomes the extracted function's return value.
    Project variables, assets and targets remain stable references.
    """

    normalized_name = str(display_name or '').strip()
    if not normalized_name:
        raise ProgramExtractionError('项目函数名称不能为空')
    selected_ids = [str(item) for item in statement_ids if str(item)]
    if not selected_ids or len(set(selected_ids)) != len(selected_ids):
        raise ProgramExtractionError('请选择一条或多条不重复的语句')

    raw = document.model_dump(mode='json')
    located = [_find_container(raw['function']['statements'], item) for item in selected_ids]
    if any(item is None for item in located):
        raise ProgramExtractionError('选择中包含已经不存在的语句')
    first_container = located[0][0]  # type: ignore[index]
    if any(item[0] is not first_container for item in located if item is not None):
        raise ProgramExtractionError('只能提取同一语句块中的连续语句')
    indexes = sorted(item[1] for item in located if item is not None)
    if indexes != list(range(indexes[0], indexes[-1] + 1)):
        raise ProgramExtractionError('只能提取同一语句块中的连续语句')
    ordered_ids = [str(first_container[index]['statement_id']) for index in indexes]
    if set(ordered_ids) != set(selected_ids):
        raise ProgramExtractionError('选择中夹有未选语句，请补全连续范围')

    selected = copy.deepcopy(first_container[indexes[0]:indexes[-1] + 1])
    _assert_control_flow_is_self_contained(selected)
    catalog = _symbol_catalog(raw)
    internal_symbols = _declared_symbols(selected)
    _assert_no_outer_local_mutation(selected, internal_symbols)

    external_references = [
        (symbol_id, value_type)
        for symbol_id, value_type in _referenced_symbols(selected)
        if symbol_id not in internal_symbols
    ]
    for symbol_id, _ in external_references:
        if symbol_id not in catalog:
            raise ProgramExtractionError(f'无法确定外部局部值：{symbol_id}')

    remaining = copy.deepcopy(raw['function']['statements'])
    remaining_location = _find_container(remaining, ordered_ids[0])
    assert remaining_location is not None
    remaining_container, remaining_start = remaining_location
    del remaining_container[remaining_start:remaining_start + len(selected)]
    outside_references = {symbol_id for symbol_id, _ in _referenced_symbols(remaining)}
    outputs = sorted(internal_symbols.intersection(outside_references))
    if len(outputs) > 1:
        names = '、'.join(catalog[item][0] for item in outputs)
        raise ProgramExtractionError(f'所选语句向后提供多个局部值（{names}），请缩小范围或先组合为一个值')

    internal_map = {symbol_id: new_stable_id('symbol') for symbol_id in internal_symbols}
    parameter_map: dict[str, tuple[str, str, str, str]] = {}
    parameters: list[dict[str, Any]] = []
    for symbol_id, referenced_type in external_references:
        display, declared_type = catalog[symbol_id]
        value_type = declared_type or referenced_type
        parameter_id = new_stable_id('param')
        parameter_symbol = new_stable_id('symbol')
        parameter_map[symbol_id] = (parameter_id, parameter_symbol, display, value_type)
        parameters.append({
            'parameter_id': parameter_id,
            'symbol_id': parameter_symbol,
            'display_name': display,
            'value_type': value_type,
            'required': True,
            'default_value': None,
        })

    id_keys = {
        'statement_id': 'stmt', 'value_id': 'value',
        'branch_id': 'branch', 'catch_id': 'catch',
    }

    def clone(node: Any) -> Any:
        if isinstance(node, list):
            return [clone(item) for item in node]
        if not isinstance(node, dict):
            return copy.deepcopy(node)
        copied: dict[str, Any] = {}
        for key, item in node.items():
            if key in id_keys:
                copied[key] = new_stable_id(id_keys[key])
            elif key == 'symbol_id' and str(item) in internal_map:
                copied[key] = internal_map[str(item)]
            elif key == 'symbol_id' and str(item) in parameter_map:
                copied[key] = parameter_map[str(item)][1]
            else:
                copied[key] = clone(item)
        return copied

    extracted_statements = clone(selected)
    output_id = outputs[0] if outputs else ''
    return_type = catalog[output_id][1] if output_id else 'null'
    if output_id:
        extracted_statements.append({
            'statement_id': new_stable_id('stmt'),
            'kind': 'return',
            'value': {
                'value_id': new_stable_id('value'),
                'kind': 'symbol_ref',
                'symbol_id': internal_map[output_id],
                'value_type': return_type,
            },
            'step_label': None,
        })

    extracted_function_id = new_stable_id('func')
    extracted_raw = {
        'schema_version': raw['schema_version'],
        'document_id': new_stable_id('doc'),
        'function': {
            'function_id': extracted_function_id,
            'display_name': normalized_name,
            'parameters': parameters,
            'return_type': return_type,
            'statements': extracted_statements,
        },
    }

    call_statement_id = new_stable_id('stmt')
    call_arguments = {
        parameter_id: {
            'value_id': new_stable_id('value'),
            'kind': 'symbol_ref',
            'symbol_id': source_symbol,
            'value_type': value_type,
        }
        for source_symbol, (parameter_id, _parameter_symbol, _display, value_type)
        in parameter_map.items()
    }
    call: dict[str, Any] = {
        'statement_id': call_statement_id,
        'kind': 'call',
        'function_id': extracted_function_id,
        'arguments': call_arguments,
        'result_binding': None,
        'step_label': None,
        'author_review_fingerprint': None,
    }
    if output_id:
        output_name, output_type = catalog[output_id]
        call['result_binding'] = {
            'symbol_id': output_id,
            'display_name': output_name,
            'value_type': output_type,
            'declare': True,
        }
    remaining_container.insert(remaining_start, call)
    source_raw = copy.deepcopy(raw)
    source_raw['function']['statements'] = remaining

    try:
        extracted = ProgramDocument.model_validate(extracted_raw)
        source = ProgramDocument.model_validate(source_raw)
    except ValueError as exc:
        raise ProgramExtractionError(f'提取后的结构无效：{exc}') from exc
    return ProgramExtractionResult(source, extracted, call_statement_id)


__all__ = [
    'ProgramExtractionError', 'ProgramExtractionResult', 'extract_contiguous_statements',
]
