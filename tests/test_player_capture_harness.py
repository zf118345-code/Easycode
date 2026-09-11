from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from core.vnext.android_delivery_v6 import AndroidDeliveryServiceV6
from scripts.create_player_capture_harness import create_fixture


def test_android_local_capture_harness_has_only_android_local_target(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path, include_android_local=True)

    metadata = AndroidDeliveryServiceV6().validate_bundle(
        fixture['bundle'],
        fixture['trust_root'],
    )
    assert metadata['project_id'] == 'player_capture_harness'
    assert metadata['android_local_contract_status'] == 'planned'

    with zipfile.ZipFile(fixture['bundle']) as archive:
        project = json.loads(archive.read('runtime/project.json'))
        ecir = json.loads(archive.read('runtime/ecir.json'))
    assert project['default_target_id'] == 'target_android_local'
    assert project['targets'] == [{
        'target_id': 'target_android_local',
        'name': '当前 Android 设备',
        'type': 'android_local',
    }]
    variables = {
        item['variable_id']: item
        for item in ecir['project_variables']
    }
    assert variables['variable_image']['value_type'] == 'optional<asset_ref<image>>'
    assert variables['variable_image']['default_value'] is None
    assert variables['variable_point']['value_type'] == 'point'
    assert variables['variable_input_file']['constraints'] == {}


def test_android_local_capture_harness_rejects_adb_target_mix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='不能同时声明'):
        create_fixture(tmp_path, adb_serials=('emulator-5554',), include_android_local=True)


def test_android_runtime_harness_exercises_real_frame_and_ocr(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_runtime=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'target.capture_frame',
        'text.recognize',
        'log.write',
        'standard.text.match',
        'standard.text.wait_visible',
        'log.write',
    ]
    assert ecir['required_capabilities'] == ['target.capture_frame']
    assert instructions[0]['capabilities'] == ['target.capture_frame']
    assert instructions[2]['arguments']['official.log.output.parameter.content']['kind'] == (
        'member_access'
    )


def test_android_control_harness_exercises_semantic_control_flow(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_controls=True,
        android_application_id='com.example.easycode.debug',
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'host.app.start',
        'wait.duration',
        'control.find',
        'control.input_text',
        'wait.duration',
        'control.read_text',
        'log.write',
        'control.click',
        'input.text',
        'wait.duration',
        'control.read_text',
        'log.write',
        'input.key',
        'wait.duration',
        'control.find',
        'control.click',
        'wait.duration',
        'control.find',
        'control.read_text',
        'log.write',
        'control.find',
        'input.click',
        'wait.duration',
        'control.read_text',
        'log.write',
        'control.find',
        'input.drag',
        'wait.duration',
        'control.read_text',
        'log.write',
        'input.scroll',
        'wait.duration',
        'control.read_text',
        'log.write',
        'input.key',
        'log.write',
    ]
    assert set(ecir['required_capabilities']) == {
        'application.launch', 'control.semantic', 'host.launch_application',
        'target.input', 'input.key',
    }
    application = instructions[0]['arguments']['official.application.start.parameter.application']
    assert application['application_ref.field.package'] == 'com.example.easycode.debug'
    assert application['application_ref.field.activity'] == (
        'com.easycode.player.input.SemanticControlHarnessActivity'
    )
    selector = instructions[2]['arguments']['official.control.find.parameter.selector']
    assert selector['control_selector.field.provider'] == 'android_accessibility'
    assert selector['control_selector.field.content_description'] == 'EasyCode 测试输入框'
    coordinate_instruction = next(item for item in instructions if item['instruction_id'] == 'statement_click_derived_coordinate')
    coordinate = coordinate_instruction['arguments']['official.input.click.parameter.position']
    assert coordinate['operation_id'] == 'core.rect_center.v1'
    assert coordinate['inputs']['core.rect_center.v1.input.rect']['field_id'] == 'control_ref.field.rect'
    assert instructions[-3]['arguments']['official.log.output.parameter.content']['kind'] == 'reference'
    drag = next(item for item in instructions if item['opcode'] == 'input.drag')
    assert drag['arguments']['official.input.drag.parameter.path']['kind'] == 'path'
    scroll = next(item for item in instructions if item['opcode'] == 'input.scroll')
    assert scroll['arguments']['official.input.scroll.parameter.start']['operation_id'] == 'core.rect_center.v1'
    assert instructions[-1]['arguments']['official.log.output.parameter.content'] == 'Android 返回键已验证'


