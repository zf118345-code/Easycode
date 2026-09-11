"""Player form schema-3 validation and stable binding application service."""

from __future__ import annotations

import copy
import json
import os
from typing import TYPE_CHECKING, Any

from .player_bindings import (
    PLAYER_BINDING_KINDS,
    PLAYER_FORM_SCHEMA_VERSION,
    PLAYER_TERMINAL_ACTION_SPECS,
    PlayerBindingError,
    apply_player_bindings,
    build_player_binding_sources,
    merge_target_overrides,
    validate_player_form_bindings,
    validate_player_target_scope,
)
from .workspace_context import VNextWorkspaceError

if TYPE_CHECKING:
    from .workspace import VNextWorkspaceManager


_CONTROL_TYPES = frozenset({
    'text', 'number', 'toggle', 'select', 'slider-number', 'duration', 'time',
    'color', 'coordinate', 'region', 'resource', 'control-selector', 'gesture-path',
    'file', 'directory', 'list', 'key-value', 'expression', 'button',
})
_PLATFORMS = frozenset({'windows', 'android_adb', 'android_local', 'no_target'})


def _schema_error(code: str, message: str) -> VNextWorkspaceError:
    return VNextWorkspaceError(f'[{code}] {message}')


def _exact_fields(value: dict[str, Any], allowed: set[str], owner: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _schema_error('PLY-FORM-003', f'{owner} 包含未知字段：{unknown[0]}')


def _normalise_options(value: Any, owner: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _schema_error('PLY-FORM-004', f'{owner} 的 options 必须是列表')
    result: list[dict[str, Any]] = []
    identities: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise _schema_error('PLY-FORM-004', f'{owner} 的选项 #{index + 1} 格式无效')
        _exact_fields(
            item,
            {'label', 'value', 'platforms', 'fixed_value', 'fixed_reason'},
            f'{owner} 的选项 #{index + 1}',
        )
        if 'value' not in item:
            raise _schema_error('PLY-FORM-004', f'{owner} 的选项 #{index + 1} 缺少 value')
        platforms = item.get('platforms') or []
        if not isinstance(platforms, list) or any(str(entry) not in _PLATFORMS for entry in platforms):
            raise _schema_error('PLY-FORM-004', f'{owner} 的选项 #{index + 1} 包含未知平台')
        try:
            identity = json.dumps(
                item['value'], ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            )
        except (TypeError, ValueError) as exc:
            raise _schema_error('PLY-FORM-004', f'{owner} 的选项值必须是 JSON') from exc
        if identity in identities:
            raise _schema_error('PLY-FORM-004', f'{owner} 包含重复选项值')
        identities.add(identity)
        normalised = {'label': str(item.get('label') or item['value']), 'value': copy.deepcopy(item['value'])}
        if platforms:
            normalised['platforms'] = [str(entry) for entry in platforms]
        if 'fixed_value' in item:
            if not isinstance(item.get('fixed_value'), bool):
                raise _schema_error(
                    'PLY-FORM-004',
                    f'{owner} 的选项 #{index + 1} 的 fixed_value 必须是布尔值',
                )
            normalised['fixed_value'] = bool(item['fixed_value'])
        if 'fixed_reason' in item:
            reason = str(item.get('fixed_reason') or '').strip()
            if len(reason) > 240:
                raise _schema_error(
                    'PLY-FORM-004',
                    f'{owner} 的选项 #{index + 1} 的 fixed_reason 不能超过 240 个字符',
                )
            if reason:
                normalised['fixed_reason'] = reason
        result.append(normalised)
    return result


def _normalise_terminal_actions(value: Any, owner: str) -> list[dict[str, Any]]:
    """Normalize explicit terminal permissions; absence is strict opt-out."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise _schema_error('PLY-ACTION-001', f'{owner} 的 terminal_actions 必须是列表')
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise _schema_error('PLY-ACTION-001', f'{owner} 的终端动作 #{index + 1} 格式无效')
        _exact_fields(raw, {'action_id', 'platforms'}, f'{owner} 的终端动作 #{index + 1}')
        action_id = str(raw.get('action_id') or '').strip()
        platforms = raw.get('platforms')
        if not action_id or action_id in seen:
            raise _schema_error('PLY-ACTION-001', f'{owner} 包含空或重复的终端动作')
        if action_id not in PLAYER_TERMINAL_ACTION_SPECS:
            raise _schema_error('PLY-ACTION-002', f'{owner} 包含未知终端动作：{action_id}')
        if not isinstance(platforms, list) or not platforms:
            raise _schema_error('PLY-ACTION-003', f'{owner} 的动作 {action_id} 必须选择至少一个平台')
        normalized_platforms = [str(item) for item in platforms]
        if (
            len(set(normalized_platforms)) != len(normalized_platforms)
            or any(item not in _PLATFORMS for item in normalized_platforms)
        ):
            raise _schema_error('PLY-ACTION-003', f'{owner} 的动作 {action_id} 包含无效平台')
        seen.add(action_id)
        result.append({'action_id': action_id, 'platforms': sorted(normalized_platforms)})
    return sorted(result, key=lambda item: str(item['action_id']))


class VNextPlayerService:
    def __init__(self, owner: VNextWorkspaceManager) -> None:
        self._owner = owner

    def form(self, workspace_id: str, generation: int) -> dict[str, Any]:
        owner = self._owner
        workspace = owner._require(workspace_id, generation)
        value = owner._read_json(os.path.join(workspace.project_path, 'player', 'form.json'))
        return self.normalize_form(value)

    @staticmethod
    def normalize_form(value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise _schema_error('PLY-FORM-001', 'Player 表单必须是对象')
        _exact_fields(value, {'schema_version', 'title', 'icon_asset_id', 'features', 'pages', 'bindings'}, 'Player 表单')
        if value.get('schema_version') != PLAYER_FORM_SCHEMA_VERSION:
            raise _schema_error(
                'PLY-FORM-001',
                f'Player 表单必须使用 schema {PLAYER_FORM_SCHEMA_VERSION}；旧表单不兼容',
            )
        if value.get('bindings') not in (None, []):
            raise _schema_error('PLY-FORM-002', '根级 bindings 已移除；绑定必须属于具体控件')
        title = str(value.get('title') or '脚本运行器').strip() or '脚本运行器'
        if len(title) > 256:
            raise _schema_error('PLY-FORM-003', 'Player 标题不能超过 256 个字符')
        icon_asset_id = str(value.get('icon_asset_id') or '').strip()
        if len(icon_asset_id) > 160:
            raise _schema_error('PLY-FORM-003', 'Player 应用图标资源 ID 不能超过 160 个字符')
        features_raw = value.get('features') or {}
        if not isinstance(features_raw, dict):
            raise _schema_error('PLY-FORM-003', 'Player features 必须是对象')
        _exact_fields(features_raw, {'recording'}, 'Player 可选能力')
        if 'recording' in features_raw and not isinstance(features_raw.get('recording'), bool):
            raise _schema_error('PLY-FORM-003', 'Player 录制能力开关必须是布尔值')
        features = {'recording': bool(features_raw.get('recording', False))}
        pages_raw = value.get('pages')
        if not isinstance(pages_raw, list):
            raise _schema_error('PLY-FORM-003', 'Player pages 必须是列表')

        pages: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        seen_controls: set[str] = set()
        for page_index, raw_page in enumerate(pages_raw):
            if not isinstance(raw_page, dict):
                raise _schema_error('PLY-FORM-003', f'Player 页面 #{page_index + 1} 格式无效')
            _exact_fields(raw_page, {'page_id', 'title', 'controls'}, f'Player 页面 #{page_index + 1}')
            page_id = str(raw_page.get('page_id') or '').strip()
            if not page_id or page_id in seen_pages:
                raise _schema_error('PLY-FORM-003', 'Player 页面需要唯一且非空的 page_id')
            seen_pages.add(page_id)
            raw_controls = raw_page.get('controls')
            if not isinstance(raw_controls, list):
                raise _schema_error('PLY-FORM-003', f'Player 页面 {page_id} 的 controls 必须是列表')
            controls: list[dict[str, Any]] = []
            for control_index, raw in enumerate(raw_controls):
                if not isinstance(raw, dict):
                    raise _schema_error('PLY-FORM-003', f'Player 控件 #{control_index + 1} 格式无效')
                _exact_fields(raw, {
                    'control_id', 'type', 'label', 'help', 'default', 'options',
                    'required', 'binding', 'layout', 'parameter_ui', 'constraints',
                    'platforms', 'source_type', 'type_fingerprint', 'terminal_actions',
                }, f'Player 控件 #{control_index + 1}')
                control_id = str(raw.get('control_id') or '').strip()
                control_type = str(raw.get('type') or '').strip()
                binding = raw.get('binding') if isinstance(raw.get('binding'), dict) else {}
                if not control_id or control_id in seen_controls:
                    raise _schema_error('PLY-FORM-003', 'Player 控件需要全局唯一且非空的 control_id')
                if control_type not in _CONTROL_TYPES:
                    raise _schema_error('PLY-FORM-003', f'Player 控件类型无效：{control_type}')
                binding_kind = str(binding.get('kind') or '')
                if binding_kind not in PLAYER_BINDING_KINDS and binding_kind not in {'variable', 'resource', 'target'}:
                    raise _schema_error('PLY-FORM-003', f'Player 控件 {control_id} 缺少有效绑定')
                if control_type == 'button' and binding_kind != 'function_action':
                    raise _schema_error('PLY-FORM-003', f'Player 按钮 {control_id} 必须绑定项目函数')
                if control_type != 'button' and binding_kind == 'function_action':
                    raise _schema_error('PLY-FORM-003', f'Player 参数控件 {control_id} 不能绑定函数动作')
                platforms = raw.get('platforms') or []
                if not isinstance(platforms, list) or any(str(item) not in _PLATFORMS for item in platforms):
                    raise _schema_error('PLY-FORM-004', f'Player 控件 {control_id} 包含未知平台')
                if len({str(item) for item in platforms}) != len(platforms):
                    raise _schema_error('PLY-FORM-004', f'Player 控件 {control_id} 包含重复平台')
                layout = raw.get('layout') or {}
                if not isinstance(layout, dict):
                    raise _schema_error('PLY-FORM-004', f'Player 控件 {control_id} 的 layout 无效')
                _exact_fields(layout, {'span'}, f'Player 控件 {control_id} 的 layout')
                span = layout.get('span', 12)
                if isinstance(span, bool) or not isinstance(span, int) or not 1 <= span <= 12:
                    raise _schema_error('PLY-FORM-004', f'Player 控件 {control_id} 的 span 必须为 1..12')
                constraints = raw.get('constraints') or {}
                parameter_ui = raw.get('parameter_ui') or {}
                if not isinstance(constraints, dict) or not isinstance(parameter_ui, dict):
                    raise _schema_error('PLY-FORM-004', f'Player 控件 {control_id} 的配置必须是对象')
                control: dict[str, Any] = {
                    'control_id': control_id,
                    'type': control_type,
                    'label': str(raw.get('label') or '未命名控件'),
                    'help': str(raw.get('help') or ''),
                    'options': _normalise_options(raw.get('options'), f'Player 控件 {control_id}'),
                    'required': bool(raw.get('required')),
                    'binding': copy.deepcopy(binding),
                    'layout': {'span': span},
                    'parameter_ui': copy.deepcopy(parameter_ui),
                    'constraints': copy.deepcopy(constraints),
                    'platforms': [str(item) for item in platforms],
                }
                if 'default' in raw:
                    control['default'] = copy.deepcopy(raw.get('default'))
                if control_type != 'button':
                    source_type = str(raw.get('source_type') or '').strip()
                    type_fingerprint = str(raw.get('type_fingerprint') or '').strip()
                    if not source_type or not type_fingerprint:
                        raise _schema_error(
                            'PLY-FORM-005',
                            f'Player 控件 {control_id} 缺少来源类型或类型指纹',
                        )
                    control['source_type'] = source_type
                    control['type_fingerprint'] = type_fingerprint
                    control['terminal_actions'] = _normalise_terminal_actions(
                        raw.get('terminal_actions'), f'Player 控件 {control_id}',
                    )
                elif 'source_type' in raw or 'type_fingerprint' in raw:
                    raise _schema_error('PLY-FORM-005', f'Player 按钮 {control_id} 不应声明值类型')
                elif 'terminal_actions' in raw:
                    raise _schema_error('PLY-ACTION-001', f'Player 按钮 {control_id} 不应声明终端字段动作')
                seen_controls.add(control_id)
                controls.append(control)
            pages.append({
                'page_id': page_id,
                'title': str(raw_page.get('title') or f'页面 {page_index + 1}'),
                'controls': controls,
            })
        return {
            'schema_version': PLAYER_FORM_SCHEMA_VERSION,
            'title': title,
            'icon_asset_id': icon_asset_id,
            'features': features,
            'pages': pages,
        }

    def save(self, workspace_id: str, generation: int, form: dict[str, Any]) -> dict[str, Any]:
        with self._owner._lock:
            return self._save_locked(workspace_id, generation, form)

    def _save_locked(self, workspace_id: str, generation: int, form: dict[str, Any]) -> dict[str, Any]:
        owner = self._owner
        workspace = owner._require(workspace_id, generation, writable=True)
        normalized = self.normalize_form(form)
        icon_asset_id = str(normalized.get('icon_asset_id') or '')
        if icon_asset_id:
            from .resources import ProjectAssetService

            icon_asset = next((
                item for item in ProjectAssetService(workspace.project_path).list()['assets']
                if str(item.get('asset_id') or '') == icon_asset_id
            ), None)
            if not icon_asset or icon_asset.get('category') != 'image':
                raise _schema_error('PLY-FORM-006', 'Player 应用图标必须选择现有的图像资源')
            if str(icon_asset.get('extension') or '').casefold() not in {'.png', '.jpg', '.jpeg', '.bmp'}:
                raise _schema_error('PLY-FORM-006', 'Player 应用图标仅支持 PNG、JPG、JPEG 或 BMP')
        targets = list(owner.target_configuration(workspace_id, generation).get('targets') or [])
        program_bindings = [
            control['binding']
            for page in normalized['pages']
            for control in page['controls']
            if control['binding'].get('kind') != 'setting'
        ]
        ecir: dict[str, Any] = {'functions': [], 'project_variables': [], 'targets': targets}
        if program_bindings:
            manifest = owner._read_json(os.path.join(workspace.project_path, 'project.json'))
            entry_function_id = str(manifest.get('entry_function_id') or '')
            linked = owner.compile_program(workspace_id, generation, entry_function_id)
            if not linked.get('valid') or not linked.get('ecir'):
                raise _schema_error('PLY-BIND-013', '项目检查未通过，不能保存 Player 程序绑定')
            ecir = copy.deepcopy(linked['ecir'])
            ecir['targets'] = targets
        try:
            validate_player_form_bindings(ecir, normalized, targets=targets)
        except PlayerBindingError as exc:
            raise VNextWorkspaceError(str(exc)) from exc
        owner._atomic_write_json(os.path.join(workspace.project_path, 'player', 'form.json'), normalized)
        return normalized

    def binding_sources(self, workspace_id: str, generation: int) -> dict[str, Any]:
        """Return the only source catalog the schema-3 designer may expose."""

        owner = self._owner
        workspace = owner._require(workspace_id, generation)
        manifest = owner._read_json(os.path.join(workspace.project_path, 'project.json'))
        entry_function_id = str(manifest.get('entry_function_id') or '')
        linked = owner.compile_program(workspace_id, generation, entry_function_id)
        if not linked.get('valid') or not linked.get('ecir'):
            diagnostics = list(linked.get('diagnostics') or [])
            messages = [
                str(item.get('message') or '')
                for item in diagnostics
                if item.get('severity') == 'error'
            ]
            detail = '；'.join(item for item in messages[:5] if item) or '项目检查未通过'
            return {
                'schema_version': 3,
                'available': False,
                'unavailable_reason': f'先修复项目问题后才能选择 Player 绑定：{detail}',
                'diagnostics': diagnostics,
                'sources': [],
            }
        targets = list(owner.target_configuration(workspace_id, generation).get('targets') or [])
        ecir = copy.deepcopy(linked['ecir'])
        ecir['targets'] = targets
        try:
            result = build_player_binding_sources(ecir, targets=targets)
            return {
                **result,
                'available': True,
                'unavailable_reason': '',
                'diagnostics': [],
            }
        except PlayerBindingError as exc:
            raise VNextWorkspaceError(str(exc)) from exc

    def preview_plan(
        self,
        workspace_id: str,
        generation: int,
        *,
        values: dict[str, Any] | None = None,
        action_control_id: str = '',
        target_id: str = '',
    ) -> dict[str, Any]:
        """Compile and bind an IDE Player preview without starting a host.

        The router owns runtime/message orchestration; this method guarantees
        the preview and packaged Player consume the same signed value slots.
        """

        owner = self._owner
        workspace = owner._require(workspace_id, generation)
        manifest = owner._read_json(os.path.join(workspace.project_path, 'project.json'))
        entry_function_id = str(manifest.get('entry_function_id') or '')
        target = owner.resolve_target(workspace_id, generation, target_id)
        platform = str((target or {}).get('type') or 'no_target')
        linked = owner.program_runtime_plan(
            workspace_id,
            generation,
            entry_function_id,
            target_platform=platform,
        )
        if not linked.get('valid') or not linked.get('execution_plan'):
            return linked
        targets = list(owner.target_configuration(workspace_id, generation).get('targets') or [])
        plan = copy.deepcopy(linked['execution_plan'])
        plan['targets'] = targets
        form = self.form(workspace_id, generation)
        validate_player_target_scope(
            form,
            values or {},
            str((target or {}).get('target_id') or ''),
            error=VNextWorkspaceError,
        )
        bound = apply_player_bindings(
            plan,
            form,
            values or {},
            action_control_id,
            selected_target_id=str((target or {}).get('target_id') or ''),
            error=VNextWorkspaceError,
        )
        merged_target = merge_target_overrides(
            target,
            bound.get('target_overrides') or {},
        )
        return {
            **linked,
            'execution_plan': bound,
            'target': merged_target,
        }

    def apply_values(
        self,
        workspace_id: str,
        generation: int,
        ecir: dict[str, Any],
        values: dict[str, Any],
        action_control_id: str = '',
    ) -> dict[str, Any]:
        return apply_player_bindings(
            ecir,
            self.form(workspace_id, generation),
            values,
            action_control_id,
            error=VNextWorkspaceError,
        )
