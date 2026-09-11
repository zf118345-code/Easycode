from __future__ import annotations

import copy
import json
import zipfile

import pytest

from core.vnext.player_bindings import (
    PLAYER_TERMINAL_ACTION_SPECS,
    PlayerBindingError,
    apply_player_bindings,
    build_player_binding_sources,
    merge_target_overrides,
    player_binding_contract,
    player_terminal_action_closure,
    player_type_fingerprint,
    validate_player_form_bindings,
)
from core.vnext.player_bundle import PlayerBundleError, VNextPlayerBundleManager
from core.vnext.file_runtime_v6 import windows_directory_reference
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.player_service import VNextPlayerService
from core.vnext.publish import VNextPublisher
from core.vnext.workspace import VNextWorkspaceManager
from core.vnext.workspace_context import VNextWorkspaceError

LOG_CONTENT = 'official.log.output.parameter.content'
LOG_CATEGORY = 'official.log.output.parameter.category'


def test_player_preflight_reports_numpy_and_pillow_frame_sizes() -> None:
    numpy_like = type('NumpyFrame', (), {'shape': (640, 900, 3)})()
    pillow_like = type('PillowFrame', (), {'size': (1080, 2340)})()

    assert VNextPlayerBundleManager._frame_size(numpy_like) == [900, 640]
    assert VNextPlayerBundleManager._frame_size(pillow_like) == [1080, 2340]
    assert VNextPlayerBundleManager._frame_size(object()) == []


def _target(target_id: str = 'target_game') -> dict:
    return {
        'target_id': target_id,
        'name': '游戏窗口',
        'type': 'windows',
        'window_title': 'Game',
        'window_match': 'contains',
        'work_area': {'mode': 'client'},
        'allow_physical_fallback': True,
    }


def _ecir() -> dict:
    return {
        'ecir_version': 1,
        'entry_function_id': 'function_main',
        'supported_platforms': ['windows'],
        'targets': [_target()],
        'project_variables': [{
            'variable_id': 'variable_count',
            'display_name': '次数',
            'value_type': 'int64',
            'default_value': 1,
            'constraints': {'minimum': 0, 'maximum': 10},
        }],
        'functions': [{
            'function_id': 'function_main',
            'name': '主程序',
            'parameter_definitions': [],
            'instructions': [{
                'instruction_id': 'statement_log',
                'function_id': 'official.log.output',
                'opcode': 'log.output',
                'arguments': {LOG_CONTENT: '原内容'},
                'parameter_ids': {LOG_CONTENT: LOG_CONTENT},
            }],
        }, {
            'function_id': 'function_worker',
            'name': '执行任务',
            'parameter_definitions': [{
                'parameter_id': 'parameter_limit',
                'name': 'symbol_limit',
                'display_name': '上限',
                'value_type': 'int64',
                'required': True,
                'default': None,
                'constraints': {'minimum': 1, 'maximum': 20},
            }],
            'instructions': [],
        }],
    }


def _value_control(
    control_id: str,
    control_type: str,
    binding: dict,
    value_type: str,
    source_constraints: dict | None = None,
    **extra,
) -> dict:
    return {
        'control_id': control_id,
        'type': control_type,
        'label': control_id,
        'source_type': value_type,
        'type_fingerprint': player_type_fingerprint(value_type, source_constraints),
        'binding': binding,
        **extra,
    }


def _form() -> dict:
    return {
        'schema_version': 3,
        'title': '测试 Player',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [
                _value_control(
                    'count', 'number',
                    {'kind': 'project_variable', 'variable_id': 'variable_count'},
                    'int64', {'minimum': 0, 'maximum': 10},
                    default=2,
                ),
                _value_control(
                    'limit', 'number',
                    {
                        'kind': 'function_parameter',
                        'function_id': 'function_worker',
                        'parameter_id': 'parameter_limit',
                    },
                    'int64', {'minimum': 1, 'maximum': 20},
                    default=5,
                ),
                _value_control(
                    'message', 'expression',
                    {
                        'kind': 'statement_parameter',
                        'function_id': 'function_main',
                        'statement_id': 'statement_log',
                        'parameter_id': LOG_CONTENT,
                    },
                    'any', {}, default='Player 内容',
                ),
                {
                    'control_id': 'run_worker',
                    'type': 'button',
                    'label': '执行任务',
                    'binding': {'kind': 'function_action', 'function_id': 'function_worker'},
                },
                _value_control(
                    'window_title', 'text',
                    {
                        'kind': 'setting',
                        'target_id': 'target_game',
                        'setting_id': 'target.window_title',
                    },
                    'string', {'max_length': 512}, default='Player Game',
                ),
            ],
        }],
    }


def test_schema3_stable_bindings_apply_all_supported_slots() -> None:
    ecir = _ecir()
    form = _form()
    resolved = validate_player_form_bindings(ecir, form)
    assert set(resolved) == {
        'count', 'limit', 'message', 'run_worker', 'window_title',
    }

    applied = apply_player_bindings(
        ecir,
        form,
        {
            'count': 7,
            'limit': 9,
            'message': '运行时内容',
            'window_title': 'Runtime Game',
        },
        'run_worker',
    )
    assert applied['entry_function_id'] == 'function_worker'
    assert applied['project_variable_overrides'] == {'variable_count': 7}
    assert applied['function_arguments'] == {
        'function_worker': {'parameter_limit': 9},
    }
    instruction = applied['functions'][0]['instructions'][0]
    assert instruction['arguments'][LOG_CONTENT] == '运行时内容'
    assert applied['target_overrides'] == {
        'target_game': {'target.window_title': 'Runtime Game'},
    }
    # Validation and application never write private authoring markers into ECIR.
    assert '_player_owner_function_id' not in json.dumps(applied)

    defaults = apply_player_bindings(ecir, form, {})
    assert defaults['project_variable_overrides']['variable_count'] == 2
    assert defaults['function_arguments']['function_worker']['parameter_limit'] == 5
    assert defaults['functions'][0]['instructions'][0]['arguments'][LOG_CONTENT] == 'Player 内容'
    assert defaults['target_overrides']['target_game']['target.window_title'] == 'Player Game'


def test_boolean_map_fixed_options_are_validated_and_cannot_be_bypassed() -> None:
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_tasks',
        'display_name': '任务列表',
        'value_type': 'map<string,bool>',
        'default_value': {'开放任务': True, '暂未开放': False},
        'constraints': {},
    })
    control = _value_control(
        'tasks', 'key-value',
        {'kind': 'project_variable', 'variable_id': 'variable_tasks'},
        'map<string,bool>', {},
        default={'开放任务': True, '暂未开放': False},
        options=[
            {'label': '开放任务', 'value': '开放任务'},
            {
                'label': '暂未开放', 'value': '暂未开放',
                'fixed_value': False,
                'fixed_reason': '当前版本暂未开放',
            },
        ],
    )
    form = {
        'schema_version': 3,
        'title': '任务 Player',
        'pages': [{'page_id': 'main', 'title': '任务', 'controls': [control]}],
    }

    normalized = VNextPlayerService.normalize_form(form)
    validate_player_form_bindings(ecir, normalized)
    applied = apply_player_bindings(
        ecir,
        normalized,
        {'tasks': {'开放任务': False, '暂未开放': True}},
    )
    assert applied['project_variable_overrides']['variable_tasks'] == {
        '开放任务': False,
        '暂未开放': False,
    }

    invalid = copy.deepcopy(normalized)
    invalid['pages'][0]['controls'][0]['options'][1]['value'] = '不存在的任务'
    with pytest.raises(PlayerBindingError, match='PLY-OPTION-001'):
        validate_player_form_bindings(ecir, invalid)


