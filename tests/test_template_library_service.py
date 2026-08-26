import json
from pathlib import Path

import pytest
from PIL import Image

from core.project_schema import PROJECT_SCHEMA_VERSION, new_project_documents
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService
from core.services.template_library_service import TemplateLibraryService


def write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def make_project(tmp_path: Path):
    AssetService.ensure_structure(str(tmp_path))
    for filename, value in new_project_documents('assets-test').items():
        write_json(tmp_path / filename, value)


def graph_with_reference(reference: str, *, feature=False):
    params = {
        'image_source': reference,
        'region_type': 'recorded',
        'region_value': [10, 20, 30, 40],
        'region_reference_size': [1280, 720],
        'crop_rect': [10, 20, 30, 40],
        'region': [10, 20, 30, 40],
    }
    if feature:
        params = {'page_id': 'page_test', 'features': [{'condition_type': 'image_exists', **params}]}
    return {
        'schema_version': PROJECT_SCHEMA_VERSION,
        'tasks': [{
            'task_id': 'task_a',
            'task_name': '测试组',
            'nodes': [{
                'node_id': 'node_a',
                'node_name': '识别节点',
                'node_type': 'page_state' if feature else 'image_recognition',
                'params': params,
            }],
        }],
        'edges': [],
    }


def test_delete_asset_is_recoverable_and_clears_graph_state(tmp_path):
    make_project(tmp_path)
    image_path = tmp_path / 'templates' / 'image' / 'button.png'
    Image.new('RGB', (20, 10), (10, 20, 30)).save(image_path)
    record = AssetService.register_file(
        str(tmp_path), 'image/button.png', 'image',
        capture={'region': [10, 20, 30, 40], 'reference_size': [1280, 720]},
    )
    reference = AssetService.reference(record['id'])
    write_json(tmp_path / 'workflow.json', graph_with_reference(reference))
    write_json(tmp_path / 'topology.json', graph_with_reference(reference, feature=True))

    impact = TemplateLibraryService.inspect(str(tmp_path), 'image/button.png')
    assert impact['node_count'] == 2
    assert impact['reference_count'] == 2

    result = TemplateLibraryService.delete(str(tmp_path), 'image/button.png')

    assert result['node_count'] == 2
    assert result['trash_id'].startswith('trash_')
    assert not image_path.exists()
    trash_image = (
        tmp_path / '.easycode' / 'resource-trash' / result['trash_id'] /
        'templates' / 'image' / 'button.png'
    )
    assert trash_image.is_file()
    assert (trash_image.parents[2] / 'manifest.json').is_file()
    assert record['id'] not in AssetService.load_registry(str(tmp_path))['assets']

    workflow_params = read_json(tmp_path / 'workflow.json')['tasks'][0]['nodes'][0]['params']
    assert workflow_params['image_source'] == ''
    assert workflow_params['region_type'] == 'fullwindow'
    assert workflow_params['region_value'] == [0, 0, 0, 0]
    assert workflow_params['region_reference_size'] == [0, 0]
    assert workflow_params['crop_rect'] == [0, 0, 0, 0]
    assert workflow_params['region'] == [0, 0, 0, 0]
    topology_feature = read_json(tmp_path / 'topology.json')['tasks'][0]['nodes'][0]['params']['features'][0]
    assert topology_feature['image_source'] == ''
    assert topology_feature['region_value'] == [0, 0, 0, 0]
    assert not (tmp_path / 'templates' / 'regions.json').exists()

    listed = TemplateLibraryService.list_trash(str(tmp_path))
    assert listed['entries'][0]['transaction_id'] == result['trash_id']
    assert listed['entries'][0]['restorable'] is True
    restored = TemplateLibraryService.restore(str(tmp_path), result['trash_id'])
    assert restored['references_restored'] == 0
    assert image_path.is_file()
    restored_record = AssetService.load_registry(str(tmp_path))['assets'][record['id']]
    assert restored_record['capture']['region'] == [10, 20, 30, 40]
    assert TemplateLibraryService.list_trash(str(tmp_path))['entries'] == []
    # Restoring a resource does not overwrite graph edits made after deletion.
    assert read_json(tmp_path / 'workflow.json')['tasks'][0]['nodes'][0]['params']['image_source'] == ''


