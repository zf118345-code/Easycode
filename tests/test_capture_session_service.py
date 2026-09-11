import io
import json
import os
import concurrent.futures
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
    from core.services.capture_target_pool import capture_target_pool
    capture_target_pool.close_owner('ide')
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
    capture_target_pool.close_owner('ide')
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


@pytest.mark.parametrize(
    ('overlay_region', 'expected_region', 'expected_presentation'),
    [
        ([120, 80, 920, 680], [120, 80, 920, 680], 'target_aligned'),
        (None, [0, 0, 800, 600], 'centered_fit'),
    ],
)
def test_vnext_snapshot_preserves_physical_windows_alignment_and_centers_virtual_targets(
    monkeypatch, tmp_path, overlay_region, expected_region, expected_presentation,
):
    from core.vnext import vnext_workspace_manager

    workspace = {
        'workspace_id': 'workspace_vnext', 'generation': 4,
        'project_id': 'project_vnext', 'project_path': str(tmp_path),
    }
    target = {'target_id': 'target_windows', 'type': 'windows', 'platform': 'windows'}
    monkeypatch.setattr(vnext_workspace_manager, 'active', lambda: workspace)
    monkeypatch.setattr(
        vnext_workspace_manager, 'require_path',
        lambda workspace_id, generation, writable=False: str(tmp_path),
    )
    monkeypatch.setattr(vnext_workspace_manager, 'resolve_target', lambda *_args, **_kwargs: target)

    class FakeDriver:
        frame_is_bgr = False

        @staticmethod
        def capture_frame():
            return Image.new('RGB', (800, 600), (24, 28, 34))

        @staticmethod
        def capture_overlay_region():
            return overlay_region

        @staticmethod
        def close():
            return None

    monkeypatch.setattr('core.vnext.target_runtime.create_target_driver', lambda *_args: FakeDriver())
    CaptureSessionService.register_ui_session({
        'session_id': 'vnext_capture', 'workspace_kind': 'vnext',
        'workspace_id': 'workspace_vnext', 'workspace_generation': 4,
        'project_id': 'project_vnext', 'project_path': str(tmp_path),
        'capture_context': {'target_id': 'target_windows'},
        'execution_state': 'idle',
    })

    created = CaptureSessionService.create_snapshot(
        str(tmp_path), session_id='vnext_capture', include_image=False,
    )

    assert created['region'] == expected_region
    assert created['presentation'] == expected_presentation
    assert CaptureSessionService.get_snapshot(created['snapshot_id'], include_image=False)['presentation'] == expected_presentation


def test_vnext_capture_reuses_target_driver_and_defers_png_on_native_hot_path(monkeypatch, tmp_path):
    from core.vnext import vnext_workspace_manager

    workspace = {
        'workspace_id': 'workspace_vnext', 'generation': 4,
        'project_id': 'project_vnext', 'project_path': str(tmp_path),
    }
    target = {'target_id': 'target_adb', 'type': 'android_adb', 'device_serial': 'device-1'}
    monkeypatch.setattr(vnext_workspace_manager, 'active', lambda: workspace)
    monkeypatch.setattr(vnext_workspace_manager, 'require_path', lambda *_args, **_kwargs: str(tmp_path))
    monkeypatch.setattr(vnext_workspace_manager, 'resolve_target', lambda *_args, **_kwargs: target)
    created = []

    class FakeDriver:
        frame_is_bgr = False

        def __init__(self):
            self.closed = False

        def capture_frame(self):
            return Image.new('RGB', (32, 24), (20, 24, 28))

        @staticmethod
        def capture_overlay_region():
            return None

        def close(self):
            self.closed = True

    def create_driver(*_args):
        driver = FakeDriver()
        created.append(driver)
        return driver

    monkeypatch.setattr('core.vnext.target_runtime.create_target_driver', create_driver)
    CaptureSessionService.register_ui_session({
        'session_id': 'vnext_capture', 'workspace_kind': 'vnext',
        'workspace_id': 'workspace_vnext', 'workspace_generation': 4,
        'project_id': 'project_vnext', 'project_path': str(tmp_path),
        'capture_context': {'target_id': 'target_adb'}, 'execution_state': 'idle',
    })

    first = CaptureSessionService.create_snapshot(str(tmp_path), session_id='vnext_capture', include_image=False)
    second = CaptureSessionService.create_snapshot(str(tmp_path), session_id='vnext_capture', include_image=False)

    assert len(created) == 1
    assert first['performance']['driver_reused'] is False
    assert second['performance']['driver_reused'] is True
    assert CaptureSessionService._snapshots[first['snapshot_id']].png == b''
    assert CaptureSessionService.get_snapshot(first['snapshot_id'])['image']
    assert CaptureSessionService._snapshots[first['snapshot_id']].performance['png_encode_deferred'] is True


