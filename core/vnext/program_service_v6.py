"""Workspace-scoped application service for format-6 ProgramDocuments."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .program_commands import (
    ProgramCommandError,
    StatementLocation,
    add_catch_clause,
    add_if_branch,
    copy_statement,
    delete_statement,
    delete_statements,
    insert_assignment,
    insert_break,
    insert_call,
    insert_continue,
    insert_fail,
    insert_if,
    insert_if_from_call_result,
    insert_listen,
    insert_loop,
    insert_return,
    insert_target_scope,
    insert_try,
    move_statement,
    move_statements,
    paste_statements,
    repair_missing_call_arguments,
    remove_if_branch,
    review_dangerous_call,
    review_retry_risk,
    set_result_binding,
    set_step_label,
    update_assignment_target,
    update_assignment_value,
    update_call_argument,
    update_catch_clause,
    update_fail,
    update_if_condition,
    update_listen,
    update_loop,
    update_return_value,
    update_target_scope,
    update_try_retry_policy,
)
from .program_compiler import (
    compile_program_bundle,
    linked_function_registry,
    project_function_contract,
)
from .program_contracts import FunctionContractProvider
from .program_extraction_v6 import ProgramExtractionError, extract_contiguous_statements
from .program_repository import ProgramConflictError, ProgramDocumentRepository, ProgramSnapshot
from .program_types import (
    AssignmentStatement,
    AssignmentTarget,
    CallStatement,
    CatchClause,
    ListenStatement,
    LoopBinding,
    MemberAccessValue,
    MessageEventSource,
    ProgramDocument,
    ProjectVariableAssignmentTarget,
    ProjectVariableReferenceValue,
    PureOperationValue,
    RecordValue,
    ResultBinding,
    RetryPolicy,
    ValueNode,
    create_program_document,
    iter_value_children,
    value_type,
)
from .program_validation import iter_statement_tree, iter_statement_values, types_compatible, validate_program_document
from .program_value_scope_v6 import AvailableValueSourceV6, available_value_sources
from .project_variables_v6 import ProjectVariableRegistry, ProjectVariableRepository
from .record_types_v6 import RECORD_TYPE_CONTRACTS, record_type_contract
from .value_catalog_v6 import PURE_OPERATION_PRESENTATIONS, pure_value_catalog_payload
from .workspace_context import VNextWorkspaceContext


class ProgramServiceError(RuntimeError):
    pass


class ProgramCommandRequestError(ProgramServiceError):
    pass


class ProgramEntryPointDeletionError(ProgramServiceError):
    def __init__(self, function_id: str) -> None:
        super().__init__('项目入口函数不能删除')
        self.function_id = function_id


class ProgramReferencedError(ProgramServiceError):
    def __init__(self, function_id: str, references: list[dict[str, Any]]) -> None:
        super().__init__(f'项目函数仍有 {len(references)} 处引用，不能删除')
        self.function_id = function_id
        self.references = references


@dataclass(slots=True)
class _HistoryEntry:
    document: ProgramDocument
    companion_document: ProgramDocument | None = None
    companion_should_exist: bool | None = None


@dataclass(slots=True)
class _DocumentHistory:
    undo: list[_HistoryEntry] = field(default_factory=list)
    redo: list[_HistoryEntry] = field(default_factory=list)


class ProgramServiceV6:
    """Own structural edits, optimistic persistence, and session undo/redo.

    History is intentionally an IDE-session concern.  ProgramDocument files
    contain business facts only; restarting the IDE does not pretend an old
    in-memory command stack is still valid against externally changed files.
    """

    def __init__(
        self,
        context: VNextWorkspaceContext,
        registry: FunctionContractProvider,
        *,
        history_limit: int = 100,
    ) -> None:
        self._context = context
        self._registry = registry
        self._history_limit = max(1, int(history_limit))
        self._history: dict[tuple[str, int, str], _DocumentHistory] = {}
        self._summary_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _workspace(self, workspace_id: str, generation: int, *, writable: bool = False):
        return self._context.require(workspace_id, generation, writable=writable)

    @staticmethod
    def _program_presentations(document: ProgramDocument) -> dict[str, Any]:
        """Return the localized labels needed to render this document.

        Stable IDs remain the ProgramDocument truth. The browser must not
        recreate user-facing names from those IDs, and sending only referenced
        operations keeps every structural mutation response compact.
        """

        operation_ids: set[str] = set()
        field_ids: set[str] = set()
        record_type_ids: set[str] = set()

        def collect(value: ValueNode) -> None:
            if isinstance(value, PureOperationValue):
                operation_ids.add(value.operation_id)
            if isinstance(value, RecordValue):
                record_type_ids.add(value.record_type)
                contract = record_type_contract(value.record_type)
                if contract is not None:
                    # A RecordValue is rendered from its full authoritative
                    # shape, including fields currently left at defaults.  The
                    # snapshot must therefore carry every localized field name
                    # and cannot rely on a later catalog request.
                    field_ids.update(field.field_id for field in contract.fields)
            if isinstance(value, MemberAccessValue):
                field_ids.add(value.field_id)
                contract = record_type_contract(value_type(value.source))
                if contract is not None:
                    record_type_ids.add(contract.type_id)

        def visit(value: ValueNode) -> None:
            collect(value)
            for child in iter_value_children(value):
                visit(child)

        for parameter in document.function.parameters:
            if parameter.default_value is not None:
                visit(parameter.default_value)
        for statement in iter_statement_tree(document.function.statements):
            for value in iter_statement_values(statement):
                collect(value)

        operations: dict[str, Any] = {}
        for operation_id in sorted(operation_ids):
            presentation = PURE_OPERATION_PRESENTATIONS.get(operation_id)
            if presentation is None:
                continue
            operations[operation_id] = {
                'display_name': presentation.display_name,
                'syntax_name': presentation.syntax_name,
                'input_labels': {
                    f'{operation_id}.input.{name}': label
                    for name, label in presentation.input_labels.items()
                },
            }
        all_fields = {
            field.field_id: field.display_name
            for contract in RECORD_TYPE_CONTRACTS.values()
            for field in contract.fields
        }
        return {
            'operations': operations,
            'fields': {
                field_id: all_fields[field_id]
                for field_id in sorted(field_ids)
                if field_id in all_fields
            },
            'record_types': {
                type_id: contract.display_name
                for type_id in sorted(record_type_ids)
                if (contract := record_type_contract(type_id)) is not None
            },
        }

    @classmethod
    def _snapshot_payload(cls, snapshot: ProgramSnapshot, **extra: Any) -> dict[str, Any]:
        return {
            'document': snapshot.document.model_dump(mode='json'),
            'revision': snapshot.revision,
            'presentations': cls._program_presentations(snapshot.document),
            **extra,
        }

    @staticmethod
    def _summary(snapshot: ProgramSnapshot) -> dict[str, Any]:
        document = snapshot.document
        contract = project_function_contract(document)
        return {
            'document_id': document.document_id,
            'function_id': document.function.function_id,
            'display_name': document.function.display_name,
            'statement_count': sum(1 for _ in iter_statement_tree(document.function.statements)),
            'revision': snapshot.revision,
            # The project-program catalog is also the authoritative insertion
            # contract for project calls.  Stable IDs, never display names, are
            # used by commands and ECIR.
            'parameters': [
                {
                    'parameter_id': parameter.parameter_id,
                    'symbol_id': source.symbol_id,
                    'display_name': parameter.display_name,
                    'value_type': parameter.value_type,
                    'required': parameter.required,
                    'default_value': (
                        source.default_value.model_dump(mode='json')
                        if source.default_value is not None else None
                    ),
                }
                for parameter, source in zip(
                    contract.parameters,
                    document.function.parameters,
                    strict=True,
                )
            ],
            'return_type': contract.return_type,
            'contract_version': contract.contract_version,
            'contract_fingerprint': contract.contract_fingerprint,
        }

    @staticmethod
    def _documents(repository: ProgramDocumentRepository) -> list[ProgramDocument]:
        if not repository.functions_path.is_dir():
            return []
        return [
            repository.load(path.stem).document
            for path in sorted(
                repository.functions_path.glob('*.json'),
                key=lambda item: item.name.casefold(),
            )
        ]

    def _linked_registry(
        self,
        repository: ProgramDocumentRepository,
        *,
        replacement: ProgramDocument | None = None,
    ) -> FunctionContractProvider:
        documents = self._documents(repository)
        if replacement is not None:
            documents = [
                replacement if item.function.function_id == replacement.function.function_id else item
                for item in documents
            ]
            if not any(
                item.function.function_id == replacement.function.function_id
                for item in documents
            ):
                documents.append(replacement)
        try:
            return linked_function_registry(documents, self._registry)
        except ValueError as exc:
            raise ProgramCommandRequestError(str(exc)) from exc

    @staticmethod
    def _project_variables(repository: ProgramDocumentRepository) -> ProjectVariableRegistry:
        return ProjectVariableRepository(repository.project_path).load().registry

    @staticmethod
    def _validate_project_variable_usage(
        document: ProgramDocument,
        variables: ProjectVariableRegistry,
    ) -> None:
        definitions = {item.variable_id: item for item in variables.variables}
        for statement in iter_statement_tree(document.function.statements):
            if (
                isinstance(statement, AssignmentStatement)
                and isinstance(statement.target, ProjectVariableAssignmentTarget)
            ):
                definition = definitions.get(statement.target.variable_id)
                if definition is None:
                    raise ProgramCommandRequestError(
                        f'项目变量不存在：{statement.target.variable_id}'
                    )
                if not types_compatible(statement.target.value_type, definition.value_type):
                    raise ProgramCommandRequestError('项目变量赋值目标类型与变量定义不兼容')
            for value in iter_statement_values(statement):
                if not isinstance(value, ProjectVariableReferenceValue):
                    continue
                definition = definitions.get(value.variable_id)
                if definition is None:
                    raise ProgramCommandRequestError(f'项目变量不存在：{value.variable_id}')
                if not types_compatible(definition.value_type, value.value_type):
                    raise ProgramCommandRequestError('项目变量引用类型与变量定义不兼容')

    def list_documents(self, workspace_id: str, generation: int) -> list[dict[str, Any]]:
        workspace = self._workspace(workspace_id, generation)
        repository = ProgramDocumentRepository(workspace.project_path)
        items = []
        if repository.functions_path.is_dir():
            for path in sorted(repository.functions_path.glob('*.json'), key=lambda item: item.name.casefold()):
                snapshot = repository.load(path.stem)
                key = (workspace.project_path, path.stem, snapshot.revision)
                summary = self._summary_cache.get(key)
                if summary is None:
                    summary = self._summary(snapshot)
                    self._summary_cache[key] = summary
                    if len(self._summary_cache) > 4096:
                        del self._summary_cache[next(iter(self._summary_cache))]
                items.append(dict(summary))
        return items

    def load(self, workspace_id: str, generation: int, function_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            snapshot = repository.load(function_id)
            diagnostics = validate_program_document(
                snapshot.document,
                self._linked_registry(repository),
            )
            history = self._history.get((workspace_id, generation, function_id))
            return self._snapshot_payload(
                snapshot,
                diagnostics=[item.to_dict() for item in diagnostics],
                can_undo=bool(history and history.undo),
                can_redo=bool(history and history.redo),
            )

    def history(self, workspace_id: str, generation: int, function_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation)
        repository = ProgramDocumentRepository(workspace.project_path)
        current = repository.load(function_id)
        return {
            'function_id': function_id,
            'current_revision': current.revision,
            'items': [{
                'history_id': item.history_id,
                'revision': item.revision,
                'created_at': item.created_at,
                'reason': item.reason,
                'display_name': item.document.function.display_name,
                'statement_count': len(tuple(iter_statement_tree(item.document.function.statements))),
            } for item in repository.list_history(function_id)],
        }

    def restore_history(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
        history_id: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            restored = repository.restore_history(
                function_id,
                history_id,
                expected_revision=expected_revision,
            )
            self._history.pop((workspace_id, generation, function_id), None)
            diagnostics = validate_program_document(
                restored.document,
                self._linked_registry(repository, replacement=restored.document),
            )
            return self._snapshot_payload(
                restored,
                diagnostics=[item.to_dict() for item in diagnostics],
                selected_statement_id='',
                created_ids=[],
                can_undo=False,
                can_redo=False,
            )

    def value_catalog(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        statement_id: str,
        expected_type: str,
        scope_bindings: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Resolve only operations and members legal at one value slot."""

        workspace = self._workspace(workspace_id, generation)
        repository = ProgramDocumentRepository(workspace.project_path)
        snapshot = repository.load(function_id)
        try:
            sources = available_value_sources(
                snapshot.document,
                statement_id,
                self._project_variables(repository),
            )
        except ValueError as exc:
            raise ProgramCommandRequestError(str(exc)) from exc
        scoped_sources = list(sources)
        known_ids = {item.source_id for item in scoped_sources}
        for index, raw in enumerate(scope_bindings or []):
            symbol_id = str(raw.get('symbol_id') or '').strip()
            display_name = str(raw.get('display_name') or '').strip()
            value_type = str(raw.get('value_type') or '').strip()
            if not symbol_id or not display_name or not value_type:
                raise ProgramCommandRequestError(f'逐项作用域绑定 #{index + 1} 不完整')
            if symbol_id in known_ids:
                raise ProgramCommandRequestError(f'逐项作用域稳定 ID 重复：{symbol_id}')
            known_ids.add(symbol_id)
            scoped_sources.append(AvailableValueSourceV6(
                source='local', source_id=symbol_id,
                display_name=display_name, value_type=value_type,
            ))
        sources = tuple(scoped_sources)
        available_types = {
            item.narrowed_type or item.value_type
            for item in sources
        }
        payload = pure_value_catalog_payload(expected_type, available_types, sources)
        payload['revision'] = snapshot.revision
        payload['sources'] = [item.to_dict() for item in sources]
        # Filled from the authoritative record registry below.  Keeping the
        # key present makes absence explicit instead of letting the client
        # invent member names from runtime dictionaries.
        return payload

    @staticmethod
    def _assert_unique_display_name(
        repository: ProgramDocumentRepository,
        display_name: str,
        *,
        excluding_function_id: str = '',
    ) -> None:
        normalized = display_name.casefold()
        for document in ProgramServiceV6._documents(repository):
            function = document.function
            if function.function_id == excluding_function_id:
                continue
            if function.display_name.casefold() == normalized:
                raise ProgramCommandRequestError(
                    f'项目函数名称已存在：{display_name}'
                )

    def create(self, workspace_id: str, generation: int, display_name: str) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        normalized = str(display_name or '').strip()
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            self._assert_unique_display_name(repository, normalized)
            document = create_program_document(normalized)
            snapshot = repository.create(document)
            return self._snapshot_payload(snapshot, diagnostics=[])

    def rename(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
        display_name: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        normalized = str(display_name or '').strip()
        if not normalized:
            raise ProgramCommandRequestError('项目函数名称不能为空')
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            self._assert_unique_display_name(
                repository,
                normalized,
                excluding_function_id=function_id,
            )
            raw = current.document.model_dump(mode='json')
            raw['function']['display_name'] = normalized
            try:
                updated = ProgramDocument.model_validate(raw)
            except ValidationError as exc:
                raise ProgramCommandRequestError(
                    f'项目函数名称无效：{exc}'
                ) from exc
            diagnostics = validate_program_document(
                updated,
                self._linked_registry(repository, replacement=updated),
            )
            if diagnostics:
                raise ProgramCommandRequestError(
                    '; '.join(item.message for item in diagnostics)
                )
            saved = repository.save(updated, expected_revision=expected_revision)
            history = self._history.setdefault(
                (workspace_id, generation, function_id),
                _DocumentHistory(),
            )
            history.undo.append(_HistoryEntry(current.document))
            del history.undo[:-self._history_limit]
            history.redo.clear()
            payload = self._snapshot_payload(
                saved,
                selected_statement_id='',
                created_ids=[],
                diagnostics=[],
                can_undo=True,
                can_redo=False,
            )
            return payload

    @staticmethod
    def _function_references(
        repository: ProgramDocumentRepository,
        function_id: str,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for document in ProgramServiceV6._documents(repository):
            if document.function.function_id == function_id:
                continue
            for statement in iter_statement_tree(document.function.statements):
                if isinstance(statement, CallStatement) and statement.function_id == function_id:
                    result.append({
                        'kind': 'program_call',
                        'function_id': document.function.function_id,
                        'function_name': document.function.display_name,
                        'statement_id': statement.statement_id,
                        'field': 'function_id',
                    })
                if (
                    isinstance(statement, ListenStatement)
                    and statement.handler_function_id == function_id
                ):
                    result.append({
                        'kind': 'listen_handler',
                        'function_id': document.function.function_id,
                        'function_name': document.function.display_name,
                        'statement_id': statement.statement_id,
                        'field': 'handler_function_id',
                    })
        return result

    def delete(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            try:
                project = json.loads(
                    (Path(workspace.project_path) / 'project.json').read_text(
                        encoding='utf-8-sig'
                    )
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProgramCommandRequestError(f'project.json 无法读取：{exc}') from exc
            if str(project.get('entry_function_id') or '') == function_id:
                raise ProgramEntryPointDeletionError(function_id)
            references = self._function_references(repository, function_id)
            if references:
                raise ProgramReferencedError(function_id, references)
            repository.delete(function_id, expected_revision=expected_revision)
            self._history.pop((workspace_id, generation, function_id), None)
            return {
                'deleted_function_id': function_id,
                'programs': self.list_documents(workspace_id, generation),
            }

    @staticmethod
    def _location(payload: Mapping[str, Any] | None) -> StatementLocation:
        value = dict(payload or {})
        try:
            return StatementLocation(
                parent_statement_id=value.get('parent_statement_id'),
                block=str(value.get('block') or 'root'),
                clause_id=value.get('clause_id'),
                before_statement_id=value.get('before_statement_id'),
            )
        except (TypeError, ValueError) as exc:
            raise ProgramCommandRequestError(str(exc)) from exc

    @staticmethod
    def _typed_value(payload: Any, field_name: str, *, optional: bool = False):
        if payload is None and optional:
            return None
        try:
            return TypeAdapter(ValueNode).validate_python(payload)
        except ValidationError as exc:
            raise ProgramCommandRequestError(
                f'{field_name} 不符合 ProgramDocument 值契约：{exc}'
            ) from exc

    @staticmethod
    def _typed_model(model: Any, payload: Any, field_name: str, *, optional: bool = False):
        if payload is None and optional:
            return None
        try:
            return TypeAdapter(model).validate_python(payload)
        except ValidationError as exc:
            raise ProgramCommandRequestError(
                f'{field_name} 不符合 ProgramDocument 契约：{exc}'
            ) from exc

    @classmethod
    def _typed_values(cls, payload: Mapping[str, Any] | None, field_name: str):
        return {
            str(key): cls._typed_value(value, f'{field_name}.{key}')
            for key, value in dict(payload or {}).items()
        }

    def _apply_command(
        self,
        document: ProgramDocument,
        command: Mapping[str, Any],
        registry: FunctionContractProvider,
    ):
        kind = str(command.get('kind') or '')
        try:
            if kind == 'insert_call':
                return insert_call(
                    document,
                    registry,
                    str(command.get('function_id') or ''),
                    location=self._location(command.get('location')),
                    arguments=self._typed_values(command.get('arguments'), 'arguments'),
                )
            if kind == 'insert_assignment':
                return insert_assignment(
                    document,
                    self._typed_model(AssignmentTarget, command.get('target'), 'target'),
                    self._typed_value(command.get('value'), 'value'),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_if':
                return insert_if(
                    document,
                    self._typed_value(command.get('condition'), 'condition'),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_if_from_call_result':
                return insert_if_from_call_result(
                    document,
                    registry,
                    str(command.get('statement_id') or ''),
                    display_name=command.get('display_name'),
                )
            if kind == 'insert_loop':
                return insert_loop(
                    document,
                    str(command.get('mode') or ''),
                    self._typed_value(command.get('source'), 'source'),
                    item_binding=self._typed_model(
                        LoopBinding, command.get('item_binding'), 'item_binding', optional=True,
                    ),
                    index_binding=self._typed_model(
                        LoopBinding, command.get('index_binding'), 'index_binding', optional=True,
                    ),
                    key_binding=self._typed_model(
                        LoopBinding, command.get('key_binding'), 'key_binding', optional=True,
                    ),
                    value_binding=self._typed_model(
                        LoopBinding, command.get('value_binding'), 'value_binding', optional=True,
                    ),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_break':
                return insert_break(
                    document,
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_continue':
                return insert_continue(
                    document,
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_return':
                return insert_return(
                    document,
                    self._typed_value(command.get('value'), 'value', optional=True),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_fail':
                return insert_fail(
                    document,
                    str(command.get('error_id') or ''),
                    self._typed_value(command.get('message'), 'message'),
                    details=self._typed_value(command.get('details'), 'details', optional=True),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_try':
                return insert_try(
                    document,
                    retry_policy=self._typed_model(
                        RetryPolicy, command.get('retry_policy'), 'retry_policy', optional=True,
                    ),
                    catches=self._typed_model(
                        tuple[CatchClause, ...], command.get('catches') or (), 'catches',
                    ),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_target_scope':
                return insert_target_scope(
                    document,
                    self._typed_value(command.get('target'), 'target'),
                    location=self._location(command.get('location')),
                )
            if kind == 'insert_listen':
                return insert_listen(
                    document,
                    self._typed_model(
                        MessageEventSource, command.get('event_source'), 'event_source',
                    ),
                    self._typed_model(
                        LoopBinding, command.get('receive_binding'), 'receive_binding',
                    ),
                    str(command.get('handler_function_id') or ''),
                    condition=self._typed_value(
                        command.get('condition'), 'condition', optional=True,
                    ),
                    handler_arguments=self._typed_values(
                        command.get('handler_arguments'), 'handler_arguments',
                    ),
                    location=self._location(command.get('location')),
                )
            if kind == 'add_if_branch':
                return add_if_branch(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_value(command.get('condition'), 'condition'),
                )
            if kind == 'remove_if_branch':
                return remove_if_branch(
                    document,
                    str(command.get('statement_id') or ''),
                    str(command.get('branch_id') or ''),
                )
            if kind == 'add_catch_clause':
                return add_catch_clause(
                    document,
                    str(command.get('statement_id') or ''),
                    error_ids=tuple(str(value) for value in command.get('error_ids') or ()),
                    error_binding=self._typed_model(
                        LoopBinding, command.get('error_binding'), 'error_binding', optional=True,
                    ),
                )
            if kind == 'update_argument':
                return update_call_argument(
                    document,
                    registry,
                    str(command.get('statement_id') or ''),
                    str(command.get('parameter_id') or ''),
                    self._typed_value(command.get('value'), 'value'),
                )
            if kind == 'repair_missing_arguments':
                return repair_missing_call_arguments(
                    document,
                    registry,
                    str(command.get('statement_id') or ''),
                )
            if kind == 'update_assignment_value':
                return update_assignment_value(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_value(command.get('value'), 'value'),
                    registry=registry,
                )
            if kind == 'update_assignment_target':
                return update_assignment_target(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_model(AssignmentTarget, command.get('target'), 'target'),
                    value=self._typed_value(
                        command.get('value'), 'value', optional=True,
                    ),
                    registry=registry,
                )
            if kind == 'update_if_condition':
                return update_if_condition(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_value(command.get('condition'), 'condition'),
                    branch_id=command.get('branch_id'),
                    registry=registry,
                )
            if kind == 'update_loop':
                return update_loop(
                    document,
                    str(command.get('statement_id') or ''),
                    mode=str(command.get('mode') or ''),
                    source=self._typed_value(command.get('source'), 'source'),
                    item_binding=self._typed_model(
                        LoopBinding, command.get('item_binding'), 'item_binding', optional=True,
                    ),
                    index_binding=self._typed_model(
                        LoopBinding, command.get('index_binding'), 'index_binding', optional=True,
                    ),
                    key_binding=self._typed_model(
                        LoopBinding, command.get('key_binding'), 'key_binding', optional=True,
                    ),
                    value_binding=self._typed_model(
                        LoopBinding, command.get('value_binding'), 'value_binding', optional=True,
                    ),
                    registry=registry,
                )
            if kind == 'update_return_value':
                return update_return_value(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_value(command.get('value'), 'value', optional=True),
                    registry=registry,
                )
            if kind == 'update_fail':
                return update_fail(
                    document,
                    str(command.get('statement_id') or ''),
                    error_id=str(command.get('error_id') or ''),
                    message=self._typed_value(command.get('message'), 'message'),
                    details=self._typed_value(command.get('details'), 'details', optional=True),
                    registry=registry,
                )
            if kind == 'update_try_retry_policy':
                return update_try_retry_policy(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_model(
                        RetryPolicy,
                        command.get('retry_policy'),
                        'retry_policy',
                        optional=True,
                    ),
                    registry=registry,
                )
            if kind == 'review_retry_risk':
                return review_retry_risk(
                    document,
                    str(command.get('statement_id') or ''),
                    registry,
                )
            if kind == 'review_dangerous_call':
                return review_dangerous_call(
                    document,
                    str(command.get('statement_id') or ''),
                    registry,
                )
            if kind == 'update_catch_clause':
                return update_catch_clause(
                    document,
                    str(command.get('statement_id') or ''),
                    str(command.get('catch_id') or ''),
                    error_ids=tuple(
                        str(value) for value in command.get('error_ids') or ()
                    ),
                    error_binding=self._typed_model(
                        LoopBinding,
                        command.get('error_binding'),
                        'error_binding',
                        optional=True,
                    ),
                    registry=registry,
                )
            if kind == 'update_target_scope':
                return update_target_scope(
                    document,
                    str(command.get('statement_id') or ''),
                    self._typed_value(command.get('target'), 'target'),
                    registry=registry,
                )
            if kind == 'update_listen':
                return update_listen(
                    document,
                    str(command.get('statement_id') or ''),
                    event_source=self._typed_model(
                        MessageEventSource,
                        command.get('event_source'),
                        'event_source',
                    ),
                    receive_binding=self._typed_model(
                        LoopBinding,
                        command.get('receive_binding'),
                        'receive_binding',
                    ),
                    handler_function_id=str(command.get('handler_function_id') or ''),
                    condition=self._typed_value(
                        command.get('condition'), 'condition', optional=True,
                    ),
                    handler_arguments=self._typed_values(
                        command.get('handler_arguments'), 'handler_arguments',
                    ),
                    registry=registry,
                )
            if kind == 'set_result_binding':
                return set_result_binding(
                    document,
                    registry,
                    str(command.get('statement_id') or ''),
                    self._typed_model(
                        ResultBinding, command.get('binding'), 'binding', optional=True,
                    ),
                )
            if kind == 'set_step_label':
                return set_step_label(
                    document,
                    str(command.get('statement_id') or ''),
                    command.get('label'),
                )
            if kind == 'move_statement':
                return move_statement(
                    document,
                    str(command.get('statement_id') or ''),
                    self._location(command.get('location')),
                )
            if kind == 'move_statements':
                return move_statements(
                    document,
                    [str(item) for item in command.get('statement_ids') or []],
                    self._location(command.get('location')),
                )
            if kind == 'copy_statement':
                return copy_statement(
                    document,
                    str(command.get('statement_id') or ''),
                    self._location(command.get('location')),
                )
            if kind == 'paste_statements':
                raw_statements = command.get('statements')
                if not isinstance(raw_statements, list):
                    raise ProgramCommandRequestError('结构剪贴板内容不完整')
                return paste_statements(
                    document,
                    raw_statements,
                    self._location(command.get('location')),
                    registry=registry,
                )
            if kind == 'delete_statement':
                return delete_statement(document, str(command.get('statement_id') or ''))
            if kind == 'delete_statements':
                return delete_statements(
                    document,
                    [str(item) for item in command.get('statement_ids') or []],
                )
        except ProgramCommandError as exc:
            raise ProgramCommandRequestError(str(exc)) from exc
        except ValidationError as exc:
            raise ProgramCommandRequestError(
                f'结构命令不符合 ProgramDocument 契约：{exc}'
            ) from exc
        raise ProgramCommandRequestError(f'不支持的结构命令：{kind or "<empty>"}')

    def apply_command(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        command: Mapping[str, Any],
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            registry = self._linked_registry(repository, replacement=current.document)
            result = self._apply_command(current.document, command, registry)
            self._validate_project_variable_usage(
                result.document,
                self._project_variables(repository),
            )
            saved = repository.save(result.document, expected_revision=expected_revision)
            history = self._history.setdefault((workspace_id, generation, function_id), _DocumentHistory())
            history.undo.append(_HistoryEntry(current.document))
            del history.undo[:-self._history_limit]
            history.redo.clear()
            diagnostics = validate_program_document(
                saved.document,
                self._linked_registry(repository, replacement=saved.document),
            )
            payload = self._snapshot_payload(
                saved,
                selected_statement_id=result.selected_statement_id,
                created_ids=list(result.created_ids),
                diagnostics=[item.to_dict() for item in diagnostics],
                can_undo=bool(history.undo),
                can_redo=False,
            )
            return payload

    def apply_commands(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        commands: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Apply a reviewed command bundle as one save and one undo entry."""
        if not commands:
            raise ProgramCommandRequestError('批量命令不能为空')
        if len(commands) > 2000:
            raise ProgramCommandRequestError('单次批量命令不能超过 2000 条')
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            document = current.document
            selected_statement_id = ''
            created_ids: list[str] = []
            for command in commands:
                registry = self._linked_registry(repository, replacement=document)
                result = self._apply_command(document, command, registry)
                document = result.document
                selected_statement_id = result.selected_statement_id
                created_ids.extend(result.created_ids)
            self._validate_project_variable_usage(document, self._project_variables(repository))
            saved = repository.save(document, expected_revision=expected_revision)
            history = self._history.setdefault((workspace_id, generation, function_id), _DocumentHistory())
            history.undo.append(_HistoryEntry(current.document))
            del history.undo[:-self._history_limit]
            history.redo.clear()
            diagnostics = validate_program_document(
                saved.document, self._linked_registry(repository, replacement=saved.document),
            )
            return self._snapshot_payload(
                saved,
                selected_statement_id=selected_statement_id,
                created_ids=created_ids,
                diagnostics=[item.to_dict() for item in diagnostics],
                can_undo=True,
                can_redo=False,
            )

    def extract_statements(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        statement_ids: list[str],
        display_name: str,
    ) -> dict[str, Any]:
        """Extract one contiguous selection and persist both documents as one IDE edit."""

        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            normalized = str(display_name or '').strip()
            self._assert_unique_display_name(repository, normalized)
            try:
                result = extract_contiguous_statements(
                    current.document,
                    statement_ids,
                    normalized,
                )
            except ProgramExtractionError as exc:
                raise ProgramCommandRequestError(str(exc)) from exc

            documents = [
                item for item in self._documents(repository)
                if item.function.function_id != function_id
            ] + [result.source, result.extracted]
            try:
                registry = linked_function_registry(documents, self._registry)
            except ValueError as exc:
                raise ProgramCommandRequestError(str(exc)) from exc
            source_diagnostics = validate_program_document(result.source, registry)
            extracted_diagnostics = validate_program_document(result.extracted, registry)
            diagnostics = [*source_diagnostics, *extracted_diagnostics]
            if diagnostics:
                raise ProgramCommandRequestError('; '.join(item.message for item in diagnostics))
            variables = self._project_variables(repository)
            self._validate_project_variable_usage(result.source, variables)
            self._validate_project_variable_usage(result.extracted, variables)

            extracted_snapshot = repository.create(result.extracted)
            try:
                saved = repository.save(result.source, expected_revision=expected_revision)
            except Exception:
                repository.delete(
                    result.extracted.function.function_id,
                    expected_revision=extracted_snapshot.revision,
                )
                raise

            history = self._history.setdefault(
                (workspace_id, generation, function_id),
                _DocumentHistory(),
            )
            history.undo.append(_HistoryEntry(
                current.document,
                companion_document=result.extracted,
                companion_should_exist=False,
            ))
            del history.undo[:-self._history_limit]
            history.redo.clear()
            payload = self._snapshot_payload(
                saved,
                selected_statement_id=result.call_statement_id,
                created_ids=[
                    result.extracted.function.function_id,
                    result.call_statement_id,
                ],
                diagnostics=[],
                can_undo=True,
                can_redo=False,
            )
            payload['extracted_program'] = self._summary(extracted_snapshot)
            return payload

    def _restore_history(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        *,
        direction: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProgramDocumentRepository(workspace.project_path)
        with self._lock:
            current = repository.load(function_id)
            if current.revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, current.revision)
            history = self._history.setdefault((workspace_id, generation, function_id), _DocumentHistory())
            source = history.undo if direction == 'undo' else history.redo
            destination = history.redo if direction == 'undo' else history.undo
            if not source:
                raise ProgramCommandRequestError('没有可撤销的操作' if direction == 'undo' else '没有可重做的操作')
            entry = source[-1]
            previous = entry.document
            companion = entry.companion_document
            if companion is not None and entry.companion_should_exist is False:
                try:
                    companion_snapshot = repository.load(companion.function.function_id)
                except Exception as exc:
                    raise ProgramCommandRequestError('提取出的项目函数已经不存在，不能安全撤销') from exc
                if companion_snapshot.document != companion:
                    raise ProgramCommandRequestError('提取出的项目函数已经修改，不能在此处撤销并删除它')
                saved = repository.save(previous, expected_revision=expected_revision)
                try:
                    repository.delete(
                        companion.function.function_id,
                        expected_revision=companion_snapshot.revision,
                    )
                except Exception:
                    repository.save(current.document, expected_revision=saved.revision)
                    raise
            elif companion is not None and entry.companion_should_exist is True:
                companion_snapshot = repository.create(companion)
                try:
                    saved = repository.save(previous, expected_revision=expected_revision)
                except Exception:
                    repository.delete(
                        companion.function.function_id,
                        expected_revision=companion_snapshot.revision,
                    )
                    raise
            else:
                saved = repository.save(previous, expected_revision=expected_revision)
            source.pop()
            destination.append(_HistoryEntry(
                current.document,
                companion_document=companion,
                companion_should_exist=(
                    not entry.companion_should_exist
                    if entry.companion_should_exist is not None else None
                ),
            ))
            del destination[:-self._history_limit]
            payload = self._snapshot_payload(
                saved,
                diagnostics=[
                    item.to_dict()
                    for item in validate_program_document(
                        saved.document,
                        self._linked_registry(repository, replacement=saved.document),
                    )
                ],
                selected_statement_id='',
                created_ids=[],
                can_undo=bool(history.undo),
                can_redo=bool(history.redo),
            )
            if companion is not None:
                payload['programs'] = self.list_documents(workspace_id, generation)
            return payload

    def undo(self, workspace_id: str, generation: int, function_id: str, expected_revision: str) -> dict[str, Any]:
        return self._restore_history(
            workspace_id,
            generation,
            function_id,
            expected_revision,
            direction='undo',
        )

    def redo(self, workspace_id: str, generation: int, function_id: str, expected_revision: str) -> dict[str, Any]:
        return self._restore_history(
            workspace_id,
            generation,
            function_id,
            expected_revision,
            direction='redo',
        )

    def compile(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        target_platform: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation)
        repository = ProgramDocumentRepository(workspace.project_path)
        documents = self._documents(repository)
        project_variables = self._project_variables(repository)
        # Targets are a separate optimistic document, but the compiler must
        # consume the exact active workspace snapshot so target_scope never
        # compiles against an empty or invented registry.  Unit-level service
        # tests may intentionally construct ProgramService without the target
        # service; production workspace wiring always registers it.
        try:
            target_configuration = self._context.service('targets').configuration(
                workspace_id,
                generation,
            )
        except KeyError:
            target_configuration = {'targets': [], 'default_target_id': None}
        effective_platform = target_platform
        if effective_platform is None:
            default_target_id = str(target_configuration.get('default_target_id') or '')
            default_target = next((
                item for item in (target_configuration.get('targets') or [])
                if str(item.get('target_id') or '') == default_target_id
            ), None)
            effective_platform = str((default_target or {}).get('type') or 'no_target')
        project_path = Path(workspace.project_path) / 'project.json'
        try:
            project_manifest = json.loads(project_path.read_text(encoding='utf-8-sig'))
            network_policies = project_manifest.get('network_policies') or []
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProgramServiceError(f'无法读取项目网络策略：{exc}') from exc
        # An explicit no-target run is an isolated execution mode.  Keep the
        # target registry available so target_scope statements can still
        # switch to a named target, but do not let the project's UI default
        # silently become the initial runtime target.
        initial_target_id = (
            None
            if effective_platform == 'no_target'
            else target_configuration.get('default_target_id')
        )
        return compile_program_bundle(
            documents,
            self._registry,
            entry_function_id=function_id,
            target_platform=effective_platform,
            project_variables=project_variables.variables,
            target_definitions=target_configuration.get('targets') or [],
            default_target_id=initial_target_id,
            network_policies=network_policies,
        )


__all__ = [
    'ProgramCommandRequestError',
    'ProgramEntryPointDeletionError',
    'ProgramReferencedError',
    'ProgramServiceError',
    'ProgramServiceV6',
]
