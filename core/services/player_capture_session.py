"""Minimal frozen-frame service for the independently packaged Player.

Unlike the IDE capture service this module has no project workspace, authoring,
asset-editor, replay, or legacy execution dependencies.  It owns only the
opaque snapshot and SSE acknowledgement bridge required by published Player
field actions.
"""

from __future__ import annotations

import concurrent.futures
import io
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from PIL import Image


SNAPSHOT_TTL_SECONDS = 30 * 60
PLAYER_SESSION_TTL_SECONDS = 10 * 60


@dataclass
class PlayerSnapshot:
    snapshot_id: str
    project_path: str
    project_id: str
    workspace_id: str
    workspace_generation: int
    session_id: str
    png: bytes
    width: int
    height: int
    region: list[int]
    backend: str
    presentation: str = 'target_aligned'
    source: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict, repr=False)
    semantic_future: concurrent.futures.Future | None = field(default=None, repr=False)
    image: Image.Image | None = field(default=None, repr=False)
    performance: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class PlayerCaptureSessionService:
    _lock = threading.RLock()
    _trigger_lock = threading.Lock()
    _ui_sessions: dict[str, dict[str, Any]] = {}
    _snapshots: dict[str, PlayerSnapshot] = {}
    _pending_actions: dict[str, dict[str, Any]] = {}
    _active_snapshot_id: str | None = None
    _semantic_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix='easycode-player-capture-semantic',
    )

    @staticmethod
    def _capture_adb_semantic(target: dict[str, Any]) -> dict[str, Any]:
        from core.vnext.android_control_v6 import AdbUiAutomatorAdapter

        started = time.perf_counter()
        adapter = AdbUiAutomatorAdapter(str(target.get('device_serial') or ''))
        nodes = adapter.snapshot()
        return {
            'nodes': nodes,
            'duration_ms': round((time.perf_counter() - started) * 1000, 1),
        }

    @classmethod
    def _cleanup(cls) -> None:
        now = time.time()
        expired = [
            item for item in cls._snapshots.values()
            if now - item.created_at > SNAPSHOT_TTL_SECONDS
        ]
        cls._snapshots = {
            key: item for key, item in cls._snapshots.items()
            if now - item.created_at <= SNAPSHOT_TTL_SECONDS
        }
        for item in expired:
            if item.semantic_future is not None:
                item.semantic_future.cancel()
        cls._ui_sessions = {
            key: item for key, item in cls._ui_sessions.items()
            if now - float(item.get('last_seen_at', 0)) <= PLAYER_SESSION_TTL_SECONDS
        }
        if cls._active_snapshot_id not in cls._snapshots:
            cls._active_snapshot_id = None

    @classmethod
    def register_ui_session(cls, payload: dict[str, Any]) -> dict[str, Any]:
        from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager

        session_id = str(payload.get('session_id') or '').strip()
        if not session_id:
            raise HTTPException(status_code=400, detail='缺少 Player Capture 会话标识')
        try:
            bound_path = vnext_player_bundle_manager.validate_player_capture_session(payload)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        now = time.time()
        record = {
            **payload,
            'session_id': session_id,
            'workspace_kind': 'player',
            'project_path': os.path.abspath(bound_path),
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
        from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager

        with cls._lock:
            cls._cleanup()
            if session_id:
                active = dict(cls._ui_sessions.get(str(session_id)) or {})
            else:
                sessions = sorted(
                    cls._ui_sessions.values(),
                    key=lambda item: (
                        float(item.get('last_focus_at', 0)),
                        float(item.get('last_seen_at', 0)),
                    ),
                    reverse=True,
                )
                active = dict(sessions[0]) if sessions else {}
        if not active:
            raise HTTPException(status_code=409, detail='Player Capture 会话不存在或已过期')
        try:
            bound_path = vnext_player_bundle_manager.validate_player_capture_session(active)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(
            os.path.realpath(str(active.get('project_path') or ''))
        ):
            raise HTTPException(status_code=409, detail='Player Capture 运行目录不一致')
        return active

    @staticmethod
    def _to_image(frame: Any, *, frame_is_bgr: bool) -> Image.Image:
        if isinstance(frame, Image.Image):
            return frame.convert('RGB')
        import numpy as np

        value = np.asarray(frame)
        if value.ndim == 3 and value.shape[2] == 4:
            if frame_is_bgr:
                value = value[:, :, [2, 1, 0, 3]]
            return Image.fromarray(value.astype('uint8'), mode='RGBA').convert('RGB')
        if value.ndim == 3 and value.shape[2] == 3:
            if frame_is_bgr:
                value = value[:, :, ::-1]
            return Image.fromarray(value.astype('uint8'), mode='RGB')
        return Image.fromarray(value.astype('uint8')).convert('RGB')

    @classmethod
    def _snapshot_png(cls, snapshot: PlayerSnapshot) -> bytes:
        if snapshot.png:
            return snapshot.png
        if snapshot.image is None:
            raise HTTPException(status_code=500, detail='Player 冻结帧缺少可编码画面')
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
    def create_snapshot(cls, session: dict[str, Any]) -> dict[str, Any]:
        from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
        from core.vnext.runtime import RuntimeFailure
        from core.vnext.target_service import TargetServiceError
        from core.services.capture_target_pool import capture_target_pool

        started = time.perf_counter()
        semantic_future = None
        try:
            project_path, target = vnext_player_bundle_manager.player_capture_target(session)
            field_capture = (session.get('capture_context') or {}).get('fieldCapture') or {}
            if (
                str(field_capture.get('selectionMode') or '') == 'control'
                and str(target.get('type') or '') == 'android_adb'
            ):
                semantic_future = cls._semantic_executor.submit(cls._capture_adb_semantic, dict(target))
            acquire_started = time.perf_counter()
            entry, reused = capture_target_pool.acquire('player', project_path, target)
            acquire_ms = (time.perf_counter() - acquire_started) * 1000
            rebuilt = False
            try:
                for attempt in range(2):
                    frame_started = time.perf_counter()
                    try:
                        with entry.lock:
                            if str(target.get('type') or '') == 'windows' and hasattr(entry.driver, '_workspace_box'):
                                entry.driver._box = entry.driver._workspace_box()
                            frame = entry.driver.capture_frame()
                            overlay_region = entry.driver.capture_overlay_region()
                            frame_ms = (time.perf_counter() - frame_started) * 1000
                            convert_started = time.perf_counter()
                            image = cls._to_image(frame, frame_is_bgr=bool(entry.driver.frame_is_bgr))
                            convert_ms = (time.perf_counter() - convert_started) * 1000
                            entry.last_used_at = time.monotonic()
                        driver = entry.driver
                        break
                    except Exception:
                        capture_target_pool.invalidate(entry)
                        if not reused or attempt:
                            raise
                        acquire_started = time.perf_counter()
                        entry, _ = capture_target_pool.acquire('player', project_path, target, force_new=True)
                        acquire_ms += (time.perf_counter() - acquire_started) * 1000
                        reused = False
                        rebuilt = True
                else:
                    raise RuntimeFailure('Player 捕获驱动重建失败')
            except Exception:
                if semantic_future is not None:
                    semantic_future.cancel()
                raise
        except (PlayerBundleError, RuntimeFailure, TargetServiceError) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    'code': 'capture_target_unavailable',
                    'message': str(exc),
                    'state': 'target_unavailable',
                },
            ) from exc
        # The resident native overlay reads the owned RGB frame through shared
        # memory. Encode only when a confirmed image field actually needs PNG.
        encode_ms = 0.0
        snapshot_id = f'player_snap_{uuid.uuid4().hex}'
        target_type = str((target or {}).get('type') or 'unknown')
        destination = dict((session.get('capture_context') or {}).get('player_destination') or {})
        capture_purpose = (
            'window_binding'
            if str(destination.get('action_id') or '') == 'capture-window'
            else ''
        )
        window_candidates: list[dict[str, Any]] = []
        if capture_purpose == 'window_binding':
            from core.services.native_capture_overlay import native_capture_overlay
            from core.services.native_desktop_shell import desktop_shell_process_id
            from core.vnext.window_binding_v2 import enumerate_window_candidates

            window_candidates = enumerate_window_candidates(
                exclude_process_ids={
                    os.getpid(),
                    native_capture_overlay.process_id,
                    desktop_shell_process_id(),
                },
            )
        target_aligned = (
            isinstance(overlay_region, list)
            and len(overlay_region) == 4
            and overlay_region[2] > overlay_region[0]
            and overlay_region[3] > overlay_region[1]
        )
        item = PlayerSnapshot(
            snapshot_id=snapshot_id,
            project_path=os.path.abspath(project_path),
            project_id=str(session.get('project_id') or ''),
            workspace_id=str(session.get('workspace_id') or ''),
            workspace_generation=int(session.get('workspace_generation') or 0),
            session_id=str(session.get('session_id') or ''),
            png=b'',
            width=image.width,
            height=image.height,
            region=(overlay_region if target_aligned else [0, 0, image.width, image.height]),
            backend=f'player:{target_type}',
            presentation='target_aligned' if target_aligned else 'centered_fit',
            source={
                'target_id': str((target or {}).get('target_id') or ''),
                'platform': str((target or {}).get('platform') or target_type),
                'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'window_handle': int(getattr(driver, 'hwnd', 0) or 0),
                'purpose': capture_purpose,
                'window_candidates': window_candidates,
            },
            target=dict(target or {}),
            semantic_future=semantic_future,
            image=image.copy(),
            performance={
                'driver_acquire_ms': round(acquire_ms, 1),
                'driver_reused': bool(reused),
                'driver_rebuilt': rebuilt,
                'frame_ms': round(frame_ms, 1),
                'frame_convert_ms': round(convert_ms, 1),
                'png_encode_ms': round(encode_ms, 1),
                'png_encode_deferred': True,
                'capture_service_ms': round((time.perf_counter() - started) * 1000, 1),
                'semantic_prefetch_started': semantic_future is not None,
            },
        )
        with cls._lock:
            cls._cleanup()
            cls._snapshots[snapshot_id] = item
            cls._active_snapshot_id = snapshot_id
        return {
            'snapshot_id': snapshot_id,
            'session_id': item.session_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'presentation': item.presentation,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'expires_in': SNAPSHOT_TTL_SECONDS,
            'performance': dict(item.performance),
        }

    @classmethod
    def trigger_global_capture(cls, options: dict[str, Any] | None = None) -> dict[str, Any]:
        from core.services import capture_mode
        from core.services.native_capture_overlay import native_capture_overlay

        options = options or {}
        field_capture = options.get('field_capture')
        if not isinstance(field_capture, dict):
            raise HTTPException(status_code=400, detail='Player 字段捕获请求格式无效')
        request_id = str(field_capture.get('request_id') or '').strip()
        selection_mode = str(field_capture.get('selection_mode') or '').strip()
        if not request_id or selection_mode not in {'point', 'region', 'color', 'path', 'control'}:
            raise HTTPException(status_code=400, detail='Player 字段捕获请求缺少必要参数')
        with cls._trigger_lock:
            session = cls.active_ui_session(str(options.get('session_id') or ''))
            if capture_mode.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先退出控件捕获模式')
            with cls._lock:
                cls._cleanup()
                active = cls._snapshots.get(cls._active_snapshot_id or '')
            if active is not None:
                if native_capture_overlay.is_alive() and native_capture_overlay.focus():
                    raise HTTPException(status_code=409, detail='请先完成或退出当前字段捕获')
                cls.close_capture(active.snapshot_id)
            session = dict(session)
            context = dict(session.get('capture_context') or {})
            context['fieldCapture'] = {
                'requestId': request_id,
                'selectionMode': selection_mode,
                'category': 'image',
                'maxRects': 1,
                'title': str(field_capture.get('title') or '采集字段'),
            }
            session['capture_context'] = context
            snapshot = cls.create_snapshot(session)
            with cls._lock:
                item = cls._snapshots.get(snapshot['snapshot_id'])
            result = native_capture_overlay.show(
                session,
                snapshot,
                item.png if item else b'',
                image=item.image if item else None,
            )
            if not result.get('ok'):
                cls.close_capture(snapshot['snapshot_id'])
                raise HTTPException(
                    status_code=409,
                    detail=f'桌面捕获宿主启动失败：{result.get("message") or native_capture_overlay.last_error}',
                )
            capture_mode.publish_event({
                'event': 'screenshot-capture',
                'session_id': session['session_id'],
                'snapshot': snapshot,
                'capture_context': context,
                'project_name': session.get('project_name') or 'EasyCode Player',
                'target_name': session.get('target_name') or '',
                'native_host': True,
            })
            return {'ok': True, 'native_host': True, **snapshot}

    @classmethod
    def request_player_action(cls, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        from core.services import capture_mode

        snapshot_id = str(payload.get('snapshot_id') or '')
        session_id = str(payload.get('session_id') or '')
        cls.validate_player_snapshot(snapshot_id, session_id)
        kind = str(payload.get('kind') or '')
        if kind == 'field_control_probe':
            try:
                with cls._lock:
                    snapshot = cls._snapshots.get(snapshot_id)
                if snapshot is None:
                    raise HTTPException(status_code=404, detail='Player 冻结帧不存在或已过期')
                point = payload.get('point')
                reference_size = payload.get('reference_size')
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise HTTPException(status_code=422, detail='控件捕获点无效')
                if tuple(int(value) for value in reference_size or ()) != (snapshot.width, snapshot.height):
                    raise HTTPException(status_code=409, detail='冻结帧尺寸已变化，请重新捕获')
                semantic_snapshot = None
                if snapshot.semantic_future is not None:
                    semantic_snapshot = snapshot.semantic_future.result(timeout=5.0).get('nodes')
                from core.vnext.control_capture_v6 import resolve_control_candidates
                from core.services.native_capture_overlay import native_capture_overlay
                from core.services.native_desktop_shell import desktop_shell_process_id
                return {
                    'ok': True,
                    'candidates': resolve_control_candidates(
                        snapshot.project_path,
                        snapshot.target,
                        (int(point[0]), int(point[1])),
                        (snapshot.width, snapshot.height),
                        capture_region=snapshot.region,
                        expected_hwnd=int(snapshot.source.get('window_handle') or 0),
                        semantic_snapshot=semantic_snapshot,
                        exclude_process_ids={
                            native_capture_overlay.process_id,
                            desktop_shell_process_id(),
                        },
                    ),
                }
            except concurrent.futures.TimeoutError as exc:
                raise HTTPException(status_code=504, detail='控件树读取超时，请重新捕获') from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if kind not in {'field_confirm', 'field_cancel'}:
            raise HTTPException(status_code=422, detail='Player 只接受字段确认或取消动作')
        request_id = f'player_capture_req_{uuid.uuid4().hex}'
        done = threading.Event()
        pending = {'event': done, 'result': None}
        with cls._lock:
            cls._pending_actions[request_id] = pending
        capture_mode.publish_event({'event': 'capture-command', 'request_id': request_id, **payload})
        if not done.wait(max(1.0, float(timeout))):
            with cls._lock:
                cls._pending_actions.pop(request_id, None)
            raise HTTPException(status_code=504, detail='Player 页面未响应字段捕获操作')
        with cls._lock:
            result = pending.get('result') or {'ok': False, 'message': 'Player 页面返回了空结果'}
            cls._pending_actions.pop(request_id, None)
        return result

    @classmethod
    def acknowledge_player_action(cls, request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with cls._lock:
            pending = cls._pending_actions.get(str(request_id or ''))
            if pending is None:
                raise HTTPException(status_code=404, detail='Player 捕获操作不存在或已超时')
            pending['result'] = result
            pending['event'].set()
        return {'ok': True}

    @staticmethod
    def _validate_rect(rect: list[int], snapshot: PlayerSnapshot) -> list[int]:
        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
            raise ValueError('框选范围格式无效')
        x, y, width, height = [int(value) for value in rect]
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError('框选范围必须位于冻结帧内')
        if x + width > snapshot.width or y + height > snapshot.height:
            raise ValueError('框选范围超出冻结帧')
        return [x, y, width, height]

    @classmethod
    def validate_player_snapshot(
        cls,
        snapshot_id: str,
        session_id: str,
        rect: list[int] | None = None,
    ) -> dict[str, Any]:
        from core.vnext.player_bundle import PlayerBundleError

        with cls._lock:
            cls._cleanup()
            item = cls._snapshots.get(str(snapshot_id or ''))
        if item is None:
            raise PlayerBundleError('Player 冻结帧不存在或已过期')
        if item.session_id != str(session_id or ''):
            raise PlayerBundleError('Player 冻结帧属于另一采集会话')
        session = cls.active_ui_session(item.session_id)
        if str(session.get('project_id') or '') != item.project_id:
            raise PlayerBundleError('Player 冻结帧产品身份不一致')
        if rect is not None:
            try:
                cls._validate_rect(rect, item)
            except (TypeError, ValueError) as exc:
                raise PlayerBundleError(str(exc)) from exc
        return {
            'snapshot_id': item.snapshot_id,
            'width': item.width,
            'height': item.height,
            'backend': item.backend,
            'presentation': item.presentation,
            'source': dict(item.source),
        }

    @classmethod
    def player_snapshot_crop(cls, snapshot_id: str, session_id: str, rect: list[int]) -> bytes:
        from core.vnext.player_bundle import PlayerBundleError

        cls.validate_player_snapshot(snapshot_id, session_id, rect)
        with cls._lock:
            item = cls._snapshots.get(str(snapshot_id or ''))
        if item is None:
            raise PlayerBundleError('Player 冻结帧已过期')
        x, y, width, height = cls._validate_rect(rect, item)
        with Image.open(io.BytesIO(cls._snapshot_png(item))) as image:
            cropped = image.convert('RGB').crop((x, y, x + width, y + height))
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG', optimize=False)
            return buffer.getvalue()

    @classmethod
    def resolve_window_capture(
        cls,
        snapshot_id: str,
        session_id: str,
        point: Any,
        reference_size: Any,
    ) -> dict[str, Any]:
        """Resolve a clicked full-desktop point to one versioned window binding."""

        from core.vnext.player_bundle import PlayerBundleError
        from core.vnext.window_binding_v2 import (
            WindowBindingResolutionError,
            candidate_at_screen_point,
            captured_binding,
        )

        cls.validate_player_snapshot(snapshot_id, session_id)
        with cls._lock:
            snapshot = cls._snapshots.get(str(snapshot_id or ''))
        if snapshot is None:
            raise PlayerBundleError('Player 冻结帧已过期')
        if str(snapshot.source.get('purpose') or '') != 'window_binding':
            raise PlayerBundleError('当前冻结帧不是窗口捕获会话')
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise PlayerBundleError('窗口捕获点无效')
        if tuple(int(value) for value in reference_size or ()) != (snapshot.width, snapshot.height):
            raise PlayerBundleError('窗口捕获画面尺寸已经变化，请重新捕获')
        clean_point = (int(point[0]), int(point[1]))
        if not (0 <= clean_point[0] < snapshot.width and 0 <= clean_point[1] < snapshot.height):
            raise PlayerBundleError('窗口捕获点超出冻结帧')
        screen_point = (
            int(snapshot.region[0]) + clean_point[0],
            int(snapshot.region[1]) + clean_point[1],
        )
        try:
            candidate = candidate_at_screen_point(
                list(snapshot.source.get('window_candidates') or []),
                screen_point,
            )
        except WindowBindingResolutionError as exc:
            raise PlayerBundleError(str(exc)) from exc
        return captured_binding(candidate)

    @classmethod
    def is_capture_active(cls) -> bool:
        with cls._lock:
            cls._cleanup()
            return bool(cls._active_snapshot_id)

    @classmethod
    def close_capture(cls, snapshot_id: str = '') -> dict[str, Any]:
        from core.services.native_capture_overlay import native_capture_overlay

        with cls._lock:
            target = str(snapshot_id or cls._active_snapshot_id or '')
            if not snapshot_id or cls._active_snapshot_id == snapshot_id:
                cls._active_snapshot_id = None
            if target:
                removed = cls._snapshots.pop(target, None)
            else:
                removed = None
        if removed is not None and removed.semantic_future is not None:
            removed.semantic_future.cancel()
        if target:
            native_capture_overlay.hide(target)
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
            item['result'] = {'ok': False, 'message': 'Player 正在关闭'}
            item['event'].set()
        capture_target_pool.close_owner('player')


player_capture_session_service = PlayerCaptureSessionService

__all__ = ['PlayerCaptureSessionService', 'player_capture_session_service']
