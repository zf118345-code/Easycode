from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.player_bindings import player_type_fingerprint
from core.vnext.player_bundle import PlayerBundleError, VNextPlayerBundleManager
from core.vnext.runtime import RuntimeFailure
from core.vnext.target_runtime import AndroidAdbTargetDriver
from core.vnext.target_service import TargetConflictError
from core.vnext.workspace import VNextWorkspaceManager

PIXEL_PNG = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=='
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> tuple[dict, dict[str, str]]:
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project),
        'initialize': True,
        'project_name': '目标配置纵向测试',
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    workspace = payload['workspace']
    return payload, {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def _window_target(target_id: str = 'target_game') -> dict:
    return {
        'target_id': target_id,
        'name': '游戏窗口',
        'type': 'windows',
        'window_title': 'EasyCode Target Test',
        'window_match': 'exact',
        'work_area': {'mode': 'client'},
        'allow_physical_fallback': True,
    }


def _save_targets(
    client: TestClient,
    headers: dict[str, str],
    revision: str,
    targets: list[dict],
    default_target_id: str | None,
):
    return client.put('/api/vnext/targets', headers=headers, json={
        'expected_revision': revision,
        'targets': targets,
        'default_target_id': default_target_id,
    })


def test_adb_control_resolve_uses_explicit_target_and_frozen_frame_size(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from core.vnext.android_control_v6 import AdbUiAutomatorAdapter

    client = _client()
    opened, headers = _open(client, tmp_path / 'control-resolve')
    target = {
        'target_id': 'target_adb', 'name': 'ADB 手机',
        'type': 'android_adb', 'device_serial': 'serial-123',
    }
    saved = _save_targets(
        client, headers, opened['revision'], [target], 'target_adb',
    )
    assert saved.status_code == 200, saved.text
    calls: list[tuple[object, ...]] = []

    def capture_candidates_at(self, x, y, target_id, source_size=None):
        calls.append((self.device_serial, x, y, target_id, source_size))
        return [{
            'label': '登录按钮',
            'role': 'button',
            'frame_rect': [200, 500, 140, 80],
            'selector': {
            'control_selector.field.provider': 'android_uiautomator',
            'control_selector.field.target_id': target_id,
            'control_selector.field.resource_id': 'demo:id/login',
            },
        }]

    monkeypatch.setattr(AdbUiAutomatorAdapter, 'capture_candidates_at', capture_candidates_at)
    response = client.post('/api/vnext/capture/control/resolve', headers=headers, json={
        'target_id': 'target_adb',
        'point': [270, 585],
        'reference_size': [540, 1170],
    })
    assert response.status_code == 200, response.text
    assert calls == [('serial-123', 270, 585, 'target_adb', (540, 1170))]
    assert response.json()['candidates'][0]['selector']['control_selector.field.resource_id'] == 'demo:id/login'

    missing_size = client.post('/api/vnext/capture/control/resolve', headers=headers, json={
        'target_id': 'target_adb', 'point': [270, 585],
    })
    assert missing_size.status_code == 422


def test_target_bootstrap_crud_revision_and_workspace_headers(tmp_path: Path) -> None:
    client = _client()
    opened, headers = _open(client, tmp_path / 'target-crud')
    assert opened['schema_version'] == 1
    assert opened['targets'] == []
    assert opened['default_target_id'] is None
    assert opened['revision'].startswith('sha256:')

    assert client.get('/api/vnext/targets').status_code == 422
    initial = client.get('/api/vnext/targets', headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()['revision'] == opened['revision']

    unknown_capture_target = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image',
        'file_name': 'unknown.png',
        'content_base64': PIXEL_PNG,
        'capture': {'target_id': 'target_missing', 'platform': 'windows'},
    })
    assert unknown_capture_target.status_code == 404
    assert unknown_capture_target.json()['detail']['code'] == 'target_not_found'
    unknown_player_target = client.put('/api/vnext/player/form', headers=headers, json={
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'unknown_target',
                'type': 'text',
                'label': '目标',
                'source_type': 'string',
                'type_fingerprint': player_type_fingerprint(
                    'string', {'max_length': 512},
                ),
                'binding': {
                    'kind': 'setting',
                    'setting_id': 'target.window_title',
                    'target_id': 'target_missing',
                },
            }],
        }],
    })
    assert unknown_player_target.status_code == 409
    assert 'PLY-BIND-004' in unknown_player_target.json()['detail']['message']

    targets = [
        _window_target(),
        {
            'target_id': 'target_desktop',
            'name': '全屏幕',
            'type': 'windows',
            'window_title': '',
            'window_match': 'contains',
            'work_area': {'mode': 'desktop'},
            'allow_physical_fallback': True,
        },
        {
            'target_id': 'target_android_adb',
            'name': '雷电模拟器',
            'type': 'android_adb',
            'device_serial': 'emulator-5554',
        },
        {
            'target_id': 'target_android_local',
            'name': '当前手机',
            'type': 'android_local',
        },
    ]
    saved = _save_targets(
        client, headers, opened['revision'], targets, 'target_game',
    )
    assert saved.status_code == 200, saved.text
    saved_payload = saved.json()
    assert saved_payload['default_target_id'] == 'target_game'
    assert saved_payload['targets'][2]['device_serial'] == 'emulator-5554'
    assert saved_payload['revision'] != opened['revision']
    active = client.get('/api/vnext/workspaces/active')
    assert active.status_code == 200, active.text
    assert active.json()['revision'] == saved_payload['revision']
    assert active.json()['targets'] == saved_payload['targets']

    stale = _save_targets(
        client, headers, opened['revision'], targets, 'target_game',
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'target_revision_conflict'
    assert stale.json()['detail']['diagnostics'] == [{
        'expected_revision': opened['revision'],
        'actual_revision': saved_payload['revision'],
    }]

    rebound_targets = json.loads(json.dumps(targets))
    rebound_targets[2]['device_serial'] = 'emulator-5556'
    rebound = _save_targets(
        client,
        headers,
        saved_payload['revision'],
        rebound_targets,
        'target_game',
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()['targets'][2]['target_id'] == 'target_android_adb'
    assert rebound.json()['targets'][2]['device_serial'] == 'emulator-5556'

    changed_type = json.loads(json.dumps(rebound_targets))
    changed_type[0] = {
        'target_id': 'target_game',
        'name': '游戏窗口',
        'type': 'android_adb',
        'device_serial': 'emulator-5558',
    }
    rejected_type_change = _save_targets(
        client,
        headers,
        rebound.json()['revision'],
        changed_type,
        'target_game',
    )
    assert rejected_type_change.status_code == 422
    assert rejected_type_change.json()['detail']['code'] == (
        'target_configuration_invalid'
    )

    missing = client.post(
        f"/api/vnext/programs/{opened['inspection']['entry_function_id']}/run",
        headers=headers,
        json={'target_id': 'target_missing'},
    )
    assert missing.status_code == 404
    assert missing.json()['detail']['code'] == 'target_not_found'


@pytest.mark.parametrize(
    'targets,default_target_id',
    [
        ([_window_target('target_one'), _window_target('target_one')], 'target_one'),
        (
            [
                _window_target('target_one'),
                {**_window_target('target_two'), 'name': '游戏窗口'},
            ],
            'target_one',
        ),
        ([_window_target()], 'target_missing'),
        (
            [
                {
                    'target_id': 'target_local_one',
                    'name': '当前手机一',
                    'type': 'android_local',
                },
                {
                    'target_id': 'target_local_two',
                    'name': '当前手机二',
                    'type': 'android_local',
                },
            ],
            'target_local_one',
        ),
    ],
)
def test_target_registry_rejects_duplicate_identity_and_dangling_default(
    tmp_path: Path,
    targets: list[dict],
    default_target_id: str,
) -> None:
    client = _client()
    opened, headers = _open(client, tmp_path / default_target_id)
    response = _save_targets(
        client, headers, opened['revision'], targets, default_target_id,
    )
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'target_configuration_invalid'


@pytest.mark.parametrize(
    'target',
    [
        {
            **_window_target(),
            'window_match': 'regex',
            'window_title': '[',
        },
        {
            **_window_target(),
            'work_area': {'mode': 'region', 'region': [0, 0, 0, 100]},
        },
        {
            'target_id': 'target_adb',
            'name': 'ADB',
            'type': 'android_adb',
            'device_serial': '   ',
        },
        {
            'target_id': 'target_local',
            'name': '本机',
            'type': 'android_local',
            'device_serial': 'must-not-be-accepted',
        },
        {
            **_window_target(),
            'name': '   ',
        },
        {
            **_window_target(),
            'window_title': '',
            'work_area': {'mode': 'desktop'},
            'allow_physical_fallback': False,
        },
    ],
)
def test_target_http_contract_rejects_invalid_selector_binding_and_extra_fields(
    tmp_path: Path,
    target: dict,
) -> None:
    client = _client()
    opened, headers = _open(client, tmp_path / target['target_id'])
    response = _save_targets(
        client, headers, opened['revision'], [target], target['target_id'],
    )
    assert response.status_code == 422


def test_target_delete_reports_program_variable_resource_and_player_references(
    tmp_path: Path,
) -> None:
    client = _client()
    opened, headers = _open(client, tmp_path / 'target-references')
    function_id = opened['inspection']['entry_function_id']
    saved = _save_targets(
        client,
        headers,
        opened['revision'],
        [_window_target()],
        'target_game',
    )
    assert saved.status_code == 200, saved.text
    target_revision = saved.json()['revision']

    program = client.get(f'/api/vnext/programs/{function_id}', headers=headers).json()
    inserted = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': program['revision'],
            'command': {
                'kind': 'insert_target_scope',
                'target': {
                    'value_id': 'value_target_game',
                    'kind': 'target_ref',
                    'target_id': 'target_game',
                },
            },
        },
    )
    assert inserted.status_code == 200, inserted.text
    statement_id = inserted.json()['selected_statement_id']

    compiled = client.post(
        f'/api/vnext/programs/{function_id}/compile',
        headers=headers,
        json={'target_platform': 'windows'},
    )
    assert compiled.status_code == 200, compiled.text
    compiled_payload = compiled.json()
    assert compiled_payload['valid'] is True, compiled_payload['diagnostics']
    assert compiled_payload['ecir']['default_target_id'] == 'target_game'
    assert compiled_payload['ecir']['targets'] == [_window_target()]

    variables = client.get('/api/vnext/project-variables', headers=headers).json()
    variable = client.post('/api/vnext/project-variables', headers=headers, json={
        'expected_revision': variables['revision'],
        'display_name': '备用目标',
        'value_type': 'target_ref',
        'default_value': {
            'value_id': 'value_default_target',
            'kind': 'target_ref',
            'target_id': 'target_game',
        },
    })
    assert variable.status_code == 200, variable.text

    asset = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image',
        'file_name': 'target.png',
        'display_name': '目标截图',
        'content_base64': PIXEL_PNG,
        'source': 'capture',
        'capture': {
            'platform': 'windows',
            'target_id': 'target_game',
            'reference_size': [1920, 1080],
        },
    })
    assert asset.status_code == 200, asset.text
    asset_id = asset.json()['asset']['asset_id']

    player_form = client.put('/api/vnext/player/form', headers=headers, json={
        'schema_version': 3,
        'title': '目标设置',
        'features': {'recording': True},
        'pages': [{
            'page_id': 'main',
            'title': '运行',
            'controls': [{
                'control_id': 'window_title',
                'type': 'text',
                'label': '窗口标题',
                'default': 'EasyCode Target Test',
                'source_type': 'string',
                'type_fingerprint': player_type_fingerprint(
                    'string', {'max_length': 512},
                ),
                'binding': {
                    'kind': 'setting',
                    'setting_id': 'target.window_title',
                    'target_id': 'target_game',
                },
            }],
        }],
    })
    assert player_form.status_code == 200, player_form.text
    assert player_form.json()['features'] == {'recording': True}

    references = client.get(
        '/api/vnext/targets/target_game/references', headers=headers,
    )
    assert references.status_code == 200, references.text
    found = references.json()['references']
    assert any(
        item['kind'] == 'program_value'
        and item['statement_id'] == statement_id
        and item['value_id'] == 'value_target_game'
        for item in found
    )
    assert any(item['kind'] == 'project_variable_default' for item in found)
    assert any(
        item['kind'] == 'resource'
        and item['path'] == 'assets/registry.json'
        for item in found
    )
    assert any(
        item['kind'] == 'player_form'
        and item['path'] == 'player/form.json'
        for item in found
    )

    blocked = _save_targets(client, headers, target_revision, [], None)
    assert blocked.status_code == 409
    assert blocked.json()['detail']['code'] == 'target_referenced'
    assert len(blocked.json()['detail']['diagnostics']) >= 4

    deleted_statement = client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={
            'expected_revision': inserted.json()['revision'],
            'command': {
                'kind': 'delete_statement',
                'statement_id': statement_id,
            },
        },
    )
    assert deleted_statement.status_code == 200, deleted_statement.text
    deleted_variable = client.request(
        'DELETE',
        f"/api/vnext/project-variables/{variable.json()['selected_variable_id']}",
        headers=headers,
        json={'expected_revision': variable.json()['revision']},
    )
    assert deleted_variable.status_code == 200, deleted_variable.text
    deleted_asset = client.delete(f'/api/vnext/assets/{asset_id}', headers=headers)
    assert deleted_asset.status_code == 200, deleted_asset.text
    cleared_form = client.put('/api/vnext/player/form', headers=headers, json={
        'schema_version': 3,
        'title': '脚本运行器',
        'pages': [],
    })
    assert cleared_form.status_code == 200, cleared_form.text

    removed = _save_targets(client, headers, target_revision, [], None)
    assert removed.status_code == 200, removed.text
    assert removed.json()['targets'] == []
    assert json.loads(
        (tmp_path / 'target-references' / 'project.json').read_text(encoding='utf-8')
    )['targets'] == []


