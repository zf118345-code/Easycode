from __future__ import annotations

from fastapi import HTTPException, Request

from core.services.project_workspace_service import WorkspaceError, project_workspace_manager


def request_project_path(request: Request, *, writable: bool = False) -> str:
    workspace_id = str(request.headers.get('x-workspace-id') or '')
    generation_raw = request.headers.get('x-workspace-generation')
    if not workspace_id or generation_raw is None:
        raise HTTPException(status_code=409, detail='缺少当前工作区身份，请重新打开项目')
    try:
        generation = int(generation_raw)
        return project_workspace_manager.require(workspace_id, generation, writable=writable)
    except (WorkspaceError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def assert_matching_legacy_path(request: Request, supplied_path: str | None, *, writable: bool = False) -> str:
    """Transition guard: old request models may still contain project_path.

    The value is never trusted.  It must resolve to the active workspace and is
    ignored afterwards.  This lets routers migrate independently without
    reopening the arbitrary-path vulnerability.
    """
    active = request_project_path(request, writable=writable)
    if supplied_path:
        try:
            supplied_key = project_workspace_manager.path_key(supplied_path)
            active_key = project_workspace_manager.path_key(active)
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if supplied_key != active_key:
            raise HTTPException(status_code=409, detail='请求中的项目路径不属于当前工作区')
    return active

