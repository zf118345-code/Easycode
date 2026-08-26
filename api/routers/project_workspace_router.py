from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

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
    async def inspect_project(data: dict = Body(...)):
        try:
            return await run_in_threadpool(manager.inspect, str(data.get('path') or ''))
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/open')
    async def open_project(data: dict = Body(...)):
        try:
            result = await run_in_threadpool(
                manager.open,
                str(data.get('path') or ''),
                initialize=bool(data.get('initialize', False)),
                confirm_nonempty=bool(data.get('confirm_nonempty', False)),
                project_name=str(data.get('project_name') or ''),
                allow_read_only=bool(data.get('allow_read_only', True)),
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
    async def repair_project(data: dict = Body(...)):
        try:
            return await run_in_threadpool(
                manager.repair,
                str(data.get('path') or ''),
                confirmed=bool(data.get('confirmed', False)),
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
    async def remove_recent(data: dict = Body(...)):
        try:
            return {'projects': await run_in_threadpool(manager.remove_recent, str(data.get('path') or ''))}
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/choose-folder')
    async def choose_folder(data: dict | None = Body(default=None)):
        try:
            title = str((data or {}).get('title') or '选择 EasyCode 项目文件夹')
            return {'path': await run_in_threadpool(manager.choose_folder, title)}
        except WorkspaceError as exc:
            translate(exc)

    @router.post('/choose-file')
    async def choose_file(data: dict | None = Body(default=None)):
        try:
            payload = data or {}
            title = str(payload.get('title') or '选择文件')
            extensions = [str(item) for item in (payload.get('extensions') or [])]
            return {'path': await run_in_threadpool(manager.choose_file, title, extensions)}
        except WorkspaceError as exc:
            translate(exc)

    return router