def test_move_keeps_stable_id_and_requires_no_graph_rewrite(tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'button.png'
    destination_dir = tmp_path / 'templates' / 'page' / 'login'
    destination_dir.mkdir(parents=True)
    Image.new('RGB', (8, 6), (1, 2, 3)).save(source)
    record = AssetService.register_file(str(tmp_path), 'image/button.png', 'image')
    write_json(tmp_path / 'workflow.json', graph_with_reference(AssetService.reference(record['id'])))
    write_json(tmp_path / 'topology.json', graph_with_reference(AssetService.reference(record['id']), feature=True))

    result = TemplateLibraryService.move(
        str(tmp_path), 'image/button.png', 'page/login', 'submit.png',
    )

    assert result['new_path'] == 'page/login/submit.png'
    assert read_json(tmp_path / 'project.json')['revision'] == 1
    assert not source.exists()
    assert (destination_dir / 'submit.png').is_file()
    moved_record = AssetService.load_registry(str(tmp_path))['assets'][record['id']]
    assert moved_record['path'] == 'page/login/submit.png'
    assert moved_record['kind'] == 'page'
    assert moved_record['display_name'] == 'submit'
    workflow_ref = read_json(tmp_path / 'workflow.json')['tasks'][0]['nodes'][0]['params']['image_source']
    topology_ref = read_json(tmp_path / 'topology.json')['tasks'][0]['nodes'][0]['params']['features'][0]['image_source']
    assert workflow_ref == AssetService.reference(record['id'])
    assert topology_ref == AssetService.reference(record['id'])
    assert not (tmp_path / 'templates' / 'regions.json').exists()


def test_move_folder_updates_all_registered_paths(tmp_path):
    make_project(tmp_path)
    source_dir = tmp_path / 'templates' / 'image' / 'buttons'
    destination = tmp_path / 'templates' / 'ocr'
    source_dir.mkdir()
    Image.new('RGB', (2, 2)).save(source_dir / 'one.png')
    Image.new('RGB', (3, 3)).save(source_dir / 'two.png')
    first = AssetService.register_file(str(tmp_path), 'image/buttons/one.png', 'image')
    second = AssetService.register_file(str(tmp_path), 'image/buttons/two.png', 'image')

    TemplateLibraryService.move(str(tmp_path), 'image/buttons', 'ocr', 'controls')

    registry = AssetService.load_registry(str(tmp_path))['assets']
    assert registry[first['id']]['path'] == 'ocr/controls/one.png'
    assert registry[second['id']]['path'] == 'ocr/controls/two.png'
    assert registry[first['id']]['kind'] == 'ocr'
    assert not source_dir.exists()
    assert (destination / 'controls' / 'one.png').is_file()


@pytest.mark.parametrize('root', ['image', 'ocr', 'page'])
def test_default_resource_roots_cannot_be_deleted_or_moved(tmp_path, root):
    make_project(tmp_path)
    with pytest.raises(PermissionError):
        TemplateLibraryService.delete(str(tmp_path), root)
    with pytest.raises(PermissionError):
        TemplateLibraryService.move(str(tmp_path), root, 'image', 'renamed')


def test_failed_delete_rolls_back_file_and_all_json(monkeypatch, tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'rollback.png'
    Image.new('RGB', (4, 4)).save(source)
    record = AssetService.register_file(str(tmp_path), 'image/rollback.png', 'image')
    write_json(tmp_path / 'workflow.json', graph_with_reference(AssetService.reference(record['id'])))
    TemplateLibraryService.inspect(str(tmp_path), 'image/rollback.png')
    before_workflow = (tmp_path / 'workflow.json').read_bytes()
    before_registry = (tmp_path / 'templates' / 'assets.json').read_bytes()

    def fail_write(_state):
        raise OSError('simulated write failure')

    monkeypatch.setattr(TemplateLibraryService, '_write_mutated_state', fail_write)
    with pytest.raises(OSError, match='simulated'):
        TemplateLibraryService.delete(str(tmp_path), 'image/rollback.png')

    assert source.is_file()
    assert (tmp_path / 'workflow.json').read_bytes() == before_workflow
    assert (tmp_path / 'templates' / 'assets.json').read_bytes() == before_registry


def test_stale_editor_save_cannot_revive_a_deleted_asset_reference(tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'stale.png'
    Image.new('RGB', (4, 4)).save(source)
    record = AssetService.register_file(str(tmp_path), 'image/stale.png', 'image')
    stale_graph = graph_with_reference(AssetService.reference(record['id']))
    write_json(tmp_path / 'workflow.json', stale_graph)

    TemplateLibraryService.delete(str(tmp_path), 'image/stale.png')
    BlueprintService.save_workflow(str(tmp_path), stale_graph, create_snapshot=False)

    params = read_json(tmp_path / 'workflow.json')['tasks'][0]['nodes'][0]['params']
    assert params['image_source'] == ''
    assert params['region_value'] == [0, 0, 0, 0]


def test_registering_a_new_file_does_not_reactivate_deleted_stable_id(tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'replace.png'
    Image.new('RGB', (4, 4)).save(source)
    old_record = AssetService.register_file(str(tmp_path), 'image/replace.png', 'image')
    TemplateLibraryService.delete(str(tmp_path), 'image/replace.png')

    Image.new('RGB', (5, 5)).save(source)
    new_record = AssetService.register_file(str(tmp_path), 'image/replace.png', 'image')
    assert new_record['id'] != old_record['id']

    old_stable_graph = graph_with_reference(AssetService.reference(old_record['id']))
    BlueprintService.save_workflow(str(tmp_path), old_stable_graph, create_snapshot=False)
    assert read_json(tmp_path / 'workflow.json')['tasks'][0]['nodes'][0]['params']['image_source'] == ''
