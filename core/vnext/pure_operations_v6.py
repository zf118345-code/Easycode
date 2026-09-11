"""Frozen execution availability for format-6 pure value operations.

This registry is deliberately independent from presentation names.  A value
tree may save an approved-but-unavailable operation, but Compiler Service must
produce a stable diagnostic instead of emitting ECIR that fails late.
"""

from __future__ import annotations

import hashlib
import json

# Bump whenever an operation's stable slots, type contract, empty-result rule,
# evaluation order, or runtime meaning changes.  Presentation labels do not
# participate in this version; they are a separate UI projection.
PURE_OPERATION_REGISTRY_VERSION = 10

EXECUTABLE_PURE_OPERATIONS = frozenset({
    'core.number_add.v1', 'core.number_subtract.v1', 'core.number_multiply.v1',
    'core.number_divide.v1', 'core.number_modulo.v1', 'core.number_min.v1',
    'core.number_max.v1', 'core.number_clamp.v1', 'core.number_round.v1',
    'core.number_to_int.v1', 'core.number_to_float.v1',
    'core.value_to_text.v1', 'core.text_to_int.v1', 'core.text_to_float.v1',
    'core.text_concat.v1', 'core.text_replace.v1', 'core.text_slice.v1',
    'core.text_lower.v1', 'core.text_upper.v1', 'core.text_trim.v1',
    'core.text_length.v1', 'core.text_matches.v1', 'core.text_split.v1',
    'core.text_join.v1',
    'core.text_regex_extract.v1', 'core.text_regex_groups.v1',
    'core.text_extract_first_int.v1', 'core.text_parse_datetime.v1',
    'core.datetime_add_duration.v1', 'core.datetime_subtract_duration.v1',
    'core.datetime_difference.v1', 'core.datetime_format.v1',
    'core.date_add_days.v1', 'core.date_difference.v1',
    'core.time_add_duration.v1',
    'core.duration_from_milliseconds.v1', 'core.duration_from_seconds.v1',
    'core.duration_from_minutes.v1', 'core.duration_poll_count.v1',
    'core.optional_has_value.v1',
    'core.optional_default.v1', 'core.select.v1',
    'core.point_offset.v1', 'core.point_scale.v1',
    'core.rect_center.v1', 'core.rect_scale.v1', 'core.rect_from_center.v1',
    'core.color_matches.v1',
    'core.list_is_empty.v1', 'core.list_length.v1', 'core.list_contains.v1',
    'core.list_first.v1', 'core.list_last.v1', 'core.list_get.v1',
    'core.list_append.v1', 'core.list_prepend.v1', 'core.list_insert.v1',
    'core.list_replace.v1', 'core.list_remove_at.v1', 'core.list_clear.v1',
    'core.list_reverse.v1', 'core.list_slice.v1', 'core.list_concat.v1',
    'core.list_distinct.v1', 'core.list_sum.v1', 'core.list_average.v1',
    'core.list_min.v1', 'core.list_max.v1',
    'core.list_filter.v1', 'core.list_map.v1', 'core.list_sort_by.v1',
    'core.list_group_by.v1', 'core.list_flatten.v1', 'core.list_zip.v1',
    'core.list_find_first.v1', 'core.list_any.v1', 'core.list_all.v1',
    'core.list_count_match.v1', 'core.list_index_by.v1',
    'core.map_has_key.v1', 'core.map_get.v1', 'core.map_set.v1',
    'core.map_delete.v1', 'core.map_clear.v1', 'core.map_keys.v1',
    'core.map_values.v1', 'core.map_entries.v1', 'core.map_merge.v1',
    'core.map_filter.v1', 'core.map_map_values.v1', 'core.map_group_by.v1',
    'core.json_parse_text.v1', 'core.json_path_exists.v1',
    'core.json_path_get.v1', 'core.json_path_set.v1', 'core.json_path_delete.v1',
    'core.json_validate_schema.v1',
    'core.file_ref_child.v1',
})

OPERATION_INPUT_NAMES: dict[str, tuple[str, ...]] = {}


