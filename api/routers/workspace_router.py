import asyncio
import json
import logging
import queue

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from core.schemas import ContextSaveRequestSchema, CropScreenshotRequestSchema
from api.workspace_context import assert_matching_legacy_path

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_workspace_router(workspace_service, recording_service=None):
    router = APIRouter(tags=['工作区与截图'])

    @router.get('/api/screenshot/full')
    async def get_full_screenshot(request: Request, project_path: str | None = None):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        path = assert_matching_legacy_path(request, project_path)
        return await run_in_threadpool(workspace_service.get_full_screenshot, path)

    @router.get('/api/screenshot/capability')
    async def get_capture_capability(request: Request, project_path: str | None = None, probe: bool = False):
        from core.services.capture_capability_service import capture_capability_service

        path = assert_matching_legacy_path(request, project_path)
        return await run_in_threadpool(capture_capability_service.inspect_project, path, probe=probe)

    @router.post('/api/screenshot/crop')
    async def crop_screenshot(payload: CropScreenshotRequestSchema, request: Request):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(
            workspace_service.crop_screenshot,
            assert_matching_legacy_path(request, payload.project_path, writable=True),
            payload.template_name,
            payload.crop_rect,
        )

    # 逐帧录制：按保存策略筛选；落盘帧均无损、不覆盖且不自动清理。
    @router.post('/api/frame-recording/start')
    async def start_frame_recording(request: Request, data: dict = Body(...)):
        if recording_service is None:
            _service_unavailable('FrameRecordingService')
        try:
            path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
            options = data.get('options') if isinstance(data.get('options'), dict) else None
            if options:
                return await run_in_threadpool(recording_service.start, path, options)
            return await run_in_threadpool(recording_service.start, path)
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/api/frame-recording/stop')
    async def stop_frame_recording(data: dict | None = Body(default=None)):
        if recording_service is None:
            _service_unavailable('FrameRecordingService')
        data = data or {}
        return await run_in_threadpool(recording_service.stop, data.get('reason', 'api'))

    @router.get('/api/frame-recording/status')
    async def get_frame_recording_status():
        if recording_service is None:
            _service_unavailable('FrameRecordingService')
        return recording_service.get_state()

    @router.post('/api/frame-recording/mark')
    async def mark_frame_recording_event(data: dict | None = Body(default=None)):
        if recording_service is None:
            _service_unavailable('FrameRecordingService')
        data = data or {}
        try:
            return recording_service.mark_event(str(data.get('label') or '手动标记'))
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/api/frame-recording/sessions')
    async def list_frame_recording_sessions(request: Request, project_path: str | None = None):
        from core.services.recording_replay_service import recording_replay_service

        path = assert_matching_legacy_path(request, project_path)
        sessions = await run_in_threadpool(recording_replay_service.list_sessions, path)
        return {'sessions': sessions}

    @router.get('/api/frame-recording/sessions/{session_id}/frames')
    async def list_recorded_frames(
        request: Request,
        session_id: str,
        project_path: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ):
        from core.services.recording_replay_service import recording_replay_service

        path = assert_matching_legacy_path(request, project_path)
        return await run_in_threadpool(recording_replay_service.list_frames, path, session_id, offset, limit)

    @router.get('/api/frame-recording/sessions/{session_id}/frames/{frame_index}/image')
    async def get_recorded_frame_image(
        request: Request,
        session_id: str,
        frame_index: int,
        project_path: str | None = None,
        thumbnail: bool = False,
    ):
        from core.services.recording_replay_service import recording_replay_service

        path = assert_matching_legacy_path(request, project_path)
        if thumbnail:
            content = await run_in_threadpool(recording_replay_service.frame_thumbnail_bytes, path, session_id, frame_index)
            return Response(content=content, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600'})
        content, _ = await run_in_threadpool(recording_replay_service.frame_bytes, path, session_id, frame_index)
        return Response(content=content, media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})

    @router.post('/api/frame-recording/analyze')
    async def analyze_recorded_frame(request: Request, data: dict = Body(...)):
        from core.services.recording_replay_service import recording_replay_service

        path = assert_matching_legacy_path(request, data.get('project_path'))
        return await run_in_threadpool(
            recording_replay_service.analyze_frame,
            path,
            str(data.get('session_id') or ''),
            int(data.get('frame_index') or 0),
            diagnostics=bool(data.get('diagnostics')),
        )

    @router.post('/api/frame-recording/analyze-session')
    async def analyze_recording_session(request: Request, data: dict = Body(...)):
        from core.services.recording_replay_service import recording_replay_service

        path = assert_matching_legacy_path(request, data.get('project_path'))
        return await run_in_threadpool(
            recording_replay_service.analyze_session,
            path,
            str(data.get('session_id') or ''),
            diagnostics=bool(data.get('diagnostics')),
            changes_only=bool(data.get('changes_only')),
            change_threshold=float(data.get('change_threshold') or 0.006),
            step=int(data.get('step') or 1),
            max_frames=int(data.get('max_frames') or 10000),
        )

    @router.get('/api/frame-recording/events')
    async def frame_recording_events():
        if recording_service is None:
            _service_unavailable('FrameRecordingService')
        subscriber = recording_service.subscribe()

        async def generate():
            try:
                while True:
                    try:
                        event = await asyncio.to_thread(subscriber.get, True, 15)
                        yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
                    except queue.Empty:
                        yield ': keepalive\n\n'
            finally:
                recording_service.unsubscribe(subscriber)

        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    @router.get('/api/windows')
    async def get_windows():
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_windows)

    @router.post('/api/adb/resolve')
    async def resolve_adb_device(data: dict = Body(...)):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(
            workspace_service.resolve_adb_device,
            data.get('window_title', ''),
            int(data.get('window_hwnd', 0) or 0),
            int(data.get('process_id', 0) or 0),
        )

    @router.get('/api/adb/devices')
    async def get_adb_devices():
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_adb_devices)

    @router.post('/api/context')
    async def save_context(payload: ContextSaveRequestSchema, request: Request):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        payload.project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        return await run_in_threadpool(workspace_service.save_context, payload)

    @router.get('/api/context')
    async def get_context(request: Request, project_path: str | None = None):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_context, assert_matching_legacy_path(request, project_path))

    # ⚡ 项目级引擎设置（前端「项目设置」页面）：GET 返回合并后的设置 + 分组元数据；PUT 保存
    @router.get('/api/project/settings')
    async def get_project_settings(request: Request, project_path: str | None = None):
        from core.services.blueprint_service import BlueprintService
        from core.settings import SETTINGS_GROUPS, merge_settings

        project_path = assert_matching_legacy_path(request, project_path)
        raw = BlueprintService.load_project_meta(project_path) or {}
        settings = merge_settings(raw.get('settings'))
        return {'status': 'success', 'settings': settings, 'groups': SETTINGS_GROUPS}

    @router.put('/api/project/settings')
    async def save_project_settings(request: Request, data: dict = Body(...)):
        from core.services.blueprint_service import BlueprintService
        from core.settings import merge_settings

        project_path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
        raw = BlueprintService.load_project_meta(project_path) or {}
        raw['settings'] = merge_settings(data.get('settings'))
        BlueprintService.save_project_meta(project_path, raw)
        return {'status': 'success', 'settings': raw['settings']}

    return router