def test_snapshot_bound_control_probe_is_resolved_without_browser_roundtrip(monkeypatch, tmp_path):
    global _TEST_ACTIVE_PATH
    _TEST_ACTIVE_PATH = os.fspath(tmp_path)
    CaptureSessionService.register_ui_session({
        'session_id': 'ide_test', 'workspace_id': 'workspace_test',
        'workspace_generation': 1, 'project_id': 'project_test',
        'project_path': _TEST_ACTIVE_PATH, 'execution_state': 'idle',
    })
    future = concurrent.futures.Future()
    future.set_result({'nodes': ['cached-node'], 'provider': 'android_uiautomator'})
    snapshot = _snapshot(tmp_path)
    snapshot.target = {'target_id': 'target_adb', 'type': 'android_adb', 'device_serial': 'device-1'}
    snapshot.semantic_future = future
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    calls = []

    def resolve(project_path, target, point, reference_size, **options):
        calls.append((project_path, target, point, reference_size, options))
        return [{'label': '按钮', 'selector': {'control_selector.field.target_id': 'target_adb'}}]

    monkeypatch.setattr('core.vnext.control_capture_v6.resolve_control_candidates', resolve)
    result = CaptureSessionService.request_ide_action({
        'kind': 'field_control_probe', 'session_id': 'ide_test',
        'snapshot_id': snapshot.snapshot_id, 'point': [3, 2], 'reference_size': [8, 6],
    })

    assert result['ok'] is True
    assert result['performance']['semantic_prefetched'] is True
    assert calls[0][4]['semantic_snapshot'] == ['cached-node']
    assert calls[0][4]['exclude_process_ids'] == {0}
    assert CaptureSessionService._pending_actions == {}


def test_prewarm_discards_one_target_frame_before_the_first_click(monkeypatch, tmp_path):
    global _TEST_ACTIVE_PATH
    from core.vnext import vnext_workspace_manager

    _TEST_ACTIVE_PATH = os.fspath(tmp_path)
    monkeypatch.setattr(
        vnext_workspace_manager,
        'require_path',
        lambda workspace_id, generation, writable=False: _TEST_ACTIVE_PATH,
    )
    target = {'target_id': 'target_windows', 'type': 'windows', 'work_area': {'mode': 'desktop'}}
    monkeypatch.setattr(vnext_workspace_manager, 'resolve_target', lambda *_args, **_kwargs: target)
    CaptureSessionService.register_ui_session({
        'session_id': 'prewarm_test', 'workspace_kind': 'vnext',
        'workspace_id': 'workspace_test', 'workspace_generation': 1,
        'project_id': 'project_test', 'project_path': _TEST_ACTIVE_PATH,
        'capture_context': {'target_id': 'target_windows'}, 'execution_state': 'idle',
        'origin': 'http://127.0.0.1:5174',
    })
    calls = []

    def capture(_cls, project_path, selected_target):
        calls.append((project_path, selected_target))
        return Image.new('RGB', (8, 6)), [0, 0, 8, 6], {'frame_ms': 4.0}, object()

    monkeypatch.setattr(CaptureSessionService, '_capture_target_image', classmethod(capture))
    monkeypatch.setattr(native_capture_overlay, 'prewarm', lambda: True)
    monkeypatch.setattr(native_capture_overlay, 'warm_resource_manager', lambda _origin: {'ok': True})
    monkeypatch.setattr(native_capture_overlay, 'is_alive', lambda: True)
    monkeypatch.setattr(type(native_capture_overlay), 'process', property(lambda _self: None))
    monkeypatch.setattr(type(native_capture_overlay), 'last_error', property(lambda _self: ''))

    result = CaptureSessionService.prewarm_native_host()

    assert result['ok'] is True
    assert result['target_ready'] is True
    assert result['target_performance']['frame_ms'] == 4.0
    assert calls == [(_TEST_ACTIVE_PATH, target)]


