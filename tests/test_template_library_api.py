import json

from PIL import Image

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService


def prepare_project(tmp_path):
    AssetService.ensure_structure(str(tmp_path))
    for filename, value in new_project_documents('api-test').items():
        (tmp_path / filename).write_text(json.dumps(value), encoding='utf-8')
    (tmp_path / 'templates' / 'image' / 'archive').mkdir()
    Image.new('RGB', (6, 4), (2, 3, 4)).save(tmp_path / 'templates' / 'image' / 'source.png')
    AssetService.register_file(str(tmp_path), 'image/source.png', 'image')


def open_headers(client, project_path):
    response = client.post('/api/workspaces/open', json={'path': project_path})
    assert response.status_code == 200, response.text
    workspace = response.json()['workspace']
    return {
        'X-Workspace-Id': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def test_template_library_impact_move_delete_api_chain(client, tmp_path):
    prepare_project(tmp_path)
    project_path = str(tmp_path)
    headers = open_headers(client, project_path)

    impact = client.get('/api/templates/impact', params={
        'project_path': project_path,
        'relative_path': 'image/source.png',
    }, headers=headers)
    assert impact.status_code == 200
    assert impact.json()['file_count'] == 1

    moved = client.post('/api/templates/move', json={
        'project_path': project_path,
        'relative_path': 'image/source.png',
        'target_parent_path': 'image/archive',
        'new_name': 'renamed.png',
    }, headers=headers)
    assert moved.status_code == 200, moved.text
    assert moved.json()['new_path'] == 'image/archive/renamed.png'
    assert (tmp_path / 'templates' / 'image' / 'archive' / 'renamed.png').is_file()

    deleted = client.post('/api/templates/delete', json={
        'project_path': project_path,
        'relative_path': 'image/archive/renamed.png',
    }, headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['trash_id'].startswith('trash_')
    assert not (tmp_path / 'templates' / 'image' / 'archive' / 'renamed.png').exists()

    trash = client.get('/api/templates/trash', params={'project_path': project_path}, headers=headers)
    assert trash.status_code == 200, trash.text
    assert trash.json()['entries'][0]['transaction_id'] == deleted.json()['trash_id']

    restored = client.post(
        f"/api/templates/trash/{deleted.json()['trash_id']}/restore",
        json={'project_path': project_path},
        headers=headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()['references_restored'] == 0
    assert (tmp_path / 'templates' / 'image' / 'archive' / 'renamed.png').is_file()


def test_template_library_api_protects_default_roots(client, tmp_path):
    prepare_project(tmp_path)
    headers = open_headers(client, str(tmp_path))
    response = client.post('/api/templates/delete', json={
        'project_path': str(tmp_path),
        'relative_path': 'image',
    }, headers=headers)
    assert response.status_code == 403
    assert '默认资源目录' in response.json()['detail']
