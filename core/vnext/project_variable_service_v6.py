"""Workspace-scoped CRUD and reference safety for format-6 project variables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .program_repository import ProgramDocumentRepository
from .program_types import (
    AssignmentStatement,
    ProjectVariableAssignmentTarget,
    ProjectVariableReferenceValue,
    ValueNode,
    iter_value_children,
)
from .program_validation import iter_statement_tree, iter_statement_values
from .project_variables_v6 import (
    ProjectVariableDefinition,
    ProjectVariableRegistry,
    ProjectVariableRepository,
    ProjectVariableSnapshot,
    create_project_variable,
    validate_project_variable_value,
)
from .workspace_context import VNextWorkspaceContext


class ProjectVariableServiceError(RuntimeError):
    pass


class ProjectVariableNotFoundError(ProjectVariableServiceError):
    pass


class ProjectVariableReferencedError(ProjectVariableServiceError):
    def __init__(self, variable_id: str, references: list[dict[str, Any]]) -> None:
        super().__init__(f'项目变量仍有 {len(references)} 处引用，不能删除或改变类型')
        self.variable_id = variable_id
        self.references = references


class ProjectVariableRequestError(ProjectVariableServiceError):
    pass


def _snapshot_payload(snapshot: ProjectVariableSnapshot) -> dict[str, Any]:
    return {
        'schema_version': snapshot.registry.schema_version,
        'variables': [item.model_dump(mode='json') for item in snapshot.registry.variables],
        'revision': snapshot.revision,
    }


def _json_references(path: Path, variable_id: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    result: list[dict[str, Any]] = []

    def visit(value: Any, location: str) -> None:
        if isinstance(value, dict):
            if value.get('variable_id') == variable_id:
                result.append({
                    'kind': 'data',
                    'path': path.as_posix(),
                    'location': location,
                })
            for key, child in value.items():
                visit(child, f'{location}.{key}')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f'{location}[{index}]')

    visit(payload, '$')
    return result


class ProjectVariableServiceV6:
    def __init__(self, context: VNextWorkspaceContext) -> None:
        self._context = context

    def _workspace(self, workspace_id: str, generation: int, *, writable: bool = False):
        return self._context.require(workspace_id, generation, writable=writable)

    @staticmethod
    def _typed_value(payload: Any) -> ValueNode:
        try:
            return TypeAdapter(ValueNode).validate_python(payload)
        except ValidationError as exc:
            raise ProjectVariableRequestError(
                f'default_value 不符合 ProgramDocument 值契约：{exc}'
            ) from exc

    @staticmethod
    def _validate_default_value_ids(
        project_path: str | Path,
        registry: ProjectVariableRegistry,
    ) -> None:
        program_value_ids: set[str] = set()

        def visit(value: ValueNode) -> None:
            program_value_ids.add(value.value_id)
            for child in iter_value_children(value):
                visit(child)

        repository = ProgramDocumentRepository(project_path)
        if repository.functions_path.is_dir():
            for path in repository.functions_path.glob('*.json'):
                document = repository.load(path.stem).document
                for parameter in document.function.parameters:
                    if parameter.default_value is not None:
                        visit(parameter.default_value)
                for statement in iter_statement_tree(document.function.statements):
                    for value in iter_statement_values(statement):
                        visit(value)
        for variable in registry.variables:
            variable_ids: list[str] = []

            def collect(
                value: ValueNode,
                destination: list[str] = variable_ids,
            ) -> None:
                destination.append(value.value_id)
                for child in iter_value_children(value):
                    collect(child)

            collect(variable.default_value)
            collision = next((item for item in variable_ids if item in program_value_ids), None)
            if collision is not None:
                raise ProjectVariableRequestError(
                    f'项目变量默认值 ID 与 ProgramDocument 冲突：{collision}'
                )

    def load(self, workspace_id: str, generation: int) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation)
        return _snapshot_payload(ProjectVariableRepository(workspace.project_path).load())

    def references(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
    ) -> list[dict[str, Any]]:
        workspace = self._workspace(workspace_id, generation)
        root = Path(workspace.project_path).resolve()
        variable_snapshot = ProjectVariableRepository(root).load()
        if not any(
            item.variable_id == variable_id
            for item in variable_snapshot.registry.variables
        ):
            raise ProjectVariableNotFoundError(variable_id)
        repository = ProgramDocumentRepository(root)
        result: list[dict[str, Any]] = []
        if repository.functions_path.is_dir():
            for path in sorted(repository.functions_path.glob('*.json'), key=lambda item: item.name.casefold()):
                snapshot = repository.load(path.stem)
                function = snapshot.document.function
                for statement in iter_statement_tree(function.statements):
                    if (
                        isinstance(statement, AssignmentStatement)
                        and isinstance(statement.target, ProjectVariableAssignmentTarget)
                        and statement.target.variable_id == variable_id
                    ):
                        result.append({
                            'kind': 'program_assignment',
                            'function_id': function.function_id,
                            'function_name': function.display_name,
                            'statement_id': statement.statement_id,
                            'field': 'target',
                        })
                    for value in iter_statement_values(statement):
                        if (
                            isinstance(value, ProjectVariableReferenceValue)
                            and value.variable_id == variable_id
                        ):
                            result.append({
                                'kind': 'program_value',
                                'function_id': function.function_id,
                                'function_name': function.display_name,
                                'statement_id': statement.statement_id,
                                'value_id': value.value_id,
                            })

        player_form = root / 'player' / 'form.json'
        if player_form.is_file():
            result.extend(_json_references(player_form, variable_id))
        extension_data = root / 'extension-data'
        if extension_data.is_dir():
            for path in sorted(extension_data.rglob('*.json')):
                result.extend(_json_references(path, variable_id))
        return result

    def create(
        self,
        workspace_id: str,
        generation: int,
        *,
        expected_revision: str,
        display_name: str,
        value_type: str,
        default_value: Any,
        description: str = '',
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProjectVariableRepository(workspace.project_path)
        current = repository.load()
        try:
            variable = create_project_variable(
                str(display_name or '').strip(),
                str(value_type or '').strip(),
                self._typed_value(default_value),
                description=str(description or ''),
                constraints=constraints,
            )
            registry = ProjectVariableRegistry(variables=(*current.registry.variables, variable))
            self._validate_default_value_ids(workspace.project_path, registry)
        except ValidationError as exc:
            raise ProjectVariableRequestError(str(exc)) from exc
        saved = repository.save(registry, expected_revision=expected_revision)
        return {**_snapshot_payload(saved), 'selected_variable_id': variable.variable_id}

    def update(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
        *,
        expected_revision: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProjectVariableRepository(workspace.project_path)
        current = repository.load()
        existing = next(
            (item for item in current.registry.variables if item.variable_id == variable_id),
            None,
        )
        if existing is None:
            raise ProjectVariableNotFoundError(variable_id)

        allowed = {'display_name', 'value_type', 'default_value', 'description', 'constraints'}
        unknown = set(changes) - allowed
        if unknown:
            raise ProjectVariableRequestError(f'不支持的项目变量字段：{"、".join(sorted(unknown))}')
        if not changes:
            raise ProjectVariableRequestError('项目变量更新至少需要一个字段')
        if 'value_type' in changes and str(changes['value_type']) != existing.value_type:
            refs = self.references(workspace_id, generation, variable_id)
            if refs:
                raise ProjectVariableReferencedError(variable_id, refs)

        values = existing.model_dump(mode='python')
        values.update(changes)
        if 'default_value' in changes:
            replacement = self._typed_value(changes['default_value'])
            # The root value slot is a stable Player/inspector binding.  A
            # scalar edit changes its content, never its identity.
            replacement = replacement.model_copy(update={'value_id': existing.default_value.value_id})
            values['default_value'] = replacement
        try:
            updated = ProjectVariableDefinition.model_validate(values)
            registry = ProjectVariableRegistry(variables=tuple(
                updated if item.variable_id == variable_id else item
                for item in current.registry.variables
            ))
            self._validate_default_value_ids(workspace.project_path, registry)
        except ValidationError as exc:
            raise ProjectVariableRequestError(str(exc)) from exc
        saved = repository.save(registry, expected_revision=expected_revision)
        return {**_snapshot_payload(saved), 'selected_variable_id': variable_id}

    def validate_overrides(
        self,
        workspace_id: str,
        generation: int,
        overrides: dict[str, Any] | None,
    ) -> dict[str, ValueNode]:
        """Validate one run's typed initial values without persisting them."""

        workspace = self._workspace(workspace_id, generation)
        snapshot = ProjectVariableRepository(workspace.project_path).load()
        definitions = {item.variable_id: item for item in snapshot.registry.variables}
        unknown = sorted(set(overrides or {}) - set(definitions))
        if unknown:
            raise ProjectVariableRequestError(f'项目变量不存在：{unknown[0]}')
        result: dict[str, ValueNode] = {}
        for variable_id, payload in (overrides or {}).items():
            value = self._typed_value(payload)
            try:
                validate_project_variable_value(definitions[variable_id], value)
            except ValueError as exc:
                raise ProjectVariableRequestError(
                    f'项目变量“{definitions[variable_id].display_name}”的初始覆盖无效：{exc}'
                ) from exc
            result[variable_id] = value
        return result

    def delete(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        repository = ProjectVariableRepository(workspace.project_path)
        current = repository.load()
        if not any(item.variable_id == variable_id for item in current.registry.variables):
            raise ProjectVariableNotFoundError(variable_id)
        refs = self.references(workspace_id, generation, variable_id)
        if refs:
            raise ProjectVariableReferencedError(variable_id, refs)
        registry = ProjectVariableRegistry(variables=tuple(
            item for item in current.registry.variables if item.variable_id != variable_id
        ))
        return _snapshot_payload(repository.save(registry, expected_revision=expected_revision))


__all__ = [
    'ProjectVariableNotFoundError',
    'ProjectVariableReferencedError',
    'ProjectVariableRequestError',
    'ProjectVariableServiceError',
    'ProjectVariableServiceV6',
]
