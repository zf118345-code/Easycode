from __future__ import annotations

import pytest

from core.vnext.pure_operations_v6 import (
    EXECUTABLE_PURE_OPERATIONS,
    OPERATION_INPUT_NAMES,
    pure_operation_registry_hash,
    pure_operation_registry_payload,
    pure_operation_type_issues,
)


def _types(operation_id: str, **inputs: str) -> dict[str, str]:
    return {
        f'{operation_id}.input.{name}': value_type
        for name, value_type in inputs.items()
    }


def _issues(operation_id: str, result_type: str, **inputs: str) -> tuple[str, ...]:
    return pure_operation_type_issues(operation_id, result_type, _types(operation_id, **inputs))


def test_every_executable_operation_publishes_exact_input_names() -> None:
    assert set(OPERATION_INPUT_NAMES) == set(EXECUTABLE_PURE_OPERATIONS)
    assert all(names for names in OPERATION_INPUT_NAMES.values())


def test_registry_identity_is_canonical_and_covers_planned_boundaries() -> None:
    payload = pure_operation_registry_payload()
    operation_ids = [item['operation_id'] for item in payload['operations']]
    assert operation_ids == sorted(operation_ids)
    assert payload['registry_version'] >= 2
    assert 'core.number_add.v1' in operation_ids
    assert 'core.list_filter.v1' in operation_ids
    assert len(pure_operation_registry_hash()) == 64
    assert pure_operation_registry_hash() == pure_operation_registry_hash()


@pytest.mark.parametrize(
    ('operation_id', 'result_type', 'inputs'),
    [
        ('core.number_add.v1', 'int64', {'left': 'int64', 'right': 'int64'}),
        ('core.number_add.v1', 'float64', {'left': 'int64', 'right': 'float64'}),
        ('core.number_divide.v1', 'float64', {'left': 'int64', 'right': 'int64'}),
        ('core.number_clamp.v1', 'float64', {
            'value': 'float64', 'minimum': 'int64', 'maximum': 'int64',
        }),
        ('core.value_to_text.v1', 'string', {'value': 'bool'}),
        ('core.text_to_int.v1', 'optional<int64>', {'text': 'string'}),
        ('core.text_to_float.v1', 'optional<float64>', {'text': 'string'}),
        ('core.text_split.v1', 'list<string>', {
            'text': 'string', 'separator': 'string',
        }),
        ('core.text_join.v1', 'string', {
            'list': 'list<string>', 'separator': 'string',
        }),
        ('core.point_scale.v1', 'point', {
            'point': 'point', 'scale_x': 'float64', 'scale_y': 'int64',
        }),
        ('core.rect_scale.v1', 'rect', {
            'rect': 'rect', 'scale_x': 'int64', 'scale_y': 'float64',
        }),
        ('core.rect_from_center.v1', 'rect', {
            'center': 'point', 'width': 'int64', 'height': 'float64',
        }),
        ('core.color_matches.v1', 'bool', {
            'actual': 'color', 'expected': 'color', 'tolerance': 'int64',
        }),
        ('core.optional_default.v1', 'string', {
            'value': 'optional<string>', 'default': 'string',
        }),
        ('core.select.v1', 'float64', {
            'condition': 'bool', 'when_true': 'int64', 'when_false': 'float64',
        }),
        ('core.list_first.v1', 'optional<string>', {'list': 'list<string>'}),
        ('core.list_average.v1', 'optional<float64>', {'list': 'list<int64>'}),
        ('core.list_append.v1', 'list<string>', {
            'list': 'list<string>', 'value': 'string',
        }),
        ('core.map_get.v1', 'optional<int64>', {
            'map': 'map<string,int64>', 'key': 'string',
        }),
        ('core.map_set.v1', 'map<string,int64>', {
            'map': 'map<string,int64>', 'key': 'string', 'value': 'int64',
        }),
        ('core.json_path_get.v1', 'optional<json_value>', {
            'json': 'json_value', 'path': 'list<string>',
        }),
        ('core.file_ref_child.v1', 'file_ref<write>', {
            'directory': 'directory_ref<read_write>', 'relative_path': 'relative_path',
        }),
    ],
)
def test_valid_operation_signatures_have_no_type_issues(
    operation_id: str,
    result_type: str,
    inputs: dict[str, str],
) -> None:
    assert _issues(operation_id, result_type, **inputs) == ()


@pytest.mark.parametrize(
    ('operation_id', 'result_type', 'inputs'),
    [
        ('core.number_divide.v1', 'int64', {'left': 'int64', 'right': 'int64'}),
        ('core.value_to_text.v1', 'string', {'value': 'ref<asset>'}),
        ('core.text_to_int.v1', 'int64', {'text': 'string'}),
        ('core.text_join.v1', 'string', {
            'list': 'list<int64>', 'separator': 'string',
        }),
        ('core.point_scale.v1', 'point', {
            'point': 'rect', 'scale_x': 'float64', 'scale_y': 'float64',
        }),
        ('core.color_matches.v1', 'bool', {
            'actual': 'string', 'expected': 'color', 'tolerance': 'int64',
        }),
        ('core.list_average.v1', 'optional<float64>', {'list': 'list<string>'}),
        ('core.list_first.v1', 'optional<int64>', {'list': 'list<string>'}),
        ('core.list_append.v1', 'list<string>', {
            'list': 'list<string>', 'value': 'int64',
        }),
        ('core.map_get.v1', 'optional<int64>', {
            'map': 'map<string,int64>', 'key': 'int64',
        }),
        ('core.map_set.v1', 'map<string,string>', {
            'map': 'map<string,int64>', 'key': 'string', 'value': 'int64',
        }),
        ('core.optional_default.v1', 'string', {
            'value': 'optional<int64>', 'default': 'string',
        }),
        ('core.json_path_get.v1', 'optional<int64>', {
            'json': 'json_value', 'path': 'list<string>',
        }),
        ('core.file_ref_child.v1', 'file_ref<write>', {
            'directory': 'directory_ref<read>', 'relative_path': 'relative_path',
        }),
    ],
)
def test_invalid_operation_signatures_are_rejected_before_runtime(
    operation_id: str,
    result_type: str,
    inputs: dict[str, str],
) -> None:
    assert _issues(operation_id, result_type, **inputs)