def _inputs(names: tuple[str, ...], *operation_ids: str) -> None:
    for operation_id in operation_ids:
        OPERATION_INPUT_NAMES[operation_id] = names


_inputs(('left', 'right'),
        'core.number_add.v1', 'core.number_subtract.v1', 'core.number_multiply.v1',
        'core.number_divide.v1', 'core.number_modulo.v1', 'core.number_min.v1',
        'core.number_max.v1', 'core.text_concat.v1')
_inputs(('value',),
        'core.number_to_int.v1', 'core.number_to_float.v1',
        'core.optional_has_value.v1', 'core.value_to_text.v1')
_inputs(('text',), 'core.text_to_int.v1', 'core.text_to_float.v1')
_inputs(('text',),
        'core.text_lower.v1', 'core.text_upper.v1', 'core.text_trim.v1',
        'core.text_length.v1')
_inputs(('actual', 'expected', 'mode'), 'core.text_matches.v1')
_inputs(('timeout', 'interval'), 'core.duration_poll_count.v1')
_inputs(('amount',),
        'core.duration_from_milliseconds.v1', 'core.duration_from_seconds.v1',
        'core.duration_from_minutes.v1')
_inputs(('value', 'minimum', 'maximum'), 'core.number_clamp.v1')
_inputs(('value', 'digits'), 'core.number_round.v1')
_inputs(('text', 'search', 'replacement'), 'core.text_replace.v1')
_inputs(('text', 'start', 'end'), 'core.text_slice.v1')
_inputs(('text', 'separator'), 'core.text_split.v1')
_inputs(('list', 'separator'), 'core.text_join.v1')
_inputs(('text', 'pattern', 'group'), 'core.text_regex_extract.v1')
_inputs(('text', 'pattern'), 'core.text_regex_groups.v1')
_inputs(('text',), 'core.text_extract_first_int.v1')
_inputs(('text', 'pattern'), 'core.text_parse_datetime.v1')
_inputs(('datetime', 'duration'),
        'core.datetime_add_duration.v1', 'core.datetime_subtract_duration.v1')
_inputs(('later', 'earlier'), 'core.datetime_difference.v1')
_inputs(('datetime', 'pattern'), 'core.datetime_format.v1')
_inputs(('date', 'days'), 'core.date_add_days.v1')
_inputs(('later', 'earlier'), 'core.date_difference.v1')
_inputs(('time', 'duration'), 'core.time_add_duration.v1')
_inputs(('value', 'default'), 'core.optional_default.v1')
_inputs(('condition', 'when_true', 'when_false'), 'core.select.v1')
_inputs(('point', 'offset'), 'core.point_offset.v1')
_inputs(('point', 'scale_x', 'scale_y'), 'core.point_scale.v1')
_inputs(('rect',), 'core.rect_center.v1')
_inputs(('rect', 'scale_x', 'scale_y'), 'core.rect_scale.v1')
_inputs(('center', 'width', 'height'), 'core.rect_from_center.v1')
_inputs(('actual', 'expected', 'tolerance'), 'core.color_matches.v1')
_inputs(('list',),
        'core.list_is_empty.v1', 'core.list_length.v1', 'core.list_first.v1',
        'core.list_last.v1', 'core.list_clear.v1', 'core.list_reverse.v1',
        'core.list_distinct.v1', 'core.list_sum.v1', 'core.list_average.v1',
        'core.list_min.v1', 'core.list_max.v1')
_inputs(('list', 'value'),
        'core.list_contains.v1', 'core.list_append.v1', 'core.list_prepend.v1')
_inputs(('list', 'index'), 'core.list_get.v1', 'core.list_remove_at.v1')
_inputs(('list', 'index', 'value'), 'core.list_insert.v1', 'core.list_replace.v1')
_inputs(('list', 'start', 'end'), 'core.list_slice.v1')
_inputs(('list', 'other'), 'core.list_concat.v1')
_inputs(('list', 'predicate'), 'core.list_filter.v1', 'core.list_find_first.v1',
        'core.list_any.v1', 'core.list_all.v1', 'core.list_count_match.v1')
