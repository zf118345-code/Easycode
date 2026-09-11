from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from api.routers.capture_router import create_capture_router
from api.routers.vnext_router import create_vnext_router
from core.services.capture_session_service import CaptureSessionService, Snapshot
from core.vnext.resources import ProjectAssetService


def _png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new('RGB', (width, height), color).save(output, format='PNG')
    return output.getvalue()


def _encoded(content: bytes) -> str:
    return base64.b64encode(content).decode('ascii')


@pytest.fixture(autouse=True)
def _reset_capture_state():
    with CaptureSessionService._lock:
        CaptureSessionService._ui_sessions.clear()
        CaptureSessionService._snapshots.clear()
        CaptureSessionService._transactions.clear()
        CaptureSessionService._pending_actions.clear()
        CaptureSessionService._active_snapshot_id = None
    yield
    with CaptureSessionService._lock:
        CaptureSessionService._ui_sessions.clear()
        CaptureSessionService._snapshots.clear()
        CaptureSessionService._transactions.clear()
        CaptureSessionService._pending_actions.clear()
        CaptureSessionService._active_snapshot_id = None


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    app.include_router(create_capture_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> tuple[dict, dict[str, str]]:
    response = client.post('/api/vnext/workspaces/open', json={
        'path': str(project),
        'initialize': True,
        'project_name': '资源垂直切片',
    })
    assert response.status_code == 200, response.text
    opened = response.json()
    workspace = opened['workspace']
    return opened, {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def test_resource_registry_cache_observes_external_atomic_replacement(tmp_path: Path) -> None:
    client = _client()
    project = tmp_path / 'external-registry-change'
    _opened, _headers = _open(client, project)
    service = ProjectAssetService(str(project))
    assert service.list()['assets'] == []

    registry_path = project / 'assets' / 'registry.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    registry['folders']['image'] = ['外部目录']
    replacement = registry_path.with_suffix('.external.json')
    replacement.write_text(json.dumps(registry, ensure_ascii=False), encoding='utf-8')
    replacement.replace(registry_path)

    categories = service.list()['categories']
    assert categories[0]['folders'] == ['外部目录']


def test_format6_resource_api_uses_one_tree_and_blocks_program_asset_references(tmp_path: Path) -> None:
    client = _client()
    project = tmp_path / 'resources'
    opened, headers = _open(client, project)

    assert all((project / 'assets' / category).is_dir() for category in ('image', 'ocr', 'page'))
    listing = client.get('/api/vnext/assets', headers=headers)
    assert listing.status_code == 200, listing.text
    assert [item['id'] for item in listing.json()['categories']] == ['image', 'ocr', 'page']

    created_folder = client.post('/api/vnext/asset-folders', headers=headers, json={
        'category': 'image',
        'folder': '登录/按钮',
    })
    assert created_folder.status_code == 200, created_folder.text
    first_png = _png(3, 2, (220, 40, 60))
    imported_response = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image',
        'folder': '登录/按钮',
        'file_name': 'login.png',
        'display_name': '登录按钮',
        'content_base64': _encoded(first_png),
        'source': 'import',
    })
    assert imported_response.status_code == 200, imported_response.text
    asset = imported_response.json()['asset']
    asset_id = asset['asset_id']
    assert asset['width'] == 3 and asset['height'] == 2

    preview = client.get(f'/api/vnext/assets/{asset_id}/content', headers=headers)
    assert preview.status_code == 200
    assert preview.content == first_png

    moved_response = client.patch(f'/api/vnext/assets/{asset_id}', headers=headers, json={
        'category': 'ocr',
        'folder': '文字',
        'display_name': '登录文字',
    })
    assert moved_response.status_code == 200, moved_response.text
    moved = moved_response.json()['asset']
    assert moved['asset_id'] == asset_id
    assert moved['path'].startswith('assets/ocr/文字/')
    assert (project / moved['path']).is_file()

    second_png = _png(4, 5, (20, 120, 230))
    replaced_response = client.put(f'/api/vnext/assets/{asset_id}/content', headers=headers, json={
        'file_name': 'replacement.png',
        'content_base64': _encoded(second_png),
    })
    assert replaced_response.status_code == 200, replaced_response.text
    replaced = replaced_response.json()['asset']
    assert replaced['asset_id'] == asset_id
    assert replaced['width'] == 4 and replaced['height'] == 5
    assert replaced['sha256'] != asset['sha256']
    replaced_path = project / replaced['path']
    replaced_path.write_bytes(b'externally changed')
    stale_preview = client.get(f'/api/vnext/assets/{asset_id}/content', headers=headers)
    assert stale_preview.status_code == 409
    assert '外部修改' in str(stale_preview.json()['detail'])
    replaced_path.write_bytes(second_png)

    entry_function_id = opened['inspection']['entry_function_id']
    program_path = project / 'program' / 'functions' / f'{entry_function_id}.json'
    original_program = program_path.read_bytes()
    program = json.loads(original_program)
    program['function']['statements'] = [{
        'statement_id': 'stmt_asset_reference',
        'kind': 'call',
        'function_id': 'extension.test.image_consumer',
        'arguments': {
            'extension.test.image_consumer.parameter.image': {
                'value_id': 'value_asset_reference',
                'kind': 'asset_ref',
                'asset_id': asset_id,
            },
        },
        'result_binding': None,
        'step_label': None,
    }]
    program_path.write_text(json.dumps(program, ensure_ascii=False), encoding='utf-8')

    references_response = client.get(f'/api/vnext/assets/{asset_id}/references', headers=headers)
    assert references_response.status_code == 200, references_response.text
    references = references_response.json()['references']
    assert references == [{
        'kind': 'program_parameter',
        'path': f'program/functions/{entry_function_id}.json',
        'document_id': program['document_id'],
        'function_id': entry_function_id,
        'statement_id': 'stmt_asset_reference',
        'parameter_id': 'extension.test.image_consumer.parameter.image',
        'value_id': 'value_asset_reference',
        'field_path': 'function.statements[0].arguments.extension.test.image_consumer.parameter.image',
        'preview': 'extension.test.image_consumer · extension.test.image_consumer.parameter.image',
    }]
    blocked = client.delete(f'/api/vnext/assets/{asset_id}?force=true', headers=headers)
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()['blocked'] is True
    assert (project / replaced['path']).is_file()

    program_path.write_bytes(original_program)
    deleted = client.delete(f'/api/vnext/assets/{asset_id}', headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()['deleted'] is True
    assert not (project / replaced['path']).exists()


def test_format6_import_validates_real_images_and_reports_duplicate_content(tmp_path: Path) -> None:
    client = _client()
    project = tmp_path / 'validated-imports'
    _, headers = _open(client, project)
    registry_path = project / 'assets' / 'registry.json'
    registry_before = registry_path.read_bytes()

    invalid = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image',
        'folder': '',
        'file_name': 'broken.png',
        'display_name': '损坏图片',
        'content_base64': _encoded(b'not an image'),
        'source': 'import',
    })
    assert invalid.status_code == 409
    assert '无法解码' in str(invalid.json()['detail'])
    assert registry_path.read_bytes() == registry_before
    assert not list((project / 'assets' / 'image').iterdir())

    png = _png(7, 9, (12, 34, 56))
    mismatched = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image',
        'folder': '',
        'file_name': 'wrong.jpg',
        'display_name': '扩展名错误',
        'content_base64': _encoded(png),
        'source': 'import',
    })
    assert mismatched.status_code == 409
    assert '扩展名与实际格式不一致' in str(mismatched.json()['detail'])
    assert registry_path.read_bytes() == registry_before

    first = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'image', 'folder': '按钮', 'file_name': 'button.png',
        'display_name': '按钮', 'content_base64': _encoded(png), 'source': 'import',
    })
    assert first.status_code == 200, first.text
    first_asset = first.json()['asset']
    first_registry = registry_path.read_bytes()
    first_file = project / first_asset['path']
    rejected_replace = client.put(f'/api/vnext/assets/{first_asset["asset_id"]}/content', headers=headers, json={
        'file_name': 'replacement.png',
        'content_base64': _encoded(b'broken replacement'),
    })
    assert rejected_replace.status_code == 409
    assert registry_path.read_bytes() == first_registry
    assert first_file.read_bytes() == png

    duplicate = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'ocr', 'folder': '文字', 'file_name': 'button-copy.png',
        'display_name': '按钮副本', 'content_base64': _encoded(png), 'source': 'import',
    })
    assert duplicate.status_code == 200, duplicate.text
    duplicated_payload = duplicate.json()
    assert duplicated_payload['asset']['asset_id'] != first_asset['asset_id']
    assert duplicated_payload['duplicate_of']['asset_id'] == first_asset['asset_id']
    assert duplicated_payload['asset']['sha256'] == first_asset['sha256']
    assert duplicated_payload['asset']['width'] == 7
    assert duplicated_payload['asset']['height'] == 9
    assert (project / duplicated_payload['asset']['path']).read_bytes() == png

    page = client.post('/api/vnext/assets', headers=headers, json={
        'category': 'page', 'folder': '页面样本', 'file_name': 'page.png',
        'display_name': '页面', 'content_base64': _encoded(_png(2, 3, (90, 80, 70))), 'source': 'import',
    })
    assert page.status_code == 200, page.text
    listing = client.get('/api/vnext/assets', headers=headers).json()
    assert [item['id'] for item in listing['categories']] == ['image', 'ocr', 'page']
    assert [len([asset for asset in listing['assets'] if asset['category'] == category]) for category in ('image', 'ocr', 'page')] == [1, 1, 1]

    moved_folder = client.post('/api/vnext/asset-folders/move', headers=headers, json={
        'source_path': 'image/按钮',
        'target_parent': 'page',
        'name': '交互按钮',
    })
    assert moved_folder.status_code == 200, moved_folder.text
    assert moved_folder.json()['new_path'] == 'page/交互按钮'
    after_move = client.get('/api/vnext/assets', headers=headers).json()['assets']
    moved_asset = next(item for item in after_move if item['asset_id'] == first_asset['asset_id'])
    assert moved_asset['category'] == 'page'
    assert moved_asset['folder'] == '交互按钮'
    assert (project / moved_asset['path']).read_bytes() == png
    assert not (project / first_asset['path']).exists()

    delete_preview = client.delete('/api/vnext/asset-folders/page/交互按钮', headers=headers)
    assert delete_preview.status_code == 200, delete_preview.text
    assert delete_preview.json()['requires_confirmation'] is True
    deleted_folder = client.delete('/api/vnext/asset-folders/page/交互按钮?force=true', headers=headers)
    assert deleted_folder.status_code == 200, deleted_folder.text
    assert deleted_folder.json()['deleted'] is True
    assert not any(item['asset_id'] == first_asset['asset_id'] for item in client.get('/api/vnext/assets', headers=headers).json()['assets'])


