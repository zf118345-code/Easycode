from __future__ import annotations

import json
import time

import numpy as np
import pytest
from PIL import Image


def test_input_frame_change_verification_reports_effect(monkeypatch):
    from core.services import input_verification as verification

    frames = iter([
        np.zeros((36, 64), dtype=np.float32),
        np.full((36, 64), 80, dtype=np.float32),
    ])
    monkeypatch.setattr(verification, 'capture_signature', lambda _context: next(frames))
    result = verification.verify_frame_change(object(), np.zeros((36, 64), dtype=np.float32), timeout_ms=80, poll_ms=10)
    assert result['verified'] is True
    assert result['difference'] > 0.1


def test_target_capability_profile_persists_by_versioned_fingerprint(tmp_path, monkeypatch):
    from core.services.target_capability_profile import TargetCapabilityProfileService

    context = type('Context', (), {'project_dir': str(tmp_path), 'window_hwnd': 123})()
    monkeypatch.setattr(
        TargetCapabilityProfileService,
        'fingerprint',
        staticmethod(lambda _hwnd: {'id': 'app-v1', 'version': '1.2.3', 'class_name': 'Demo'}),
    )
    TargetCapabilityProfileService.record(context, 'background_click', False, '后置验证失败')
    observed = TargetCapabilityProfileService.observation(context, 'background_click')
    assert observed['supported'] is False
    assert observed['reason'] == '后置验证失败'
    assert json.loads((tmp_path / '.easycode' / 'target-capabilities.json').read_text(encoding='utf-8'))['targets']['app-v1']


def test_window_capture_crop_accepts_client_area_provider(monkeypatch):
    import win32gui

    from core.services import screenshot_service

    monkeypatch.setattr(win32gui, 'GetWindowRect', lambda _hwnd: (90, 80, 330, 260))
    monkeypatch.setattr(win32gui, 'GetClientRect', lambda _hwnd: (0, 0, 200, 120))
    monkeypatch.setattr(
        win32gui, 'ClientToScreen',
        lambda _hwnd, point: (100 + point[0], 100 + point[1]),
    )
    image = Image.new('RGB', (200, 120), (10, 20, 30))
    cropped = screenshot_service.crop_window_image(1, image, (110, 110, 190, 160))
    assert cropped.size == (80, 50)


def test_windows_target_refreshes_workspace_box_before_capture(monkeypatch):
    from core.services import screenshot_service
    from core.vnext.target_runtime import WindowsTargetDriver

    driver = object.__new__(WindowsTargetDriver)
    driver.target = {'work_area': {'mode': 'client'}}
    driver.hwnd = 101
    driver._box = (10, 20, 110, 120)
    monkeypatch.setattr(driver, '_workspace_box', lambda: (200, 300, 649, 1142))
    monkeypatch.setattr(
        screenshot_service,
        'capture_window_with_info',
        lambda _hwnd: (Image.new('RGB', (449, 842)), {'provider': 'test'}),
    )
    observed = {}

    def crop(_hwnd, image, screen_box):
        observed['screen_box'] = screen_box
        return image

    monkeypatch.setattr(screenshot_service, 'crop_window_image', crop)

    frame = driver.capture_frame()

    assert frame.size == (449, 842)
    assert observed['screen_box'] == (200, 300, 649, 1142)
    assert driver._box == (200, 300, 649, 1142)


def test_window_capture_crop_uses_dwm_bounds_for_wgc_resize_border(monkeypatch):
    import win32gui

    from core.services import screenshot_service

    monkeypatch.setattr(win32gui, 'GetWindowRect', lambda _hwnd: (120, 120, 1036, 799))
    monkeypatch.setattr(win32gui, 'GetClientRect', lambda _hwnd: (0, 0, 900, 640))
    monkeypatch.setattr(
        win32gui, 'ClientToScreen',
        lambda _hwnd, point: (128 + point[0], 151 + point[1]),
    )
    monkeypatch.setattr(
        screenshot_service, '_extended_frame_bounds',
        lambda _hwnd: (127, 120, 1029, 792),
    )
    image = Image.new('RGB', (902, 672), (10, 20, 30))

    cropped = screenshot_service.crop_window_image(1, image, (128, 151, 1028, 791))

    assert cropped.size == (900, 640)


def test_whole_window_capture_ignores_invisible_outer_resize_border(monkeypatch):
    import win32gui

    from core.services import screenshot_service

    monkeypatch.setattr(win32gui, 'GetWindowRect', lambda _hwnd: (55, 81, 1010, 769))
    monkeypatch.setattr(win32gui, 'GetClientRect', lambda _hwnd: (0, 0, 941, 681))
    monkeypatch.setattr(
        win32gui, 'ClientToScreen',
        lambda _hwnd, point: (62 + point[0], 81 + point[1]),
    )
    monkeypatch.setattr(
        screenshot_service, '_extended_frame_bounds',
        lambda _hwnd: (62, 81, 1003, 762),
    )
    image = Image.new('RGB', (941, 681), (10, 20, 30))

    cropped = screenshot_service.crop_window_image(1, image, (55, 81, 1010, 769))

    assert cropped.size == (941, 681)
    assert screenshot_service.window_image_screen_box(1, image.size) == (62, 81, 1003, 762)


