from __future__ import annotations

import re
from datetime import time
from pathlib import Path

import pytest

from core.vnext.function_contracts_v6 import (
    _parameter_placeholder,
    official_function_registry_v6,
)
from core.vnext.record_types_v6 import record_type_contract
from core.vnext.program_commands import ProgramCommandError, insert_call, update_call_argument
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import (
    adapt_program_ecir_for_runtime,
    assert_available_runtime_contracts_are_bound,
)
from core.vnext.program_types import PathValue, PointLiteral, PointValue, StringValue, TimeValue, create_program_document, new_stable_id
from core.vnext.runtime import RuntimeFailure


def test_approved_function_catalog_and_runtime_registry_have_exact_stable_id_parity() -> None:
    """Prevent the approved public catalog and implementation from drifting again."""

    catalog_text = Path('docs/vnext/FUNCTIONS.md').read_text(encoding='utf-8')
    approved = {
        qualified_name: function_id
        for qualified_name, function_id in re.findall(
            r'^\| `([^`]+\.[^`]+)` \| `(official\.[^`]+)` \|',
            catalog_text,
            flags=re.MULTILINE,
        )
    }
    implemented = {
        item['qualified_name']: item['function_id']
        for item in official_function_registry_v6.complete_catalog()
    }

    assert len(approved) == 85
    assert implemented == approved


def test_complete_v1_contract_catalog_is_stable_unique_and_scope_correct() -> None:
    catalog = official_function_registry_v6.complete_catalog()

    assert len(catalog) >= 60
    assert len({item['function_id'] for item in catalog}) == len(catalog)
    assert len({item['qualified_name'] for item in catalog}) == len(catalog)
    assert len({item['contract_fingerprint'] for item in catalog}) == len(catalog)
    assert not any(item['namespace'] == '页面' for item in catalog)
    assert not any(item['namespace'] in {'存储', '租约'} for item in catalog)
    assert not any(item['qualified_name'] in {'图像.存在', '控件.存在', '输入.长按'} for item in catalog)


def test_runtime_image_samples_are_typed_reference_only_and_discoverable() -> None:
    sample = record_type_contract('image_sample')
    comparison = record_type_contract('image_comparison')
    crop = official_function_registry_v6.require('official.frame.crop_region')
    compare = official_function_registry_v6.require('official.image.compare')

    assert sample is not None and sample.authoring_mode == 'reference_only'
    assert comparison is not None and comparison.authoring_mode == 'reference_only'
    assert crop.return_type == 'image_sample'
    assert compare.return_type == 'image_comparison'
    size_strategy = next(
        item for item in compare.parameters
        if item.parameter_id == 'official.image.compare.parameter.size_strategy'
    )
    assert size_strategy.default == 'strict'


def test_statement_summaries_are_typed_and_reference_only_declared_parameters() -> None:
    catalog = official_function_registry_v6.complete_catalog()

    for function in catalog:
        summary = function['statement_summary']
        assert summary['schema_version'] == 1
        parameter_ids = {parameter['parameter_id'] for parameter in function['parameters']}
        for part in summary['parts']:
            assert part['kind'] in {'text', 'parameter'}
            if part['kind'] == 'parameter':
                assert part['parameter_id'] in parameter_ids
                assert part['presentation'] == 'auto'

    image_wait = next(item for item in catalog if item['function_id'] == 'official.image.wait_visible')
    assert [part['kind'] for part in image_wait['statement_summary']['parts']] == ['text', 'parameter', 'text']
    assert image_wait['statement_summary']['parts'][1]['parameter_id'] == 'official.image.wait_visible.parameter.image'