def test_format6_capture_reports_unavailable_state_and_saves_into_shared_resource_tree(tmp_path: Path) -> None:
    client = _client()
    project = tmp_path / 'capture'
    opened, headers = _open(client, project)
    workspace = opened['workspace']
    session_payload = {
        'session_id': 'session_v6_capture',
        'project_path': str(project),
        'workspace_kind': 'vnext',
        'workspace_id': workspace['workspace_id'],
        'workspace_generation': workspace['generation'],
        'project_id': workspace['project_id'],
        'project_name': workspace['project_name'],
        'capture_context': {'target_id': ''},
        'execution_state': 'idle',
    }
    registered = client.post('/api/capture/session/register', headers=headers, json=session_payload)
    assert registered.status_code == 200, registered.text

    unavailable = client.post('/api/capture/trigger', json={
        'session_id': 'session_v6_capture',
        'field_capture': {
            'request_id': 'capture_request_1',
            'selection_mode': 'asset',
            'category': 'image',
            'destination': 'resource',
            'max_rects': 1,
            'title': '录入图片',
        },
    })
    assert unavailable.status_code == 409
    assert '可截图的运行目标' in str(unavailable.json()['detail'])

    frozen_png = _png(8, 6, (90, 140, 190))
    snapshot = Snapshot(
        snapshot_id='snapshot_v6',
        project_path=str(project),
        project_id=workspace['project_id'],
        workspace_id=workspace['workspace_id'],
        workspace_generation=workspace['generation'],
        png=frozen_png,
        width=8,
        height=6,
        region=[0, 0, 8, 6],
        backend='test:frozen-frame',
        workspace_kind='vnext',
        session_id='session_v6_capture',
        source={
            'target_id': 'target_test',
            'platform': 'windows',
            'captured_at': '2026-09-01T01:00:00+08:00',
        },
    )
    with CaptureSessionService._lock:
        CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
        CaptureSessionService._active_snapshot_id = snapshot.snapshot_id

    metadata_response = client.get(
        f'/api/capture/snapshot/{snapshot.snapshot_id}',
        params={'include_image': 'false'},
    )
    assert metadata_response.status_code == 200, metadata_response.text
    assert metadata_response.json()['width'] == 8
    assert 'image' not in metadata_response.json()

    saved_response = client.post('/api/capture/assets', json={
        'snapshot_id': snapshot.snapshot_id,
        # The capture opened on image, then the user selected page/弹窗.
        'category': 'image',
        'relative_dir': 'page/弹窗',
        'prefix': '随机弹窗',
        'rects': [[2, 1, 3, 4]],
        'collision': 'ask',
    })
    assert saved_response.status_code == 200, saved_response.text
    saved = saved_response.json()
    assert saved['ok'] is True
    assert saved['files'][0].startswith('assets/page/弹窗/')
    assert saved['assets'][0]['asset_id'] == saved['asset_ids'][0]
    assert saved['assets'][0]['display_name'] == '随机弹窗'

    listing_response = client.get('/api/vnext/assets', headers=headers)
    assert listing_response.status_code == 200, listing_response.text
    listing = listing_response.json()
    assert [item['id'] for item in listing['categories']] == ['image', 'ocr', 'page']
    captured = next(item for item in listing['assets'] if item['asset_id'] == saved['asset_ids'][0])
    assert captured['category'] == 'page'
    assert captured['folder'] == '弹窗'
    assert captured['width'] == 3 and captured['height'] == 4
    assert captured['source'] == 'capture'
    assert captured['capture']['selection_rect'] == [2, 1, 3, 4]
    assert captured['capture']['work_area'] == [0, 0, 8, 6]
    assert captured['capture']['reference_size'] == [8, 6]
    assert captured['capture']['target_id'] == 'target_test'
    assert captured['capture']['host'] == 'test:frozen-frame'
    assert 'region' not in captured['capture']
    assert captured['size_bytes'] > 0
    assert len(captured['sha256']) == 64

    preview = client.get(f'/api/vnext/assets/{captured["asset_id"]}/content', headers=headers)
    assert preview.status_code == 200
    with Image.open(io.BytesIO(preview.content)) as image:
        assert image.size == (3, 4)

    conflict = client.post('/api/capture/assets', json={
        'snapshot_id': snapshot.snapshot_id,
        'category': 'page',
        'relative_dir': 'page/弹窗',
        'prefix': '随机弹窗',
        'rects': [[2, 1, 3, 4]],
        'collision': 'ask',
    })
    assert conflict.status_code == 200, conflict.text
    assert conflict.json()['conflict'] is True
    assert conflict.json()['conflicts'][0]['asset_id'] == captured['asset_id']

    entry_function_id = opened['inspection']['entry_function_id']
    program_path = project / 'program' / 'functions' / f'{entry_function_id}.json'
    valid_program = program_path.read_bytes()
    program_path.write_text('{ damaged ProgramDocument', encoding='utf-8')
    fail_closed = client.post('/api/capture/assets', json={
        'snapshot_id': snapshot.snapshot_id,
        'category': 'page',
        'relative_dir': 'page/弹窗',
        'prefix': '随机弹窗',
        'rects': [[2, 1, 3, 4]],
        'collision': 'overwrite',
        'overwrite_confirmed': True,
    })
    assert fail_closed.status_code == 409
    assert '无法检查同名资源引用' in str(fail_closed.json()['detail'])
    program_path.write_bytes(valid_program)
    assets_after_rejection = client.get('/api/vnext/assets', headers=headers).json()['assets']
    assert [item['asset_id'] for item in assets_after_rejection] == [captured['asset_id']]

    undone = client.post('/api/capture/assets/undo', json={'transaction_id': saved['transaction_id']})
    assert undone.status_code == 200, undone.text
    after_undo = client.get('/api/vnext/assets', headers=headers).json()
    assert not any(item['asset_id'] == captured['asset_id'] for item in after_undo['assets'])