def test_target_service_never_uses_global_active_workspace_or_guesses_adb(
    tmp_path: Path,
) -> None:
    manager = VNextWorkspaceManager()
    first = manager.open(str(tmp_path / 'workspace-one'), initialize=True)['workspace']
    manager.open(str(tmp_path / 'workspace-two'), initialize=True)

    with pytest.raises(Exception, match='工作区|项目已切换|身份'):
        manager.target_configuration(first['workspace_id'], first['generation'])

    with pytest.raises(RuntimeFailure) as error:
        AndroidAdbTargetDriver(str(tmp_path), {
            'target_id': 'target_adb',
            'name': 'ADB',
            'type': 'android_adb',
            'device_serial': '',
        })
    assert error.value.error_id == 'target.adb_rebind_required'


def test_target_commit_rechecks_external_edits_and_preserves_unrelated_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = VNextWorkspaceManager()
    project_path = tmp_path / 'target-atomic'
    opened = manager.open(str(project_path), initialize=True)
    workspace = opened['workspace']
    saved = manager.save_targets(
        workspace['workspace_id'],
        workspace['generation'],
        [_window_target()],
        'target_game',
        expected_revision=opened['revision'],
    )
    project_file = project_path / 'project.json'

    def change_target_during_reference_scan(*_args, **_kwargs):
        project = json.loads(project_file.read_text(encoding='utf-8'))
        project['targets'][0]['window_title'] = 'Externally Changed Target'
        project_file.write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        return []

    monkeypatch.setattr(
        manager._targets,
        'references',
        change_target_during_reference_scan,
    )
    with pytest.raises(TargetConflictError):
        manager.save_targets(
            workspace['workspace_id'],
            workspace['generation'],
            [],
            None,
            expected_revision=saved['revision'],
        )
    after_conflict = manager.target_configuration(
        workspace['workspace_id'], workspace['generation'],
    )
    assert after_conflict['targets'][0]['window_title'] == 'Externally Changed Target'

    def change_name_during_reference_scan(*_args, **_kwargs):
        project = json.loads(project_file.read_text(encoding='utf-8'))
        project['name'] = '外部重命名后仍保留'
        project_file.write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        return []

    monkeypatch.setattr(
        manager._targets,
        'references',
        change_name_during_reference_scan,
    )
    removed = manager.save_targets(
        workspace['workspace_id'],
        workspace['generation'],
        [],
        None,
        expected_revision=after_conflict['revision'],
    )
    assert removed['targets'] == []
    assert json.loads(project_file.read_text(encoding='utf-8'))['name'] == (
        '外部重命名后仍保留'
    )


