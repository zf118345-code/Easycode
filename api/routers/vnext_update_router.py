"""Author and terminal HTTP surfaces for signed v6 updates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.contracts.vnext_update import (
    AuthorUpdateConfigurationRequest,
    InitializeUpdateRepositoryRequest,
    PublishApplicationUpdateRequest,
    PublishContentUpdateRequest,
    RequiredUpdatePolicyRequest,
    RevokeUpdatePolicyRequest,
    UpdatePreferencesRequest,
    UpdateRolloutRequest,
)
from api.errors import failure_detail
from api.routers.vnext_player_update_router import create_vnext_player_update_router
from core.vnext import vnext_workspace_manager
from core.vnext.ide_update_v6 import ide_update_service_v6
from core.vnext.update_protocol_v6 import UpdateProtocolError
from core.vnext.workspace_context import VNextWorkspaceError

WorkspaceId = Annotated[str, Header(alias="X-Workspace-ID")]
WorkspaceGeneration = Annotated[int, Header(alias="X-Workspace-Generation")]


def create_vnext_update_router() -> APIRouter:
    router = APIRouter(prefix="/api/vnext", tags=["EasyCode vNext Updates"])

    def translate(exc: Exception) -> None:
        code = exc.code if isinstance(exc, UpdateProtocolError) else "update_operation_failed"
        status = 422 if isinstance(exc, UpdateProtocolError) else 409
        raise HTTPException(
            status_code=status,
            detail=failure_detail(
                str(code),
                str(exc),
                action="fix_request" if status == 422 else "retry",
            ),
        ) from exc

    @router.get("/updates/configuration")
    async def update_configuration(
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.update_configuration,
                x_workspace_id,
                x_workspace_generation,
            )
        except (VNextWorkspaceError, UpdateProtocolError) as exc:
            translate(exc)

    @router.get("/updates/ide/status")
    async def ide_update_status():
        try:
            return await run_in_threadpool(ide_update_service_v6.status)
        except UpdateProtocolError as exc:
            translate(exc)

    @router.post("/updates/ide/check")
    async def ide_update_check():
        try:
            return await run_in_threadpool(ide_update_service_v6.check)
        except UpdateProtocolError as exc:
            translate(exc)

    @router.post("/updates/ide/download")
    async def ide_update_download():
        try:
            return await run_in_threadpool(ide_update_service_v6.download)
        except UpdateProtocolError as exc:
            translate(exc)

    @router.post("/updates/ide/apply")
    async def ide_update_apply():
        try:
            return await run_in_threadpool(ide_update_service_v6.apply)
        except UpdateProtocolError as exc:
            translate(exc)

    @router.put("/updates/ide/preferences")
    async def ide_update_preferences(payload: UpdatePreferencesRequest):
        try:
            return await run_in_threadpool(
                ide_update_service_v6.save_preferences,
                payload.model_dump(mode="python"),
            )
        except UpdateProtocolError as exc:
            translate(exc)

    @router.put("/updates/configuration")
    async def save_update_configuration(
        payload: AuthorUpdateConfigurationRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.save_update_configuration,
                x_workspace_id,
                x_workspace_generation,
                payload.model_dump(mode="json"),
            )
        except (VNextWorkspaceError, UpdateProtocolError) as exc:
            translate(exc)

    @router.post("/updates/repository/initialize")
    async def initialize_update_repository(
        payload: InitializeUpdateRepositoryRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.initialize_repository,
                x_workspace_id,
                x_workspace_generation,
                domain=payload.domain,
                repository_root=payload.repository_root,
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError) as exc:
            translate(exc)

    @router.post("/updates/releases/project-content")
    async def publish_project_content_update(
        payload: PublishContentUpdateRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.publish_project_content,
                x_workspace_id,
                x_workspace_generation,
                **payload.model_dump(mode="python"),
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError, ValueError) as exc:
            translate(exc)

    @router.post("/updates/releases/player-application")
    async def publish_player_application_update(
        payload: PublishApplicationUpdateRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.publish_application_artifact,
                x_workspace_id,
                x_workspace_generation,
                **payload.model_dump(mode="python"),
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError, ValueError) as exc:
            translate(exc)

    @router.put("/updates/rollout")
    async def set_update_rollout(
        payload: UpdateRolloutRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        values = payload.model_dump(mode="python")
        domain = values.pop("domain")
        repository_root = values.pop("repository_root")
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.set_rollout,
                x_workspace_id,
                x_workspace_generation,
                domain=domain,
                repository_root=repository_root,
                **values,
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError, ValueError) as exc:
            translate(exc)

    @router.put("/updates/required-policy")
    async def set_required_update_policy(
        payload: RequiredUpdatePolicyRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.set_required_policy,
                x_workspace_id,
                x_workspace_generation,
                **payload.model_dump(mode="python"),
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError, ValueError) as exc:
            translate(exc)

    @router.post("/updates/required-policy/revoke")
    async def revoke_required_update_policy(
        payload: RevokeUpdatePolicyRequest,
        x_workspace_id: WorkspaceId,
        x_workspace_generation: WorkspaceGeneration,
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager._updates.revoke_required_policy,
                x_workspace_id,
                x_workspace_generation,
                **payload.model_dump(mode="python"),
            )
        except (VNextWorkspaceError, UpdateProtocolError, OSError, ValueError) as exc:
            translate(exc)

    router.include_router(create_vnext_player_update_router(prefix="/player/runtime"))
    return router


__all__ = ["create_vnext_player_update_router", "create_vnext_update_router"]
