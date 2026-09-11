"""Frozen-workspace capture sessions and asset transactions.

The capture UI is intentionally decoupled from the IDE window.  A global hotkey can
therefore create an immutable snapshot while the IDE is in the background, and a
small CaptureHost can edit that exact frame.  This module owns the short-lived
snapshot bytes and the reversible file transactions; canvas mutations remain in
the active IDE session and are acknowledged through the event bridge.
"""

from __future__ import annotations

import base64
import concurrent.futures
import contextlib
import io
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image

from core.security import assert_safe_path
from core.services.asset_service import AssetService

logger = logging.getLogger(__name__)


SNAPSHOT_TTL_SECONDS = 30 * 60
TRANSACTION_TTL_SECONDS = 2 * 60 * 60
SESSION_TTL_SECONDS = 90
PLAYER_SESSION_TTL_SECONDS = 10 * 60
MAX_RECTS = 32
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


@dataclass
class Snapshot:
    snapshot_id: str
    project_path: str
    project_id: str
    workspace_id: str
    workspace_generation: int
    png: bytes
    width: int
    height: int
    region: list[int]
    backend: str
    presentation: str = 'target_aligned'
    workspace_kind: str = 'legacy'
    session_id: str = ''
    source: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict, repr=False)
    semantic_future: concurrent.futures.Future | None = field(default=None, repr=False)
    image: Image.Image | None = field(default=None, repr=False)
    performance: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class AssetTransaction:
    transaction_id: str
    project_path: str
    project_id: str
    workspace_id: str
    workspace_generation: int
    created_files: list[str]
    overwritten: dict[str, bytes]
    registry_before: bytes | None
    workspace_kind: str = 'legacy'
    created_at: float = field(default_factory=time.time)
    undone: bool = False


