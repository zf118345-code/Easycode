"""Typed, source-free ProgramDocument contracts for project format 6.

ProgramDocument is the only editable program fact. Every configurable value
is a stable, recursively typed node; display text never participates in
execution identity.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, time
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

PROGRAM_DOCUMENT_SCHEMA_VERSION = 1

StableId: TypeAlias = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=160, pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$'),
]
DisplayName: TypeAlias = Annotated[StrictStr, StringConstraints(min_length=1, max_length=160)]
TypeId: TypeAlias = Annotated[StrictStr, StringConstraints(min_length=1, max_length=240)]
Number: TypeAlias = StrictInt | StrictFloat


def new_stable_id(prefix: str) -> str:
    if not prefix or not prefix.replace('_', '').isalnum():
        raise ValueError('stable ID prefix must contain only letters, digits, or underscores')
    return f'{prefix}_{uuid.uuid4().hex}'


class ProgramModel(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True, allow_inf_nan=False)


class UnsetValue(ProgramModel):
    value_id: StableId
    kind: Literal['unset'] = 'unset'
    expected_type: TypeId


class NullValue(ProgramModel):
    value_id: StableId
    kind: Literal['null'] = 'null'


class StringValue(ProgramModel):
    value_id: StableId
    kind: Literal['string'] = 'string'
    value: StrictStr


class IntValue(ProgramModel):
    value_id: StableId
    kind: Literal['int64'] = 'int64'
    value: StrictInt


class FloatValue(ProgramModel):
    value_id: StableId
    kind: Literal['float64'] = 'float64'
    value: StrictFloat


class BoolValue(ProgramModel):
    value_id: StableId
    kind: Literal['bool'] = 'bool'
    value: StrictBool


class DateValue(ProgramModel):
    value_id: StableId
    kind: Literal['date'] = 'date'
    value: date


class DateTimeValue(ProgramModel):
    value_id: StableId
    kind: Literal['datetime'] = 'datetime'
    value: datetime


class TimeValue(ProgramModel):
    value_id: StableId
    kind: Literal['time'] = 'time'
    value: time


class DurationValue(ProgramModel):
    value_id: StableId
    kind: Literal['duration'] = 'duration'
    milliseconds: Annotated[StrictInt, Field(ge=0)]


class PointLiteral(ProgramModel):
    x: Number
    y: Number


class PointValue(ProgramModel):
    value_id: StableId
    kind: Literal['point'] = 'point'
    x: Number
    y: Number


class RectValue(ProgramModel):
    value_id: StableId
    kind: Literal['rect'] = 'rect'
    x: Number
    y: Number
    width: Annotated[Number, Field(ge=0)]
    height: Annotated[Number, Field(ge=0)]


class PathValue(ProgramModel):
    value_id: StableId
    kind: Literal['path'] = 'path'
    points: Annotated[tuple[PointLiteral, ...], Field(min_length=1)]


class SymbolReferenceValue(ProgramModel):
    value_id: StableId
    kind: Literal['symbol_ref'] = 'symbol_ref'
    symbol_id: StableId
    value_type: TypeId


class ProjectVariableReferenceValue(ProgramModel):
    value_id: StableId
    kind: Literal['project_variable_ref'] = 'project_variable_ref'
    variable_id: StableId
    value_type: TypeId


class AssetReferenceValue(ProgramModel):
    value_id: StableId
    kind: Literal['asset_ref'] = 'asset_ref'
    asset_id: StableId
    asset_kind: TypeId = 'image'


class TargetReferenceValue(ProgramModel):
    value_id: StableId
    kind: Literal['target_ref'] = 'target_ref'
    target_id: StableId


class EntityReferenceValue(ProgramModel):
    """Stable references such as control, instance, application, or function."""

    value_id: StableId
    kind: Literal['entity_ref'] = 'entity_ref'
    reference_id: StableId
    reference_type: TypeId


class MemberAccessValue(ProgramModel):
    value_id: StableId
    kind: Literal['member_access'] = 'member_access'
    source: ValueNode
    field_id: StableId
    result_type: TypeId


class ListValue(ProgramModel):
    value_id: StableId
    kind: Literal['list'] = 'list'
    item_type: TypeId
    items: tuple[ValueNode, ...] = ()


class MapEntry(ProgramModel):
    key: ValueNode
    value: ValueNode


class MapValue(ProgramModel):
    value_id: StableId
    kind: Literal['map'] = 'map'
    key_type: TypeId
    entry_value_type: TypeId
    entries: tuple[MapEntry, ...] = ()
    duplicate_policy: Literal['error'] = 'error'


class RecordValue(ProgramModel):
    value_id: StableId
    kind: Literal['record'] = 'record'
    record_type: TypeId
    fields: dict[StableId, ValueNode] = Field(default_factory=dict)


def _validate_json_payload(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('JSON numbers must be finite')
        return value
    if isinstance(value, list):
        for item in value:
            _validate_json_payload(item)
        return value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError('JSON object keys must be strings')
        for item in value.values():
            _validate_json_payload(item)
        return value
    raise ValueError(f'unsupported JSON value: {type(value).__name__}')


class JsonValue(ProgramModel):
    value_id: StableId
    kind: Literal['json'] = 'json'
    payload: Any

    @field_validator('payload')
    @classmethod
    def validate_payload(cls, value: Any) -> Any:
        return _validate_json_payload(value)


class PureOperationValue(ProgramModel):
    value_id: StableId
    kind: Literal['operation'] = 'operation'
    operation_id: StableId
    result_type: TypeId
    inputs: dict[StableId, ValueNode] = Field(default_factory=dict)


class SelectorBinding(ProgramModel):
    """One lexically scoped, pure collection-expression binding.

    ``symbol_id`` is execution identity; ``display_name`` is presentation only.
    Roles are deliberately closed so a selector cannot smuggle arbitrary
    locals or a callable into the value tree.
    """

    symbol_id: StableId
    role: Literal['item', 'index', 'key', 'value']
    display_name: DisplayName
    value_type: TypeId


class SelectorValue(ProgramModel):
    """A pure expression evaluated once for each item/key-value snapshot row."""

    value_id: StableId
    kind: Literal['selector'] = 'selector'
    bindings: Annotated[tuple[SelectorBinding, ...], Field(min_length=1, max_length=2)]
    result_type: TypeId
    expression: ValueNode

    @model_validator(mode='after')
    def validate_binding_roles(self) -> SelectorValue:
        roles = [binding.role for binding in self.bindings]
        if len(set(roles)) != len(roles):
            raise ValueError('selector binding roles must be unique')
        if set(roles) not in ({'item', 'index'}, {'key', 'value'}):
            raise ValueError('selector bindings must be item/index or key/value')
        by_role = {binding.role: binding for binding in self.bindings}
        if 'index' in by_role and by_role['index'].value_type != 'int64':
            raise ValueError('selector index binding must be int64')
        return self


class ComparisonValue(ProgramModel):
    value_id: StableId
    kind: Literal['compare'] = 'compare'
    operator: Literal['eq', 'ne', 'lt', 'lte', 'gt', 'gte']
    left: ValueNode
    right: ValueNode


class ConditionGroupValue(ProgramModel):
    value_id: StableId
    kind: Literal['condition_group'] = 'condition_group'
    operator: Literal['all', 'any']
    conditions: Annotated[tuple[ValueNode, ...], Field(min_length=1)]


class NotValue(ProgramModel):
    value_id: StableId
    kind: Literal['not'] = 'not'
    condition: ValueNode


ValueNode: TypeAlias = Annotated[
    UnsetValue
    | NullValue
    | StringValue
    | IntValue
    | FloatValue
    | BoolValue
    | DateValue
    | DateTimeValue
    | TimeValue
    | DurationValue
    | PointValue
    | RectValue
    | PathValue
    | SymbolReferenceValue
    | ProjectVariableReferenceValue
    | AssetReferenceValue
    | TargetReferenceValue
    | EntityReferenceValue
    | MemberAccessValue
    | ListValue
    | MapValue
    | RecordValue
    | JsonValue
    | PureOperationValue
    | SelectorValue
    | ComparisonValue
    | ConditionGroupValue
    | NotValue,
    Field(discriminator='kind'),
]

_VALUE_NAMESPACE = {'ValueNode': ValueNode}
for _recursive_value in (
    MemberAccessValue,
    ListValue,
    MapEntry,
    MapValue,
    RecordValue,
    PureOperationValue,
    SelectorValue,
    ComparisonValue,
    ConditionGroupValue,
    NotValue,
):
    _recursive_value.model_rebuild(_types_namespace=_VALUE_NAMESPACE)


class ProgramParameter(ProgramModel):
    parameter_id: StableId
    symbol_id: StableId
    display_name: DisplayName
    value_type: TypeId
    required: bool = True
    default_value: ValueNode | None = None


class ResultBinding(ProgramModel):
    symbol_id: StableId
    display_name: DisplayName
    value_type: TypeId
    declare: bool = True


class LocalAssignmentTarget(ProgramModel):
    kind: Literal['local'] = 'local'
    symbol_id: StableId
    display_name: DisplayName
    value_type: TypeId
    declare: bool = True


class ProjectVariableAssignmentTarget(ProgramModel):
    kind: Literal['project_variable'] = 'project_variable'
    variable_id: StableId
    value_type: TypeId


AssignmentTarget: TypeAlias = Annotated[
    LocalAssignmentTarget | ProjectVariableAssignmentTarget,
    Field(discriminator='kind'),
]


class CallStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['call'] = 'call'
    function_id: StableId
    arguments: dict[StableId, ValueNode] = Field(default_factory=dict)
    result_binding: ResultBinding | None = None
    step_label: str | None = None
    author_review_fingerprint: str | None = None


class AssignmentStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['assignment'] = 'assignment'
    target: AssignmentTarget
    value: ValueNode
    step_label: str | None = None


class ConditionalBranch(ProgramModel):
    branch_id: StableId
    condition: ValueNode
    statements: tuple[Statement, ...] = ()


class IfStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['if'] = 'if'
    condition: ValueNode
    then_statements: tuple[Statement, ...] = ()
    additional_branches: tuple[ConditionalBranch, ...] = ()
    otherwise_statements: tuple[Statement, ...] = ()
    step_label: str | None = None


class LoopBinding(ProgramModel):
    symbol_id: StableId
    display_name: DisplayName
    value_type: TypeId


class LoopStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['loop'] = 'loop'
    mode: Literal['repeat', 'while', 'for_each', 'for_each_map']
    source: ValueNode
    body: tuple[Statement, ...] = ()
    item_binding: LoopBinding | None = None
    index_binding: LoopBinding | None = None
    key_binding: LoopBinding | None = None
    value_binding: LoopBinding | None = None
    step_label: str | None = None

    @model_validator(mode='after')
    def validate_bindings(self) -> LoopStatement:
        if self.mode == 'for_each' and self.item_binding is None:
            raise ValueError('for_each loop requires item_binding')
        if self.mode == 'for_each_map' and (self.key_binding is None or self.value_binding is None):
            raise ValueError('for_each_map loop requires key_binding and value_binding')
        if self.mode in {'repeat', 'while'} and any((
            self.item_binding,
            self.index_binding,
            self.key_binding,
            self.value_binding,
        )):
            raise ValueError(f'{self.mode} loop cannot declare collection bindings')
        return self


class BreakStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['break'] = 'break'
    step_label: str | None = None


class ContinueStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['continue'] = 'continue'
    step_label: str | None = None


class ReturnStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['return'] = 'return'
    value: ValueNode | None = None
    step_label: str | None = None


class FailStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['fail'] = 'fail'
    error_id: StableId
    message: ValueNode
    details: ValueNode | None = None
    step_label: str | None = None


class RetryPolicy(ProgramModel):
    max_retries: ValueNode
    interval: ValueNode
    transient_only: Literal[True] = True
    author_review_fingerprint: str | None = None


class CatchClause(ProgramModel):
    catch_id: StableId
    error_ids: tuple[StableId, ...] = ()
    error_binding: LoopBinding | None = None
    statements: tuple[Statement, ...] = ()


class TryStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['try'] = 'try'
    body: tuple[Statement, ...] = ()
    retry_policy: RetryPolicy | None = None
    catches: tuple[CatchClause, ...] = ()
    finally_statements: tuple[Statement, ...] = ()
    step_label: str | None = None


class TargetScopeStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['target_scope'] = 'target_scope'
    target: ValueNode
    body: tuple[Statement, ...] = ()
    step_label: str | None = None


class MessageEventSource(ProgramModel):
    kind: Literal['message'] = 'message'
    name: ValueNode
    sender: ValueNode | None = None


class ListenStatement(ProgramModel):
    statement_id: StableId
    kind: Literal['listen'] = 'listen'
    event_source: MessageEventSource
    receive_binding: LoopBinding
    condition: ValueNode | None = None
    handler_function_id: StableId
    handler_arguments: dict[StableId, ValueNode] = Field(default_factory=dict)
    step_label: str | None = None


Statement: TypeAlias = Annotated[
    CallStatement
    | AssignmentStatement
    | IfStatement
    | LoopStatement
    | BreakStatement
    | ContinueStatement
    | ReturnStatement
    | FailStatement
    | TryStatement
    | TargetScopeStatement
    | ListenStatement,
    Field(discriminator='kind'),
]

_STATEMENT_NAMESPACE = {'Statement': Statement, 'ValueNode': ValueNode}
for _recursive_statement in (
    ConditionalBranch,
    IfStatement,
    LoopStatement,
    CatchClause,
    TryStatement,
    TargetScopeStatement,
):
    _recursive_statement.model_rebuild(_types_namespace=_STATEMENT_NAMESPACE)


class ProgramFunction(ProgramModel):
    function_id: StableId
    display_name: DisplayName
    parameters: tuple[ProgramParameter, ...] = ()
    return_type: TypeId = 'null'
    statements: tuple[Statement, ...] = ()


def iter_value_children(value: ValueNode) -> tuple[ValueNode, ...]:
    if isinstance(value, MemberAccessValue):
        return (value.source,)
    if isinstance(value, ListValue):
        return value.items
    if isinstance(value, MapValue):
        return tuple(child for entry in value.entries for child in (entry.key, entry.value))
    if isinstance(value, RecordValue):
        return tuple(value.fields.values())
    if isinstance(value, PureOperationValue):
        return tuple(value.inputs.values())
    if isinstance(value, SelectorValue):
        return (value.expression,)
    if isinstance(value, ComparisonValue):
        return (value.left, value.right)
    if isinstance(value, ConditionGroupValue):
        return value.conditions
    if isinstance(value, NotValue):
        return (value.condition,)
    return ()


def statement_child_blocks(statement: Statement) -> tuple[tuple[Statement, ...], ...]:
    if isinstance(statement, IfStatement):
        return (
            statement.then_statements,
            *(branch.statements for branch in statement.additional_branches),
            statement.otherwise_statements,
        )
    if isinstance(statement, LoopStatement):
        return (statement.body,)
    if isinstance(statement, TryStatement):
        return (
            statement.body,
            *(clause.statements for clause in statement.catches),
            statement.finally_statements,
        )
    if isinstance(statement, TargetScopeStatement):
        return (statement.body,)
    return ()


class ProgramDocument(ProgramModel):
    schema_version: Literal[PROGRAM_DOCUMENT_SCHEMA_VERSION] = PROGRAM_DOCUMENT_SCHEMA_VERSION
    document_id: StableId
    function: ProgramFunction

    @model_validator(mode='after')
    def validate_stable_id_uniqueness(self) -> ProgramDocument:
        ids: dict[str, str] = {}

        def remember(value: str, owner: str) -> None:
            previous = ids.get(value)
            if previous is not None:
                raise ValueError(f'duplicate stable ID {value!r}: {previous} and {owner}')
            ids[value] = owner

        def binding(binding_value: ResultBinding | LoopBinding | LocalAssignmentTarget, owner: str) -> None:
            if not isinstance(binding_value, (ResultBinding, LocalAssignmentTarget)) or binding_value.declare:
                remember(binding_value.symbol_id, owner)

        def visit_value(value: ValueNode, owner: str) -> None:
            remember(value.value_id, owner)
            if isinstance(value, SelectorValue):
                for index, item in enumerate(value.bindings):
                    remember(item.symbol_id, f'{owner}.selector_binding[{index}]')
            for index, child in enumerate(iter_value_children(value)):
                visit_value(child, f'{owner}.value[{index}]')

        def visit_statement(statement: Statement, owner: str) -> None:
            remember(statement.statement_id, owner)
            if isinstance(statement, CallStatement):
                for parameter_id, value in statement.arguments.items():
                    visit_value(value, f'{owner}.arguments.{parameter_id}')
                if statement.result_binding is not None:
                    binding(statement.result_binding, f'{owner}.result')
            elif isinstance(statement, AssignmentStatement):
                visit_value(statement.value, f'{owner}.value')
                if isinstance(statement.target, LocalAssignmentTarget):
                    binding(statement.target, f'{owner}.target')
            elif isinstance(statement, IfStatement):
                visit_value(statement.condition, f'{owner}.condition')
                for branch_index, branch in enumerate(statement.additional_branches):
                    remember(branch.branch_id, f'{owner}.branch[{branch_index}]')
                    visit_value(branch.condition, f'{owner}.branch[{branch_index}].condition')
            elif isinstance(statement, LoopStatement):
                visit_value(statement.source, f'{owner}.source')
                for name in ('item_binding', 'index_binding', 'key_binding', 'value_binding'):
                    item = getattr(statement, name)
                    if item is not None:
                        binding(item, f'{owner}.{name}')
            elif isinstance(statement, ReturnStatement):
                if statement.value is not None:
                    visit_value(statement.value, f'{owner}.value')
            elif isinstance(statement, FailStatement):
                visit_value(statement.message, f'{owner}.message')
                if statement.details is not None:
                    visit_value(statement.details, f'{owner}.details')
            elif isinstance(statement, TryStatement):
                if statement.retry_policy is not None:
                    visit_value(statement.retry_policy.max_retries, f'{owner}.retry.max_retries')
                    visit_value(statement.retry_policy.interval, f'{owner}.retry.interval')
                for catch_index, clause in enumerate(statement.catches):
                    remember(clause.catch_id, f'{owner}.catch[{catch_index}]')
                    if clause.error_binding is not None:
                        binding(clause.error_binding, f'{owner}.catch[{catch_index}].error')
            elif isinstance(statement, TargetScopeStatement):
                visit_value(statement.target, f'{owner}.target')
            elif isinstance(statement, ListenStatement):
                binding(statement.receive_binding, f'{owner}.receive')
                visit_value(statement.event_source.name, f'{owner}.event.name')
                if statement.event_source.sender is not None:
                    visit_value(statement.event_source.sender, f'{owner}.event.sender')
                if statement.condition is not None:
                    visit_value(statement.condition, f'{owner}.condition')
                for parameter_id, value in statement.handler_arguments.items():
                    visit_value(value, f'{owner}.handler_arguments.{parameter_id}')
            for block_index, block in enumerate(statement_child_blocks(statement)):
                for child_index, child in enumerate(block):
                    visit_statement(child, f'{owner}.block[{block_index}][{child_index}]')

        remember(self.document_id, 'document')
        remember(self.function.function_id, 'function')
        for parameter in self.function.parameters:
            remember(parameter.parameter_id, f'parameter {parameter.display_name}')
            remember(parameter.symbol_id, f'parameter symbol {parameter.display_name}')
            if parameter.default_value is not None:
                visit_value(parameter.default_value, f'parameter default {parameter.display_name}')
        for index, statement in enumerate(self.function.statements):
            visit_statement(statement, f'function.statements[{index}]')
        return self


def create_program_document(
    display_name: str,
    *,
    function_id: str | None = None,
    document_id: str | None = None,
) -> ProgramDocument:
    resolved_function_id = function_id or new_stable_id('func')
    return ProgramDocument(
        document_id=document_id or new_stable_id('doc'),
        function=ProgramFunction(function_id=resolved_function_id, display_name=display_name),
    )


def value_type(value: ValueNode) -> str:
    if isinstance(value, UnsetValue):
        return value.expected_type
    if isinstance(value, NullValue):
        return 'null'
    if isinstance(value, (StringValue, IntValue, FloatValue, BoolValue)):
        return value.kind
    if isinstance(value, (DateValue, DateTimeValue, TimeValue, DurationValue)):
        return value.kind
    if isinstance(value, (PointValue, RectValue, PathValue)):
        return value.kind
    if isinstance(value, (SymbolReferenceValue, ProjectVariableReferenceValue)):
        return value.value_type
    if isinstance(value, AssetReferenceValue):
        return f'asset_ref<{value.asset_kind}>'
    if isinstance(value, TargetReferenceValue):
        return 'target_ref'
    if isinstance(value, EntityReferenceValue):
        return value.reference_type
    if isinstance(value, (MemberAccessValue, PureOperationValue)):
        return value.result_type
    if isinstance(value, SelectorValue):
        by_role = {item.role: item.value_type for item in value.bindings}
        if set(by_role) == {'item', 'index'}:
            return f'list_selector<{by_role["item"]},{value.result_type}>'
        return f'map_selector<{by_role["key"]},{by_role["value"]},{value.result_type}>'
    if isinstance(value, ListValue):
        return f'list<{value.item_type}>'
    if isinstance(value, MapValue):
        return f'map<{value.key_type},{value.entry_value_type}>'
    if isinstance(value, RecordValue):
        return value.record_type
    if isinstance(value, JsonValue):
        return 'json_value'
    return 'bool'


def value_from_python(value: Any, *, value_id: str | None = None) -> ValueNode:
    resolved_id = value_id or new_stable_id('value')
    if value is None:
        return NullValue(value_id=resolved_id)
    if isinstance(value, bool):
        return BoolValue(value_id=resolved_id, value=value)
    if isinstance(value, int):
        return IntValue(value_id=resolved_id, value=value)
    if isinstance(value, float):
        return FloatValue(value_id=resolved_id, value=value)
    if isinstance(value, str):
        return StringValue(value_id=resolved_id, value=value)
    raise TypeError(f'no literal value node for {type(value).__name__}')


__all__ = [
    'AssetReferenceValue', 'AssignmentStatement', 'AssignmentTarget', 'BoolValue',
    'CallStatement', 'CatchClause', 'ComparisonValue', 'ConditionGroupValue',
    'ConditionalBranch', 'DateTimeValue', 'DateValue', 'DurationValue',
    'EntityReferenceValue', 'FloatValue', 'IfStatement', 'IntValue', 'JsonValue',
    'ListValue', 'ListenStatement', 'LocalAssignmentTarget', 'LoopBinding',
    'LoopStatement', 'MapEntry', 'MapValue', 'MemberAccessValue', 'MessageEventSource',
    'NotValue', 'NullValue', 'PathValue', 'PointLiteral', 'PointValue',
    'ProgramDocument', 'ProgramFunction', 'ProgramParameter',
    'ProjectVariableAssignmentTarget', 'ProjectVariableReferenceValue',
    'PureOperationValue', 'RecordValue', 'RectValue', 'ResultBinding', 'RetryPolicy',
    'SelectorBinding', 'SelectorValue',
    'ReturnStatement', 'Statement', 'StringValue', 'SymbolReferenceValue',
    'TargetReferenceValue', 'TargetScopeStatement', 'TimeValue', 'TryStatement',
    'UnsetValue', 'ValueNode', 'create_program_document', 'iter_value_children',
    'new_stable_id', 'statement_child_blocks', 'value_from_python', 'value_type',
]