_inputs(('list', 'transform'), 'core.list_map.v1')
_inputs(('list', 'key_selector', 'descending'), 'core.list_sort_by.v1')
_inputs(('list', 'key_selector'), 'core.list_group_by.v1', 'core.list_index_by.v1')
_inputs(('list',), 'core.list_flatten.v1')
_inputs(('list', 'other'), 'core.list_zip.v1')
_inputs(('map',),
        'core.map_clear.v1', 'core.map_keys.v1', 'core.map_values.v1',
        'core.map_entries.v1')
_inputs(('map', 'key'), 'core.map_has_key.v1', 'core.map_get.v1', 'core.map_delete.v1')
_inputs(('map', 'key', 'value'), 'core.map_set.v1')
_inputs(('map', 'other', 'conflict'), 'core.map_merge.v1')
_inputs(('map', 'predicate'), 'core.map_filter.v1')
_inputs(('map', 'transform'), 'core.map_map_values.v1')
_inputs(('map', 'key_selector'), 'core.map_group_by.v1')
_inputs(('text',), 'core.json_parse_text.v1')
_inputs(('json', 'path'), 'core.json_path_exists.v1', 'core.json_path_get.v1',
        'core.json_path_delete.v1')
_inputs(('json', 'path', 'value'), 'core.json_path_set.v1')
_inputs(('json', 'schema'), 'core.json_validate_schema.v1')
_inputs(('directory', 'relative_path'), 'core.file_ref_child.v1')

# Approved semantics that are intentionally not executable belong here.  A
# stable planned ID produces a compile diagnostic instead of a late no-op.
# The set is empty after the selector and file-reference vertical slices were
# closed, but remains part of the registry contract for future review gates.
PLANNED_PURE_OPERATIONS = frozenset()


def pure_operation_state(operation_id: str) -> str:
    if operation_id in EXECUTABLE_PURE_OPERATIONS:
        return 'verified'
    if operation_id in PLANNED_PURE_OPERATIONS:
        return 'planned'
    return 'unknown'


def pure_operation_registry_payload() -> dict[str, object]:
    """Return the deterministic execution identity of the core registry.

    The version is deliberately explicit: Python implementation details and
    localized labels are not a portable lock contract.  Stable operation IDs,
    stable input-slot IDs, implementation state, and the manually reviewed
    semantics version are.  The canonical hash is embedded in ECIR/lock data
    by their owning services so registry drift cannot be mistaken for an
    unchanged program.
    """

    return {
        'registry_version': PURE_OPERATION_REGISTRY_VERSION,
        'operations': [
            {
                'operation_id': operation_id,
                'state': pure_operation_state(operation_id),
                'input_ids': [
                    f'{operation_id}.input.{name}'
                    for name in OPERATION_INPUT_NAMES.get(operation_id, ())
                ],
            }
            for operation_id in sorted(EXECUTABLE_PURE_OPERATIONS | PLANNED_PURE_OPERATIONS)
        ],
    }


