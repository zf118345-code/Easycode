"""HTTP boundary for the format-6 local schedule control plane."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from api.contracts.vnext_player import ApiErrorResponse
from api.contracts.vnext_schedule import (
    ScheduleDeleteResponse,
    ScheduleDiagnosticResponse,
    ScheduleDispatchResponse,
    ScheduleOccurrenceResponse,
    SchedulePlanRequest,
    SchedulePlanResponse,
    SchedulePlanUpdateRequest,
)
from api.errors import failure_detail
from core.vnext.schedule_v6 import (
    ScheduleError,
    ScheduleServiceV6,
)


def _status_for(exc: ScheduleError) -> int:
    if exc.error_id.endswith('_not_found') or exc.error_id == 'schedule.not_found':
        return 404
    if exc.error_id in {
        'schedule.revision_conflict',
        'schedule.identity_conflict',
        'schedule.dispatch_identity_conflict',
        'schedule.run_identity_mismatch',
        'schedule.run_terminal_conflict',
        'schedule.installed_registry_unavailable',
        'schedule.execution_adapter_unavailable',
        'schedule.remote_dispatch_unavailable',
    }:
        return 409
    if exc.error_id == 'schedule.database_unavailable':
        return 503
    return 422


def _translate(exc: ScheduleError) -> None:
    raise HTTPException(
        status_code=_status_for(exc),
        detail=failure_detail(
            exc.error_id,
            str(exc),
            retryable=exc.transient,
            action=exc.action,
            diagnostics=exc.diagnostics,
        ),
    ) from exc


def create_vnext_schedule_router(
    service: ScheduleServiceV6 | None = None,
) -> APIRouter:
    error_responses = {
        status: {'model': ApiErrorResponse, 'description': description}
        for status, description in (
            (404, '计划或记录不存在'),
            (409, 'revision、身份或宿主状态冲突'),
            (422, '计划字段或引用无效'),
            (503, '本地计划数据库暂时不可用'),
        )
    }
    router = APIRouter(
        prefix='/api/vnext/schedules',
        tags=['EasyCode vNext schedules'],
        responses=error_responses,
    )

    def current_service() -> ScheduleServiceV6:
        # App import and OpenAPI generation must not create a runtime database.
        # The default service is initialized only when the control plane is used.
        if service is not None:
            return service
        # The real product path uses the per-user installed-product registry
        # and ordinary Runtime dispatch adapter.  ``get_schedule_service_v6``
        # remains available for isolated core embeddings/tests only.
        from core.vnext.schedule_hub_v6 import get_player_hub_v6

        return get_player_hub_v6().schedule

    @router.get('', response_model=list[SchedulePlanResponse])
    async def list_schedules(include_deleted: bool = False):
        try:
            return await run_in_threadpool(
                current_service().list_plans,
                include_deleted=include_deleted,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post('', response_model=SchedulePlanResponse, status_code=201)
    async def create_schedule(request: SchedulePlanRequest):
        try:
            result = await run_in_threadpool(
                current_service().create_plan,
                request.model_dump(exclude_none=True),
            )
            if service is None:
                from core.vnext.schedule_hub_v6 import get_player_hub_v6

                await run_in_threadpool(get_player_hub_v6().refresh_wake_if_installed)
            return result
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/occurrences', response_model=list[ScheduleOccurrenceResponse])
    async def list_occurrences(
        schedule_id: str = Query(default='', max_length=128),
        limit: int = Query(default=200, ge=1, le=2_000),
    ):
        try:
            return await run_in_threadpool(
                current_service().list_occurrences,
                schedule_id=schedule_id,
                limit=limit,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/dispatches', response_model=list[ScheduleDispatchResponse])
    async def list_dispatches(
        occurrence_id: str = Query(default='', max_length=128),
        limit: int = Query(default=500, ge=1, le=5_000),
    ):
        try:
            return await run_in_threadpool(
                current_service().list_dispatches,
                occurrence_id=occurrence_id,
                limit=limit,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/diagnostics', response_model=list[ScheduleDiagnosticResponse])
    async def list_diagnostics(
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=500, ge=1, le=5_000),
    ):
        try:
            return await run_in_threadpool(
                current_service().list_diagnostics,
                after_sequence=after_sequence,
                limit=limit,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get('/{schedule_id}', response_model=SchedulePlanResponse)
    async def get_schedule(schedule_id: str):
        try:
            return await run_in_threadpool(current_service().get_plan, schedule_id)
        except ScheduleError as exc:
            _translate(exc)

    @router.put('/{schedule_id}', response_model=SchedulePlanResponse)
    async def update_schedule(schedule_id: str, request: SchedulePlanUpdateRequest):
        try:
            payload = request.model_dump(exclude={'expected_revision'}, exclude_none=True)
            result = await run_in_threadpool(
                current_service().update_plan,
                schedule_id,
                request.expected_revision,
                payload,
            )
            if service is None:
                from core.vnext.schedule_hub_v6 import get_player_hub_v6

                await run_in_threadpool(get_player_hub_v6().refresh_wake_if_installed)
            return result
        except ScheduleError as exc:
            _translate(exc)

    @router.delete('/{schedule_id}', response_model=ScheduleDeleteResponse)
    async def delete_schedule(
        schedule_id: str,
        expected_revision: int = Query(ge=1),
    ):
        try:
            result = await run_in_threadpool(
                current_service().delete_plan,
                schedule_id,
                expected_revision,
            )
            if service is None:
                from core.vnext.schedule_hub_v6 import get_player_hub_v6

                await run_in_threadpool(get_player_hub_v6().refresh_wake_if_installed)
            return result
        except ScheduleError as exc:
            _translate(exc)

    return router
