"""Semantic, reference, scope, and contract validation for ProgramDocument."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass

from .program_contracts import FunctionContractProvider, get_contract, parameter_display_name
from .program_serialization import canonical_json_bytes, content_revision
from .program_types import (
    AssignmentStatement,
    BreakStatement,
    CallStatement,
    ComparisonValue,
    ConditionGroupValue,
    ContinueStatement,
    FailStatement,
    IfStatement,
    IntValue,
    ListenStatement,
    ListValue,
    LocalAssignmentTarget,
    LoopStatement,
    MapValue,
    MemberAccessValue,
    NotValue,
    NullValue,
    ProgramDocument,
    PureOperationValue,
    RecordValue,
    ReturnStatement,
    SelectorValue,
    Statement,
    StringValue,
    SymbolReferenceValue,
    TargetScopeStatement,
    TryStatement,
    UnsetValue,
    ValueNode,
    iter_value_children,
    statement_child_blocks,
    value_type,
)
from .pure_operations_v6 import (
    OPERATION_INPUT_NAMES,
    pure_operation_state,
    pure_operation_type_issues,
)
from .record_types_v6 import record_type_contract


def retry_review_fingerprint(
    statement: TryStatement,
    registry: FunctionContractProvider | None,
) -> str:
    """Bind a retry review to its exact body and locked function contracts."""

    contracts: dict[str, str] = {}
    for child in iter_statement_tree(statement.body):
        if not isinstance(child, CallStatement):
            continue
        contract = get_contract(registry, child.function_id) if registry is not None else None
        if contract is None:
            contracts[child.function_id] = 'unresolved'
            continue
        fingerprint = getattr(contract, 'contract_fingerprint', '')
        fingerprint_method = getattr(contract, 'fingerprint', None)
        if not fingerprint and callable(fingerprint_method):
            fingerprint = fingerprint_method()
        contracts[child.function_id] = str(fingerprint or contract.contract_version)
    return content_revision(canonical_json_bytes({
        'statement_id': statement.statement_id,
        'body': [item.model_dump(mode='json') for item in statement.body],
        'contracts': contracts,
    }))


def dangerous_call_review_fingerprint(
    statement: CallStatement,
    registry: FunctionContractProvider | None,
) -> str:
    """Bind an author review to one dangerous call and its exact value tree."""

    contract = get_contract(registry, statement.function_id) if registry is not None else None
    if contract is None or not bool(getattr(contract, 'dangerous', False)):
        raise ValueError('call is not a resolved dangerous function')
    fingerprint = str(getattr(contract, 'contract_fingerprint', '') or '')
    fingerprint_method = getattr(contract, 'fingerprint', None)
    if not fingerprint and callable(fingerprint_method):
        fingerprint = str(fingerprint_method())
    return content_revision(canonical_json_bytes({
        'statement_id': statement.statement_id,
        'function_id': statement.function_id,
        'arguments': {
            key: value.model_dump(mode='json')
            for key, value in sorted(statement.arguments.items())
        },
        'contract_fingerprint': fingerprint or str(contract.contract_version),
        'permission_contract': tuple(getattr(contract, 'permissions', ()) or ()),
    }))


def retry_body_has_side_effects(
    statement: TryStatement,
    registry: FunctionContractProvider | None,
) -> bool:
    """Return whether the retry body calls a contract with declared side effects."""

    if registry is None:
        return False
    for child in iter_statement_tree(statement.body):
        if not isinstance(child, CallStatement):
            continue
        contract = get_contract(registry, child.function_id)
        if contract is not None and getattr(contract, 'side_effects', ()):
            return True
    return False


@dataclass(frozen=True, slots=True)
class ProgramDiagnostic:
    code: str
    severity: str
    message: str
    function_id: str
    statement_id: str = ''
    value_id: str = ''
    field_path: str = ''

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def iter_statement_tree(statements: Iterable[Statement]) -> Iterator[Statement]:
    for statement in statements:
        yield statement
        for block in statement_child_blocks(statement):
            yield from iter_statement_tree(block)


def iter_statement_values(statement: Statement) -> Iterator[ValueNode]:
    roots: list[ValueNode] = []
    if isinstance(statement, CallStatement):
        roots.extend(statement.arguments.values())
    elif isinstance(statement, AssignmentStatement):
        roots.append(statement.value)
    elif isinstance(statement, IfStatement):
        roots.append(statement.condition)
        roots.extend(branch.condition for branch in statement.additional_branches)
    elif isinstance(statement, LoopStatement):
        roots.append(statement.source)
    elif isinstance(statement, ReturnStatement) and statement.value is not None:
        roots.append(statement.value)
    elif isinstance(statement, FailStatement):
        roots.append(statement.message)
        if statement.details is not None:
            roots.append(statement.details)
    elif isinstance(statement, TryStatement) and statement.retry_policy is not None:
        roots.extend((statement.retry_policy.max_retries, statement.retry_policy.interval))
    elif isinstance(statement, TargetScopeStatement):
        roots.append(statement.target)
    elif isinstance(statement, ListenStatement):
        roots.append(statement.event_source.name)
        if statement.event_source.sender is not None:
            roots.append(statement.event_source.sender)
        if statement.condition is not None:
            roots.append(statement.condition)
        roots.extend(statement.handler_arguments.values())

    def visit(value: ValueNode) -> Iterator[ValueNode]:
        yield value
        for child in iter_value_children(value):
            yield from visit(child)

    for root in roots:
        yield from visit(root)


def _generic_inner(type_id: str, prefix: str) -> str | None:
    marker = f'{prefix}<'
    return type_id[len(marker):-1] if type_id.startswith(marker) and type_id.endswith('>') else None


def _map_types(type_id: str) -> tuple[str, str] | None:
    inner = _generic_inner(type_id, 'map')
    if inner is None or ',' not in inner:
        return None
    left, right = inner.split(',', 1)
    return left, right


def _record_contract_type_id(type_id: str) -> str:
    if type_id.startswith('record<') and type_id.endswith('>'):
        return type_id[7:-1]
    if type_id.startswith('record.'):
        return type_id[7:]
    return type_id


def types_compatible(actual: str, expected: str) -> bool:
    """Return whether a typed value can be assigned to ``expected``.

    This is the single compatibility rule used by ProgramDocument validation,
    project-variable defaults, Player overrides, and Runtime argument checks.
    Keeping it public prevents those vertical slices from slowly inventing
    subtly different type systems.
    """

    if expected == 'any' or actual == expected:
        return True
    if expected == 'message_value':
        if actual in {
            'null', 'bool', 'int64', 'float64', 'string',
            'json', 'json_value', 'message_value',
        }:
            return True
        list_item = _generic_inner(actual, 'list')
        if list_item is not None:
            return types_compatible(list_item, 'message_value')
        map_types = _map_types(actual)
        if map_types is not None:
            key_type, item_type = map_types
            return key_type == 'string' and types_compatible(item_type, 'message_value')
        return False
    if expected.startswith('enum<') and actual == 'string':
        return True
    # ProgramDocument stores captured drag gestures in the single structural
    # PathValue representation. ``gesture_path`` is the public parameter type
    # used to distinguish an authored drag gesture from other path-like data.
    if expected == 'gesture_path' and actual == 'path':
        return True
    if expected == 'percentage' and actual in {'int64', 'float64'}:
        return True
    if expected in {'relative_path', 'url', 'timezone'} and actual == 'string':
        return True
    if expected.startswith('optional<'):
        return actual == 'null' or types_compatible(actual, expected[9:-1])
    if expected == 'asset_ref' and actual.startswith('asset_ref<'):
        return True
    return expected == 'float64' and actual == 'int64'


_compatible = types_compatible


def _ordered_comparable(type_id: str) -> bool:
    return type_id in {'int64', 'float64', 'string', 'date', 'datetime', 'time', 'duration'}


def narrowed_optional_symbols(condition: ValueNode) -> set[str]:
    if (
        isinstance(condition, PureOperationValue)
        and condition.operation_id == 'core.optional_has_value.v1'
    ):
        return {
            value.symbol_id
            for value in condition.inputs.values()
            if isinstance(value, SymbolReferenceValue)
        }
    if isinstance(condition, ComparisonValue) and condition.operator in {'ne', 'eq'}:
        values = (condition.left, condition.right)
        symbol = next((item for item in values if isinstance(item, SymbolReferenceValue)), None)
        has_null = any(isinstance(item, NullValue) for item in values)
        if symbol is not None and has_null and condition.operator == 'ne':
            return {symbol.symbol_id}
    if isinstance(condition, ConditionGroupValue) and condition.operator == 'all':
        return set().union(*(narrowed_optional_symbols(item) for item in condition.conditions))
    return set()


# Backward-compatible private alias for older internal call sites.  New
# catalog/scope code imports the public helper so optional narrowing has one
# authoritative implementation.
_narrowed_optional_symbols = narrowed_optional_symbols


def validate_program_document(
    document: ProgramDocument,
    registry: FunctionContractProvider | None = None,
    *,
    require_configured: bool = False,
) -> tuple[ProgramDiagnostic, ...]:
    """Validate types, lexical scope, references, and compile boundaries."""

    diagnostics: list[ProgramDiagnostic] = []
    function_id = document.function.function_id
    initial_symbols = {item.symbol_id: item.value_type for item in document.function.parameters}
    narrowed_paths: dict[str, frozenset[str]] = {}

    def diagnostic(
        code: str,
        message: str,
        *,
        statement_id: str = '',
        value_id: str = '',
        field_path: str = '',
    ) -> None:
        diagnostics.append(ProgramDiagnostic(
            code=code,
            severity='error',
            message=message,
            function_id=function_id,
            statement_id=statement_id,
            value_id=value_id,
            field_path=field_path,
        ))

    def validate_value(
        value: ValueNode,
        available_symbols: dict[str, str],
        *,
        statement_id: str,
        field_path: str,
        expected_type: str | None = None,
        narrowed_symbols: frozenset[str] = frozenset(),
        selector_allowed: bool = False,
    ) -> None:
        path_narrowed = set(narrowed_symbols)
        for prefix, symbols in narrowed_paths.items():
            if field_path.startswith(prefix):
                path_narrowed.update(symbols)
        narrowed_symbols = frozenset(path_narrowed)
        actual = value_type(value)
        if isinstance(value, SymbolReferenceValue):
            symbol_type = available_symbols.get(value.symbol_id)
            if symbol_type is None:
                diagnostic(
                    'PGM-REF-001',
                    f'局部变量引用不存在或不在当前作用域：{value.symbol_id}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            elif not _compatible(symbol_type, value.value_type):
                diagnostic(
                    'PGM-REF-002',
                    f'局部变量声明为 {symbol_type}，引用却声明为 {value.value_type}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
        if isinstance(value, SelectorValue):
            if not selector_allowed:
                diagnostic(
                    'PGM-SELECTOR-001',
                    '逐项选择器只能用于集合纯值操作的筛选、转换或依据输入',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            if not _compatible(value_type(value.expression), value.result_type):
                diagnostic(
                    'PGM-SELECTOR-002',
                    f'逐项计算声明返回 {value.result_type}，实际为 {value_type(value.expression)}',
                    statement_id=statement_id,
                    value_id=value.expression.value_id,
                    field_path=f'{field_path}.expression',
                )
            selector_symbols = dict(available_symbols)
            for binding in value.bindings:
                selector_symbols[binding.symbol_id] = binding.value_type
            validate_value(
                value.expression,
                selector_symbols,
                statement_id=statement_id,
                field_path=f'{field_path}.expression',
                expected_type=value.result_type,
                narrowed_symbols=narrowed_symbols,
            )
        if isinstance(value, UnsetValue) and require_configured:
            diagnostic(
                'PGM-VALUE-001',
                '必填值尚未配置',
                statement_id=statement_id,
                value_id=value.value_id,
                field_path=field_path,
            )
        if isinstance(value, MemberAccessValue):
            source_type = value_type(value.source)
            if source_type.startswith(('map<', 'list<')) or source_type == 'json_value':
                diagnostic(
                    'PGM-MEMBER-001',
                    '动态字典、列表或 JSON 不能伪装成命名记录成员',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            record_type = source_type[9:-1] if source_type.startswith('optional<') and source_type.endswith('>') else source_type
            record_type = _record_contract_type_id(record_type)
            contract = record_type_contract(record_type)
            field = next((item for item in contract.fields if item.field_id == value.field_id), None) if contract else None
            if contract is None:
                diagnostic(
                    'PGM-MEMBER-002',
                    f'类型 {record_type} 没有已注册的命名字段契约',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            elif field is None:
                diagnostic(
                    'PGM-MEMBER-003',
                    f'字段不属于 {contract.display_name}：{value.field_id}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            elif not _compatible(field.value_type, value.result_type):
                diagnostic(
                    'PGM-MEMBER-004',
                    f'字段 {field.display_name} 应为 {field.value_type}，当前声明为 {value.result_type}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
        if isinstance(value, RecordValue):
            contract = record_type_contract(_record_contract_type_id(value.record_type))
            if contract is not None:
                known = {field.field_id: field for field in contract.fields}
                for field_id, child in value.fields.items():
                    field = known.get(field_id)
                    if field is None:
                        diagnostic(
                            'PGM-RECORD-001',
                            f'记录 {contract.display_name} 不包含字段：{field_id}',
                            statement_id=statement_id,
                            value_id=child.value_id,
                            field_path=f'{field_path}.fields.{field_id}',
                        )
                    elif not _compatible(value_type(child), field.value_type):
                        diagnostic(
                            'PGM-RECORD-002',
                            f'字段 {field.display_name} 需要 {field.value_type}，当前为 {value_type(child)}',
                            statement_id=statement_id,
                            value_id=child.value_id,
                            field_path=f'{field_path}.fields.{field_id}',
                        )
                for field_id, field in known.items():
                    if field_id not in value.fields and not field.value_type.startswith('optional<'):
                        diagnostic(
                            'PGM-RECORD-003',
                            f'记录 {contract.display_name} 缺少字段：{field.display_name}',
                            statement_id=statement_id,
                            value_id=value.value_id,
                            field_path=f'{field_path}.fields.{field_id}',
                        )
                def configured(field_id: str) -> bool:
                    child = value.fields.get(field_id)
                    if child is None or isinstance(child, (UnsetValue, NullValue)):
                        return False
                    if isinstance(child, StringValue):
                        return bool(child.value.strip())
                    return True

                if contract.required_any and not any(configured(item) for item in contract.required_any):
                    names = '、'.join(known[item].display_name for item in contract.required_any)
                    diagnostic(
                        'PGM-RECORD-004',
                        f'记录 {contract.display_name} 至少需要填写一项：{names}',
                        statement_id=statement_id,
                        value_id=value.value_id,
                        field_path=field_path,
                    )
                for field_id in contract.non_negative:
                    child = value.fields.get(field_id)
                    if isinstance(child, IntValue) and child.value < 0:
                        diagnostic(
                            'PGM-RECORD-005',
                            f'字段 {known[field_id].display_name} 不能为负数',
                            statement_id=statement_id,
                            value_id=child.value_id,
                            field_path=f'{field_path}.fields.{field_id}',
                        )
        if isinstance(value, ListValue):
            for index, item in enumerate(value.items):
                if not _compatible(value_type(item), value.item_type):
                    diagnostic(
                        'PGM-COLLECTION-001',
                        f'列表项需要 {value.item_type}，当前值为 {value_type(item)}',
                        statement_id=statement_id,
                        value_id=item.value_id,
                        field_path=f'{field_path}.items[{index}]',
                    )
        if isinstance(value, MapValue):
            allowed_keys = {'string', 'int64'}
            if value.key_type not in allowed_keys and not value.key_type.startswith(('enum<', 'ref<')):
                diagnostic(
                    'PGM-COLLECTION-002',
                    f'字典键类型不稳定：{value.key_type}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            for index, entry in enumerate(value.entries):
                if not _compatible(value_type(entry.key), value.key_type):
                    diagnostic(
                        'PGM-COLLECTION-003',
                        f'字典键需要 {value.key_type}，当前值为 {value_type(entry.key)}',
                        statement_id=statement_id,
                        value_id=entry.key.value_id,
                        field_path=f'{field_path}.entries[{index}].key',
                    )
                if not _compatible(value_type(entry.value), value.entry_value_type):
                    diagnostic(
                        'PGM-COLLECTION-004',
                        f'字典值需要 {value.entry_value_type}，当前值为 {value_type(entry.value)}',
                        statement_id=statement_id,
                        value_id=entry.value.value_id,
                        field_path=f'{field_path}.entries[{index}].value',
                    )
        if isinstance(value, PureOperationValue):
            operation_state = pure_operation_state(value.operation_id)
            if operation_state == 'unknown':
                diagnostic(
                    'PGM-OP-001',
                    f'纯值操作不属于核心注册表：{value.operation_id}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            elif operation_state == 'planned' and require_configured:
                diagnostic(
                    'PGM-OP-002',
                    f'纯值操作尚未形成可执行闭环：{value.operation_id}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
            elif operation_state == 'verified':
                expected_inputs = {
                    f'{value.operation_id}.input.{name}'
                    for name in OPERATION_INPUT_NAMES[value.operation_id]
                }
                actual_inputs = set(value.inputs)
                if actual_inputs != expected_inputs:
                    missing = sorted(expected_inputs - actual_inputs)
                    unknown = sorted(actual_inputs - expected_inputs)
                    diagnostic(
                        'PGM-OP-003',
                        f'纯值操作输入不匹配；缺少={missing}，未知={unknown}',
                        statement_id=statement_id,
                        value_id=value.value_id,
                        field_path=f'{field_path}.inputs',
                    )
                for issue in pure_operation_type_issues(
                    value.operation_id,
                    value.result_type,
                    {key: value_type(item) for key, item in value.inputs.items()},
                ):
                    diagnostic(
                        'PGM-OP-004',
                        f'纯值操作类型不匹配：{issue}',
                        statement_id=statement_id,
                        value_id=value.value_id,
                        field_path=field_path,
                    )
                for input_id, child in value.inputs.items():
                    if not isinstance(child, SelectorValue):
                        continue
                    expected_roles = (
                        {'item', 'index'} if value.operation_id.startswith('core.list_')
                        else {'key', 'value'} if value.operation_id.startswith('core.map_')
                        else set()
                    )
                    actual_roles = {binding.role for binding in child.bindings}
                    if actual_roles != expected_roles:
                        diagnostic(
                            'PGM-SELECTOR-003',
                            '列表选择器需要“当前项/当前序号”，字典选择器需要“当前键/当前值”',
                            statement_id=statement_id,
                            value_id=child.value_id,
                            field_path=f'{field_path}.inputs.{input_id}',
                        )
        if isinstance(value, ComparisonValue):
            left_type = value_type(value.left)
            right_type = value_type(value.right)
            compatible = (
                _compatible(left_type, right_type)
                or _compatible(right_type, left_type)
                or (
                    'null' in {left_type, right_type}
                    and any(item.startswith('optional<') for item in (left_type, right_type))
                )
            )
            if not compatible or (
                value.operator not in {'eq', 'ne'} and not _ordered_comparable(left_type)
            ):
                diagnostic(
                    'PGM-CONDITION-002',
                    f'不能用 {value.operator} 比较 {left_type} 与 {right_type}',
                    statement_id=statement_id,
                    value_id=value.value_id,
                    field_path=field_path,
                )
        if isinstance(value, (ConditionGroupValue, NotValue)):
            for child in iter_value_children(value):
                if value_type(child) != 'bool':
                    diagnostic(
                        'PGM-CONDITION-003',
                        f'条件组合只接受 bool，当前值为 {value_type(child)}',
                        statement_id=statement_id,
                        value_id=child.value_id,
                        field_path=field_path,
                    )
        children = iter_value_children(value)
        if isinstance(value, SelectorValue):
            children = ()
        for index, child in enumerate(children):
            selector_input = False
            child_path = f'{field_path}.value[{index}]'
            if isinstance(value, PureOperationValue):
                input_items = tuple(value.inputs.items())
                if index < len(input_items):
                    input_id, _ = input_items[index]
                    selector_input = input_id.endswith(('.input.predicate', '.input.transform', '.input.key_selector'))
                    child_path = f'{field_path}.inputs.{input_id}'
            validate_value(
                child,
                available_symbols,
                statement_id=statement_id,
                field_path=child_path,
                narrowed_symbols=narrowed_symbols,
                selector_allowed=selector_input,
            )
        if expected_type is not None and not _compatible(actual, expected_type):
            diagnostic(
                'PGM-TYPE-001',
                f'参数需要 {expected_type}，当前值为 {actual}',
                statement_id=statement_id,
                value_id=value.value_id,
                field_path=field_path,
            )

    def declare_symbol(
        symbols: dict[str, str],
        symbol_id: str,
        symbol_type: str,
        *,
        statement_id: str,
        field_path: str,
    ) -> None:
        if symbol_id in symbols:
            diagnostic(
                'PGM-SYMBOL-001',
                f'局部变量已在当前作用域声明：{symbol_id}',
                statement_id=statement_id,
                field_path=field_path,
            )
        else:
            symbols[symbol_id] = symbol_type

    def require_assignment_target(
        symbols: dict[str, str],
        symbol_id: str,
        target_type: str,
        declare: bool,
        *,
        statement_id: str,
        field_path: str,
    ) -> None:
        if declare:
            declare_symbol(
                symbols,
                symbol_id,
                target_type,
                statement_id=statement_id,
                field_path=field_path,
            )
            return
        existing = symbols.get(symbol_id)
        if existing is None:
            diagnostic(
                'PGM-REF-003',
                f'赋值目标局部变量不存在：{symbol_id}',
                statement_id=statement_id,
                field_path=field_path,
            )
        elif not _compatible(target_type, existing):
            diagnostic(
                'PGM-TYPE-002',
                f'赋值目标为 {existing}，当前绑定声明为 {target_type}',
                statement_id=statement_id,
                field_path=field_path,
            )

    def validate_block(
        statements: Iterable[Statement],
        available_symbols: dict[str, str],
        block_path: str,
        loop_depth: int = 0,
    ) -> dict[str, str]:
        current_symbols = dict(available_symbols)
        for index, statement in enumerate(statements):
            statement_path = f'{block_path}[{index}]'
            statement_id = statement.statement_id
            if isinstance(statement, CallStatement):
                contract = get_contract(registry, statement.function_id) if registry is not None else None
                if registry is not None and contract is None:
                    diagnostic(
                        'PGM-CALL-001',
                        f'函数契约不存在：{statement.function_id}',
                        statement_id=statement_id,
                        field_path=f'{statement_path}.function_id',
                    )
                parameters = {
                    item.parameter_id: item for item in (contract.parameters if contract is not None else ())
                }
                if contract is not None:
                    for parameter_id in statement.arguments:
                        if parameter_id not in parameters:
                            diagnostic(
                                'PGM-CALL-002',
                                f'函数契约不存在参数：{parameter_id}',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.arguments.{parameter_id}',
                            )
                    for parameter in contract.parameters:
                        if parameter.required and parameter.parameter_id not in statement.arguments:
                            diagnostic(
                                'PGM-CALL-003',
                                f'缺少必填参数：{parameter_display_name(parameter)}',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.arguments.{parameter.parameter_id}',
                            )
                    if bool(getattr(contract, 'dangerous', False)):
                        expected_review = dangerous_call_review_fingerprint(
                            statement, registry,
                        )
                        if statement.author_review_fingerprint != expected_review:
                            diagnostic(
                                'PGM-DANGER-001',
                                '危险调用需要作者审核；调用、参数、权限或函数契约变化后必须重新审核',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.author_review_fingerprint',
                            )
                for parameter_id, value in statement.arguments.items():
                    parameter = parameters.get(parameter_id)
                    validate_value(
                        value,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.arguments.{parameter_id}',
                        expected_type=parameter.value_type if parameter is not None else None,
                    )
                    constraints = getattr(parameter, 'constraints', {}) if parameter is not None else {}
                    choices = constraints.get('choices') if isinstance(constraints, dict) else None
                    if choices and isinstance(value, StringValue):
                        allowed_values = {
                            item.get('value') if isinstance(item, dict) else item
                            for item in choices
                        }
                        if value.value not in allowed_values:
                            diagnostic(
                                'PGM-CALL-007',
                                f'{parameter_display_name(parameter)}不是受支持的选项：{value.value}',
                                statement_id=statement_id,
                                value_id=value.value_id,
                                field_path=f'{statement_path}.arguments.{parameter_id}',
                            )
                if statement.result_binding is not None:
                    binding = statement.result_binding
                    if contract is not None and contract.return_type in {'null', 'unit'}:
                        diagnostic(
                            'PGM-CALL-004',
                            '无返回值函数不能绑定结果',
                            statement_id=statement_id,
                            field_path=f'{statement_path}.result_binding',
                        )
                    elif contract is not None and not _compatible(contract.return_type, binding.value_type):
                        diagnostic(
                            'PGM-CALL-005',
                            f'函数返回 {contract.return_type}，结果绑定声明为 {binding.value_type}',
                            statement_id=statement_id,
                            field_path=f'{statement_path}.result_binding',
                        )
                    require_assignment_target(
                        current_symbols,
                        binding.symbol_id,
                        binding.value_type,
                        binding.declare,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.result_binding',
                    )
                continue

            if isinstance(statement, AssignmentStatement):
                target_type = statement.target.value_type
                validate_value(
                    statement.value,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.value',
                    expected_type=target_type,
                )
                if isinstance(statement.target, LocalAssignmentTarget):
                    require_assignment_target(
                        current_symbols,
                        statement.target.symbol_id,
                        target_type,
                        statement.target.declare,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.target',
                    )
                continue

            if isinstance(statement, IfStatement):
                validate_value(
                    statement.condition,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.condition',
                    expected_type='bool',
                )
                narrowed = frozenset(_narrowed_optional_symbols(statement.condition))
                narrowed_paths[f'{statement_path}.then_statements'] = narrowed
                validate_block(
                    statement.then_statements,
                    current_symbols,
                    f'{statement_path}.then_statements',
                    loop_depth,
                )
                for branch_index, branch in enumerate(statement.additional_branches):
                    validate_value(
                        branch.condition,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.additional_branches[{branch_index}].condition',
                        expected_type='bool',
                    )
                    branch_path = (
                        f'{statement_path}.additional_branches[{branch_index}].statements'
                    )
                    narrowed_paths[branch_path] = frozenset(
                        _narrowed_optional_symbols(branch.condition)
                    )
                    validate_block(
                        branch.statements,
                        current_symbols,
                        branch_path,
                        loop_depth,
                    )
                validate_block(
                    statement.otherwise_statements,
                    current_symbols,
                    f'{statement_path}.otherwise_statements',
                    loop_depth,
                )
                continue

            if isinstance(statement, LoopStatement):
                source_type = value_type(statement.source)
                expected = {'repeat': 'int64', 'while': 'bool'}.get(statement.mode)
                validate_value(
                    statement.source,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.source',
                    expected_type=expected,
                )
                if (
                    statement.mode == 'repeat'
                    and isinstance(statement.source, IntValue)
                    and statement.source.value < 0
                ):
                    diagnostic(
                        'PGM-LOOP-006',
                        '重复次数不能为负数',
                        statement_id=statement_id,
                        value_id=statement.source.value_id,
                        field_path=f'{statement_path}.source',
                    )
                loop_symbols = dict(current_symbols)
                if statement.mode == 'for_each':
                    item_type = _generic_inner(source_type, 'list')
                    if item_type is None:
                        diagnostic(
                            'PGM-LOOP-001',
                            f'列表循环需要 list<T>，当前值为 {source_type}',
                            statement_id=statement_id,
                            value_id=statement.source.value_id,
                            field_path=f'{statement_path}.source',
                        )
                    elif statement.item_binding is not None:
                        if not _compatible(item_type, statement.item_binding.value_type):
                            diagnostic(
                                'PGM-LOOP-002',
                                f'循环项需要 {item_type}，绑定为 {statement.item_binding.value_type}',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.item_binding',
                            )
                        declare_symbol(
                            loop_symbols,
                            statement.item_binding.symbol_id,
                            statement.item_binding.value_type,
                            statement_id=statement_id,
                            field_path=f'{statement_path}.item_binding',
                        )
                    if statement.index_binding is not None:
                        if statement.index_binding.value_type != 'int64':
                            diagnostic(
                                'PGM-LOOP-003',
                                '循环序号必须为 int64',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.index_binding',
                            )
                        declare_symbol(
                            loop_symbols,
                            statement.index_binding.symbol_id,
                            statement.index_binding.value_type,
                            statement_id=statement_id,
                            field_path=f'{statement_path}.index_binding',
                        )
                elif statement.mode == 'for_each_map':
                    map_types = _map_types(source_type)
                    if map_types is None:
                        diagnostic(
                            'PGM-LOOP-004',
                            f'字典循环需要 map<K,V>，当前值为 {source_type}',
                            statement_id=statement_id,
                            value_id=statement.source.value_id,
                            field_path=f'{statement_path}.source',
                        )
                    else:
                        for binding, expected_type, name in (
                            (statement.key_binding, map_types[0], 'key_binding'),
                            (statement.value_binding, map_types[1], 'value_binding'),
                        ):
                            if binding is not None:
                                if not _compatible(expected_type, binding.value_type):
                                    diagnostic(
                                        'PGM-LOOP-005',
                                        f'字典循环绑定需要 {expected_type}，当前为 {binding.value_type}',
                                        statement_id=statement_id,
                                        field_path=f'{statement_path}.{name}',
                                    )
                                declare_symbol(
                                    loop_symbols,
                                    binding.symbol_id,
                                    binding.value_type,
                                    statement_id=statement_id,
                                    field_path=f'{statement_path}.{name}',
                                )
                validate_block(statement.body, loop_symbols, f'{statement_path}.body', loop_depth + 1)
                continue

            if isinstance(statement, (BreakStatement, ContinueStatement)):
                if loop_depth <= 0:
                    diagnostic(
                        'PGM-FLOW-001',
                        '跳出循环或跳过本轮只能放在当前函数的循环体内',
                        statement_id=statement_id,
                        field_path=statement_path,
                    )
                continue

            if isinstance(statement, ReturnStatement):
                if statement.value is None:
                    if document.function.return_type not in {'unit', 'null'}:
                        diagnostic(
                            'PGM-RETURN-001',
                            f'函数必须返回 {document.function.return_type}',
                            statement_id=statement_id,
                            field_path=f'{statement_path}.value',
                        )
                elif document.function.return_type in {'unit', 'null'}:
                    diagnostic(
                        'PGM-RETURN-002',
                        '无返回值函数不能返回数据',
                        statement_id=statement_id,
                        value_id=statement.value.value_id,
                        field_path=f'{statement_path}.value',
                    )
                else:
                    validate_value(
                        statement.value,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.value',
                        expected_type=document.function.return_type,
                    )
                continue

            if isinstance(statement, FailStatement):
                validate_value(
                    statement.message,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.message',
                    expected_type='string',
                )
                if statement.details is not None:
                    validate_value(
                        statement.details,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.details',
                        expected_type='json_value',
                    )
                continue

            if isinstance(statement, TryStatement):
                if statement.retry_policy is not None:
                    validate_value(
                        statement.retry_policy.max_retries,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.retry_policy.max_retries',
                        expected_type='int64',
                    )
                    validate_value(
                        statement.retry_policy.interval,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.retry_policy.interval',
                        expected_type='duration',
                    )
                    if (
                        isinstance(statement.retry_policy.max_retries, IntValue)
                        and statement.retry_policy.max_retries.value < 0
                    ):
                        diagnostic(
                            'PGM-TRY-002',
                            '最大重试次数不能为负数',
                            statement_id=statement_id,
                            value_id=statement.retry_policy.max_retries.value_id,
                            field_path=f'{statement_path}.retry_policy.max_retries',
                        )
                    if retry_body_has_side_effects(statement, registry):
                        expected_review = retry_review_fingerprint(statement, registry)
                        if statement.retry_policy.author_review_fingerprint != expected_review:
                            diagnostic(
                                'PGM-TRY-003',
                                '异常区域包含副作用，重试审核指纹缺失或已失效',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.retry_policy.author_review_fingerprint',
                            )
                validate_block(statement.body, current_symbols, f'{statement_path}.body', loop_depth)
                for catch_index, clause in enumerate(statement.catches):
                    catch_symbols = dict(current_symbols)
                    if clause.error_binding is not None:
                        if clause.error_binding.value_type != 'error':
                            diagnostic(
                                'PGM-TRY-001',
                                '异常绑定必须为 error 类型',
                                statement_id=statement_id,
                                field_path=f'{statement_path}.catches[{catch_index}].error_binding',
                            )
                        declare_symbol(
                            catch_symbols,
                            clause.error_binding.symbol_id,
                            clause.error_binding.value_type,
                            statement_id=statement_id,
                            field_path=f'{statement_path}.catches[{catch_index}].error_binding',
                        )
                    validate_block(
                        clause.statements,
                        catch_symbols,
                        f'{statement_path}.catches[{catch_index}].statements',
                        loop_depth,
                    )
                validate_block(
                    statement.finally_statements,
                    current_symbols,
                    f'{statement_path}.finally_statements',
                    loop_depth,
                )
                continue

            if isinstance(statement, TargetScopeStatement):
                validate_value(
                    statement.target,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.target',
                    expected_type='target_ref',
                )
                validate_block(statement.body, current_symbols, f'{statement_path}.body', loop_depth)
                continue

            if isinstance(statement, ListenStatement):
                validate_value(
                    statement.event_source.name,
                    current_symbols,
                    statement_id=statement_id,
                    field_path=f'{statement_path}.event_source.name',
                    expected_type='string',
                )
                if statement.event_source.sender is not None:
                    validate_value(
                        statement.event_source.sender,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.event_source.sender',
                        expected_type='instance_ref',
                    )
                if statement.condition is not None:
                    validate_value(
                        statement.condition,
                        current_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.condition',
                        expected_type='bool',
                    )
                handler_symbols = dict(current_symbols)
                if statement.receive_binding.value_type != 'received_message':
                    diagnostic(
                        'PGM-LISTEN-001',
                        '消息监听接收绑定必须是 received_message 类型',
                        statement_id=statement_id,
                        field_path=f'{statement_path}.receive_binding.value_type',
                    )
                handler_symbols[statement.receive_binding.symbol_id] = statement.receive_binding.value_type
                handler_contract = (
                    get_contract(registry, statement.handler_function_id)
                    if registry is not None else None
                )
                if registry is not None and handler_contract is None:
                    diagnostic(
                        'PGM-LISTEN-002',
                        f'监听处理项目函数不存在：{statement.handler_function_id}',
                        statement_id=statement_id,
                        field_path=f'{statement_path}.handler_function_id',
                    )
                elif handler_contract is not None and str(handler_contract.opcode) != 'call.project':
                    diagnostic(
                        'PGM-LISTEN-003',
                        '监听处理器必须引用普通项目函数',
                        statement_id=statement_id,
                        field_path=f'{statement_path}.handler_function_id',
                    )
                handler_parameters = {
                    item.parameter_id: item
                    for item in (
                        handler_contract.parameters
                        if handler_contract is not None else ()
                    )
                }
                if handler_contract is not None:
                    for parameter_id in statement.handler_arguments:
                        if parameter_id not in handler_parameters:
                            diagnostic(
                                'PGM-LISTEN-004',
                                f'监听处理函数不存在参数：{parameter_id}',
                                statement_id=statement_id,
                                field_path=(
                                    f'{statement_path}.handler_arguments.{parameter_id}'
                                ),
                            )
                    for parameter in handler_contract.parameters:
                        if (
                            parameter.required
                            and parameter.parameter_id not in statement.handler_arguments
                        ):
                            diagnostic(
                                'PGM-LISTEN-005',
                                f'监听处理函数缺少必填参数：{parameter_display_name(parameter)}',
                                statement_id=statement_id,
                                field_path=(
                                    f'{statement_path}.handler_arguments.'
                                    f'{parameter.parameter_id}'
                                ),
                            )
                for parameter_id, value in statement.handler_arguments.items():
                    parameter = handler_parameters.get(parameter_id)
                    validate_value(
                        value,
                        handler_symbols,
                        statement_id=statement_id,
                        field_path=f'{statement_path}.handler_arguments.{parameter_id}',
                        expected_type=(
                            parameter.value_type if parameter is not None else None
                        ),
                    )
                continue
        return current_symbols

    for parameter_index, parameter in enumerate(document.function.parameters):
        if parameter.default_value is not None:
            validate_value(
                parameter.default_value,
                initial_symbols,
                statement_id='',
                field_path=f'function.parameters[{parameter_index}].default_value',
                expected_type=parameter.value_type,
            )
    validate_block(document.function.statements, initial_symbols, 'function.statements')
    return tuple(diagnostics)


__all__ = [
    'ProgramDiagnostic',
    'iter_statement_tree',
    'iter_statement_values',
    'dangerous_call_review_fingerprint',
    'retry_review_fingerprint',
    'retry_body_has_side_effects',
    'validate_program_document',
]