def test_player_profile_persists_canonical_fixed_boolean_options(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_tasks',
        'display_name': '任务列表',
        'value_type': 'map<string,bool>',
        'default_value': {'开放任务': True, '暂未开放': False},
        'constraints': {},
    })
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '任务 Player',
        'pages': [{
            'page_id': 'main',
            'title': '任务',
            'controls': [_value_control(
                'tasks', 'key-value',
                {'kind': 'project_variable', 'variable_id': 'variable_tasks'},
                'map<string,bool>', {},
                default={'开放任务': True, '暂未开放': False},
                options=[
                    {'label': '开放任务', 'value': '开放任务'},
                    {'label': '暂未开放', 'value': '暂未开放', 'fixed_value': False},
                ],
            )],
        }],
    })
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {'project_id': 'project_fixed_tasks', 'name': 'Fixed Tasks'}
    manager._project = {'targets': [_target()], 'default_target_id': 'target_game'}
    manager._ecir = ecir
    manager._form = form

    saved = manager.save_profile(
        '', '任务方案', None,
        {'tasks': {'开放任务': False, '暂未开放': True}},
    )['profile']
    assert saved['values']['tasks'] == {'开放任务': False, '暂未开放': False}
    assert manager.profiles()['profiles'][0]['values']['tasks']['暂未开放'] is False


@pytest.mark.parametrize(
    ('binding', 'code'),
    [
        ({'kind': 'variable', 'variable_id': 'variable_count'}, 'PLY-BIND-002'),
        ({'kind': 'resource', 'resource_id': 'asset_one'}, 'PLY-BIND-011'),
        ({'kind': 'target', 'target_id': 'target_game'}, 'PLY-BIND-011'),
        ({
            'kind': 'statement_parameter',
            'function_id': 'function_main',
            'statement_id': 'statement_log',
            'parameter_id': LOG_CONTENT,
            'value_id': 'value_nested',
        }, 'PLY-BIND-010'),
    ],
)
def test_legacy_and_unsigned_binding_kinds_are_explicitly_rejected(
    binding: dict,
    code: str,
) -> None:
    form = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'controls': [{
                **_value_control('unsupported', 'text', binding, 'string', {}),
            }],
        }],
    }
    with pytest.raises(PlayerBindingError, match=code):
        validate_player_form_bindings(_ecir(), form)


def test_save_validation_rejects_stale_fingerprint_duplicate_and_dynamic_root() -> None:
    stale = _form()
    stale['pages'][0]['controls'][0]['type_fingerprint'] = player_type_fingerprint(
        'int64', {'minimum': 0, 'maximum': 99},
    )
    with pytest.raises(PlayerBindingError, match='PLY-BIND-005'):
        validate_player_form_bindings(_ecir(), stale)

    duplicate = _form()
    duplicate['pages'][0]['controls'].append(copy.deepcopy(duplicate['pages'][0]['controls'][0]))
    duplicate['pages'][0]['controls'][-1]['control_id'] = 'count_again'
    with pytest.raises(PlayerBindingError, match='PLY-BIND-006'):
        validate_player_form_bindings(_ecir(), duplicate)

    dynamic_ecir = _ecir()
    dynamic_ecir['functions'][0]['instructions'][0]['arguments'][LOG_CONTENT] = {
        'kind': 'reference', 'scope': 'project', 'variable_id': 'variable_count',
    }
    with pytest.raises(PlayerBindingError, match='PLY-BIND-012'):
        validate_player_form_bindings(dynamic_ecir, _form())


def test_values_are_checked_against_source_and_control_constraints() -> None:
    form = _form()
    form['pages'][0]['controls'][0]['constraints'] = {'maximum': 8}
    with pytest.raises(ValueError, match='PLY-BIND-008'):
        apply_player_bindings(_ecir(), form, {'count': 9})
    with pytest.raises(ValueError, match='PLY-BIND-007'):
        apply_player_bindings(_ecir(), form, {'count': '9'})

    required = _form()
    required['pages'][0]['controls'][1].pop('default')
    # A required parameter belongs to its selected function action, not every
    # other runnable project function in the same form.
    apply_player_bindings(_ecir(), required, {})
    with pytest.raises(ValueError, match='PLY-BIND-008'):
        apply_player_bindings(_ecir(), required, {}, 'run_worker')


def test_target_settings_are_scoped_and_validated_for_target_type() -> None:
    first = _target('target_one')
    second = _target('target_two')
    overrides = {
        'target_one': {'target.window_title': 'One'},
        'target_two': {'target.window_title': 'Two'},
    }
    assert merge_target_overrides(first, overrides)['window_title'] == 'One'
    assert merge_target_overrides(second, overrides)['window_title'] == 'Two'

    adb = {
        'target_id': 'target_adb', 'name': 'ADB', 'type': 'android_adb',
        'device_serial': 'emulator-5554',
    }
    with pytest.raises(PlayerBindingError, match='PLY-BIND-009'):
        merge_target_overrides(
            adb,
            {'target_adb': {'target.window_title': 'Wrong platform'}},
        )


def test_player_window_binding_setting_uses_signed_capture_and_exact_identity() -> None:
    binding = {
        'binding_version': 1,
        'binding_id': 'window_binding_customer_one',
        'title': '超能世界',
        'class_name': 'Chrome_WidgetWin_1',
        'executable_name': 'WeChatAppEx.exe',
        'hwnd': 101,
        'process_id': 2001,
        'process_started_at_ms': 123456,
        'captured_at': '2026-09-09T00:00:00+0800',
    }
    target = _target()
    target['window_title'] = '超能世界'
    target['window_match'] = 'exact'
    sources = {
        item['source_id']: item
        for item in build_player_binding_sources(_ecir(), targets=[target])['sources']
    }
    source = sources['setting:target_game:target.window_binding']
    assert source['recommended_control'] == 'control-selector'
    assert source['value_type'] == 'optional<window_binding>'
    assert source['parameter_ui']['actions'] == [{
        'id': 'capture-window',
        'capture_kind': 'point',
        'platforms': ['windows'],
    }]

    form = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'controls': [{
                **_value_control(
                    'window_instance',
                    'control-selector',
                    {
                        'kind': 'setting',
                        'target_id': 'target_game',
                        'setting_id': 'target.window_binding',
                    },
                    'optional<window_binding>',
                    {},
                    default=None,
                ),
                'parameter_ui': source['parameter_ui'],
                'terminal_actions': [{
                    'action_id': 'capture-window',
                    'platforms': ['windows'],
                }],
            }],
        }],
    }
    validate_player_form_bindings(_ecir(), form, targets=[target])
    applied = apply_player_bindings(
        _ecir(), form, {'window_instance': binding}, selected_target_id='target_game',
    )
    merged = merge_target_overrides(target, applied['target_overrides'])
    assert merged['window_title'] == '超能世界'
    assert merged['window_match'] == 'exact'
    assert merged['window_binding'] == binding

    with pytest.raises(PlayerBindingError, match='窗口标题与捕获的窗口实例不一致'):
        merge_target_overrides(target, {'target_game': {
            'target.window_title': '另一个窗口',
            'target.window_binding': binding,
        }})


