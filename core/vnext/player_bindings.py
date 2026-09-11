"""Strict, stable Player bindings shared by IDE, publisher and Player.

Format-6 projects deliberately have no compatibility reader.  A Player form
is an author-approved set of typed value slots.  The slot identity, type and
constraints are signed by stable ids and a deterministic fingerprint; labels
and parameter names never participate in execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .control_defaults import parameter_ui_for_type
from .function_contracts_v6 import official_function_registry_v6
from .project_variables_v6 import (
    runtime_project_value_conforms,
    validate_runtime_constraints,
)

PLAYER_FORM_SCHEMA_VERSION = 3
PLAYER_TYPE_FINGERPRINT_CONTRACT = 'easycode.player.value-slot.v1'
PLAYER_BINDING_KINDS = frozenset({
    'project_variable',
    'function_parameter',
    'statement_parameter',
    'function_action',
    'setting',
})
UNSUPPORTED_PLAYER_BINDING_KINDS = frozenset({'resource', 'target'})

# Terminal actions are an explicit publication permission, not a projection of
# an editor Control.  The value is the host capability required to complete the
# action and the platforms for which a Player host has a real bridge.
PLAYER_TERMINAL_ACTION_SPECS: dict[str, dict[str, Any]] = {
    'pick-point': {
        'capability': 'player.capture.point',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'pick-region': {
        'capability': 'player.capture.region',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'pick-color': {
        'capability': 'player.capture.color',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'capture-image': {
        'capability': 'player.capture.image',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'choose-resource': {
        'capability': 'player.image.choose',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'capture-control': {
        'capability': 'player.capture.control',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'capture-window': {
        'capability': 'player.capture.window',
        'platforms': ['windows'],
        'minimum_android_api': 21,
    },
    'capture-path': {
        'capability': 'player.capture.path',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'choose-file-read': {
        'capability': 'player.file.choose_read',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'choose-file-save': {
        'capability': 'player.file.choose_write',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
    'choose-directory': {
        'capability': 'player.directory.choose',
        'platforms': ['android_adb', 'android_local', 'windows'],
        'minimum_android_api': 21,
    },
}


class PlayerBindingError(ValueError):
    """A deterministic authoring/runtime Player contract failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f'[{code}] {message}')


def _fail(code: str, message: str) -> PlayerBindingError:
    return PlayerBindingError(code, message)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _parameter_ui_actions(value: Any, label: str) -> dict[str, set[str]]:
    """Return a strict action/platform map from a Control UI contract."""

    ui = value if isinstance(value, Mapping) else {}
    raw_actions = ui.get('actions') or []
    if not isinstance(raw_actions, list):
        raise _fail('PLY-ACTION-002', f'Player 控件“{label}”的 parameter_ui.actions 必须是列表')
    actions: dict[str, set[str]] = {}
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, Mapping):
            raise _fail('PLY-ACTION-002', f'Player 控件“{label}”的动作 #{index + 1} 格式无效')
        action_id = str(raw.get('id') or '').strip()
        platforms = raw.get('platforms') or []
        if not action_id or action_id in actions:
            raise _fail('PLY-ACTION-002', f'Player 控件“{label}”包含空或重复的动作 ID')
        if not isinstance(platforms, list) or any(not str(item).strip() for item in platforms):
            raise _fail('PLY-ACTION-002', f'Player 控件“{label}”的动作 {action_id} 平台无效')
        normalized = [str(item) for item in platforms]
        if len(set(normalized)) != len(normalized):
            raise _fail('PLY-ACTION-002', f'Player 控件“{label}”的动作 {action_id} 包含重复平台')
        actions[action_id] = set(normalized)
    return actions


def _default_parameter_ui(value_type: str) -> dict[str, Any]:
    """Build authoritative Control metadata for sources without declared UI."""

    return copy.deepcopy(parameter_ui_for_type(value_type))


