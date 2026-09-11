import os

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from api.contracts.capture import (
    CaptureActionAcknowledgeRequest,
    CaptureActionRequest,
    CaptureAssetSaveRequest,
    CaptureAssetUndoRequest,
    CaptureCloseRequest,
    CaptureReplayRequest,
    CaptureSessionRegisterRequest,
    CaptureSessionRequest,
    CaptureSnapshotRequest,
    CaptureTriggerRequest,
)
from api.idempotency import execute_idempotent
from api.workspace_context import assert_matching_legacy_path
from core.services.capture_session_service import capture_session_service


def create_capture_router() -> APIRouter:
    router = APIRouter(tags=['冻结捕获'])

    @router.post('/api/capture/session/register')
    async def register_session(request: Request, request_body: CaptureSessionRegisterRequest):
        payload = request_body.model_dump(exclude_none=True)
        if request_body.workspace_kind == 'player':
            from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
            try:
                payload['project_path'] = vnext_player_bundle_manager.validate_player_capture_session(payload)
            except PlayerBundleError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        elif request_body.workspace_kind == 'vnext':
            from core.vnext import VNextWorkspaceError, vnext_workspace_manager
            try:
                payload['project_path'] = vnext_workspace_manager.require_path(
                    str(request.headers.get('x-workspace-id') or ''),
                    int(request.headers.get('x-workspace-generation') or -1),
                )
            except (VNextWorkspaceError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        else:
            payload['project_path'] = assert_matching_legacy_path(request, payload.get('project_path'))
        return capture_session_service.register_ui_session(payload)

    @router.post('/api/capture/session/unregister')
    async def unregister_session(payload: CaptureSessionRequest):
        return capture_session_service.unregister_ui_session(payload.session_id)

    @router.post('/api/capture/trigger')
    async def trigger_capture(payload: CaptureTriggerRequest = Body(default_factory=CaptureTriggerRequest)):
        return await run_in_threadpool(
            capture_session_service.trigger_global_capture,
            payload.model_dump(exclude_none=True),
        )

    @router.post('/api/capture/prewarm')
    async def prewarm_capture_host():
        return await run_in_threadpool(capture_session_service.prewarm_native_host)

    @router.post('/api/capture/replay')
    async def replay_capture(payload: CaptureReplayRequest):
        return await run_in_threadpool(
            capture_session_service.trigger_recording_capture,
            payload.recording_session_id,
            payload.frame_index,
            payload.session_id,
        )

    @router.post('/api/capture/snapshot')
    async def create_snapshot(request: Request, payload: CaptureSnapshotRequest):
        session_id = payload.session_id
        if session_id:
            session = capture_session_service.active_ui_session(session_id)
            requested = os.path.abspath(str(payload.project_path or session['project_path']))
            bound = os.path.abspath(str(session['project_path']))
            if os.path.normcase(os.path.realpath(requested)) != os.path.normcase(os.path.realpath(bound)):
                raise HTTPException(status_code=409, detail='截图刷新请求与当前捕获会话项目不一致')
            project_path = bound
        else:
            project_path = assert_matching_legacy_path(request, payload.project_path)
        return await run_in_threadpool(
            capture_session_service.create_snapshot,
            project_path,
            session_id=session_id,
        )

    @router.get('/api/capture/snapshot/{snapshot_id}')
    async def get_snapshot(snapshot_id: str, include_image: bool = True):
        return capture_session_service.get_snapshot(snapshot_id, include_image=include_image)

    @router.post('/api/capture/close')
    async def close_capture(payload: CaptureCloseRequest = Body(default_factory=CaptureCloseRequest)):
        return capture_session_service.close_capture(payload.snapshot_id)

    @router.post('/api/capture/assets')
    async def save_assets(
        payload: CaptureAssetSaveRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def produce():
            return await run_in_threadpool(capture_session_service.save_assets, payload.model_dump())

        return await execute_idempotent(
            idempotency_key,
            'capture.assets.save',
            payload.model_dump(mode='json'),
            produce,
        )

    @router.post('/api/capture/assets/undo')
    async def undo_assets(payload: CaptureAssetUndoRequest):
        return await run_in_threadpool(capture_session_service.undo_assets, payload.transaction_id)

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
    async def request_action(
        payload: CaptureActionRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def produce():
            return await run_in_threadpool(capture_session_service.request_ide_action, payload.model_dump())

        return await execute_idempotent(
            idempotency_key,
            'legacy.capture.action',
            payload.model_dump(mode='json'),
            produce,
        )

    @router.post('/api/capture/action/ack')
    async def acknowledge_action(payload: CaptureActionAcknowledgeRequest):
        return capture_session_service.acknowledge_ide_action(payload.request_id, payload.result)

    return router
