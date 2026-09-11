"""Terminal-only native capture bridge for the standalone Player."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Body, Header
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from api.contracts.vnext_player import (
    CaptureActionAckRequest,
    CaptureActionRequest,
    CaptureCloseRequest,
)
from api.idempotency import execute_idempotent
from core.services import capture_mode
from core.services.player_capture_session import player_capture_session_service


def create_vnext_player_capture_router() -> APIRouter:
    """Expose only SSE, field action/ack, and close.

    Session registration and trigger authority remain internal to the signed
    Player runtime router.  Legacy snapshot, asset, replay, settings, hotkey,
    and UI-control-mode routes are intentionally absent.
    """

    router = APIRouter(tags=['EasyCode vNext Player Capture'])

    @router.get('/api/ui-control/events')
    async def player_capture_events():
        event_queue = capture_mode.subscribe_events()

        async def stream():
            try:
                while True:
                    item = await asyncio.to_thread(event_queue.get)
                    yield f'data: {json.dumps(item, ensure_ascii=False)}\n\n'
            finally:
                capture_mode.unsubscribe_events(event_queue)

        return StreamingResponse(
            stream(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    @router.post('/api/capture/action')
    async def request_player_capture_action(
        payload: CaptureActionRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            return await run_in_threadpool(
                player_capture_session_service.request_player_action,
                payload.model_dump(mode='json'),
            )

        return await execute_idempotent(
            idempotency_key,
            'vnext.player.capture.action',
            payload.model_dump(mode='json'),
            operation,
            timeout=45,
        )

    @router.post('/api/capture/action/ack')
    async def acknowledge_player_capture_action(payload: CaptureActionAckRequest):
        return player_capture_session_service.acknowledge_player_action(
            payload.request_id,
            payload.result,
        )

    @router.post('/api/capture/close')
    async def close_player_capture(
        payload: CaptureCloseRequest = Body(default_factory=CaptureCloseRequest),
    ):
        return player_capture_session_service.close_capture(payload.snapshot_id)

    return router


__all__ = ['create_vnext_player_capture_router']
