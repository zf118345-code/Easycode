from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.services.workspace_service import WorkspaceService


def completed(stdout: str, returncode: int = 0, stderr: str = ''):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_resolve_adb_uses_only_online_device():
    with patch('core.services.workspace_service.subprocess.run', return_value=completed('List of devices attached\nemulator-5554\tdevice\n')):
        result = WorkspaceService.resolve_adb_device('雷电模拟器')
    assert result['serial'] == 'emulator-5554'
    assert result['method'] == 'single_online_device'


def test_resolve_adb_rejects_ambiguous_multiple_devices():
    responses = [completed('List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n')]
    responses.extend(completed('generic\n') for _ in range(8))
    with patch('core.services.workspace_service.subprocess.run', side_effect=responses):
        with pytest.raises(HTTPException) as error:
            WorkspaceService.resolve_adb_device('雷电模拟器')
    assert error.value.status_code == 409
    assert '无法根据窗口标题' in error.value.detail


def test_android_device_list_reports_current_rotated_viewport():
    responses = [
        completed(
            'List of devices attached\n'
            'emulator-5554 device product:demo model:Demo_Phone device:demo transport_id:1\n'
        ),
        completed('Physical size: 720x1280\n'),
        completed(
            'DisplayViewport[id=0]\n'
            '  Width=1280, Height=720\n'
            '  Transform (ROT_270)\n'
            '  Orientation: 3\n'
        ),
        completed('14\n'),
    ]
    with patch('core.services.workspace_service.subprocess.run', side_effect=responses):
        device = WorkspaceService.get_adb_devices()['devices'][0]
    assert device['width'] == 1280
    assert device['height'] == 720
    assert device['natural_width'] == 720
    assert device['natural_height'] == 1280
    assert device['rotation'] == 3
    assert device['capture_tier'] == 'scrcpy_latest_frame'