def test_native_capture_host_receives_binary_snapshot_without_base64(monkeypatch, tmp_path):
    snapshot = _snapshot(tmp_path)
    CaptureSessionService._snapshots[snapshot.snapshot_id] = snapshot
    calls = []
    fake_process = object()

    def fake_show(session, metadata, png, *, image=None):
        calls.append((session, metadata, png, image))
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


def test_explicit_capture_session_does_not_follow_a_newer_unrelated_ide(tmp_path):
    global _TEST_ACTIVE_PATH
    _TEST_ACTIVE_PATH = os.fspath(tmp_path)
    common = {
        'workspace_id': 'workspace_test',
        'workspace_generation': 1,
        'project_id': 'project_test',
        'project_path': _TEST_ACTIVE_PATH,
        'execution_state': 'idle',
    }
    CaptureSessionService.register_ui_session({
        **common, 'session_id': 'vnext_expected', 'last_focus_at': 10,
    })
    CaptureSessionService.register_ui_session({
        **common, 'session_id': 'legacy_newer', 'last_focus_at': 20,
    })

    assert CaptureSessionService.active_ui_session()['session_id'] == 'legacy_newer'
    assert CaptureSessionService.active_ui_session('vnext_expected')['session_id'] == 'vnext_expected'


def test_queued_capture_session_is_blocked_before_snapshot(tmp_path):
    global _TEST_ACTIVE_PATH
    _TEST_ACTIVE_PATH = os.fspath(tmp_path)
    CaptureSessionService.register_ui_session({
        'session_id': 'queued', 'workspace_id': 'workspace_test',
        'workspace_generation': 1, 'project_id': 'project_test',
        'project_path': _TEST_ACTIVE_PATH, 'execution_state': 'queued',
    })
    with pytest.raises(HTTPException, match='请先停止当前任务'):
        CaptureSessionService.active_ui_session('queued')


def test_dead_native_overlay_does_not_strand_next_field_capture(monkeypatch, tmp_path):
    global _TEST_ACTIVE_PATH
    from core.services import capture_mode
    from core.services.execution_service import ExecutionService
    from core.services.frame_recording_service import frame_recording_service

    _TEST_ACTIVE_PATH = os.fspath(tmp_path)
    CaptureSessionService.register_ui_session({
        'session_id': 'field_session', 'workspace_id': 'workspace_test',
        'workspace_generation': 1, 'project_id': 'project_test',
        'project_path': _TEST_ACTIVE_PATH, 'execution_state': 'idle',
    })
    stale = _snapshot(tmp_path, 'snap_stale')
    CaptureSessionService._snapshots[stale.snapshot_id] = stale
    CaptureSessionService._active_snapshot_id = stale.snapshot_id
    monkeypatch.setattr(native_capture_overlay, 'is_alive', lambda: False)
    monkeypatch.setattr(ExecutionService, 'has_active_execution', staticmethod(lambda: False))
    monkeypatch.setattr(frame_recording_service, 'get_state', lambda: {'active': False})
    monkeypatch.setattr(capture_mode, 'get_state', lambda: {'active': False})
    monkeypatch.setattr(capture_mode, 'publish_event', lambda _payload: None)
    created = []

    def fake_snapshot(_cls, project_path, *, session_id='', include_image=True, prefetch_control=False):
        created.append((project_path, session_id, include_image, prefetch_control))
        return {'snapshot_id': 'snap_fresh', 'width': 8, 'height': 6, 'region': [0, 0, 8, 6], 'backend': 'test'}

    monkeypatch.setattr(CaptureSessionService, 'create_snapshot', classmethod(fake_snapshot))
    monkeypatch.setattr(CaptureSessionService, '_launch_native_host', classmethod(lambda _cls, _session, _snapshot: True))

    result = CaptureSessionService.trigger_global_capture({
        'session_id': 'field_session',
        'field_capture': {'request_id': 'field_1', 'selection_mode': 'point', 'category': 'image'},
    })

    assert result['ok'] is True
    assert created == [(_TEST_ACTIVE_PATH, 'field_session', False, False)]
    assert 'snap_stale' not in CaptureSessionService._snapshots