def test_player_protected_documents_and_redaction_roundtrip(tmp_path):
    from core.services.player_secret_service import PlayerSecretService

    checkpoint = {'task_id': 'main', 'variables': {'password': 'top-secret'}}
    protected = PlayerSecretService.protect_document(checkpoint, str(tmp_path))
    serialized = json.dumps(protected)
    assert 'top-secret' not in serialized
    assert PlayerSecretService.unprotect_document(protected, str(tmp_path)) == checkpoint
    assert PlayerSecretService.redact({'message': 'token=top-secret'}, ['top-secret'])['message'] == 'token=***REDACTED***'


def _worker_payload(tmp_path, suffix: str, *, valid: bool = True):
    node_id = f'node_{suffix}'
    return {
        'execution_id': f'exec_{suffix}',
        'instance_id': suffix,
        'project_path': str(tmp_path),
        'task_id': 'main' if valid else 'missing',
        'start_node_id': node_id,
        'blueprint': {
            'schema_version': 3,
            'project_name': 'worker-load',
            'variables': {},
            'settings': {},
            'main_graph': {
                'graph_id': 'main',
                'nodes': [{
                    'node_id': node_id, 'node_name': '日志', 'node_type': 'log',
                    'params': {'message': f'worker-{suffix}'}, 'delay_before': 0,
                    'loop_count': 1, 'enabled': True,
                }],
                'edges': [],
            },
            'functions': [],
            'function_folders': [],
            'page_map': {'schema_version': 3, 'nodes': [], 'edges': []},
        },
        'context': {},
        'persist_blueprint': False,
    }


def _run_worker_batch(tmp_path, count: int):
    from core.services.execution_worker import next_worker_event, spawn_execution_worker

    proxies = [spawn_execution_worker(_worker_payload(tmp_path, f'{count}-{index}')) for index in range(count)]
    finals = []
    deadline = time.monotonic() + 25
    try:
        ready = set()
        while len(finals) < count and time.monotonic() < deadline:
            for index, proxy in enumerate(proxies):
                event = next_worker_event(proxy, 0.02)
                if not event:
                    continue
                if event['type'] == 'ready' and index not in ready:
                    ready.add(index)
                    proxy.start_event.set()
                elif event['type'] == 'final':
                    finals.append((index, event))
            if len(finals) < count:
                time.sleep(0.01)
        assert len(finals) == count
        assert all(event['status'] == 'success' for _, event in finals), finals
    finally:
        for proxy in proxies:
            proxy.stop()
            proxy.process.join(timeout=3)
            if proxy.process.is_alive():
                proxy.process.terminate()
                proxy.process.join(timeout=1)


@pytest.mark.parametrize('count', [1, 2, 4, 8])
def test_isolated_worker_load_levels(tmp_path, count):
    _run_worker_batch(tmp_path, count)


def test_one_worker_failure_does_not_stop_another(tmp_path):
    from core.services.execution_worker import next_worker_event, spawn_execution_worker

    good = spawn_execution_worker(_worker_payload(tmp_path, 'good'))
    bad = spawn_execution_worker(_worker_payload(tmp_path, 'bad', valid=False))
    finals = {}
    deadline = time.monotonic() + 20
    try:
        for _name, proxy in [('good', good), ('bad', bad)]:
            while time.monotonic() < deadline:
                event = next_worker_event(proxy, 0.1)
                if event and event['type'] == 'ready':
                    proxy.start_event.set()
                    break
        while len(finals) < 2 and time.monotonic() < deadline:
            for name, proxy in [('good', good), ('bad', bad)]:
                if name in finals:
                    continue
                event = next_worker_event(proxy, 0.05)
                if event and event['type'] == 'final':
                    finals[name] = event
        assert finals['good']['status'] == 'success'
        assert finals['bad']['status'] == 'error'
    finally:
        for proxy in (good, bad):
            proxy.stop()
            proxy.process.join(timeout=3)
            if proxy.process.is_alive():
                proxy.process.terminate()
                proxy.process.join(timeout=1)


def test_worker_checkpoint_is_encrypted_and_logs_are_redacted(tmp_path):
    from core.services.execution_worker import next_worker_event, spawn_execution_worker
    from core.services.player_secret_service import PlayerSecretService

    checkpoint_path = tmp_path / 'checkpoint.json'
    payload = _worker_payload(tmp_path, 'secret')
    payload['blueprint']['variables'] = {'password': 'top-secret'}
    payload['checkpoint_path'] = str(checkpoint_path)
    payload['checkpoint_storage_root'] = str(tmp_path)
    payload['redact_values'] = ['top-secret']
    payload['blueprint']['main_graph']['nodes'][0]['params']['message'] = 'password=top-secret'
    proxy = spawn_execution_worker(payload)
    final = None
    logs = []
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline and final is None:
            event = next_worker_event(proxy, 0.1)
            if not event:
                continue
            if event['type'] == 'ready':
                proxy.start_event.set()
            elif event['type'] == 'log':
                logs.append(event['log'])
            elif event['type'] == 'final':
                final = event
        assert final and final['status'] == 'success'
        assert all('top-secret' not in json.dumps(item, ensure_ascii=False) for item in logs)
        stored_text = checkpoint_path.read_text(encoding='utf-8')
        assert 'top-secret' not in stored_text
        checkpoint = PlayerSecretService.unprotect_document(json.loads(stored_text), str(tmp_path))
        assert checkpoint['variables']['password'] == 'top-secret'
    finally:
        proxy.stop()
        proxy.process.join(timeout=3)
        if proxy.process.is_alive():
            proxy.process.terminate()
            proxy.process.join(timeout=1)