def test_player_window_capture_maps_desktop_point_to_versioned_binding(monkeypatch) -> None:
    from core.services.player_capture_session import PlayerCaptureSessionService, PlayerSnapshot

    snapshot = PlayerSnapshot(
        snapshot_id='player_snap_window',
        project_path='D:/runtime',
        project_id='project_one',
        workspace_id='player:project_one:release_one',
        workspace_generation=1,
        session_id='player_session_window',
        png=b'',
        width=1000,
        height=700,
        region=[-100, 0, 900, 700],
        backend='player:windows',
        source={
            'purpose': 'window_binding',
            'window_candidates': [{
                'hwnd': 101,
                'process_id': 202,
                'process_started_at_ms': 303,
                'title': '超能世界',
                'class_name': 'Chrome_WidgetWin_1',
                'executable_name': 'WeChatAppEx.exe',
                'rect': [100, 100, 400, 500],
            }],
        },
    )
    monkeypatch.setattr(
        PlayerCaptureSessionService,
        'validate_player_snapshot',
        classmethod(lambda cls, snapshot_id, session_id, rect=None: {'snapshot_id': snapshot_id}),
    )
    with PlayerCaptureSessionService._lock:
        PlayerCaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    try:
        binding = PlayerCaptureSessionService.resolve_window_capture(
            snapshot.snapshot_id,
            snapshot.session_id,
            [250, 150],
            [1000, 700],
        )
    finally:
        with PlayerCaptureSessionService._lock:
            PlayerCaptureSessionService._snapshots.pop(snapshot.snapshot_id, None)

    assert binding['title'] == '超能世界'
    assert binding['hwnd'] == 101
    assert binding['binding_id'].startswith('window_binding_')


def test_player_window_capture_commits_only_current_profile_revision(tmp_path, monkeypatch) -> None:
    from core.services.player_capture_session import player_capture_session_service

    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    target = _target()
    target['window_title'] = '超能世界'
    target['window_match'] = 'exact'
    source = next(
        item for item in build_player_binding_sources(_ecir(), targets=[target])['sources']
        if item['source_id'] == 'setting:target_game:target.window_binding'
    )
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '窗口方案',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'window_instance',
                'type': 'control-selector',
                'label': '目标窗口实例',
                'help': '',
                'default': None,
                'options': [],
                'required': False,
                'binding': source['binding'],
                'layout': {'span': 12},
                'parameter_ui': source['parameter_ui'],
                'terminal_actions': [{
                    'action_id': 'capture-window',
                    'platforms': ['windows'],
                }],
                'constraints': {},
                'platforms': ['windows'],
                'source_type': source['value_type'],
                'type_fingerprint': source['type_fingerprint'],
            }],
        }],
    })
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(tmp_path / 'runtime')
    (tmp_path / 'runtime').mkdir()
    manager._manifest = {
        'project_id': 'project_window_capture',
        'release_id': 'release_window_capture',
        'name': 'Window capture',
    }
    manager._project = {'targets': [target], 'default_target_id': 'target_game'}
    manager._ecir = _ecir()
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.capture.window'],
    }
    monkeypatch.setattr(manager, '_host_action_reason', lambda _action, _platform: '')
    monkeypatch.setattr(manager, '_release_control_capture', lambda _state: None)
    unsaved = manager.terminal_action_availability('', None, 'target_game')
    assert unsaved['platform'] == 'windows'
    assert unsaved['blocked_reason'] == '请先保存并选择一个配置方案'
    assert unsaved['actions'][0]['action_id'] == 'capture-window'
    assert unsaved['actions'][0]['enabled'] is False
    assert unsaved['actions'][0]['disabled_reason'] == '请先保存并选择一个配置方案'
    binding = {
        'binding_version': 1,
        'binding_id': 'window_binding_player_one',
        'title': '超能世界',
        'class_name': 'Chrome_WidgetWin_1',
        'executable_name': 'WeChatAppEx.exe',
        'hwnd': 111,
        'process_id': 222,
        'process_started_at_ms': 333,
        'captured_at': '2026-09-09T00:00:00+0800',
    }
    monkeypatch.setattr(
        player_capture_session_service,
        'resolve_window_capture',
        lambda *_args, **_kwargs: copy.deepcopy(binding),
    )
    saved = manager.save_profile('', '账号一', 'target_game', {})['profile']
    destination = manager.terminal_action_availability(
        saved['profile_id'], saved['revision'], 'target_game',
    )['actions'][0]['destination']
    manager._active_capture = {
        'capture_id': 'capture_window',
        'session_id': 'session_window',
        'snapshot_id': 'snapshot_window',
        'destination': copy.deepcopy(destination),
    }

    confirmed = manager.confirm_control_capture(
        'capture_window',
        destination,
        {
            'kind': 'field_confirm',
            'snapshot_id': 'snapshot_window',
            'point': [100, 200],
            'reference_size': [1920, 1080],
        },
    )

    assert confirmed['profile']['revision'] == 2
    assert confirmed['profile']['values']['window_instance'] == binding
    effective = manager._effective_profile_target(confirmed['profile'], target)
    assert effective['window_binding'] == binding
    assert effective['window_match'] == 'exact'


def test_form_normalization_is_strict_and_never_infers_stable_identity() -> None:
    with pytest.raises(VNextWorkspaceError, match='PLY-FORM-001'):
        VNextPlayerService.normalize_form({'schema_version': 2, 'pages': []})
    missing_fingerprint = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'controls': [{
                'control_id': 'count', 'type': 'number',
                'binding': {'kind': 'project_variable', 'variable_id': 'variable_count'},
            }],
        }],
    }
    with pytest.raises(VNextWorkspaceError, match='PLY-FORM-005'):
        VNextPlayerService.normalize_form(missing_fingerprint)
    unknown_field = _form()
    unknown_field['pages'][0]['controls'][0]['parameter_name'] = 'count'
    with pytest.raises(VNextWorkspaceError, match='PLY-FORM-003'):
        VNextPlayerService.normalize_form(unknown_field)

    compact = VNextPlayerService.normalize_form(_form())
    assert compact['features'] == {'recording': False}
    with_recording = _form()
    with_recording['features'] = {'recording': True}
    assert VNextPlayerService.normalize_form(with_recording)['features'] == {'recording': True}
    invalid_feature = _form()
    invalid_feature['features'] = {'recording': 'yes'}
    with pytest.raises(VNextWorkspaceError, match='PLY-FORM-003'):
        VNextPlayerService.normalize_form(invalid_feature)


def _terminal_capture_contract() -> tuple[dict, dict]:
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_point',
        'display_name': '坐标',
        'value_type': 'point',
        'default_value': {'kind': 'point', 'x': 1, 'y': 2},
        'constraints': {},
    })
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '采集',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'point',
                'type': 'coordinate',
                'label': '坐标',
                'default': {'x': 1, 'y': 2},
                'binding': {'kind': 'project_variable', 'variable_id': 'variable_point'},
                'source_type': 'point',
                'type_fingerprint': player_type_fingerprint('point', {}),
                'platforms': ['windows'],
                'parameter_ui': {
                    'control': 'coordinate',
                    'actions': [{
                        'id': 'pick-point',
                        'capture_kind': 'point',
                        'platforms': ['windows', 'android_adb', 'android_local'],
                    }],
                },
                'terminal_actions': [{
                    'action_id': 'pick-point',
                    'platforms': ['windows'],
                }],
            }],
        }],
    })
    return ecir, form