def test_android_vision_marker_harness_packages_and_uses_real_asset(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_controls=True,
        exercise_android_vision_marker=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
        registry = json.loads(archive.read('assets/registry.json'))
        marker = archive.read('assets/image/asset_android_vision_marker.png')
    record = registry['assets']['asset_android_vision_marker']
    assert record['width'] == 64 and record['height'] == 64
    assert record['size_bytes'] == len(marker)
    assert set(ecir['required_capabilities']) >= {'target.capture_frame', 'target.input'}
    opcodes = [item['opcode'] for item in ecir['functions'][0]['instructions']]
    assert opcodes[-7:] == [
        'target.capture_frame', 'vision.find', 'log.write',
        'standard.image.wait_visible', 'log.write', 'input.key', 'log.write',
    ]


def test_android_file_harness_exercises_private_text_json_and_directory(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_files=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'project.data_directory',
        'file.write_text',
        'file.append_text',
        'file.replace_text',
        'file.read_text',
        'log.write',
        'file.write_json',
        'file.read_json',
        'log.write',
        'directory.list',
        'log.write',
    ]
    write_reference = instructions[1]['arguments']['official.file.write_text.parameter.file']
    read_reference = instructions[4]['arguments']['official.file.read_text.parameter.file']
    assert write_reference['operation_id'] == 'core.file_ref_child.v1'
    assert write_reference['result_type'] == 'file_ref<write>'
    assert read_reference['result_type'] == 'file_ref<read>'
    assert write_reference['inputs']['core.file_ref_child.v1.input.relative_path'] == 'g6-runtime.txt'
    assert instructions[-1]['arguments']['official.log.output.parameter.category'] == 'android-file-harness'


def test_android_remaining_basics_harness_is_assertive_and_requires_its_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match='exercise-android-runtime'):
        create_fixture(
            tmp_path / 'invalid',
            include_android_local=True,
            exercise_android_remaining_basics=True,
        )

    fixture = create_fixture(
        tmp_path / 'valid',
        include_android_local=True,
        exercise_android_runtime=True,
        exercise_android_files=True,
        exercise_android_remaining_basics=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    by_id = {item['instruction_id']: item for item in instructions}

    assert by_id['statement_save_android_frame']['opcode'] == 'frame.save'
    assert by_id['statement_android_frame_exists']['opcode'] == 'file.exists'
    assert by_id['statement_assert_android_frame_saved']['arguments']['otherwise'][0][
        'arguments'
    ]['error_id'] == 'harness.android_frame_not_saved'
    assert by_id['statement_read_android_color']['opcode'] == 'color.read'
    assert by_id['statement_find_android_color']['opcode'] == 'color.find'
    assert by_id['statement_assert_android_color_found']['arguments']['otherwise'][0][
        'arguments'
    ]['error_id'] == 'harness.android_color_not_found'
    assert by_id['statement_write_android_clipboard']['opcode'] == 'clipboard.write_text'
    assert by_id['statement_read_android_clipboard']['opcode'] == 'clipboard.read_text'
    assert by_id['statement_assert_android_clipboard']['arguments']['otherwise'][0][
        'arguments'
    ]['error_id'] == 'harness.android_clipboard_mismatch'
    assert set(ecir['required_capabilities']) >= {
        'target.capture_frame', 'filesystem', 'host.clipboard',
        'clipboard_read', 'clipboard_write',
    }


def test_android_recording_harness_keeps_a_real_multiframe_window(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_recording=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == ['wait.duration', 'log.write']
    assert instructions[0]['arguments']['official.wait.duration.parameter.duration'] == 5_000


def test_android_message_harness_fails_when_wait_returns_no_message(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_messages=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'message.wait_receive', 'control.if',
    ]
    assertion = instructions[1]['arguments']
    assert assertion['condition']['left']['symbol_id'] == 'local_real_lan_message'
    assert assertion['then'][0]['instruction_id'] == 'statement_log_real_lan_message'
    assert assertion['otherwise'][0]['opcode'] == 'control.fail'
    assert assertion['otherwise'][0]['arguments']['error_id'] == 'harness.message_not_received'


def test_android_listener_harness_requires_handler_dispatch(tmp_path: Path) -> None:
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        exercise_android_message_listener=True,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    variables = {item['variable_id']: item for item in ecir['project_variables']}
    assert variables['variable_listener_received']['default_value'] is False
    main = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in main] == [
        'log.write', 'control.listen', 'wait.duration', 'control.if',
    ]
    assertion = main[-1]['arguments']
    assert assertion['condition']['variable_id'] == 'variable_listener_received'
    assert assertion['otherwise'][0]['arguments']['error_id'] == 'harness.listener_not_dispatched'
    handler = ecir['functions'][1]['instructions']
    assert handler[0]['opcode'] == 'data.assign_project'
    assert handler[0]['arguments']['target']['variable_id'] == 'variable_listener_received'
    assert handler[1]['instruction_id'] == 'statement_log_listener_handler'


def test_android_message_sender_seeds_sync_and_listener_paths(tmp_path: Path) -> None:
    recipient = 'instance_ref.v1.test-host.test-instance'
    fixture = create_fixture(
        tmp_path,
        include_android_local=True,
        android_message_recipient=recipient,
    )
    with zipfile.ZipFile(fixture['bundle']) as archive:
        ecir = json.loads(archive.read('runtime/ecir.json'))
    instructions = ecir['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'message.send', 'message.send', 'log.write',
    ]
    assert [
        item['arguments']['official.message.send.parameter.name']
        for item in instructions[:2]
    ] == ['真实互通测试', '监听互通测试']
    assert all(
        item['arguments']['official.message.send.parameter.recipients'][0]['reference_id'] == recipient
        for item in instructions[:2]
    )