def pure_operation_registry_hash() -> str:
    canonical = json.dumps(
        pure_operation_registry_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def pure_operation_type_issues(
    operation_id: str,
    result_type: str,
    input_types: dict[str, str],
) -> tuple[str, ...]:
    """Return stable type-contract violations for an executable operation.

    The previous implementation mostly checked that an input was "some list"
    or "some number".  That allowed a document to claim that division returned
    an integer, that ``list<T>`` operations returned an unrelated type, or that
    a map key/value belonged to a different map.  The runtime would then either
    fail late or place a value in a slot whose declared type was false.  This
    function is the canonical operation signature check until the public
    operation catalog is projected from the same metadata.
    """

    issues: list[str] = []

    def actual(name: str) -> str:
        return input_types.get(f'{operation_id}.input.{name}', '<missing>')

    def require(name: str, predicate, expected: str) -> None:
        current = actual(name)
        if current != '<missing>' and not predicate(current):
            issues.append(f'{name} 需要 {expected}，当前为 {current}')

    def require_result(expected: str) -> None:
        if result_type != expected:
            issues.append(f'结果需要 {expected}，当前为 {result_type}')

    def numeric(value: str) -> bool:
        return value in {'int64', 'float64'}

    def numeric_result(*names: str) -> str | None:
        values = [actual(name) for name in names]
        if any(value == '<missing>' for value in values) or not all(numeric(value) for value in values):
            return None
        return 'float64' if 'float64' in values else 'int64'

    def generic(type_id: str, prefix: str) -> tuple[str, ...] | None:
        marker = f'{prefix}<'
        if not type_id.startswith(marker) or not type_id.endswith('>'):
            return None
        inner = type_id[len(marker):-1]
        parts: list[str] = []
        depth = 0
        start = 0
        for index, character in enumerate(inner):
            if character == '<':
                depth += 1
            elif character == '>':
                depth -= 1
            elif character == ',' and depth == 0:
                parts.append(inner[start:index].strip())
                start = index + 1
        parts.append(inner[start:].strip())
        return tuple(parts) if all(parts) else None

    def compatible(current: str, expected: str) -> bool:
        if current == expected:
            return True
        if expected == 'float64' and current == 'int64':
            return True
        return expected.startswith('enum<') and current == 'string'

    def stable_key(value: str) -> bool:
        return value in {'string', 'int64'} or value.startswith(('enum<', 'ref<'))

    def sortable(value: str) -> bool:
        return value in {
            'string', 'int64', 'float64', 'percentage', 'duration',
            'date', 'datetime', 'time', 'time_of_day',
        } or value.startswith(('enum<', 'ref<'))

    numeric_same_result = {
        'core.number_add.v1', 'core.number_subtract.v1',
        'core.number_multiply.v1', 'core.number_modulo.v1',
        'core.number_min.v1', 'core.number_max.v1',
    }
    if operation_id in numeric_same_result:
        require('left', numeric, 'int64/float64')
        require('right', numeric, 'int64/float64')
        expected = numeric_result('left', 'right')
        if expected is not None:
            require_result(expected)
    elif operation_id == 'core.number_divide.v1':
        require('left', numeric, 'int64/float64')
        require('right', numeric, 'int64/float64')
        require_result('float64')
    elif operation_id == 'core.number_clamp.v1':
        for name in ('value', 'minimum', 'maximum'):
            require(name, numeric, 'int64/float64')
        expected = numeric_result('value', 'minimum', 'maximum')
        if expected is not None:
            require_result(expected)
    elif operation_id == 'core.number_round.v1':
        require('value', numeric, 'int64/float64')
        require('digits', lambda value: value == 'int64', 'int64')
        if numeric(actual('value')):
            require_result(actual('value'))
    elif operation_id == 'core.number_to_int.v1':
        require('value', numeric, 'int64/float64')
        require_result('int64')
    elif operation_id == 'core.number_to_float.v1':
        require('value', numeric, 'int64/float64')
        require_result('float64')

    if operation_id == 'core.value_to_text.v1':
        require(
            'value',
            lambda value: value in {
                'string', 'int64', 'float64', 'percentage', 'bool',
                'date', 'datetime', 'time', 'time_of_day', 'duration',
            } or value.startswith('enum<'),
            '基础标量值',
        )
        require_result('string')
    elif operation_id == 'core.text_to_int.v1':
        require('text', lambda value: value == 'string', 'string')
        require_result('optional<int64>')
    elif operation_id == 'core.text_to_float.v1':
        require('text', lambda value: value == 'string', 'string')
        require_result('optional<float64>')

    temporal_signatures = {
        'core.datetime_add_duration.v1': ('datetime', {'datetime': 'datetime', 'duration': 'duration'}),
        'core.datetime_subtract_duration.v1': ('datetime', {'datetime': 'datetime', 'duration': 'duration'}),
        'core.datetime_difference.v1': ('duration', {'later': 'datetime', 'earlier': 'datetime'}),
        'core.datetime_format.v1': ('string', {'datetime': 'datetime', 'pattern': 'string'}),
        'core.date_add_days.v1': ('date', {'date': 'date', 'days': 'int64'}),
        'core.date_difference.v1': ('int64', {'later': 'date', 'earlier': 'date'}),
        'core.time_add_duration.v1': ('time', {'time': 'time', 'duration': 'duration'}),
    }
    if operation_id in {
        'core.duration_from_milliseconds.v1', 'core.duration_from_seconds.v1',
        'core.duration_from_minutes.v1',
    }:
        require('amount', numeric, 'int64/float64')
        require_result('duration')
    if operation_id in temporal_signatures:
        expected_result, expected_inputs = temporal_signatures[operation_id]
        for name, expected in expected_inputs.items():
            require(name, lambda value, expected=expected: value == expected, expected)
        require_result(expected_result)

    if operation_id.startswith('core.text_') and operation_id != 'core.text_matches.v1':
        if operation_id == 'core.text_join.v1':
            require('list', lambda value: value == 'list<string>', 'list<string>')
            require('separator', lambda value: value == 'string', 'string')
            require_result('string')
        elif operation_id == 'core.text_split.v1':
            require('text', lambda value: value == 'string', 'string')
            require('separator', lambda value: value == 'string', 'string')
            require_result('list<string>')
        elif operation_id == 'core.text_regex_extract.v1':
            require('text', lambda value: value == 'string', 'string')
            require('pattern', lambda value: value == 'string', 'string')
            require('group', lambda value: value == 'int64', 'int64')
            require_result('optional<string>')
        elif operation_id == 'core.text_regex_groups.v1':
            require('text', lambda value: value == 'string', 'string')
            require('pattern', lambda value: value == 'string', 'string')
            require_result('list<string>')
        elif operation_id == 'core.text_extract_first_int.v1':
            require('text', lambda value: value == 'string', 'string')
            require_result('optional<int64>')
        elif operation_id == 'core.text_parse_datetime.v1':
            require('text', lambda value: value == 'string', 'string')
            require('pattern', lambda value: value == 'string', 'string')
            require_result('optional<datetime>')
        elif operation_id not in {'core.text_to_int.v1', 'core.text_to_float.v1'}:
            for name in OPERATION_INPUT_NAMES[operation_id]:
                expected = 'int64' if name in {'start', 'end'} else 'string'
                require(name, lambda value, expected=expected: value == expected, expected)
            require_result('int64' if operation_id == 'core.text_length.v1' else 'string')

    if operation_id == 'core.text_matches.v1':
        require('actual', lambda value: value == 'string', 'string')
        require('expected', lambda value: value == 'string', 'string')
        require('mode', lambda value: value in {'string', 'enum<text_match_mode>'}, 'enum<text_match_mode>')
        require_result('bool')
    elif operation_id == 'core.duration_poll_count.v1':
        require('timeout', lambda value: value == 'duration', 'duration')
        require('interval', lambda value: value == 'duration', 'duration')
        require_result('int64')

    if operation_id == 'core.optional_has_value.v1':
        require('value', lambda value: generic(value, 'optional') is not None, 'optional<T>')
        require_result('bool')
    elif operation_id == 'core.optional_default.v1':
        optional = generic(actual('value'), 'optional')
        if actual('value') != '<missing>' and optional is None:
            issues.append(f'value 需要 optional<T>，当前为 {actual("value")}')
        if optional is not None:
            expected = optional[0]
            if actual('default') != '<missing>' and not compatible(actual('default'), expected):
                issues.append(f'default 需要 {expected}，当前为 {actual("default")}')
            require_result(expected)
    elif operation_id == 'core.select.v1':
        require('condition', lambda value: value == 'bool', 'bool')
        left, right = actual('when_true'), actual('when_false')
        if '<missing>' not in {left, right}:
            expected = (
                'float64' if {left, right} <= {'int64', 'float64'} and 'float64' in {left, right}
                else left if left == right else ''
            )
            if not expected:
                issues.append('when_true 与 when_false 类型必须可归一')
            else:
                require_result(expected)
    elif operation_id == 'core.point_offset.v1':
        require('point', lambda value: value == 'point', 'point')
        require('offset', lambda value: value == 'point', 'point')
        require_result('point')
    elif operation_id == 'core.point_scale.v1':
        require('point', lambda value: value == 'point', 'point')
        require('scale_x', numeric, 'int64/float64')
        require('scale_y', numeric, 'int64/float64')
        require_result('point')
    elif operation_id == 'core.rect_center.v1':
        require('rect', lambda value: value == 'rect', 'rect')
        require_result('point')
    elif operation_id == 'core.rect_scale.v1':
        require('rect', lambda value: value == 'rect', 'rect')
        require('scale_x', numeric, 'int64/float64')
        require('scale_y', numeric, 'int64/float64')
        require_result('rect')
    elif operation_id == 'core.rect_from_center.v1':
        require('center', lambda value: value == 'point', 'point')
        require('width', numeric, 'int64/float64')
        require('height', numeric, 'int64/float64')
        require_result('rect')
    elif operation_id == 'core.color_matches.v1':
        require('actual', lambda value: value == 'color', 'color')
        require('expected', lambda value: value == 'color', 'color')
        require('tolerance', lambda value: value == 'int64', 'int64')
        require_result('bool')

    if operation_id.startswith('core.list_'):
        list_parts = generic(actual('list'), 'list')
        if actual('list') != '<missing>' and (list_parts is None or len(list_parts) != 1):
            issues.append(f'list 需要 list<T>，当前为 {actual("list")}')
        item_type = list_parts[0] if list_parts and len(list_parts) == 1 else ''
        for name in ('index', 'start', 'end'):
            if name in OPERATION_INPUT_NAMES[operation_id]:
                require(name, lambda value: value == 'int64', 'int64')
        if item_type and 'value' in OPERATION_INPUT_NAMES[operation_id]:
            require('value', lambda value: compatible(value, item_type), item_type)
        if item_type and 'other' in OPERATION_INPUT_NAMES[operation_id] and operation_id != 'core.list_zip.v1':
            require('other', lambda value: value == f'list<{item_type}>', f'list<{item_type}>')

        selector_parts = None
        selector_name = next((name for name in ('predicate', 'transform', 'key_selector') if name in OPERATION_INPUT_NAMES[operation_id]), '')
        if selector_name:
            selector_parts = generic(actual(selector_name), 'list_selector')
            if actual(selector_name) != '<missing>' and (selector_parts is None or len(selector_parts) != 2):
                issues.append(f'{selector_name} 需要当前项/序号选择器，当前为 {actual(selector_name)}')
            elif selector_parts and item_type:
                if selector_parts[0] != item_type:
                    issues.append(f'{selector_name} 的当前项需要 {item_type}')

        fixed_results = {
            'core.list_is_empty.v1': 'bool',
            'core.list_length.v1': 'int64',
            'core.list_contains.v1': 'bool',
        }
        if operation_id in fixed_results:
            require_result(fixed_results[operation_id])
        elif item_type and operation_id in {
            'core.list_first.v1', 'core.list_last.v1', 'core.list_get.v1',
            'core.list_min.v1', 'core.list_max.v1',
        }:
            require_result(f'optional<{item_type}>')
        elif item_type and operation_id == 'core.list_sum.v1':
            if not numeric(item_type):
                issues.append(f'list 需要数值列表，当前项类型为 {item_type}')
            else:
                require_result(item_type)
        elif item_type and operation_id == 'core.list_average.v1':
            if not numeric(item_type):
                issues.append(f'list 需要数值列表，当前项类型为 {item_type}')
            require_result('optional<float64>')
        elif item_type and operation_id == 'core.list_filter.v1':
            if selector_parts and selector_parts[1] != 'bool':
                issues.append(f'predicate 结果需要 bool，当前为 {selector_parts[1]}')
            require_result(f'list<{item_type}>')
        elif item_type and operation_id == 'core.list_map.v1':
            if selector_parts:
                require_result(f'list<{selector_parts[1]}>')
        elif item_type and operation_id == 'core.list_sort_by.v1':
            if selector_parts and not sortable(selector_parts[1]):
                issues.append(f'key_selector 结果不可排序：{selector_parts[1]}')
            require('descending', lambda value: value == 'bool', 'bool')
            require_result(f'list<{item_type}>')
        elif item_type and operation_id == 'core.list_group_by.v1':
            if selector_parts:
                key_type = selector_parts[1]
                if not stable_key(key_type):
                    issues.append(f'key_selector 结果不能作为字典键：{key_type}')
                require_result(f'map<{key_type},list<{item_type}>>')
        elif operation_id == 'core.list_flatten.v1' and list_parts:
            nested = generic(list_parts[0], 'list')
            if nested is None or len(nested) != 1:
                issues.append(f'list 需要 list<list<T>>，当前为 {actual("list")}')
            else:
                require_result(f'list<{nested[0]}>')
        elif item_type and operation_id == 'core.list_zip.v1':
            other_parts = generic(actual('other'), 'list')
            if other_parts is None or len(other_parts) != 1:
                issues.append(f'other 需要 list<T>，当前为 {actual("other")}')
            else:
                require_result(f'list<record<zip_pair<{item_type},{other_parts[0]}>>>')
        elif item_type and operation_id == 'core.list_find_first.v1':
            if selector_parts and selector_parts[1] != 'bool':
                issues.append(f'predicate 结果需要 bool，当前为 {selector_parts[1]}')
            require_result(f'optional<{item_type}>')
        elif item_type and operation_id in {'core.list_any.v1', 'core.list_all.v1'}:
            if selector_parts and selector_parts[1] != 'bool':
                issues.append(f'predicate 结果需要 bool，当前为 {selector_parts[1]}')
            require_result('bool')
        elif item_type and operation_id == 'core.list_count_match.v1':
            if selector_parts and selector_parts[1] != 'bool':
                issues.append(f'predicate 结果需要 bool，当前为 {selector_parts[1]}')
            require_result('int64')
        elif item_type and operation_id == 'core.list_index_by.v1':
            if selector_parts:
                key_type = selector_parts[1]
                if not stable_key(key_type):
                    issues.append(f'key_selector 结果不能作为字典键：{key_type}')
                require_result(f'map<{key_type},{item_type}>')
        elif item_type:
            require_result(f'list<{item_type}>')

    if operation_id.startswith('core.map_'):
        map_parts = generic(actual('map'), 'map')
        if actual('map') != '<missing>' and (map_parts is None or len(map_parts) != 2):
            issues.append(f'map 需要 map<K,V>，当前为 {actual("map")}')
        key_type, value_type = map_parts if map_parts and len(map_parts) == 2 else ('', '')
        if key_type and 'key' in OPERATION_INPUT_NAMES[operation_id]:
            require('key', lambda value: compatible(value, key_type), key_type)
        if value_type and 'value' in OPERATION_INPUT_NAMES[operation_id]:
            require('value', lambda value: compatible(value, value_type), value_type)
        if key_type and value_type and 'other' in OPERATION_INPUT_NAMES[operation_id]:
            require('other', lambda value: value == actual('map'), actual('map'))
        if 'conflict' in OPERATION_INPUT_NAMES[operation_id]:
            require('conflict', lambda value: value in {'string', 'enum<map_conflict>'}, 'enum<map_conflict>')

        selector_parts = None
        selector_name = next((name for name in ('predicate', 'transform', 'key_selector') if name in OPERATION_INPUT_NAMES[operation_id]), '')
        if selector_name:
            selector_parts = generic(actual(selector_name), 'map_selector')
            if actual(selector_name) != '<missing>' and (selector_parts is None or len(selector_parts) != 3):
                issues.append(f'{selector_name} 需要当前键/当前值选择器，当前为 {actual(selector_name)}')
            elif selector_parts and (selector_parts[0], selector_parts[1]) != (key_type, value_type):
                issues.append(f'{selector_name} 的当前键/当前值需要 {key_type}/{value_type}')

        if operation_id == 'core.map_has_key.v1':
            require_result('bool')
        elif key_type and value_type and operation_id == 'core.map_get.v1':
            require_result(f'optional<{value_type}>')
        elif key_type and value_type and operation_id == 'core.map_keys.v1':
            require_result(f'list<{key_type}>')
        elif key_type and value_type and operation_id == 'core.map_values.v1':
            require_result(f'list<{value_type}>')
        elif key_type and value_type and operation_id == 'core.map_entries.v1':
            require_result(f'list<record<map_entry<{key_type},{value_type}>>>')
        elif key_type and value_type and operation_id == 'core.map_filter.v1':
            if selector_parts and selector_parts[2] != 'bool':
                issues.append(f'predicate 结果需要 bool，当前为 {selector_parts[2]}')
            require_result(actual('map'))
        elif key_type and value_type and operation_id == 'core.map_map_values.v1':
            if selector_parts:
                require_result(f'map<{key_type},{selector_parts[2]}>')
        elif key_type and value_type and operation_id == 'core.map_group_by.v1':
            if selector_parts:
                group_type = selector_parts[2]
                if not stable_key(group_type):
                    issues.append(f'key_selector 结果不能作为字典键：{group_type}')
                require_result(
                    f'map<{group_type},list<record<map_entry<{key_type},{value_type}>>>>'
                )
        elif key_type and value_type:
            require_result(actual('map'))

    if operation_id.startswith('core.json_') and operation_id not in {
        'core.json_parse_text.v1', 'core.json_validate_schema.v1',
    }:
        require('json', lambda value: value == 'json_value', 'json_value')
        # ProgramDocument lists are homogeneous.  A path made entirely from
        # object keys or entirely from array indexes therefore remains a
        # normal typed list; ``json_path_segment`` is reserved for a future
        # mixed-segment record projection.  ``json_value`` is accepted for an
        # already parsed external path representation.
        require(
            'path',
            lambda value: value in {
                'list<string>', 'list<int64>', 'list<json_path_segment>', 'json_value',
            },
            'list<string>/list<int64>/list<json_path_segment>',
        )
        if operation_id == 'core.json_path_set.v1':
            require('value', lambda value: value == 'json_value', 'json_value')
        if operation_id == 'core.json_path_exists.v1':
            require_result('bool')
        else:
            require_result('optional<json_value>')
    if operation_id == 'core.json_parse_text.v1':
        require('text', lambda value: value == 'string', 'string')
        require_result('optional<json_value>')
    elif operation_id == 'core.json_validate_schema.v1':
        require('json', lambda value: value == 'json_value', 'json_value')
        require('schema', lambda value: value == 'json_value', 'json_value')
        if result_type in {'any', 'unit', 'unset', 'null'} or result_type.startswith(('list_selector<', 'map_selector<')):
            issues.append(f'结果类型不能用于 JSON Schema 转换：{result_type}')

    if operation_id == 'core.file_ref_child.v1':
        allowed_directories = {
            'file_ref<read>': {'directory_ref<read>', 'directory_ref<read_write>'},
            'file_ref<write>': {'directory_ref<create>', 'directory_ref<read_write>'},
        }
        expected_directories = allowed_directories.get(result_type)
        if expected_directories is None:
            issues.append(f'结果只支持 file_ref<read>/file_ref<write>，当前为 {result_type}')
        else:
            require(
                'directory',
                lambda value: value in expected_directories,
                '/'.join(sorted(expected_directories)),
            )
        require(
            'relative_path',
            lambda value: value in {'string', 'relative_path'},
            'relative_path',
        )

    return tuple(dict.fromkeys(issues))


__all__ = [
    'EXECUTABLE_PURE_OPERATIONS',
    'PLANNED_PURE_OPERATIONS',
    'OPERATION_INPUT_NAMES',
    'PURE_OPERATION_REGISTRY_VERSION',
    'pure_operation_registry_hash',
    'pure_operation_registry_payload',
    'pure_operation_state',
    'pure_operation_type_issues',
]
