"""Strongly typed, workspace-scoped target configuration for project format 6."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from .program_serialization import canonical_json_bytes, content_revision
from .program_types import (
    DisplayName,
    ProgramModel,
    StableId,
    TargetReferenceValue,
    ValueNode,
    iter_value_children,
)
from .program_validation import iter_statement_tree, iter_statement_values
from .project_variables_v6 import (
    ProjectVariableRepository,
    ProjectVariableRepositoryError,
)
from .workspace_context import VNextWorkspaceContext

TARGET_CONFIGURATION_SCHEMA_VERSION = 1
WindowTitle = Annotated[str, StringConstraints(max_length=512)]
WindowIdentityText = Annotated[str, StringConstraints(max_length=512)]
AdbSerial = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ClientWorkArea(ProgramModel):
    mode: Literal['client'] = 'client'


class WindowWorkArea(ProgramModel):
    mode: Literal['window'] = 'window'


class DesktopWorkArea(ProgramModel):
    mode: Literal['desktop'] = 'desktop'


class RegionWorkArea(ProgramModel):
    mode: Literal['region'] = 'region'
    region: tuple[StrictInt, StrictInt, StrictInt, StrictInt]

    @model_validator(mode='after')
    def validate_region(self) -> RegionWorkArea:
        x, y, width, height = self.region
        if x < 0 or y < 0:
            raise ValueError('自定义区域的 x、y 不能为负数')
        if width <= 0 or height <= 0:
            raise ValueError('自定义区域的宽、高必须大于 0')
        return self


WindowsWorkArea = Annotated[
    ClientWorkArea | WindowWorkArea | DesktopWorkArea | RegionWorkArea,
    Field(discriminator='mode'),
]


class TargetIdentity(ProgramModel):
    target_id: StableId
    name: DisplayName

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = unicodedata.normalize('NFKC', value).strip()
        if not normalized:
            raise ValueError('目标名称不能为空')
        return normalized


class CapturedWindowBinding(ProgramModel):
    binding_version: Literal[1] = 1
    binding_id: StableId
    title: WindowTitle
    class_name: WindowIdentityText = ''
    executable_name: WindowIdentityText = ''
    hwnd: Annotated[StrictInt, Field(gt=0)]
    process_id: Annotated[StrictInt, Field(gt=0)]
    process_started_at_ms: Annotated[StrictInt, Field(ge=0)] = 0
    captured_at: Annotated[str, StringConstraints(min_length=1, max_length=64)]


class WindowsTargetDefinition(TargetIdentity):
    type: Literal['windows'] = 'windows'
    window_title: WindowTitle = ''
    window_match: Literal['contains', 'exact', 'regex'] = 'contains'
    window_binding: CapturedWindowBinding | None = None
    work_area: WindowsWorkArea = Field(default_factory=ClientWorkArea)
    allow_physical_fallback: StrictBool = True

    @field_validator('window_title')
    @classmethod
    def normalize_window_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode='after')
    def validate_selector_and_fallback(self) -> WindowsTargetDefinition:
        title = self.window_title
        if self.work_area.mode == 'desktop':
            if title:
                raise ValueError('全屏幕目标不能同时绑定窗口标题')
            if self.window_binding is not None:
                raise ValueError('全屏幕目标不能保存窗口捕获绑定')
            if not self.allow_physical_fallback:
                raise ValueError('全屏幕目标必须启用物理输入')
        elif not title:
            raise ValueError('Windows 窗口目标必须填写窗口标题')
        if self.window_binding is not None:
            if self.window_match != 'exact' or self.window_binding.title != title:
                raise ValueError('窗口捕获绑定与标题规则不一致，请重新捕获')
        if self.window_match == 'regex' and title:
            try:
                re.compile(title)
            except re.error as exc:
                raise ValueError(f'窗口标题正则表达式无效：{exc}') from exc
        return self


class AndroidAdbTargetDefinition(TargetIdentity):
    type: Literal['android_adb'] = 'android_adb'
    device_serial: AdbSerial

    @field_validator('device_serial')
    @classmethod
    def normalize_device_serial(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode='after')
    def validate_explicit_serial(self) -> AndroidAdbTargetDefinition:
        serial = self.device_serial
        if not serial or re.search(r'[\s\x00-\x1f]', serial):
            raise ValueError('ADB 目标必须填写不含空白字符的显式设备序列号')
        return self


class AndroidLocalTargetDefinition(TargetIdentity):
    type: Literal['android_local'] = 'android_local'


TargetDefinition = Annotated[
    WindowsTargetDefinition | AndroidAdbTargetDefinition | AndroidLocalTargetDefinition,
    Field(discriminator='type'),
]


class TargetConfiguration(ProgramModel):
    schema_version: Literal[TARGET_CONFIGURATION_SCHEMA_VERSION] = (
        TARGET_CONFIGURATION_SCHEMA_VERSION
    )
    targets: tuple[TargetDefinition, ...] = ()
    default_target_id: StableId | None = None

    @model_validator(mode='after')
    def validate_registry(self) -> TargetConfiguration:
        ids: set[str] = set()
        names: set[str] = set()
        local_count = 0
        for target in self.targets:
            if target.target_id in ids:
                raise ValueError(f'目标 ID 重复：{target.target_id}')
            normalized_name = target.name.casefold()
            if normalized_name in names:
                raise ValueError(f'目标名称重复：{target.name}')
            ids.add(target.target_id)
            names.add(normalized_name)
            if isinstance(target, AndroidLocalTargetDefinition):
                local_count += 1
        if local_count > 1:
            raise ValueError('Android 本机宿主只能登记当前手机这一个目标')
        if self.default_target_id is not None and self.default_target_id not in ids:
            raise ValueError('默认目标不在目标列表中')
        return self


class TargetServiceError(RuntimeError):
    pass


class TargetNotFoundError(TargetServiceError):
    pass


class TargetRequestError(TargetServiceError):
    pass


class TargetConfigurationCorruptError(TargetServiceError):
    pass


class TargetConflictError(TargetServiceError):
    def __init__(self, expected_revision: str, actual_revision: str) -> None:
        super().__init__('目标配置已被其他操作修改')
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision


class TargetReferencedError(TargetServiceError):
    def __init__(self, target_id: str, references: list[dict[str, Any]]) -> None:
        super().__init__(f'运行目标仍有 {len(references)} 处引用，不能删除')
        self.target_id = target_id
        self.references = references


def target_configuration_revision(configuration: TargetConfiguration) -> str:
    # Optional target capabilities must not rewrite every existing project's
    # optimistic-lock revision merely because the runtime gained a new field.
    # Persisted values remain part of the hash; absent optionals remain absent.
    return content_revision(canonical_json_bytes({
        'schema_version': configuration.schema_version,
        'targets': [
            item.model_dump(mode='json', exclude_none=True)
            for item in configuration.targets
        ],
        'default_target_id': configuration.default_target_id,
    }))


def _configuration_payload(configuration: TargetConfiguration) -> dict[str, Any]:
    payload = configuration.model_dump(mode='json')
    payload['targets'] = [
        item.model_dump(mode='json', exclude_none=True)
        for item in configuration.targets
    ]
    return {
        **payload,
        'revision': target_configuration_revision(configuration),
    }


def _target_values(value: ValueNode) -> list[TargetReferenceValue]:
    result: list[TargetReferenceValue] = []

    def visit(current: ValueNode) -> None:
        if isinstance(current, TargetReferenceValue):
            result.append(current)
        for child in iter_value_children(current):
            visit(child)

    visit(value)
    return result


def _json_references(
    root: Path,
    path: Path,
    target_id: str,
    kind: str,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TargetConfigurationCorruptError(
            f'无法扫描目标引用：{path.name}（{exc}）'
        ) from exc
    result: list[dict[str, Any]] = []

    def visit(value: Any, location: str) -> None:
        if isinstance(value, dict):
            if value.get('target_id') == target_id:
                result.append({
                    'kind': kind,
                    'path': path.relative_to(root).as_posix(),
                    'location': f'{location}.target_id',
                })
            for key, child in value.items():
                visit(child, f'{location}.{key}')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f'{location}[{index}]')

    visit(payload, '$')
    return result


class VNextTargetService:
    def __init__(
        self,
        context: VNextWorkspaceContext,
        read_json: Callable[[str], dict[str, Any]],
        write_json: Callable[[str, Any], None],
        project_file: str,
    ) -> None:
        self._context = context
        self._read_json = read_json
        self._write_json = write_json
        self._project_file = project_file

    def _workspace(self, workspace_id: str, generation: int, *, writable: bool = False):
        return self._context.require(workspace_id, generation, writable=writable)

    def _load_project(self, project_path: str) -> tuple[dict[str, Any], TargetConfiguration]:
        project = self._read_json(str(Path(project_path) / self._project_file))
        raw = {
            'schema_version': project.get('targets_schema_version', 1),
            'targets': project.get('targets', []),
            'default_target_id': project.get('default_target_id'),
        }
        try:
            return project, TargetConfiguration.model_validate(raw)
        except ValidationError as exc:
            raise TargetConfigurationCorruptError(f'目标配置损坏：{exc}') from exc

    def configuration(self, workspace_id: str, generation: int) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation)
        _project, configuration = self._load_project(workspace.project_path)
        return _configuration_payload(configuration)

    def resolve(
        self,
        workspace_id: str,
        generation: int,
        target_id: str = '',
    ) -> dict[str, Any] | None:
        workspace = self._workspace(workspace_id, generation)
        _project, configuration = self._load_project(workspace.project_path)
        chosen = str(target_id or configuration.default_target_id or '')
        if not chosen:
            return None
        target = next(
            (item for item in configuration.targets if item.target_id == chosen),
            None,
        )
        if target is None:
            raise TargetNotFoundError(chosen)
        return target.model_dump(mode='json', exclude_none=True)

    def references(
        self,
        workspace_id: str,
        generation: int,
        target_id: str,
    ) -> list[dict[str, Any]]:
        # Reference scanning is an authoring-only operation.  Keep the editable
        # ProgramDocument repository outside the module import graph so the
        # shared target schema remains safe for the frozen Player runtime.
        from .program_repository import ProgramDocumentRepository, ProgramRepositoryError

        workspace = self._workspace(workspace_id, generation)
        root = Path(workspace.project_path).resolve()
        _project, configuration = self._load_project(workspace.project_path)
        if not any(item.target_id == target_id for item in configuration.targets):
            raise TargetNotFoundError(target_id)
        result: list[dict[str, Any]] = []
        program_repository = ProgramDocumentRepository(root)
        if program_repository.functions_path.is_dir():
            for path in sorted(
                program_repository.functions_path.glob('*.json'),
                key=lambda item: item.name.casefold(),
            ):
                try:
                    document = program_repository.load(path.stem).document
                except ProgramRepositoryError as exc:
                    raise TargetConfigurationCorruptError(
                        f'无法扫描项目函数中的目标引用：{path.name}（{exc}）'
                    ) from exc
                for parameter in document.function.parameters:
                    if parameter.default_value is None:
                        continue
                    for reference in _target_values(parameter.default_value):
                        if reference.target_id == target_id:
                            result.append({
                                'kind': 'program_parameter_default',
                                'function_id': document.function.function_id,
                                'function_name': document.function.display_name,
                                'parameter_id': parameter.parameter_id,
                                'value_id': reference.value_id,
                                'field': 'default_value',
                            })
                for statement in iter_statement_tree(document.function.statements):
                    for value in iter_statement_values(statement):
                        if (
                            isinstance(value, TargetReferenceValue)
                            and value.target_id == target_id
                        ):
                            result.append({
                                'kind': 'program_value',
                                'function_id': document.function.function_id,
                                'function_name': document.function.display_name,
                                'statement_id': statement.statement_id,
                                'value_id': value.value_id,
                            })
        try:
            variables = ProjectVariableRepository(root).load().registry
        except ProjectVariableRepositoryError as exc:
            raise TargetConfigurationCorruptError(
                f'无法扫描项目变量中的目标引用：{exc}'
            ) from exc
        for variable in variables.variables:
            for reference in _target_values(variable.default_value):
                if reference.target_id == target_id:
                    result.append({
                        'kind': 'project_variable_default',
                        'variable_id': variable.variable_id,
                        'variable_name': variable.display_name,
                        'value_id': reference.value_id,
                    })
        result.extend(
            _json_references(
                root,
                root / 'assets' / 'registry.json',
                target_id,
                'resource',
            )
        )
        result.extend(
            _json_references(
                root,
                root / 'player' / 'form.json',
                target_id,
                'player_form',
            )
        )
        result.extend(
            _json_references(
                root,
                root / 'player' / 'profiles.json',
                target_id,
                'player_profile',
            )
        )
        return result

    def save(
        self,
        workspace_id: str,
        generation: int,
        *,
        expected_revision: str,
        targets: list[dict[str, Any]],
        default_target_id: str | None,
    ) -> dict[str, Any]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        project, current = self._load_project(workspace.project_path)
        actual_revision = target_configuration_revision(current)
        if expected_revision != actual_revision:
            raise TargetConflictError(expected_revision, actual_revision)
        try:
            updated = TargetConfiguration.model_validate({
                'schema_version': TARGET_CONFIGURATION_SCHEMA_VERSION,
                'targets': targets,
                'default_target_id': default_target_id,
            })
        except ValidationError as exc:
            raise TargetRequestError(str(exc)) from exc
        current_by_id = {item.target_id: item for item in current.targets}
        updated_by_id = {item.target_id: item for item in updated.targets}
        for target_id in sorted(set(current_by_id) - set(updated_by_id)):
            references = self.references(workspace_id, generation, target_id)
            if references:
                raise TargetReferencedError(target_id, references)
        for target_id in sorted(set(current_by_id) & set(updated_by_id)):
            if current_by_id[target_id].type != updated_by_id[target_id].type:
                raise TargetRequestError(
                    f'目标 {target_id} 的类型不能原地改变；请使用新的 target_id'
                )
        # Reference scanning can take longer on a large project. Re-read the
        # manifest immediately before commit so an external target edit is not
        # overwritten and unrelated project metadata edits are preserved.
        latest_project, latest = self._load_project(workspace.project_path)
        latest_revision = target_configuration_revision(latest)
        if latest_revision != actual_revision:
            raise TargetConflictError(expected_revision, latest_revision)
        project = latest_project
        project['targets_schema_version'] = TARGET_CONFIGURATION_SCHEMA_VERSION
        project['targets'] = [item.model_dump(mode='json', exclude_none=True) for item in updated.targets]
        project['default_target_id'] = updated.default_target_id
        self._write_json(str(Path(workspace.project_path) / self._project_file), project)
        return _configuration_payload(updated)


__all__ = [
    'AndroidAdbTargetDefinition',
    'AndroidLocalTargetDefinition',
    'TargetConfiguration',
    'CapturedWindowBinding',
    'TargetConfigurationCorruptError',
    'TargetConflictError',
    'TargetDefinition',
    'TargetNotFoundError',
    'TargetReferencedError',
    'TargetRequestError',
    'TargetServiceError',
    'VNextTargetService',
    'WindowsTargetDefinition',
    'WindowsWorkArea',
    'target_configuration_revision',
]
