import json
import os

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService
from core.services.template_library_service import TemplateLibraryService


def make_project(path):
    for filename, value in new_project_documents('recovery').items():
        (path / filename).write_text(json.dumps(value), encoding='utf-8')
    AssetService.ensure_structure(str(path))


def test_delete_and_restore_resource_without_rebinding_graph(tmp_path):
    make_project(tmp_path)
    image = tmp_path / 'templates' / 'image' / 'button.png'
    image.write_bytes(b'not-decoded-in-resource-transaction')
    asset_id = 'asset_recovery'
    registry = AssetService.empty_registry()
    registry['assets'][asset_id] = {
        'id': asset_id,
        'path': 'image/button.png',
        'key': 'image/button',
        'kind': 'image',
        'display_name': 'button',
        'capture': {
            'region': [1, 2, 3, 4],
            'reference_size': [100, 80],
            'coordinate_space': 'workspace_px',
        },
    }
    AssetService.save_registry(str(tmp_path), registry)
    workflow = {
        'schema_version': 3,
        'main_graph': {
            'graph_id': 'main',
            'nodes': [{
                'node_id': 'node_1', 'node_name': '识图', 'node_type': 'image_recognition',
                'params': {
                    'image_source': AssetService.reference(asset_id),
                    'region_type': 'recorded',
                    'region_value': [1, 2, 3, 4],
                    'region_reference_size': [100, 80],
                },
            }],
            'edges': [],
        },
        'functions': [],
        'function_folders': [],
    }
    (tmp_path / 'workflow.json').write_text(json.dumps(workflow), encoding='utf-8')

    deleted = TemplateLibraryService.delete(str(tmp_path), 'image/button.png')
    assert json.loads((tmp_path / 'project.json').read_text(encoding='utf-8'))['revision'] == 1
    params = json.loads((tmp_path / 'workflow.json').read_text(encoding='utf-8'))['main_graph']['nodes'][0]['params']
    assert params['image_source'] == ''
    assert params['region_value'] == [0, 0, 0, 0]
    assert TemplateLibraryService.list_trash(str(tmp_path))['entries'][0]['restorable'] is True

    restored = TemplateLibraryService.restore(str(tmp_path), deleted['trash_id'])
    assert json.loads((tmp_path / 'project.json').read_text(encoding='utf-8'))['revision'] == 2
    assert restored['references_restored'] == 0
    assert image.read_bytes() == b'not-decoded-in-resource-transaction'
    assert AssetService.load_registry(str(tmp_path))['assets'][asset_id]['capture']['region'] == [1, 2, 3, 4]
    params = json.loads((tmp_path / 'workflow.json').read_text(encoding='utf-8'))['main_graph']['nodes'][0]['params']
    assert params['image_source'] == ''


def test_prepared_delete_is_rolled_back_after_process_interruption(tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'interrupted.png'
    source.write_bytes(b'original')
    registry_before = (tmp_path / 'templates' / 'assets.json').read_bytes()
    project_before = (tmp_path / 'project.json').read_bytes()
    workflow_before = (tmp_path / 'workflow.json').read_bytes()
    trash = tmp_path / '.easycode' / 'resource-trash' / 'trash_interrupted'
    TemplateLibraryService._backup_documents(str(tmp_path), str(trash))
    manifest = {
        'schema_version': 1,
        'transaction_id': 'trash_interrupted',
        'operation': 'delete',
        'state': 'prepared',
        'deleted_at': '2026-08-22T00:00:00+00:00',
        'original_path': 'image/interrupted.png',
        'entry_type': 'file',
        'asset_records': {},
        'references': [],
    }
    (trash / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    payload = trash / 'templates' / 'image' / 'interrupted.png'
    payload.parent.mkdir(parents=True)
    os.replace(source, payload)
    (tmp_path / 'workflow.json').write_text('{partial', encoding='utf-8')
    (tmp_path / 'templates' / 'assets.json').write_text('{partial', encoding='utf-8')

    result = TemplateLibraryService.recover_pending(str(tmp_path))

    assert result['recovered'] == 1
    assert source.read_bytes() == b'original'
    assert (tmp_path / 'workflow.json').read_bytes() == workflow_before
    assert (tmp_path / 'templates' / 'assets.json').read_bytes() == registry_before
    assert (tmp_path / 'project.json').read_bytes() == project_before
    assert not trash.exists()


def test_prepared_move_is_rolled_back_after_process_interruption(tmp_path):
    make_project(tmp_path)
    source = tmp_path / 'templates' / 'image' / 'move.png'
    destination = tmp_path / 'templates' / 'ocr' / 'move.png'
    source.write_bytes(b'original')
    transaction = tmp_path / '.easycode' / 'resource-transactions' / 'move_interrupted'
    TemplateLibraryService._backup_documents(str(tmp_path), str(transaction))
    (transaction / 'manifest.json').write_text(json.dumps({
        'schema_version': 1,
        'operation': 'move',
        'state': 'prepared',
        'source_path': 'image/move.png',
        'destination_path': 'ocr/move.png',
    }), encoding='utf-8')
    os.replace(source, destination)

    result = TemplateLibraryService.recover_pending(str(tmp_path))

    assert result['recovered'] == 1
    assert source.read_bytes() == b'original'
    assert not destination.exists()
    assert not transaction.exists()
    assert json.loads((tmp_path / 'project.json').read_text(encoding='utf-8'))['revision'] == 0
