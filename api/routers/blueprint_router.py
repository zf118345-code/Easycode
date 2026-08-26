import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from core.schemas import (
    FunctionCreateRequestSchema,
    FunctionSaveRequestSchema,
    SaveBlueprintRequestSchema,
    TopologySaveRequestSchema,
    WorkflowSaveRequestSchema,
)
from api.workspace_context import assert_matching_legacy_path

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_blueprint_router(blueprint_service, load_project_fn):
    router = APIRouter(tags=['项目蓝图'])

    # ============ 项目元数据（project.json） ============

    @router.get('/api/blueprint')
    async def get_full_blueprint(request: Request, project_path: str | None = None):
        """加载项目元数据（project.json：project_name/variables/ui_state）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, project_path)
            return await run_in_threadpool(blueprint_service.load_project_meta, path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载项目元数据失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载项目元数据失败: {str(e)}') from e

    @router.post('/api/blueprint/save')
    async def save_full_blueprint(payload: SaveBlueprintRequestSchema, request: Request):
        """保存蓝图：按字段拆分写入三个文件（payload 可只含部分字段）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, payload.project_path, writable=True)
            await run_in_threadpool(blueprint_service.save_blueprint, path, payload.blueprint_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存蓝图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存蓝图失败: {str(e)}') from e

    # ============ 流程画布（workflow.json） ============

    @router.get('/api/workflow')
    async def get_workflow(request: Request, project_path: str | None = None):
        """加载流程与函数（workflow.json：{main_graph, functions, function_folders}）。"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, project_path)
            return await run_in_threadpool(blueprint_service.load_workflow, path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载流程画布失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载流程画布失败: {str(e)}') from e

    @router.post('/api/workflow/save')
    async def save_workflow(payload: WorkflowSaveRequestSchema, request: Request):
        """保存流程画布（workflow.json）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, payload.project_path, writable=True)
            await run_in_threadpool(blueprint_service.save_workflow, path, payload.workflow_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存流程画布失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存流程画布失败: {str(e)}') from e

    # ============ 拓扑地图（topology.json） ============

    @router.get('/api/topology')
    async def get_topology(request: Request, project_path: str | None = None):
        """加载项目唯一扁平页面地图（topology.json：{nodes, edges, blocks}）。"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, project_path)
            return await run_in_threadpool(blueprint_service.load_topology, path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载拓扑地图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载拓扑地图失败: {str(e)}') from e

    @router.post('/api/topology/save')
    async def save_topology(payload: TopologySaveRequestSchema, request: Request):
        """保存拓扑地图（topology.json）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            path = assert_matching_legacy_path(request, payload.project_path, writable=True)
            await run_in_threadpool(blueprint_service.save_topology, path, payload.topology_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存拓扑地图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存拓扑地图失败: {str(e)}') from e

    # ============ 函数库 ============

    @router.get('/api/functions')
    async def list_functions(request: Request, project_path: str | None = None):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.list_functions, assert_matching_legacy_path(request, project_path))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'获取函数列表失败: {str(e)}') from e

    @router.get('/api/functions/{function_id}')
    async def get_function(function_id: str, request: Request, project_path: str | None = None):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.get_function, function_id, assert_matching_legacy_path(request, project_path))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'获取函数失败: {str(e)}') from e

    @router.put('/api/functions/{function_id}')
    async def save_function(function_id: str, payload: FunctionSaveRequestSchema, request: Request):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        return await run_in_threadpool(blueprint_service.save_function, function_id, project_path, payload.function_data)

    @router.post('/api/functions')
    async def create_function(payload: FunctionCreateRequestSchema, request: Request):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        return await run_in_threadpool(blueprint_service.create_function, project_path, payload.name, payload.folder_id)

    @router.delete('/api/functions/{function_id}')
    async def delete_function(function_id: str, request: Request, project_path: str | None = None):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        return await run_in_threadpool(
            blueprint_service.delete_function, function_id, assert_matching_legacy_path(request, project_path, writable=True)
        )

    @router.post('/api/functions/{function_id}/duplicate')
    async def duplicate_function(function_id: str, request: Request, project_path: str | None = None):
        project_path = assert_matching_legacy_path(request, project_path, writable=True)
        return await run_in_threadpool(blueprint_service.duplicate_function, function_id, project_path)

    @router.get('/api/functions/{function_id}/export')
    async def export_function(function_id: str, request: Request, project_path: str | None = None):
        from core.services.function_package_service import FunctionPackageService

        project_path = assert_matching_legacy_path(request, project_path, writable=True)
        path = await run_in_threadpool(FunctionPackageService.export_function, project_path, function_id)
        return FileResponse(path, filename=os.path.basename(path), media_type='application/octet-stream')

    @router.post('/api/functions/import')
    async def import_function(request: Request, package_path: str, project_path: str | None = None):
        from core.services.function_package_service import FunctionPackageService

        project_path = assert_matching_legacy_path(request, project_path, writable=True)
        return await run_in_threadpool(FunctionPackageService.import_function, project_path, package_path)

    # ============ 版本历史 ============

    @router.get('/api/history')
    async def list_history(request: Request, project_path: str | None = None):
        from core.services.snapshot_service import SnapshotService

        project_path = assert_matching_legacy_path(request, project_path)
        return {'snapshots': await run_in_threadpool(SnapshotService.list, project_path)}

    @router.post('/api/history/{snapshot_id}/restore')
    async def restore_history(snapshot_id: str, request: Request, project_path: str | None = None):
        from core.services.snapshot_service import SnapshotService

        try:
            project_path = assert_matching_legacy_path(request, project_path, writable=True)
            return await run_in_threadpool(SnapshotService.restore, project_path, snapshot_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