def player_type_fingerprint(value_type: str, constraints: Mapping[str, Any] | None = None) -> str:
    """Fingerprint the authoritative source contract, not UI presentation."""

    payload = {
        'contract': PLAYER_TYPE_FINGERPRINT_CONTRACT,
        'value_type': str(value_type),
        'constraints': copy.deepcopy(dict(constraints or {})),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()
    return f'sha256:{digest}'


# Only settings with a real target-driver consumer belong here.  ``target_id``
# is part of every setting binding, so one target's form value can never leak
# into another target selected by a different Player instance.
TARGET_SETTING_SPECS: dict[str, dict[str, Any]] = {
    'target.allow_physical_fallback': {
        'type': 'toggle', 'label': '允许物理输入兜底', 'value_type': 'bool',
        'constraints': {}, 'target_types': ['windows'],
    },
    'target.window_title': {
        'type': 'text', 'label': '目标窗口标题', 'value_type': 'string',
        'constraints': {'max_length': 512}, 'target_types': ['windows'],
    },
    'target.window_binding': {
        'type': 'control-selector', 'label': '目标窗口实例',
        'value_type': 'optional<window_binding>', 'constraints': {},
        'target_types': ['windows'],
        'parameter_ui': {
            'control': 'control-selector',
            'editor_strategy': 'capture',
            'action_placement': 'adjacent',
            'actions': [{
                'id': 'capture-window',
                'capture_kind': 'point',
                'platforms': ['windows'],
            }],
            'placeholder': '捕获要由当前 Player 实例控制的窗口',
            'help': '同名窗口必须逐个实例捕获；窗口重启后若仍无法唯一定位，Player 会要求重新捕获。',
            'importance': 'primary',
        },
    },
    'target.device_serial': {
        'type': 'text', 'label': 'Android 设备序列号', 'value_type': 'string',
        'constraints': {
            'min_length': 1, 'max_length': 256,
            'pattern': r'[^\s\x00-\x1f]+',
        },
        'target_types': ['android_adb'],
    },
    'target.work_area.mode': {
        'type': 'select', 'label': '工作区域模式',
        'value_type': 'enum<work_area_mode>',
        'constraints': {'choices': [
            {'label': '客户区', 'value': 'client'},
            {'label': '完整窗口', 'value': 'window'},
            {'label': '全屏幕', 'value': 'desktop'},
            {'label': '自定义区域', 'value': 'region'},
        ]},
        'target_types': ['windows'],
        'options': [
            {'label': '客户区', 'value': 'client'},
            {'label': '完整窗口', 'value': 'window'},
            {'label': '全屏幕', 'value': 'desktop'},
            {'label': '自定义区域', 'value': 'region'},
        ],
    },
    'target.work_area.region': {
        'type': 'region', 'label': '自定义工作区域', 'value_type': 'rect',
        'constraints': {}, 'target_types': ['windows'],
    },
}


def _collect_instructions(ecir: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Collect every instruction and remember its owning project function."""

    result: dict[str, dict[str, Any]] = {}

    def visit(value: Any, owner_function_id: str) -> None:
        if isinstance(value, dict):
            instruction_id = str(value.get('instruction_id') or '')
            if instruction_id and value.get('opcode'):
                if instruction_id in result:
                    raise _fail('PLY-BIND-004', f'编译产物包含重复语句 ID：{instruction_id}')
                result[instruction_id] = {
                    'instruction': value,
                    'owner_function_id': owner_function_id,
                }
            for child in value.values():
                visit(child, owner_function_id)
        elif isinstance(value, list):
            for child in value:
                visit(child, owner_function_id)

    for function in ecir.get('functions') or []:
        owner = str(function.get('function_id') or '')
        visit(function.get('instructions') or [], owner)
    return result


def _function_map(ecir: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get('function_id') or ''): item
        for item in ecir.get('functions') or [] if item.get('function_id')
    }


def _project_variable_map(ecir: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get('variable_id') or ''): item
        for item in ecir.get('project_variables') or [] if item.get('variable_id')
    }


def _value_override_slot_map(ecir: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in ecir.get('value_override_slots') or []:
        if not isinstance(raw, Mapping):
            raise _fail('PLY-BIND-004', '编译产物包含无效的嵌套值签名插槽')
        value_id = str(raw.get('value_id') or '')
        path = raw.get('path')
        if (
            not value_id or value_id in result
            or not isinstance(path, list) or not path or len(path) > 64
            or any(not isinstance(part, (str, int)) or isinstance(part, bool) for part in path)
            or not str(raw.get('value_type') or '')
        ):
            raise _fail('PLY-BIND-004', '编译产物包含重复或不完整的嵌套值签名插槽')
        result[value_id] = copy.deepcopy(dict(raw))
    return result


def _path_value(root: Any, path: Iterable[str | int]) -> Any:
    current = root
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part < 0 or part >= len(current):
                raise _fail('PLY-BIND-004', '嵌套值签名路径已失效')
            current = current[part]
        else:
            if not isinstance(current, Mapping) or part not in current:
                raise _fail('PLY-BIND-004', '嵌套值签名路径已失效')
            current = current[part]
    return current


def _set_path_value(root: Any, path: Iterable[str | int], replacement: Any) -> None:
    parts = list(path)
    if not parts:
        raise _fail('PLY-BIND-004', '嵌套值签名路径不能为空')
    parent = _path_value(root, parts[:-1]) if len(parts) > 1 else root
    final = parts[-1]
    if isinstance(final, int):
        if not isinstance(parent, list) or final < 0 or final >= len(parent):
            raise _fail('PLY-BIND-004', '嵌套值签名路径已失效')
        parent[final] = copy.deepcopy(replacement)
    else:
        if not isinstance(parent, dict) or final not in parent:
            raise _fail('PLY-BIND-004', '嵌套值签名路径已失效')
        parent[final] = copy.deepcopy(replacement)


def _nested_slot_labels(root: Any, path: Iterable[str | int]) -> list[str]:
    """Project a signed ECIR path into short non-technical authoring labels."""

    parts = list(path)
    current = root
    labels: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        kind = str(current.get('kind') or '') if isinstance(current, Mapping) else ''
        if kind == 'operation' and part == 'inputs' and index + 1 < len(parts):
            input_id = str(parts[index + 1])
            input_name = input_id.rsplit('.input.', 1)[-1]
            try:
                from .value_catalog_v6 import PURE_OPERATION_PRESENTATIONS
                presentation = PURE_OPERATION_PRESENTATIONS.get(str(current.get('operation_id') or ''))
                label = presentation.input_labels.get(input_name, input_name) if presentation else input_name
            except Exception:
                label = input_name
            labels.append(str(label))
            current = (current.get('inputs') or {}).get(input_id)
            index += 2
            continue
        if kind == 'selector' and part == 'expression':
            labels.append('逐项条件' if current.get('result_type') == 'bool' else '逐项结果')
        elif kind == 'compare' and part in {'left', 'right'}:
            labels.append('左侧值' if part == 'left' else '右侧值')
        elif kind == 'condition_group' and part == 'conditions' and index + 1 < len(parts):
            labels.append(f'第 {int(parts[index + 1]) + 1} 个条件')
            current = (current.get('conditions') or [])[int(parts[index + 1])]
            index += 2
            continue
        elif kind == 'list' and part == 'items' and index + 1 < len(parts):
            labels.append(f'第 {int(parts[index + 1]) + 1} 项')
            current = (current.get('items') or [])[int(parts[index + 1])]
            index += 2
            continue
        elif kind == 'map' and part == 'entries' and index + 2 < len(parts):
            entry_index = int(parts[index + 1])
            side = str(parts[index + 2])
            labels.append(f'第 {entry_index + 1} 项' + ('键' if side == 'key' else '值'))
            current = (current.get('entries') or [])[entry_index].get(side)
            index += 3
            continue
        elif kind == 'record' and part == 'fields' and index + 1 < len(parts):
            field_id = str(parts[index + 1])
            label = field_id
            try:
                from .record_types_v6 import record_type_contract
                contract = record_type_contract(str(current.get('record_type') or ''))
                field = next((item for item in contract.fields if item.field_id == field_id), None)
                if field is not None:
                    label = field.display_name
            except Exception:
                pass
            labels.append(label)
            current = (current.get('fields') or {}).get(field_id)
            index += 2
            continue
        elif kind == 'member_access' and part == 'source':
            labels.append('来源')
        elif kind == 'not' and part == 'condition':
            labels.append('条件')
        else:
            labels.append(str(part))
        current = _path_value(current, [part])
        index += 1
    return labels


def _parameter_by_id(function: Mapping[str, Any], parameter_id: str) -> dict[str, Any] | None:
    return next((
        item for item in function.get('parameter_definitions') or []
        if str(item.get('parameter_id') or '') == parameter_id
    ), None)


def _raw_choices(constraints: Mapping[str, Any]) -> list[Any] | None:
    choices = constraints.get('choices')
    if choices is None:
        return None
    if not isinstance(choices, list):
        raise _fail('PLY-BIND-008', 'choices 必须是列表')
    return [
        item.get('value') if isinstance(item, dict) and 'value' in item else item
        for item in choices
    ]


def _runtime_constraints(constraints: Mapping[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(dict(constraints or {}))
    # File-picker filters are authoring/terminal UI constraints. They narrow
    # what the system dialog offers, but are not scalar runtime constraints.
    result.pop('extensions', None)
    choices = _raw_choices(result)
    if choices is not None:
        result['choices'] = choices
    return result


def _validate_constraint_definition(constraints: Mapping[str, Any], label: str) -> None:
    allowed = {
        'minimum', 'maximum', 'step', 'min_length', 'max_length',
        'min_items', 'max_items', 'unique_items', 'choices', 'pattern',
        'extensions',
    }
    unknown = sorted(set(constraints) - allowed)
    if unknown:
        raise _fail('PLY-BIND-008', f'Player 控件“{label}”包含未知约束：{unknown[0]}')
    extensions = constraints.get('extensions')
    if extensions is not None and (
        not isinstance(extensions, list)
        or any(
            not isinstance(item, str)
            or not item.strip().startswith('.')
            or len(item.strip()) > 24
            for item in extensions
        )
    ):
        raise _fail('PLY-BIND-008', f'Player 控件“{label}”的 extensions 必须是 .json 这样的扩展名列表')
    try:
        validate_runtime_constraints(None, _runtime_constraints(constraints))
    except ValueError as exc:
        raise _fail('PLY-BIND-008', f'Player 控件“{label}”约束无效：{exc}') from exc


def _validate_value(value: Any, value_type: str, constraints: Mapping[str, Any], label: str) -> None:
    current = _value_kind(value_type)
    if current == 'window_binding':
        if value is None:
            return
        try:
            from .target_service import CapturedWindowBinding

            CapturedWindowBinding.model_validate(value)
        except Exception as exc:
            raise _fail('PLY-BIND-007', f'Player 控件“{label}”的窗口绑定无效') from exc
    elif not runtime_project_value_conforms(value, value_type):
        raise _fail('PLY-BIND-007', f'Player 控件“{label}”的值不符合类型 {value_type}')
    try:
        validate_runtime_constraints(value, _runtime_constraints(constraints))
    except ValueError as exc:
        raise _fail('PLY-BIND-008', f'Player 控件“{label}”的值违反约束：{exc}') from exc


def _value_kind(value_type: str) -> str:
    current = value_type
    while current.startswith('optional<') and current.endswith('>'):
        current = current[len('optional<'):-1]
    return current


def _control_accepts(control_type: str, value_type: str) -> bool:
    current = _value_kind(value_type)
    if control_type == 'expression':
        return True
    if control_type == 'text':
        return current in {'string', 'relative_path', 'url', 'timezone'} or current.startswith('enum<')
    if control_type in {'number', 'slider-number'}:
        return current in {'int64', 'float64', 'percentage'}
    if control_type == 'toggle':
        return current == 'bool'
    if control_type == 'select':
        return current.startswith('enum<') or current == 'string'
    if control_type == 'duration':
        return current == 'duration'
    if control_type == 'time':
        return current in {'date', 'datetime', 'time', 'time_of_day'}
    if control_type == 'color':
        return current == 'color'
    if control_type == 'coordinate':
        return current == 'point'
    if control_type == 'region':
        return current == 'rect'
    if control_type == 'resource':
        return current.startswith('asset_ref')
    if control_type == 'control-selector':
        return current in {'control_selector', 'window_binding'} or current.startswith('selector')
    if control_type == 'gesture-path':
        return current in {'path', 'gesture_path'}
    if control_type == 'file':
        return current == 'file_ref' or current.startswith('file_ref<')
    if control_type == 'directory':
        return current == 'directory_ref' or current.startswith('directory_ref<')
    if control_type == 'list':
        return current.startswith('list<')
    if control_type == 'key-value':
        return current.startswith('map<') or current in {'json', 'json_value', 'message_value'}
    return False


def _normalize_runtime_value(value: Any, value_type: str) -> Any:
    """Canonicalise Control payloads without parsing display text."""

    current = _value_kind(value_type)
    if value is None:
        return None
    if current == 'duration' and isinstance(value, dict) and set(value) <= {'kind', 'milliseconds'}:
        return value.get('milliseconds')
    if current == 'point' and isinstance(value, (list, tuple)) and len(value) == 2:
        return {'x': value[0], 'y': value[1]}
    if current == 'point' and isinstance(value, dict):
        return {'x': value.get('x'), 'y': value.get('y')}
    if current == 'rect' and isinstance(value, (list, tuple)) and len(value) == 4:
        return {'x': value[0], 'y': value[1], 'width': value[2], 'height': value[3]}
    if current == 'rect' and isinstance(value, dict):
        return {
            'x': value.get('x'), 'y': value.get('y'),
            'width': value.get('width'), 'height': value.get('height'),
        }
    if current == 'color' and isinstance(value, dict):
        return {
            f'color.field.{name}': value.get(f'color.field.{name}', value.get(name))
            for name in ('red', 'green', 'blue', 'alpha')
        }
    if current == 'path' and isinstance(value, dict) and value.get('kind') == 'path':
        value = value.get('points')
    if current == 'path' and isinstance(value, list):
        return [
            {'x': item[0], 'y': item[1]}
            if isinstance(item, (list, tuple)) and len(item) == 2
            else {'x': item.get('x'), 'y': item.get('y')}
            if isinstance(item, dict)
            else item
            for item in value
        ]
    if current.startswith('asset_ref') and isinstance(value, str):
        return {'asset_id': value}
    if current == 'window_binding' and isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    if current == 'target_ref' and isinstance(value, str):
        return {'target_id': value}
    return copy.deepcopy(value)


def _ecir_static_to_runtime(value: Any) -> Any:
    """Project a compiler static value into the Control runtime value shape."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return copy.deepcopy(value)
    if isinstance(value, list):
        return [_ecir_static_to_runtime(item) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    kind = str(value.get('kind') or '')
    if kind == 'duration':
        return value.get('milliseconds')
    if kind in {'date', 'datetime', 'time'}:
        return value.get('value')
    if kind == 'point':
        return {'x': value.get('x'), 'y': value.get('y')}
    if kind == 'rect':
        return {
            'x': value.get('x'), 'y': value.get('y'),
            'width': value.get('width'), 'height': value.get('height'),
        }
    if kind == 'path':
        return [
            {'x': item.get('x'), 'y': item.get('y')}
            for item in value.get('points') or [] if isinstance(item, dict)
        ]
    if kind == 'list':
        return [_ecir_static_to_runtime(item) for item in value.get('items') or []]
    if kind == 'map':
        result: dict[Any, Any] = {}
        for entry in value.get('entries') or []:
            if not isinstance(entry, dict):
                continue
            key = _ecir_static_to_runtime(entry.get('key'))
            result[key] = _ecir_static_to_runtime(entry.get('value'))
        return result
    if kind == 'record':
        return {
            key: _ecir_static_to_runtime(item)
            for key, item in (value.get('fields') or {}).items()
        }
    if kind == 'json':
        return copy.deepcopy(value.get('value'))
    if kind == 'asset_ref':
        return {'asset_id': value.get('asset_id'), 'asset_kind': value.get('asset_kind')}
    if kind == 'target_ref':
        return {'target_id': value.get('target_id')}
    return {key: _ecir_static_to_runtime(item) for key, item in value.items()}


def _recommended_control(value_type: str, declared: str = '') -> str:
    if declared and declared != 'auto':
        return declared
    current = _value_kind(value_type)
    if current == 'bool':
        return 'toggle'
    if current in {'int64', 'float64', 'percentage'}:
        return 'number'
    if current == 'duration':
        return 'duration'
    if current in {'date', 'datetime', 'time', 'time_of_day'}:
        return 'time'
    if current == 'color':
        return 'color'
    if current == 'point':
        return 'coordinate'
    if current == 'rect':
        return 'region'
    if current == 'path':
        return 'gesture-path'
    if current == 'gesture_path':
        return 'gesture-path'
    if current == 'file_ref' or current.startswith('file_ref<'):
        return 'file'
    if current == 'directory_ref' or current.startswith('directory_ref<'):
        return 'directory'
    if current == 'control_selector' or current.startswith('selector'):
        return 'control-selector'
    if current == 'window_binding':
        return 'control-selector'
    if current.startswith('asset_ref'):
        return 'resource'
    if current.startswith('list<'):
        return 'list'
    if current.startswith('map<') or current in {'json', 'json_value', 'message_value'}:
        return 'key-value'
    if current.startswith('enum<'):
        return 'select'
    if current in {'string', 'relative_path', 'url', 'timezone'}:
        return 'text'
    return 'expression'


def _ecir_value_is_static_root(value: Any) -> bool:
    """A root slot may replace a static value, never an expression/source."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return not isinstance(value, float) or math.isfinite(value)
    if isinstance(value, list):
        return all(_ecir_value_is_static_root(item) for item in value)
    if not isinstance(value, dict):
        return False
    kind = str(value.get('kind') or '')
    if kind in {
        'reference', 'member_access', 'operation', 'compare', 'condition_group',
        'not', 'asset_ref', 'target_ref', 'entity_ref',
    }:
        return False
    if kind in {'duration', 'date', 'datetime', 'time', 'point', 'rect', 'path', 'json'}:
        return True
    if kind == 'list':
        return all(_ecir_value_is_static_root(item) for item in value.get('items') or [])
    if kind == 'map':
        return all(
            _ecir_value_is_static_root(item.get('key'))
            and _ecir_value_is_static_root(item.get('value'))
            for item in value.get('entries') or [] if isinstance(item, dict)
        )
    if kind == 'record':
        return all(_ecir_value_is_static_root(item) for item in (value.get('fields') or {}).values())
    return not kind and all(_ecir_value_is_static_root(item) for item in value.values())


def _source_for_binding(
    binding: Mapping[str, Any], *, ecir: Mapping[str, Any],
    instructions: Mapping[str, Mapping[str, Any]],
    functions: Mapping[str, Mapping[str, Any]],
    project_variables: Mapping[str, Mapping[str, Any]],
    targets: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    kind = str(binding.get('kind') or '')
    if kind in UNSUPPORTED_PLAYER_BINDING_KINDS:
        raise _fail('PLY-BIND-011', f'Player 绑定类型 {kind} 尚无编译器签名插槽')
    if kind == 'variable':
        raise _fail('PLY-BIND-002', '旧 variable 绑定已移除；请选择明确的项目变量或函数参数')
    if kind not in PLAYER_BINDING_KINDS:
        raise _fail('PLY-BIND-002', f'不支持的 Player 绑定类型：{kind or "<empty>"}')

    allowed_fields = {
        'project_variable': {'kind', 'variable_id'},
        'function_parameter': {'kind', 'function_id', 'parameter_id'},
        'statement_parameter': {
            'kind', 'function_id', 'statement_id', 'parameter_id', 'value_id',
        },
        'function_action': {'kind', 'function_id'},
        'setting': {'kind', 'target_id', 'setting_id'},
    }[kind]
    required_fields = allowed_fields - {'kind', 'value_id'}
    unknown = sorted(set(binding) - allowed_fields)
    missing = sorted(field for field in required_fields if not str(binding.get(field) or '').strip())
    if unknown or missing:
        detail = f'未知字段 {unknown[0]}' if unknown else f'缺少字段 {missing[0]}'
        raise _fail('PLY-BIND-003', f'{kind} 绑定字段无效：{detail}')

    if kind == 'project_variable':
        variable_id = str(binding['variable_id'])
        definition = project_variables.get(variable_id)
        if definition is None:
            raise _fail('PLY-BIND-004', f'项目变量绑定已失效：{variable_id}')
        value_type = str(definition.get('value_type') or '')
        return {
            'identity': (kind, variable_id),
            'value_type': value_type,
            'constraints': copy.deepcopy(dict(definition.get('constraints') or {})),
            'platforms': list(ecir.get('supported_platforms') or []),
            'parameter_ui': _default_parameter_ui(value_type),
        }

    if kind == 'function_parameter':
        function_id = str(binding['function_id'])
        parameter_id = str(binding['parameter_id'])
        function = functions.get(function_id)
        parameter = _parameter_by_id(function or {}, parameter_id)
        if function is None or parameter is None:
            raise _fail('PLY-BIND-004', f'函数参数绑定已失效：{function_id}/{parameter_id}')
        value_type = str(parameter.get('value_type') or '')
        return {
            'identity': (kind, function_id, parameter_id),
            'value_type': value_type,
            'constraints': copy.deepcopy(dict(parameter.get('constraints') or {})),
            # A Player control may strengthen an optional source, but it must
            # never weaken a required project-function parameter.  Runtime
            # relevance is decided after the action button selects the real
            # entry function.
            'required': bool(parameter.get('required', True)),
            'platforms': list(ecir.get('supported_platforms') or []),
            'parameter_ui': copy.deepcopy(
                dict(parameter.get('ui') or _default_parameter_ui(value_type))
            ),
        }

    if kind == 'statement_parameter':
        owner_function_id = str(binding['function_id'])
        statement_id = str(binding['statement_id'])
        parameter_id = str(binding['parameter_id'])
        nested_value_id = str(binding.get('value_id') or '')
        record = instructions.get(statement_id)
        instruction = (record or {}).get('instruction')
        if instruction is None or str((record or {}).get('owner_function_id') or '') != owner_function_id:
            raise _fail('PLY-BIND-004', f'语句绑定已失效：{owner_function_id}/{statement_id}')
        if parameter_id not in (instruction.get('arguments') or {}):
            raise _fail('PLY-BIND-004', f'语句参数绑定已失效：{statement_id}/{parameter_id}')
        stable_parameter_id = str((instruction.get('parameter_ids') or {}).get(parameter_id) or '')
        if stable_parameter_id != parameter_id:
            raise _fail('PLY-BIND-004', f'语句参数稳定 ID 已失效：{statement_id}/{parameter_id}')

        if nested_value_id:
            slot = _value_override_slot_map(ecir).get(nested_value_id)
            if slot is None or any(
                str(slot.get(field) or '') != expected
                for field, expected in (
                    ('function_id', owner_function_id),
                    ('statement_id', statement_id),
                    ('parameter_id', parameter_id),
                )
            ):
                raise _fail('PLY-BIND-010', f'嵌套值签名插槽已失效：{nested_value_id}')
            raw_nested = _path_value(
                (instruction.get('arguments') or {})[parameter_id],
                slot.get('path') or [],
            )
            if not _ecir_value_is_static_root(raw_nested):
                raise _fail('PLY-BIND-012', '嵌套值签名只能指向静态值')
            nested_type = str(slot.get('value_type') or '')
            return {
                'identity': (
                    kind, owner_function_id, statement_id,
                    parameter_id, nested_value_id,
                ),
                'value_type': nested_type,
                'constraints': {},
                'instruction': instruction,
                'value_path': copy.deepcopy(list(slot.get('path') or [])),
                'platforms': list(
                    instruction.get('platforms')
                    or ecir.get('supported_platforms') or []
                ),
                'parameter_ui': _default_parameter_ui(nested_type),
            }

        if not _ecir_value_is_static_root((instruction.get('arguments') or {}).get(parameter_id)):
            raise _fail('PLY-BIND-012', '只能暴露静态根参数；动态参数请使用编译器提供的嵌套值插槽')

        called_function_id = str(instruction.get('function_id') or '')
        called = functions.get(called_function_id)
        parameter: Any = _parameter_by_id(called or {}, parameter_id)
        if parameter is None:
            try:
                official = official_function_registry_v6.require(called_function_id)
            except KeyError as exc:
                raise _fail('PLY-BIND-004', f'语句调用契约已失效：{called_function_id}') from exc
            parameter = next((item for item in official.parameters if item.parameter_id == parameter_id), None)
        if parameter is None:
            raise _fail('PLY-BIND-004', f'语句参数契约已失效：{called_function_id}/{parameter_id}')
        value_type = (
            str(parameter.get('value_type') or '') if isinstance(parameter, dict)
            else str(parameter.value_type)
        )
        constraints = (
            dict(parameter.get('constraints') or {}) if isinstance(parameter, dict)
            else dict(parameter.constraints)
        )
        parameter_ui = (
            dict(parameter.get('ui') or _default_parameter_ui(value_type))
            if isinstance(parameter, dict)
            else dict(parameter.ui or _default_parameter_ui(value_type))
        )
        if str(parameter_ui.get('importance') or '') == 'internal':
            raise _fail('PLY-BIND-013', '该参数由运行时管理，不能暴露为 Player 字段')
        return {
            'identity': (kind, owner_function_id, statement_id, parameter_id),
            'value_type': value_type,
            'constraints': copy.deepcopy(constraints),
            'instruction': instruction,
            'platforms': list(instruction.get('platforms') or ecir.get('supported_platforms') or []),
            'parameter_ui': copy.deepcopy(parameter_ui),
        }

    if kind == 'function_action':
        function_id = str(binding['function_id'])
        if function_id not in functions:
            raise _fail('PLY-BIND-004', f'函数按钮绑定已失效：{function_id}')
        return {
            'identity': (kind, function_id),
            'action': True,
            'platforms': list(ecir.get('supported_platforms') or []),
        }

    setting_id = str(binding['setting_id'])
    target_id = str(binding['target_id'])
    spec = TARGET_SETTING_SPECS.get(setting_id)
    target = targets.get(target_id)
    if spec is None:
        raise _fail('PLY-BIND-009', f'运行设置没有真实消费者：{setting_id}')
    if target is None:
        raise _fail('PLY-BIND-004', f'运行设置目标已失效：{target_id}')
    if str(target.get('type') or '') not in set(spec['target_types']):
        raise _fail('PLY-BIND-009', f'运行设置 {setting_id} 不适用于目标 {target_id}')
    value_type = str(spec['value_type'])
    return {
        'identity': (kind, target_id, setting_id),
        'value_type': value_type,
        'constraints': copy.deepcopy(dict(spec.get('constraints') or {})),
        'target': target,
        'platforms': [str(target.get('type') or '')],
        'parameter_ui': copy.deepcopy(
            dict(spec.get('parameter_ui') or _default_parameter_ui(value_type))
        ),
    }


def validate_player_form_bindings(
    ecir: Mapping[str, Any], form: Mapping[str, Any],
    *, targets: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate all stable references and return resolved source contracts."""

    if form.get('schema_version') != PLAYER_FORM_SCHEMA_VERSION:
        raise _fail('PLY-BIND-001', f'Player 表单必须使用 schema {PLAYER_FORM_SCHEMA_VERSION}')
    if form.get('bindings'):
        raise _fail('PLY-BIND-003', 'Player 根级 bindings 已移除；绑定必须属于具体控件')

    detached = copy.deepcopy(dict(ecir))
    instructions = _collect_instructions(detached)
    functions = _function_map(detached)
    variables = _project_variable_map(detached)
    target_items = list(targets if targets is not None else detached.get('targets') or [])
    target_map = {
        str(item.get('target_id') or ''): dict(item)
        for item in target_items if item.get('target_id')
    }
    identities: dict[tuple[str, ...], str] = {}
    resolved: dict[str, dict[str, Any]] = {}
    control_ids: set[str] = set()

    for page in form.get('pages') or []:
        for control in page.get('controls') or []:
            control_id = str(control.get('control_id') or '')
            if not control_id or control_id in control_ids:
                raise _fail('PLY-BIND-003', 'Player 控件 ID 必须全局唯一且非空')
            control_ids.add(control_id)
            label = str(control.get('label') or control_id or '未命名控件')
            binding = control.get('binding') if isinstance(control.get('binding'), dict) else {}
            source = _source_for_binding(
                binding,
                ecir=detached,
                instructions=instructions,
                functions=functions,
                project_variables=variables,
                targets=target_map,
            )
            identity = tuple(source['identity'])
            if identity in identities:
                raise _fail(
                    'PLY-BIND-006',
                    f'Player 控件“{label}”与“{identities[identity]}”重复绑定同一来源',
                )
            identities[identity] = label

            declared_platforms = {str(item) for item in control.get('platforms') or []}
            source_platforms = {str(item) for item in source.get('platforms') or []}
            if declared_platforms and not declared_platforms.issubset(source_platforms):
                raise _fail(
                    'PLY-BIND-005',
                    f'Player 控件“{label}”声明了来源不支持的平台',
                )

            if source.get('action'):
                if control.get('terminal_actions'):
                    raise _fail('PLY-ACTION-001', f'Player 按钮“{label}”不能声明终端字段动作')
                if control.get('type') != 'button':
                    raise _fail('PLY-BIND-003', f'Player 函数动作“{label}”必须使用按钮')
                resolved[control_id] = source
                continue
            if control.get('type') == 'button':
                raise _fail('PLY-BIND-003', f'Player 值控件“{label}”不能使用按钮')
            value_type = str(source['value_type'])
            constraints = dict(source['constraints'])
            _validate_constraint_definition(constraints, label)
            if str(control.get('source_type') or '') != value_type:
                raise _fail('PLY-BIND-005', f'Player 控件“{label}”的来源类型指纹已失效')
            expected_fingerprint = player_type_fingerprint(value_type, constraints)
            if str(control.get('type_fingerprint') or '') != expected_fingerprint:
                raise _fail('PLY-BIND-005', f'Player 控件“{label}”的类型或约束已发生变化')
            if not _control_accepts(str(control.get('type') or ''), value_type):
                raise _fail('PLY-BIND-005', f'Player 控件“{label}”不适用于类型 {value_type}')
            fixed_options = [
                option for option in control.get('options') or []
                if isinstance(option, Mapping)
                and ('fixed_value' in option or 'fixed_reason' in option)
            ]
            if fixed_options:
                if str(control.get('type') or '') != 'key-value' or value_type != 'map<string,bool>':
                    raise _fail(
                        'PLY-OPTION-001',
                        f'Player 控件“{label}”只有布尔字典复选清单可以固定选项',
                    )
                default_value = control.get('default')
                if not isinstance(default_value, Mapping):
                    raise _fail(
                        'PLY-OPTION-001',
                        f'Player 控件“{label}”固定选项前必须提供布尔字典默认值',
                    )
                for option in fixed_options:
                    key = option.get('value')
                    if 'fixed_value' not in option:
                        raise _fail(
                            'PLY-OPTION-001',
                            f'Player 控件“{label}”的固定原因缺少 fixed_value',
                        )
                    if not isinstance(key, str) or key not in default_value:
                        raise _fail(
                            'PLY-OPTION-001',
                            f'Player 控件“{label}”的固定选项没有对应默认字典键',
                        )
                    if not isinstance(default_value.get(key), bool):
                        raise _fail(
                            'PLY-OPTION-001',
                            f'Player 控件“{label}”的固定选项默认值必须是布尔值',
                        )
            terminal_actions = control.get('terminal_actions') or []
            if not isinstance(terminal_actions, list):
                raise _fail('PLY-ACTION-001', f'Player 控件“{label}”的 terminal_actions 必须是列表')
            control_ui_actions = _parameter_ui_actions(control.get('parameter_ui'), label)
            source_ui_actions = _parameter_ui_actions(source.get('parameter_ui'), label)
            effective_control_platforms = declared_platforms or source_platforms
            normalized_terminal_actions: list[dict[str, Any]] = []
            seen_action_ids: set[str] = set()
            for index, raw_action in enumerate(terminal_actions):
                if not isinstance(raw_action, Mapping):
                    raise _fail(
                        'PLY-ACTION-001',
                        f'Player 控件“{label}”的终端动作 #{index + 1} 格式无效',
                    )
                unknown = sorted(set(raw_action) - {'action_id', 'platforms'})
                if unknown:
                    raise _fail(
                        'PLY-ACTION-001',
                        f'Player 控件“{label}”的终端动作包含未知字段：{unknown[0]}',
                    )
                action_id = str(raw_action.get('action_id') or '').strip()
                raw_platforms = raw_action.get('platforms')
                if not action_id or action_id in seen_action_ids:
                    raise _fail('PLY-ACTION-001', f'Player 控件“{label}”包含空或重复的终端动作')
                if action_id not in PLAYER_TERMINAL_ACTION_SPECS:
                    raise _fail('PLY-ACTION-002', f'Player 控件“{label}”声明了未知终端动作：{action_id}')
                if action_id not in control_ui_actions:
                    raise _fail(
                        'PLY-ACTION-002',
                        f'Player 控件“{label}”的动作 {action_id} 不属于 parameter_ui.actions',
                    )
                if action_id not in source_ui_actions:
                    raise _fail(
                        'PLY-ACTION-002',
                        f'Player 控件“{label}”的动作 {action_id} 已不属于来源契约',
                    )
                if not isinstance(raw_platforms, list) or not raw_platforms:
                    raise _fail(
                        'PLY-ACTION-003',
                        f'Player 控件“{label}”的动作 {action_id} 必须选择至少一个平台',
                    )
                platforms = [str(item) for item in raw_platforms]
                if any(not item for item in platforms) or len(set(platforms)) != len(platforms):
                    raise _fail(
                        'PLY-ACTION-003',
                        f'Player 控件“{label}”的动作 {action_id} 包含空或重复平台',
                    )
                permitted = (
                    set(PLAYER_TERMINAL_ACTION_SPECS[action_id]['platforms'])
                    & source_platforms
                    & effective_control_platforms
                    & control_ui_actions[action_id]
                    & source_ui_actions[action_id]
                )
                if not set(platforms).issubset(permitted):
                    raise _fail(
                        'PLY-ACTION-003',
                        f'Player 控件“{label}”的动作 {action_id} 声明了无效平台交集',
                    )
                seen_action_ids.add(action_id)
                normalized_terminal_actions.append({
                    'action_id': action_id,
                    'platforms': sorted(platforms),
                })
            source['terminal_actions'] = sorted(
                normalized_terminal_actions,
                key=lambda item: str(item['action_id']),
            )
            control_constraints = dict(control.get('constraints') or {})
            _validate_constraint_definition(control_constraints, label)
            if 'default' in control:
                default = _normalize_runtime_value(control.get('default'), value_type)
                _validate_value(default, value_type, constraints, label)
                _validate_value(default, value_type, control_constraints, label)
            resolved[control_id] = source

    default_overrides: dict[str, dict[str, Any]] = {}
    for page in form.get('pages') or []:
        for control in page.get('controls') or []:
            if 'default' not in control:
                continue
            binding = control.get('binding') or {}
            if binding.get('kind') != 'setting':
                continue
            source = resolved[str(control['control_id'])]
            default_overrides.setdefault(str(binding['target_id']), {})[
                str(binding['setting_id'])
            ] = _normalize_runtime_value(control.get('default'), str(source['value_type']))
    for target_id, overrides in default_overrides.items():
        merge_target_overrides(target_map[target_id], {target_id: overrides})
    return resolved


def canonicalize_player_fixed_options(
    form: Mapping[str, Any], values: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply author-fixed boolean choices to a detached value mapping.

    Callers must validate the form first.  Keeping this transformation in the
    binding layer makes IDE preview, saved profiles and packaged Player runs
    share the same non-bypassable semantics.
    """

    result = copy.deepcopy(dict(values or {}))
    for page in form.get('pages') or []:
        for control in page.get('controls') or []:
            fixed_options = [
                option for option in control.get('options') or []
                if isinstance(option, Mapping) and 'fixed_value' in option
            ]
            if not fixed_options:
                continue
            control_id = str(control.get('control_id') or '')
            raw_value = result.get(control_id, control.get('default'))
            value = copy.deepcopy(dict(raw_value)) if isinstance(raw_value, Mapping) else {}
            for option in fixed_options:
                value[str(option['value'])] = bool(option['fixed_value'])
            result[control_id] = value
    return result


def player_terminal_action_closure(form: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project validated publication permissions into a deterministic closure."""

    result: list[dict[str, Any]] = []
    for page in form.get('pages') or []:
        for control in page.get('controls') or []:
            control_id = str(control.get('control_id') or '')
            for action in control.get('terminal_actions') or []:
                action_id = str(action.get('action_id') or '')
                spec = PLAYER_TERMINAL_ACTION_SPECS.get(action_id)
                if not control_id or spec is None:
                    continue
                result.append({
                    'control_id': control_id,
                    'action_id': action_id,
                    'platforms': sorted({str(item) for item in action.get('platforms') or []}),
                    'capability': str(spec['capability']),
                })
    return sorted(result, key=lambda item: (str(item['control_id']), str(item['action_id'])))


def apply_player_bindings(
    ecir: dict[str, Any], form: dict[str, Any], values: dict[str, Any] | None,
    action_control_id: str = '', *,
    selected_target_id: str | None = None,
    error: Callable[[str], Exception] = ValueError,
) -> dict[str, Any]:
    """Apply validated author-published values to a detached ECIR."""

    try:
        result = copy.deepcopy(ecir)
        sources = validate_player_form_bindings(result, form)
        controls = {
            str(control.get('control_id') or ''): control
            for page in form.get('pages') or [] for control in page.get('controls') or []
            if control.get('control_id')
        }
        submitted_values = dict(values or {})
        unknown = sorted(set(submitted_values) - set(controls))
        if unknown:
            raise _fail('PLY-BIND-003', f'Player 提交了未发布控件：{unknown[0]}')
        selected_entry_id = str(result.get('entry_function_id') or '')
        if action_control_id:
            action = controls.get(str(action_control_id))
            if action is None or not sources.get(str(action_control_id), {}).get('action'):
                raise _fail('PLY-BIND-003', 'Player 请求了未发布的函数按钮')
            selected_entry_id = str((action.get('binding') or {}).get('function_id') or '')
            if selected_entry_id not in _function_map(result):
                raise _fail('PLY-BIND-004', f'Player 函数按钮绑定已失效：{selected_entry_id}')
            result['entry_function_id'] = selected_entry_id
        effective_values = {
            control_id: copy.deepcopy(control['default'])
            for control_id, control in controls.items()
            if control.get('type') != 'button' and 'default' in control
        }
        effective_values.update(submitted_values)
        effective_values = canonicalize_player_fixed_options(form, effective_values)
        for control_id, control in controls.items():
            if control.get('type') == 'button':
                continue
            binding = control.get('binding') or {}
            relevant = not (
                binding.get('kind') == 'setting'
                and selected_target_id is not None
                and str(binding.get('target_id') or '') != selected_target_id
            )
            if binding.get('kind') == 'function_parameter':
                relevant = str(binding.get('function_id') or '') == selected_entry_id
            source_required = bool(sources.get(control_id, {}).get('required'))
            if (
                relevant
                and (bool(control.get('required')) or source_required)
                and control_id not in effective_values
            ):
                raise _fail('PLY-BIND-008', f'Player 必填控件尚未填写：{control_id}')
        instructions = _collect_instructions(result)
        function_arguments: dict[str, dict[str, Any]] = copy.deepcopy(result.get('function_arguments') or {})
        variable_overrides: dict[str, Any] = copy.deepcopy(result.get('project_variable_overrides') or {})
        target_overrides: dict[str, dict[str, Any]] = copy.deepcopy(result.get('target_overrides') or {})

        for control_id, submitted in effective_values.items():
            control = controls[control_id]
            binding = control['binding']
            source = sources[control_id]
            if source.get('action'):
                raise _fail('PLY-BIND-003', f'Player 按钮 {control_id} 不能提交参数值')
            value_type = str(source['value_type'])
            value = _normalize_runtime_value(submitted, value_type)
            label = str(control.get('label') or control_id)
            _validate_value(value, value_type, dict(source['constraints']), label)
            _validate_value(value, value_type, dict(control.get('constraints') or {}), label)
            kind = str(binding['kind'])
            if kind == 'project_variable':
                variable_overrides[str(binding['variable_id'])] = copy.deepcopy(value)
            elif kind == 'function_parameter':
                function_arguments.setdefault(str(binding['function_id']), {})[
                    str(binding['parameter_id'])
                ] = copy.deepcopy(value)
            elif kind == 'statement_parameter':
                instruction = instructions[str(binding['statement_id'])]['instruction']
                parameter_id = str(binding['parameter_id'])
                nested_value_id = str(binding.get('value_id') or '')
                if nested_value_id:
                    slot = _value_override_slot_map(result).get(nested_value_id)
                    if slot is None:
                        raise _fail('PLY-BIND-010', f'嵌套值签名插槽已失效：{nested_value_id}')
                    _set_path_value(
                        instruction.setdefault('arguments', {})[parameter_id],
                        slot.get('path') or [],
                        value,
                    )
                else:
                    instruction.setdefault('arguments', {})[parameter_id] = copy.deepcopy(value)
            elif kind == 'setting':
                target_overrides.setdefault(str(binding['target_id']), {})[
                    str(binding['setting_id'])
                ] = copy.deepcopy(value)
            else:
                raise _fail('PLY-BIND-002', f'不支持的 Player 值绑定：{kind}')

        result['function_arguments'] = function_arguments
        result['project_variable_overrides'] = variable_overrides
        result['target_overrides'] = target_overrides
        return result
    except PlayerBindingError as exc:
        raise error(str(exc)) from exc


def validate_player_target_scope(
    form: Mapping[str, Any], values: Mapping[str, Any] | None,
    selected_target_id: str,
    *, error: Callable[[str], Exception] = ValueError,
) -> None:
    """Reject target-setting values that cannot affect the selected instance."""

    controls = {
        str(control.get('control_id') or ''): control
        for page in form.get('pages') or [] for control in page.get('controls') or []
        if control.get('control_id')
    }
    for control_id in (values or {}):
        binding = (controls.get(str(control_id)) or {}).get('binding') or {}
        if binding.get('kind') != 'setting':
            continue
        bound_target_id = str(binding.get('target_id') or '')
        if bound_target_id != str(selected_target_id or ''):
            exc = _fail(
                'PLY-BIND-009',
                f'Player 控件 {control_id} 属于目标 {bound_target_id}，不能用于当前目标',
            )
            raise error(str(exc)) from exc


def merge_target_overrides(
    target: dict[str, Any] | None,
    overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Merge only overrides signed for the concrete target being launched."""

    if target is None:
        return None
    merged = copy.deepcopy(target)
    target_id = str(merged.get('target_id') or '')
    scoped = copy.deepcopy(dict((overrides or {}).get(target_id) or {}))
    unknown = sorted(set(scoped) - set(TARGET_SETTING_SPECS))
    if unknown:
        raise _fail('PLY-BIND-009', f'运行设置没有真实消费者：{unknown[0]}')
    target_type = str(merged.get('type') or '')
    binding_override_present = 'target.window_binding' in scoped
    captured_override: dict[str, Any] | None = None
    for setting_id, value in scoped.items():
        spec = TARGET_SETTING_SPECS[setting_id]
        if target_type not in set(spec['target_types']):
            raise _fail('PLY-BIND-009', f'运行设置 {setting_id} 不适用于目标 {target_id}')
        canonical = _normalize_runtime_value(value, str(spec['value_type']))
        _validate_value(canonical, str(spec['value_type']), dict(spec.get('constraints') or {}), setting_id)
        if setting_id == 'target.allow_physical_fallback':
            merged['allow_physical_fallback'] = canonical
        elif setting_id == 'target.window_title':
            merged['window_title'] = canonical
            # A Player-authored title override describes a new target rule.
            # Never retain an IDE-captured HWND/PID identity behind that rule.
            merged.pop('window_binding', None)
        elif setting_id == 'target.window_binding':
            captured_override = copy.deepcopy(canonical)
        elif setting_id == 'target.device_serial':
            merged['device_serial'] = canonical
        elif setting_id == 'target.work_area.mode':
            merged.setdefault('work_area', {})['mode'] = canonical
            if canonical != 'region':
                merged.setdefault('work_area', {}).pop('region', None)
            if canonical == 'desktop':
                merged['window_title'] = ''
                merged.pop('window_binding', None)
        elif setting_id == 'target.work_area.region':
            merged.setdefault('work_area', {})['region'] = [
                int(canonical['x']), int(canonical['y']),
                int(canonical['width']), int(canonical['height']),
            ]
    if (merged.get('work_area') or {}).get('mode') == 'desktop':
        if str(scoped.get('target.window_title') or '') or captured_override is not None:
            raise _fail('PLY-BIND-009', '全屏幕模式不能同时覆盖窗口标题')
        merged['window_title'] = ''
        merged['allow_physical_fallback'] = True
    elif binding_override_present and captured_override is None:
        merged.pop('window_binding', None)
    elif captured_override is not None:
        supplied_title = scoped.get('target.window_title')
        if supplied_title is not None and str(supplied_title) != str(captured_override.get('title') or ''):
            raise _fail('PLY-BIND-009', '目标窗口标题与捕获的窗口实例不一致')
        merged['window_title'] = str(captured_override.get('title') or '')
        merged['window_match'] = 'exact'
        merged['window_binding'] = captured_override

    from .target_service import TargetConfiguration

    try:
        validated = TargetConfiguration.model_validate({
            'targets': [merged], 'default_target_id': merged.get('target_id'),
        })
    except Exception as exc:
        raise _fail('PLY-BIND-009', f'Player 运行目标覆盖无效：{exc}') from exc
    return validated.targets[0].model_dump(mode='json')


def _source_catalog_item(
    *, source_id: str, kind: str, label: str, path: list[dict[str, str]],
    binding: dict[str, str], value_type: str = '', constraints: dict[str, Any] | None = None,
    recommended_control: str = '', default: Any = ..., platforms: Iterable[str] = (),
    parameter_ui: Mapping[str, Any] | None = None, required: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        'source_id': source_id,
        'kind': kind,
        'label': label,
        'path': copy.deepcopy(path),
        'binding': copy.deepcopy(binding),
        'recommended_control': recommended_control,
        'platforms': sorted({str(platform) for platform in platforms if str(platform)}),
    }
    if kind != 'function_action':
        source_constraints = copy.deepcopy(dict(constraints or {}))
        item.update({
            'value_type': value_type,
            'type_fingerprint': player_type_fingerprint(value_type, source_constraints),
            'constraints': source_constraints,
            'required': bool(required),
            'options': copy.deepcopy(
                source_constraints.get('choices')
                if isinstance(source_constraints.get('choices'), list) else []
            ),
            'parameter_ui': copy.deepcopy(
                dict(_default_parameter_ui(value_type) if parameter_ui is None else parameter_ui)
            ),
        })
        if default is not ...:
            item['default'] = copy.deepcopy(default)
    return item


def build_player_binding_sources(
    ecir: Mapping[str, Any], *, targets: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the sole authoring catalog for schema-3 Player controls.

    The frontend receives fingerprints and stable bindings from here; it never
    hashes contracts, infers parameter IDs, or advertises unsigned slots.
    """

    detached = copy.deepcopy(dict(ecir))
    functions = _function_map(detached)
    instructions = _collect_instructions(detached)
    debug_statements = dict((detached.get('debug_map') or {}).get('statements') or {})
    target_items = [dict(item) for item in (
        targets if targets is not None else detached.get('targets') or []
    )]
    supported = list(detached.get('supported_platforms') or [])
    sources: list[dict[str, Any]] = []

    for variable in sorted(
        _project_variable_map(detached).values(),
        key=lambda item: (str(item.get('display_name') or '').casefold(), str(item.get('variable_id') or '')),
    ):
        variable_id = str(variable['variable_id'])
        value_type = str(variable.get('value_type') or '')
        constraints = dict(variable.get('constraints') or {})
        sources.append(_source_catalog_item(
            source_id=f'project_variable:{variable_id}',
            kind='project_variable',
            label=str(variable.get('display_name') or variable_id),
            path=[{'id': 'project_variables', 'label': '项目变量'}],
            binding={'kind': 'project_variable', 'variable_id': variable_id},
            value_type=value_type,
            constraints=constraints,
            recommended_control=_recommended_control(value_type),
            default=_ecir_static_to_runtime(variable.get('default_value')),
            platforms=supported,
        ))

    for function in sorted(
        functions.values(),
        key=lambda item: (str(item.get('name') or '').casefold(), str(item.get('function_id') or '')),
    ):
        function_id = str(function['function_id'])
        function_label = str(function.get('name') or function_id)
        function_path = [
            {'id': 'project_functions', 'label': '项目函数'},
            {'id': function_id, 'label': function_label},
        ]
        sources.append(_source_catalog_item(
            source_id=f'function_action:{function_id}',
            kind='function_action',
            label=f'运行 {function_label}',
            path=[*function_path, {'id': 'actions', 'label': '运行按钮'}],
            binding={'kind': 'function_action', 'function_id': function_id},
            recommended_control='button',
            platforms=supported,
        ))
        for parameter in function.get('parameter_definitions') or []:
            parameter_id = str(parameter.get('parameter_id') or '')
            if not parameter_id:
                continue
            value_type = str(parameter.get('value_type') or '')
            constraints = dict(parameter.get('constraints') or {})
            default = parameter.get('default')
            sources.append(_source_catalog_item(
                source_id=f'function_parameter:{function_id}:{parameter_id}',
                kind='function_parameter',
                label=str(parameter.get('display_name') or parameter_id),
                path=[*function_path, {'id': 'parameters', 'label': '函数参数'}],
                binding={
                    'kind': 'function_parameter',
                    'function_id': function_id,
                    'parameter_id': parameter_id,
                },
                value_type=value_type,
                constraints=constraints,
                recommended_control=_recommended_control(value_type),
                default=(
                    _ecir_static_to_runtime(default)
                    if default is not None else ...
                ),
                platforms=supported,
                required=bool(parameter.get('required', True)),
            ))

    for statement_id, record in sorted(instructions.items()):
        instruction = record['instruction']
        owner_id = str(record['owner_function_id'])
        owner = functions.get(owner_id) or {}
        owner_label = str(owner.get('name') or owner_id)
        called_id = str(instruction.get('function_id') or '')
        called_project = functions.get(called_id)
        official = None
        if called_project is None:
            try:
                official = official_function_registry_v6.require(called_id)
            except KeyError:
                continue
        called_label = (
            str(called_project.get('name') or called_id)
            if called_project is not None
            else f'{official.namespace}.{official.name}'
        )
        statement_debug = debug_statements.get(statement_id) or {}
        step_label = str(statement_debug.get('step_label') or '').strip()
        statement_label = step_label or called_label
        for parameter_id, raw_default in sorted((instruction.get('arguments') or {}).items()):
            binding = {
                'kind': 'statement_parameter',
                'function_id': owner_id,
                'statement_id': statement_id,
                'parameter_id': str(parameter_id),
            }
            try:
                source = _source_for_binding(
                    binding,
                    ecir=detached,
                    instructions=instructions,
                    functions=functions,
                    project_variables=_project_variable_map(detached),
                    targets={str(item.get('target_id') or ''): item for item in target_items},
                )
            except PlayerBindingError as exc:
                # The catalog contains only publishable author inputs.  Keep
                # the resolver strict so a forged/stale form still fails
                # validation, but do not let one dynamic or runtime-managed
                # argument make every other valid source unavailable.
                if exc.code in {'PLY-BIND-012', 'PLY-BIND-013'}:
                    continue
                raise
            project_parameter = _parameter_by_id(called_project or {}, str(parameter_id))
            official_parameter = next((
                item for item in (official.parameters if official is not None else ())
                if item.parameter_id == parameter_id
            ), None)
            if official_parameter is not None and official_parameter.ui.get('importance') == 'internal':
                continue
            parameter_label = (
                str(project_parameter.get('display_name') or parameter_id)
                if project_parameter is not None
                else str(official_parameter.display_name if official_parameter is not None else parameter_id)
            )
            declared_control = (
                '' if official_parameter is None else str(official_parameter.control or '')
            )
            sources.append(_source_catalog_item(
                source_id=f'statement_parameter:{owner_id}:{statement_id}:{parameter_id}',
                kind='statement_parameter',
                label=f'{statement_label} · {parameter_label}',
                path=[
                    {'id': 'project_functions', 'label': '项目函数'},
                    {'id': owner_id, 'label': owner_label},
                    {'id': 'statement_parameters', 'label': '语句参数'},
                    {'id': statement_id, 'label': statement_label},
                ],
                binding=binding,
                value_type=str(source['value_type']),
                constraints=dict(source['constraints']),
                recommended_control=_recommended_control(
                    str(source['value_type']), declared_control,
                ),
                default=_ecir_static_to_runtime(raw_default),
                platforms=instruction.get('platforms') or supported,
                parameter_ui=source.get('parameter_ui'),
                required=bool(source.get('required')),
            ))

    for value_id, slot in sorted(_value_override_slot_map(detached).items()):
        owner_id = str(slot['function_id'])
        statement_id = str(slot['statement_id'])
        parameter_id = str(slot['parameter_id'])
        record = instructions.get(statement_id) or {}
        instruction = record.get('instruction') or {}
        owner = functions.get(owner_id) or {}
        called_id = str(instruction.get('function_id') or '')
        called_project = functions.get(called_id)
        official = None
        if called_project is None:
            try:
                official = official_function_registry_v6.require(called_id)
            except KeyError:
                continue
        project_parameter = _parameter_by_id(called_project or {}, parameter_id)
        official_parameter = next((
            item for item in (official.parameters if official is not None else ())
            if item.parameter_id == parameter_id
        ), None)
        if official_parameter is not None and official_parameter.ui.get('importance') == 'internal':
            continue
        parameter_label = (
            str(project_parameter.get('display_name') or parameter_id)
            if project_parameter is not None
            else str(official_parameter.display_name if official_parameter is not None else parameter_id)
        )
        called_label = (
            str(called_project.get('name') or called_id)
            if called_project is not None
            else f'{official.namespace}.{official.name}'
        )
        binding = {
            'kind': 'statement_parameter',
            'function_id': owner_id,
            'statement_id': statement_id,
            'parameter_id': parameter_id,
            'value_id': value_id,
        }
        source = _source_for_binding(
            binding,
            ecir=detached,
            instructions=instructions,
            functions=functions,
            project_variables=_project_variable_map(detached),
            targets={str(item.get('target_id') or ''): item for item in target_items},
        )
        raw_root = (instruction.get('arguments') or {}).get(parameter_id)
        nested_labels = _nested_slot_labels(raw_root, slot.get('path') or [])
        label = ' · '.join((called_label, parameter_label, *nested_labels))
        sources.append(_source_catalog_item(
            source_id=(
                f'statement_parameter:{owner_id}:{statement_id}:'
                f'{parameter_id}:{value_id}'
            ),
            kind='statement_parameter',
            label=label,
            path=[
                {'id': 'project_functions', 'label': '项目函数'},
                {'id': owner_id, 'label': str(owner.get('name') or owner_id)},
                {'id': 'statement_parameters', 'label': '语句参数'},
                {'id': statement_id, 'label': called_label},
            ],
            binding=binding,
            value_type=str(source['value_type']),
            constraints={},
            recommended_control=_recommended_control(str(source['value_type'])),
            default=_ecir_static_to_runtime(
                _path_value(raw_root, slot.get('path') or [])
            ),
            platforms=instruction.get('platforms') or supported,
            parameter_ui=source.get('parameter_ui'),
        ))

    for target in sorted(
        target_items,
        key=lambda item: (str(item.get('name') or '').casefold(), str(item.get('target_id') or '')),
    ):
        target_id = str(target.get('target_id') or '')
        target_type = str(target.get('type') or '')
        if not target_id:
            continue
        for setting_id, spec in sorted(TARGET_SETTING_SPECS.items()):
            if target_type not in set(spec['target_types']):
                continue
            default: Any = ...
            if setting_id == 'target.allow_physical_fallback':
                default = target.get('allow_physical_fallback')
            elif setting_id == 'target.window_title':
                default = target.get('window_title')
            elif setting_id == 'target.window_binding':
                default = target.get('window_binding')
            elif setting_id == 'target.device_serial':
                default = target.get('device_serial')
            elif setting_id == 'target.work_area.mode':
                default = (target.get('work_area') or {}).get('mode')
            elif setting_id == 'target.work_area.region':
                region = (target.get('work_area') or {}).get('region')
                if isinstance(region, (list, tuple)) and len(region) == 4:
                    default = {
                        'x': region[0], 'y': region[1],
                        'width': region[2], 'height': region[3],
                    }
            sources.append(_source_catalog_item(
                source_id=f'setting:{target_id}:{setting_id}',
                kind='setting',
                label=str(spec['label']),
                path=[
                    {'id': 'targets', 'label': '运行目标'},
                    {'id': target_id, 'label': str(target.get('name') or target_id)},
                    {'id': 'settings', 'label': '目标设置'},
                ],
                binding={'kind': 'setting', 'target_id': target_id, 'setting_id': setting_id},
                value_type=str(spec['value_type']),
                constraints=dict(spec.get('constraints') or {}),
                recommended_control=str(spec['type']),
                default=default,
                platforms=[target_type],
                parameter_ui=spec.get('parameter_ui'),
            ))

    return {'schema_version': PLAYER_FORM_SCHEMA_VERSION, 'sources': sources}


def player_binding_contract() -> dict[str, Any]:
    """Public authoring contract used by IDE without inventing capabilities."""

    binding_fields = {
        'project_variable': ['variable_id'],
        'function_parameter': ['function_id', 'parameter_id'],
        'statement_parameter': ['function_id', 'statement_id', 'parameter_id'],
        'function_action': ['function_id'],
        'setting': ['target_id', 'setting_id'],
    }
    return {
        'schema_version': PLAYER_FORM_SCHEMA_VERSION,
        'type_fingerprint_contract': PLAYER_TYPE_FINGERPRINT_CONTRACT,
        'binding_kinds': [
            {
                'kind': kind,
                'required_fields': binding_fields[kind],
                **(
                    {'optional_fields': ['value_id']}
                    if kind == 'statement_parameter' else {}
                ),
            }
            for kind in sorted(PLAYER_BINDING_KINDS)
        ],
        'unsupported': [
            {
                'kind': 'resource',
                'error_code': 'PLY-BIND-011',
                'reason': 'compiler_resource_override_slot_missing',
            },
            {
                'kind': 'target',
                'error_code': 'PLY-BIND-011',
                'reason': 'compiler_target_override_slot_missing',
            },
        ],
        'target_settings': [
            {
                'setting_id': setting_id,
                **copy.deepcopy(spec),
                'type_fingerprint': player_type_fingerprint(
                    str(spec['value_type']), dict(spec.get('constraints') or {}),
                ),
            }
            for setting_id, spec in sorted(TARGET_SETTING_SPECS.items())
        ],
    }


__all__ = [
    'PLAYER_BINDING_KINDS', 'PLAYER_FORM_SCHEMA_VERSION',
    'PLAYER_TERMINAL_ACTION_SPECS', 'PLAYER_TYPE_FINGERPRINT_CONTRACT', 'TARGET_SETTING_SPECS',
    'UNSUPPORTED_PLAYER_BINDING_KINDS', 'PlayerBindingError',
    'apply_player_bindings', 'build_player_binding_sources', 'canonicalize_player_fixed_options',
    'merge_target_overrides', 'player_terminal_action_closure',
    'player_binding_contract', 'player_type_fingerprint',
    'validate_player_form_bindings', 'validate_player_target_scope',
]
