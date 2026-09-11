"""Pure structural commands for format-6 ProgramDocument editing."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .program_contracts import (
    FunctionContractProvider,
    contract_parameter,
    parameter_has_default,
    require_contract,
)
from .program_types import (
    AssignmentStatement,
    BoolValue,
    BreakStatement,
    CallStatement,
    CatchClause,
    ComparisonValue,
    DurationValue,
    ContinueStatement,
    FailStatement,
    IfStatement,
    IntValue,
    JsonValue,
    ListenStatement,
    ListValue,
    LocalAssignmentTarget,
    LoopBinding,
    LoopStatement,
    MapEntry,
    MapValue,
    MessageEventSource,
    NullValue,
    NotValue,
    ProgramDocument,
    ProjectVariableAssignmentTarget,
    RecordValue,
    ResultBinding,
    RetryPolicy,
    ReturnStatement,
    Statement,
    StringValue,
    SymbolReferenceValue,
    TargetScopeStatement,
    TryStatement,
    UnsetValue,
    ValueNode,
    new_stable_id,
    value_from_python,
)
from .program_validation import (
    dangerous_call_review_fingerprint,
    iter_statement_tree,
    retry_body_has_side_effects,
    retry_review_fingerprint,
    validate_program_document,
)


class ProgramCommandError(ValueError):
    """A structural command could not be applied without corrupting meaning."""


class ProgramReferenceError(ProgramCommandError):
    """A command would leave an invalid local-symbol reference."""


@dataclass(frozen=True, slots=True)
class StatementLocation:
    """Stable insertion target.

    Root statements use ``parent_statement_id=None`` and ``block='root'``.
    ``clause_id`` selects an additional branch or catch clause when needed.
    ``before_statement_id=None`` appends to the selected block.
    """

    parent_statement_id: str | None = None
    block: Literal[
        'root', 'then', 'otherwise', 'additional_branch', 'body', 'catch', 'finally'
    ] = 'root'
    clause_id: str | None = None
    before_statement_id: str | None = None

    def __post_init__(self) -> None:
        if self.parent_statement_id is None and self.block != 'root':
            raise ValueError('root insertion requires block="root"')
        if self.parent_statement_id is not None and self.block == 'root':
            raise ValueError('nested insertion requires a child block')
        if self.block in {'additional_branch', 'catch'} and not self.clause_id:
            raise ValueError(f'{self.block} insertion requires clause_id')


@dataclass(frozen=True, slots=True)
class ProgramEditResult:
    document: ProgramDocument
    selected_statement_id: str
    created_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _StatementCursor:
    container: list[dict]
    index: int
    statement: dict


def _child_blocks(statement: dict) -> list[list[dict]]:
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


def _find_statement(statements: list[dict], statement_id: str) -> _StatementCursor | None:
    for index, statement in enumerate(statements):
        if statement.get('statement_id') == statement_id:
            return _StatementCursor(statements, index, statement)
        for block in _child_blocks(statement):
            found = _find_statement(block, statement_id)
            if found is not None:
                return found
    return None


def _descendant_statement_ids(statement: dict) -> set[str]:
    ids = {str(statement.get('statement_id') or '')}
    for block in _child_blocks(statement):
        for child in block:
            ids.update(_descendant_statement_ids(child))
    return ids


def _target_block(document: dict, location: StatementLocation) -> list[dict]:
    root = document['function']['statements']
    if location.parent_statement_id is None:
        return root
    parent = _find_statement(root, location.parent_statement_id)
    if parent is None:
        raise ProgramCommandError(f'target parent statement not found: {location.parent_statement_id}')
    statement = parent.statement
    kind = statement.get('kind')
    if kind == 'if' and location.block in {'then', 'otherwise'}:
        return statement['then_statements' if location.block == 'then' else 'otherwise_statements']
    if kind == 'if' and location.block == 'additional_branch':
        branch = next(
            (item for item in statement.get('additional_branches') or []
             if item.get('branch_id') == location.clause_id),
            None,
        )
        if branch is not None:
            return branch['statements']
    if kind in {'loop', 'target_scope'} and location.block == 'body':
        return statement['body']
    if kind == 'try' and location.block == 'body':
        return statement['body']
    if kind == 'try' and location.block == 'finally':
        return statement['finally_statements']
    if kind == 'try' and location.block == 'catch':
        clause = next(
            (item for item in statement.get('catches') or []
             if item.get('catch_id') == location.clause_id),
            None,
        )
        if clause is not None:
            return clause['statements']
    raise ProgramCommandError('the selected parent does not own the requested statement block')


def _insert_into(block: list[dict], statement: dict, before_statement_id: str | None) -> None:
    if before_statement_id is None:
        block.append(statement)
        return
    for index, existing in enumerate(block):
        if existing.get('statement_id') == before_statement_id:
            block.insert(index, statement)
            return
    raise ProgramCommandError(f'target statement not found in selected block: {before_statement_id}')


def _validate_command_result(
    raw: dict,
    registry: FunctionContractProvider | None = None,
) -> ProgramDocument:
    candidate = ProgramDocument.model_validate(raw)
    diagnostics = tuple(
        item
        for item in validate_program_document(candidate, registry)
        # An unreviewed retry risk is a valid editable draft.  Compiler Service
        # remains the gate that rejects it until the dedicated review command
        # records a server-computed fingerprint.
        if item.code not in {'PGM-TRY-003', 'PGM-DANGER-001'}
    )
    if diagnostics:
        details = '; '.join(item.message for item in diagnostics)
        if any(item.code.startswith('PGM-REF-') for item in diagnostics):
            raise ProgramReferenceError(details)
        raise ProgramCommandError(details)
    return candidate


def _default_value(parameter) -> ValueNode:
    if not parameter_has_default(parameter):
        return UnsetValue(value_id=new_stable_id('value'), expected_type=parameter.value_type)
    if parameter.value_type == 'duration':
        raw = parameter.default
        milliseconds = raw.get('milliseconds') if isinstance(raw, dict) else raw
        return DurationValue(value_id=new_stable_id('value'), milliseconds=int(milliseconds))
    raw = parameter.default
    if raw is None:
        return NullValue(value_id=new_stable_id('value'))
    if parameter.value_type.startswith('list<') and isinstance(raw, list):
        item_type = parameter.value_type[5:-1]
        return ListValue(
            value_id=new_stable_id('value'),
            item_type=item_type,
            items=tuple(value_from_python(item) for item in raw),
        )
    if parameter.value_type.startswith('map<') and isinstance(raw, dict):
        key_type, item_type = parameter.value_type[4:-1].split(',', 1)
        return MapValue(
            value_id=new_stable_id('value'),
            key_type=key_type,
            entry_value_type=item_type,
            entries=tuple(
                MapEntry(key=value_from_python(key), value=value_from_python(item))
                for key, item in raw.items()
            ),
        )
    if parameter.value_type == 'json_value':
        return JsonValue(value_id=new_stable_id('value'), payload=raw)
    if isinstance(raw, dict):
        return RecordValue(
            value_id=new_stable_id('value'),
            record_type=parameter.value_type,
            fields={key: value_from_python(item) for key, item in raw.items()},
        )
    return value_from_python(parameter.default)


def _insert_structured_statement(
    document: ProgramDocument,
    statement: Statement,
    location: StatementLocation,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    payload = statement.model_dump(mode='json')
    _insert_into(_target_block(raw, location), payload, location.before_statement_id)
    created = tuple(_owned_ids(payload))
    return ProgramEditResult(
        _validate_command_result(raw, registry),
        statement.statement_id,
        created,
    )


def _owned_ids(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'statement_id', 'value_id', 'branch_id', 'catch_id'} or (
                key == 'symbol_id'
                and 'display_name' in value
                and 'value_type' in value
                and value.get('kind') != 'symbol_ref'
                and value.get('declare', True)
            ):
                result.append(str(item))
            else:
                result.extend(_owned_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_owned_ids(item))
    return result


def insert_call(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    function_id: str,
    *,
    location: StatementLocation = StatementLocation(),
    arguments: Mapping[str, ValueNode] | None = None,
) -> ProgramEditResult:
    """Insert a call skeleton using stable parameter IDs and explicit unset."""

    try:
        contract = require_contract(registry, function_id)
    except KeyError as exc:
        raise ProgramCommandError(f'function contract not found: {function_id}') from exc
    provided = dict(arguments or {})
    allowed = {item.parameter_id for item in contract.parameters}
    unknown = sorted(set(provided) - allowed)
    if unknown:
        raise ProgramCommandError(f'unknown parameters for {function_id}: {", ".join(unknown)}')
    statement_id = new_stable_id('stmt')
    created_ids = [statement_id]
    encoded_arguments: dict[str, dict] = {}
    for parameter in contract.parameters:
        value = provided.get(parameter.parameter_id) or _default_value(parameter)
        encoded_arguments[parameter.parameter_id] = value.model_dump(mode='json')
        created_ids.append(value.value_id)
    statement = {
        'statement_id': statement_id,
        'kind': 'call',
        'function_id': function_id,
        'arguments': encoded_arguments,
        'result_binding': None,
        'step_label': None,
    }
    raw = document.model_dump(mode='json')
    _insert_into(_target_block(raw, location), statement, location.before_statement_id)
    return ProgramEditResult(
        _validate_command_result(raw, registry),
        statement_id,
        tuple(created_ids),
    )


def insert_assignment(
    document: ProgramDocument,
    target: LocalAssignmentTarget | ProjectVariableAssignmentTarget,
    value: ValueNode,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        AssignmentStatement(
            statement_id=new_stable_id('stmt'),
            target=target,
            value=value,
        ),
        location,
    )


def insert_if(
    document: ProgramDocument,
    condition: ValueNode,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        IfStatement(statement_id=new_stable_id('stmt'), condition=condition),
        location,
    )


def insert_if_from_call_result(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    statement_id: str,
    *,
    display_name: str | None = None,
) -> ProgramEditResult:
    """Atomically bind a call result and insert its adjacent typed guard."""

    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    if cursor.statement.get('kind') != 'call':
        raise ProgramCommandError('only call statements can create a result condition')
    function_id = str(cursor.statement.get('function_id') or '')
    try:
        contract = require_contract(registry, function_id)
    except KeyError as exc:
        raise ProgramCommandError(f'function contract not found: {function_id}') from exc
    result_type = str(getattr(contract, 'return_type', '') or '')
    if result_type != 'bool' and not (
        result_type.startswith('optional<') and result_type.endswith('>')
    ):
        raise ProgramCommandError('only bool or optional call results can create a condition')

    created_ids: list[str] = []
    binding = cursor.statement.get('result_binding')
    if binding is None:
        contract_name = str(
            getattr(contract, 'name', '')
            or getattr(contract, 'qualified_name', '')
            or '函数'
        ).split('.')[-1]
        symbol_id = new_stable_id('symbol')
        binding = {
            'symbol_id': symbol_id,
            'display_name': str(display_name or f'{contract_name}结果').strip(),
            'value_type': result_type,
            'declare': True,
        }
        cursor.statement['result_binding'] = binding
        created_ids.append(symbol_id)
    elif str(binding.get('value_type') or '') != result_type:
        raise ProgramCommandError('existing result binding type does not match function contract')

    reference = {
        'value_id': new_stable_id('value'),
        'kind': 'symbol_ref',
        'symbol_id': binding['symbol_id'],
        'value_type': result_type,
    }
    created_ids.append(reference['value_id'])
    if result_type == 'bool':
        condition = reference
    else:
        null_value = {'value_id': new_stable_id('value'), 'kind': 'null'}
        condition = {
            'value_id': new_stable_id('value'),
            'kind': 'compare',
            'operator': 'ne',
            'left': reference,
            'right': null_value,
        }
        created_ids.extend([null_value['value_id'], condition['value_id']])

    if_statement = IfStatement(
        statement_id=new_stable_id('stmt'),
        condition=condition,
    ).model_dump(mode='json')
    created_ids.insert(0, if_statement['statement_id'])
    cursor.container.insert(cursor.index + 1, if_statement)
    return ProgramEditResult(
        _validate_command_result(raw, registry),
        if_statement['statement_id'],
        tuple(created_ids),
    )


def insert_call_and_if(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    function_id: str,
    *,
    location: StatementLocation = StatementLocation(),
    arguments: Mapping[str, ValueNode] | None = None,
    display_name: str | None = None,
) -> ProgramEditResult:
    """Create one ordinary call and its adjacent result guard as one edit."""

    inserted = insert_call(
        document,
        registry,
        function_id,
        location=location,
        arguments=arguments,
    )
    guarded = insert_if_from_call_result(
        inserted.document,
        registry,
        inserted.selected_statement_id,
        display_name=display_name,
    )
    return ProgramEditResult(
        guarded.document,
        guarded.selected_statement_id,
        tuple((*inserted.created_ids, *guarded.created_ids)),
    )


def insert_execute_until(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    condition_function_id: str,
    *,
    location: StatementLocation = StatementLocation(),
    arguments: Mapping[str, ValueNode] | None = None,
    display_name: str | None = None,
    max_attempts: int = 20,
) -> ProgramEditResult:
    """Create a bounded observe-before-act loop from ordinary statements.

    The selected statement is the inner result guard.  A subsequent ordinary
    insertion therefore lands after that guard inside the loop body, which is
    the action slot.  No special Runtime opcode or persisted source syntax is
    introduced.
    """

    if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 100_000:
        raise ProgramCommandError('max_attempts must be between 1 and 100000')
    try:
        contract = require_contract(registry, condition_function_id)
    except KeyError as exc:
        raise ProgramCommandError(
            f'function contract not found: {condition_function_id}'
        ) from exc
    result_type = str(getattr(contract, 'return_type', '') or '')
    if result_type != 'bool' and not (
        result_type.startswith('optional<') and result_type.endswith('>')
    ):
        raise ProgramCommandError(
            'execute-until observation must return bool or optional'
        )

    provided = dict(arguments or {})
    allowed = {item.parameter_id for item in contract.parameters}
    unknown = sorted(set(provided) - allowed)
    if unknown:
        raise ProgramCommandError(
            f'unknown parameters for {condition_function_id}: {", ".join(unknown)}'
        )
    encoded_arguments = {
        parameter.parameter_id: provided.get(parameter.parameter_id) or _default_value(parameter)
        for parameter in contract.parameters
    }

    completed_symbol_id = new_stable_id('symbol')
    observation_symbol_id = new_stable_id('symbol')
    completed_name = '直到条件已满足'
    contract_name = str(
        getattr(contract, 'name', '')
        or getattr(contract, 'qualified_name', '')
        or '条件'
    )
    observation_name = str(display_name or f'{contract_name}结果').strip()

    completed_reference = SymbolReferenceValue(
        value_id=new_stable_id('value'),
        symbol_id=completed_symbol_id,
        value_type='bool',
    )
    observation_reference = SymbolReferenceValue(
        value_id=new_stable_id('value'),
        symbol_id=observation_symbol_id,
        value_type=result_type,
    )
    observation_condition: ValueNode
    if result_type == 'bool':
        observation_condition = observation_reference
    else:
        observation_condition = ComparisonValue(
            value_id=new_stable_id('value'),
            operator='ne',
            left=observation_reference,
            right=NullValue(value_id=new_stable_id('value')),
        )

    declare_completed = AssignmentStatement(
        statement_id=new_stable_id('stmt'),
        target=LocalAssignmentTarget(
            symbol_id=completed_symbol_id,
            display_name=completed_name,
            value_type='bool',
            declare=True,
        ),
        value=BoolValue(value_id=new_stable_id('value'), value=False),
    )
    observation_call = CallStatement(
        statement_id=new_stable_id('stmt'),
        function_id=condition_function_id,
        arguments=encoded_arguments,
        result_binding=ResultBinding(
            symbol_id=observation_symbol_id,
            display_name=observation_name,
            value_type=result_type,
        ),
    )
    mark_completed = AssignmentStatement(
        statement_id=new_stable_id('stmt'),
        target=LocalAssignmentTarget(
            symbol_id=completed_symbol_id,
            display_name=completed_name,
            value_type='bool',
            declare=False,
        ),
        value=BoolValue(value_id=new_stable_id('value'), value=True),
    )
    break_statement = BreakStatement(statement_id=new_stable_id('stmt'))
    result_guard = IfStatement(
        statement_id=new_stable_id('stmt'),
        condition=observation_condition,
        then_statements=(mark_completed, break_statement),
    )
    loop = LoopStatement(
        statement_id=new_stable_id('stmt'),
        mode='repeat',
        source=IntValue(value_id=new_stable_id('value'), value=max_attempts),
        body=(observation_call, result_guard),
    )
    timeout_failure = FailStatement(
        statement_id=new_stable_id('stmt'),
        error_id='ExecuteUntil.ConditionNotMet',
        message=StringValue(
            value_id=new_stable_id('value'),
            value=f'达到最大尝试次数后，{observation_name}仍未满足',
        ),
    )
    timeout_guard = IfStatement(
        statement_id=new_stable_id('stmt'),
        condition=NotValue(
            value_id=new_stable_id('value'),
            condition=completed_reference,
        ),
        then_statements=(timeout_failure,),
    )

    raw = document.model_dump(mode='json')
    target = _target_block(raw, location)
    payloads = [
        declare_completed.model_dump(mode='json'),
        loop.model_dump(mode='json'),
        timeout_guard.model_dump(mode='json'),
    ]
    for payload in payloads:
        _insert_into(target, payload, location.before_statement_id)
    return ProgramEditResult(
        _validate_command_result(raw, registry),
        result_guard.statement_id,
        tuple(item for payload in payloads for item in _owned_ids(payload)),
    )


def insert_loop(
    document: ProgramDocument,
    mode: Literal['repeat', 'while', 'for_each', 'for_each_map'],
    source: ValueNode,
    *,
    item_binding: LoopBinding | None = None,
    index_binding: LoopBinding | None = None,
    key_binding: LoopBinding | None = None,
    value_binding: LoopBinding | None = None,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        LoopStatement(
            statement_id=new_stable_id('stmt'),
            mode=mode,
            source=source,
            item_binding=item_binding,
            index_binding=index_binding,
            key_binding=key_binding,
            value_binding=value_binding,
        ),
        location,
    )


def insert_break(
    document: ProgramDocument,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        BreakStatement(statement_id=new_stable_id('stmt')),
        location,
    )


def insert_continue(
    document: ProgramDocument,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        ContinueStatement(statement_id=new_stable_id('stmt')),
        location,
    )


def insert_return(
    document: ProgramDocument,
    value: ValueNode | None = None,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        ReturnStatement(statement_id=new_stable_id('stmt'), value=value),
        location,
    )


def insert_fail(
    document: ProgramDocument,
    error_id: str,
    message: ValueNode,
    *,
    details: ValueNode | None = None,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        FailStatement(
            statement_id=new_stable_id('stmt'),
            error_id=error_id,
            message=message,
            details=details,
        ),
        location,
    )


def insert_try(
    document: ProgramDocument,
    *,
    retry_policy: RetryPolicy | None = None,
    catches: tuple[CatchClause, ...] = (),
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    if retry_policy is not None:
        retry_policy = retry_policy.model_copy(update={'author_review_fingerprint': None})
    return _insert_structured_statement(
        document,
        TryStatement(
            statement_id=new_stable_id('stmt'),
            retry_policy=retry_policy,
            catches=catches,
        ),
        location,
    )


def insert_target_scope(
    document: ProgramDocument,
    target: ValueNode,
    *,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        TargetScopeStatement(statement_id=new_stable_id('stmt'), target=target),
        location,
    )


def insert_listen(
    document: ProgramDocument,
    event_source: MessageEventSource,
    receive_binding: LoopBinding,
    handler_function_id: str,
    *,
    condition: ValueNode | None = None,
    handler_arguments: Mapping[str, ValueNode] | None = None,
    location: StatementLocation = StatementLocation(),
) -> ProgramEditResult:
    return _insert_structured_statement(
        document,
        ListenStatement(
            statement_id=new_stable_id('stmt'),
            event_source=event_source,
            receive_binding=receive_binding,
            condition=condition,
            handler_function_id=handler_function_id,
            handler_arguments=dict(handler_arguments or {}),
        ),
        location,
    )


def add_if_branch(
    document: ProgramDocument,
    statement_id: str,
    condition: ValueNode,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None or cursor.statement.get('kind') != 'if':
        raise ProgramCommandError(f'if statement not found: {statement_id}')
    branch_id = new_stable_id('branch')
    cursor.statement.setdefault('additional_branches', []).append({
        'branch_id': branch_id,
        'condition': condition.model_dump(mode='json'),
        'statements': [],
    })
    return ProgramEditResult(
        _validate_command_result(raw),
        statement_id,
        (branch_id, condition.value_id),
    )


def remove_if_branch(
    document: ProgramDocument,
    statement_id: str,
    branch_id: str,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None or cursor.statement.get('kind') != 'if':
        raise ProgramCommandError(f'if statement not found: {statement_id}')
    branches = cursor.statement.get('additional_branches') or []
    branch = next((item for item in branches if item.get('branch_id') == branch_id), None)
    if branch is None:
        raise ProgramCommandError(f'if branch not found: {branch_id}')
    if branch.get('statements'):
        raise ProgramCommandError('只能直接移除空的否则如果分支，请先处理分支内语句')
    cursor.statement['additional_branches'] = [
        item for item in branches if item.get('branch_id') != branch_id
    ]
    return ProgramEditResult(_validate_command_result(raw), statement_id)


def add_catch_clause(
    document: ProgramDocument,
    statement_id: str,
    *,
    error_ids: tuple[str, ...] = (),
    error_binding: LoopBinding | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None or cursor.statement.get('kind') != 'try':
        raise ProgramCommandError(f'try statement not found: {statement_id}')
    catch_id = new_stable_id('catch')
    cursor.statement.setdefault('catches', []).append({
        'catch_id': catch_id,
        'error_ids': list(error_ids),
        'error_binding': (
            error_binding.model_dump(mode='json') if error_binding is not None else None
        ),
        'statements': [],
    })
    created = [catch_id]
    if error_binding is not None:
        created.append(error_binding.symbol_id)
    return ProgramEditResult(
        _validate_command_result(raw),
        statement_id,
        tuple(created),
    )


def update_call_argument(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    statement_id: str,
    parameter_id: str,
    value: ValueNode,
) -> ProgramEditResult:
    """Update one parameter while preserving its existing root ``value_id``."""

    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    if cursor.statement.get('kind') != 'call':
        raise ProgramCommandError('only call statements own function parameters')
    try:
        contract = require_contract(registry, str(cursor.statement.get('function_id') or ''))
    except KeyError:
        raise ProgramCommandError(
            f'function contract not found: {cursor.statement.get("function_id")}'
        ) from None
    parameter = contract_parameter(contract, parameter_id)
    if parameter is None:
        raise ProgramCommandError(f'parameter contract not found: {parameter_id}')
    current = (cursor.statement.get('arguments') or {}).get(parameter_id)
    encoded = value.model_dump(mode='json')
    if current is not None:
        encoded['value_id'] = current['value_id']
    cursor.statement.setdefault('arguments', {})[parameter_id] = encoded
    if bool(getattr(contract, 'dangerous', False)):
        # A review is bound to the exact value tree.  Never leave stale
        # evidence looking current after an argument edit.
        cursor.statement['author_review_fingerprint'] = None
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def repair_missing_call_arguments(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    statement_id: str,
) -> ProgramEditResult:
    """Materialize every missing call slot from the authoritative contract.

    Existing values are left byte-for-byte equivalent.  The client selects
    only the call; it cannot provide replacement defaults or stable IDs.
    """

    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    if cursor.statement.get('kind') != 'call':
        raise ProgramCommandError('only call statements own function parameters')
    function_id = str(cursor.statement.get('function_id') or '')
    try:
        contract = require_contract(registry, function_id)
    except KeyError:
        raise ProgramCommandError(f'function contract not found: {function_id}') from None
    arguments = cursor.statement.setdefault('arguments', {})
    missing = [
        parameter for parameter in contract.parameters
        if parameter.parameter_id not in arguments
    ]
    if not missing:
        raise ProgramCommandError('call statement has no missing parameters')
    created_ids: list[str] = []
    for parameter in missing:
        encoded = _default_value(parameter).model_dump(mode='json')
        arguments[parameter.parameter_id] = encoded
        created_ids.extend(_owned_ids(encoded))
    if bool(getattr(contract, 'dangerous', False)):
        cursor.statement['author_review_fingerprint'] = None
    return ProgramEditResult(
        _validate_command_result(raw, registry),
        statement_id,
        tuple(created_ids),
    )


def _statement_for_update(
    raw: dict,
    statement_id: str,
    expected_kind: str,
) -> dict:
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    if cursor.statement.get('kind') != expected_kind:
        raise ProgramCommandError(
            f'{expected_kind} statement not found: {statement_id}'
        )
    return cursor.statement


def _replace_value(
    current: dict | None,
    replacement: ValueNode | None,
    *,
    field_name: str,
) -> dict | None:
    """Replace one whitelisted value slot without changing its stable identity.

    The field-specific command fixes the surrounding ProgramDocument structure;
    the ValueNode variant may still change (for example literal -> variable
    reference).  The existing root ``value_id`` remains the identity observed by
    the Inspector and Player bindings. Optional slots may be created or cleared.
    """

    if replacement is None:
        return None
    encoded = replacement.model_dump(mode='json')
    if current is None:
        return encoded
    if not current.get('value_id'):
        raise ProgramCommandError(f'{field_name} has no stable value_id')
    encoded['value_id'] = current['value_id']
    return encoded


def _replace_binding(current: dict | None, replacement: LoopBinding | None) -> dict | None:
    if replacement is None:
        return None
    encoded = replacement.model_dump(mode='json')
    if current is not None:
        encoded['symbol_id'] = current['symbol_id']
    return encoded


def update_assignment_value(
    document: ProgramDocument,
    statement_id: str,
    value: ValueNode,
    *,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'assignment')
    statement['value'] = _replace_value(
        statement['value'], value, field_name='assignment.value'
    )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_assignment_target(
    document: ProgramDocument,
    statement_id: str,
    target: LocalAssignmentTarget | ProjectVariableAssignmentTarget,
    *,
    value: ValueNode | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'assignment')
    current = statement['target']
    encoded = target.model_dump(mode='json')
    if current.get('kind') == encoded.get('kind') == 'local':
        encoded['symbol_id'] = current['symbol_id']
    statement['target'] = encoded
    if value is not None:
        statement['value'] = _replace_value(
            statement['value'], value, field_name='assignment.value'
        )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_if_condition(
    document: ProgramDocument,
    statement_id: str,
    condition: ValueNode,
    *,
    branch_id: str | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'if')
    if branch_id is None:
        statement['condition'] = _replace_value(
            statement['condition'], condition, field_name='if.condition'
        )
    else:
        branch = next(
            (
                item
                for item in statement.get('additional_branches') or []
                if item.get('branch_id') == branch_id
            ),
            None,
        )
        if branch is None:
            raise ProgramCommandError(f'if branch not found: {branch_id}')
        branch['condition'] = _replace_value(
            branch['condition'], condition, field_name='if.additional_branch.condition'
        )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_loop(
    document: ProgramDocument,
    statement_id: str,
    *,
    mode: Literal['repeat', 'while', 'for_each', 'for_each_map'],
    source: ValueNode,
    item_binding: LoopBinding | None = None,
    index_binding: LoopBinding | None = None,
    key_binding: LoopBinding | None = None,
    value_binding: LoopBinding | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'loop')
    statement.update({
        'mode': mode,
        'source': _replace_value(
            statement['source'], source, field_name='loop.source'
        ),
        'item_binding': _replace_binding(statement.get('item_binding'), item_binding),
        'index_binding': _replace_binding(statement.get('index_binding'), index_binding),
        'key_binding': _replace_binding(statement.get('key_binding'), key_binding),
        'value_binding': _replace_binding(statement.get('value_binding'), value_binding),
    })
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_return_value(
    document: ProgramDocument,
    statement_id: str,
    value: ValueNode | None,
    *,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'return')
    statement['value'] = _replace_value(
        statement.get('value'), value, field_name='return.value'
    )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_fail(
    document: ProgramDocument,
    statement_id: str,
    *,
    error_id: str,
    message: ValueNode,
    details: ValueNode | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'fail')
    statement.update({
        'error_id': error_id,
        'message': _replace_value(statement['message'], message, field_name='fail.message'),
        'details': _replace_value(statement.get('details'), details, field_name='fail.details'),
    })
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_try_retry_policy(
    document: ProgramDocument,
    statement_id: str,
    retry_policy: RetryPolicy | None,
    *,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'try')
    current = statement.get('retry_policy')
    if retry_policy is None:
        statement['retry_policy'] = None
    else:
        encoded = retry_policy.model_dump(mode='json')
        # Review evidence is service-owned.  A structural policy update may
        # preserve existing evidence, but it can never import evidence from a
        # client payload.
        encoded['author_review_fingerprint'] = (
            current.get('author_review_fingerprint') if current is not None else None
        )
        if current is not None:
            encoded['max_retries'] = _replace_value(
                current['max_retries'],
                retry_policy.max_retries,
                field_name='try.retry_policy.max_retries',
            )
            encoded['interval'] = _replace_value(
                current['interval'],
                retry_policy.interval,
                field_name='try.retry_policy.interval',
            )
        statement['retry_policy'] = encoded
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def review_retry_risk(
    document: ProgramDocument,
    statement_id: str,
    registry: FunctionContractProvider,
) -> ProgramEditResult:
    """Record an author review using only server-owned program and contract facts."""

    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None or cursor.statement.get('kind') != 'try':
        raise ProgramCommandError(f'try statement not found: {statement_id}')
    typed_statement = next(
        statement
        for statement in iter_statement_tree(document.function.statements)
        if statement.statement_id == statement_id
    )
    if not isinstance(typed_statement, TryStatement):
        raise ProgramCommandError(f'try statement not found: {statement_id}')
    if typed_statement.retry_policy is None:
        raise ProgramCommandError('未启用重试策略，无需审核副作用风险')
    if not retry_body_has_side_effects(typed_statement, registry):
        raise ProgramCommandError('重试主体不包含已声明的副作用，无需审核')
    cursor.statement['retry_policy']['author_review_fingerprint'] = (
        retry_review_fingerprint(typed_statement, registry)
    )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def review_dangerous_call(
    document: ProgramDocument,
    statement_id: str,
    registry: FunctionContractProvider,
) -> ProgramEditResult:
    """Record server-owned author approval for one exact dangerous call."""

    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None or cursor.statement.get('kind') != 'call':
        raise ProgramCommandError(f'call statement not found: {statement_id}')
    typed_statement = next(
        statement
        for statement in iter_statement_tree(document.function.statements)
        if statement.statement_id == statement_id
    )
    if not isinstance(typed_statement, CallStatement):
        raise ProgramCommandError(f'call statement not found: {statement_id}')
    contract = require_contract(registry, typed_statement.function_id)
    if not bool(getattr(contract, 'dangerous', False)):
        raise ProgramCommandError('当前函数不是危险调用，无需审核')
    cursor.statement['author_review_fingerprint'] = dangerous_call_review_fingerprint(
        typed_statement, registry,
    )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_catch_clause(
    document: ProgramDocument,
    statement_id: str,
    catch_id: str,
    *,
    error_ids: tuple[str, ...] = (),
    error_binding: LoopBinding | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'try')
    clause = next(
        (
            item
            for item in statement.get('catches') or []
            if item.get('catch_id') == catch_id
        ),
        None,
    )
    if clause is None:
        raise ProgramCommandError(f'catch clause not found: {catch_id}')
    encoded_binding = _replace_binding(clause.get('error_binding'), error_binding)
    clause['error_ids'] = list(error_ids)
    clause['error_binding'] = encoded_binding
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_target_scope(
    document: ProgramDocument,
    statement_id: str,
    target: ValueNode,
    *,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'target_scope')
    statement['target'] = _replace_value(
        statement['target'], target, field_name='target_scope.target'
    )
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def update_listen(
    document: ProgramDocument,
    statement_id: str,
    *,
    event_source: MessageEventSource,
    receive_binding: LoopBinding,
    handler_function_id: str,
    condition: ValueNode | None = None,
    handler_arguments: Mapping[str, ValueNode] | None = None,
    registry: FunctionContractProvider | None = None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    statement = _statement_for_update(raw, statement_id, 'listen')
    current_source = statement['event_source']
    encoded_source = event_source.model_dump(mode='json')
    encoded_source['name'] = _replace_value(
        current_source['name'], event_source.name, field_name='listen.event_source.name'
    )
    encoded_source['sender'] = _replace_value(
        current_source.get('sender'),
        event_source.sender,
        field_name='listen.event_source.sender',
    )
    encoded_binding = _replace_binding(statement['receive_binding'], receive_binding)
    current_arguments = statement.get('handler_arguments') or {}
    encoded_arguments = {
        parameter_id: _replace_value(
            current_arguments.get(parameter_id),
            value,
            field_name=f'listen.handler_arguments.{parameter_id}',
        )
        for parameter_id, value in dict(handler_arguments or {}).items()
    }
    statement.update({
        'event_source': encoded_source,
        'receive_binding': encoded_binding,
        'condition': _replace_value(
            statement.get('condition'), condition, field_name='listen.condition'
        ),
        'handler_function_id': handler_function_id,
        'handler_arguments': encoded_arguments,
    })
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def set_result_binding(
    document: ProgramDocument,
    registry: FunctionContractProvider,
    statement_id: str,
    binding: ResultBinding | None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    if cursor.statement.get('kind') != 'call':
        raise ProgramCommandError('only call statements can bind a function result')
    encoded = binding.model_dump(mode='json') if binding is not None else None
    current = cursor.statement.get('result_binding')
    if encoded is not None and current is not None:
        # Renaming or retargeting a result never changes the local symbol that
        # downstream references and debugger snapshots are bound to.
        encoded['symbol_id'] = current['symbol_id']
    cursor.statement['result_binding'] = encoded
    return ProgramEditResult(_validate_command_result(raw, registry), statement_id)


def set_step_label(
    document: ProgramDocument,
    statement_id: str,
    label: str | None,
) -> ProgramEditResult:
    raw = document.model_dump(mode='json')
    cursor = _find_statement(raw['function']['statements'], statement_id)
    if cursor is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    normalized = str(label).strip() if label is not None else None
    cursor.statement['step_label'] = normalized or None
    return ProgramEditResult(_validate_command_result(raw), statement_id)


def move_statement(
    document: ProgramDocument,
    statement_id: str,
    location: StatementLocation,
) -> ProgramEditResult:
    """Move a statement subtree without changing any stable ID."""

    raw = document.model_dump(mode='json')
    root = raw['function']['statements']
    source = _find_statement(root, statement_id)
    if source is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    descendants = _descendant_statement_ids(source.statement)
    if location.parent_statement_id in descendants:
        raise ProgramCommandError('a statement cannot be moved into its own subtree')
    if location.before_statement_id == statement_id:
        return ProgramEditResult(document, statement_id)
    moved = source.container.pop(source.index)
    _insert_into(_target_block(raw, location), moved, location.before_statement_id)
    return ProgramEditResult(_validate_command_result(raw), statement_id)


def move_statements(
    document: ProgramDocument,
    statement_ids: list[str],
    location: StatementLocation,
) -> ProgramEditResult:
    """Move sibling subtrees as one validated edit while preserving their order."""

    unique_ids = list(dict.fromkeys(statement_ids))
    if not unique_ids:
        raise ProgramCommandError('no statements selected')
    raw = document.model_dump(mode='json')
    root = raw['function']['statements']
    cursors = [_find_statement(root, statement_id) for statement_id in unique_ids]
    if any(cursor is None for cursor in cursors):
        missing = unique_ids[next(index for index, cursor in enumerate(cursors) if cursor is None)]
        raise ProgramCommandError(f'statement not found: {missing}')
    typed_cursors = [cursor for cursor in cursors if cursor is not None]
    source_container = typed_cursors[0].container
    if any(cursor.container is not source_container for cursor in typed_cursors):
        raise ProgramCommandError('selected statements must belong to the same statement block')
    ordered = sorted(typed_cursors, key=lambda cursor: cursor.index)
    selected = {cursor.statement['statement_id'] for cursor in ordered}
    if location.before_statement_id in selected:
        return ProgramEditResult(document, ordered[-1].statement['statement_id'])
    descendants: set[str] = set()
    for cursor in ordered:
        descendants.update(_descendant_statement_ids(cursor.statement))
    if location.parent_statement_id in descendants:
        raise ProgramCommandError('statements cannot be moved into their own subtree')

    moved = [cursor.statement for cursor in ordered]
    for cursor in reversed(ordered):
        cursor.container.pop(cursor.index)
    target = _target_block(raw, location)
    insertion_index = len(target)
    if location.before_statement_id is not None:
        insertion_index = next(
            (index for index, item in enumerate(target) if item['statement_id'] == location.before_statement_id),
            -1,
        )
        if insertion_index < 0:
            raise ProgramCommandError(
                f'target statement not found in selected block: {location.before_statement_id}'
            )
    for offset, statement in enumerate(moved):
        target.insert(insertion_index + offset, statement)
    return ProgramEditResult(
        _validate_command_result(raw),
        moved[-1]['statement_id'],
    )


def _copy_statement_payloads(statements: list[dict]) -> tuple[list[dict], tuple[str, ...]]:
    """Clone one clipboard batch with one shared owned-symbol remap.

    Sharing the map across every selected root preserves references from a later
    copied statement to a result declared by an earlier copied statement.
    """
    result_symbols: dict[str, str] = {}

    def collect_selector_symbols(value: object) -> None:
        if isinstance(value, list):
            for child in value:
                collect_selector_symbols(child)
            return
        if not isinstance(value, dict):
            return
        if value.get('kind') == 'selector':
            for binding in value.get('bindings') or []:
                if isinstance(binding, dict) and binding.get('symbol_id'):
                    result_symbols[str(binding['symbol_id'])] = new_stable_id('symbol')
        for child in value.values():
            collect_selector_symbols(child)

    def collect_symbols(node: dict) -> None:
        collect_selector_symbols(node)
        binding = node.get('result_binding')
        if binding and binding.get('declare', True):
            result_symbols[str(binding['symbol_id'])] = new_stable_id('symbol')
        target = node.get('target')
        if (
            node.get('kind') == 'assignment'
            and isinstance(target, dict)
            and target.get('kind') == 'local'
            and target.get('declare', True)
        ):
            result_symbols[str(target['symbol_id'])] = new_stable_id('symbol')
        if node.get('kind') == 'loop':
            for name in ('item_binding', 'index_binding', 'key_binding', 'value_binding'):
                item = node.get(name)
                if item:
                    result_symbols[str(item['symbol_id'])] = new_stable_id('symbol')
        if node.get('kind') == 'try':
            for clause in node.get('catches') or []:
                item = clause.get('error_binding')
                if item:
                    result_symbols[str(item['symbol_id'])] = new_stable_id('symbol')
        if node.get('kind') == 'listen' and node.get('receive_binding'):
            item = node['receive_binding']
            result_symbols[str(item['symbol_id'])] = new_stable_id('symbol')
        for block in _child_blocks(node):
            for child in block:
                collect_symbols(child)

    for statement in statements:
        collect_symbols(statement)
    created: list[str] = list(result_symbols.values())

    def clone(node: object) -> object:
        if isinstance(node, list):
            return [clone(item) for item in node]
        if not isinstance(node, dict):
            return copy.deepcopy(node)
        copied: dict = {}
        for key, item in node.items():
            if key == 'statement_id':
                replacement = new_stable_id('stmt')
                created.append(replacement)
                copied[key] = replacement
            elif key == 'value_id':
                replacement = new_stable_id('value')
                created.append(replacement)
                copied[key] = replacement
            elif key == 'branch_id':
                replacement = new_stable_id('branch')
                created.append(replacement)
                copied[key] = replacement
            elif key == 'catch_id':
                replacement = new_stable_id('catch')
                created.append(replacement)
                copied[key] = replacement
            elif key == 'symbol_id' and item in result_symbols:
                copied[key] = result_symbols[item]
            else:
                copied[key] = clone(item)
        return copied

    return [clone(statement) for statement in statements], tuple(created)


def _copy_statement_payload(statement: dict) -> tuple[dict, tuple[str, ...]]:
    copied, created_ids = _copy_statement_payloads([statement])
    return copied[0], created_ids


def copy_statement(
    document: ProgramDocument,
    statement_id: str,
    location: StatementLocation,
) -> ProgramEditResult:
    """Copy a subtree and recursively regenerate owned stable IDs."""

    raw = document.model_dump(mode='json')
    source = _find_statement(raw['function']['statements'], statement_id)
    if source is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    copied, created_ids = _copy_statement_payload(source.statement)
    _insert_into(_target_block(raw, location), copied, location.before_statement_id)
    result = _validate_command_result(raw)
    return ProgramEditResult(result, copied['statement_id'], created_ids)


def paste_statements(
    document: ProgramDocument,
    statements: list[Mapping[str, object]],
    location: StatementLocation,
    *,
    registry: FunctionContractProvider,
) -> ProgramEditResult:
    """Paste a structural clipboard snapshot and regenerate all owned IDs."""

    if not statements:
        raise ProgramCommandError('clipboard does not contain any statements')
    raw = document.model_dump(mode='json')
    payloads = [copy.deepcopy(dict(statement)) for statement in statements]
    copied, created_ids = _copy_statement_payloads(payloads)
    target = _target_block(raw, location)
    insertion_index = len(target)
    if location.before_statement_id is not None:
        insertion_index = next(
            (index for index, item in enumerate(target) if item['statement_id'] == location.before_statement_id),
            -1,
        )
        if insertion_index < 0:
            raise ProgramCommandError(
                f'target statement not found in selected block: {location.before_statement_id}'
            )
    for offset, statement in enumerate(copied):
        target.insert(insertion_index + offset, statement)
    # The structural clipboard is supplied by the client.  Validate the
    # resulting document against the currently linked function registry so an
    # expired or tampered snapshot cannot persist unknown calls or parameters.
    result = _validate_command_result(raw, registry)
    return ProgramEditResult(
        result,
        copied[-1]['statement_id'],
        created_ids,
    )


def delete_statement(document: ProgramDocument, statement_id: str) -> ProgramEditResult:
    """Delete a subtree, rejecting any remaining reference to its local results."""

    raw = document.model_dump(mode='json')
    source = _find_statement(raw['function']['statements'], statement_id)
    if source is None:
        raise ProgramCommandError(f'statement not found: {statement_id}')
    source.container.pop(source.index)
    result = _validate_command_result(raw)
    next_selection = ''
    if source.container:
        next_selection = source.container[min(source.index, len(source.container) - 1)]['statement_id']
    return ProgramEditResult(result, next_selection)


def delete_statements(document: ProgramDocument, statement_ids: list[str]) -> ProgramEditResult:
    """Delete sibling subtrees together so no partially deleted document is visible."""

    unique_ids = list(dict.fromkeys(statement_ids))
    if not unique_ids:
        raise ProgramCommandError('no statements selected')
    raw = document.model_dump(mode='json')
    root = raw['function']['statements']
    cursors = [_find_statement(root, statement_id) for statement_id in unique_ids]
    if any(cursor is None for cursor in cursors):
        missing = unique_ids[next(index for index, cursor in enumerate(cursors) if cursor is None)]
        raise ProgramCommandError(f'statement not found: {missing}')
    typed_cursors = [cursor for cursor in cursors if cursor is not None]
    source_container = typed_cursors[0].container
    if any(cursor.container is not source_container for cursor in typed_cursors):
        raise ProgramCommandError('selected statements must belong to the same statement block')
    ordered = sorted(typed_cursors, key=lambda cursor: cursor.index)
    fallback_index = ordered[0].index
    for cursor in reversed(ordered):
        cursor.container.pop(cursor.index)
    result = _validate_command_result(raw)
    next_selection = ''
    if source_container:
        next_selection = source_container[min(fallback_index, len(source_container) - 1)]['statement_id']
    return ProgramEditResult(result, next_selection)


__all__ = [
    'add_catch_clause',
    'add_if_branch',
    'remove_if_branch',
    'ProgramCommandError',
    'ProgramEditResult',
    'ProgramReferenceError',
    'StatementLocation',
    'copy_statement',
    'paste_statements',
    'delete_statement',
    'delete_statements',
    'insert_assignment',
    'insert_break',
    'insert_call',
    'insert_call_and_if',
    'insert_execute_until',
    'insert_continue',
    'insert_fail',
    'insert_if',
    'insert_if_from_call_result',
    'insert_listen',
    'insert_loop',
    'insert_return',
    'insert_target_scope',
    'insert_try',
    'move_statement',
    'move_statements',
    'review_retry_risk',
    'review_dangerous_call',
    'repair_missing_call_arguments',
    'set_result_binding',
    'set_step_label',
    'update_assignment_target',
    'update_assignment_value',
    'update_catch_clause',
    'update_call_argument',
    'update_fail',
    'update_if_condition',
    'update_listen',
    'update_loop',
    'update_return_value',
    'update_target_scope',
    'update_try_retry_policy',
]
