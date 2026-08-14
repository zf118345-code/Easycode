import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from core.schemas import RunRequestSchema

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f"服务不可用: {name} 模块未加载")


def create_execution_router(execution_service):
    router = APIRouter(tags=["执行引擎"])

    @router.post("/api/run")
    async def run_task(request: RunRequestSchema, background_tasks: BackgroundTasks):
        """运行任务"""
        if execution_service is None:
            _service_unavailable("ExecutionService")
        bp_dict = request.blueprint_data if request.blueprint_data else None
        try:
            return execution_service.run_task(
                request.project_path, request.task_id,
                request.start_node_id, bp_dict, background_tasks
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"启动任务失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

    @router.get("/api/execution/{execution_id}")
    async def get_execution_status(execution_id: str):
        if execution_service is None:
            _service_unavailable("ExecutionService")
        try:
            return execution_service.get_execution_status(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取执行状态失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/stop")
    async def stop_execution(execution_id: str):
        """停止正在运行的执行"""
        if execution_service is None:
            _service_unavailable("ExecutionService")
        try:
            return execution_service.stop_execution(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"停止执行失败: {str(e)}")

    @router.get("/api/execution/{execution_id}/stream")
    async def stream_execution(execution_id: str):
        if execution_service is None:
            _service_unavailable("ExecutionService")
        status_data = execution_service.get_execution_status(execution_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="执行记录不存在")

        return StreamingResponse(
            execution_service.stream_execution_logs(execution_id),
            media_type="text/event-stream"
        )

    return router
