import logging

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from core.schemas import ImageTestRequestSchema, OcrTestRequestSchema

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_vision_router(vision_service):
    router = APIRouter(tags=['模板与视觉资源'])

    @router.get('/api/templates/tree')
    async def get_templates_tree(project_path: str):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_templates_tree, project_path)

    @router.get('/api/templates/preview')
    async def get_template_preview(project_path: str, relative_path: str = ''):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_template_preview, project_path, relative_path)

    @router.get('/api/image/thumb')
    async def get_image_thumb(project_path: str, name: str):
        if vision_service is None:
            _service_unavailable('VisionService')
        thumb_path = await run_in_threadpool(vision_service.get_image_thumb_path, project_path, name)
        return FileResponse(thumb_path, media_type='image/png')

    @router.post('/api/templates/mkdir')
    async def create_template_folder(data: dict = Body(...)):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.create_template_folder,
            data.get('project_path'),
            data.get('parent_path', ''),
            data.get('folder_name', ''),
        )

    @router.get('/api/regions')
    async def get_regions(project_path: str):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_regions, project_path)

    @router.post('/api/regions')
    async def save_region(data: dict = Body(...)):
        if vision_service is None:
            _service_unavailable('VisionService')
        template_name = data.get('template_name') or data.get('relative_path')
        crop_rect = data.get('crop_rect') or data.get('region')
        return await run_in_threadpool(vision_service.save_region, data.get('project_path'), template_name, crop_rect)

    @router.post('/api/ocr/test')
    async def test_ocr_recognition(request: OcrTestRequestSchema):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.test_ocr,
            request.project_path,
            request.region_value,
            request.gray_scale,
            request.gray_threshold,
            request.image_source,
        )

    @router.post('/api/image/test')
    async def test_image_recognition(request: ImageTestRequestSchema):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.test_image,
            request.project_path,
            request.template_name,
            request.gray_scale,
            request.gray_threshold,
        )

    return router