def _terminal_color_capture_contract() -> tuple[dict, dict]:
    ecir = _ecir()
    default = {
        'color.field.red': 0,
        'color.field.green': 0,
        'color.field.blue': 0,
        'color.field.alpha': 255,
    }
    ecir['project_variables'].append({
        'variable_id': 'variable_color',
        'display_name': '目标颜色',
        'value_type': 'color',
        'default_value': copy.deepcopy(default),
        'constraints': {},
    })
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '颜色采集',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'target_color',
                'type': 'color',
                'label': '目标颜色',
                'default': copy.deepcopy(default),
                'binding': {'kind': 'project_variable', 'variable_id': 'variable_color'},
                'source_type': 'color',
                'type_fingerprint': player_type_fingerprint('color', {}),
                'platforms': ['windows'],
                'parameter_ui': {
                    'control': 'color',
                    'actions': [{
                        'id': 'pick-color',
                        'capture_kind': 'color',
                        'platforms': ['windows', 'android_adb', 'android_local'],
                    }],
                },
                'terminal_actions': [{
                    'action_id': 'pick-color',
                    'platforms': ['windows'],
                }],
            }],
        }],
    })
    return ecir, form


def _terminal_file_contract() -> tuple[dict, dict]:
    ecir = _ecir()
    ecir['supported_platforms'] = ['windows', 'android_adb', 'android_local']
    ecir['project_variables'].append({
        'variable_id': 'variable_input_file',
        'display_name': '输入文件',
        'value_type': 'file_ref<read>',
        'default_value': None,
        'constraints': {'extensions': ['.json']},
    })
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '文件选择',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'input_file',
                'type': 'file',
                'label': '输入文件',
                'binding': {
                    'kind': 'project_variable',
                    'variable_id': 'variable_input_file',
                },
                'source_type': 'file_ref<read>',
                'type_fingerprint': player_type_fingerprint(
                    'file_ref<read>', {'extensions': ['.json']},
                ),
                'platforms': ['windows', 'android_adb', 'android_local'],
                'constraints': {'extensions': ['.json']},
                'parameter_ui': {
                    'control': 'file',
                    'actions': [{
                        'id': 'choose-file-read',
                        'platforms': ['windows', 'android_adb', 'android_local'],
                    }],
                    'player_supported': True,
                },
                'terminal_actions': [{
                    'action_id': 'choose-file-read',
                    'platforms': ['windows', 'android_adb', 'android_local'],
                }],
            }],
        }],
    })
    return ecir, form


def _terminal_control_selector_contract() -> tuple[dict, dict]:
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_control_selector',
        'display_name': '登录按钮选择器',
        'value_type': 'control_selector',
        'default_value': None,
        'constraints': {},
    })
    form = VNextPlayerService.normalize_form({
        'schema_version': 3,
        'title': '控件捕获',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'control',
                'type': 'control-selector',
                'label': '登录按钮',
                'binding': {
                    'kind': 'project_variable',
                    'variable_id': 'variable_control_selector',
                },
                'source_type': 'control_selector',
                'type_fingerprint': player_type_fingerprint('control_selector', {}),
                'platforms': ['windows'],
                'parameter_ui': {
                    'control': 'control-selector',
                    'actions': [{
                        'id': 'capture-control',
                        'capture_kind': 'control',
                        'platforms': ['windows'],
                    }],
                },
                'terminal_actions': [{
                    'action_id': 'capture-control',
                    'platforms': ['windows'],
                }],
            }],
        }],
    })
    return ecir, form


def test_terminal_actions_default_off_and_require_authoritative_platform_intersection(tmp_path) -> None:
    normalized = VNextPlayerService.normalize_form(_form())
    value_controls = [
        control for page in normalized['pages'] for control in page['controls']
        if control['type'] != 'button'
    ]
    assert value_controls
    assert all(control['terminal_actions'] == [] for control in value_controls)

    ecir, form = _terminal_capture_contract()
    validate_player_form_bindings(ecir, form)
    assert player_terminal_action_closure(form) == [{
        'control_id': 'point',
        'action_id': 'pick-point',
        'platforms': ['windows'],
        'capability': 'player.capture.point',
    }]

    invalid = copy.deepcopy(form)
    invalid['pages'][0]['controls'][0]['terminal_actions'][0]['platforms'] = ['android_local']
    with pytest.raises(PlayerBindingError, match='PLY-ACTION-003'):
        validate_player_form_bindings(ecir, invalid)

    not_a_control_action = copy.deepcopy(form)
    not_a_control_action['pages'][0]['controls'][0]['terminal_actions'] = [{
        'action_id': 'capture-image', 'platforms': ['windows'],
    }]
    with pytest.raises(PlayerBindingError, match='PLY-ACTION-002'):
        validate_player_form_bindings(ecir, not_a_control_action)

    (tmp_path / 'project.json').write_text(
        json.dumps({'targets': [_target()]}, ensure_ascii=False), encoding='utf-8',
    )
    report = VNextPublisher(str(tmp_path)).report({'diagnostics': [], 'ecir': ecir}, form)
    assert report['valid'] is True, report['errors']
    assert report['player_terminal_actions'] == player_terminal_action_closure(form)
    assert report['player_terminal_capabilities'] == ['player.capture.point']


def test_terminal_actions_declare_android_floor_and_publish_can_raise_project_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert all(
        isinstance(spec.get('minimum_android_api'), int)
        and 21 <= int(spec['minimum_android_api']) <= 37
        for spec in PLAYER_TERMINAL_ACTION_SPECS.values()
    )
    ecir, form = _terminal_capture_contract()
    ecir.update({
        'target_platform': 'android_local',
        'supported_platforms': ['android_local'],
        'minimum_android_api': 21,
        'android_api_requirements': [],
    })
    form['pages'][0]['controls'][0]['terminal_actions'][0]['platforms'] = ['android_local']
    monkeypatch.setitem(PLAYER_TERMINAL_ACTION_SPECS['pick-point'], 'minimum_android_api', 24)

    projected = VNextPublisher._with_android_requirements(
        {'diagnostics': [], 'ecir': ecir}, None, form,
    )

    assert projected['ecir']['minimum_android_api'] == 24
    assert projected['ecir']['android_api_requirements'] == [{
        'kind': 'player_terminal_action',
        'action_id': 'pick-point',
        'control_id': 'point',
        'display_name': 'pick-point',
        'minimum_android_api': 24,
        'statement_ids': [],
    }]


