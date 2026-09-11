"""Deterministic ProgramDocument-to-ECIR compiler, independent of source text."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .network_runtime_v6 import (
    merge_network_authorizations,
    project_network_authorization,
    static_network_authorization,
)
from .program_contracts import (
    FunctionContract,
    FunctionContractProvider,
    ParameterContract,
    contract_capabilities,
    contract_minimum_android_api,
    contract_platform_detail,
    contract_platforms,
    get_contract,
    require_contract,
)
from .program_serialization import canonical_json_bytes, content_revision
from .program_types import (
    AssetReferenceValue,
    AssignmentStatement,
    BoolValue,
    BreakStatement,
    CallStatement,
    ComparisonValue,
    ConditionGroupValue,
    ContinueStatement,
    DateTimeValue,
    DateValue,
    DurationValue,
    EntityReferenceValue,
    FloatValue,
    FailStatement,
    IfStatement,
    IntValue,
    JsonValue,
    ListenStatement,
    ListValue,
    LocalAssignmentTarget,
    LoopStatement,
    MapValue,
    MemberAccessValue,
    NotValue,
    NullValue,
    PathValue,
    PointValue,
    ProgramDocument,
    ProjectVariableAssignmentTarget,
    ProjectVariableReferenceValue,
    PureOperationValue,
    RecordValue,
    RectValue,
    ReturnStatement,
    SelectorValue,
    Statement,
    StringValue,
    SymbolReferenceValue,
    TargetReferenceValue,
    TargetScopeStatement,
    TimeValue,
    TryStatement,
    UnsetValue,
    ValueNode,
    iter_value_children,
    statement_child_blocks,
    value_type,
)
from .program_validation import (
    ProgramDiagnostic,
    iter_statement_tree,
    iter_statement_values,
    types_compatible,
    validate_program_document,
)
from .pure_operations_v6 import (
    pure_operation_registry_hash,
    pure_operation_registry_payload,
)

ECIR_VERSION = 1
PROGRAM_MODEL_VERSION = 1
VERIFIED_CORE_PLATFORMS = ('android_adb', 'no_target', 'windows')
MESSAGE_WAIT_RECEIVE_FUNCTION_ID = 'official.message.wait_receive'
MESSAGE_WAIT_RECEIVE_NAME_PARAMETER_ID = (
    'official.message.wait_receive.parameter.name'
)
MESSAGE_WAIT_RECEIVE_SENDER_PARAMETER_ID = (
    'official.message.wait_receive.parameter.sender'
)


class _LinkedContractRegistry:
    """Overlay project contracts without mutating the official registry."""

    def __init__(
        self,
        official: FunctionContractProvider,
        project_contracts: dict[str, FunctionContract],
    ) -> None:
        self._official = official
        self._project_contracts = project_contracts

    def get(self, function_id: str) -> Any | None:
        return self._project_contracts.get(function_id) or get_contract(
            self._official, function_id,
        )

    def require(self, function_id: str) -> Any:
        contract = self.get(function_id)
        if contract is None:
            raise KeyError(function_id)
        return contract


def _project_contract(document: ProgramDocument) -> FunctionContract:
    function = document.function
    parameters: list[ParameterContract] = []
    for parameter in function.parameters:
        fields = {
            'parameter_id': parameter.parameter_id,
            'name': parameter.symbol_id,
            'display_name': parameter.display_name,
            'value_type': parameter.value_type,
            'required': parameter.required,
        }
        if parameter.default_value is not None:
            fields['default'] = parameter.default_value
        parameters.append(ParameterContract(**fields))
    return FunctionContract(
        function_id=function.function_id,
        qualified_name=function.display_name,
        opcode='call.project',
        parameters=tuple(parameters),
        return_type=function.return_type,
        platforms=VERIFIED_CORE_PLATFORMS,
        contract_version='project-v1',
        contract_fingerprint=content_revision(canonical_json_bytes({
            'function_id': function.function_id,
            'parameters': [{
                'parameter_id': parameter.parameter_id,
                'value_type': parameter.value_type,
                'required': parameter.required,
                'default_value': (
                    parameter.default_value.model_dump(mode='json')
                    if parameter.default_value is not None else None
                ),
            } for parameter in function.parameters],
            'return_type': function.return_type,
        })),
    )


def project_function_contract(document: ProgramDocument) -> FunctionContract:
    """Expose the same stable project contract to editing and compilation."""

    return _project_contract(document)


def linked_function_registry(
    documents: Sequence[ProgramDocument],
    official_registry: FunctionContractProvider,
) -> FunctionContractProvider:
    """Return an official registry overlaid with validated project signatures."""

    contracts: dict[str, FunctionContract] = {}
    for document in documents:
        function_id = document.function.function_id
        if function_id in contracts:
            raise ValueError(f'duplicate project function contract: {function_id}')
        contracts[function_id] = _project_contract(document)
    return _LinkedContractRegistry(official_registry, contracts)

class _LoweringError(ValueError):
    def __init__(self, value_id: str, message: str) -> None:
        super().__init__(message)
        self.value_id = value_id


def _lower_value(value: ValueNode) -> Any:
    if isinstance(value, UnsetValue):
        raise _LoweringError(value.value_id, '未配置值不能进入 ECIR')
    if isinstance(value, NullValue):
        return None
    if isinstance(value, (StringValue, IntValue, FloatValue, BoolValue)):
        return value.value
    if isinstance(value, (DateValue, DateTimeValue, TimeValue)):
        return {'kind': value.kind, 'value': value.value.isoformat()}
    if isinstance(value, DurationValue):
        return {'kind': 'duration', 'milliseconds': value.milliseconds}
    if isinstance(value, SymbolReferenceValue):
        return {'kind': 'reference', 'scope': 'local', 'symbol_id': value.symbol_id}
    if isinstance(value, ProjectVariableReferenceValue):
        return {'kind': 'reference', 'scope': 'project', 'variable_id': value.variable_id}
    if isinstance(value, AssetReferenceValue):
        return {'kind': 'asset_ref', 'asset_id': value.asset_id, 'asset_kind': value.asset_kind}
    if isinstance(value, TargetReferenceValue):
        return {'kind': 'target_ref', 'target_id': value.target_id}
    if isinstance(value, EntityReferenceValue):
        return {
            'kind': 'entity_ref',
            'reference_id': value.reference_id,
            'reference_type': value.reference_type,
        }
    if isinstance(value, PointValue):
        return {'kind': 'point', 'x': value.x, 'y': value.y}
    if isinstance(value, RectValue):
        return {
            'kind': 'rect', 'x': value.x, 'y': value.y,
            'width': value.width, 'height': value.height,
        }
    if isinstance(value, PathValue):
        return {
            'kind': 'path',
            'points': [{'x': point.x, 'y': point.y} for point in value.points],
        }
    if isinstance(value, MemberAccessValue):
        return {
            'kind': 'member_access',
            'source': _lower_value(value.source),
            'field_id': value.field_id,
            'result_type': value.result_type,
        }
    if isinstance(value, ListValue):
        return {
            'kind': 'list', 'item_type': value.item_type,
            'items': [_lower_value(item) for item in value.items],
        }
    if isinstance(value, MapValue):
        return {
            'kind': 'map',
            'key_type': value.key_type,
            'value_type': value.entry_value_type,
            'duplicate_policy': value.duplicate_policy,
            'entries': [
                {'key': _lower_value(entry.key), 'value': _lower_value(entry.value)}
                for entry in value.entries
            ],
        }
    if isinstance(value, RecordValue):
        return {
            'kind': 'record',
            'record_type': value.record_type,
            'fields': {key: _lower_value(item) for key, item in sorted(value.fields.items())},
        }
    if isinstance(value, JsonValue):
        return {'kind': 'json', 'value': value.payload}
    if isinstance(value, PureOperationValue):
        return {
            'kind': 'operation',
            'operation_id': value.operation_id,
            'result_type': value.result_type,
            'inputs': {key: _lower_value(item) for key, item in sorted(value.inputs.items())},
        }
    if isinstance(value, SelectorValue):
        return {
            'kind': 'selector',
            'bindings': [
                {
                    'symbol_id': binding.symbol_id,
                    'role': binding.role,
                    'value_type': binding.value_type,
                }
                for binding in value.bindings
            ],
            'result_type': value.result_type,
            'expression': _lower_value(value.expression),
        }
    if isinstance(value, ComparisonValue):
        return {
            'kind': 'compare', 'operator': value.operator,
            'operand_type': value_type(value.left),
            'left': _lower_value(value.left), 'right': _lower_value(value.right),
        }
    if isinstance(value, ConditionGroupValue):
        return {
            'kind': 'condition_group', 'operator': value.operator,
            'conditions': [_lower_value(item) for item in value.conditions],
        }
    if isinstance(value, NotValue):
        return {'kind': 'not', 'condition': _lower_value(value.condition)}
    raise _LoweringError(value.value_id, f'尚未实现值类型：{value.kind}')


def lower_value_node(value: ValueNode) -> Any:
    """Lower one validated typed value without exposing compiler internals."""

    return _lower_value(value)


def _value_is_player_static(value: ValueNode) -> bool:
    """Return whether a whole author value can be replaced as one Player slot.

    References, selectors and pure operations are deliberately excluded.  A
    dynamic parent is traversed and its largest static children become slots,
    which avoids overlapping parent/child overrides with order-dependent
    results.
    """

    if isinstance(value, (StringValue, IntValue, FloatValue, BoolValue)):
        return True
    if isinstance(value, (DateValue, DateTimeValue, TimeValue, DurationValue)):
        return True
    if isinstance(value, (PointValue, RectValue, PathValue, JsonValue)):
        return True
    if isinstance(value, ListValue):
        return all(_value_is_player_static(item) for item in value.items)
    if isinstance(value, MapValue):
        return all(
            _value_is_player_static(entry.key) and _value_is_player_static(entry.value)
            for entry in value.entries
        )
    if isinstance(value, RecordValue):
        return all(_value_is_player_static(item) for item in value.fields.values())
    return False


def _nested_player_value_slots(
    value: ValueNode,
    path: tuple[str | int, ...] = (),
) -> Iterable[tuple[ValueNode, tuple[str | int, ...]]]:
    """Yield non-overlapping static descendants of a dynamic root value."""

    if path and _value_is_player_static(value):
        yield value, path
        return
    if isinstance(value, MemberAccessValue):
        yield from _nested_player_value_slots(value.source, (*path, 'source'))
    elif isinstance(value, ListValue):
        for index, item in enumerate(value.items):
            yield from _nested_player_value_slots(item, (*path, 'items', index))
    elif isinstance(value, MapValue):
        for index, entry in enumerate(value.entries):
            yield from _nested_player_value_slots(entry.key, (*path, 'entries', index, 'key'))
            yield from _nested_player_value_slots(entry.value, (*path, 'entries', index, 'value'))
    elif isinstance(value, RecordValue):
        for field_id, item in sorted(value.fields.items()):
            yield from _nested_player_value_slots(item, (*path, 'fields', field_id))
    elif isinstance(value, PureOperationValue):
        for input_id, item in sorted(value.inputs.items()):
            yield from _nested_player_value_slots(item, (*path, 'inputs', input_id))
    elif isinstance(value, SelectorValue):
        yield from _nested_player_value_slots(value.expression, (*path, 'expression'))
    elif isinstance(value, ComparisonValue):
        yield from _nested_player_value_slots(value.left, (*path, 'left'))
        yield from _nested_player_value_slots(value.right, (*path, 'right'))
    elif isinstance(value, ConditionGroupValue):
        for index, item in enumerate(value.conditions):
            yield from _nested_player_value_slots(item, (*path, 'conditions', index))
    elif isinstance(value, NotValue):
        yield from _nested_player_value_slots(value.condition, (*path, 'condition'))


def _project_variable_definitions(project_variables: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            'variable_id': variable.variable_id,
            'display_name': variable.display_name,
            'value_type': variable.value_type,
            'default_value': _lower_value(variable.default_value),
            'constraints': dict(variable.constraints),
        }
        for variable in project_variables
    ]


def _statement_value_roots(statement: Statement) -> tuple[tuple[str, ValueNode], ...]:
    if isinstance(statement, CallStatement):
        return tuple((f'arguments.{key}', value) for key, value in statement.arguments.items())
    if isinstance(statement, AssignmentStatement):
        return (('value', statement.value),)
    if isinstance(statement, IfStatement):
        return (
            ('condition', statement.condition),
            *((f'additional_branches.{item.branch_id}.condition', item.condition)
              for item in statement.additional_branches),
        )
    if isinstance(statement, LoopStatement):
        return (('source', statement.source),)
    if isinstance(statement, ReturnStatement):
        return (('value', statement.value),) if statement.value is not None else ()
    if isinstance(statement, FailStatement):
        roots: list[tuple[str, ValueNode]] = [('message', statement.message)]
        if statement.details is not None:
            roots.append(('details', statement.details))
        return tuple(roots)
    if isinstance(statement, TryStatement) and statement.retry_policy is not None:
        return (
            ('retry_policy.max_retries', statement.retry_policy.max_retries),
            ('retry_policy.interval', statement.retry_policy.interval),
        )
    if isinstance(statement, TargetScopeStatement):
        return (('target', statement.target),)
    if isinstance(statement, ListenStatement):
        result: list[tuple[str, ValueNode]] = [('event_source.name', statement.event_source.name)]
        if statement.event_source.sender is not None:
            result.append(('event_source.sender', statement.event_source.sender))
        if statement.condition is not None:
            result.append(('condition', statement.condition))
        result.extend(
            (f'handler_arguments.{key}', value)
            for key, value in statement.handler_arguments.items()
        )
        return tuple(result)
    return ()


def _walk(statements: Iterable[Statement]) -> Iterable[Statement]:
    for statement in statements:
        yield statement
        for block in statement_child_blocks(statement):
            yield from _walk(block)


def _static_message_name(value: ValueNode | None) -> tuple[str, str]:
    if isinstance(value, StringValue):
        return 'exact', value.value
    return 'dynamic', ''


def _static_message_sender(value: ValueNode | None) -> tuple[str, str]:
    if value is None or isinstance(value, NullValue):
        return 'wildcard', ''
    if isinstance(value, EntityReferenceValue) and value.reference_type == 'instance_ref':
        return 'exact', value.reference_id
    return 'dynamic', ''


def _message_filters_are_proven_disjoint(
    left_name: tuple[str, str],
    left_sender: tuple[str, str],
    right_name: tuple[str, str],
    right_sender: tuple[str, str],
) -> bool:
    if left_name[0] == right_name[0] == 'exact' and left_name[1] != right_name[1]:
        return True
    return (
        left_sender[0] == right_sender[0] == 'exact'
        and left_sender[1] != right_sender[1]
    )


def _message_consumer_conflicts(
    documents: Sequence[ProgramDocument],
) -> list[ProgramDiagnostic]:
    """Reject wait/listen pairs unless their receive ranges are provably disjoint."""

    waits: list[tuple[str, CallStatement, tuple[str, str], tuple[str, str]]] = []
    listeners: list[
        tuple[str, ListenStatement, tuple[str, str], tuple[str, str]]
    ] = []
    for document in documents:
        owner = document.function.function_id
        for statement in _walk(document.function.statements):
            if (
                isinstance(statement, CallStatement)
                and statement.function_id == MESSAGE_WAIT_RECEIVE_FUNCTION_ID
            ):
                waits.append((
                    owner,
                    statement,
                    _static_message_name(
                        statement.arguments.get(MESSAGE_WAIT_RECEIVE_NAME_PARAMETER_ID)
                    ),
                    _static_message_sender(
                        statement.arguments.get(MESSAGE_WAIT_RECEIVE_SENDER_PARAMETER_ID)
                    ),
                ))
            elif isinstance(statement, ListenStatement):
                listeners.append((
                    owner,
                    statement,
                    _static_message_name(statement.event_source.name),
                    _static_message_sender(statement.event_source.sender),
                ))
    diagnostics: list[ProgramDiagnostic] = []
    for wait_owner, wait, wait_name, wait_sender in waits:
        for _listener_owner, listener, listener_name, listener_sender in listeners:
            if _message_filters_are_proven_disjoint(
                wait_name,
                wait_sender,
                listener_name,
                listener_sender,
            ):
                continue
            dynamic = 'dynamic' in {
                wait_name[0],
                wait_sender[0],
                listener_name[0],
                listener_sender[0],
            }
            diagnostics.append(ProgramDiagnostic(
                code='PGM-MSG-002' if dynamic else 'PGM-MSG-001',
                severity='error',
                message=(
                    '同步等待与消息监听的动态消费范围无法证明互斥，已保守阻止争抢'
                    if dynamic else
                    '同步等待与消息监听会消费相同的消息名称/来源范围'
                ),
                function_id=wait_owner,
                statement_id=wait.statement_id,
                field_path=(
                    'function.statements; conflicts_with_listener='
                    f'{listener.statement_id}'
                ),
            ))
    return diagnostics


def compile_program_document(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    *,
    target_platform: str | None = None,
    _project_function_ids: frozenset[str] = frozenset(),
    project_variables: Sequence[Any] | None = None,
    target_definitions: Sequence[Any] | None = None,
    default_target_id: str | None = None,
    network_policies: Sequence[Mapping[str, Any]] | None = None,
    _skip_message_conflict_check: bool = False,
) -> dict[str, Any]:
    """Compile the first ProgramDocument vertical slice into runtime ECIR."""

    diagnostics = list(validate_program_document(document, registry, require_configured=True))
    if not _skip_message_conflict_check:
        diagnostics.extend(_message_consumer_conflicts((document,)))
    function_id = document.function.function_id
    normalized_targets = [
        item.model_dump(mode='json') if hasattr(item, 'model_dump') else dict(item)
        for item in (target_definitions or ())
    ]
    targets_by_id: dict[str, dict[str, Any]] = {}
    for target in normalized_targets:
        target_id = str(target.get('target_id') or '')
        if not target_id or target_id in targets_by_id:
            diagnostics.append(ProgramDiagnostic(
                code='PGM-TARGET-002', severity='error',
                message='目标配置缺少稳定 ID 或包含重复 ID',
                function_id=function_id, field_path='targets',
            ))
            continue
        targets_by_id[target_id] = target
    referenced_target_ids: set[str] = set()
    for statement in _walk(document.function.statements):
        for value in iter_statement_values(statement):
            if not isinstance(value, TargetReferenceValue):
                continue
            referenced_target_ids.add(value.target_id)
            if value.target_id not in targets_by_id:
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-TARGET-001', severity='error',
                    message=f'目标引用未进入编译闭包：{value.target_id}',
                    function_id=function_id, statement_id=statement.statement_id,
                    value_id=value.value_id, field_path='target.target_id',
                ))
    if default_target_id:
        referenced_target_ids.add(default_target_id)
        if default_target_id not in targets_by_id:
            diagnostics.append(ProgramDiagnostic(
                code='PGM-TARGET-001', severity='error',
                message=f'默认目标未进入编译闭包：{default_target_id}',
                function_id=function_id, field_path='default_target_id',
            ))
    for statement in _walk(document.function.statements):
        if not isinstance(statement, TargetScopeStatement):
            continue
        target_id = statement.target.target_id
        if target_id in targets_by_id and targets_by_id[target_id].get('type') == 'android_local':
            diagnostics.append(ProgramDiagnostic(
                code='PGM-TARGET-003', severity='error',
                message='Windows Runtime 不能进入 Android 本机目标作用域',
                function_id=function_id, statement_id=statement.statement_id,
                value_id=statement.target.value_id, field_path='target.target_id',
            ))
    variable_definitions = {
        variable.variable_id: variable for variable in (project_variables or ())
    }
    for statement in (
        iter_statement_tree(document.function.statements)
        if project_variables is not None else ()
    ):
        if (
            isinstance(statement, AssignmentStatement)
            and isinstance(statement.target, ProjectVariableAssignmentTarget)
        ):
            definition = variable_definitions.get(statement.target.variable_id)
            if definition is None:
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-VAR-001', severity='error',
                    message=f'项目变量不存在：{statement.target.variable_id}',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    field_path='target.variable_id',
                ))
            elif not types_compatible(statement.target.value_type, definition.value_type):
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-VAR-002', severity='error',
                    message='项目变量赋值目标类型与变量定义不兼容',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    field_path='target.value_type',
                ))
        for value in iter_statement_values(statement):
            if not isinstance(value, ProjectVariableReferenceValue):
                continue
            definition = variable_definitions.get(value.variable_id)
            if definition is None:
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-VAR-001', severity='error',
                    message=f'项目变量不存在：{value.variable_id}',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    value_id=value.value_id,
                    field_path='project_variable_ref.variable_id',
                ))
            elif not types_compatible(definition.value_type, value.value_type):
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-VAR-002', severity='error',
                    message='项目变量引用类型与变量定义不兼容',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    value_id=value.value_id,
                    field_path='project_variable_ref.value_type',
                ))
    network_authorizations: dict[str, dict[str, Any]] = {}
    project_authorization: dict[str, Any] | None = None
    if network_policies:
        try:
            project_authorization = project_network_authorization(network_policies)
        except (TypeError, ValueError) as exc:
            diagnostics.append(ProgramDiagnostic(
                code='PGM-NET-002', severity='error',
                message=f'项目网络策略无效：{exc}',
                function_id=function_id, field_path='network_policies',
            ))
    for statement in _walk(document.function.statements):
        if not isinstance(statement, CallStatement):
            continue
        contract = get_contract(registry, statement.function_id)
        if contract is not None and not contract_platforms(contract):
            diagnostics.append(ProgramDiagnostic(
                code='PGM-CALL-006',
                severity='error',
                message=f'{contract.qualified_name} 尚未提供可运行实现',
                function_id=function_id,
                statement_id=statement.statement_id,
                field_path='function.statements',
            ))
        if contract is None or not str(contract.opcode).startswith('network.'):
            continue
        url_parameter_id = f'{contract.function_id}.parameter.url'
        url_value = statement.arguments.get(url_parameter_id)
        try:
            if isinstance(url_value, StringValue):
                authorization = static_network_authorization(url_value.value)
                if project_authorization is not None:
                    authorization = merge_network_authorizations(
                        authorization,
                        project_authorization,
                    )
                network_authorizations[statement.statement_id] = authorization
            elif project_authorization is not None:
                network_authorizations[statement.statement_id] = project_authorization
            else:
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-NET-001', severity='error',
                    message='动态 URL 必须绑定开发者批准的项目网络策略',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    field_path=f'arguments.{url_parameter_id}',
                ))
        except (RuntimeError, TypeError, ValueError) as exc:
            diagnostics.append(ProgramDiagnostic(
                code='PGM-NET-002', severity='error',
                message=f'网络 URL 或授权策略无效：{exc}',
                function_id=function_id,
                statement_id=statement.statement_id,
                field_path=f'arguments.{url_parameter_id}',
            ))
    if target_platform is not None:
        initial_platform = target_platform
        if default_target_id in targets_by_id:
            initial_platform = str(
                targets_by_id[default_target_id].get('type') or target_platform
            )

        def walk_platform(
            statements: Iterable[Statement], platform: str,
        ) -> Iterable[tuple[Statement, str]]:
            for statement in statements:
                effective = platform
                if isinstance(statement, TargetScopeStatement):
                    effective = str(
                        targets_by_id.get(statement.target.target_id, {}).get('type') or platform
                    )
                yield statement, effective
                for block in statement_child_blocks(statement):
                    yield from walk_platform(block, effective)

        for statement, effective_platform in walk_platform(
            document.function.statements, initial_platform,
        ):
            if not isinstance(statement, CallStatement):
                continue
            contract = get_contract(registry, statement.function_id)
            if contract is None:
                continue
            if effective_platform not in contract_platforms(contract):
                detail = contract_platform_detail(contract, effective_platform)
                if effective_platform == 'no_target':
                    code = 'PGM-PLATFORM-001'
                    message = (
                        f'{contract.qualified_name}需要操作目标；'
                        '请设置默认目标，或把语句放入目标作用域'
                    )
                elif detail is not None and detail.support != 'unsupported':
                    code = 'PGM-PLATFORM-002'
                    message = f'{contract.qualified_name} 尚未在目标平台验证：{effective_platform}'
                else:
                    code = 'PGM-PLATFORM-001'
                    message = f'{contract.qualified_name} 不支持目标平台：{effective_platform}'
                diagnostics.append(ProgramDiagnostic(
                    code=code,
                    severity='error',
                    message=message,
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    field_path='function.statements',
                ))
                continue
            parameters = {
                parameter.parameter_id: parameter
                for parameter in contract.parameters
            }
            for parameter_id, value in statement.arguments.items():
                if not isinstance(value, StringValue):
                    continue
                parameter = parameters.get(parameter_id)
                constraints = getattr(parameter, 'constraints', {}) if parameter is not None else {}
                choices = constraints.get('choices') if isinstance(constraints, dict) else None
                if not choices:
                    continue
                selected = next((
                    choice for choice in choices
                    if (
                        choice.get('value') if isinstance(choice, dict) else choice
                    ) == value.value
                ), None)
                if not isinstance(selected, dict):
                    continue
                platforms = tuple(selected.get('platforms') or ())
                if platforms and effective_platform not in platforms:
                    diagnostics.append(ProgramDiagnostic(
                        code='PGM-PLATFORM-003',
                        severity='error',
                        message=(
                            f'{getattr(parameter, "display_name", parameter_id)}的选项“'
                            f'{selected.get("label", value.value)}”不支持目标平台：{effective_platform}'
                        ),
                        function_id=function_id,
                        statement_id=statement.statement_id,
                        value_id=value.value_id,
                        field_path=f'arguments.{parameter_id}',
                    ))
    if (
        target_platform is not None
        and target_platform not in VERIFIED_CORE_PLATFORMS
        and not any(item.code.startswith('PGM-PLATFORM-') for item in diagnostics)
    ):
        diagnostics.append(ProgramDiagnostic(
            code='PGM-PLATFORM-002',
            severity='error',
            message=f'格式 6 核心运行时尚未在目标平台验证：{target_platform}',
            function_id=function_id,
            field_path='function.statements',
        ))
    if diagnostics:
        return {'valid': False, 'ecir': None, 'diagnostics': [item.to_dict() for item in diagnostics]}

    debug_statements: dict[str, dict[str, Any]] = {}
    debug_values: dict[str, dict[str, Any]] = {}
    debug_symbols: dict[str, dict[str, Any]] = {
        parameter.symbol_id: {
            'function_id': function_id,
            'symbol_id': parameter.symbol_id,
            'display_name': parameter.display_name,
            'value_type': parameter.value_type,
            'kind': 'parameter',
        }
        for parameter in document.function.parameters
    }
    value_override_slots: list[dict[str, Any]] = []

    def register_value(value: ValueNode, statement_id: str, field_path: str) -> None:
        debug_values[value.value_id] = {
            'function_id': function_id,
            'statement_id': statement_id,
            'value_id': value.value_id,
            'field_path': field_path,
        }
        for index, child in enumerate(iter_value_children(value)):
            register_value(child, statement_id, f'{field_path}.value[{index}]')

    def instruction(
        statement: Statement,
        opcode: str,
        arguments: dict[str, Any],
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            'instruction_id': statement.statement_id,
            'opcode': opcode,
            'arguments': arguments,
            'result_slot': None,
            'source': {},
            'platforms': list(VERIFIED_CORE_PLATFORMS),
            'capabilities': [],
            **extra,
        }

    def compile_block(statements: Iterable[Statement], block_path: str) -> list[dict[str, Any]]:
        compiled: list[dict[str, Any]] = []
        for index, statement in enumerate(statements):
            statement_path = f'{block_path}[{index}]'
            roots = _statement_value_roots(statement)
            debug_statements[statement.statement_id] = {
                'function_id': function_id,
                'statement_id': statement.statement_id,
                'value_ids': [value.value_id for _, value in roots],
                'field_path': statement_path,
                **({'step_label': statement.step_label} if statement.step_label else {}),
            }
            for relative_path, value in roots:
                register_value(value, statement.statement_id, f'{statement_path}.{relative_path}')
            if isinstance(statement, CallStatement):
                contract = require_contract(registry, statement.function_id)
                arguments: dict[str, Any] = {}
                parameter_ids: dict[str, str] = {}
                for parameter in contract.parameters:
                    value = statement.arguments.get(parameter.parameter_id)
                    if value is None:
                        continue
                    arguments[parameter.parameter_id] = _lower_value(value)
                    parameter_ids[parameter.parameter_id] = parameter.parameter_id
                    if not _value_is_player_static(value):
                        for nested_value, nested_path in _nested_player_value_slots(value):
                            value_override_slots.append({
                                'value_id': nested_value.value_id,
                                'function_id': function_id,
                                'statement_id': statement.statement_id,
                                'parameter_id': parameter.parameter_id,
                                'path': list(nested_path),
                                'value_type': value_type(nested_value),
                            })
                compiled.append({
                    'instruction_id': statement.statement_id,
                    'function_id': contract.function_id,
                    'opcode': contract.opcode,
                    'arguments': arguments,
                    'parameter_ids': parameter_ids,
                    'result_type': contract.return_type,
                    'result_slot': (
                        statement.result_binding.symbol_id if statement.result_binding is not None else None
                    ),
                    'source': {},
                    'platforms': list(contract_platforms(contract)),
                    'capabilities': list(contract_capabilities(contract)),
                    'callee_function_id': (
                        contract.function_id
                        if contract.function_id in _project_function_ids
                        or contract.opcode == 'call.extension'
                        else None
                    ),
                    **(
                        {'timeout_ms': int(getattr(contract, 'timeout_ms', 30_000))}
                        if contract.opcode == 'call.extension'
                        else {}
                    ),
                    **(
                        {
                            'network_authorization': network_authorizations[
                                statement.statement_id
                            ],
                        }
                        if statement.statement_id in network_authorizations
                        else {}
                    ),
                    **(
                        {
                            'dangerous_author_review': {
                                'fingerprint': statement.author_review_fingerprint,
                                'contract_fingerprint': contract.fingerprint(),
                            },
                        }
                        if bool(getattr(contract, 'dangerous', False))
                        else {}
                    ),
                })
                if statement.result_binding is not None:
                    debug_symbols[statement.result_binding.symbol_id] = {
                        'function_id': function_id,
                        'symbol_id': statement.result_binding.symbol_id,
                        'display_name': statement.result_binding.display_name,
                        'value_type': statement.result_binding.value_type,
                        'kind': 'result',
                    }
                continue
            if isinstance(statement, AssignmentStatement):
                if isinstance(statement.target, LocalAssignmentTarget):
                    target = {
                        'scope': 'local',
                        'symbol_id': statement.target.symbol_id,
                        'declare': statement.target.declare,
                        'value_type': statement.target.value_type,
                    }
                    opcode = 'data.assign_local'
                    debug_symbols[statement.target.symbol_id] = {
                        'function_id': function_id,
                        'symbol_id': statement.target.symbol_id,
                        'display_name': statement.target.display_name,
                        'value_type': statement.target.value_type,
                        'kind': 'local',
                    }
                else:
                    target = {
                        'scope': 'project',
                        'variable_id': statement.target.variable_id,
                        'value_type': statement.target.value_type,
                    }
                    opcode = 'data.assign_project'
                compiled.append(instruction(
                    statement,
                    opcode,
                    {'target': target, 'value': _lower_value(statement.value)},
                ))
                continue
            if isinstance(statement, IfStatement):
                compiled.append(instruction(statement, 'control.if', {
                    'condition': _lower_value(statement.condition),
                    'then': compile_block(
                        statement.then_statements,
                        f'{statement_path}.then_statements',
                    ),
                    'additional_branches': [{
                        'branch_id': branch.branch_id,
                        'condition': _lower_value(branch.condition),
                        'body': compile_block(
                            branch.statements,
                            f'{statement_path}.additional_branches.{branch.branch_id}.statements',
                        ),
                    } for branch in statement.additional_branches],
                    'otherwise': compile_block(
                        statement.otherwise_statements,
                        f'{statement_path}.otherwise_statements',
                    ),
                }))
                continue
            if isinstance(statement, LoopStatement):
                opcode = {
                    'repeat': 'control.repeat',
                    'while': 'control.while',
                    'for_each': 'control.for_each',
                    'for_each_map': 'control.for_each_map',
                }[statement.mode]
                bindings = {
                    key: ({
                        'symbol_id': binding.symbol_id,
                        'value_type': binding.value_type,
                    } if binding is not None else None)
                    for key, binding in (
                        ('item', statement.item_binding),
                        ('index', statement.index_binding),
                        ('key', statement.key_binding),
                        ('value', statement.value_binding),
                    )
                }
                for binding in (
                    statement.item_binding, statement.index_binding,
                    statement.key_binding, statement.value_binding,
                ):
                    if binding is not None:
                        debug_symbols[binding.symbol_id] = {
                            'function_id': function_id,
                            'symbol_id': binding.symbol_id,
                            'display_name': binding.display_name,
                            'value_type': binding.value_type,
                            'kind': 'loop',
                        }
                compiled.append(instruction(statement, opcode, {
                    'source': _lower_value(statement.source),
                    'snapshot': statement.mode in {'for_each', 'for_each_map'},
                    'bindings': bindings,
                    'body': compile_block(statement.body, f'{statement_path}.body'),
                }))
                continue
            if isinstance(statement, BreakStatement):
                compiled.append(instruction(statement, 'control.break', {}))
                continue
            if isinstance(statement, ContinueStatement):
                compiled.append(instruction(statement, 'control.continue', {}))
                continue
            if isinstance(statement, ReturnStatement):
                compiled.append(instruction(
                    statement,
                    'control.return',
                    {'value': _lower_value(statement.value) if statement.value is not None else None},
                ))
                continue
            if isinstance(statement, FailStatement):
                compiled.append(instruction(statement, 'control.fail', {
                    'error_id': statement.error_id,
                    'message': _lower_value(statement.message),
                    'details': (
                        _lower_value(statement.details)
                        if statement.details is not None else None
                    ),
                }))
                continue
            if isinstance(statement, TryStatement):
                for clause in statement.catches:
                    if clause.error_binding is not None:
                        debug_symbols[clause.error_binding.symbol_id] = {
                            'function_id': function_id,
                            'symbol_id': clause.error_binding.symbol_id,
                            'display_name': clause.error_binding.display_name,
                            'value_type': clause.error_binding.value_type,
                            'kind': 'error',
                        }
                retry = None
                if statement.retry_policy is not None:
                    retry = {
                        'max_retries': _lower_value(statement.retry_policy.max_retries),
                        'interval': _lower_value(statement.retry_policy.interval),
                        'transient_only': True,
                        'author_review_fingerprint': (
                            statement.retry_policy.author_review_fingerprint
                        ),
                        'evaluate_on_entry': True,
                    }
                compiled.append(instruction(statement, 'control.try', {
                    'body': compile_block(statement.body, f'{statement_path}.body'),
                    'retry_policy': retry,
                    'catches': [{
                        'catch_id': clause.catch_id,
                        'error_ids': list(clause.error_ids),
                        'error_slot': (
                            clause.error_binding.symbol_id
                            if clause.error_binding is not None else None
                        ),
                        'body': compile_block(
                            clause.statements,
                            f'{statement_path}.catches.{clause.catch_id}.statements',
                        ),
                    } for clause in statement.catches],
                    'finally': compile_block(
                        statement.finally_statements,
                        f'{statement_path}.finally_statements',
                    ),
                }))
                continue
            if isinstance(statement, TargetScopeStatement):
                compiled.append(instruction(statement, 'control.target_scope', {
                    'target': _lower_value(statement.target),
                    'body': compile_block(statement.body, f'{statement_path}.body'),
                    'restore_logical_target': True,
                }))
                continue
            if isinstance(statement, ListenStatement):
                debug_symbols[statement.receive_binding.symbol_id] = {
                    'function_id': function_id,
                    'symbol_id': statement.receive_binding.symbol_id,
                    'display_name': statement.receive_binding.display_name,
                    'value_type': statement.receive_binding.value_type,
                    'kind': 'message',
                }
                compiled.append(instruction(statement, 'control.listen', {
                    'event_source': {
                        'kind': 'message',
                        'name': _lower_value(statement.event_source.name),
                        'sender': (
                            _lower_value(statement.event_source.sender)
                            if statement.event_source.sender is not None else None
                        ),
                    },
                    'receive_slot': statement.receive_binding.symbol_id,
                    'condition': (
                        _lower_value(statement.condition)
                        if statement.condition is not None else None
                    ),
                    'handler_function_id': statement.handler_function_id,
                    'handler_arguments': {
                        key: _lower_value(value)
                        for key, value in sorted(statement.handler_arguments.items())
                    },
                    'dispatch': {'serial': True, 'fifo': True, 'safe_checkpoint': True},
                }))
                continue
            raise _LoweringError('', f'尚未实现语句类型：{statement.kind}')
        return compiled

    try:
        instructions = compile_block(document.function.statements, 'function.statements')
    except _LoweringError as exc:
        diagnostic = ProgramDiagnostic(
            code='PGM-COMPILE-001',
            severity='error',
            message=str(exc),
            function_id=function_id,
            value_id=exc.value_id,
        )
        return {'valid': False, 'ecir': None, 'diagnostics': [diagnostic.to_dict()]}

    call_statements = [
        statement for statement in _walk(document.function.statements)
        if isinstance(statement, CallStatement)
    ]
    contracts = [
        require_contract(registry, statement.function_id)
        for statement in call_statements
    ]
    has_listener = any(isinstance(statement, ListenStatement) for statement in _walk(
        document.function.statements,
    ))
    minimum_android_api = max(
        (contract_minimum_android_api(contract) for contract in contracts),
        default=21,
    )
    if has_listener:
        minimum_android_api = max(minimum_android_api, 23)
    api_requirement_groups: dict[tuple[str, int], list[str]] = {}
    for statement, contract in zip(call_statements, contracts, strict=True):
        floor = contract_minimum_android_api(contract)
        if floor > 21:
            api_requirement_groups.setdefault((contract.function_id, floor), []).append(
                statement.statement_id,
            )
    android_api_requirements = [
        {
            'kind': 'function',
            'contract_function_id': contract_id,
            'display_name': require_contract(registry, contract_id).qualified_name,
            'minimum_android_api': floor,
            'statement_ids': sorted(statement_ids),
        }
        for (contract_id, floor), statement_ids in sorted(api_requirement_groups.items())
    ]
    listener_ids = sorted(
        statement.statement_id for statement in _walk(document.function.statements)
        if isinstance(statement, ListenStatement)
    )
    if listener_ids:
        android_api_requirements.append({
            'kind': 'language_feature',
            'feature_id': 'program.listen.message',
            'display_name': '消息监听',
            'minimum_android_api': 23,
            'statement_ids': listener_ids,
        })
    capabilities = sorted({
        capability for contract in contracts for capability in contract_capabilities(contract)
    } | (
        {'messaging'} if has_listener else set()
    ))
    supported = (
        sorted(set.intersection(*(set(contract_platforms(contract)) for contract in contracts)))
        if contracts
        else list(VERIFIED_CORE_PLATFORMS)
    )
    document_revision = content_revision(canonical_json_bytes(document))
    pure_registry = pure_operation_registry_payload()
    ecir = {
        'ecir_version': ECIR_VERSION,
        'program_model_version': PROGRAM_MODEL_VERSION,
        'document_id': document.document_id,
        'source_revision': document_revision,
        'pure_operation_registry': {
            'registry_version': pure_registry['registry_version'],
            'content_hash': pure_operation_registry_hash(),
        },
        'target_platform': target_platform,
        'entry_function_id': function_id,
        'functions': [{
            'function_id': function_id,
            'name': document.function.display_name,
            'parameters': [parameter.symbol_id for parameter in document.function.parameters],
            'parameter_definitions': [{
                'parameter_id': parameter.parameter_id,
                'name': parameter.symbol_id,
                'display_name': parameter.display_name,
                'value_type': parameter.value_type,
                'required': parameter.required,
                'default': (
                    _lower_value(parameter.default_value)
                    if parameter.default_value is not None else None
                ),
            } for parameter in document.function.parameters],
            'return_type': document.function.return_type,
            'instructions': instructions,
        }],
        'required_capabilities': capabilities,
        'minimum_android_api': minimum_android_api,
        'android_api_requirements': android_api_requirements,
        'supported_platforms': supported,
        'default_target_id': default_target_id,
        'targets': [targets_by_id[target_id] for target_id in sorted(referenced_target_ids)],
        'project_variables': _project_variable_definitions(project_variables or ()),
        'value_override_slots': sorted(
            value_override_slots,
            key=lambda item: (
                str(item['function_id']), str(item['statement_id']),
                str(item['parameter_id']), str(item['value_id']),
            ),
        ),
        'debug_map': {
            'statements': debug_statements,
            'values': debug_values,
            'symbols': debug_symbols,
        },
    }
    ecir_revision = content_revision(canonical_json_bytes(ecir))
    return {
        'valid': True,
        'ecir': ecir,
        'ecir_revision': ecir_revision,
        'diagnostics': [],
    }


def compile_program_bundle(
    documents: Sequence[ProgramDocument],
    registry: FunctionContractProvider,
    *,
    entry_function_id: str,
    target_platform: str | None = None,
    project_variables: Sequence[Any] | None = None,
    target_definitions: Sequence[Any] | None = None,
    default_target_id: str | None = None,
    network_policies: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Link the reachable project-function closure into one deterministic ECIR."""

    diagnostics: list[ProgramDiagnostic] = []
    by_function: dict[str, ProgramDocument] = {}
    document_ids: set[str] = set()
    duplicate_function_ids: set[str] = set()
    for document in documents:
        function_id = document.function.function_id
        if document.document_id in document_ids:
            diagnostics.append(ProgramDiagnostic(
                code='PGM-LINK-002', severity='error',
                message=f'项目中存在重复文档 ID：{document.document_id}',
                function_id=function_id,
            ))
        document_ids.add(document.document_id)
        if function_id in by_function:
            duplicate_function_ids.add(function_id)
            diagnostics.append(ProgramDiagnostic(
                code='PGM-LINK-003', severity='error',
                message=f'项目中存在重复函数 ID：{function_id}',
                function_id=function_id,
            ))
        else:
            by_function[function_id] = document
    if entry_function_id not in by_function:
        diagnostics.append(ProgramDiagnostic(
            code='PGM-LINK-001', severity='error',
            message=f'入口项目函数不存在：{entry_function_id}',
            function_id=entry_function_id,
        ))
    if diagnostics:
        return {'valid': False, 'ecir': None, 'diagnostics': [item.to_dict() for item in diagnostics]}

    project_contracts = {
        function_id: _project_contract(document)
        for function_id, document in by_function.items()
        if function_id not in duplicate_function_ids
    }
    linked_registry = _LinkedContractRegistry(registry, project_contracts)
    project_function_ids = frozenset(project_contracts)

    # Statement/value identities are workspace-stable, so collisions across
    # documents would make diagnostics and Player bindings ambiguous.
    owned_ids: dict[str, tuple[str, str, str]] = {}
    for function_id, document in sorted(by_function.items()):
        for statement in iter_statement_tree(document.function.statements):
            owners = [(statement.statement_id, statement.statement_id, '')]
            owners.extend(
                (value.value_id, statement.statement_id, value.value_id)
                for value in iter_statement_values(statement)
            )
            for owner_id, statement_id, value_id in owners:
                previous = owned_ids.get(owner_id)
                if previous is not None and previous[0] != function_id:
                    diagnostics.append(ProgramDiagnostic(
                        code='PGM-LINK-004', severity='error',
                        message=f'项目函数之间存在重复稳定 ID：{owner_id}',
                        function_id=function_id,
                        statement_id=statement_id,
                        value_id=value_id,
                    ))
                else:
                    owned_ids[owner_id] = (function_id, statement_id, value_id)
    for variable in project_variables or ():
        pending = [variable.default_value]
        while pending:
            value = pending.pop()
            previous = owned_ids.get(value.value_id)
            if previous is not None:
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-LINK-004', severity='error',
                    message=f'项目变量默认值与程序存在重复稳定 ID：{value.value_id}',
                    function_id=entry_function_id,
                    value_id=value.value_id,
                    field_path=f'project_variables.{variable.variable_id}.default_value',
                ))
            else:
                owned_ids[value.value_id] = ('project_variables', '', value.value_id)
            pending.extend(iter_value_children(value))

    closure: list[str] = []
    state: dict[str, str] = {}

    def visit(function_id: str, stack: tuple[str, ...]) -> None:
        state[function_id] = 'visiting'
        closure.append(function_id)
        document = by_function[function_id]
        for statement in iter_statement_tree(document.function.statements):
            if isinstance(statement, CallStatement):
                callee_id = statement.function_id
                dependency_kind = 'call'
            elif isinstance(statement, ListenStatement):
                callee_id = statement.handler_function_id
                dependency_kind = 'listen'
            else:
                continue
            if callee_id not in by_function:
                if dependency_kind == 'listen':
                    diagnostics.append(ProgramDiagnostic(
                        code='PGM-LISTEN-002', severity='error',
                        message=f'监听处理项目函数不存在：{callee_id}',
                        function_id=function_id,
                        statement_id=statement.statement_id,
                        field_path='handler_function_id',
                    ))
                elif get_contract(registry, callee_id) is None:
                    diagnostics.append(ProgramDiagnostic(
                        code='PGM-LINK-005', severity='error',
                        message=f'调用的函数不存在：{callee_id}',
                        function_id=function_id,
                        statement_id=statement.statement_id,
                        field_path='function_id',
                    ))
                continue
            callee_state = state.get(callee_id)
            if callee_state == 'visiting':
                cycle = ' -> '.join((*stack, function_id, callee_id))
                diagnostics.append(ProgramDiagnostic(
                    code='PGM-LINK-006', severity='error',
                    message=f'项目函数不允许递归或监听处理循环引用：{cycle}',
                    function_id=function_id,
                    statement_id=statement.statement_id,
                    field_path=(
                        'handler_function_id'
                        if dependency_kind == 'listen' else 'function_id'
                    ),
                ))
            elif callee_state is None:
                visit(callee_id, (*stack, function_id))
        state[function_id] = 'visited'

    if entry_function_id in by_function:
        visit(entry_function_id, ())
    diagnostics.extend(_message_consumer_conflicts(tuple(
        by_function[function_id] for function_id in closure
    )))
    if diagnostics:
        return {'valid': False, 'ecir': None, 'diagnostics': [item.to_dict() for item in diagnostics]}

    compiled_documents: list[dict[str, Any]] = []
    for function_id in closure:
        compiled = compile_program_document(
            by_function[function_id],
            linked_registry,
            target_platform=target_platform,
            _project_function_ids=project_function_ids,
            project_variables=project_variables,
            target_definitions=target_definitions,
            default_target_id=default_target_id,
            network_policies=network_policies,
            _skip_message_conflict_check=True,
        )
        if not compiled['valid']:
            diagnostics.extend(ProgramDiagnostic(**item) for item in compiled['diagnostics'])
        else:
            compiled_documents.append(compiled)
    if diagnostics:
        return {'valid': False, 'ecir': None, 'diagnostics': [item.to_dict() for item in diagnostics]}

    functions = [item['ecir']['functions'][0] for item in compiled_documents]
    capabilities = sorted({
        capability
        for item in compiled_documents
        for capability in item['ecir']['required_capabilities']
    })
    minimum_android_api = max(
        (int(item['ecir'].get('minimum_android_api') or 21) for item in compiled_documents),
        default=21,
    )
    android_api_requirements = [
        {
            **requirement,
            'source_document_id': item['ecir']['document_id'],
            'source_function_id': item['ecir']['entry_function_id'],
        }
        for item in compiled_documents
        for requirement in item['ecir'].get('android_api_requirements') or []
    ]
    platform_sets = [set(item['ecir']['supported_platforms']) for item in compiled_documents]
    supported_platforms = (
        sorted(set.intersection(*platform_sets))
        if platform_sets else list(VERIFIED_CORE_PLATFORMS)
    )
    debug_statements: dict[str, Any] = {}
    debug_values: dict[str, Any] = {}
    debug_symbols: dict[str, Any] = {}
    for item in compiled_documents:
        debug_statements.update(item['ecir']['debug_map']['statements'])
        debug_values.update(item['ecir']['debug_map']['values'])
        debug_symbols.update(item['ecir']['debug_map'].get('symbols') or {})
    source_revision = content_revision(canonical_json_bytes([
        by_function[function_id].model_dump(mode='json') for function_id in closure
    ]))
    pure_registry = pure_operation_registry_payload()
    ecir = {
        'ecir_version': ECIR_VERSION,
        'program_model_version': PROGRAM_MODEL_VERSION,
        'document_id': by_function[entry_function_id].document_id,
        'source_revision': source_revision,
        'pure_operation_registry': {
            'registry_version': pure_registry['registry_version'],
            'content_hash': pure_operation_registry_hash(),
        },
        'target_platform': target_platform,
        'entry_function_id': entry_function_id,
        'functions': functions,
        'required_capabilities': capabilities,
        'minimum_android_api': minimum_android_api,
        'android_api_requirements': android_api_requirements,
        'supported_platforms': supported_platforms,
        'default_target_id': default_target_id,
        'targets': sorted(
            {
                str(target.get('target_id')): target
                for item in compiled_documents
                for target in (item['ecir'].get('targets') or [])
            }.values(),
            key=lambda item: str(item.get('target_id') or ''),
        ),
        'project_variables': _project_variable_definitions(project_variables or ()),
        'value_override_slots': sorted(
            (
                copy_slot
                for item in compiled_documents
                for copy_slot in item['ecir'].get('value_override_slots') or []
            ),
            key=lambda item: (
                str(item['function_id']), str(item['statement_id']),
                str(item['parameter_id']), str(item['value_id']),
            ),
        ),
        'debug_map': {
            'statements': debug_statements,
            'values': debug_values,
            'symbols': debug_symbols,
        },
    }
    return {
        'valid': True,
        'ecir': ecir,
        'ecir_revision': content_revision(canonical_json_bytes(ecir)),
        'diagnostics': [],
    }


__all__ = [
    'ECIR_VERSION',
    'PROGRAM_MODEL_VERSION',
    'compile_program_bundle',
    'compile_program_document',
    'linked_function_registry',
    'lower_value_node',
    'project_function_contract',
]