def test_every_parameterized_action_exposes_its_required_semantic_object() -> None:
    """Future official functions cannot silently fall back to an opaque verb-only row."""

    for function in official_function_registry_v6.complete_catalog():
        required_parameters = {
            parameter['name']
            for parameter in function['parameters']
            if parameter['required'] and not parameter['has_default']
        }
        if not required_parameters:
            continue
        summary_parameters = {
            part['parameter_name']
            for part in function['statement_summary']['parts']
            if part['kind'] == 'parameter'
        }
        assert summary_parameters & required_parameters, (
            f"{function['function_id']} 有必填语义对象，但中央摘要只显示函数名"
        )

    expected_slots = {
        'official.frame.save': {'file'},
        'official.window.move': {'window', 'position'},
        'official.file.replace_text': {'file'},
        'official.directory.copy': {'source', 'destination_parent'},
        'official.network.request': {'method', 'url'},
        'official.network.download_file': {'url', 'destination'},
        'official.message.send': {'recipients', 'name'},
    }
    catalog = {item['function_id']: item for item in official_function_registry_v6.complete_catalog()}
    for function_id, required_slots in expected_slots.items():
        actual_slots = {
            part['parameter_name']
            for part in catalog[function_id]['statement_summary']['parts']
            if part['kind'] == 'parameter'
        }
        assert required_slots <= actual_slots


def test_every_official_parameter_and_result_type_is_composable() -> None:
    """A visible function must not publish an opaque structure the editor cannot build or inspect."""

    atomic_types = {
        'unit', 'bool', 'int64', 'float64', 'string', 'date', 'time', 'datetime',
        'duration', 'percentage', 'json_value', 'point', 'rect', 'size', 'url',
        'relative_path', 'timezone', 'any', 'message_value', 'gesture_path', 'key_chord',
        'instance_ref', 'target_ref', 'window_ref', 'control_ref', 'application_ref', 'frame_ref',
        'asset_ref', 'file_ref', 'directory_ref',
    }

    def generic_parts(value_type: str) -> tuple[str, tuple[str, ...]] | None:
        if '<' not in value_type or not value_type.endswith('>'):
            return None
        outer, tail = value_type.split('<', 1)
        inner = tail[:-1]
        depth = 0
        start = 0
        parts: list[str] = []
        for index, character in enumerate(inner):
            if character == '<':
                depth += 1
            elif character == '>':
                depth -= 1
            elif character == ',' and depth == 0:
                parts.append(inner[start:index].strip())
                start = index + 1
        parts.append(inner[start:].strip())
        return outer, tuple(parts)

    def assert_known(value_type: str, where: str) -> None:
        generic = generic_parts(value_type)
        if generic is not None:
            outer, parts = generic
            if outer in {'enum', 'asset_ref', 'file_ref', 'directory_ref'}:
                return
            if outer in {'optional', 'list', 'set', 'map'}:
                for part in parts:
                    assert_known(part, where)
                return
            assert record_type_contract(value_type) is not None, f'{where}: {value_type}'
            return
        assert value_type in atomic_types or record_type_contract(value_type) is not None, (
            f'{where}: {value_type}'
        )

    for function in official_function_registry_v6.complete_catalog():
        for parameter in function['parameters']:
            assert_known(parameter['value_type'], f"{function['function_id']}.{parameter['name']}")
        assert_known(function['return_type'], f"{function['function_id']}.return")


def test_window_selector_is_a_structured_editable_contract() -> None:
    selector = record_type_contract('window_selector')
    assert selector is not None
    assert [field.field_id for field in selector.fields] == [
        'window_selector.field.title',
        'window_selector.field.match_mode',
        'window_selector.field.class_name',
        'window_selector.field.process_id',
        'window_selector.field.index',
    ]
    for function_id in ('official.window.find', 'official.window.wait_visible'):
        contract = official_function_registry_v6.require(function_id)
        parameter = next(item for item in contract.parameters if item.name == 'selector')
        assert parameter.value_type == 'window_selector'
        assert parameter.control == 'key-value'


