"""vNext target bridge for the format-6 bounded frame recorder."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
from PIL import Image

from .recorder_v6 import V6FrameRecorder, V6RecordingError, v6_frame_recorder
from .runtime import RuntimeFailure
from .target_runtime import create_target_driver
from .workspace_context import VNextWorkspaceError


class VNextRecordingService:
    def __init__(self, recorder: V6FrameRecorder | None = None) -> None:
        self._recorder = recorder or v6_frame_recorder
        self._start_lock = threading.Lock()

    @staticmethod
    def _pil_frame(frame: Any, *, bgr: bool) -> Image.Image:
        if isinstance(frame, Image.Image):
            return frame.convert('RGB')
        value = np.asarray(frame)
        if value.ndim == 3 and value.shape[2] == 4:
            value = value[:, :, [2, 1, 0, 3]] if bgr else value
            return Image.fromarray(value.astype(np.uint8), mode='RGBA').convert('RGB')
        if value.ndim == 3 and value.shape[2] == 3:
            value = value[:, :, ::-1] if bgr else value
            return Image.fromarray(value.astype(np.uint8), mode='RGB')
        return Image.fromarray(value.astype(np.uint8)).convert('RGB')

    def start(
        self,
        project_path: str,
        target: dict[str, Any] | None,
        options: dict[str, Any] | None = None,
        *,
        run_id: str = '',
        instance_id: str = 'ide',
        storage_root: str | None = None,
    ) -> dict[str, Any]:
        if target is None:
            raise VNextWorkspaceError('逐帧录制需要先选择一个可截图的运行目标')
        if target.get('type') == 'android_local':
            raise VNextWorkspaceError('Android 本机目标不能由 Windows IDE 录制')
        with self._start_lock:
            current = self._recorder.get_state()
            if current.get('active'):
                if str(current.get('project_path') or '').casefold() == str(project_path).casefold():
                    return current
                raise VNextWorkspaceError('已有其他项目正在逐帧录制')
            try:
                driver = create_target_driver(project_path, target)
                if driver is None:
                    raise RuntimeFailure('运行目标不支持截图')
            except RuntimeFailure as exc:
                raise VNextWorkspaceError(str(exc)) from exc

            release_lock = threading.Lock()
            released = False

            def release_driver() -> None:
                nonlocal released
                with release_lock:
                    if released:
                        return
                    released = True
                try:
                    driver.close()
                except Exception:
                    # Cleanup must remain exactly-once without replacing the
                    # original start/recording failure.
                    pass

            def capture() -> Image.Image:
                return self._pil_frame(driver.capture_frame(), bgr=bool(driver.frame_is_bgr))

            def target_snapshot() -> dict[str, Any]:
                # Target identity comes from the resolved target contract;
                # width/height/orientation are derived from every captured
                # frame by the recorder and create a new segment on change.
                return {
                    **target,
                    'target_id': str(target.get('target_id') or ''),
                    'target_kind': str(target.get('type') or driver.platform or ''),
                    'target_title': str(
                        target.get('name') or target.get('window_title') or target.get('target_id') or '运行目标'
                    ),
                }

            try:
                result = self._recorder.start(
                    project_path,
                    options,
                    capture_provider=capture,
                    capture_release=release_driver,
                    target_snapshot_provider=target_snapshot,
                    capture_backend=f'vnext:{target.get("type") or "unknown"}',
                    run_id=run_id,
                    instance_id=instance_id,
                    storage_root=storage_root,
                )
            except V6RecordingError as exc:
                release_driver()
                raise VNextWorkspaceError(str(exc)) from exc
            except Exception as exc:
                release_driver()
                raise VNextWorkspaceError(f'逐帧录制初始化失败：{exc}') from exc
            if not self._recorder.uses_capture_provider(capture):
                release_driver()
            return result

    def status(self, project_path: str) -> dict[str, Any]:
        state = self._recorder.get_state()
        if state.get('active') and str(state.get('project_path') or '').casefold() != str(project_path).casefold():
            return {**state, 'owned_by_current_workspace': False}
        return {**state, 'owned_by_current_workspace': True}

    def stop(self, project_path: str, reason: str = 'user') -> dict[str, Any]:
        state = self.status(project_path)
        if state.get('active') and not state.get('owned_by_current_workspace'):
            raise VNextWorkspaceError('不能从当前工作区停止其他项目的录制')
        return self._recorder.stop(reason)

    def mark(self, project_path: str, label: str) -> dict[str, Any]:
        state = self.status(project_path)
        if not state.get('active') or not state.get('owned_by_current_workspace'):
            raise VNextWorkspaceError('当前项目没有正在进行的逐帧录制')
        try:
            return self._recorder.mark_event(label)
        except V6RecordingError as exc:
            raise VNextWorkspaceError(str(exc)) from exc


vnext_recording_service = VNextRecordingService()
