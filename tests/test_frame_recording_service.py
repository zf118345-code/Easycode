import json
import sys
import time
import types

import pytest
from PIL import Image

from core.services.frame_recording_service import FrameRecordingError, FrameRecordingService


def _create_project(tmp_path):
    project = tmp_path / 'recording-project'
    project.mkdir()
    (project / 'context.json').write_text(
        json.dumps(
            {
                'work_mode': 'window',
                'window_title': '一次性页面',
                'window_hwnd': 123,
                'window_process_id': 456,
                'offset_top': 10,
                'offset_bottom': 20,
                'offset_left': 30,
                'offset_right': 40,
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    return project


def _wait_finished(service, timeout=4):
    deadline = time.time() + timeout
    while service.get_state()['active'] and time.time() < deadline:
        time.sleep(0.01)
    state = service.get_state()
    assert state['active'] is False, state
    return state


def _prepare_service(monkeypatch, service):
    escape_calls = []
    monkeypatch.setattr(service, '_enable_escape', lambda: {'ok': True, 'message': 'ok'})
    monkeypatch.setattr(service, '_disable_escape', lambda: escape_calls.append('released'))
    monkeypatch.setattr(service, '_activate_target', lambda context: (123, 'print_window'))
    return escape_calls


def test_every_captured_frame_is_retained_without_deduplication(monkeypatch, tmp_path):
    project = _create_project(tmp_path)
    service = FrameRecordingService()
    escape_calls = _prepare_service(monkeypatch, service)
    captures = []

    def capture(_context):
        captures.append(len(captures) + 1)
        # 四张完全相同的图仍必须全部保存，验证录制服务不存在去重或覆盖。
        image = Image.new('RGB', (48, 32), (16, 32, 64))
        if len(captures) == 4:
            service.request_stop('esc')
        return image

    monkeypatch.setattr(service, '_capture_image', capture)
    started = service.start(str(project))
    assert started['frame_count'] >= 1
    state = _wait_finished(service)

    output_dir = project / 'recordings' / state['session_id']
    frames = sorted(output_dir.glob('frame_*.png'))
    records = [json.loads(line) for line in (output_dir / 'frames.jsonl').read_text(encoding='utf-8').splitlines()]
    manifest = json.loads((output_dir / 'session.json').read_text(encoding='utf-8'))

    assert len(frames) == 4
    assert [record['index'] for record in records] == [1, 2, 3, 4]
    assert len({frame.name for frame in frames}) == 4
    assert state['frame_count'] == 4
    assert state['stop_reason'] == 'esc'
    assert state['status'] == 'stopped'
    assert manifest['frame_count'] == 4
    assert manifest['retention_policy'] == 'never_delete_automatically'
    assert manifest['lossless_png'] is True
    assert manifest['final'] is True
    assert escape_calls == ['released']


def test_vnext_capture_provider_records_without_legacy_context_and_releases_driver(monkeypatch, tmp_path):
    project = tmp_path / 'vnext-recording-project'
    project.mkdir()
    service = FrameRecordingService()
    _prepare_service(monkeypatch, service)
    captures = []
    releases = []

    def capture():
        captures.append(len(captures) + 1)
        if len(captures) == 3:
            service.request_stop('test_complete')
        return Image.new('RGB', (32, 18), (len(captures), 20, 40))

    started = service.start(
        str(project), {'target_fps': 30},
        capture_provider=capture, capture_release=lambda: releases.append(True),
        target_title='测试模拟器', capture_backend='vnext:android_adb',
    )
    state = _wait_finished(service)
    manifest = json.loads((project / 'recordings' / started['session_id'] / 'session.json').read_text(encoding='utf-8'))

    assert state['frame_count'] == 3
    assert state['target_title'] == '测试模拟器'
    assert state['capture_backend'] == 'vnext:android_adb'
    assert state['screen_region'] == [0, 0, 32, 18]
    assert manifest['workspace_size'] == [32, 18]
    assert releases == [True]


def test_capture_failure_keeps_all_frames_saved_before_error(monkeypatch, tmp_path):
    project = _create_project(tmp_path)
    service = FrameRecordingService()
    _prepare_service(monkeypatch, service)
    calls = 0

    def capture(_context):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Image.new('RGB', (20, 10), 'red')
        raise RuntimeError('瞬时截图源失效')

    monkeypatch.setattr(service, '_capture_image', capture)
    started = service.start(str(project))
    state = _wait_finished(service)
    output_dir = project / 'recordings' / started['session_id']
    manifest = json.loads((output_dir / 'session.json').read_text(encoding='utf-8'))

    assert len(list(output_dir.glob('frame_*.png'))) == 1
    assert len((output_dir / 'frames.jsonl').read_text(encoding='utf-8').splitlines()) == 1
    assert state['status'] == 'error'
    assert '连续截图失败 5 次' in state['last_error']
    assert manifest['frame_count'] == 1
    assert manifest['final'] is True


def test_diagnostic_marker_is_attached_to_next_captured_frame(monkeypatch):
    service = FrameRecordingService()
    monkeypatch.setattr(service, '_capture_image', lambda _context: Image.new('RGB', (20, 10), 'green'))
    monkeypatch.setattr(service, '_screen_region_for_image', lambda _context, image: [0, 0, image.width, image.height])
    with service._lock:
        service._context = {}
        service._state = {**service._empty_state(), 'active': True, 'capture_count': 0}

    result = service.mark_event('开售按钮出现')
    packet = service._capture_packet()
    following = service._capture_packet()

    assert result == {'status': 'success', 'label': '开售按钮出现'}
    assert packet['event']['label'] == '开售按钮出现'
    assert packet['event']['type'] == 'manual'
    assert following['event'] is None


def test_start_is_blocked_before_activation_when_escape_cannot_be_owned(monkeypatch, tmp_path):
    project = _create_project(tmp_path)
    service = FrameRecordingService()
    activated = []
    captured = []
    released = []
    monkeypatch.setattr(service, '_enable_escape', lambda: {'ok': False, 'message': 'Esc 被占用'})
    monkeypatch.setattr(service, '_disable_escape', lambda: released.append(True))
    monkeypatch.setattr(service, '_activate_target', lambda context: activated.append(context))
    monkeypatch.setattr(service, '_capture_image', lambda context: captured.append(context))

    with pytest.raises(FrameRecordingError, match='无法优先接管 Esc'):
        service.start(str(project))

    state = service.get_state()
    output_dir = project / 'recordings' / state['session_id']
    manifest = json.loads((output_dir / 'session.json').read_text(encoding='utf-8'))
    assert activated == []
    assert captured == []
    assert state['active'] is False
    assert state['status'] == 'error'
    assert manifest['frame_count'] == 0
    assert manifest['final'] is True
    assert released == [True]


def test_foreground_capture_uses_live_cropped_work_panel_and_rejects_focus_loss(monkeypatch):
    from core.services import screenshot_service

    foreground = [321]
    win32con = types.ModuleType('win32con')
    win32con.GA_ROOT = 2
    win32gui = types.ModuleType('win32gui')
    win32gui.GetAncestor = lambda hwnd, flag: hwnd
    win32gui.GetForegroundWindow = lambda: foreground[0]
    win32gui.GetClientRect = lambda hwnd: (0, 0, 1000, 700)
    win32gui.ClientToScreen = lambda hwnd, point: (100 + point[0], 200 + point[1])
    monkeypatch.setitem(sys.modules, 'win32con', win32con)
    monkeypatch.setitem(sys.modules, 'win32gui', win32gui)

    workspace_module = types.ModuleType('core.services.workspace_service')

    class FakeWorkspaceService:
        _resolve_context_window = staticmethod(lambda context: 321)

    workspace_module.WorkspaceService = FakeWorkspaceService
    monkeypatch.setitem(sys.modules, 'core.services.workspace_service', workspace_module)

    captured_regions = []
    monkeypatch.setattr(screenshot_service, '_clamp_region', lambda region: region)
    monkeypatch.setattr(
        screenshot_service,
        'capture',
        lambda region=None: captured_regions.append(region) or Image.new('RGB', (930, 670), 'blue'),
    )
    context = {
        'work_mode': 'window',
        'window_title': '一次性页面',
        'offset_left': 30,
        'offset_top': 10,
        'offset_right': 40,
        'offset_bottom': 20,
    }

    image = FrameRecordingService._capture_image(context)
    assert image.size == (930, 670)
    assert captured_regions == [(130, 210, 1060, 880)]

    foreground[0] = 999
    with pytest.raises(FrameRecordingError, match='失去前台焦点'):
        FrameRecordingService._capture_image(context)
    assert captured_regions == [(130, 210, 1060, 880)]


def test_frame_recording_http_start_status_and_stop_contract(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import workspace_router
    from api.routers.workspace_router import create_workspace_router

    monkeypatch.setattr(
        workspace_router,
        'assert_matching_legacy_path',
        lambda request, supplied_path, writable=False: supplied_path,
    )

    class FakeRecordingService:
        def __init__(self):
            self.state = {'active': False, 'status': 'idle', 'frame_count': 0}
            self.calls = []

        def start(self, project_path):
            self.calls.append(('start', project_path))
            self.state = {'active': True, 'status': 'recording', 'frame_count': 1}
            return dict(self.state)

        def stop(self, reason):
            self.calls.append(('stop', reason))
            self.state = {'active': False, 'status': 'stopped', 'frame_count': 8}
            return dict(self.state)

        def get_state(self):
            return dict(self.state)

    service = FakeRecordingService()
    app = FastAPI()
    app.include_router(create_workspace_router(None, service))
    client = TestClient(app)

    started = client.post('/api/frame-recording/start', json={'project_path': 'D:/项目'}).json()
    status = client.get('/api/frame-recording/status').json()
    stopped = client.post('/api/frame-recording/stop', json={'reason': 'esc'}).json()

    assert started == {'active': True, 'status': 'recording', 'frame_count': 1}
    assert status == started
    assert stopped == {'active': False, 'status': 'stopped', 'frame_count': 8}
    assert service.calls == [('start', 'D:/项目'), ('stop', 'esc')]
