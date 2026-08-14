import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from core.schemas import (
    SaveBlueprintRequestSchema,
    SaveTaskRequestSchema,
    TopologySaveRequestSchema,
    WorkflowSaveRequestSchema,
)

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_blueprint_router(blueprint_service, load_project_fn):
    router = APIRouter(tags=['蓝图与任务'])

    # ============ 项目元数据（project.json） ============

    @router.get('/api/blueprint')
    async def get_full_blueprint(project_path: str):
        """加载项目元数据（project.json：project_name/variables/ui_state）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.load_project_meta, project_path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载项目元数据失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载项目元数据失败: {str(e)}') from e

    @router.post('/api/blueprint/save')
    async def save_full_blueprint(request: SaveBlueprintRequestSchema):
        """保存蓝图：按字段拆分写入三个文件（payload 可只含部分字段）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            await run_in_threadpool(blueprint_service.save_blueprint, request.project_path, request.blueprint_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存蓝图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存蓝图失败: {str(e)}') from e

    # ============ 流程画布（workflow.json） ============

    @router.get('/api/workflow')
    async def get_workflow(project_path: str):
        """加载流程画布（workflow.json：{tasks, edges}）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.load_workflow, project_path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载流程画布失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载流程画布失败: {str(e)}') from e

    @router.post('/api/workflow/save')
    async def save_workflow(request: WorkflowSaveRequestSchema):
        """保存流程画布（workflow.json）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            await run_in_threadpool(blueprint_service.save_workflow, request.project_path, request.workflow_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存流程画布失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存流程画布失败: {str(e)}') from e

    # ============ 拓扑地图（topology.json） ============

    @router.get('/api/topology')
    async def get_topology(project_path: str):
        """加载拓扑地图（topology.json：{tasks, edges}）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.load_topology, project_path)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'加载拓扑地图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'加载拓扑地图失败: {str(e)}') from e

    @router.post('/api/topology/save')
    async def save_topology(request: TopologySaveRequestSchema):
        """保存拓扑地图（topology.json）"""
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            await run_in_threadpool(blueprint_service.save_topology, request.project_path, request.topology_data)
            return {'status': 'success'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'保存拓扑地图失败: {e}', exc_info=True)
            raise HTTPException(status_code=500, detail=f'保存拓扑地图失败: {str(e)}') from e

    # ============ 任务 CRUD（操作 workflow.json） ============

    @router.get('/api/tasks')
    async def list_tasks(project_path: str):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.list_tasks, project_path)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'获取任务列表失败: {str(e)}') from e

    @router.get('/api/tasks/{task_id}')
    async def get_task(task_id: str, project_path: str):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        try:
            return await run_in_threadpool(blueprint_service.get_task, task_id, project_path)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'获取任务失败: {str(e)}') from e

    @router.put('/api/tasks/{task_id}')
    async def save_task(task_id: str, request: SaveTaskRequestSchema):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        return await run_in_threadpool(blueprint_service.save_task, task_id, request)

    @router.post('/api/tasks')
    async def create_task(request: SaveTaskRequestSchema):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        return await run_in_threadpool(blueprint_service.create_task, request)

    @router.delete('/api/tasks/{task_id}')
    async def delete_task(task_id: str, project_path: str):
        if blueprint_service is None:
            _service_unavailable('BlueprintService')
        return await run_in_threadpool(blueprint_service.delete_task, task_id, project_path)

    @router.get('/api/tasks/{task_id}/nodes')
    async def get_task_nodes(task_id: str, project_path: str):
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目不存在')
        try:
            project = await run_in_threadpool(load_project_fn, project_path)
            task = project.tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail='任务不存在')
            return [{'node_id': n.node_id, 'node_name': n.node_name} for n in task.nodes]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'获取节点列表失败: {str(e)}') from e

    return router