def test_publish_revalidates_slots_and_required_action_inputs(tmp_path) -> None:
    (tmp_path / 'project.json').write_text(
        json.dumps({'targets': [_target()]}, ensure_ascii=False),
        encoding='utf-8',
    )
    publisher = VNextPublisher(str(tmp_path))
    linked = {'diagnostics': [], 'ecir': _ecir()}
    valid = publisher.report(linked, _form())
    assert valid['valid'] is True, valid['errors']

    missing = _form()
    missing['pages'][0]['controls'] = [
        control for control in missing['pages'][0]['controls']
        if control['control_id'] != 'limit'
    ]
    report = publisher.report(linked, missing)
    assert report['valid'] is False
    assert any(item['code'] == 'P2110' for item in report['errors'])

    stale = _form()
    stale['pages'][0]['controls'][2]['binding']['parameter_id'] = 'missing_parameter'
    report = publisher.report(linked, stale)
    assert report['valid'] is False
    assert any(item['code'] == 'PLY-BIND-004' for item in report['errors'])


def test_binding_contract_only_advertises_executable_schema3_surface() -> None:
    contract = player_binding_contract()
    assert contract['schema_version'] == 3
    assert {item['kind'] for item in contract['binding_kinds']} == {
        'project_variable', 'function_parameter', 'statement_parameter',
        'function_action', 'setting',
    }
    assert {item['kind'] for item in contract['unsupported']} == {
        'resource', 'target',
    }
    statement = next(
        item for item in contract['binding_kinds']
        if item['kind'] == 'statement_parameter'
    )
    assert statement['optional_fields'] == ['value_id']
    assert all(
        item['type_fingerprint'].startswith('sha256:')
        for item in contract['target_settings']
    )


def test_binding_source_catalog_is_hierarchical_and_backend_signed() -> None:
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_control',
        'display_name': '登录按钮控件',
        'value_type': 'control_selector',
        'default_value': None,
        'constraints': {},
    })
    ecir['debug_map'] = {
        'statements': {'statement_log': {'step_label': '登录阶段'}},
        'values': {},
    }
    catalog = build_player_binding_sources(ecir, targets=[_target()])
    assert catalog['schema_version'] == 3
    sources = {item['source_id']: item for item in catalog['sources']}
    variable = sources['project_variable:variable_count']
    assert variable['path'] == [{'id': 'project_variables', 'label': '项目变量'}]
    assert variable['default'] == 1
    assert variable['type_fingerprint'] == player_type_fingerprint(
        'int64', {'minimum': 0, 'maximum': 10},
    )
    control = sources['project_variable:variable_control']
    assert control['recommended_control'] == 'control-selector'
    assert control['parameter_ui']['actions'] == [{
        'id': 'capture-control',
        'capture_kind': 'control',
        'platforms': ['android_adb', 'android_local', 'windows'],
    }]
    statement_id = f'statement_parameter:function_main:statement_log:{LOG_CONTENT}'
    statement = sources[statement_id]
    assert statement['binding']['parameter_id'] == LOG_CONTENT
    assert statement['recommended_control'] == 'expression'
    assert len(statement['path']) == 4
    assert statement['path'][-1]['id'] == 'statement_log'
    assert statement['path'][-1]['label'] == '登录阶段'
    assert statement['label'].startswith('登录阶段 · ')
    assert sources['function_parameter:function_worker:parameter_limit']['required'] is True
    setting = sources['setting:target_game:target.window_title']
    assert setting['binding']['target_id'] == 'target_game'
    assert setting['default'] == 'Game'

    dynamic = _ecir()
    dynamic['functions'][0]['instructions'][0]['arguments'][LOG_CONTENT] = {
        'kind': 'reference', 'scope': 'local', 'symbol_id': 'symbol_message',
    }
    dynamic_sources = build_player_binding_sources(dynamic)['sources']
    assert not any(item['source_id'] == statement_id for item in dynamic_sources)


def test_runtime_managed_statement_parameter_is_omitted_from_catalog_but_rejected_if_forged() -> None:
    ecir = _ecir()
    instruction = ecir['functions'][0]['instructions'][0]
    instruction['arguments'][LOG_CATEGORY] = 'script'
    instruction['parameter_ids'][LOG_CATEGORY] = LOG_CATEGORY

    sources = build_player_binding_sources(ecir)['sources']

    assert any(
        item['binding'].get('parameter_id') == LOG_CONTENT
        for item in sources
        if item['kind'] == 'statement_parameter'
    )
    assert not any(
        item['binding'].get('parameter_id') == LOG_CATEGORY
        for item in sources
        if item['kind'] == 'statement_parameter'
    )

    forged = {
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'controls': [
                _value_control(
                    'runtime_category',
                    'text',
                    {
                        'kind': 'statement_parameter',
                        'function_id': 'function_main',
                        'statement_id': 'statement_log',
                        'parameter_id': LOG_CATEGORY,
                    },
                    'string',
                    {},
                ),
            ],
        }],
    }
    with pytest.raises(PlayerBindingError, match='PLY-BIND-013'):
        validate_player_form_bindings(ecir, forged)


def test_runtime_control_reference_is_not_a_persisted_player_selector() -> None:
    ecir = _ecir()
    ecir['project_variables'].append({
        'variable_id': 'variable_runtime_control',
        'display_name': '运行期控件引用',
        'value_type': 'control_ref',
        'default_value': None,
        'constraints': {},
    })
    source = next(
        item for item in build_player_binding_sources(ecir)['sources']
        if item['source_id'] == 'project_variable:variable_runtime_control'
    )
    assert source['recommended_control'] == 'expression'