class CaptureSessionService:
    _lock = threading.RLock()
    _trigger_lock = threading.Lock()
    _ui_sessions: dict[str, dict[str, Any]] = {}
    _snapshots: dict[str, Snapshot] = {}
    _transactions: dict[str, AssetTransaction] = {}
    _pending_actions: dict[str, dict[str, Any]] = {}
    _native_process: subprocess.Popen | None = None
    _native_host_title: str = ''
    _native_launch_error: str = ''
    _active_snapshot_id: str | None = None
    _semantic_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix='easycode-capture-semantic',
    )

    @staticmethod
    def _capture_adb_semantic(target: dict[str, Any]) -> dict[str, Any]:
        from core.vnext.android_control_v6 import AdbUiAutomatorAdapter

        started = time.perf_counter()
        adapter = AdbUiAutomatorAdapter(str(target.get('device_serial') or ''))
        nodes = adapter.snapshot()
        return {
            'nodes': nodes,
            'provider': adapter.provider,
            'tree_size': list(adapter.display_size),
            'duration_ms': round((time.perf_counter() - started) * 1000, 1),
        }

    @classmethod
    def _start_semantic_prefetch(
        cls,
        target: dict[str, Any],
        *,
        enabled: bool,
    ) -> concurrent.futures.Future | None:
        if not enabled or str(target.get('type') or '') != 'android_adb':
            return None
        return cls._semantic_executor.submit(cls._capture_adb_semantic, dict(target))

    @staticmethod
    def _frame_to_image(frame: Any, *, frame_is_bgr: bool) -> Image.Image:
        if isinstance(frame, Image.Image):
            return frame if frame.mode == 'RGB' else frame.convert('RGB')
        import numpy as np

        value = np.asarray(frame)
        if value.ndim == 3 and value.shape[2] == 4:
            value = value[:, :, [2, 1, 0, 3]] if frame_is_bgr else value
            return Image.fromarray(value.astype('uint8'), mode='RGBA').convert('RGB')
        if value.ndim == 3 and value.shape[2] == 3:
            value = value[:, :, ::-1] if frame_is_bgr else value
            return Image.fromarray(value.astype('uint8'), mode='RGB')
        return Image.fromarray(value.astype('uint8')).convert('RGB')

    @classmethod
    def _snapshot_png(cls, snapshot: Snapshot) -> bytes:
        if snapshot.png:
            return snapshot.png
        if snapshot.image is None:
            raise HTTPException(status_code=500, detail='冻结帧缺少可编码画面')
        started = time.perf_counter()
        buffer = io.BytesIO()
        snapshot.image.save(buffer, format='PNG', optimize=False, compress_level=1)
        encoded = buffer.getvalue()
        with cls._lock:
            if not snapshot.png:
                snapshot.png = encoded
                snapshot.performance['png_encode_ms'] = round((time.perf_counter() - started) * 1000, 1)
                snapshot.performance['png_encode_deferred'] = True
            return snapshot.png

    @classmethod
    def _capture_target_image(
        cls,
        project_path: str,
        target: dict[str, Any],
    ) -> tuple[Image.Image, list[int] | None, dict[str, Any], Any]:
        from core.services.capture_target_pool import capture_target_pool

        acquire_started = time.perf_counter()
        entry, reused = capture_target_pool.acquire('ide', project_path, target)
        acquire_ms = (time.perf_counter() - acquire_started) * 1000
        for attempt in range(2):
            frame_started = time.perf_counter()
            try:
                with entry.lock:
                    # A cached Windows driver keeps the stable HWND but refreshes
                    # geometry on every snapshot so moving/resizing a window never
                    # reuses stale coordinate space.
                    if str(target.get('type') or '') == 'windows' and hasattr(entry.driver, '_workspace_box'):
                        entry.driver._box = entry.driver._workspace_box()
                    frame = entry.driver.capture_frame()
                    overlay_region = entry.driver.capture_overlay_region()
                    frame_ms = (time.perf_counter() - frame_started) * 1000
                    convert_started = time.perf_counter()
                    image = cls._frame_to_image(frame, frame_is_bgr=bool(entry.driver.frame_is_bgr))
                    convert_ms = (time.perf_counter() - convert_started) * 1000
                    entry.last_used_at = time.monotonic()
                return image, overlay_region, {
                    'driver_acquire_ms': round(acquire_ms, 1),
                    'driver_reused': bool(reused),
                    'frame_ms': round(frame_ms, 1),
                    'frame_convert_ms': round(convert_ms, 1),
                    'driver_rebuilt': bool(attempt),
                }, entry.driver
            except Exception:
                capture_target_pool.invalidate(entry)
                if not reused or attempt:
                    raise
                acquire_started = time.perf_counter()
                entry, _ = capture_target_pool.acquire('ide', project_path, target, force_new=True)
                acquire_ms += (time.perf_counter() - acquire_started) * 1000
                reused = False
        raise RuntimeError('捕获驱动重建失败')

    @staticmethod
    def _replace_bytes(path: str, content: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = f'{path}.capture-restore-{uuid.uuid4().hex}.tmp'
        try:
            Path(temporary).write_bytes(content)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                with contextlib.suppress(OSError):
                    os.remove(temporary)

    @classmethod
    def _cleanup(cls) -> None:
        now = time.time()
        expired_snapshots = [
            item for item in cls._snapshots.values()
            if now - item.created_at > SNAPSHOT_TTL_SECONDS
        ]
        cls._snapshots = {
            key: item for key, item in cls._snapshots.items()
            if now - item.created_at <= SNAPSHOT_TTL_SECONDS
        }
        for item in expired_snapshots:
            if item.semantic_future is not None:
                item.semantic_future.cancel()
        cls._transactions = {
            key: item for key, item in cls._transactions.items()
            if now - item.created_at <= TRANSACTION_TTL_SECONDS
        }
        cls._ui_sessions = {
            key: item for key, item in cls._ui_sessions.items()
            if now - float(item.get('last_seen_at', 0)) <= (
                PLAYER_SESSION_TTL_SECONDS
                if str(item.get('workspace_kind') or '') == 'player'
                else SESSION_TTL_SECONDS
            )
        }

    @classmethod
    def register_ui_session(cls, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get('session_id') or '').strip()
        project_path = os.path.abspath(str(payload.get('project_path') or '').strip())
        if not session_id:
            raise HTTPException(status_code=400, detail='缺少 IDE 会话标识')
        if not project_path or not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='当前项目路径无效')
        now = time.time()
        record = {
            **payload,
            'session_id': session_id,
            'project_path': project_path,
            'last_seen_at': now,
            'last_focus_at': float(payload.get('last_focus_at') or now),
        }
        with cls._lock:
            cls._cleanup()
            cls._ui_sessions[session_id] = record
        return {'ok': True, 'session_id': session_id}

    @classmethod
    def unregister_ui_session(cls, session_id: str) -> dict[str, Any]:
        with cls._lock:
            cls._ui_sessions.pop(str(session_id or ''), None)
        return {'ok': True}

    @classmethod
    def active_ui_session(cls, session_id: str = '') -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            if not cls._ui_sessions:
                raise HTTPException(status_code=409, detail='没有可用的 IDE 项目会话')
            if session_id:
                selected = cls._ui_sessions.get(str(session_id))
                if selected is None:
                    raise HTTPException(status_code=409, detail='截图捕获会话已失效，请重试')
                active = dict(selected)
            else:
                sessions = sorted(
                    cls._ui_sessions.values(),
                    key=lambda item: (float(item.get('last_focus_at', 0)), float(item.get('last_seen_at', 0))),
                    reverse=True,
                )
                active = dict(sessions[0])
        workspace_kind = str(active.get('workspace_kind') or '')
        if workspace_kind == 'player':
            from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
            try:
                bound_path = vnext_player_bundle_manager.validate_player_capture_session(active)
            except PlayerBundleError as exc:
                raise HTTPException(status_code=409, detail=f'Player Capture 会话已失效: {exc}') from exc
        elif workspace_kind == 'vnext':
            from core.vnext import VNextWorkspaceError, vnext_workspace_manager
            try:
                bound_path = vnext_workspace_manager.require_path(
                    str(active.get('workspace_id') or ''),
                    int(active.get('workspace_generation') or -1), writable=True,
                )
            except (VNextWorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=f'IDE 项目会话已失效: {exc}') from exc
        else:
            from core.services.project_workspace_service import WorkspaceError, project_workspace_manager
            try:
                bound_path = project_workspace_manager.require(
                    str(active.get('workspace_id') or ''),
                    int(active.get('workspace_generation') or -1),
                    writable=True,
                )
            except (WorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=f'IDE 项目会话已失效: {exc}') from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(active['project_path'])):
            raise HTTPException(status_code=409, detail='IDE 捕获会话与当前项目不一致')
        state = str(active.get('execution_state') or 'idle')
        if state in {'queued', 'running', 'paused'}:
            raise HTTPException(status_code=409, detail='请先停止当前任务')
        if bool(active.get('recording_active')):
            raise HTTPException(status_code=409, detail='请先停止逐帧录制')
        return active

    @classmethod
    def create_snapshot(
        cls,
        project_path: str,
        *,
        session_id: str = '',
        include_image: bool = True,
        prefetch_control: bool = False,
    ) -> dict[str, Any]:
        capture_started = time.perf_counter()
        project_path = os.path.abspath(str(project_path or ''))
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')
        with cls._lock:
            session = dict(cls._ui_sessions.get(session_id) or {}) if session_id else {}
        workspace_kind = str(session.get('workspace_kind') or '')
        if workspace_kind == 'player':
            from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
            try:
                bound_path, target = vnext_player_bundle_manager.player_capture_target(session)
            except PlayerBundleError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            active = {
                'project_id': str(session.get('project_id') or ''),
                'workspace_id': str(session.get('workspace_id') or ''),
                'generation': int(session.get('workspace_generation') or 0),
            }
        elif workspace_kind == 'vnext':
            from core.vnext import VNextWorkspaceError, vnext_workspace_manager
            active = vnext_workspace_manager.active()
            try:
                if not active:
                    raise VNextWorkspaceError('当前没有打开vNext项目')
                bound_path = vnext_workspace_manager.require_path(
                    str(session.get('workspace_id') or ''),
                    int(session.get('workspace_generation') or -1), writable=True,
                )
            except (VNextWorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        else:
            from core.services.project_workspace_service import WorkspaceError, project_workspace_manager
            active = project_workspace_manager.active()
            try:
                if not active:
                    raise WorkspaceError('当前没有打开项目')
                bound_path = project_workspace_manager.require(
                    str(active.get('workspace_id') or ''),
                    int(active.get('generation') or -1), writable=True,
                )
            except (WorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(project_path)):
            raise HTTPException(status_code=409, detail='截图请求不属于当前工作区')
        if workspace_kind in {'vnext', 'player'}:
            from core.vnext import vnext_workspace_manager
            from core.vnext.player_bundle import PlayerBundleError
            from core.vnext.runtime import RuntimeFailure
            from core.vnext.target_service import TargetServiceError
            target_id = str((session.get('capture_context') or {}).get('target_id') or '')
            capture_purpose = str((session.get('capture_context') or {}).get('purpose') or '')
            semantic_future = None
            try:
                if workspace_kind == 'vnext' and capture_purpose == 'window_binding':
                    target = {
                        'target_id': 'target_window_capture_desktop',
                        'name': '窗口捕获桌面',
                        'type': 'windows',
                        'window_title': '',
                        'window_match': 'contains',
                        'work_area': {'mode': 'desktop'},
                        'allow_physical_fallback': True,
                    }
                elif workspace_kind == 'vnext':
                    target = vnext_workspace_manager.resolve_target(
                        str(session.get('workspace_id') or ''),
                        int(session.get('workspace_generation') or -1),
                        target_id,
                    )
                if target is None:
                    raise TargetServiceError('当前项目没有可截图的运行目标')
                semantic_future = cls._start_semantic_prefetch(
                    target,
                    enabled=prefetch_control,
                )
                image, overlay_region, capture_performance, capture_driver = cls._capture_target_image(
                    project_path, target,
                )
            except (PlayerBundleError, RuntimeFailure, TargetServiceError) as exc:
                if semantic_future is not None:
                    semantic_future.cancel()
                raise HTTPException(
                    status_code=409,
                    detail={
                        'code': 'capture_target_unavailable',
                        'message': str(exc),
                        'state': 'target_unavailable',
                        'target_id': target_id or None,
                    },
                ) from exc
            except Exception:
                if semantic_future is not None:
                    semantic_future.cancel()
                raise
            if include_image:
                encode_started = time.perf_counter()
                buffer = io.BytesIO()
                image.save(buffer, format='PNG', optimize=False, compress_level=1)
                png = buffer.getvalue()
                encode_ms = (time.perf_counter() - encode_started) * 1000
            else:
                # The native overlay consumes the owned RGB frame through
                # shared memory. PNG work is deferred until refresh/save needs
                # encoded bytes, outside click-to-overlay latency.
                png = b''
                encode_ms = 0.0
            target_aligned = (
                isinstance(overlay_region, list)
                and len(overlay_region) == 4
                and overlay_region[2] > overlay_region[0]
                and overlay_region[3] > overlay_region[1]
            )
            result = {
                'width': image.width, 'height': image.height,
                'region': overlay_region if target_aligned else [0, 0, image.width, image.height],
                'backend': f'{workspace_kind}:{str((target or {}).get("type") or "unknown")}',
                'presentation': 'target_aligned' if target_aligned else 'centered_fit',
            }
        else:
            from core.services.workspace_service import WorkspaceService
            result = WorkspaceService.capture_frozen_snapshot(project_path)
            png = result.pop('_png')
            result['presentation'] = 'target_aligned'
            target = {}
            semantic_future = None
            capture_driver = None
            capture_performance = {}
            encode_ms = 0.0
        snapshot_id = f'snap_{uuid.uuid4().hex}'
        window_candidates: list[dict[str, Any]] = []
        if workspace_kind == 'vnext' and str((session.get('capture_context') or {}).get('purpose') or '') == 'window_binding':
            from core.services.native_capture_overlay import native_capture_overlay
            from core.vnext.window_binding_v2 import enumerate_window_candidates

            window_candidates = enumerate_window_candidates(
                exclude_process_ids={os.getpid(), native_capture_overlay.process_id},
            )
        item = Snapshot(
            snapshot_id=snapshot_id,
            project_path=project_path,
            project_id=str(active.get('project_id') or ''),
            workspace_id=str(active['workspace_id']),
            workspace_generation=int(active['generation']),
            png=png,
            width=int(result['width']),
            height=int(result['height']),
            region=list(result.get('region') or [0, 0, result['width'], result['height']]),
            backend=str(result.get('backend') or 'unknown'),
            presentation=str(result.get('presentation') or 'target_aligned'),
            workspace_kind=workspace_kind or 'legacy',
            session_id=session_id,
            source={
                'target_id': (
                    str((target or {}).get('target_id') or '')
                    if workspace_kind in {'vnext', 'player'}
                    else ''
                ),
                'platform': str((target or {}).get('platform') or (target or {}).get('type') or '') if workspace_kind in {'vnext', 'player'} else '',
                'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'window_handle': (
                    int(getattr(capture_driver, 'hwnd', 0) or 0)
                    if capture_driver is not None
                    else 0
                ),
                'purpose': str((session.get('capture_context') or {}).get('purpose') or ''),
                'window_candidates': window_candidates,
            },
            target=dict(target or {}),
            semantic_future=semantic_future,
            image=image.copy() if workspace_kind in {'vnext', 'player'} else None,
            performance={
                **capture_performance,
                'png_encode_ms': round(encode_ms, 1),
                'png_encode_deferred': not bool(png),
                'capture_service_ms': round((time.perf_counter() - capture_started) * 1000, 1),
                'semantic_prefetch_started': semantic_future is not None,
            },
        )
        with cls._lock:
            cls._cleanup()
            cls._snapshots[snapshot_id] = item
            cls._active_snapshot_id = snapshot_id
        payload = {
            'snapshot_id': snapshot_id,
            'session_id': session_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            # Windows targets expose their exact physical desktop rectangle and
            # therefore enter capture without a visible jump or scale change.
            # Virtual targets (ADB/Android) have no desktop rectangle and use
            # the largest aspect-preserving centered projection instead.
            'presentation': item.presentation,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'expires_in': SNAPSHOT_TTL_SECONDS,
            'performance': dict(item.performance),
        }
        if include_image:
            payload['image'] = base64.b64encode(cls._snapshot_png(item)).decode('ascii')
        return payload

    @classmethod
    def resolve_window_capture(
        cls,
        payload: dict[str, Any],
        *,
        workspace_id: str,
        workspace_generation: int,
    ) -> dict[str, Any]:
        from core.vnext.window_binding_v2 import (
            WindowBindingResolutionError,
            candidate_at_screen_point,
            captured_binding,
        )

        snapshot_id = str(payload.get('snapshot_id') or '')
        session_id = str(payload.get('session_id') or '')
        with cls._lock:
            cls._cleanup()
            snapshot = cls._snapshots.get(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail='窗口捕获画面已过期，请重新捕获')
        if snapshot.session_id != session_id:
            raise HTTPException(status_code=409, detail='窗口捕获不属于当前项目会话')
        if snapshot.workspace_id != str(workspace_id) or snapshot.workspace_generation != int(workspace_generation):
            raise HTTPException(status_code=409, detail='窗口捕获工作区已经变化')
        if str(snapshot.source.get('purpose') or '') != 'window_binding':
            raise HTTPException(status_code=409, detail='当前冻结帧不是窗口捕获会话')
        point = payload.get('point')
        reference_size = payload.get('reference_size')
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise HTTPException(status_code=422, detail='窗口捕获点无效')
        if not isinstance(reference_size, (list, tuple)) or len(reference_size) != 2:
            raise HTTPException(status_code=422, detail='窗口捕获坐标空间无效')
        if (int(reference_size[0]), int(reference_size[1])) != (snapshot.width, snapshot.height):
            raise HTTPException(status_code=409, detail='窗口捕获画面尺寸已经变化，请重新捕获')
        clean_point = (int(point[0]), int(point[1]))
        if not (0 <= clean_point[0] < snapshot.width and 0 <= clean_point[1] < snapshot.height):
            raise HTTPException(status_code=422, detail='窗口捕获点超出冻结帧')
        region = snapshot.region
        screen_point = (int(region[0]) + clean_point[0], int(region[1]) + clean_point[1])
        try:
            candidate = candidate_at_screen_point(
                list(snapshot.source.get('window_candidates') or []), screen_point,
            )
        except WindowBindingResolutionError as exc:
            raise HTTPException(
                status_code=409,
                detail={'error_id': exc.error_id, 'message': str(exc), 'transient': exc.transient},
            ) from exc
        binding = captured_binding(candidate)
        return {
            'ok': True,
            'binding': binding,
            'title': str(candidate.get('title') or ''),
            'application': str(candidate.get('executable_name') or ''),
            'window_rect': list(candidate.get('rect') or []),
            'message': '已捕获当前窗口实例；保存设置后生效',
        }

    @classmethod
    def create_recording_snapshot(
        cls,
        project_path: str,
        recording_session_id: str,
        frame_index: int,
        *,
        session_id: str = '',
        include_image: bool = True,
    ) -> dict[str, Any]:
        """Register a historical frame as a normal immutable capture credential."""
        from core.services.recording_replay_service import recording_replay_service

        project_path = os.path.abspath(str(project_path or ''))
        with cls._lock:
            registered_session = dict(cls._ui_sessions.get(str(session_id or '')) or {})
        workspace_kind = str(registered_session.get('workspace_kind') or 'legacy')
        if workspace_kind == 'vnext':
            from core.vnext import VNextWorkspaceError, vnext_workspace_manager
            active = vnext_workspace_manager.active()
            try:
                if not active:
                    raise VNextWorkspaceError('当前没有打开vNext项目')
                bound_path = vnext_workspace_manager.require_path(
                    str(registered_session.get('workspace_id') or ''),
                    int(registered_session.get('workspace_generation') or -1),
                    writable=True,
                )
            except (VNextWorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        else:
            from core.services.project_workspace_service import WorkspaceError, project_workspace_manager
            active = project_workspace_manager.active()
            try:
                if not active:
                    raise WorkspaceError('当前没有打开项目')
                bound_path = project_workspace_manager.require(
                    str(active.get('workspace_id') or ''), int(active.get('generation') or -1), writable=True,
                )
            except (WorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(project_path)):
            raise HTTPException(status_code=409, detail='历史帧不属于当前工作区')

        frame = recording_replay_service.resolve_frame(project_path, recording_session_id, frame_index)
        png = Path(frame.path).read_bytes()
        try:
            with Image.open(io.BytesIO(png)) as image:
                width, height = image.size
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f'录制帧无法解码: {exc}') from exc
        raw_region = frame.record.get('screen_region')
        if isinstance(raw_region, list) and len(raw_region) == 4:
            region = [int(value) for value in raw_region]
        else:
            region = [0, 0, int(width), int(height)]
        if region[2] - region[0] != width or region[3] - region[1] != height:
            region = [region[0], region[1], region[0] + int(width), region[1] + int(height)]

        snapshot_id = f'snap_{uuid.uuid4().hex}'
        source = {
            'kind': 'recording',
            'recording_session_id': recording_session_id,
            'frame_index': int(frame_index),
            'captured_at': frame.record.get('captured_at', ''),
        }
        item = Snapshot(
            snapshot_id=snapshot_id,
            project_path=project_path,
            project_id=str(active.get('project_id') or ''),
            workspace_id=str(active['workspace_id']),
            workspace_generation=int(active['generation']),
            png=png,
            width=int(width),
            height=int(height),
            region=region,
            backend='recording_replay',
            presentation='centered_fit',
            workspace_kind=workspace_kind,
            session_id=session_id,
            source=source,
        )
        with cls._lock:
            cls._cleanup()
            if cls._active_snapshot_id and cls._active_snapshot_id in cls._snapshots:
                raise HTTPException(status_code=409, detail='请先退出当前截图捕获模式')
            cls._snapshots[snapshot_id] = item
            cls._active_snapshot_id = snapshot_id
        payload = {
            'snapshot_id': snapshot_id,
            'session_id': session_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'presentation': item.presentation,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'expires_in': SNAPSHOT_TTL_SECONDS,
            'source': source,
        }
        if include_image:
            payload['image'] = base64.b64encode(png).decode('ascii')
        return payload

    @classmethod
    def get_snapshot(cls, snapshot_id: str, *, include_image: bool = True) -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            item = cls._snapshots.get(snapshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail='冻结帧已过期，请按 R 重新捕获')
        result = {
            'snapshot_id': item.snapshot_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'presentation': item.presentation,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'session_id': item.session_id,
            'project_id': item.project_id,
            # 独立 Capture WebView 没有 IDE 页面内存中的工作区身份。冻结帧是
            # 不可猜测且已绑定工作区的短期凭据，用它把相同身份交给资源管理器，
            # 后续目录/缩略图请求才能走与 IDE 完全相同的并发保护。
            'workspace_id': item.workspace_id,
            'workspace_generation': item.workspace_generation,
            'workspace_kind': item.workspace_kind,
            'source': item.source,
        }
        if item.session_id:
            with cls._lock:
                session = dict(cls._ui_sessions.get(item.session_id) or {})
            result.update({
                'project_path': item.project_path,
                'project_name': session.get('project_name') or os.path.basename(item.project_path),
                'target_name': session.get('target_name') or '',
                'capture_context': session.get('capture_context') or {},
            })
        if include_image:
            result['image'] = base64.b64encode(cls._snapshot_png(item)).decode('ascii')
        return result

    @classmethod
    def validate_player_snapshot(
        cls,
        snapshot_id: str,
        session_id: str,
        rect: list[int] | None = None,
    ) -> dict[str, Any]:
        """Validate an opaque frozen-frame credential for the active Player session."""

        from core.vnext.player_bundle import PlayerBundleError

        with cls._lock:
            cls._cleanup()
            item = cls._snapshots.get(str(snapshot_id or ''))
        if item is None:
            raise PlayerBundleError('Player 冻结帧不存在或已过期')
        if item.workspace_kind != 'player' or item.session_id != str(session_id or ''):
            raise PlayerBundleError('Player 冻结帧属于另一采集会话')
        session = cls.active_ui_session(item.session_id)
        if str(session.get('project_id') or '') != item.project_id:
            raise PlayerBundleError('Player 冻结帧产品身份不一致')
        if rect is not None:
            try:
                cls._validate_rects([rect], item)
            except HTTPException as exc:
                raise PlayerBundleError(str(exc.detail)) from exc
        return {
            'snapshot_id': item.snapshot_id,
            'width': item.width,
            'height': item.height,
            'backend': item.backend,
            'source': dict(item.source),
        }

    @classmethod
    def player_snapshot_crop(
        cls,
        snapshot_id: str,
        session_id: str,
        rect: list[int],
    ) -> bytes:
        from core.vnext.player_bundle import PlayerBundleError

        cls.validate_player_snapshot(snapshot_id, session_id, rect)
        with cls._lock:
            item = cls._snapshots.get(str(snapshot_id or ''))
        if item is None:
            raise PlayerBundleError('Player 冻结帧已过期')
        x, y, width, height = cls._validate_rects([rect], item)[0]
        with Image.open(io.BytesIO(cls._snapshot_png(item))) as image:
            cropped = image.convert('RGB').crop((x, y, x + width, y + height))
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG', optimize=False)
            return buffer.getvalue()

    @classmethod
    def is_capture_active(cls) -> bool:
        with cls._lock:
            cls._cleanup()
            return bool(cls._active_snapshot_id and cls._active_snapshot_id in cls._snapshots)

    @classmethod
    def close_capture(cls, snapshot_id: str = '') -> dict[str, Any]:
        with cls._lock:
            if not snapshot_id or cls._active_snapshot_id == snapshot_id:
                cls._active_snapshot_id = None
        return {'ok': True}

    @classmethod
    def shutdown(cls) -> None:
        from core.services.capture_target_pool import capture_target_pool

        with cls._lock:
            pending = list(cls._pending_actions.values())
            snapshots = list(cls._snapshots.values())
            cls._pending_actions.clear()
            cls._snapshots.clear()
            cls._ui_sessions.clear()
            cls._active_snapshot_id = None
        for snapshot in snapshots:
            if snapshot.semantic_future is not None:
                snapshot.semantic_future.cancel()
        for item in pending:
            item['result'] = {'ok': False, 'message': '捕获服务正在关闭'}
            item['event'].set()
        capture_target_pool.close_owner('ide')

    @classmethod
    def prewarm_native_host(cls) -> dict[str, Any]:
        """Start the resident overlay and selected target provider while idle.

        Compilation only occurs in source checkouts and only when the C# sources
        are newer than the cached executable. No window is shown here; one frame
        is discarded so WGC/scrcpy lazy startup is paid before the first click.
        """
        from core.services.native_capture_overlay import native_capture_overlay

        native_capture_overlay.prewarm()
        with cls._lock:
            sessions = sorted(
                cls._ui_sessions.values(),
                key=lambda item: (float(item.get('last_focus_at', 0)), float(item.get('last_seen_at', 0))),
                reverse=True,
            )
            selected_session = dict(sessions[0]) if sessions else {}
            origin = str(selected_session.get('origin') or '')
        warm_result = native_capture_overlay.warm_resource_manager(origin) if origin else {
            'ok': False,
            'message': '尚未注册可用于预热的 IDE 页面',
        }
        target_ready = False
        target_performance: dict[str, Any] = {}
        target_message = ''
        if selected_session and str(selected_session.get('workspace_kind') or '') in {'vnext', 'player'}:
            target_started = time.perf_counter()
            try:
                session = cls.active_ui_session(str(selected_session.get('session_id') or ''))
                workspace_kind = str(session.get('workspace_kind') or '')
                if workspace_kind == 'player':
                    from core.vnext.player_bundle import vnext_player_bundle_manager

                    project_path, target = vnext_player_bundle_manager.player_capture_target(session)
                else:
                    from core.vnext import vnext_workspace_manager

                    project_path = str(session.get('project_path') or '')
                    target = vnext_workspace_manager.resolve_target(
                        str(session.get('workspace_id') or ''),
                        int(session.get('workspace_generation') or -1),
                        str((session.get('capture_context') or {}).get('target_id') or ''),
                    )
                _, _, target_performance, _ = cls._capture_target_image(project_path, target)
                target_ready = True
            except Exception as exc:
                target_message = str(exc)
                logger.info('[CaptureOverlay] target prewarm skipped: %s', exc)
            target_performance = {
                **target_performance,
                'prewarm_total_ms': round((time.perf_counter() - target_started) * 1000, 1),
            }
        with cls._lock:
            cls._native_process = native_capture_overlay.process
            cls._native_launch_error = native_capture_overlay.last_error
        return {
            'ok': native_capture_overlay.is_alive(),
            'resident': native_capture_overlay.is_alive(),
            'resource_manager_ready': bool(warm_result.get('ok')),
            'target_ready': target_ready,
            'target_performance': target_performance,
            'message': str(target_message or warm_result.get('message') or native_capture_overlay.last_error or ''),
        }

    @classmethod
    def _validate_rects(cls, rects: list[Any], snapshot: Snapshot) -> list[list[int]]:
        if not isinstance(rects, list) or not rects:
            raise HTTPException(status_code=400, detail='请先框选至少一个有效范围')
        if len(rects) > MAX_RECTS:
            raise HTTPException(status_code=400, detail=f'单个页面最多允许 {MAX_RECTS} 个特征范围')
        clean: list[list[int]] = []
        for raw in rects:
            if not isinstance(raw, (list, tuple)) or len(raw) != 4:
                raise HTTPException(status_code=400, detail='框选范围格式无效')
            try:
                x, y, width, height = [int(value) for value in raw]
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail='框选范围必须为整数') from exc
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise HTTPException(status_code=400, detail='框选范围必须位于工作面板内')
            if x + width > snapshot.width or y + height > snapshot.height:
                raise HTTPException(status_code=400, detail='框选范围超出冻结工作面板')
            clean.append([x, y, width, height])
        return clean

    @staticmethod
    def _validate_prefix(prefix: str) -> str:
        value = str(prefix or '').strip()
        if value.lower().endswith('.png'):
            value = value[:-4].rstrip()
        if not value:
            return ''
        if _INVALID_FILENAME.search(value) or value.endswith(('.', ' ')):
            raise HTTPException(status_code=400, detail='文件名包含 Windows 不允许的字符')
        if value.upper() in _RESERVED_NAMES:
            raise HTTPException(status_code=400, detail=f'“{value}”是 Windows 保留文件名')
        return value

    @staticmethod
    def _next_numbered_names(directory: str, prefix: str, count: int) -> list[str]:
        existing = {entry.name.casefold() for entry in Path(directory).glob('*.png')}
        names: list[str] = []
        number = 1
        while len(names) < count:
            suffix = f'{number:03d}' if number < 1000 else str(number)
            candidate = f'{prefix}{suffix}.png'
            if candidate.casefold() not in existing:
                names.append(candidate)
                existing.add(candidate.casefold())
            number += 1
        return names

    @staticmethod
    def _reference_hits(project_path: str, relative_path: str) -> list[dict[str, Any]]:
        template_key = relative_path.replace('\\', '/').removeprefix('templates/')
        try:
            registered = AssetService.resolve(project_path, template_key)
        except (FileNotFoundError, ValueError):
            return []
        asset_id = registered.get('asset_id')
        if not asset_id:
            return []
        needle = AssetService.reference(asset_id).casefold()
        hits: list[dict[str, Any]] = []
        for filename in ('workflow.json', 'topology.json'):
            path = os.path.join(project_path, filename)
            if not os.path.exists(path):
                continue
            try:
                text = Path(path).read_text(encoding='utf-8')
            except Exception:
                continue
            count = text.casefold().count(needle)
            if count:
                hits.append({'file': filename, 'count': count})
        return hits

    @classmethod
    def save_assets(cls, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(payload.get('snapshot_id') or '')
        with cls._lock:
            cls._cleanup()
            snapshot = cls._snapshots.get(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail='冻结帧已过期，请重新捕获')

        if snapshot.workspace_kind == 'player':
            raise HTTPException(status_code=409, detail='Player 私有图片只能通过字段确认路由提交')
        if snapshot.workspace_kind == 'vnext':
            return cls._save_vnext_assets(snapshot, payload)

        # The native overlay intentionally does not carry browser headers, so
        # bind its opaque snapshot back to the authoritative active workspace
        # before any project write. A snapshot from project A cannot write after
        # the IDE switches to project B.
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

        try:
            active_path = project_workspace_manager.require(
                snapshot.workspace_id,
                snapshot.workspace_generation,
                writable=True,
            )
        except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(active_path)) != os.path.normcase(os.path.realpath(snapshot.project_path)):
            raise HTTPException(status_code=409, detail='冻结帧属于已切换的旧项目，已拒绝保存')

        rects = cls._validate_rects(list(payload.get('rects') or []), snapshot)
        requested_category = str(payload.get('category') or 'image').strip().lower()
        if requested_category not in {'image', 'ocr', 'page'}:
            raise HTTPException(status_code=400, detail='资源分类必须为 image、ocr 或 page')

        templates_dir = os.path.join(snapshot.project_path, 'templates')
        relative_dir = str(payload.get('relative_dir') or requested_category).replace('\\', '/').strip('/')
        category = relative_dir.split('/', 1)[0].lower() if relative_dir else requested_category
        if category not in {'image', 'ocr', 'page'}:
            raise HTTPException(status_code=400, detail='资源必须保存到 image、ocr 或 page 根目录下')
        prefix = cls._validate_prefix(str(payload.get('prefix') or ''))
        collision = str(payload.get('collision') or 'ask')
        overwrite_confirmed = bool(payload.get('overwrite_confirmed'))

        target_dir = assert_safe_path(templates_dir, os.path.join(templates_dir, relative_dir))
        os.makedirs(target_dir, exist_ok=True)

        stamp = time.strftime('%Y%m%d_%H%M%S')
        if not prefix:
            prefix = f'{category}_{stamp}_feature_' if category == 'page' else f'{category}_{stamp}_'
            names = cls._next_numbered_names(target_dir, prefix, len(rects))
            if len(rects) == 1 and category != 'page':
                simple = f'{category}_{stamp}.png'
                if not os.path.exists(os.path.join(target_dir, simple)):
                    names = [simple]
        elif len(rects) > 1 or collision == 'sequence':
            names = cls._next_numbered_names(target_dir, prefix, len(rects))
        else:
            names = [f'{prefix}.png']

        paths = [assert_safe_path(templates_dir, os.path.join(target_dir, name)) for name in names]
        conflicts = []
        for path in paths:
            if os.path.exists(path):
                rel = os.path.relpath(path, snapshot.project_path).replace('\\', '/')
                conflicts.append({'path': rel, 'references': cls._reference_hits(snapshot.project_path, rel)})
        if conflicts and collision == 'ask':
            return {'ok': False, 'conflict': True, 'conflicts': conflicts, 'message': '目标文件已存在'}
        if conflicts and collision == 'cancel':
            raise HTTPException(status_code=409, detail='保存已取消，请修改文件名')
        if conflicts and collision == 'overwrite':
            referenced = [item for item in conflicts if item['references']]
            if referenced and not overwrite_confirmed:
                return {
                    'ok': False,
                    'conflict': True,
                    'requires_reference_confirmation': True,
                    'conflicts': conflicts,
                    'message': '资源已被流程引用，覆盖会改变所有引用位置',
                }
        elif conflicts:
            raise HTTPException(status_code=409, detail='目标文件已存在且未允许覆盖')

        image = Image.open(io.BytesIO(cls._snapshot_png(snapshot))).convert('RGB')
        registry_path = AssetService.registry_path(snapshot.project_path)
        registry_before = Path(registry_path).read_bytes() if os.path.exists(registry_path) else None
        asset_records: list[dict[str, Any]] = []
        created: list[str] = []
        overwritten: dict[str, bytes] = {}
        temp_paths: list[str] = []
        try:
            for path, rect in zip(paths, rects, strict=True):
                if os.path.exists(path):
                    overwritten[path] = Path(path).read_bytes()
                x, y, width, height = rect
                cropped = image.crop((x, y, x + width, y + height))
                temp_path = f'{path}.capture-{uuid.uuid4().hex}.tmp'
                cropped.save(temp_path, format='PNG')
                temp_paths.append(temp_path)
            for temp_path, path in zip(temp_paths, paths, strict=True):
                os.replace(temp_path, path)
                created.append(path)
            asset_records = AssetService.register_files(snapshot.project_path, [
                {
                    'relative_path': os.path.relpath(path, templates_dir).replace('\\', '/'),
                    'kind': category,
                    'capture': {
                        'region': rect,
                        'reference_size': [snapshot.width, snapshot.height],
                        'coordinate_space': 'workspace_px',
                        'snapshot_id': snapshot.snapshot_id,
                    },
                }
                for path, rect in zip(paths, rects, strict=True)
            ])
        except Exception as exc:
            for temp_path in temp_paths:
                if os.path.exists(temp_path):
                    with contextlib.suppress(OSError):
                        os.remove(temp_path)
            for path in created:
                try:
                    if path in overwritten:
                        cls._replace_bytes(path, overwritten[path])
                    elif os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
            if registry_before is None:
                if os.path.exists(registry_path):
                    with contextlib.suppress(OSError):
                        os.remove(registry_path)
            else:
                cls._replace_bytes(registry_path, registry_before)
            raise HTTPException(status_code=500, detail=f'资源事务保存失败，已回滚: {exc}') from exc

        transaction_id = f'asset_tx_{uuid.uuid4().hex}'
        tx = AssetTransaction(
            transaction_id=transaction_id,
            project_path=snapshot.project_path,
            project_id=snapshot.project_id,
            workspace_id=snapshot.workspace_id,
            workspace_generation=snapshot.workspace_generation,
            created_files=created,
            overwritten=overwritten,
            registry_before=registry_before,
        )
        with cls._lock:
            cls._transactions[transaction_id] = tx
        project_workspace_manager.acknowledge(snapshot.workspace_id, snapshot.workspace_generation)
        files = [os.path.relpath(path, snapshot.project_path).replace('\\', '/') for path in paths]
        return {
            'ok': True,
            'transaction_id': transaction_id,
            'files': files,
            'template_keys': [
                os.path.splitext(os.path.relpath(path, os.path.join(snapshot.project_path, 'templates')).replace('\\', '/'))[0]
                for path in paths
            ],
            'asset_ids': [record['id'] for record in asset_records],
            'asset_refs': [AssetService.reference(record['id']) for record in asset_records],
            'rects': rects,
            'reference_size': [snapshot.width, snapshot.height],
        }

    @classmethod
    def _save_vnext_assets(cls, snapshot: Snapshot, payload: dict[str, Any]) -> dict[str, Any]:
        """Commit capture crops into the vNext stable-id asset registry.

        Display-name collisions are handled like the desktop resource manager,
        while physical file names remain immutable asset ids. Capture rectangles
        are diagnostic provenance only; runtime regions belong to call arguments.
        """
        from core.vnext import vnext_workspace_manager

        with vnext_workspace_manager.project_transaction(
            snapshot.workspace_id, snapshot.workspace_generation, writable=True,
        ):
            result = cls._save_vnext_assets_locked(snapshot, payload)
        transaction = result.pop('_transaction', None)
        if transaction is None:
            # Name/reference conflicts are a successful preflight response, not
            # a partially-created transaction.  Keep them visible to the
            # capture UI instead of turning them into an internal KeyError.
            return result
        with cls._lock:
            cls._transactions[transaction.transaction_id] = transaction
        return result

    @classmethod
    def _save_vnext_assets_locked(cls, snapshot: Snapshot, payload: dict[str, Any]) -> dict[str, Any]:
        from core.vnext import VNextWorkspaceError, vnext_workspace_manager

        try:
            active_path = vnext_workspace_manager.require_path(
                snapshot.workspace_id, snapshot.workspace_generation, writable=True,
            )
        except (VNextWorkspaceError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(active_path)) != os.path.normcase(os.path.realpath(snapshot.project_path)):
            raise HTTPException(status_code=409, detail='冻结帧属于已切换的旧项目，已拒绝保存')

        rects = cls._validate_rects(list(payload.get('rects') or []), snapshot)
        requested_category = str(payload.get('category') or 'image').strip().lower()
        relative_dir = str(payload.get('relative_dir') or requested_category).replace('\\', '/').strip('/')
        parts = [part for part in relative_dir.split('/') if part]
        category = (parts[0] if parts else requested_category).lower()
        if category not in {'image', 'ocr', 'page'}:
            raise HTTPException(status_code=400, detail='资源必须保存到 image、ocr 或 page 根目录下')
        folder = '/'.join(parts[1:])
        prefix = cls._validate_prefix(str(payload.get('prefix') or ''))
        collision = str(payload.get('collision') or 'ask')
        overwrite_confirmed = bool(payload.get('overwrite_confirmed'))
        service = vnext_workspace_manager.asset_service(
            snapshot.workspace_id, snapshot.workspace_generation, writable=True,
        )
        listing = service.list()
        scoped_assets = [
            item for item in listing.get('assets', [])
            if item.get('category') == category and str(item.get('folder') or '') == folder
        ]
        existing_by_name = {
            str(item.get('display_name') or '').casefold(): item for item in scoped_assets
        }
        stamp = time.strftime('%Y%m%d_%H%M%S')
        if not prefix:
            prefix = f'{category}_{stamp}_feature' if category == 'page' else f'{category}_{stamp}'

        def numbered_names(base: str, count: int) -> list[str]:
            used = {str(item.get('display_name') or '').casefold() for item in scoped_assets}
            values: list[str] = []
            index = 1
            width = max(3, len(str(count)))
            while len(values) < count:
                candidate = f'{base}{index:0{width}d}'
                if candidate.casefold() not in used:
                    values.append(candidate)
                    used.add(candidate.casefold())
                index += 1
            return values

        explicit_single = bool(str(payload.get('prefix') or '').strip()) and len(rects) == 1
        if len(rects) > 1 or collision == 'sequence':
            display_names = numbered_names(prefix, len(rects))
        else:
            display_names = [prefix]

        conflicts: list[dict[str, Any]] = []
        for name in display_names:
            existing = existing_by_name.get(name.casefold())
            if existing:
                try:
                    references = service.references(str(existing.get('asset_id') or ''))
                except VNextWorkspaceError as exc:
                    # Overwrite impact is fail-closed. A damaged ProgramDocument
                    # must never be interpreted as an unreferenced resource.
                    raise HTTPException(
                        status_code=409,
                        detail=f'无法检查同名资源引用，已拒绝覆盖：{exc}',
                    ) from exc
                conflicts.append({
                    'path': f'{category}/{folder}/{name}'.replace('//', '/'),
                    'asset_id': existing.get('asset_id'),
                    'references': references,
                })
        if conflicts and collision == 'ask':
            return {'ok': False, 'conflict': True, 'conflicts': conflicts, 'message': '同目录下已有同名资源'}
        if conflicts and collision == 'cancel':
            raise HTTPException(status_code=409, detail='保存已取消，请修改资源名称')
        if conflicts and collision == 'overwrite':
            referenced = [item for item in conflicts if item['references']]
            if referenced and not overwrite_confirmed:
                return {
                    'ok': False, 'conflict': True, 'requires_reference_confirmation': True,
                    'conflicts': conflicts, 'message': '资源已被 ProgramDocument 引用，覆盖会影响所有引用位置',
                }
        elif conflicts:
            raise HTTPException(status_code=409, detail='资源名称冲突且未允许覆盖')

        registry_path = service.registry_path
        registry_before = Path(registry_path).read_bytes() if os.path.exists(registry_path) else None
        image = Image.open(io.BytesIO(cls._snapshot_png(snapshot))).convert('RGB')
        created_files: list[str] = []
        overwritten: dict[str, bytes] = {}
        records: list[dict[str, Any]] = []
        try:
            for name, rect in zip(display_names, rects, strict=True):
                x, y, width, height = rect
                crop = image.crop((x, y, x + width, y + height))
                buffer = io.BytesIO()
                crop.save(buffer, format='PNG', optimize=False)
                encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
                capture = {
                    **snapshot.source,
                    'work_area': snapshot.region,
                    'selection_rect': rect,
                    'reference_size': [snapshot.width, snapshot.height],
                    'coordinate_space': 'workspace_px',
                    'host': snapshot.backend,
                }
                existing = existing_by_name.get(name.casefold()) if explicit_single else None
                if existing and collision == 'overwrite':
                    old_path, _ = service.content_path(str(existing['asset_id']))
                    overwritten[old_path] = Path(old_path).read_bytes()
                    result = service.replace_base64(
                        str(existing['asset_id']), file_name=f'{name}.png', content_base64=encoded,
                        source='capture', capture=capture,
                    )
                else:
                    result = service.import_base64(
                        category=category, folder=folder, file_name=f'{name}.png', display_name=name,
                        content_base64=encoded, source='capture', capture=capture,
                    )
                item = dict(result['asset'])
                path = service._absolute(str(item['path']))
                created_files.append(path)
                records.append(item)
        except Exception as exc:
            for path in created_files:
                try:
                    if path in overwritten:
                        cls._replace_bytes(path, overwritten[path])
                    elif os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
            if registry_before is not None:
                cls._replace_bytes(registry_path, registry_before)
            raise HTTPException(status_code=500, detail=f'资源事务保存失败，已回滚: {exc}') from exc

        transaction_id = f'asset_tx_{uuid.uuid4().hex}'
        transaction = AssetTransaction(
            transaction_id=transaction_id, project_path=snapshot.project_path,
            project_id=snapshot.project_id, workspace_id=snapshot.workspace_id,
            workspace_generation=snapshot.workspace_generation, created_files=created_files,
            overwritten=overwritten, registry_before=registry_before, workspace_kind='vnext',
        )
        return {
            'ok': True, 'transaction_id': transaction_id,
            'files': [str(item.get('path') or '') for item in records],
            'template_keys': [],
            'asset_ids': [str(item['asset_id']) for item in records],
            'asset_refs': [f'asset://{item["asset_id"]}' for item in records],
            # 让 IDE 增量合并本次提交，避免确认前重新读取全项目资源。
            'assets': records,
            'rects': rects, 'reference_size': [snapshot.width, snapshot.height],
            '_transaction': transaction,
        }

    @classmethod
    def undo_assets(cls, transaction_id: str) -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            tx = cls._transactions.get(str(transaction_id or ''))
            if tx is None:
                raise HTTPException(status_code=404, detail='资源事务不存在或已过期')
            if tx.undone:
                return {'ok': True, 'already_undone': True}
            if tx.workspace_kind == 'vnext':
                from core.vnext import VNextWorkspaceError, vnext_workspace_manager
                try:
                    active_path = vnext_workspace_manager.require_path(
                        tx.workspace_id, tx.workspace_generation, writable=True,
                    )
                except (VNextWorkspaceError, KeyError, TypeError, ValueError) as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                registry_path = os.path.join(tx.project_path, 'assets', 'registry.json')
                acknowledge = None
            else:
                from core.services.project_workspace_service import WorkspaceError, project_workspace_manager
                try:
                    active_path = project_workspace_manager.require(
                        tx.workspace_id, tx.workspace_generation, writable=True,
                    )
                except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                registry_path = AssetService.registry_path(tx.project_path)
                acknowledge = project_workspace_manager.acknowledge
            if os.path.normcase(os.path.realpath(active_path)) != os.path.normcase(os.path.realpath(tx.project_path)):
                raise HTTPException(status_code=409, detail='资源事务属于已切换的旧项目，已拒绝撤销')
            files_before = {
                path: (Path(path).read_bytes() if os.path.exists(path) else None)
                for path in tx.created_files
            }
            registry_current = Path(registry_path).read_bytes() if os.path.exists(registry_path) else None
            try:
                for path in tx.created_files:
                    if path in tx.overwritten:
                        cls._replace_bytes(path, tx.overwritten[path])
                    elif os.path.exists(path):
                        os.remove(path)
                if tx.registry_before is None:
                    if os.path.exists(registry_path):
                        os.remove(registry_path)
                else:
                    cls._replace_bytes(registry_path, tx.registry_before)
            except Exception as exc:
                # Restore the state from immediately before undo, so Ctrl+Z is
                # retryable and never leaves half of an asset batch reverted.
                for path, content in files_before.items():
                    try:
                        if content is None:
                            if os.path.exists(path):
                                os.remove(path)
                        else:
                            cls._replace_bytes(path, content)
                    except OSError:
                        pass
                try:
                    if registry_current is None:
                        if os.path.exists(registry_path):
                            os.remove(registry_path)
                    else:
                        cls._replace_bytes(registry_path, registry_current)
                except OSError:
                    pass
                raise HTTPException(status_code=500, detail=f'资源撤销失败，已恢复撤销前状态: {exc}') from exc
            tx.undone = True
            if acknowledge is not None:
                acknowledge(tx.workspace_id, tx.workspace_generation)
            return {
                'ok': True,
                'restored': len(tx.overwritten),
                'deleted': len(tx.created_files) - len(tx.overwritten),
            }

    @classmethod
    def request_ide_action(cls, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        if str(payload.get('kind') or '') == 'field_control_probe':
            return cls._resolve_control_probe(payload)

        from core.services import capture_mode

        started = time.perf_counter()
        request_id = f'capture_req_{uuid.uuid4().hex}'
        done = threading.Event()
        pending = {'event': done, 'result': None}
        with cls._lock:
            cls._pending_actions[request_id] = pending
        capture_mode.publish_event({
            'event': 'capture-command',
            'request_id': request_id,
            **payload,
        })
        if not done.wait(max(1.0, float(timeout))):
            with cls._lock:
                cls._pending_actions.pop(request_id, None)
            operation_id = str(payload.get('operation_id') or '')
            if operation_id and payload.get('kind') not in {'undo', 'rollback_operation'}:
                # SSE preserves publish order. The IDE serializes capture commands,
                # so a late original commit is immediately compensated instead of
                # leaving a node that references assets already rolled back by Host.
                capture_mode.publish_event({
                    'event': 'capture-command',
                    'request_id': f'capture_rollback_{uuid.uuid4().hex}',
                    **payload,
                    'kind': 'rollback_operation',
                    'operation_id': operation_id,
                })
            logger.warning(
                '[CaptureAction] timeout request=%s kind=%s elapsed=%.1fms',
                request_id,
                str(payload.get('kind') or ''),
                (time.perf_counter() - started) * 1000,
            )
            raise HTTPException(status_code=504, detail='IDE 未响应捕获操作，请确认项目仍处于打开状态')
        with cls._lock:
            result = pending.get('result') or {'ok': False, 'message': 'IDE 返回了空结果'}
            cls._pending_actions.pop(request_id, None)
        logger.info(
            '[CaptureAction] acknowledged request=%s kind=%s ok=%s elapsed=%.1fms',
            request_id,
            str(payload.get('kind') or ''),
            bool(result.get('ok')),
            (time.perf_counter() - started) * 1000,
        )
        return result

    @classmethod
    def _resolve_control_probe(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve a snapshot-bound control point without a browser/SSE round trip."""

        started = time.perf_counter()
        snapshot_id = str(payload.get('snapshot_id') or '')
        session_id = str(payload.get('session_id') or '')
        with cls._lock:
            cls._cleanup()
            snapshot = cls._snapshots.get(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail='冻结帧已过期，请按 R 重新捕获')
        if not snapshot.session_id or snapshot.session_id != session_id:
            raise HTTPException(status_code=409, detail='控件捕获不属于当前项目会话')
        session = cls.active_ui_session(session_id)
        if (
            str(session.get('workspace_id') or '') != snapshot.workspace_id
            or int(session.get('workspace_generation') or -1) != snapshot.workspace_generation
        ):
            raise HTTPException(status_code=409, detail='控件捕获工作区版本已经变化')
        point = payload.get('point')
        reference_size = payload.get('reference_size')
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise HTTPException(status_code=422, detail='控件捕获点无效')
        if not isinstance(reference_size, (list, tuple)) or len(reference_size) != 2:
            raise HTTPException(status_code=422, detail='控件捕获坐标空间无效')
        expected_size = (snapshot.width, snapshot.height)
        requested_size = (int(reference_size[0]), int(reference_size[1]))
        if requested_size != expected_size:
            raise HTTPException(status_code=409, detail='冻结帧尺寸已变化，请按 R 重新捕获')
        clean_point = (int(point[0]), int(point[1]))
        if not (0 <= clean_point[0] < snapshot.width and 0 <= clean_point[1] < snapshot.height):
            raise HTTPException(status_code=422, detail='控件捕获点超出冻结帧')
        if not snapshot.target:
            raise HTTPException(status_code=409, detail='当前冻结帧没有可解析的控件目标')

        semantic_snapshot = None
        semantic_wait_ms = 0.0
        semantic_prefetched = False
        if snapshot.semantic_future is not None:
            wait_started = time.perf_counter()
            try:
                semantic = snapshot.semantic_future.result(timeout=5.0)
                semantic_snapshot = semantic.get('nodes')
                semantic_prefetched = True
            except concurrent.futures.TimeoutError as exc:
                raise HTTPException(status_code=504, detail='控件树读取超时，请重试或按 R 刷新') from exc
            except Exception as exc:
                logger.warning('[CaptureControl] semantic prefetch failed snapshot=%s: %s', snapshot_id, exc)
                # Keep the mature path recoverable: the resolver performs one
                # bounded live query when the background snapshot failed.
                semantic_snapshot = None
            semantic_wait_ms = (time.perf_counter() - wait_started) * 1000
        try:
            from core.vnext.control_capture_v6 import ControlCaptureError, resolve_control_candidates
            from core.services.native_capture_overlay import native_capture_overlay

            resolve_started = time.perf_counter()
            candidates = resolve_control_candidates(
                snapshot.project_path,
                snapshot.target,
                clean_point,
                requested_size,
                capture_region=snapshot.region,
                expected_hwnd=int(snapshot.source.get('window_handle') or 0),
                semantic_snapshot=semantic_snapshot,
                exclude_process_ids={native_capture_overlay.process_id},
            )
            resolve_ms = (time.perf_counter() - resolve_started) * 1000
        except ControlCaptureError as exc:
            raise HTTPException(
                status_code=409,
                detail={'error_id': exc.error_id, 'message': str(exc), 'transient': exc.transient},
            ) from exc
        performance = {
            'semantic_prefetched': semantic_prefetched,
            'semantic_wait_ms': round(semantic_wait_ms, 1),
            'control_resolve_ms': round(resolve_ms, 1),
            'control_total_ms': round((time.perf_counter() - started) * 1000, 1),
        }
        logger.info(
            '[CaptureControl] resolved snapshot=%s backend=%s candidates=%d prefetched=%s wait=%.1fms resolve=%.1fms total=%.1fms',
            snapshot_id,
            snapshot.backend,
            len(candidates),
            semantic_prefetched,
            performance['semantic_wait_ms'],
            performance['control_resolve_ms'],
            performance['control_total_ms'],
        )
        return {'ok': True, 'candidates': candidates, 'performance': performance}

    @classmethod
    def acknowledge_ide_action(cls, request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with cls._lock:
            pending = cls._pending_actions.get(str(request_id or ''))
            if pending is None:
                raise HTTPException(status_code=404, detail='捕获操作请求不存在或已超时')
            pending['result'] = result
            pending['event'].set()
        return {'ok': True}

    @classmethod
    def trigger_recording_capture(
        cls, recording_session_id: str, frame_index: int, ui_session_id: str = '',
    ) -> dict[str, Any]:
        """Open a historical frame without activating or recapturing the target window."""
        with cls._trigger_lock:
            from core.services import capture_mode
            from core.services.execution_service import ExecutionService
            from core.services.frame_recording_service import frame_recording_service

            session = cls.active_ui_session(ui_session_id)
            # vNext reports execution state through its own registered UI
            # session. A stale legacy executor must not block an unrelated
            # vNext parameter capture.
            if str(session.get('workspace_kind') or '') not in {'vnext', 'player'} and ExecutionService.has_active_execution():
                raise HTTPException(status_code=409, detail='请先停止当前任务')
            if frame_recording_service.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先停止逐帧录制')
            if capture_mode.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先退出控件捕获模式')
            snapshot = cls.create_recording_snapshot(
                session['project_path'], recording_session_id, frame_index,
                session_id=session['session_id'], include_image=False,
            )
            if not cls._launch_native_host(session, snapshot):
                with cls._lock:
                    cls._snapshots.pop(snapshot['snapshot_id'], None)
                    if cls._active_snapshot_id == snapshot['snapshot_id']:
                        cls._active_snapshot_id = None
                raise HTTPException(
                    status_code=409,
                    detail=f'桌面捕获宿主启动失败：{cls._native_launch_error or "未知错误"}',
                )
            capture_mode.publish_event({
                'event': 'screenshot-capture',
                'session_id': session['session_id'],
                'snapshot': snapshot,
                'capture_context': session.get('capture_context') or {},
                'project_name': session.get('project_name') or os.path.basename(session['project_path']),
                'target_name': f'历史帧 #{int(frame_index)}',
                'native_host': True,
                'source': snapshot.get('source'),
            })
            return {'ok': True, 'native_host': True, **snapshot}

    @classmethod
    def trigger_global_capture(cls, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Called from the RegisterHotKey worker; never blocks that window thread."""
        with cls._trigger_lock:
            return cls._trigger_global_capture_locked(options or {})

    @classmethod
    def _trigger_global_capture_locked(cls, options: dict[str, Any] | None = None) -> dict[str, Any]:
        started_at = time.perf_counter()
        session: dict[str, Any] = {}
        options = options or {}
        field_capture = options.get('field_capture')
        if field_capture is not None and not isinstance(field_capture, dict):
            raise HTTPException(status_code=400, detail='属性捕获请求格式无效')
        try:
            from core.services import capture_mode
            from core.services.execution_service import ExecutionService
            from core.services.frame_recording_service import frame_recording_service

            session = cls.active_ui_session(str(options.get('session_id') or ''))
            if field_capture:
                request_id = str(field_capture.get('request_id') or '').strip()
                selection_mode = str(field_capture.get('selection_mode') or '').strip()
                category = str(field_capture.get('category') or '').strip()
                destination = str(field_capture.get('destination') or 'parameter').strip()
                if not request_id or selection_mode not in {'point', 'region', 'asset', 'color', 'path', 'control'}:
                    raise HTTPException(status_code=400, detail='属性捕获请求缺少必要参数')
                if selection_mode == 'asset' and category not in {'image', 'ocr', 'page'}:
                    raise HTTPException(status_code=400, detail='属性捕获资源分类无效')
                if destination not in {'parameter', 'resource'}:
                    raise HTTPException(status_code=400, detail='属性捕获目的地无效')
                if destination == 'resource' and selection_mode != 'asset':
                    raise HTTPException(status_code=400, detail='独立资源录入只支持图片框选')
                field_capture = {
                    'requestId': request_id,
                    'selectionMode': selection_mode,
                    'category': category,
                    'destination': destination,
                    'maxRects': max(1, min(MAX_RECTS, int(field_capture.get('max_rects') or 1))),
                    'title': str(field_capture.get('title') or '属性捕获'),
                }
                session = dict(session)
                session_context = dict(session.get('capture_context') or {})
                session_context['fieldCapture'] = field_capture
                session['capture_context'] = session_context
            if str(session.get('workspace_kind') or '') not in {'vnext', 'player'} and ExecutionService.has_active_execution():
                raise HTTPException(status_code=409, detail='请先停止当前任务')
            if frame_recording_service.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先停止逐帧录制')
            if capture_mode.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先退出控件捕获模式')
            with cls._lock:
                active_id = cls._active_snapshot_id
                active = cls._snapshots.get(active_id or '')
                from core.services.native_capture_overlay import native_capture_overlay

                native_alive = native_capture_overlay.is_alive()
            if active is not None:
                # The native host may have already closed without completing
                # its browser acknowledgement. Never let that stale snapshot
                # permanently block every later field capture.
                if field_capture and native_alive:
                    raise HTTPException(status_code=409, detail='请先完成或退出当前截图捕获模式')
                focused = native_alive and cls._focus_native_host()
                usable_native = bool(native_alive and focused)
                if usable_native:
                    capture_mode.publish_event({
                        'event': 'screenshot-focus',
                        'session_id': active.session_id or session['session_id'],
                        'snapshot_id': active.snapshot_id,
                        'native_host': True,
                        'focused': True,
                    })
                    return {
                        'ok': True,
                        'already_active': True,
                        'native_host': True,
                        'focused': True,
                        'snapshot_id': active.snapshot_id,
                    }
                # A dead/unfocusable native window must not strand an active
                # snapshot and trigger the old browser-centered fallback.
                with cls._lock:
                    cls._active_snapshot_id = None
                    cls._snapshots.pop(active.snapshot_id, None)
            snapshot = cls.create_snapshot(
                session['project_path'],
                session_id=session['session_id'],
                include_image=False,
                prefetch_control=bool(field_capture and field_capture.get('selectionMode') == 'control'),
            )
            captured_at = time.perf_counter()
            launched = cls._launch_native_host(session, snapshot)
            if not launched:
                with cls._lock:
                    cls._snapshots.pop(snapshot['snapshot_id'], None)
                    if cls._active_snapshot_id == snapshot['snapshot_id']:
                        cls._active_snapshot_id = None
                reason = cls._native_launch_error or '未知启动错误'
                raise HTTPException(status_code=409, detail=f'桌面捕获宿主启动失败：{reason}')
            from core.services.native_capture_overlay import native_capture_overlay
            show_performance = native_capture_overlay.last_show_performance
            event_snapshot = {key: value for key, value in snapshot.items() if key != 'image'}
            payload = {
                'event': 'screenshot-capture',
                'session_id': session['session_id'],
                'snapshot': event_snapshot,
                'capture_context': session.get('capture_context') or {},
                'project_name': session.get('project_name') or os.path.basename(session['project_path']),
                'target_name': session.get('target_name') or '',
                'performance': {
                    **dict(snapshot.get('performance') or {}),
                    'capture_ms': round((captured_at - started_at) * 1000, 1),
                    'host_ms': round((time.perf_counter() - captured_at) * 1000, 1),
                    **show_performance,
                    'total_ms': round((time.perf_counter() - started_at) * 1000, 1),
                },
            }
            payload['native_host'] = True
            capture_mode.publish_event(payload)
            performance = payload['performance']
            logger.info(
                '[CaptureOverlay] ready backend=%s capture=%.1fms host=%.1fms total=%.1fms',
                snapshot.get('backend'),
                performance['capture_ms'],
                performance['host_ms'],
                performance['total_ms'],
            )
            return {
                'ok': True,
                'native_host': True,
                'snapshot_id': snapshot['snapshot_id'],
                'performance': performance,
            }
        except HTTPException as exc:
            from core.services import capture_mode

            capture_mode.publish_event({
                'event': 'screenshot-error',
                'session_id': session.get('session_id'),
                'message': str(exc.detail),
            })
            raise
        except Exception as exc:
            from core.services import capture_mode

            capture_mode.publish_event({
                'event': 'screenshot-error',
                'session_id': session.get('session_id'),
                'message': f'截图捕获失败: {exc}',
            })
            raise

    @classmethod
    def _focus_native_host(cls) -> bool:
        from core.services.native_capture_overlay import native_capture_overlay

        return native_capture_overlay.focus()

    @classmethod
    def _launch_native_host(cls, session: dict[str, Any], snapshot: dict[str, Any]) -> bool:
        from core.services.native_capture_overlay import native_capture_overlay

        cls._native_launch_error = ''
        origin = str(session.get('origin') or '').rstrip('/')
        if not origin.startswith(('http://', 'https://')):
            cls._native_launch_error = 'IDE 页面地址无效'
            return False
        with cls._lock:
            item = cls._snapshots.get(str(snapshot.get('snapshot_id') or ''))
        if item is None:
            cls._native_launch_error = '冻结帧在显示前已经失效'
            return False
        result = native_capture_overlay.show(
            session,
            snapshot,
            item.png,
            image=item.image,
        )
        with cls._lock:
            cls._native_process = native_capture_overlay.process
            cls._native_launch_error = str(result.get('message') or native_capture_overlay.last_error or '')
        return bool(result.get('ok'))


capture_session_service = CaptureSessionService
