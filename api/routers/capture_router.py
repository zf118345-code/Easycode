import os

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.services.capture_session_service import capture_session_service
from api.workspace_context import assert_matching_legacy_path


def create_capture_router() -> APIRouter:
    router = APIRouter(tags=['冻结捕获'])

    @router.post('/api/capture/session/register')
    async def register_session(request: Request, payload: dict = Body(...)):
        payload['project_path'] = assert_matching_legacy_path(request, payload.get('project_path'))
        return capture_session_service.register_ui_session(payload)

    @router.post('/api/capture/session/unregister')
    async def unregister_session(payload: dict = Body(...)):
        return capture_session_service.unregister_ui_session(str(payload.get('session_id') or ''))

    @router.post('/api/capture/trigger')
    async def trigger_capture(payload: dict = Body(default_factory=dict)):
        return await run_in_threadpool(capture_session_service.trigger_global_capture, payload)

    @router.post('/api/capture/prewarm')
    async def prewarm_capture_host():
        return await run_in_threadpool(capture_session_service.prewarm_native_host)

    @router.post('/api/capture/replay')
    async def replay_capture(payload: dict = Body(...)):
        return await run_in_threadpool(
            capture_session_service.trigger_recording_capture,
            str(payload.get('recording_session_id') or ''),
            int(payload.get('frame_index') or 0),
        )

    @router.post('/api/capture/snapshot')
    async def create_snapshot(request: Request, payload: dict = Body(...)):
        return await run_in_threadpool(
            capture_session_service.create_snapshot,
            assert_matching_legacy_path(request, payload.get('project_path')),
            session_id=str(payload.get('session_id') or ''),
        )

    @router.get('/api/capture/snapshot/{snapshot_id}')
    async def get_snapshot(snapshot_id: str):
        return capture_session_service.get_snapshot(snapshot_id)

    @router.post('/api/capture/close')
    async def close_capture(payload: dict = Body(default_factory=dict)):
        return capture_session_service.close_capture(str(payload.get('snapshot_id') or ''))

    @router.post('/api/capture/assets')
    async def save_assets(payload: dict = Body(...)):
        return await run_in_threadpool(capture_session_service.save_assets, payload)

    @router.post('/api/capture/assets/undo')
    async def undo_assets(payload: dict = Body(...)):
        return await run_in_threadpool(
            capture_session_service.undo_assets,
            str(payload.get('transaction_id') or ''),
        )

    @router.get('/api/capture/directories')
    async def list_directories(project_path: str | None = None):
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

        active = project_workspace_manager.active()
        if not active:
            raise HTTPException(status_code=409, detail='当前没有打开项目')
        try:
            if project_path and project_workspace_manager.path_key(project_path) != project_workspace_manager.path_key(active['project_path']):
                raise HTTPException(status_code=409, detail='资源目录不属于当前工作区')
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        project_path = active['project_path']
        root = os.path.abspath(os.path.join(project_path, 'templates'))
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')
        os.makedirs(root, exist_ok=True)
        directories = ['']
        for current, dirnames, _ in os.walk(root):
            dirnames[:] = [name for name in dirnames if not name.startswith('.')]
            rel = os.path.relpath(current, root).replace('\\', '/')
            if rel != '.':
                directories.append(rel)
        return {'directories': sorted(set(directories))}

    @router.post('/api/capture/action')
    async def request_action(payload: dict = Body(...)):
        return await run_in_threadpool(capture_session_service.request_ide_action, payload)

    @router.post('/api/capture/action/ack')
    async def acknowledge_action(payload: dict = Body(...)):
        request_id = str(payload.get('request_id') or '')
        return capture_session_service.acknowledge_ide_action(request_id, payload.get('result') or {})

    return router