def test_published_player_contains_and_validates_target_contract(tmp_path: Path) -> None:
    manager = VNextWorkspaceManager()
    opened = manager.open(str(tmp_path / 'target-player'), initialize=True)
    workspace = opened['workspace']
    saved = manager.save_targets(
        workspace['workspace_id'],
        workspace['generation'],
        [_window_target()],
        'target_game',
        expected_revision=opened['revision'],
    )
    built = manager.publish_player(workspace['workspace_id'], workspace['generation'])
    with zipfile.ZipFile(built['path']) as archive:
        runtime_project = json.loads(archive.read('runtime/project.json'))
    assert runtime_project['targets_schema_version'] == 1
    assert runtime_project['targets'] == saved['targets']
    assert runtime_project['default_target_id'] == 'target_game'
    assert runtime_project['target_configuration_revision'] == saved['revision']

    tampered_path = tmp_path / 'tampered-target.ecplayer'
    with (
        zipfile.ZipFile(built['path'], 'r') as source,
        zipfile.ZipFile(tampered_path, 'w', compression=zipfile.ZIP_DEFLATED) as destination,
    ):
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == 'runtime/project.json':
                tampered = json.loads(content)
                tampered['targets'][0]['window_title'] = 'Tampered Target'
                content = json.dumps(tampered, ensure_ascii=False).encode('utf-8')
            destination.writestr(info, content)
    bundle = VNextPlayerBundleManager()
    with pytest.raises(PlayerBundleError, match='校验失败'):
        bundle.load(str(tampered_path))


def test_target_configuration_corruption_is_never_silently_repaired(
    tmp_path: Path,
) -> None:
    manager = VNextWorkspaceManager()
    project_path = tmp_path / 'target-corrupt'
    opened = manager.open(str(project_path), initialize=True)
    workspace = opened['workspace']
    project_file = project_path / 'project.json'
    project = json.loads(project_file.read_text(encoding='utf-8'))
    project['default_target_id'] = 'target_missing'
    project_file.write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    assert manager.inspect(str(project_path))['status'] == 'invalid'
    with pytest.raises(Exception, match='目标配置损坏'):
        manager.target_configuration(workspace['workspace_id'], workspace['generation'])


def test_active_workspace_reports_external_target_corruption_with_stable_error(
    tmp_path: Path,
) -> None:
    client = _client()
    project_path = tmp_path / 'target-active-corrupt'
    _opened, _headers = _open(client, project_path)
    project_file = project_path / 'project.json'
    project = json.loads(project_file.read_text(encoding='utf-8'))
    project['default_target_id'] = 'target_missing'
    project_file.write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    active = client.get('/api/vnext/workspaces/active')
    assert active.status_code == 409, active.text
    assert active.json()['detail']['code'] == 'target_configuration_corrupt'
