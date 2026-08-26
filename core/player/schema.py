"""Player 表单 Schema v3：规范化、默认值生成与运行前校验。"""

from __future__ import annotations

import copy
import re
from typing import Any


SCHEMA_VERSION = 3
SUPPORTED_UI_TYPES = {'str', 'secret', 'number', 'slider', 'switch', 'select', 'checkbox_group', 'image_asset'}
def _normalize_option(option: Any) -> dict[str, Any]:
    if isinstance(option, dict):
        value = option.get('value', option.get('label', ''))
        return {'label': str(option.get('label', value)), 'value': value}
    return {'label': str(option), 'value': option}


def normalize_form_schema(schema: Any) -> dict[str, Any]:
    """规范化当前版表单；不接受旧字段名或旧控件类型。"""
    source = copy.deepcopy(schema) if isinstance(schema, dict) else {}
    version = source.get('schema_version')
    if version not in (None, SCHEMA_VERSION):
        raise ValueError(f'Player 表单版本不受支持: {version}（当前版本 {SCHEMA_VERSION}）')
    result: dict[str, Any] = {
        **source,
        'schema_version': SCHEMA_VERSION,
        'form_title': str(source.get('form_title') or '客户运行配置面板'),
        'groups': [],
    }

    groups = source.get('groups') if isinstance(source.get('groups'), list) else []
    for group_index, raw_group in enumerate(groups):
        if not isinstance(raw_group, dict):
            continue
        group = {
            **raw_group,
            'group_title': str(raw_group.get('group_title') or f'配置分组 {group_index + 1}'),
            'fields': [],
        }
        fields = raw_group.get('fields') if isinstance(raw_group.get('fields'), list) else []
        for raw_field in fields:
            if not isinstance(raw_field, dict):
                continue
            field = copy.deepcopy(raw_field)
            target = str(field.get('target') or '').strip()
            field['target'] = target

            ui_type = str(field.get('ui_type') or 'str')
            if ui_type not in SUPPORTED_UI_TYPES:
                raise ValueError(f'不支持的 Player 控件类型: {ui_type}')
            field['ui_type'] = ui_type
            field['label'] = str(field.get('label') or (target[5:] if len(target) > 5 else '未命名参数'))
            field['provider'] = str(field.get('provider') or '')
            field['required'] = bool(field.get('required', False))
            field['options'] = [_normalize_option(option) for option in (field.get('options') or [])]

            if 'default' not in field:
                if field['ui_type'] == 'switch':
                    field['default'] = False
                elif field['ui_type'] in {'number', 'slider'}:
                    field['default'] = 0
                elif field['ui_type'] == 'checkbox_group':
                    field['default'] = []
                else:
                    field['default'] = ''
            if field['ui_type'] == 'checkbox_group' and not isinstance(field['default'], list):
                field['default'] = [field['default']] if field['default'] not in (None, '') else []
            group['fields'].append(field)
        result['groups'].append(group)
    return result


def normalize_user_config(config: Any) -> dict[str, dict[str, Any]]:
    """统一客户配置槽位；运行属性绑定集中存放在 overrides。"""
    source = config if isinstance(config, dict) else {}
    return {
        'vars': dict(source.get('vars') or {}),
        'ctx': dict(source.get('ctx') or {}),
        'overrides': dict(source.get('overrides') or {}),
    }


def split_target(target: str) -> tuple[str, str] | tuple[None, None]:
    if target.startswith('$var.') and len(target) > 5:
        return 'vars', target[5:]
    if target.startswith('$ctx.') and len(target) > 5:
        return 'ctx', target[5:]
    if (target.startswith('$settings.') and len(target) > 10) or (target.startswith('$node.') and len(target) > 6):
        return 'overrides', target
    return None, None


def build_user_config(schema: Any, current: Any = None) -> dict[str, dict[str, Any]]:
    normalized_schema = normalize_form_schema(schema)
    config = normalize_user_config(current)
    for group in normalized_schema['groups']:
        for field in group['fields']:
            slot, key = split_target(field['target'])
            if slot and key not in config[slot]:
                config[slot][key] = copy.deepcopy(field.get('default'))
    return config


def _field_visible(field: dict[str, Any], config: dict[str, Any]) -> bool:
    rule = field.get('visible_if')
    if not isinstance(rule, dict):
        return True
    target = str(rule.get('target') or rule.get('field') or '')
    if target and not target.startswith('$'):
        target = f'$var.{target}'
    slot, key = split_target(target)
    current = config.get(slot, {}).get(key) if slot else None
    expected = rule.get('value')
    operator = rule.get('operator', 'eq')
    if operator == 'ne':
        return current != expected
    if operator == 'contains':
        return isinstance(current, (list, str)) and expected in current
    if operator == 'in':
        return isinstance(expected, (list, tuple, set)) and current in expected
    return current == expected


def validate_user_config(schema: Any, config: Any) -> list[dict[str, str]]:
    """返回字段级错误；空列表表示配置可安全启动。"""
    normalized_schema = normalize_form_schema(schema)
    normalized_config = build_user_config(normalized_schema, config)
    errors: list[dict[str, str]] = []
    for group in normalized_schema['groups']:
        for field in group['fields']:
            if not _field_visible(field, normalized_config):
                continue
            target = field['target']
            slot, key = split_target(target)
            if not slot:
                errors.append({'target': target, 'message': '字段目标不是受支持的运行时绑定'})
                continue
            value = normalized_config[slot].get(key)
            label = field['label']
            if field.get('required') and (value is None or value == '' or value == []):
                errors.append({'target': target, 'message': f'{label} 为必填项'})
                continue
            if value in (None, ''):
                continue
            if field['ui_type'] in {'number', 'slider'}:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append({'target': target, 'message': f'{label} 必须是数字'})
                    continue
                if field.get('min') is not None and value < field['min']:
                    errors.append({'target': target, 'message': f'{label} 不能小于 {field["min"]}'})
                if field.get('max') is not None and value > field['max']:
                    errors.append({'target': target, 'message': f'{label} 不能大于 {field["max"]}'})
            pattern = field.get('pattern')
            if pattern and isinstance(value, str):
                try:
                    if not re.fullmatch(str(pattern), value):
                        errors.append({'target': target, 'message': f'{label} 格式不正确'})
                except re.error:
                    errors.append({'target': target, 'message': f'{label} 的校验表达式无效'})
            if field['ui_type'] == 'image_asset' and value:
                text = str(value)
                if not text.startswith('asset://') and not text.startswith('data:image/'):
                    errors.append({'target': target, 'message': f'{label} 必须是项目图片或 Player 截图'})
    return errors
