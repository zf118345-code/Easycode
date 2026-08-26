import io
import json
import os
import pytest
from PIL import Image
from fastapi import HTTPException

from core.services.capture_session_service import (
    CaptureSessionService,
    Snapshot,
)
from core.services.asset_service import AssetService
from core.services.native_capture_overlay import native_capture_overlay
from core.services.project_workspace_service import WorkspaceError, project_workspace_manager


_TEST_ACTIVE_PATH = ''
_TEST_ACTIVE_GENERATION = 1


def _snapshot(project_path, snapshot_id='snap_test'):
    global _TEST_ACTIVE_PATH, _TEST_ACTIVE_GENERATION
    _TEST_ACTIVE_PATH = os.fspath(project_path)
    _TEST_ACTIVE_GENERATION = 1
    image = Image.new('RGB', (8, 6), (10, 20, 30))
    for x in range(2, 5):
        for y in range(1, 4):
            image.putpixel((x, y), (240, 40, 70))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return Snapshot(
        snapshot_id=snapshot_id,
        project_path=os.fspath(project_path),
        project_id='project_test',
        workspace_id='workspace_test',
        workspace_generation=1,
        png=stream.getvalue(),
        width=8,
        height=6,
        region=[0, 0, 8, 6],
        backend='test',
        session_id='ide_test',
    )


@pytest.fixture(autouse=True)
def clean_capture_state(monkeypatch):
    global _TEST_ACTIVE_PATH, _TEST_ACTIVE_GENERATION
    _TEST_ACTIVE_PATH = ''
    _TEST_ACTIVE_GENERATION = 1
    monkeypatch.setattr(project_workspace_manager, 'active', lambda: {
        'workspace_id': 'workspace_test',
        'generation': _TEST_ACTIVE_GENERATION,
        'project_id': 'project_test',
        'project_path': _TEST_ACTIVE_PATH,
    })
    monkeypatch.setattr(
        project_workspace_manager,
        'require',
        lambda workspace_id, generation, writable=False: _TEST_ACTIVE_PATH
        if workspace_id == 'workspace_test' and generation == _TEST_ACTIVE_GENERATION
        else (_ for _ in ()).throw(WorkspaceError('旧项目工作区已失效')),
    )
    monkeypatch.setattr(project_workspace_manager, 'acknowledge', lambda *_args, **_kwargs: None)
    service = CaptureSessionService
    with service._lock:
        service._snapshots.clear()
        service._transactions.clear()
        service._ui_sessions.clear()
        service._pending_actions.clear()
        service._active_snapshot_id = None
        service._native_process = None
        service._native_host_title = ''
        service._native_launch_error = ''
    _TEST_ACTIVE_PATH = ''
    yield
    with service._lock:
        service._snapshots.clear()
        service._transactions.clear()
        service._ui_sessions.clear()
        service._pending_actions.clear()
        service._active_snapshot_id = None
        service._native_process = None
        service._native_host_title = ''
        service._native_launch_error = ''


def test_snapshot_cannot_write_after_same_project_is_reopened(tmp_path):
    global _TEST_ACTIVE_GENERATION
    (tmp_path / 'templates' / 'image').mkdir(parents=True)
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    _TEST_ACTIVE_GENERATION = 2

    with pytest.raises(HTTPException, match='旧项目工作区已失效'):
        CaptureSessionService.save_assets({
            'snapshot_id': snapshot.snapshot_id,
            'category': 'image',
            'relative_dir': 'image',
            'prefix': 'stale',
            'rects': [[0, 0, 1, 1]],
            'collision': 'ask',
        })

    assert not (tmp_path / 'templates' / 'image' / 'stale.png').exists()


def test_assets_are_cropped_from_the_immutable_snapshot_and_undo_is_atomic(tmp_path):
    (tmp_path / 'templates' / 'image').mkdir(parents=True)
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot

    saved = CaptureSessionService.save_assets({
        'snapshot_id': snapshot.snapshot_id,
        'category': 'image',
        'relative_dir': 'image',
        'prefix': 'button',
        'rects': [[2, 1, 3, 3]],
        'collision': 'ask',
    })

    output = tmp_path / saved['files'][0]
    with Image.open(output) as cropped:
        assert cropped.size == (3, 3)
        assert cropped.getpixel((1, 1)) == (240, 40, 70)
    assert saved['asset_refs'][0].startswith('asset://asset_')
    import json
    registry = json.loads((tmp_path / 'templates' / 'assets.json').read_text(encoding='utf-8'))
    assert registry['assets'][saved['asset_ids'][0]]['path'] == 'image/button.png'
    capture = registry['assets'][saved['asset_ids'][0]]['capture']
    assert capture['region'] == [2, 1, 3, 3]
    assert capture['snapshot_id'] == snapshot.snapshot_id

    CaptureSessionService.undo_assets(saved['transaction_id'])
    assert not output.exists()
    assert not (tmp_path / 'templates' / 'assets.json').exists()


