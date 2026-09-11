"""Typed project-variable registry for project format 6.

Project variables are definitions, not persistent runtime values.  Every run
creates an isolated mutable copy from these defaults and optional Player
profile overrides.  This module owns only the authoring registry and its
optimistic, atomic persistence boundary.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, ValidationError, field_validator, model_validator

from .program_serialization import canonical_json_bytes, content_revision
from .program_types import (
    AssetReferenceValue,
    BoolValue,
    ComparisonValue,
    ConditionGroupValue,
    DateTimeValue,
    DateValue,
    DisplayName,
    DurationValue,
    EntityReferenceValue,
    FloatValue,
    IntValue,
    JsonValue,
    ListValue,
    MapValue,
    MemberAccessValue,
    NotValue,
    NullValue,
    PathValue,
    PointValue,
    ProgramModel,
    ProjectVariableReferenceValue,
    PureOperationValue,
    RecordValue,
    RectValue,
    StableId,
    StringValue,
    SymbolReferenceValue,
    TargetReferenceValue,
    TimeValue,
    TypeId,
    UnsetValue,
    ValueNode,
    iter_value_children,
    new_stable_id,
    value_type,
)
from .program_validation import types_compatible
from .revision_conflict import ProgramConflictError

PROJECT_VARIABLE_SCHEMA_VERSION = 1
Description = Annotated[str, StringConstraints(max_length=4000)]

_CONSTRAINT_KEYS = frozenset({
    'minimum', 'maximum', 'step',
    'min_length', 'max_length',
    'min_items', 'max_items', 'unique_items',
    'choices', 'pattern',
})
_RUNTIME_ONLY_REFERENCE_PREFIXES = (
    'frame_ref', 'image_sample', 'process_ref', 'window_ref', 'file_ref', 'directory_ref',
    'received_message', 'message_batch', 'application_run_ref',
)


def _validate_json_value(value: Any, path: str = 'constraints') -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in {float('inf'), float('-inf')}:
            raise ValueError(f'{path} contains a non-finite number')
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f'{path}[{index}]')
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f'{path} keys must be strings')
            _validate_json_value(item, f'{path}.{key}')
        return
    raise ValueError(f'{path} contains unsupported {type(value).__name__}')


def _is_static_default(value: ValueNode) -> bool:
    """Runtime-dependent values cannot become cross-run authoring defaults."""

    if isinstance(value, (
        UnsetValue,
        SymbolReferenceValue,
        ProjectVariableReferenceValue,
        MemberAccessValue,
        PureOperationValue,
        ComparisonValue,
        ConditionGroupValue,
        NotValue,
    )):
        return False
    if (
        isinstance(value, EntityReferenceValue)
        and value.reference_type.startswith(_RUNTIME_ONLY_REFERENCE_PREFIXES)
    ):
        return False
    return all(_is_static_default(child) for child in iter_value_children(value))


def _static_runtime_value(value: ValueNode) -> Any:
    if isinstance(value, NullValue):
        return None
    if isinstance(value, (StringValue, IntValue, FloatValue, BoolValue)):
        return value.value
    if isinstance(value, (DateValue, DateTimeValue, TimeValue)):
        return value.value.isoformat()
    if isinstance(value, DurationValue):
        return value.milliseconds
    if isinstance(value, PointValue):
        return {'x': value.x, 'y': value.y}
    if isinstance(value, RectValue):
        return {
            'x': value.x, 'y': value.y,
            'width': value.width, 'height': value.height,
        }
    if isinstance(value, PathValue):
        return [{'x': point.x, 'y': point.y} for point in value.points]
    if isinstance(value, AssetReferenceValue):
        return {'asset_id': value.asset_id, 'asset_kind': value.asset_kind}
    if isinstance(value, TargetReferenceValue):
        return {'target_id': value.target_id}
    if isinstance(value, EntityReferenceValue):
        return {
            'reference_id': value.reference_id,
            'reference_type': value.reference_type,
        }
    if isinstance(value, ListValue):
        return [_static_runtime_value(item) for item in value.items]
    if isinstance(value, MapValue):
        result: dict[Any, Any] = {}
        for entry in value.entries:
            key = _static_runtime_value(entry.key)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise ValueError('project-variable map keys must be hashable') from exc
            if duplicate:
                raise ValueError('project-variable map default contains duplicate keys')
            result[key] = _static_runtime_value(entry.value)
        return result
    if isinstance(value, RecordValue):
        return {key: _static_runtime_value(item) for key, item in value.fields.items()}
    if isinstance(value, JsonValue):
        return value.payload
    raise ValueError(f'project-variable default is not static: {value.kind}')


def _number_constraint(value: Any, name: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'constraint {name} must be a finite number')
    return value


def _length_constraint(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'constraint {name} must be a non-negative integer')
    return value


def _validate_constraint_definition(constraints: dict[str, Any]) -> None:
    _validate_json_value(constraints)
    unknown = sorted(set(constraints) - _CONSTRAINT_KEYS)
    if unknown:
        raise ValueError(f'unsupported project-variable constraint: {unknown[0]}')
    minimum = _number_constraint(constraints.get('minimum'), 'minimum')
    maximum = _number_constraint(constraints.get('maximum'), 'maximum')
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError('constraint minimum cannot exceed maximum')
    step = _number_constraint(constraints.get('step'), 'step')
    if step is not None and step <= 0:
        raise ValueError('constraint step must be a positive number')
    min_length = _length_constraint(constraints.get('min_length'), 'min_length')
    max_length = _length_constraint(constraints.get('max_length'), 'max_length')
    if min_length is not None and max_length is not None and min_length > max_length:
        raise ValueError('constraint min_length cannot exceed max_length')
    min_items = _length_constraint(constraints.get('min_items'), 'min_items')
    max_items = _length_constraint(constraints.get('max_items'), 'max_items')
    if min_items is not None and max_items is not None and min_items > max_items:
        raise ValueError('constraint min_items cannot exceed max_items')
    unique_items = constraints.get('unique_items')
    if unique_items is not None and not isinstance(unique_items, bool):
        raise ValueError('constraint unique_items must be boolean')
    choices = constraints.get('choices')
    if choices is not None and not isinstance(choices, list):
        raise ValueError('constraint choices must be a JSON array')
    pattern = constraints.get('pattern')
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ValueError('constraint pattern must be text')
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f'constraint pattern is invalid: {exc}') from exc


def validate_runtime_constraints(value: Any, constraints: dict[str, Any]) -> None:
    _validate_constraint_definition(constraints)
    minimum = constraints.get('minimum')
    maximum = constraints.get('maximum')
    step = constraints.get('step')
    min_length = constraints.get('min_length')
    max_length = constraints.get('max_length')
    min_items = constraints.get('min_items')
    max_items = constraints.get('max_items')

    if value is not None:
        if minimum is not None and isinstance(value, (int, float)) and value < minimum:
            raise ValueError('default value is below constraint minimum')
        if maximum is not None and isinstance(value, (int, float)) and value > maximum:
            raise ValueError('default value is above constraint maximum')
        if step is not None and isinstance(value, (int, float)):
            origin = minimum or 0
            quotient = (value - origin) / step
            if not math.isclose(quotient, round(quotient), rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError('default value does not align with constraint step')
        if min_length is not None and isinstance(value, str) and len(value) < min_length:
            raise ValueError('default value is shorter than constraint min_length')
        if max_length is not None and isinstance(value, str) and len(value) > max_length:
            raise ValueError('default value is longer than constraint max_length')
        if min_items is not None and isinstance(value, (list, dict)) and len(value) < min_items:
            raise ValueError('default value has fewer items than constraint min_items')
        if max_items is not None and isinstance(value, (list, dict)) and len(value) > max_items:
            raise ValueError('default value has more items than constraint max_items')
        if constraints.get('unique_items') and isinstance(value, list):
            serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(set(serialized)) != len(serialized):
                raise ValueError('default value violates constraint unique_items')
        choices = constraints.get('choices')
        if choices is not None and value not in choices:
            raise ValueError('default value is not one of constraint choices')
        pattern = constraints.get('pattern')
        if pattern is not None and isinstance(value, str) and re.fullmatch(pattern, value) is None:
            raise ValueError('default value does not match constraint pattern')


def _generic_type(type_id: str, prefix: str) -> str | None:
    marker = f'{prefix}<'
    return type_id[len(marker):-1] if type_id.startswith(marker) and type_id.endswith('>') else None


def _split_map_type(type_id: str) -> tuple[str, str] | None:
    inner = _generic_type(type_id, 'map')
    if inner is None:
        return None
    depth = 0
    for index, character in enumerate(inner):
        if character == '<':
            depth += 1
        elif character == '>':
            depth -= 1
        elif character == ',' and depth == 0:
            return inner[:index], inner[index + 1:]
    return None


def runtime_project_value_conforms(value: Any, type_id: str) -> bool:
    """Defensive check for lowered defaults and untrusted Player overrides."""

    if type_id == 'any':
        return True
    optional = _generic_type(type_id, 'optional')
    if optional is not None:
        return value is None or runtime_project_value_conforms(value, optional)
    if type_id in {'null', 'unit'}:
        return value is None
    if type_id in {'string', 'relative_path', 'url', 'timezone'} or type_id.startswith('enum<'):
        return isinstance(value, str)
    if type_id == 'int64':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_id in {'float64', 'percentage'}:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if type_id == 'bool':
        return isinstance(value, bool)
    if type_id == 'duration':
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
    if type_id in {'date', 'datetime', 'time', 'time_of_day'}:
        return isinstance(value, str) or (
            isinstance(value, dict)
            and value.get('kind') in {type_id, 'time' if type_id == 'time_of_day' else type_id}
            and isinstance(value.get('value'), str)
        )
    if type_id == 'point':
        return isinstance(value, dict) and all(
            isinstance(value.get(key), (int, float)) and not isinstance(value.get(key), bool)
            for key in ('x', 'y')
        )
    if type_id == 'rect':
        return isinstance(value, dict) and all(
            isinstance(value.get(key), (int, float)) and not isinstance(value.get(key), bool)
            for key in ('x', 'y', 'width', 'height')
        )
    if type_id == 'color':
        if not isinstance(value, dict):
            return False
        channels = tuple(
            value.get(f'color.field.{name}', value.get(name))
            for name in ('red', 'green', 'blue', 'alpha')
        )
        return all(
            isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255
            for channel in channels
        )
    if type_id == 'path':
        return isinstance(value, list) and bool(value) and all(
            runtime_project_value_conforms(item, 'point') for item in value
        )
    if type_id.startswith('asset_ref'):
        return isinstance(value, dict) and (
            bool(value.get('asset_id'))
            or (value.get('kind') == 'asset_ref' and bool(value.get('asset_id')))
        )
    if type_id == 'target_ref':
        return isinstance(value, dict) and (
            bool(value.get('target_id'))
            or (value.get('kind') == 'target_ref' and bool(value.get('target_id')))
        )
    for reference_kind in ('file_ref', 'directory_ref'):
        required_access = _generic_type(type_id, reference_kind)
        if type_id == reference_kind or required_access is not None:
            if not isinstance(value, dict) or value.get('kind') != reference_kind:
                return False
            if required_access is None:
                return True
            return required_access in {str(item) for item in value.get('access') or ()}
    if type_id.endswith('_ref') or '_ref<' in type_id:
        return isinstance(value, dict) and (
            value.get('reference_type') == type_id
            or bool(value.get('reference_id'))
        )
    item_type = _generic_type(type_id, 'list')
    if item_type is not None:
        return isinstance(value, list) and all(
            runtime_project_value_conforms(item, item_type) for item in value
        )
    map_types = _split_map_type(type_id)
    if map_types is not None:
        key_type, entry_type = map_types
        return isinstance(value, dict) and all(
            runtime_project_value_conforms(key, key_type)
            and runtime_project_value_conforms(item, entry_type)
            for key, item in value.items()
        )
    if type_id in {'json', 'json_value', 'message_value'}:
        try:
            _validate_json_value(value, 'runtime_value')
        except ValueError:
            return False
        return True
    # Named records and domain objects are represented as immutable mappings.
    return isinstance(value, dict)


class ProjectVariableDefinition(ProgramModel):
    variable_id: StableId
    display_name: DisplayName
    value_type: TypeId
    default_value: ValueNode
    description: Description = ''
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator('constraints')
    @classmethod
    def validate_constraint_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_constraint_definition(value)
        return value

    @model_validator(mode='after')
    def validate_default(self) -> ProjectVariableDefinition:
        if not _is_static_default(self.default_value):
            raise ValueError('project-variable default must be a static typed value')
        actual = value_type(self.default_value)
        if not types_compatible(actual, self.value_type):
            raise ValueError(f'default value type {actual} is not assignable to {self.value_type}')
        validate_runtime_constraints(
            _static_runtime_value(self.default_value),
            self.constraints,
        )
        return self


def validate_project_variable_value(
    definition: ProjectVariableDefinition,
    value: ValueNode,
    *,
    require_static: bool = True,
) -> None:
    if require_static and not _is_static_default(value):
        raise ValueError('project-variable value must be a static typed value')
    actual = value_type(value)
    if not types_compatible(actual, definition.value_type):
        raise ValueError(
            f'project-variable value type {actual} is not assignable to '
            f'{definition.value_type}'
        )
    validate_runtime_constraints(_static_runtime_value(value), definition.constraints)


class ProjectVariableRegistry(ProgramModel):
    schema_version: Literal[PROJECT_VARIABLE_SCHEMA_VERSION] = PROJECT_VARIABLE_SCHEMA_VERSION
    variables: tuple[ProjectVariableDefinition, ...] = ()

    @model_validator(mode='after')
    def validate_uniqueness(self) -> ProjectVariableRegistry:
        stable_ids: dict[str, str] = {}
        names: dict[str, str] = {}

        def remember(stable_id: str, owner: str) -> None:
            if stable_id in stable_ids:
                raise ValueError(f'duplicate stable ID {stable_id!r}: {stable_ids[stable_id]} and {owner}')
            stable_ids[stable_id] = owner

        def visit(value: ValueNode, owner: str) -> None:
            remember(value.value_id, owner)
            for index, child in enumerate(iter_value_children(value)):
                visit(child, f'{owner}[{index}]')

        for index, variable in enumerate(self.variables):
            owner = f'variables[{index}]'
            remember(variable.variable_id, owner)
            normalized = variable.display_name.casefold()
            if normalized in names:
                raise ValueError(
                    f'duplicate project-variable name {variable.display_name!r}: '
                    f'{names[normalized]} and {owner}'
                )
            names[normalized] = owner
            visit(variable.default_value, f'{owner}.default_value')
        return self


class ProjectVariableRepositoryError(RuntimeError):
    pass


class ProjectVariableRegistryCorruptError(ProjectVariableRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectVariableSnapshot:
    registry: ProjectVariableRegistry
    revision: str
    path: Path


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    key = os.path.normcase(os.path.abspath(path))
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class ProjectVariableRepository:
    RELATIVE_PATH = Path('program') / 'variables.json'

    def __init__(self, project_path: str | os.PathLike[str]) -> None:
        self.project_path = Path(project_path).resolve()
        self.path = (self.project_path / self.RELATIVE_PATH).resolve()
        try:
            self.path.relative_to(self.project_path)
        except ValueError as exc:
            raise ProjectVariableRepositoryError('project-variable path escapes the project') from exc

    @staticmethod
    def _decode(path: Path, content: bytes) -> ProjectVariableRegistry:
        try:
            payload = json.loads(content.decode('utf-8'))
            return ProjectVariableRegistry.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ProjectVariableRegistryCorruptError(
                f'invalid project-variable registry {path}: {exc}'
            ) from exc

    def load(self) -> ProjectVariableSnapshot:
        with _lock_for(self.path):
            try:
                content = self.path.read_bytes()
            except FileNotFoundError as exc:
                raise ProjectVariableRegistryCorruptError('program/variables.json is missing') from exc
            return ProjectVariableSnapshot(
                registry=self._decode(self.path, content),
                revision=content_revision(content),
                path=self.path,
            )

    def save(
        self,
        registry: ProjectVariableRegistry,
        *,
        expected_revision: str,
    ) -> ProjectVariableSnapshot:
        content = canonical_json_bytes(registry)
        with _lock_for(self.path):
            try:
                current = self.path.read_bytes()
            except FileNotFoundError as exc:
                raise ProgramConflictError('project_variables', expected_revision, None) from exc
            actual_revision = content_revision(current)
            if actual_revision != expected_revision:
                raise ProgramConflictError('project_variables', expected_revision, actual_revision)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f'.{self.path.name}.{uuid.uuid4().hex}.tmp')
            try:
                with temporary.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
            return ProjectVariableSnapshot(
                registry=registry,
                revision=content_revision(content),
                path=self.path,
            )


def create_project_variable(
    display_name: str,
    value_type_id: str,
    default_value: ValueNode,
    *,
    description: str = '',
    constraints: dict[str, Any] | None = None,
    variable_id: str | None = None,
) -> ProjectVariableDefinition:
    return ProjectVariableDefinition(
        variable_id=variable_id or new_stable_id('variable'),
        display_name=display_name,
        value_type=value_type_id,
        default_value=default_value,
        description=description,
        constraints=dict(constraints or {}),
    )


__all__ = [
    'PROJECT_VARIABLE_SCHEMA_VERSION',
    'ProjectVariableDefinition',
    'ProjectVariableRegistry',
    'ProjectVariableRegistryCorruptError',
    'ProjectVariableRepository',
    'ProjectVariableRepositoryError',
    'ProjectVariableSnapshot',
    'create_project_variable',
    'validate_project_variable_value',
    'validate_runtime_constraints',
    'runtime_project_value_conforms',
]
