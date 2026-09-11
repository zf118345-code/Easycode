from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.contracts.workspace import (
    FileDialogRequest,
    FolderDialogRequest,
    ProjectWorkspaceOpenRequest,
    ProjectWorkspacePathRequest,
    ProjectWorkspaceRepairRequest,
)
from core.services.project_workspace_service import ProjectWorkspaceManager, WorkspaceError


def create_project_workspace_router(manager: ProjectWorkspaceManager):
    router = APIRouter(prefix='/api/workspaces', tags=['项目工作区'])

    def translate(exc: WorkspaceError):
        message = str(exc)
        status = 409
        if '不存在' in message:
            status = 404
        raise HTTPException(status_code=status, detail=message) from exc

    @router.get('/active')
    async def active_workspace():
        return {'workspace': manager.active(), 'blockers': manager.blockers()}

    @router.get('/recent')
    async def recent_projects():
        return {'projects': await run_in_threadpool(manager.recent_projects)}

    @router.get('/changes')
    async def external_changes(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                manager.external_changes, x_workspace_id, x_workspace_generation,
            )
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/acknowledge')
    async def acknowledge_changes(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                manager.acknowledge, x_workspace_id, x_workspace_generation,
            )
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/inspect')
    async def inspect_project(payload: ProjectWorkspacePathRequest):
        try:
            return await run_in_threadpool(manager.inspect, payload.path)
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/open')
    async def open_project(payload: ProjectWorkspaceOpenRequest):
        try:
            result = await run_in_threadpool(
                manager.open,
                payload.path,
                initialize=payload.initialize,
                confirm_nonempty=payload.confirm_nonempty,
                project_name=payload.project_name,
                allow_read_only=payload.allow_read_only,
            )
            workspace = result.get('workspace') or {}
            if workspace and not workspace.get('read_only'):
                from core.services.platform_runtime_service import platform_runtime_service

                # Register immediately on project open so persisted schedules
                # resume after an IDE restart even if their dialog is never opened.
                await run_in_threadpool(platform_runtime_service.register_project, workspace['project_path'])
            return result
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/repair')
    async def repair_project(payload: ProjectWorkspaceRepairRequest):
        try:
            return await run_in_threadpool(
                manager.repair,
                payload.path,
                confirmed=payload.confirmed,
            )
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/close')
    async def close_project():
        try:
            return await run_in_threadpool(manager.close)
        except WorkspaceError as exc:
            translate(exc)

    @router.delete('/recent')
    async def remove_recent(payload: ProjectWorkspacePathRequest):
        try:
            return {'projects': await run_in_threadpool(manager.remove_recent, payload.path)}
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/choose-folder')
    async def choose_folder(payload: FolderDialogRequest = Body(default_factory=FolderDialogRequest)):
        try:
            return {'path': await run_in_threadpool(manager.choose_folder, payload.title)}
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/choose-file')
    async def choose_file(payload: FileDialogRequest = Body(default_factory=FileDialogRequest)):
        try:
            return {'path': await run_in_threadpool(manager.choose_file, payload.title, payload.extensions)}
        except WorkspaceError as exc:
            translate(exc)

    return router
