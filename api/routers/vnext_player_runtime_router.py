"""Standalone Player runtime HTTP surface.

This router intentionally has no dependency on ``vnext_router`` or the IDE
workspace manager.  Every route is backed by a verified signed Player bundle
or the runtime instance that executes its ECIR.
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from api.contracts.vnext_player import (
    ApiErrorResponse,
    PlayerCaptureCancelRequest,
    PlayerCaptureConfirmRequest,
    PlayerCaptureStartRequest,
    PlayerImageRestoreRequest,
    PlayerProfileRequest,
    PlayerRuntimeRunRequest,
)
from api.errors import failure_detail
from api.idempotency import execute_idempotent
from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
from core.vnext.runtime import RuntimeFailure, vnext_runtime


def _player_error(exc: Exception, *, status_code: int = 409) -> None:
    code = 'player_bundle_unavailable' if isinstance(exc, PlayerBundleError) else 'runtime_operation_failed'
    raise HTTPException(
        status_code=status_code,
        detail=failure_detail(code, str(exc), action='retry'),
    ) from exc


def _ensure_bundle() -> None:
    if not vnext_player_bundle_manager.available():
        vnext_player_bundle_manager.ensure_from_environment()


def create_vnext_player_runtime_router() -> APIRouter:
    error_responses = {
        status: {'model': ApiErrorResponse, 'description': description}
        for status, description in (
            (400, '请求无效'), (404, '运行或资源不存在'),
            (409, '签名包、配置或运行状态冲突'), (422, '字段校验失败'),
        )
    }
    router = APIRouter(
        prefix='/api/vnext',
        tags=['EasyCode vNext Player Runtime'],
        responses=error_responses,
    )

    async def call_bundle(operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            _ensure_bundle()
            return await run_in_threadpool(operation, *args, **kwargs)
        except PlayerBundleError as exc:
            _player_error(exc)

    @router.get('/player/runtime/bootstrap')
    async def player_runtime_bootstrap():
        try:
            _ensure_bundle()
            return await run_in_threadpool(vnext_player_bundle_manager.bootstrap)
        except PlayerBundleError as exc:
            _player_error(exc)

    @router.get('/player/runtime/state')
    async def player_runtime_state():
        """Small host projection consumed by the multi-instance console."""

        _ensure_bundle()
        return {
            'instance_id': str(os.environ.get('EASYCODE_PLAYER_INSTANCE_ID') or ''),
            'instance_name': str(os.environ.get('EASYCODE_PLAYER_INSTANCE_NAME') or ''),
            'execution': await run_in_threadpool(vnext_runtime.latest_snapshot),
        }

    @router.post('/player/runtime/run')
    async def player_runtime_run(
        payload: Annotated[PlayerRuntimeRunRequest | None, Body()] = None,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        options = payload or PlayerRuntimeRunRequest()

        async def operation():
            return await call_bundle(vnext_player_bundle_manager.start, options.model_dump())

        return await execute_idempotent(
            idempotency_key,
            'vnext.player-runtime.run',
            options.model_dump(mode='json'),
            operation,
        )

    @router.post('/player/runtime/dangerous-operations')
    async def player_runtime_dangerous_operations(
        payload: Annotated[PlayerRuntimeRunRequest | None, Body()] = None,
    ):
        options = payload or PlayerRuntimeRunRequest()
        request_payload = options.model_dump(mode='json')
        request_payload['dangerous_confirmations'] = []
        return await call_bundle(
            vnext_player_bundle_manager.dangerous_operation_requirements,
            request_payload,
        )

    @router.get('/player/runtime/preflight')
    async def player_runtime_preflight(
        target_id: str = '',
        profile_id: str = '',
        profile_revision: int | None = None,
    ):
        return await call_bundle(
            vnext_player_bundle_manager.preflight,
            target_id,
            profile_id,
            profile_revision,
        )

    @router.get('/player/runtime/profiles')
    async def player_runtime_profiles():
        return await call_bundle(vnext_player_bundle_manager.profiles)

    @router.put('/player/runtime/profiles')
    async def save_player_runtime_profile(payload: PlayerProfileRequest):
        arguments = (
            payload.profile_id, payload.name, payload.target_id, payload.values,
            payload.expected_revision,
        )
        if payload.recording is None:
            return await call_bundle(vnext_player_bundle_manager.save_profile, *arguments)
        return await call_bundle(
            vnext_player_bundle_manager.save_profile,
            *arguments,
            payload.recording.model_dump(mode='json'),
        )

    @router.delete('/player/runtime/profiles/{profile_id}')
    async def delete_player_runtime_profile(profile_id: str):
        return await call_bundle(vnext_player_bundle_manager.delete_profile, profile_id)

    @router.get('/player/runtime/recording')
    async def player_runtime_recording_status():
        return await call_bundle(vnext_player_bundle_manager.recording_status)

    @router.post('/player/runtime/recording/stop')
    async def player_runtime_recording_stop():
        return await call_bundle(vnext_player_bundle_manager.stop_recording)

    @router.get('/player/runtime/recordings')
    async def player_runtime_recording_sessions():
        return await call_bundle(vnext_player_bundle_manager.recording_sessions)

    @router.get('/player/runtime/recordings/{session_id}')
    async def player_runtime_recording_session(session_id: str):
        return await call_bundle(vnext_player_bundle_manager.recording_session, session_id)

    @router.get('/player/runtime/recordings/{session_id}/frames/{sequence}')
    async def player_runtime_recording_frame(session_id: str, sequence: int):
        return await call_bundle(vnext_player_bundle_manager.recording_frame_data, session_id, sequence)

    @router.delete('/player/runtime/recordings/{session_id}')
    async def delete_player_runtime_recording_session(session_id: str):
        return await call_bundle(vnext_player_bundle_manager.delete_recording_session, session_id)

    @router.post('/player/runtime/recordings/{session_id}/export')
    async def create_player_runtime_recording_export(session_id: str):
        return await call_bundle(vnext_player_bundle_manager.create_recording_export, session_id)

    @router.get('/player/runtime/recordings/{session_id}/exports/{export_id}')
    async def download_player_runtime_recording_export(session_id: str, export_id: str):
        try:
            _ensure_bundle()
            path = await run_in_threadpool(
                vnext_player_bundle_manager.recording_export_path, session_id, export_id,
            )
            return FileResponse(path, media_type='application/zip', filename=path.name)
        except PlayerBundleError as exc:
            _player_error(exc, status_code=404)

    @router.get('/player/runtime/assets/{asset_id}/content')
    async def player_runtime_asset_content(asset_id: str):
        try:
            _ensure_bundle()
            path, item = await run_in_threadpool(vnext_player_bundle_manager.asset_content, asset_id)
            return FileResponse(path, media_type=str(item.get('mime_type') or 'application/octet-stream'))
        except PlayerBundleError as exc:
            _player_error(exc, status_code=404)

    @router.get('/player/runtime/actions')
    async def player_runtime_actions(
        profile_id: str = '',
        profile_revision: int | None = None,
        target_id: str = '',
    ):
        return await call_bundle(
            vnext_player_bundle_manager.terminal_action_availability,
            profile_id,
            profile_revision,
            target_id,
        )

    @router.post('/player/runtime/capture/start')
    async def player_runtime_capture_start(payload: PlayerCaptureStartRequest):
        return await call_bundle(
            vnext_player_bundle_manager.start_control_capture,
            payload.destination.model_dump(mode='json'),
            origin=payload.origin,
        )

    @router.post('/player/runtime/capture/confirm')
    async def player_runtime_capture_confirm(payload: PlayerCaptureConfirmRequest):
        return await call_bundle(
            vnext_player_bundle_manager.confirm_control_capture,
            payload.capture_id,
            payload.destination.model_dump(mode='json'),
            payload.result,
        )

    @router.post('/player/runtime/capture/cancel')
    async def player_runtime_capture_cancel(payload: PlayerCaptureCancelRequest):
        return await call_bundle(
            vnext_player_bundle_manager.cancel_control_capture,
            payload.capture_id,
            payload.destination.model_dump(mode='json'),
        )

    @router.post('/player/runtime/images/restore')
    async def player_runtime_image_restore(payload: PlayerImageRestoreRequest):
        return await call_bundle(
            vnext_player_bundle_manager.restore_profile_image,
            payload.destination.model_dump(mode='json'),
        )

    @router.get('/runs/{execution_id}')
    async def run_status(execution_id: str, after_sequence: int | None = None):
        try:
            return vnext_runtime.snapshot(execution_id, after_sequence)
        except RuntimeFailure as exc:
            _player_error(exc, status_code=404)

    @router.get('/runs/{execution_id}/events')
    async def run_events(execution_id: str, after_sequence: int = 0):
        async def stream():
            cursor = max(0, after_sequence)
            while True:
                try:
                    snapshot = await run_in_threadpool(
                        vnext_runtime.wait_snapshot,
                        execution_id,
                        cursor,
                        15.0,
                    )
                except RuntimeFailure as exc:
                    payload = json.dumps({'message': str(exc)}, ensure_ascii=False)
                    yield f'event: error\ndata: {payload}\n\n'
                    return
                events = snapshot.get('events') or []
                if not events:
                    yield ': keepalive\n\n'
                for event in events:
                    cursor = max(cursor, int(event.get('sequence') or 0))
                    payload = json.dumps(event, ensure_ascii=False, separators=(',', ':'))
                    yield f'id: {cursor}\nevent: runtime\ndata: {payload}\n\n'
                if snapshot.get('status') in {'completed', 'failed', 'cancelled'} and snapshot.get('finished_at'):
                    terminal = {key: value for key, value in snapshot.items() if key != 'events'}
                    payload = json.dumps(terminal, ensure_ascii=False, separators=(',', ':'))
                    yield f'event: end\ndata: {payload}\n\n'
                    return

        return StreamingResponse(
            stream(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    @router.delete('/runs/{execution_id}')
    async def cancel_run(execution_id: str):
        try:
            return vnext_runtime.cancel(execution_id)
        except RuntimeFailure as exc:
            _player_error(exc, status_code=404)

    @router.post('/runs/{execution_id}/pause')
    async def pause_run(execution_id: str):
        try:
            return vnext_runtime.pause(execution_id)
        except RuntimeFailure as exc:
            _player_error(exc)

    @router.post('/runs/{execution_id}/resume')
    async def resume_run(execution_id: str):
        try:
            return vnext_runtime.resume(execution_id)
        except RuntimeFailure as exc:
            _player_error(exc)

    @router.get('/runs/{execution_id}/diagnostics')
    async def download_diagnostics(execution_id: str):
        try:
            path = vnext_runtime.diagnostic_path(execution_id)
            return FileResponse(path, media_type='application/zip', filename=f'{execution_id}-diagnostic.zip')
        except RuntimeFailure as exc:
            _player_error(exc, status_code=404)

    @router.get('/runs/{execution_id}/failure-frame')
    async def download_failure_frame(execution_id: str):
        try:
            path = vnext_runtime.failure_frame_path(execution_id)
            return FileResponse(path, media_type='image/png', filename=f'{execution_id}-failure.png')
        except RuntimeFailure as exc:
            _player_error(exc, status_code=404)

    return router


__all__ = ['create_vnext_player_runtime_router']