def test_player_profile_save_uses_same_schema3_validation_and_is_atomic(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {'project_id': 'project_profile', 'name': 'Profile'}
    manager._project = {
        'targets': [_target()],
        'default_target_id': 'target_game',
    }
    manager._ecir = _ecir()
    manager._form = _form()

    saved = manager.save_profile(
        '', '常用方案', None,
        {'count': 3, 'limit': 4, 'message': '内容', 'window_title': 'Game 2'},
    )
    profile_id = saved['profile']['profile_id']
    assert manager.profiles()['profiles'][0]['values']['count'] == 3

    with pytest.raises(PlayerBundleError, match='PLY-BIND-007'):
        manager.save_profile(
            profile_id, '常用方案', None,
            {'count': '错误类型'},
        )
    assert manager.profiles()['profiles'][0]['values']['count'] == 3

    with pytest.raises(PlayerBundleError, match='未发布控件'):
        manager.save_profile('', '错误方案', None, {'not_published': 1})
    with pytest.raises(PlayerBundleError, match='不能保存函数按钮值'):
        manager.save_profile('', '错误方案', None, {'run_worker': True})

    captured: dict = {}

    def fake_start(ecir, **options):
        captured['ecir'] = ecir
        captured['target'] = options.get('target')
        return {'execution_id': 'execution_profile', 'status': 'running'}

    monkeypatch.setattr('core.vnext.player_bundle.vnext_runtime.start', fake_start)
    started = manager.start({
        'profile_id': profile_id,
        'profile_revision': saved['profile']['revision'],
        'player_values': {'count': 6},
        'action_control_id': 'run_worker',
    })
    assert started['execution_id'] == 'execution_profile'
    assert captured['ecir']['project_variable_overrides']['variable_count'] == 6
    assert captured['ecir']['function_arguments']['function_worker']['parameter_limit'] == 4
    assert captured['ecir']['functions'][0]['instructions'][0]['arguments'][LOG_CONTENT] == '内容'
    assert captured['target']['window_title'] == 'Game 2'
    updated = manager.save_profile(
        profile_id, '常用方案', None,
        {'count': 8, 'limit': 4, 'message': '内容', 'window_title': 'Game 2'},
        expected_revision=1,
    )['profile']
    assert updated['revision'] == 2
    with pytest.raises(PlayerBundleError, match='revision 已过期'):
        manager.save_profile(
            profile_id, '常用方案', None,
            {'count': 9, 'limit': 4, 'message': '内容', 'window_title': 'Game 2'},
            expected_revision=1,
        )
    with pytest.raises(PlayerBundleError, match='配置方案不存在'):
        manager.start({'profile_id': 'profile_missing'})


def test_player_recursive_delete_requires_per_run_server_bound_confirmation(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    authorization_root = tmp_path / 'authorized'
    target = authorization_root / 'cache'
    target.mkdir(parents=True)
    reference = windows_directory_reference(
        str(target), str(authorization_root),
        access=('read', 'list', 'delete_tree'),
        authorization_root_id='root.authorized',
    )
    contract = official_function_registry_v6.require(
        'official.directory.delete_tree'
    )
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {'project_id': 'project_dangerous', 'name': 'Dangerous'}
    manager._project = {'targets': [], 'default_target_id': None}
    manager._form = {'schema_version': 3, 'title': '运行', 'pages': []}
    manager._ecir = {
        'target_platform': 'no_target',
        'supported_platforms': ['no_target'],
        'entry_function_id': 'function.main',
        'functions': [{
            'function_id': 'function.main',
            'parameter_definitions': [],
            'instructions': [{
                'instruction_id': 'statement.delete_tree',
                'function_id': 'official.directory.delete_tree',
                'opcode': 'directory.delete_tree',
                'arguments': {
                    'official.directory.delete_tree.parameter.directory': reference,
                },
                'dangerous_author_review': {
                    'fingerprint': 'sha256:author-reviewed',
                    'contract_fingerprint': contract.fingerprint(),
                },
            }],
        }],
        'project_variables': [],
    }

    requirements = manager.dangerous_operation_requirements({})['operations']
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement['statement_id'] == 'statement.delete_tree'
    assert requirement['authorization_root_id'] == 'root.authorized'
    assert requirement['display_path'] == str(target.resolve())

    with pytest.raises(PlayerBundleError, match='明确确认'):
        manager.start({})
    with pytest.raises(PlayerBundleError, match='不属于当前运行配置'):
        manager.start({'dangerous_confirmations': [{
            'confirmation_id': 'sha256:wrong', 'confirmed': True,
        }]})

    captured: dict = {}
    def fake_start(ecir, **_options):
        captured['ecir'] = ecir
        return {'execution_id': 'run.delete', 'status': 'queued'}

    monkeypatch.setattr(
        'core.vnext.player_bundle.vnext_runtime.start', fake_start,
    )
    manager.start({'dangerous_confirmations': [{
        'confirmation_id': requirement['confirmation_id'], 'confirmed': True,
    }]})
    confirmation = captured['ecir']['dangerous_operation_confirmations'][0]
    assert confirmation == {
        'confirmed': True,
        'statement_id': 'statement.delete_tree',
        'authorization_root_id': 'root.authorized',
        'execution_config_revision': requirement['execution_config_revision'],
        'contract_fingerprint': contract.fingerprint(),
    }


def test_profile_document_migrates_once_and_never_swallows_corruption(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {'project_id': 'project_profile_migration'}
    path = manager._profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        'schema_version': 1,
        'profiles': {
            'profile_old': {
                'profile_id': 'profile_old',
                'name': '旧方案',
                'target_id': None,
                'values': {},
                'created_at': '2026-09-01T00:00:00+00:00',
                'updated_at': '2026-09-01T00:00:00+00:00',
            },
        },
    }, ensure_ascii=False), encoding='utf-8')

    migrated = manager._read_profiles()
    assert migrated['schema_version'] == 3
    assert migrated['profiles']['profile_old']['revision'] == 1
    assert migrated['profiles']['profile_old']['image_overrides'] == {}
    assert migrated['profiles']['profile_old']['recording']['enabled'] is False
    assert json.loads(path.read_text(encoding='utf-8'))['schema_version'] == 3

    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(PlayerBundleError, match='配置方案文档损坏'):
        manager._read_profiles()


def test_player_destination_revalidates_revision_and_cancel_preserves_value(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    ecir, form = _terminal_capture_contract()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {
        'project_id': 'project_capture',
        'release_id': 'release_capture',
        'name': 'Capture',
    }
    manager._project = {'targets': [_target()], 'default_target_id': 'target_game'}
    manager._ecir = ecir
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.capture.point'],
    }
    monkeypatch.setattr(manager, '_host_action_reason', lambda _action, _platform: '')
    saved = manager.save_profile(
        '', '采集方案', 'target_game', {'point': {'x': 3, 'y': 4}},
    )['profile']
    destination = {
        'product_id': 'project_capture',
        'release_id': 'release_capture',
        'profile_id': saved['profile_id'],
        'control_id': 'point',
        'action_id': 'pick-point',
        'profile_revision': 1,
        'target_id': 'target_game',
    }
    manager._active_capture = {
        'capture_id': 'player_capture_cancel',
        'session_id': 'player_session_cancel',
        'snapshot_id': 'snap_cancel',
        'destination': copy.deepcopy(destination),
    }
    cancelled = manager.cancel_control_capture(
        'player_capture_cancel', copy.deepcopy(destination),
    )
    assert cancelled['cancelled'] is True
    unchanged = manager.profiles()['profiles'][0]
    assert unchanged['revision'] == 1
    assert unchanged['values']['point'] == {'x': 3, 'y': 4}

    from core.services.player_capture_session import player_capture_session_service

    monkeypatch.setattr(
        player_capture_session_service,
        'validate_player_snapshot',
        lambda *_args, **_kwargs: {'snapshot_id': 'snap_confirm'},
    )
    manager._active_capture = {
        'capture_id': 'player_capture_confirm',
        'session_id': 'player_session_confirm',
        'snapshot_id': 'snap_confirm',
        'destination': copy.deepcopy(destination),
    }
    confirmed = manager.confirm_control_capture(
        'player_capture_confirm',
        copy.deepcopy(destination),
        {
            'kind': 'field_confirm',
            'snapshot_id': 'snap_confirm',
            'point': [9, 10],
        },
    )
    assert confirmed['profile']['revision'] == 2
    assert confirmed['value'] == {'x': 9, 'y': 10}
    stale = manager.terminal_action_availability(
        saved['profile_id'], 1, 'target_game',
    )
    assert 'revision 已过期' in stale['blocked_reason']


