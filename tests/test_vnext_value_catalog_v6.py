from __future__ import annotations

from core.vnext.program_types import (
    AssignmentStatement,
    BoolValue,
    ComparisonValue,
    IfStatement,
    IntValue,
    LocalAssignmentTarget,
    NullValue,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    RecordValue,
    ReturnStatement,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.program_validation import validate_program_document
from core.vnext.program_value_scope_v6 import AvailableValueSourceV6, available_value_sources
from core.vnext.pure_operations_v6 import EXECUTABLE_PURE_OPERATIONS, pure_operation_type_issues
from core.vnext.value_catalog_v6 import (
    EXPRESSION_NAMESPACES,
    PURE_OPERATION_PRESENTATIONS,
    pure_value_catalog_payload,
    resolve_member_candidates,
    resolve_operation_candidates,
)


def _parameter_document() -> ProgramDocument:
    condition = ComparisonValue(
        value_id='value_has_match',
        operator='ne',
        left=SymbolReferenceValue(
            value_id='value_match_condition',
            symbol_id='symbol_match',
            value_type='optional<image_match>',
        ),
        right=NullValue(value_id='value_null'),
    )
    return ProgramDocument(
        document_id='document_value_scope',
        function=ProgramFunction(
            function_id='function_value_scope',
            display_name='目录作用域',
            parameters=(ProgramParameter(
                parameter_id='parameter_match',
                symbol_id='symbol_match',
                display_name='匹配结果',
                value_type='optional<image_match>',
            ),),
            statements=(
                IfStatement(
                    statement_id='statement_guard',
                    condition=condition,
                    then_statements=(ReturnStatement(statement_id='statement_inside'),),
                ),
                ReturnStatement(statement_id='statement_outside'),
            ),
        ),
    )


def test_operation_catalog_only_returns_concrete_executable_signatures() -> None:
    candidates = resolve_operation_candidates(
        'optional<string>',
        ('list<string>', 'map<string,string>', 'optional<string>'),
    )
    operations = {item.operation_id: item for item in candidates}

    assert {'core.list_first.v1', 'core.list_last.v1', 'core.list_get.v1', 'core.map_get.v1'} <= set(operations)
    assert 'core.map_entries.v1' not in operations  # no closed key/value-entry record yet
    assert set(PURE_OPERATION_PRESENTATIONS) == set(EXECUTABLE_PURE_OPERATIONS)
    for candidate in candidates:
        input_types = {input_id: value_type for input_id, _, value_type, _ in candidate.inputs}
        assert not pure_operation_type_issues(candidate.operation_id, candidate.result_type, input_types)
        assert all(value_type not in {'T', 'K', 'V', 'any'} for value_type in input_types.values())
    assert resolve_operation_candidates(
        'optional<string>',
        ('list<string>', 'map<string,string>', 'optional<string>'),
    ) == candidates


def test_discovery_catalog_covers_every_operation_namespace_and_trigger() -> None:
    payload = pure_value_catalog_payload('string', ('string', 'int64', 'list<string>'))
    discovery = payload['discovery']

    assert payload['schema_version'] == 2
    assert [item['name'] for item in discovery['namespaces']] == [item[0] for item in EXPRESSION_NAMESPACES]
    assert len({item['name'] for item in discovery['namespaces']}) == 12
    assert {item['operation_id'] for item in discovery['operations']} == set(EXECUTABLE_PURE_OPERATIONS)
    assert all(
        item['keywords'] and item['example'] and item['group'] and item['result_type_hints']
        for item in discovery['operations']
    )
    assert any(item['compatible'] for item in discovery['operations'])
    assert any(not item['compatible'] and item['disabled_reason'] for item in discovery['operations'])
    by_id = {item['operation_id']: item for item in discovery['operations']}
    assert by_id['core.duration_from_minutes.v1']['group'] == '转换与格式'
    assert by_id['core.list_min.v1']['group'] == '判断与统计'
    assert {item['keys'] for item in discovery['triggers']} == {'Ctrl+Space', '@', '.', '('}
    assert discovery['literals'][0]['label'] == '普通文字'


def test_discovery_literals_and_operators_follow_the_expected_type() -> None:
    boolean = pure_value_catalog_payload('bool')['discovery']
    assert [item['insert_text'] for item in boolean['literals']] == ['开启', '关闭']
    assert {' 且 ', ' 或 ', '非 '} <= {item['insert_text'] for item in boolean['operators']}

    optional = pure_value_catalog_payload('optional<int64>')['discovery']
    assert optional['literals'][0]['insert_text'] == '无结果'
    assert any(item['insert_text'] == '0' for item in optional['literals'])


def test_conversion_text_and_geometry_catalogs_only_offer_compatible_inputs() -> None:
    text_candidates = resolve_operation_candidates(
        'string',
        ('bool', 'int64', 'enum<log_level>', 'ref<asset>', 'list<string>'),
    )
    to_text_types = {
        next(value_type for input_id, _, value_type, _ in item.inputs if input_id.endswith('.input.value'))
        for item in text_candidates
        if item.operation_id == 'core.value_to_text.v1'
    }
    assert to_text_types == {'bool', 'enum<log_level>', 'int64'}
    assert any(item.operation_id == 'core.text_join.v1' for item in text_candidates)

    assert any(
        item.operation_id == 'core.text_split.v1'
        for item in resolve_operation_candidates('list<string>', ('string',))
    )
    assert any(
        item.operation_id == 'core.point_scale.v1'
        for item in resolve_operation_candidates('point', ('point', 'float64'))
    )
    assert any(
        item.operation_id == 'core.rect_scale.v1'
        for item in resolve_operation_candidates('rect', ('rect', 'float64'))
    )


def test_value_catalog_projects_record_fields_and_enum_choices_from_backend_registry() -> None:
    payload = pure_value_catalog_payload('http_body')

    assert payload['record']['type_id'] == 'http_body'
    assert payload['record']['authoring_mode'] == 'constructible'
    assert payload['record']['editor_strategy'] == 'inline_record'
    fields = {item['field_id']: item for item in payload['record']['fields']}
    assert fields['http_body.field.text']['value_type'] == 'optional<string>'
    assert fields['http_body.field.kind']['choices'] == [
        {'label': '文本', 'value': 'text'},
        {'label': 'JSON', 'value': 'json'},
    ]

    window = pure_value_catalog_payload('window_selector')
    window_fields = {item['field_id']: item for item in window['record']['fields']}
    assert window_fields['window_selector.field.match_mode']['choices'] == [
        {'label': '包含', 'value': 'contains'},
        {'label': '完全等于', 'value': 'exact'},
        {'label': '正则表达式', 'value': 'regex'},
    ]


def test_value_catalog_serializes_ocr_inline_defaults_constraints_and_visibility() -> None:
    record = pure_value_catalog_payload('optional<ocr_preprocess>')['record']

    assert record['authoring_mode'] == 'constructible'
    assert record['editor_strategy'] == 'inline_record'
    fields = {item['field_id']: item for item in record['fields']}
    assert fields['ocr_preprocess.field.binary']['default'] is False
    threshold = fields['ocr_preprocess.field.threshold']
    assert threshold['required'] is False
    assert threshold['has_default'] is True
    assert threshold['default'] == 127
    assert threshold['constraints'] == {'minimum': 0, 'maximum': 255}
    assert threshold['ui']['control'] == 'slider-number'
    assert threshold['ui']['visible_when'] == {
        'field_id': 'ocr_preprocess.field.binary',
        'operator': 'equals',
        'value': True,
    }

    pair_record = pure_value_catalog_payload('list<http_pair>')['record']
    assert pair_record['type_id'] == 'http_pair'
    assert pair_record['editor_strategy'] == 'inline_record'


def test_member_catalog_supports_strict_optional_access_and_uses_stable_field_ids() -> None:
    direct = AvailableValueSourceV6(
        source='local', source_id='symbol_direct', display_name='直接结果', value_type='image_match',
    )
    optional = AvailableValueSourceV6(
        source='local', source_id='symbol_optional', display_name='可选结果', value_type='optional<image_match>',
    )
    narrowed = AvailableValueSourceV6(
        source='local', source_id='symbol_optional', display_name='可选结果',
        value_type='optional<image_match>', narrowed_type='image_match',
    )

    optional_candidates = resolve_member_candidates('point', (optional,))
    direct_candidates = resolve_member_candidates('point', (direct,))
    narrowed_candidates = resolve_member_candidates('point', (narrowed,))
    assert [item.path[-1][0] for item in optional_candidates] == ['image_match.field.center']
    assert [item.path[-1][0] for item in direct_candidates] == ['image_match.field.center']
    assert [item.path[-1][0] for item in narrowed_candidates] == ['image_match.field.center']
    assert optional_candidates[0].source_value_type == 'optional<image_match>'
    assert narrowed_candidates[0].source_value_type == 'optional<image_match>'
    assert narrowed_candidates[0].candidate_id == resolve_member_candidates('point', (narrowed,))[0].candidate_id


def test_text_catalog_offers_only_printable_record_fields() -> None:
    narrowed = AvailableValueSourceV6(
        source='local', source_id='symbol_optional', display_name='图片测试',
        value_type='optional<image_match>', narrowed_type='image_match',
    )

    candidates = resolve_member_candidates('string', (narrowed,))
    fields = {item.path[-1][0]: item.result_type for item in candidates}

    assert fields['image_match.field.similarity'] == 'percentage'
    assert fields['image_match.field.space_version'] == 'string'
    assert fields['frame_ref.field.captured_at'] == 'datetime'
    assert 'image_match.field.center' not in fields
    assert 'image_match.field.region' not in fields
    assert 'image_match.field.source_frame' not in fields


def test_member_catalog_projects_through_nested_optional_result_without_a_guard() -> None:
    result = AvailableValueSourceV6(
        source='local',
        source_id='symbol_click_result',
        display_name='巨人游赏坐标',
        value_type='image_click_condition_result',
    )

    candidates = resolve_member_candidates('point', (result,))
    paths = [tuple(part[0] for part in item.path) for item in candidates]

    assert (
        'image_click_condition_result.field.last_match',
        'image_match.field.center',
    ) in paths


def test_statement_scope_only_marks_optional_value_inside_proven_true_branch() -> None:
    document = _parameter_document()

    inside = {item.source_id: item for item in available_value_sources(document, 'statement_inside')}
    outside = {item.source_id: item for item in available_value_sources(document, 'statement_outside')}

    assert inside['symbol_match'].value_type == 'optional<image_match>'
    assert inside['symbol_match'].narrowed_type == 'image_match'
    assert outside['symbol_match'].narrowed_type == ''
    assert resolve_member_candidates('point', inside.values())
    assert resolve_member_candidates('point', outside.values())


def test_record_validation_rejects_unknown_wrong_and_missing_required_fields() -> None:
    invalid = RecordValue(
        value_id='value_http_pair',
        record_type='record<http_pair>',
        fields={
            'http_pair.field.name': IntValue(value_id='value_wrong_name', value=1),
            'http_pair.field.unknown': StringValue(value_id='value_unknown', value='x'),
        },
    )
    document = ProgramDocument(
        document_id='document_invalid_record',
        function=ProgramFunction(
            function_id='function_invalid_record',
            display_name='错误记录',
            statements=(AssignmentStatement(
                statement_id='statement_invalid_record',
                target=LocalAssignmentTarget(
                    symbol_id='symbol_pair', display_name='请求头', value_type='record<http_pair>',
                ),
                value=invalid,
            ),),
        ),
    )

    diagnostics = validate_program_document(document)
    codes = [item.code for item in diagnostics]
    assert 'PGM-RECORD-001' in codes
    assert 'PGM-RECORD-002' in codes
    assert codes.count('PGM-RECORD-003') == 2
    assert all(item.statement_id == 'statement_invalid_record' for item in diagnostics)


def test_record_validation_accepts_complete_typed_record() -> None:
    valid = RecordValue(
        value_id='value_http_pair',
        record_type='http_pair',
        fields={
            'http_pair.field.name': StringValue(value_id='value_name', value='Authorization'),
            'http_pair.field.value': StringValue(value_id='value_value', value='secret'),
            'http_pair.field.sensitive': BoolValue(value_id='value_sensitive', value=True),
        },
    )
    document = ProgramDocument(
        document_id='document_valid_record',
        function=ProgramFunction(
            function_id='function_valid_record',
            display_name='正确记录',
            statements=(AssignmentStatement(
                statement_id='statement_valid_record',
                target=LocalAssignmentTarget(
                    symbol_id='symbol_pair', display_name='请求头', value_type='http_pair',
                ),
                value=valid,
            ),),
        ),
    )

    assert validate_program_document(document) == ()


def test_window_selector_rejects_empty_and_negative_literals_before_runtime() -> None:
    empty_selector = RecordValue(
        value_id='value_window_selector',
        record_type='window_selector',
        fields={
            'window_selector.field.title': StringValue(value_id='value_title', value='  '),
        },
    )
    negative_selector = RecordValue(
        value_id='value_negative_window_selector',
        record_type='window_selector',
        fields={
            'window_selector.field.process_id': IntValue(value_id='value_pid', value=-1),
            'window_selector.field.index': IntValue(value_id='value_index', value=-2),
        },
    )
    document = ProgramDocument(
        document_id='document_invalid_window_selector',
        function=ProgramFunction(
            function_id='function_invalid_window_selector',
            display_name='错误窗口选择器',
            statements=(
                AssignmentStatement(
                    statement_id='statement_empty_window_selector',
                    target=LocalAssignmentTarget(
                        symbol_id='symbol_empty_selector', display_name='空窗口选择器', value_type='window_selector',
                    ),
                    value=empty_selector,
                ),
                AssignmentStatement(
                    statement_id='statement_negative_window_selector',
                    target=LocalAssignmentTarget(
                        symbol_id='symbol_negative_selector', display_name='负数窗口选择器', value_type='window_selector',
                    ),
                    value=negative_selector,
                ),
            ),
        ),
    )

    codes = [item.code for item in validate_program_document(document)]
    assert 'PGM-RECORD-004' in codes
    assert codes.count('PGM-RECORD-005') == 2
