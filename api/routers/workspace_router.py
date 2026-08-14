import logging

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from core.schemas import ContextSaveRequestSchema, CropScreenshotRequestSchema

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_workspace_router(workspace_service):
    router = APIRouter(tags=['工作区与截图'])

    @router.get('/api/screenshot/full')
    async def get_full_screenshot(project_path: str = ''):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_full_screenshot, project_path)

    @router.post('/api/screenshot/crop')
    async def crop_screenshot(request: CropScreenshotRequestSchema):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(
            workspace_service.crop_screenshot, request.project_path, request.template_name, request.crop_rect
        )

    @router.post('/api/screenshot')
    async def take_screenshot(request: dict = Body(...)):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        res = await run_in_threadpool(workspace_service.take_screenshot, request)
        return JSONResponse(content=res)

    @router.get('/api/windows')
    async def get_windows():
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_windows)

    @router.post('/api/context')
    async def save_context(request: ContextSaveRequestSchema):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.save_context, request)

    @router.get('/api/context')
    async def get_context(project_path: str):
        if workspace_service is None:
            _service_unavailable('WorkspaceService')
        return await run_in_threadpool(workspace_service.get_context, project_path)

    return router
