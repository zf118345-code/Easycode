import json
import hashlib

import numpy as np
from PIL import Image

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService
from core.services.recording_replay_service import RecordingReplayService


def _project(tmp_path):
    project = tmp_path / 'offline-project'
    project.mkdir()
    for filename, value in new_project_documents('offline-project').items():
        (project / filename).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return project


def _recording(project, *, corrupt_tail=False):
    session_id = 'frame_recording_20260825_test'
    session = project / 'recordings' / session_id
    session.mkdir(parents=True)
    frame_array = np.zeros((80, 120, 3), dtype=np.uint8)
    pattern = np.random.default_rng(20260825).integers(0, 256, size=(12, 16, 3), dtype=np.uint8)
    frame_array[30:42, 45:61] = pattern
    frame_path = session / 'frame_00000001_1.png'
    Image.fromarray(frame_array, 'RGB').save(frame_path)
    record = {
        'index': 1,
        'file': frame_path.name,
        'captured_at': '2026-08-25T12:00:00+08:00',
        'timestamp_ns': 1,
        'width': 120,
        'height': 80,
        'bytes': frame_path.stat().st_size,
        'screen_region': [100, 200, 220, 280],
        'sha256': hashlib.sha256(frame_path.read_bytes()).hexdigest(),
    }
    content = json.dumps(record, ensure_ascii=False) + '\n'
    if corrupt_tail:
        content += '{"index": 2, "file":'
    (session / 'frames.jsonl').write_text(content, encoding='utf-8')
    (session / 'session.json').write_text(json.dumps({
        'schema_version': 2,
        'session_id': session_id,
        'started_at': '2026-08-25T12:00:00+08:00',
        'stopped_at': '2026-08-25T12:00:01+08:00',
        'status': 'stopped',
        'target_title': '抢票窗口',
        'capture_backend': 'foreground_screen',
        'frame_count': 1,
    }, ensure_ascii=False), encoding='utf-8')
    return session_id, pattern


def test_timeline_keeps_valid_frames_before_partial_crash_line(tmp_path):
    project = _project(tmp_path)
    session_id, _ = _recording(project, corrupt_tail=True)

    sessions = RecordingReplayService.list_sessions(str(project))
    timeline = RecordingReplayService.list_frames(str(project), session_id)
    content, path = RecordingReplayService.frame_bytes(str(project), session_id, 1)

    assert sessions[0]['frame_count'] == 1
    assert sessions[0]['target_title'] == '抢票窗口'
    assert timeline['total'] == 1
    assert timeline['frames'][0]['screen_region'] == [100, 200, 220, 280]
    assert content.startswith(b'\x89PNG')
    assert path.endswith('frame_00000001_1.png')


def test_recorded_frame_runs_current_topology_offline(tmp_path):
    project = _project(tmp_path)
    session_id, pattern = _recording(project)
    template_path = project / 'templates' / 'page' / 'ticket-button.png'
    template_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pattern, 'RGB').save(template_path)
    asset = AssetService.register_file(
        str(project), 'page/ticket-button.png', 'page',
        capture={
            'region': [45, 30, 16, 12],
            'reference_size': [120, 80],
            'coordinate_space': 'workspace_px',
        },
    )

    topology = BlueprintService.load_topology(str(project))
    topology['nodes'] = [{
            'node_id': 'sale-page',
            'node_name': '开售页面',
            'node_type': 'page_state',
            'params': {
                'page_id': 'sale',
                'feature_mode': 'and',
                'features': [{
                    'condition_type': 'image_exists',
                    'image_source': AssetService.reference(asset['id']),
                    'threshold': 0.95,
                    'region_type': 'recorded',
                }],
            },
        }]
    topology['edges'] = []
    BlueprintService.save_topology(str(project), topology)

    result = RecordingReplayService.analyze_frame(str(project), session_id, 1)

    assert [page['node_name'] for page in result['matched_pages']] == ['开售页面'], result
    assert result['pages'][0]['last_match_score'] >= 0.95
    assert result['elapsed_ms'] >= 0

    regression = RecordingReplayService.analyze_session(str(project), session_id)
    assert regression['analyzed_frame_count'] == 1
    assert regression['coverage'][0]['matched_frames'] == 1
    assert regression['frames'][0]['matched_pages'][0]['node_name'] == '开售页面'


def test_recorded_frame_becomes_capture_snapshot_without_live_recapture(monkeypatch, tmp_path):
    from core.services.capture_session_service import CaptureSessionService
    from core.services.project_workspace_service import project_workspace_manager

    project = _project(tmp_path)
    session_id, _ = _recording(project)
    monkeypatch.setattr(project_workspace_manager, 'active', lambda: {
        'workspace_id': 'workspace_test', 'generation': 7, 'project_id': 'project_test',
        'project_path': str(project),
    })
    monkeypatch.setattr(project_workspace_manager, 'require', lambda *_args, **_kwargs: str(project))
    with CaptureSessionService._lock:
        CaptureSessionService._snapshots.clear()
        CaptureSessionService._active_snapshot_id = None

    snapshot = CaptureSessionService.create_recording_snapshot(
        str(project), session_id, 1, session_id='ide_session', include_image=False,
    )
    stored = CaptureSessionService.get_snapshot(snapshot['snapshot_id'], include_image=False)

    assert snapshot['backend'] == 'recording_replay'
    assert snapshot['region'] == [100, 200, 220, 280]
    assert stored['source']['kind'] == 'recording'
    assert stored['source']['frame_index'] == 1
    CaptureSessionService.close_capture(snapshot['snapshot_id'])


def test_offline_regression_reports_checksum_corruption_without_losing_session(tmp_path):
    project = _project(tmp_path)
    session_id, _ = _recording(project)
    frame = next((project / 'recordings' / session_id).glob('frame_*.png'))
    frame.write_bytes(frame.read_bytes() + b'corrupt')

    report = RecordingReplayService.analyze_session(str(project), session_id)

    assert report['analyzed_frame_count'] == 1
    assert '帧校验失败' in report['frames'][0]['error']
