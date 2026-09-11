import json
import zipfile

from fastapi import BackgroundTasks

from core.services.execution_service import ExecutionService
from core.services.player_service import PlayerService


def _prepare_player(monkeypatch, tmp_path):
    schema = {
        'schema_version': 3,
        'groups': [{'group_title': '账号', 'fields': [
            {'target': '$var.username', 'label': '用户名', 'ui_type': 'str', 'required': True, 'default': ''},
            {'target': '$var.password', 'label': '密码', 'ui_type': 'secret', 'required': True, 'default': ''},
        ]}],
    }
    config = {'vars': {'username': 'demo', 'password': 'top-secret'}, 'ctx': {}}
    PlayerService._MEMORY_CACHE.update({
        'blueprint': {'project_name': 'player', 'variables': {}, 'tasks': [{'task_id': 'main', 'task_name': 'main', 'nodes': []}], 'edges': []},
        'form_schema': schema,
        'user_config': config,
        'templates': {},
        'context': {},
        'license_info': {},
        'bundle_hash': 'abc123',
        'config_path': '',
    })
    PlayerService._instances = {}
    PlayerService._ensure_instance('instance-1')['user_config'] = config
    monkeypatch.setattr(PlayerService, '_runtime_root', classmethod(lambda cls: str(tmp_path)))
    return schema, config


def test_profiles_are_named_and_instance_scoped(monkeypatch, tmp_path):
    _, config = _prepare_player(monkeypatch, tmp_path)

    PlayerService.save_profile('测试服', config)
    profile_text = (tmp_path / 'profiles.json').read_text(encoding='utf-8')
    applied = PlayerService.apply_profile('测试服', 'instance-2')

    assert PlayerService.list_profiles()[0]['name'] == '测试服'
    assert applied['user_config']['vars']['username'] == 'demo'
    assert PlayerService._instances['instance-2']['user_config']['vars']['password'] == 'top-secret'
    assert 'top-secret' not in profile_text
    assert 'dpapi:' in profile_text or 'fernet:' in profile_text
    PlayerService.delete_profile('测试服')
    assert PlayerService.list_profiles() == []


def test_diagnostic_package_redacts_secrets(monkeypatch, tmp_path):
    _prepare_player(monkeypatch, tmp_path)
    PlayerService._set_state('instance-1', 'error', 'token=top-secret', execution_id='exec-secret')
    monkeypatch.setattr(
        ExecutionService,
        'get_execution_status',
        staticmethod(lambda _execution_id: {
            'status': {'status': 'error', 'message': 'password top-secret'},
            'logs': [{'message': 'request token=top-secret'}],
        }),
    )
    output = PlayerService.create_diagnostic_package('instance-1')

    with zipfile.ZipFile(output) as archive:
        config = json.loads(archive.read('config.redacted.json'))
        names = set(archive.namelist())
        archive_text = '\n'.join(
            archive.read(name).decode('utf-8', errors='replace')
            for name in names if name.endswith('.json')
        )

    assert config['vars']['password'] == '***REDACTED***'
    assert config['vars']['username'] == 'demo'
    assert 'top-secret' not in archive_text
    assert {'manifest.json', 'environment.json', 'logs.json', 'status.json'}.issubset(names)


def test_saved_player_config_encrypts_secret_fields(monkeypatch, tmp_path):
    _, config = _prepare_player(monkeypatch, tmp_path)
    output = tmp_path / 'user_config.json'

    PlayerService.save_user_config(config, str(output), 'instance-1')

    text = output.read_text(encoding='utf-8')
    stored = json.loads(text)
    assert 'top-secret' not in text
    assert stored['vars']['username'] == 'demo'
    assert stored['vars']['password'].startswith(('dpapi:', 'fernet:', 'plain-test:'))


def test_status_machine_observes_execution_terminal_state(monkeypatch, tmp_path):
    _prepare_player(monkeypatch, tmp_path)
    PlayerService._set_state('instance-1', 'running', '运行中', execution_id='exec-1')
    monkeypatch.setattr(
        ExecutionService,
        'get_execution_status',
        staticmethod(lambda execution_id: {'status': {'status': 'error', 'message': 'boom', 'failure_screenshot': 'x.png'}, 'logs': []}),
    )

    status = PlayerService.get_status('instance-1')

    assert status['state'] == 'error'
    assert status['message'] == 'boom'
    assert status['failure_screenshot'] == 'x.png'


def test_player_execution_uses_memory_blueprint_without_persisting(monkeypatch, tmp_path):
    blueprint = {
        'project_name': 'memory-only', 'variables': {},
        'tasks': [{'task_id': 'main', 'task_name': 'main', 'nodes': []}],
        'edges': [], 'topology': {'tasks': [], 'edges': []},
    }
    persisted = []
    monkeypatch.setattr('core.services.execution_service.BlueprintService.save_blueprint', lambda *args, **kwargs: persisted.append(args))
    monkeypatch.setattr('core.services.execution_service._db_safe', lambda *args, **kwargs: None)
    background = BackgroundTasks()

    result = ExecutionService.run_task(
        str(tmp_path), 'main', None, blueprint, background,
        persist_blueprint=False, runtime_dir=str(tmp_path), instance_id='instance-1',
    )

    assert result['status'] == 'started'
    assert persisted == []