def test_player_color_capture_is_signed_and_commits_canonical_rgba(
    tmp_path,
    monkeypatch,
) -> None:
    from core.services.player_capture_session import player_capture_session_service

    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    ecir, form = _terminal_color_capture_contract()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {
        'project_id': 'project_color_capture',
        'release_id': 'release_color_capture',
        'name': 'Color capture',
    }
    manager._project = {'targets': [_target()], 'default_target_id': 'target_game'}
    manager._ecir = ecir
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.capture.color'],
    }
    monkeypatch.setattr(manager, '_host_action_reason', lambda _action, _platform: '')
    monkeypatch.setattr(manager, '_release_control_capture', lambda _state: None)
    monkeypatch.setattr(
        player_capture_session_service,
        'validate_player_snapshot',
        lambda *_args, **_kwargs: {'snapshot_id': 'snapshot_color'},
    )

    saved = manager.save_profile('', '颜色方案', 'target_game', {})['profile']
    availability = manager.terminal_action_availability(
        saved['profile_id'], 1, 'target_game',
    )
    assert availability['actions'][0]['capability'] == 'player.capture.color'
    destination = availability['actions'][0]['destination']
    manager._active_capture = {
        'capture_id': 'player_capture_color',
        'session_id': 'player_session_color',
        'snapshot_id': 'snapshot_color',
        'destination': copy.deepcopy(destination),
    }

    confirmed = manager.confirm_control_capture(
        'player_capture_color', destination, {
            'kind': 'field_confirm',
            'snapshot_id': 'snapshot_color',
            'color': {'red': 97, 'green': 98, 'blue': 100, 'alpha': 255},
        },
    )

    assert confirmed['profile']['revision'] == 2
    assert confirmed['value'] == {
        'color.field.red': 97,
        'color.field.green': 98,
        'color.field.blue': 100,
        'color.field.alpha': 255,
    }


def test_player_control_capture_persists_selector_not_runtime_reference(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    ecir, form = _terminal_control_selector_contract()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {
        'project_id': 'project_control_capture',
        'release_id': 'release_control_capture',
        'name': 'Control capture',
    }
    manager._project = {'targets': [_target()], 'default_target_id': 'target_game'}
    manager._ecir = ecir
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.capture.control'],
    }
    monkeypatch.setattr(manager, '_host_action_reason', lambda _action, _platform: '')
    monkeypatch.setattr(manager, '_release_control_capture', lambda _state: None)
    saved = manager.save_profile('', '控件方案', 'target_game', {})['profile']
    destination = manager.terminal_action_availability(
        saved['profile_id'], 1, 'target_game',
    )['actions'][0]['destination']
    manager._active_capture = {
        'capture_id': 'player_capture_control',
        'session_id': 'player_session_control',
        'snapshot_id': 'snapshot_windows',
        'destination': copy.deepcopy(destination),
    }

    selector = {
        'control_selector.field.schema_version': 1,
        'control_selector.field.provider': 'windows_uia',
        'control_selector.field.target_id': 'target_game',
        'control_selector.field.name': '登录',
        'control_selector.field.automation_id': 'login',
        'control_selector.field.class_name': 'Button',
        'control_selector.field.control_type': 'button',
        'control_selector.field.rect': {
            'kind': 'rect', 'x': 20, 'y': 30, 'width': 100, 'height': 40,
        },
        'control_selector.field.ancestor_path': [{
            'name': '游戏', 'automation_id': '', 'class_name': 'Window', 'control_type': 'window',
        }],
    }
    confirmed = manager.confirm_control_capture(
        'player_capture_control', destination, {
            'kind': 'field_confirm',
            'snapshot_id': 'snapshot_windows',
            'selector': selector,
        },
    )

    assert confirmed['profile']['revision'] == 2
    assert confirmed['value']['control_selector.field.automation_id'] == 'login'
    assert confirmed['value']['control_selector.field.rect'] == {
        'kind': 'rect', 'x': 20, 'y': 30, 'width': 100, 'height': 40,
    }
    assert confirmed['value']['control_selector.field.ancestor_path'][0]['name'] == '游戏'
    assert 'reference_id' not in confirmed['value']


def test_player_adb_control_capture_maps_frozen_frame_to_uiautomator_tree(
    tmp_path,
    monkeypatch,
) -> None:
    from core.vnext.android_control_v6 import parse_uiautomator_xml
    from core.services.player_capture_session import player_capture_session_service

    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    ecir, form = _terminal_control_selector_contract()
    ecir['supported_platforms'] = ['android_adb']
    adb_target = {
        'target_id': 'target_phone', 'name': '测试手机', 'type': 'android_adb',
        'device_serial': 'serial-test', 'work_area': {'mode': 'full'},
    }
    ecir['targets'] = [copy.deepcopy(adb_target)]
    control = form['pages'][0]['controls'][0]
    control['platforms'] = ['android_adb']
    control['parameter_ui']['actions'][0]['platforms'] = ['android_adb']
    control['terminal_actions'][0]['platforms'] = ['android_adb']

    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {
        'project_id': 'project_control_capture',
        'release_id': 'release_control_capture',
        'name': 'Control capture',
    }
    manager._project = {
        'targets': [copy.deepcopy(adb_target)],
        'default_target_id': 'target_phone',
    }
    manager._ecir = ecir
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.capture.control'],
    }
    monkeypatch.setattr(manager, '_host_action_reason', lambda _action, _platform: '')
    monkeypatch.setattr(manager, '_release_control_capture', lambda _state: None)
    monkeypatch.setattr(
        player_capture_session_service,
        'validate_player_snapshot',
        lambda *_args, **_kwargs: {'snapshot_id': 'snapshot_adb'},
    )

    saved = manager.save_profile('', 'ADB 控件方案', 'target_phone', {})['profile']
    destination = manager.terminal_action_availability(
        saved['profile_id'], 1, 'target_phone',
    )['actions'][0]['destination']
    semantic_snapshot = parse_uiautomator_xml('''
        <hierarchy rotation="0">
          <node index="0" class="android.widget.FrameLayout" package="demo" bounds="[0,0][1080,2340]">
            <node index="0" text="登录" resource-id="demo:id/login" class="android.widget.Button"
              package="demo" clickable="true" enabled="true" bounds="[432,936][648,1170]" />
          </node>
        </hierarchy>
    ''')
    manager._active_capture = {
        'capture_id': 'player_capture_adb',
        'session_id': 'player_session_adb',
        'snapshot_id': 'snapshot_adb',
        'reference_size': [540, 1170],
        'semantic_snapshot': semantic_snapshot,
        'destination': copy.deepcopy(destination),
    }

    from core.vnext.android_control_v6 import control_candidates_at
    selector = control_candidates_at(
        semantic_snapshot, 270, 526, 'target_phone', 'android_uiautomator',
        source_size=(540, 1170),
    )[0]['selector']
    confirmed = manager.confirm_control_capture(
        'player_capture_adb', destination, {
            'kind': 'field_confirm',
            'snapshot_id': 'snapshot_adb',
            'selector': selector,
        },
    )

    assert confirmed['profile']['revision'] == 2
    assert confirmed['value']['control_selector.field.provider'] == 'android_uiautomator'
    assert confirmed['value']['control_selector.field.target_id'] == 'target_phone'
    assert confirmed['value']['control_selector.field.resource_id'] == 'demo:id/login'
    assert confirmed['value']['control_selector.field.rect'] == {
        'kind': 'rect', 'x': 432, 'y': 936, 'width': 216, 'height': 234,
    }


