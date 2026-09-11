"""Portable pure JSON-Schema profile without remote references or I/O."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any


class JsonSchemaDefinitionError(ValueError):
    pass


@dataclass(frozen=True)
class JsonSchemaValueError(ValueError):
    path: tuple[str | int, ...]
    detail: str

    def __str__(self) -> str:
        return self.detail


_ANNOTATIONS = {'$schema', '$id', 'title', 'description', 'default', 'examples'}
_KEYWORDS = _ANNOTATIONS | {
    'type', 'enum', 'const', 'allOf', 'anyOf', 'oneOf', 'not',
    'properties', 'required', 'additionalProperties', 'minProperties', 'maxProperties',
    'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength', 'maxLength', 'pattern',
    'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf',
}
_TYPES = {'null', 'boolean', 'integer', 'number', 'string', 'array', 'object'}


def _definition(schema: Any, path: tuple[str | int, ...] = (), depth: int = 0) -> None:
    if depth > 64:
        raise JsonSchemaDefinitionError('Schema 嵌套超过 64 层')
    if isinstance(schema, bool):
        return
    if not isinstance(schema, dict):
        raise JsonSchemaDefinitionError(f'Schema {path or ("<root>",)} 必须是对象或布尔值')
    unknown = sorted(set(schema) - _KEYWORDS)
    if unknown:
        raise JsonSchemaDefinitionError(f'不支持的 Schema 关键字：{unknown[0]}')
    declared = schema.get('type')
    if declared is not None:
        values = [declared] if isinstance(declared, str) else declared
        if not isinstance(values, list) or not values or any(item not in _TYPES for item in values):
            raise JsonSchemaDefinitionError('type 必须是受支持类型或非空类型列表')
    for name in ('allOf', 'anyOf', 'oneOf'):
        branches = schema.get(name)
        if branches is not None:
            if not isinstance(branches, list) or not branches:
                raise JsonSchemaDefinitionError(f'{name} 必须是非空 Schema 列表')
            for index, child in enumerate(branches):
                _definition(child, (*path, name, index), depth + 1)
    if 'not' in schema:
        _definition(schema['not'], (*path, 'not'), depth + 1)
    properties = schema.get('properties')
    if properties is not None:
        if not isinstance(properties, dict) or any(not isinstance(key, str) for key in properties):
            raise JsonSchemaDefinitionError('properties 必须是以文本命名的 Schema 对象')
        for key, child in properties.items():
            _definition(child, (*path, 'properties', key), depth + 1)
    required = schema.get('required')
    if required is not None and (
        not isinstance(required, list) or any(not isinstance(item, str) for item in required)
        or len(set(required)) != len(required)
    ):
        raise JsonSchemaDefinitionError('required 必须是不重复的文本列表')
    additional = schema.get('additionalProperties')
    if additional is not None and not isinstance(additional, bool):
        _definition(additional, (*path, 'additionalProperties'), depth + 1)
    if 'items' in schema:
        _definition(schema['items'], (*path, 'items'), depth + 1)
    for name in ('minProperties', 'maxProperties', 'minItems', 'maxItems', 'minLength', 'maxLength'):
        value = schema.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise JsonSchemaDefinitionError(f'{name} 必须是非负整数')
    pattern = schema.get('pattern')
    if pattern is not None:
        if not isinstance(pattern, str):
            raise JsonSchemaDefinitionError('pattern 必须是文本')
        try:
            re.compile(pattern)
        except re.error as exc:
            raise JsonSchemaDefinitionError(f'pattern 无效：{exc}') from exc
    for name in ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf'):
        value = schema.get(name)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        ):
            raise JsonSchemaDefinitionError(f'{name} 必须是有限数值')
    if schema.get('multipleOf') is not None and schema['multipleOf'] <= 0:
        raise JsonSchemaDefinitionError('multipleOf 必须大于零')
    if 'enum' in schema and (not isinstance(schema['enum'], list) or not schema['enum']):
        raise JsonSchemaDefinitionError('enum 必须是非空列表')


def _json_equal(left: Any, right: Any) -> bool:
    options = {'ensure_ascii': False, 'sort_keys': True, 'separators': (',', ':')}
    return json.dumps(left, **options) == json.dumps(right, **options)


def _matches_type(value: Any, type_name: str) -> bool:
    if type_name == 'null':
        return value is None
    if type_name == 'boolean':
        return isinstance(value, bool)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'array':
        return isinstance(value, list)
    return isinstance(value, dict)


def _validate(value: Any, schema: Any, path: tuple[str | int, ...], depth: int = 0) -> None:
    if depth > 64:
        raise JsonSchemaValueError(path, '数据嵌套超过 64 层')
    if schema is True:
        return
    if schema is False:
        raise JsonSchemaValueError(path, '该位置不允许任何值')
    declared = schema.get('type')
    if declared is not None:
        types = [declared] if isinstance(declared, str) else declared
        if not any(_matches_type(value, item) for item in types):
            raise JsonSchemaValueError(path, f'需要类型 {"/".join(types)}')
    if 'const' in schema and not _json_equal(value, schema['const']):
        raise JsonSchemaValueError(path, '值不等于规定常量')
    if 'enum' in schema and not any(_json_equal(value, item) for item in schema['enum']):
        raise JsonSchemaValueError(path, '值不在允许范围内')
    for child in schema.get('allOf') or []:
        _validate(value, child, path, depth + 1)
    for name in ('anyOf', 'oneOf'):
        if name not in schema:
            continue
        branches = schema[name]
        matched = 0
        for child in branches:
            try:
                _validate(value, child, path, depth + 1)
                matched += 1
            except JsonSchemaValueError:
                pass
        if name == 'anyOf' and matched == 0:
            raise JsonSchemaValueError(path, '值不满足任一允许结构')
        if name == 'oneOf' and matched != 1:
            raise JsonSchemaValueError(path, '值必须且只能满足一个允许结构')
    if 'not' in schema:
        try:
            _validate(value, schema['not'], path, depth + 1)
        except JsonSchemaValueError:
            pass
        else:
            raise JsonSchemaValueError(path, '值命中了禁止结构')
    if isinstance(value, dict):
        minimum, maximum = schema.get('minProperties'), schema.get('maxProperties')
        if minimum is not None and len(value) < minimum:
            raise JsonSchemaValueError(path, f'对象至少需要 {minimum} 个字段')
        if maximum is not None and len(value) > maximum:
            raise JsonSchemaValueError(path, f'对象最多允许 {maximum} 个字段')
        for required in schema.get('required') or []:
            if required not in value:
                raise JsonSchemaValueError((*path, required), '缺少必填字段')
        properties = schema.get('properties') or {}
        additional = schema.get('additionalProperties', True)
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], (*path, key), depth + 1)
            elif additional is False:
                raise JsonSchemaValueError((*path, key), '不允许额外字段')
            elif isinstance(additional, dict):
                _validate(item, additional, (*path, key), depth + 1)
    if isinstance(value, list):
        minimum, maximum = schema.get('minItems'), schema.get('maxItems')
        if minimum is not None and len(value) < minimum:
            raise JsonSchemaValueError(path, f'列表至少需要 {minimum} 项')
        if maximum is not None and len(value) > maximum:
            raise JsonSchemaValueError(path, f'列表最多允许 {maximum} 项')
        if schema.get('uniqueItems'):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':')) for item in value]
            if len(set(encoded)) != len(encoded):
                raise JsonSchemaValueError(path, '列表项必须互不重复')
        if 'items' in schema:
            for index, item in enumerate(value):
                _validate(item, schema['items'], (*path, index), depth + 1)
    if isinstance(value, str):
        minimum, maximum = schema.get('minLength'), schema.get('maxLength')
        if minimum is not None and len(value) < minimum:
            raise JsonSchemaValueError(path, f'文本长度不能少于 {minimum}')
        if maximum is not None and len(value) > maximum:
            raise JsonSchemaValueError(path, f'文本长度不能超过 {maximum}')
        if schema.get('pattern') is not None and re.search(schema['pattern'], value) is None:
            raise JsonSchemaValueError(path, '文本不符合格式规则')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        checks = (
            ('minimum', lambda threshold: value < threshold, '不能小于'),
            ('maximum', lambda threshold: value > threshold, '不能大于'),
            ('exclusiveMinimum', lambda threshold: value <= threshold, '必须大于'),
            ('exclusiveMaximum', lambda threshold: value >= threshold, '必须小于'),
        )
        for name, failed, label in checks:
            if schema.get(name) is not None and failed(schema[name]):
                raise JsonSchemaValueError(path, f'数值{label} {schema[name]}')
        multiple = schema.get('multipleOf')
        if multiple is not None and not math.isclose(value / multiple, round(value / multiple), rel_tol=1e-9, abs_tol=1e-9):
            raise JsonSchemaValueError(path, f'数值必须是 {multiple} 的倍数')


def validate_json_schema(value: Any, schema: Any) -> None:
    _definition(schema)
    _validate(value, schema, ())


__all__ = ['JsonSchemaDefinitionError', 'JsonSchemaValueError', 'validate_json_schema']
