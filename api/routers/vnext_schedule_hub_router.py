"""HTTP surface for the installed-product and Player Hub host control plane."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from api.contracts.vnext_player import ApiErrorResponse
from api.contracts.vnext_schedule_hub import (
    BatchRequest,
    BatchUpdateRequest,
    HubActionResponse,
    HubStatusResponse,
    HubTickResponse,
    InstallationRegisterRequest,
    InstanceCreateRequest,
    InstanceReleaseRequest,
)
from api.errors import failure_detail
from core.vnext.schedule_hub_v6 import PlayerHubV6, get_player_hub_v6
from core.vnext.schedule_v6 import ScheduleError


def _status_for(exc: ScheduleError) -> int:
    if exc.error_id.endswith("_not_found"):
        return 404
    if exc.error_id.endswith("_database_unavailable"):
        return 503
    if exc.transient:
        return 503
    if any(
        token in exc.error_id
        for token in ("conflict", "drift", "unavailable", "disabled", "signature")
    ):
        return 409
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


def create_vnext_schedule_hub_router(hub: PlayerHubV6 | None = None) -> APIRouter:
    router = APIRouter(
        prefix="/api/vnext/player-hub",
        tags=["EasyCode vNext Player Hub"],
        responses={
            code: {"model": ApiErrorResponse, "description": description}
            for code, description in (
                (404, "已安装产品、实例或批次不存在"),
                (409, "签名、revision、文件漂移或宿主状态冲突"),
                (422, "请求字段或稳定引用无效"),
                (503, "当前用户 Hub 或系统宿主暂时不可用"),
            )
        },
    )

    def current() -> PlayerHubV6:
        # OpenAPI generation must remain side-effect free.
        return hub if hub is not None else get_player_hub_v6()

    @router.get("", response_model=HubStatusResponse)
    async def status():
        try:
            return await run_in_threadpool(current().status)
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/installations", status_code=201)
    async def register_installation(request: InstallationRegisterRequest):
        try:
            return await run_in_threadpool(
                current().registry.register_distribution,
                request.distribution_root,
                instance_name=request.instance_name,
                instance_id=request.instance_id or "",
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get("/installations")
    async def list_installations():
        try:
            return await run_in_threadpool(
                current().registry.list_installations, include_profiles=True
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/instances", status_code=201)
    async def create_instance(request: InstanceCreateRequest):
        try:
            return await run_in_threadpool(
                current().registry.create_instance,
                request.installation_id,
                name=request.name,
                instance_id=request.instance_id or "",
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get("/instances")
    async def list_instances():
        try:
            return await run_in_threadpool(
                current().registry.list_instances, include_profiles=True
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.put("/instances/{instance_id}/release")
    async def bind_instance_release(instance_id: str, request: InstanceReleaseRequest):
        try:
            return await run_in_threadpool(
                current().registry.bind_instance_release,
                instance_id,
                request.installation_id,
                expected_revision=request.expected_revision,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/instances/{instance_id}/open")
    async def open_instance_player(instance_id: str):
        try:
            return await run_in_threadpool(
                current().registry.launch_instance_player, instance_id
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post('/console/open')
    async def open_player_console(product_id: str = ''):
        try:
            return await run_in_threadpool(
                current().registry.launch_player_console,
                product_id=product_id,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.get("/batches")
    async def list_batches():
        try:
            return await run_in_threadpool(current().registry.list_batches)
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/batches", status_code=201)
    async def create_batch(request: BatchRequest):
        try:
            return await run_in_threadpool(
                current().registry.save_batch,
                request.model_dump(exclude_none=True),
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.put("/batches/{batch_id}")
    async def update_batch(batch_id: str, request: BatchUpdateRequest):
        try:
            payload = request.model_dump(exclude={"expected_revision"}, exclude_none=True)
            payload["batch_id"] = batch_id
            return await run_in_threadpool(
                current().registry.save_batch,
                payload,
                expected_revision=request.expected_revision,
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.delete("/batches/{batch_id}", response_model=HubActionResponse)
    async def delete_batch(batch_id: str, expected_revision: int = Query(ge=1)):
        try:
            return await run_in_threadpool(
                current().registry.delete_batch, batch_id, expected_revision
            )
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/agent/install", response_model=HubActionResponse)
    async def install_agent():
        try:
            return await run_in_threadpool(current().refresh_wake_registration)
        except ScheduleError as exc:
            _translate(exc)

    @router.delete("/agent", response_model=HubActionResponse)
    async def uninstall_agent():
        try:
            return await run_in_threadpool(current().task_scheduler.uninstall)
        except ScheduleError as exc:
            _translate(exc)

    @router.post("/tick", response_model=HubTickResponse)
    async def check_due_now(recovery: bool = False):
        try:
            return await run_in_threadpool(current().run_once, recovery=recovery)
        except ScheduleError as exc:
            _translate(exc)

    return router