def test_player_abandoned_capture_expires_without_changing_profile_values(monkeypatch) -> None:
    manager = VNextPlayerBundleManager()
    released: list[dict[str, object]] = []
    manager._active_capture = {
        'capture_id': 'player_capture_abandoned',
        'session_id': 'player_session_abandoned',
        'started_at': 100.0,
        'destination': {'control_id': 'point'},
    }
    monkeypatch.setattr(manager, '_release_control_capture', released.append)

    assert manager._expire_stale_control_capture(
        now=100.0 + manager.CONTROL_CAPTURE_TTL_SECONDS + 1,
    ) is True
    assert manager._active_capture is None
    assert released == [{
        'capture_id': 'player_capture_abandoned',
        'session_id': 'player_session_abandoned',
        'started_at': 100.0,
        'destination': {'control_id': 'point'},
    }]


def test_player_file_picker_is_available_without_operation_target_and_commits_atomically(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'player-data'))
    runtime_root = tmp_path / 'runtime'
    runtime_root.mkdir()
    selected = tmp_path / 'selected.json'
    selected.write_text('{"ready": true}', encoding='utf-8')
    ecir, form = _terminal_file_contract()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime_root)
    manager._manifest = {
        'project_id': 'project_file_capture',
        'release_id': 'release_file_capture',
        'name': 'File capture',
    }
    manager._project = {'targets': [], 'default_target_id': None}
    manager._ecir = ecir
    manager._form = copy.deepcopy(form)
    manager._base_form = copy.deepcopy(form)
    manager._publish_report = {
        'valid': True,
        'player_terminal_actions': player_terminal_action_closure(form),
        'player_terminal_capabilities': ['player.file.choose_read'],
    }
    saved = manager.save_profile('', '无目标文件方案', '', {})['profile']
    available = manager.terminal_action_availability(saved['profile_id'], 1, '')
    assert available['platform'] == 'windows'
    assert [(item['action_id'], item['enabled']) for item in available['actions']] == [
        ('choose-file-read', True),
    ]
    destination = available['actions'][0]['destination']
    assert destination['target_id'] == ''

    from core.services.player_native_dialogs import player_native_dialog_service

    monkeypatch.setattr(
        player_native_dialog_service,
        'choose',
        lambda *_args, **_kwargs: {
            'kind': 'file',
            'display_name': selected.name,
            'access': ['read'],
            'reference': {
                'kind': 'file_ref',
                'platform': 'windows',
                'source': 'player_system_picker',
                'display_name': selected.name,
                'path': str(selected.resolve()),
                'authorization_root': str(selected.parent.resolve()),
                'authorization_root_id': 'windows:test-root',
                'access': ['read'],
            },
        },
    )
    started = manager.start_control_capture(destination)
    assert started['state'] == 'awaiting_confirmation'
    assert started['candidate']['display_name'] == selected.name
    assert 'path' not in started['candidate']
    assert manager.profiles()['profiles'][0]['revision'] == 1
    assert 'input_file' not in manager.profiles()['profiles'][0]['values']

    confirmed = manager.confirm_control_capture(
        started['capture_id'], destination, {
            'kind': 'native-reference',
            'candidate_id': started['candidate']['candidate_id'],
        },
    )
    assert confirmed['profile']['revision'] == 2
    assert confirmed['value']['kind'] == 'file_ref'
    assert confirmed['value']['path'] == str(selected.resolve())

    destination = {
        **destination,
        'profile_revision': 2,
    }
    monkeypatch.setattr(player_native_dialog_service, 'choose', lambda *_args, **_kwargs: None)
    cancelled = manager.start_control_capture(destination)
    assert cancelled['cancelled'] is True
    assert manager.profiles()['profiles'][0]['revision'] == 2
    assert manager.profiles()['profiles'][0]['values']['input_file']['path'] == str(selected.resolve())


def test_new_workspace_uses_schema3_and_service_catalog_can_roundtrip(tmp_path) -> None:
    manager = VNextWorkspaceManager()
    opened = manager.open(
        str(tmp_path / 'schema3-workspace'),
        initialize=True,
        project_name='Schema3',
    )
    workspace = opened['workspace']
    workspace_id = workspace['workspace_id']
    generation = workspace['generation']
    assert manager.player_form(workspace_id, generation) == {
        'schema_version': 3,
        'title': '脚本运行器',
        'icon_asset_id': '',
        'features': {'recording': False},
        'pages': [],
    }
    catalog = manager._player.binding_sources(workspace_id, generation)
    assert catalog['available'] is True
    action = next(item for item in catalog['sources'] if item['kind'] == 'function_action')
    saved = manager.save_player_form(workspace_id, generation, {
        'schema_version': 3,
        'title': '运行',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'run_main',
                'type': 'button',
                'label': '运行主程序',
                'binding': action['binding'],
            }],
        }],
    })
    assert saved['pages'][0]['controls'][0]['binding'] == action['binding']
    preview = manager._player.preview_plan(
        workspace_id,
        generation,
        values={},
        action_control_id='run_main',
    )
    assert preview['valid'] is True
    assert preview['execution_plan']['entry_function_id'] == action['binding']['function_id']
    assert preview['target'] is None


def test_incomplete_program_returns_unavailable_binding_catalog_without_conflict(tmp_path) -> None:
    manager = VNextWorkspaceManager()
    opened = manager.open(
        str(tmp_path / 'schema3-incomplete'), initialize=True,
        project_name='Schema3 未完成项目',
    )
    workspace = opened['workspace']
    function_id = opened['programs'][0]['function_id']
    loaded = manager.load_program(workspace['workspace_id'], workspace['generation'], function_id)
    manager.apply_program_command(
        workspace['workspace_id'], workspace['generation'], function_id, loaded['revision'],
        {
            'kind': 'insert_call',
            'function_id': 'official.image.find',
            'arguments': {},
            'location': {'block': 'root'},
        },
    )

    catalog = manager._player.binding_sources(workspace['workspace_id'], workspace['generation'])

    assert catalog['schema_version'] == 3
    assert catalog['available'] is False
    assert catalog['sources'] == []
    assert '必填' in catalog['unavailable_reason']
    assert catalog['diagnostics']


def test_bundle_loader_revalidates_schema3_stable_bindings(tmp_path) -> None:
    manager = VNextWorkspaceManager()
    opened = manager.open(
        str(tmp_path / 'bundle-contract-workspace'),
        initialize=True,
        project_name='Bundle Contract',
    )
    workspace = opened['workspace']
    workspace_id = workspace['workspace_id']
    generation = workspace['generation']
    entry_function_id = opened['inspection']['entry_function_id']
    manager.save_player_form(workspace_id, generation, {
        'schema_version': 3,
        'title': 'Bundle Contract',
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'run_main',
                'type': 'button',
                'label': '运行主程序',
                'binding': {
                    'kind': 'function_action',
                    'function_id': entry_function_id,
                },
            }],
        }],
    })
    built = manager.publish_player(workspace_id, generation)

    tampered_path = tmp_path / 'tampered-player-binding.ecplayer'
    with (
        zipfile.ZipFile(built['path'], 'r') as source,
        zipfile.ZipFile(
            tampered_path,
            'w',
            compression=zipfile.ZIP_DEFLATED,
        ) as destination,
    ):
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == 'player/form.json':
                form = json.loads(content)
                form['pages'][0]['controls'][0]['binding']['function_id'] = (
                    'function_missing'
                )
                content = json.dumps(form, ensure_ascii=False).encode('utf-8')
            destination.writestr(info, content)

    bundle = VNextPlayerBundleManager()
    with pytest.raises(PlayerBundleError, match='校验失败'):
        bundle.load(str(tampered_path))
