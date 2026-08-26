import json
import os
import shutil

import pytest

from core.project_schema import PROJECT_SCHEMA_VERSION, load_project_documents
from core.services.project_workspace_service import ProjectWorkspaceManager, WorkspaceError


def manager_for(tmp_path, name='app-state'):
    source = tmp_path / 'easycode-source'
    source.mkdir(exist_ok=True)
    return ProjectWorkspaceManager(
        source_root=str(source),
        app_data_dir=str(tmp_path / name),
        process_id=os.getpid(),
    )


def test_app_data_directory_can_be_isolated_by_environment(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    isolated = tmp_path / 'isolated-app-state'
    monkeypatch.setenv('EASYCODE_APP_DATA_DIR', str(isolated))

    manager = ProjectWorkspaceManager(source_root=str(source), process_id=os.getpid())

    assert manager.app_data_dir == str(isolated.resolve())
    assert isolated.is_dir()


def test_empty_project_initialization_is_complete_and_transactional(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / '项目 A'
    project.mkdir()

    inspection = manager.inspect(str(project))
    assert inspection['status'] == 'empty'
    initialized = manager.initialize(str(project), '中文项目')

    assert initialized['status'] == 'valid'
    documents = load_project_documents(str(project))
    assert documents['project.json']['project_name'] == '中文项目'
    assert documents['project.json']['project_id'].startswith('project_')
    assert documents['project.json']['revision'] == 0
    assert all(document['schema_version'] == PROJECT_SCHEMA_VERSION for document in documents.values())
    assert (project / 'templates' / 'assets.json').is_file()
    assert not list(tmp_path.glob('.easycode-init-*'))


def test_nonempty_folder_requires_confirmation_and_reserved_conflict_is_rejected(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / 'existing files'
    project.mkdir()
    (project / 'notes.txt').write_text('keep me', encoding='utf-8')

    with pytest.raises(WorkspaceError, match='确认'):
        manager.initialize(str(project), '项目')
    manager.initialize(str(project), '项目', confirm_nonempty=True)
    assert (project / 'notes.txt').read_text(encoding='utf-8') == 'keep me'

    conflict = tmp_path / 'conflict'
    conflict.mkdir()
    (conflict / 'workflow.json').write_text('{}', encoding='utf-8')
    with pytest.raises(WorkspaceError, match='冲突'):
        manager.initialize(str(conflict), '项目', confirm_nonempty=True)


def test_source_root_is_never_a_script_project(tmp_path):
    manager = manager_for(tmp_path)
    with pytest.raises(WorkspaceError, match='源码根目录'):
        manager.inspect(str(tmp_path / 'easycode-source'))


def test_workspace_generation_rejects_stale_requests_and_switch_blockers(tmp_path):
    manager = manager_for(tmp_path)
    first = tmp_path / 'A'
    second = tmp_path / 'B'
    manager.initialize(str(first), 'A')
    manager.initialize(str(second), 'B')

    opened_a = manager.open(str(first))['workspace']
    assert manager.require(opened_a['workspace_id'], opened_a['generation']) == str(first.resolve())
    opened_b = manager.open(str(second))['workspace']
    with pytest.raises(WorkspaceError, match='旧项目'):
        manager.require(opened_a['workspace_id'], opened_a['generation'], writable=True)
    assert manager.require(opened_b['workspace_id'], opened_b['generation']) == str(second.resolve())

    manager.set_activity_probe(lambda: ['任务正在运行或暂停调试'])
    with pytest.raises(WorkspaceError, match='请先停止当前任务'):
        manager.close()
    manager.set_activity_probe(None)
    manager.shutdown()


def test_live_project_lock_blocks_second_writer_and_stale_lock_recovers(tmp_path):
    owner = manager_for(tmp_path, 'owner-state')
    contender = manager_for(tmp_path, 'contender-state')
    project = tmp_path / 'locked'
    owner.initialize(str(project), '锁测试')
    owner.open(str(project))

    with pytest.raises(WorkspaceError, match='另一个 EasyCode 实例'):
        contender.open(str(project), allow_read_only=False)

    read_only = contender.open(str(project), allow_read_only=True)['workspace']
    assert read_only['read_only'] is True
    with pytest.raises(WorkspaceError, match='只读'):
        contender.require(read_only['workspace_id'], read_only['generation'], writable=True)
    contender.close()

    owner.shutdown()
    stale_lock = project / '.easycode' / 'workspace.lock'
    stale_lock.write_text(json.dumps({'pid': 99999999, 'machine': 'old', 'session_nonce': 'dead'}), encoding='utf-8')
    assert contender.open(str(project))['workspace']['project_id']
    contender.shutdown()


def test_copied_project_gets_new_identity_without_touching_original(tmp_path):
    manager = manager_for(tmp_path)
    original = tmp_path / 'original'
    copy = tmp_path / 'copy'
    manager.initialize(str(original), 'Original')
    first = manager.open(str(original))['workspace']
    manager.close()
    shutil.copytree(original, copy)

    copied = manager.open(str(copy))['workspace']
    assert copied['project_id'] != first['project_id']
    assert load_project_documents(str(original))['project.json']['project_id'] == first['project_id']
    assert not (copy / '.easycode' / 'runtime.db').exists()
    manager.shutdown()


def test_invalid_project_repair_preserves_backup(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / 'repair'
    manager.initialize(str(project), 'Repair')
    (project / 'workflow.json').write_text('{broken', encoding='utf-8')

    assert manager.inspect(str(project))['status'] == 'invalid'
    repaired = manager.repair(str(project), confirmed=True)
    assert repaired['status'] == 'valid'
    recovery = repaired['recovery_path']
    assert os.path.isfile(os.path.join(recovery, 'workflow.json'))
    assert open(os.path.join(recovery, 'workflow.json'), encoding='utf-8').read() == '{broken'


def test_external_change_fingerprint_ignores_generated_outputs(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / 'watched'
    manager.initialize(str(project), 'Watched')
    workspace = manager.open(str(project))['workspace']

    assert manager.external_changes(workspace['workspace_id'], workspace['generation'])['changed'] is False
    (project / 'dist').mkdir()
    (project / 'dist' / 'generated.txt').write_text('output', encoding='utf-8')
    assert manager.external_changes(workspace['workspace_id'], workspace['generation'])['changed'] is False

    workflow = json.loads((project / 'workflow.json').read_text(encoding='utf-8'))
    workflow['tasks'] = []
    workflow['external_note'] = 'changed'
    (project / 'workflow.json').write_text(json.dumps(workflow), encoding='utf-8')
    changed = manager.external_changes(workspace['workspace_id'], workspace['generation'])
    assert changed['changed'] is True
    assert changed['paths'] == ['workflow.json']
    manager.acknowledge(workspace['workspace_id'], workspace['generation'])
    assert manager.external_changes(workspace['workspace_id'], workspace['generation'])['changed'] is False
    manager.shutdown()


def test_external_change_fingerprint_includes_project_capabilities(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / 'capability-watched'
    manager.initialize(str(project), 'Capability Watched')
    workspace = manager.open(str(project))['workspace']

    capability = project / 'capabilities' / 'ticketing'
    capability.mkdir(parents=True)
    (capability / 'main.py').write_text('def run():\n    return True\n', encoding='utf-8')
    changed = manager.external_changes(workspace['workspace_id'], workspace['generation'])
    assert changed['changed'] is True
    assert changed['paths'] == ['capabilities/ticketing/main.py']
    manager.shutdown()


def test_incremental_acknowledge_updates_only_known_internal_documents(tmp_path, monkeypatch):
    manager = manager_for(tmp_path)
    project = tmp_path / 'incremental-ack'
    manager.initialize(str(project), 'Incremental')
    workspace = manager.open(str(project))['workspace']
    meta = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    meta['revision'] += 1
    (project / 'project.json').write_text(json.dumps(meta), encoding='utf-8')

    full_scans = 0
    original = manager._workspace_fingerprint

    def counted_scan(path):
        nonlocal full_scans
        full_scans += 1
        return original(path)

    monkeypatch.setattr(manager, '_workspace_fingerprint', counted_scan)
    manager.acknowledge(
        workspace['workspace_id'],
        workspace['generation'],
        ('project.json',),
    )
    assert full_scans == 0
    assert manager.external_changes(workspace['workspace_id'], workspace['generation'])['changed'] is False
    assert full_scans == 1
    manager.shutdown()


def test_external_project_identity_change_requires_reopen(tmp_path):
    manager = manager_for(tmp_path)
    project = tmp_path / 'identity-change'
    manager.initialize(str(project), 'Before')
    workspace = manager.open(str(project))['workspace']
    meta = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    meta['project_id'] = 'project_replaced_externally'
    (project / 'project.json').write_text(json.dumps(meta), encoding='utf-8')

    changes = manager.external_changes(workspace['workspace_id'], workspace['generation'])
    assert changes['identity_changed'] is True
    with pytest.raises(WorkspaceError, match='重新打开项目'):
        manager.acknowledge(workspace['workspace_id'], workspace['generation'])
    manager.shutdown()
