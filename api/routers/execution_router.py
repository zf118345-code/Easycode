import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
from typing import Optional

from core.schemas import RunRequestSchema

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f"服务不可用: {name} 模块未加载")


def create_execution_router(execution_service, debug_service=None):
    router = APIRouter(tags=["执行引擎"])

    @router.post("/api/run")
    async def run_task(request: RunRequestSchema, background_tasks: BackgroundTasks):
        """运行任务，支持通过 __debug.breakpoints 下发初始断点"""
        if execution_service is None:
            _service_unavailable("ExecutionService")
        bp_dict = request.blueprint_data if request.blueprint_data else None
        breakpoints = None
        if isinstance(bp_dict, dict) and "__debug" in bp_dict:
            debug_cfg = bp_dict.pop("__debug") or {}
            breakpoints = debug_cfg.get("breakpoints")
            if debug_service is not None and breakpoints:
                try:
                    debug_service.set_breakpoints(None, list(breakpoints))
                except Exception as e:
                    logger.warning(f"设置初始断点失败（忽略，继续执行）: {e}")
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

    # ========== 调试路由（DebugService） ==========

    @router.post("/api/execution/{execution_id}/pause")
    async def pause_execution(execution_id: str):
        """请求暂停当前执行（命中下个检查点）"""
        if debug_service is None:
            _service_unavailable("DebugService")
        try:
            return debug_service.pause_session(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"暂停失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"暂停失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/resume")
    async def resume_execution(execution_id: str):
        """恢复已暂停的执行"""
        if debug_service is None:
            _service_unavailable("DebugService")
        try:
            return debug_service.resume_session(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"恢复失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/step")
    async def step_execution(
        execution_id: str,
        body: dict = Body(default_factory=dict)
    ):
        """单步执行：step=over(单步跳过) / into(单步进入) / out(单步跳出)"""
        if debug_service is None:
            _service_unavailable("DebugService")
        step_type = body.get("step", "over")
        valid = {"over", "into", "out", "next"}
        if step_type not in valid:
            raise HTTPException(status_code=400, detail=f"step 必须为 {valid} 之一")
        try:
            return debug_service.step_session(execution_id, step_type)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"单步失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"单步失败: {str(e)}")

    @router.get("/api/execution/{execution_id}/debug")
    async def get_debug_state(execution_id: str):
        """获取调试会话状态：status/current_node_id/callstack 等"""
        if debug_service is None:
            # 未启用调试时，回退到执行基本状态
            if execution_service is None:
                _service_unavailable("ExecutionService")
            s = execution_service.get_execution_status(execution_id)
            status = (s or {}).get("status", "unknown")
            state_map = {"running": "running", "success": "success", "error": "error", "stopped": "stopped", "paused": "paused"}
            return {"status": state_map.get(status, status), "debug_enabled": False}
        try:
            return debug_service.get_session_state(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取调试状态失败: {str(e)}")

    @router.get("/api/execution/{execution_id}/variables")
    async def get_execution_variables(execution_id: str, level: Optional[int] = 0):
        """获取调用栈某一层的局部变量快照"""
        if debug_service is None:
            _service_unavailable("DebugService")
        try:
            variables = debug_service.inspect_variables(execution_id, level or 0)
            return {"variables": variables or [], "level": level or 0}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取变量失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/breakpoints")
    async def set_breakpoints(execution_id: str, body: dict = Body(default_factory=dict)):
        """批量设置断点（覆盖所有旧断点）"""
        if debug_service is None:
            _service_unavailable("DebugService")
        node_ids = list(body.get("breakpoints") or [])
        try:
            return debug_service.set_breakpoints(execution_id, node_ids)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"设置断点失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/breakpoints/add")
    async def add_breakpoint(execution_id: str, body: dict = Body(default_factory=dict)):
        node_id = body.get("node_id")
        if not node_id:
            raise HTTPException(status_code=400, detail="缺少 node_id")
        if debug_service is None:
            _service_unavailable("DebugService")
        try:
            debug_service.add_breakpoint(execution_id, node_id)
            return {"ok": True, "node_id": node_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"新增断点失败: {str(e)}")

    @router.post("/api/execution/{execution_id}/breakpoints/remove")
    async def remove_breakpoint(execution_id: str, body: dict = Body(default_factory=dict)):
        node_id = body.get("node_id")
        if not node_id:
            raise HTTPException(status_code=400, detail="缺少 node_id")
        if debug_service is None:
            _service_unavailable("DebugService")
        try:
            debug_service.remove_breakpoint(execution_id, node_id)
            return {"ok": True, "node_id": node_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除断点失败: {str(e)}")

    return router
