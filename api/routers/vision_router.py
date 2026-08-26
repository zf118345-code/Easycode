import logging

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from core.schemas import (
    ImageTestRequestSchema,
    OcrTestRequestSchema,
    TemplateDeleteRequestSchema,
    TemplateMoveRequestSchema,
)
from api.workspace_context import assert_matching_legacy_path

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_vision_router(vision_service):
    router = APIRouter(tags=['模板与视觉资源'])

    @router.get('/api/templates/tree')
    async def get_templates_tree(request: Request, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_templates_tree, assert_matching_legacy_path(request, project_path))

    @router.get('/api/templates/preview')
    async def get_template_preview(request: Request, relative_path: str = '', project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_template_preview, assert_matching_legacy_path(request, project_path), relative_path)

    @router.get('/api/image/thumb')
    async def get_image_thumb(request: Request, name: str, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        thumb_path = await run_in_threadpool(vision_service.get_image_thumb_path, assert_matching_legacy_path(request, project_path), name)
        return FileResponse(thumb_path, media_type='image/png')

    @router.get('/api/templates/resolve')
    async def resolve_template(request: Request, reference: str, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.resolve_template, assert_matching_legacy_path(request, project_path), reference)

    @router.post('/api/templates/mkdir')
    async def create_template_folder(request: Request, data: dict = Body(...)):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.create_template_folder,
            assert_matching_legacy_path(request, data.get('project_path'), writable=True),
            data.get('parent_path', ''),
            data.get('folder_name', ''),
        )

    @router.get('/api/regions')
    async def get_regions(request: Request, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(vision_service.get_regions, assert_matching_legacy_path(request, project_path))

    @router.post('/api/regions')
    async def save_region(request: Request, data: dict = Body(...)):
        if vision_service is None:
            _service_unavailable('VisionService')
        template_name = data.get('template_name') or data.get('relative_path')
        crop_rect = data.get('crop_rect') or data.get('region')
        return await run_in_threadpool(
            vision_service.save_region,
            assert_matching_legacy_path(request, data.get('project_path'), writable=True),
            template_name,
            crop_rect,
            data.get('reference_size'),
        )

    @router.get('/api/templates/impact')
    async def inspect_template_mutation(request: Request, relative_path: str, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.inspect_template_mutation, assert_matching_legacy_path(request, project_path), relative_path,
        )

    @router.post('/api/templates/delete')
    async def delete_template_entry(payload: TemplateDeleteRequestSchema, request: Request):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.delete_template_entry,
            assert_matching_legacy_path(request, payload.project_path, writable=True),
            payload.relative_path,
        )

    @router.post('/api/templates/move')
    async def move_template_entry(payload: TemplateMoveRequestSchema, request: Request):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.move_template_entry,
            assert_matching_legacy_path(request, payload.project_path, writable=True),
            payload.relative_path,
            payload.target_parent_path,
            payload.new_name,
        )

    @router.get('/api/templates/trash')
    async def list_template_trash(request: Request, project_path: str | None = None):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.list_template_trash,
            assert_matching_legacy_path(request, project_path),
        )

    @router.post('/api/templates/trash/{transaction_id}/restore')
    async def restore_template_trash(transaction_id: str, request: Request, data: dict = Body(default={})):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.restore_template_entry,
            assert_matching_legacy_path(request, data.get('project_path'), writable=True),
            transaction_id,
        )

    @router.post('/api/templates/register')
    async def register_template(request: Request, data: dict = Body(...)):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.register_template,
            assert_matching_legacy_path(request, data.get('project_path'), writable=True),
            data.get('relative_path', ''),
            data.get('kind', ''),
        )

    @router.post('/api/ocr/test')
    async def test_ocr_recognition(payload: OcrTestRequestSchema, request: Request):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.test_ocr,
            assert_matching_legacy_path(request, payload.project_path),
            payload.region_value,
            payload.gray_scale,
            payload.gray_threshold,
            payload.image_source,
            payload.region_reference_size,
        )

    @router.post('/api/image/test')
    async def test_image_recognition(payload: ImageTestRequestSchema, request: Request):
        if vision_service is None:
            _service_unavailable('VisionService')
        return await run_in_threadpool(
            vision_service.test_image,
            assert_matching_legacy_path(request, payload.project_path),
            payload.template_name,
            payload.gray_scale,
            payload.gray_threshold,
            getattr(payload, 'region_type', 'fullwindow'),
            getattr(payload, 'region_value', None),
            getattr(payload, 'region_reference_size', None),
            getattr(payload, 'preview_only', False),
        )

    return router
