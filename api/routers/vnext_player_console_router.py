"""Loopback control plane for the one-window Windows Player console."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from api.contracts.vnext_player import ApiErrorResponse
from api.contracts.vnext_player_console import (
    PlayerConsoleInstanceCreateRequest,
    PlayerConsoleInstanceDeleteRequest,
    PlayerConsolePrepareCloseRequest,
)
from api.errors import failure_detail
from core.vnext.player_console_v1 import PlayerConsoleV1, get_player_console_v1
from core.vnext.schedule_v6 import ScheduleError


def _translate(exc: ScheduleError) -> None:
    status = 404 if exc.error_id.endswith('_not_found') else 503 if exc.transient else 409 if any(
        token in exc.error_id for token in ('conflict', 'unavailable', 'unreachable', 'active', 'timeout')
    ) else 422
    raise HTTPException(
        status_code=status,
        detail=failure_detail(
            exc.error_id,
            str(exc),
            retryable=exc.transient,
            action=exc.action,
            diagnostics=exc.diagnostics,
        ),
    ) from exc


def create_vnext_player_console_router(
    console: PlayerConsoleV1 | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix='/api/vnext/player-console',
        tags=['EasyCode Windows Player Console'],
        responses={
            code: {'model': ApiErrorResponse, 'description': description}
            for code, description in (
                (404, '实例不存在'),
                (409, '实例、工作进程或运行状态冲突'),
                (422, '请求或实例引用无效'),
                (503, '实例工作进程暂时不可用'),
            )
        },
    )

    def current() -> PlayerConsoleV1:
        return console if console is not None else get_player_console_v1()

    @router.get('')
    async def bootstrap():
        try:
            return await run_in_threadpool(current().list_instances)
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/lifecycle/close-status')
    async def close_status():
        try:
            return await run_in_threadpool(current().close_status)
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/lifecycle/prepare-close')
    async def prepare_close(payload: PlayerConsolePrepareCloseRequest):
        try:
            return await run_in_threadpool(
                current().prepare_close,
                stop_active=payload.stop_active,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances', status_code=201)
    async def create_instance(payload: PlayerConsoleInstanceCreateRequest):
        try:
            result = await run_in_threadpool(
                current().hub.registry.create_instance,
                payload.installation_id,
                name=payload.name,
            )
            return {'instance': result}
        except ScheduleError as exc:
            _translate(exc)

    @router.delete('/instances/{instance_id}')
    async def delete_instance(instance_id: str, payload: PlayerConsoleInstanceDeleteRequest):
        try:
            return await run_in_threadpool(
                current().delete_instance,
                instance_id,
                expected_revision=payload.expected_revision,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances/{instance_id}/connect')
    async def connect_instance(instance_id: str, request: Request):
        try:
            return await run_in_threadpool(
                current().connect,
                instance_id,
                f'{request.url.scheme}://{request.url.netloc}',
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/instances/{instance_id}/state')
    async def instance_state(instance_id: str):
        try:
            return await run_in_threadpool(current().state, instance_id)
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/instances/{instance_id}/diagnostics')
    async def instance_diagnostics(instance_id: str):
        try:
            path = await run_in_threadpool(current().create_support_bundle, instance_id)
            return FileResponse(
                path,
                media_type='application/zip',
                filename=f'{instance_id}-easycode-support.zip',
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances/{instance_id}/pause')
    async def pause_instance(instance_id: str):
        try:
            return await run_in_threadpool(current().control, instance_id, 'pause')
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances/{instance_id}/resume')
    async def resume_instance(instance_id: str):
        try:
            return await run_in_threadpool(current().control, instance_id, 'resume')
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances/{instance_id}/stop')
    async def stop_instance(instance_id: str):
        try:
            return await run_in_threadpool(current().control, instance_id, 'stop')
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/instances/{instance_id}/restart')
    async def restart_instance(instance_id: str, request: Request):
        try:
            return await run_in_threadpool(
                current().restart,
                instance_id,
                f'{request.url.scheme}://{request.url.netloc}',
            )
        except ScheduleError as exc:
            _translate(exc)

    return router


__all__ = ['create_vnext_player_console_router']