def test_selected_template_root_is_the_authoritative_asset_category(tmp_path):
    for category in ('image', 'ocr', 'page'):
        (tmp_path / 'templates' / category).mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot

    saved = CaptureSessionService.save_assets({
        'snapshot_id': snapshot.snapshot_id,
        # The file manager may have opened on image before the user selects ocr.
        'category': 'image',
        'relative_dir': 'ocr',
        'prefix': '',
        'rects': [[0, 0, 1, 1]],
        'collision': 'ask',
    })

    assert saved['files'][0].startswith('templates/ocr/ocr_')
    import json
    registry = json.loads((tmp_path / 'templates' / 'assets.json').read_text(encoding='utf-8'))
    record = registry['assets'][saved['asset_ids'][0]]
    assert record['kind'] == 'ocr'
    assert record['path'].startswith('ocr/ocr_')


def test_batch_prefix_fills_number_holes_without_overwriting(tmp_path):
    target = tmp_path / 'templates' / 'image'
    target.mkdir(parents=True)
    Image.new('RGB', (1, 1)).save(target / 'test001.png')
    Image.new('RGB', (1, 1)).save(target / 'test003.png')
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot

    saved = CaptureSessionService.save_assets({
        'snapshot_id': snapshot.snapshot_id,
        'category': 'image',
        'relative_dir': 'image',
        'prefix': 'test',
        'rects': [[0, 0, 1, 1], [1, 0, 1, 1]],
        'collision': 'ask',
    })

    assert saved['files'] == [
        'templates/image/test002.png',
        'templates/image/test004.png',
    ]
    assert (target / 'test001.png').exists()
    assert (target / 'test003.png').exists()


def test_referenced_single_file_requires_explicit_second_overwrite_confirmation(tmp_path):
    target = tmp_path / 'templates' / 'image'
    target.mkdir(parents=True)
    Image.new('RGB', (1, 1)).save(target / 'used.png')
    record = AssetService.register_file(str(tmp_path), 'image/used.png', 'image')
    (tmp_path / 'workflow.json').write_text(
        json.dumps({'tasks': [{'nodes': [{'params': {
            'image_source': AssetService.reference(record['id']),
        }}]}]}),
        encoding='utf-8',
    )
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    payload = {
        'snapshot_id': snapshot.snapshot_id,
        'category': 'image',
        'relative_dir': 'image',
        'prefix': 'used',
        'rects': [[0, 0, 1, 1]],
    }

    first = CaptureSessionService.save_assets({**payload, 'collision': 'ask'})
    assert first['conflict'] is True
    assert first['conflicts'][0]['references']

    second = CaptureSessionService.save_assets({**payload, 'collision': 'overwrite'})
    assert second['requires_reference_confirmation'] is True

    final = CaptureSessionService.save_assets({
        **payload,
        'collision': 'overwrite',
        'overwrite_confirmed': True,
    })
    assert final['ok'] is True


def test_initial_native_snapshot_skips_base64_but_keeps_server_copy(monkeypatch, tmp_path):
    raw = _snapshot(tmp_path).png
    monkeypatch.setattr(
        'core.services.workspace_service.WorkspaceService.capture_frozen_snapshot',
        lambda _project_path: {
            '_png': raw,
            'width': 8,
            'height': 6,
            'region': [10, 20, 18, 26],
            'backend': 'window',
        },
    )

    created = CaptureSessionService.create_snapshot(
        str(tmp_path),
        session_id='ide_test',
        include_image=False,
    )

    assert 'image' not in created
    fetched = CaptureSessionService.get_snapshot(created['snapshot_id'])
    assert fetched['image']
    assert fetched['workspace_id'] == 'workspace_test'
    assert fetched['workspace_generation'] == 1


def test_native_capture_host_receives_binary_snapshot_without_base64(monkeypatch, tmp_path):
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    calls = []
    fake_process = object()

    def fake_show(session, metadata, png):
        calls.append((session, metadata, png))
        return {'ok': True}

    monkeypatch.setattr(native_capture_overlay, 'show', fake_show)
    monkeypatch.setattr(type(native_capture_overlay), 'process', property(lambda _self: fake_process))

    launched = CaptureSessionService._launch_native_host(
        {
            'origin': 'http://127.0.0.1:8000',
            'session_id': 'ide_test',
            'project_name': '测试项目',
        },
        {
            'snapshot_id': 'snap_test',
            'width': 8,
            'height': 6,
            'region': [100, 120, 108, 126],
        },
    )

    assert launched is True
    assert calls[0][2] == snapshot.png
    assert 'image' not in calls[0][1]