def test_only_verified_runtime_functions_are_visible_to_insert() -> None:
    available = official_function_registry_v6.available_catalog()

    assert {'日志.输出', '等待.持续', '目标.获取画面', '图像.查找', '输入.点击'} <= {
        item['qualified_name'] for item in available
    }
    assert all(item['implementation_state'] == 'available' for item in available)
    assert all(item['verified_platforms'] for item in available)
    assert_available_runtime_contracts_are_bound()


def test_wait_until_uses_the_canonical_program_time_type_end_to_end() -> None:
    contract = official_function_registry_v6.require('official.wait.until')
    time_parameter = next(item for item in contract.parameters if item.name == 'time')
    assert time_parameter.value_type == 'time'

    inserted = insert_call(
        create_program_document('等待到指定时间'),
        official_function_registry_v6,
        contract.function_id,
    )
    document = update_call_argument(
        inserted.document,
        official_function_registry_v6,
        inserted.selected_statement_id,
        time_parameter.parameter_id,
        TimeValue(value_id=new_stable_id('value'), value=time(8, 30)),
    ).document

    compiled = compile_program_document(
        document,
        official_function_registry_v6,
        target_platform='windows',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    instruction = compiled['ecir']['functions'][0]['instructions'][0]
    assert instruction['arguments'][time_parameter.parameter_id] == {
        'kind': 'time', 'value': '08:30:00',
    }


def test_platform_matrix_is_complete_and_android_local_is_not_overclaimed() -> None:
    catalog = official_function_registry_v6.complete_catalog()
    for contract in catalog:
        assert [item['platform'] for item in contract['platform_support']] == [
            'windows', 'android_adb', 'android_local', 'no_target',
        ]
        for item in contract['platform_support']:
            if item['support'] == 'conditional':
                assert item['required_capabilities']

    log = official_function_registry_v6.require('official.log.output')
    capture = official_function_registry_v6.require('official.target.capture_frame')
    file_read = official_function_registry_v6.require('official.file.read_text')
    assert log.verified_platforms == ('windows', 'android_adb', 'no_target')
    assert capture.verified_platforms == ('windows', 'android_adb')
    assert file_read.verified_platforms == ('windows', 'android_adb', 'no_target')
    assert all('android_local' not in item.verified_platforms for item in (
        log, capture, file_read,
    ))


def test_android_minimum_api_is_declared_per_capability_not_globally() -> None:
    def android_floor(qualified_name: str) -> int:
        contract = official_function_registry_v6.by_qualified_name(qualified_name)
        support = next(
            item for item in contract.platform_support
            if item.platform == 'android_local'
        )
        assert support.minimum_android_api is not None
        return support.minimum_android_api

    assert android_floor('日志.输出') == 21
    assert android_floor('消息.发送') == 23
    assert android_floor('输入.点击') == 24


def test_compiler_explains_which_statement_raises_android_floor() -> None:
    inserted = insert_call(
        create_program_document('点击兼容性'),
        official_function_registry_v6,
        'official.input.click',
    )
    document = update_call_argument(
        inserted.document,
        official_function_registry_v6,
        inserted.selected_statement_id,
        'official.input.click.parameter.position',
        PointValue(value_id=new_stable_id('value'), x=10, y=20),
    ).document
    compiled = compile_program_document(
        document,
        official_function_registry_v6,
        target_platform='windows',
        target_definitions=[{
            'target_id': 'target_windows', 'name': '窗口', 'type': 'windows',
        }],
        default_target_id='target_windows',
    )

    assert compiled['valid'] is True, compiled['diagnostics']
    assert compiled['ecir']['minimum_android_api'] == 24
    assert compiled['ecir']['android_api_requirements'] == [{
        'kind': 'function',
        'contract_function_id': 'official.input.click',
        'display_name': '输入.点击',
        'minimum_android_api': 24,
        'statement_ids': [inserted.selected_statement_id],
    }]


def test_verified_windows_function_compiles_but_android_local_is_blocked() -> None:
    document = create_program_document('平台矩阵')
    document = insert_call(
        document,
        official_function_registry_v6,
        'official.target.capture_frame',
    ).document

    windows = compile_program_document(
        document, official_function_registry_v6, target_platform='windows',
    )
    assert windows['valid'] is True, windows['diagnostics']
    assert windows['ecir']['supported_platforms'] == ['android_adb', 'windows']
    assert windows['ecir']['target_platform'] == 'windows'
    assert adapt_program_ecir_for_runtime(windows['ecir'])['target_platform'] == 'windows'

    invalid_plan = {**windows['ecir'], 'target_platform': 'android_local'}
    with pytest.raises(RuntimeFailure, match='没有经过目标平台运行验证'):
        adapt_program_ecir_for_runtime(invalid_plan)

    android = compile_program_document(
        document, official_function_registry_v6, target_platform='android_local',
    )
    assert android['valid'] is False
    assert any(item['code'] == 'PGM-PLATFORM-002' for item in android['diagnostics'])


def test_host_requirement_and_target_kind_are_separate_contract_axes() -> None:
    capture = official_function_registry_v6.by_qualified_name('目标.获取画面')
    move_pointer = official_function_registry_v6.by_qualified_name('输入.移动指针')
    send = official_function_registry_v6.by_qualified_name('消息.发送')

    assert capture.host_requirements == ('windows', 'android')
    assert capture.target_kinds == ('windows', 'android_adb', 'android_local')
    assert move_pointer.host_requirements == ('windows',)
    assert move_pointer.target_kinds == ('windows',)
    assert send.target_kinds == ()
    assert send.host_requirements == ('windows', 'android')


def test_normal_empty_and_transient_errors_are_not_conflated() -> None:
    find = official_function_registry_v6.by_qualified_name('图像.查找')
    request = official_function_registry_v6.by_qualified_name('网络.请求')

    assert find.normal_empty is True
    assert find.return_type == 'optional<image_match>'
    assert {item.classification for item in find.errors} == {'transient', 'permanent'}
    assert request.normal_empty is False
    assert any(item.error_id == 'network.timeout' and item.classification == 'transient' for item in request.errors)


def test_recursive_delete_has_a_distinct_dangerous_contract() -> None:
    ordinary = official_function_registry_v6.by_qualified_name('目录.删除')
    recursive = official_function_registry_v6.by_qualified_name('目录.递归删除')

    assert ordinary.dangerous is False
    assert recursive.dangerous is True
    assert recursive.function_id != ordinary.function_id
    assert recursive.parameters[0].value_type == 'directory_ref<delete_tree>'
    assert recursive.implementation_state == 'available'
    assert recursive.verified_platforms == ('windows', 'android_adb', 'no_target')
    assert '目录.递归删除' in {
        item['qualified_name']
        for item in official_function_registry_v6.available_catalog()
    }


def test_parameter_ui_actions_only_advertise_real_capture_paths() -> None:
    vision = official_function_registry_v6.by_qualified_name('图像.查找')
    image = next(item for item in vision.parameters if item.name == 'image')
    region = next(item for item in vision.parameters if item.name == 'region')

    assert image.ui['control'] == 'resource'
    assert [item['id'] for item in image.ui['actions']] == [
        'choose-resource', 'capture-image',
    ]
    assert image.ui['actions'][1]['platforms'] == [
        'windows', 'android_adb', 'android_local',
    ]
    assert region.ui['actions'] == [{
        'id': 'pick-region',
        'capture_kind': 'region',
        'platforms': ['windows', 'android_adb', 'android_local'],
        'max_rects': 1,
    }]

    control = official_function_registry_v6.by_qualified_name('控件.查找')
    selector = next(item for item in control.parameters if item.name == 'selector')
    assert selector.ui == {
        'control': 'control-selector',
        'importance': 'primary',
        'editor_strategy': 'capture',
        'actions': [{
            'id': 'capture-control',
            'capture_kind': 'control',
            'platforms': ['windows', 'android_adb', 'android_local'],
            'result_reference_type': 'control_selector',
        }],
    }


def test_author_forms_hide_runtime_owned_parameters_and_publish_input_guidance() -> None:
    log = official_function_registry_v6.by_qualified_name('日志.输出')
    content = next(item for item in log.parameters if item.name == 'content')
    category = next(item for item in log.parameters if item.name == 'category')
    assert content.ui['importance'] == 'primary'
    assert '当前体力' in content.ui['placeholder']
    assert category.ui['importance'] == 'internal'

    wait_until = official_function_registry_v6.by_qualified_name('等待.直到')
    time = next(item for item in wait_until.parameters if item.name == 'time')
    past_policy = next(item for item in wait_until.parameters if item.name == 'past_policy')
    assert time.ui['placeholder'] == 'HH:mm:ss'
    assert past_policy.ui['importance'] == 'internal'
    assert past_policy.default == 'next_day'

    ocr = official_function_registry_v6.require('official.text.recognize')
    language = next(item for item in ocr.parameters if item.name == 'language')
    frame = next(item for item in ocr.parameters if item.name == 'frame')
    assert language.ui['importance'] == 'internal'
    assert language.default == 'auto'
    assert frame.display_name == '使用画面'
    assert frame.ui['importance'] == 'advanced'


def test_every_free_input_contract_explains_a_real_value_or_format() -> None:
    banned_labels = {'无结果', '待配置', '默认配置', '使用运行环境默认值', '请输入内容'}
    free_controls = {
        'auto', 'text', 'number', 'duration', 'time', 'slider-number',
        'json', 'coordinate', 'region',
    }
    scalar_types = {
        'string', 'any', 'message_value', 'int64', 'float64', 'percentage',
        'duration', 'date', 'datetime', 'time', 'timezone', 'point', 'rect',
        'path', 'url', 'relative_path', 'json', 'json_value',
    }

    for contract in official_function_registry_v6.complete_catalog():
        for parameter in contract['parameters']:
            ui = parameter['ui']
            where = f"{contract['function_id']}.{parameter['name']}"
            default_label = str(ui.get('effective_default_label') or '')
            assert not any(label in default_label for label in banned_labels), where
            placeholder = ui.get('placeholder', '').strip()
            assert not any(label in placeholder for label in banned_labels), where
            value_type = parameter['value_type']
            while value_type.startswith('optional<') and value_type.endswith('>'):
                value_type = value_type[9:-1]
            if (
                ui.get('importance') != 'internal'
                and parameter['control'] in free_controls
                and value_type in scalar_types
            ):
                assert ui.get('placeholder', '').strip(), where

    timezone = next(
        item for item in official_function_registry_v6.require('official.time.now').parameters
        if item.name == 'timezone'
    )
    assert timezone.ui['effective_default_label'] == '当前设备时区（如 Asia/Shanghai）'
    assert 'GMT+8' in timezone.ui['placeholder']


def test_picker_select_and_toggle_controls_do_not_publish_text_placeholders() -> None:
    no_text_placeholder = {
        'select', 'resource', 'toggle', 'file', 'directory', 'target',
        'application', 'instance', 'instance-multi-select', 'control-reference',
        'control-selector', 'gesture-path', 'key-chord', 'list', 'key-value',
    }
    for contract in official_function_registry_v6.complete_catalog():
        for parameter in contract['parameters']:
            if parameter['control'] in no_text_placeholder:
                assert 'placeholder' not in parameter['ui'], parameter['parameter_id']


def test_semantic_placeholders_cover_high_risk_text_and_numeric_parameters() -> None:
    parameters = {
        item['parameter_id']: item
        for contract in official_function_registry_v6.complete_catalog()
        for item in contract['parameters']
    }
    expected_fragments = {
        'official.file.replace_text.parameter.search': ('旧名称',),
        'official.file.replace_text.parameter.replacement': ('新名称',),
        'official.message.send.parameter.name': ('订单处理完成',),
        'official.message.wait_receive.parameter.name': ('订单处理完成',),
        'official.text.wait_visible.parameter.text': ('登录成功',),
        'official.control.set_value.parameter.value': ('已完成', '[项目 · 状态]'),
        'official.directory.copy.parameter.name': ('备份-2026-09',),
        'official.directory.move.parameter.name': ('归档-2026-09',),
        'official.frame.save.parameter.quality': ('1–100', '90'),
        'official.color.find.parameter.tolerance': ('0–255', '0'),
        'official.image.find_all.parameter.limit': ('1–1000', '100'),
        'official.network.request.parameter.max_response_bytes': ('4194304', '4 MB'),
        'official.network.request.parameter.max_redirects': ('5 次',),
        'official.network.upload_file.parameter.max_file_bytes': ('536870912', '512 MB'),
        'official.network.request.parameter.url': ('https://',),
        'official.wait.until.parameter.time': ('HH:mm:ss',),
        'official.time.now.parameter.timezone': ('GMT+8',),
    }
    for parameter_id, fragments in expected_fragments.items():
        placeholder = parameters[parameter_id]['ui']['placeholder']
        assert all(fragment in placeholder for fragment in fragments), parameter_id

    assert _parameter_placeholder(
        'synthetic.date', 'date', '日期', 'date', 'auto', {}, None,
    ) == 'YYYY-MM-DD，例如：2026-09-05'
    assert _parameter_placeholder(
        'synthetic.datetime', 'datetime', '日期时间', 'datetime', 'auto', {}, None,
    ) == 'YYYY-MM-DD HH:mm:ss，例如：2026-09-05 18:30:00'


def test_numeric_placeholders_match_declared_ranges_and_percentage_format() -> None:
    for contract in official_function_registry_v6.complete_catalog():
        for parameter in contract['parameters']:
            if parameter['control'] not in {'number', 'slider-number'}:
                continue
            constraints = parameter['constraints']
            placeholder = parameter['ui'].get('placeholder', '')
            minimum = constraints.get('minimum')
            maximum = constraints.get('maximum')
            if minimum is None or maximum is None:
                continue
            if parameter['value_type'] == 'percentage':
                assert f'{float(minimum) * 100:g}%' in placeholder
                assert f'{float(maximum) * 100:g}%' in placeholder
            else:
                assert f'{minimum:g}' in placeholder
                assert f'{maximum:g}' in placeholder


def test_select_effective_defaults_use_authoritative_display_labels() -> None:
    for contract in official_function_registry_v6.complete_catalog():
        for parameter in contract['parameters']:
            if parameter['control'] != 'select' or not parameter['has_default']:
                continue
            choice = next(
                item for item in parameter['constraints']['choices']
                if item['value'] == parameter['default']
            )
            assert parameter['ui']['effective_default_label'] == choice['label']


def test_every_select_has_unique_authoritative_choices_and_a_valid_default() -> None:
    for contract in official_function_registry_v6.complete_catalog():
        for parameter in contract['parameters']:
            if parameter['control'] != 'select':
                continue
            choices = parameter['constraints'].get('choices')
            assert choices, f"{contract['function_id']}.{parameter['name']}"
            values = [
                item['value'] if isinstance(item, dict) else item
                for item in choices
            ]
            assert len(values) == len(set(values))
            if parameter['has_default']:
                assert parameter['default'] in values


def test_every_official_call_skeleton_contains_every_contract_parameter() -> None:
    """Newly inserted calls must be immediately editable by the shared inspector."""

    for contract in official_function_registry_v6.complete_catalog():
        inserted = insert_call(
            create_program_document(contract['function_id']),
            official_function_registry_v6,
            contract['function_id'],
        )
        statement = inserted.document.function.statements[0]
        assert set(statement.arguments) == {
            parameter['parameter_id'] for parameter in contract['parameters']
        }


def test_input_contracts_declare_the_stable_errors_emitted_by_all_runtimes() -> None:
    expected = {
        'official.input.click': {
            'target.pointer_button_unsupported',
            'target.invalid_click_count',
            'target.invalid_click_hold',
        },
        'official.input.type_text': {'target.focus_missing'},
        'official.input.scroll': {
            'target.scroll_mode_unsupported',
            'target.scroll_direction_unsupported',
            'target.invalid_scroll_distance',
        },
        'official.input.drag': {
            'target.invalid_drag_path',
            'target.drag_easing_unsupported',
        },
    }

    for function_id, error_ids in expected.items():
        contract = official_function_registry_v6.require(function_id)
        assert error_ids <= {error.error_id for error in contract.errors}


def test_drag_accepts_the_structural_path_value_used_by_capture_and_recording() -> None:
    document = create_program_document('拖拽路径')
    result = insert_call(
        document,
        official_function_registry_v6,
        'official.input.drag',
        arguments={'official.input.drag.parameter.path': PathValue(
            value_id='value_drag_path',
            points=(PointLiteral(x=10, y=20), PointLiteral(x=110, y=20)),
        )},
    )

    compiled = compile_program_document(result.document, official_function_registry_v6)
    assert compiled['valid'] is True


def test_platform_specific_enum_options_are_declared_in_the_contract() -> None:
    click = official_function_registry_v6.require('official.input.click')
    button = next(item for item in click.parameters if item.name == 'button')
    choices = {item['value']: item for item in button.constraints['choices']}
    assert 'platforms' not in choices['primary']
    assert choices['secondary']['platforms'] == ['windows']
    assert choices['middle']['platforms'] == ['windows']

    text = official_function_registry_v6.require('official.input.type_text')
    mode = next(item for item in text.parameters if item.name == 'mode')
    mode_choices = {item['value']: item for item in mode.constraints['choices']}
    assert mode_choices['background']['platforms'] == ['windows']
    assert mode_choices['physical']['platforms'] == ['windows']
    assert mode_choices['target']['platforms'] == ['android_adb', 'android_local']


def test_unknown_enum_value_is_rejected_by_the_program_command_boundary() -> None:
    inserted = insert_call(
        create_program_document('文本输入'),
        official_function_registry_v6,
        'official.input.type_text',
    )
    with pytest.raises(ProgramCommandError, match='不是受支持的选项'):
        update_call_argument(
            inserted.document,
            official_function_registry_v6,
            inserted.selected_statement_id,
            'official.input.type_text.parameter.mode',
            StringValue(value_id=new_stable_id('value'), value='invented'),
        )


def test_default_target_platform_rejects_a_platform_specific_literal_choice() -> None:
    inserted = insert_call(
        create_program_document('ADB 点击'),
        official_function_registry_v6,
        'official.input.click',
    )
    document = update_call_argument(
        inserted.document,
        official_function_registry_v6,
        inserted.selected_statement_id,
        'official.input.click.parameter.position',
        PointValue(value_id=new_stable_id('value'), x=10, y=20),
    ).document
    document = update_call_argument(
        document,
        official_function_registry_v6,
        inserted.selected_statement_id,
        'official.input.click.parameter.button',
        StringValue(value_id=new_stable_id('value'), value='secondary'),
    ).document

    compiled = compile_program_document(
        document,
        official_function_registry_v6,
        target_platform='windows',
        target_definitions=[{
            'target_id': 'target_adb', 'name': '模拟器', 'type': 'android_adb',
            'device_serial': 'emulator-5554',
        }],
        default_target_id='target_adb',
    )
    assert compiled['valid'] is False
    assert any(item['code'] == 'PGM-PLATFORM-003' for item in compiled['diagnostics'])
