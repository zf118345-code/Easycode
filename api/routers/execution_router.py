from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.contracts.operations import (
    ExecutionBreakpointRequest,
    ExecutionBreakpointsRequest,
    ExecutionRunRequest,
    ExecutionStepRequest,
)
from api.error_handling import internal_http_error
from api.idempotency import execute_idempotent
from api.workspace_context import assert_matching_legacy_path


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_execution_router(execution_service, debug_service):
    router = APIRouter(tags=["执行引擎"])

    @router.post('/api/run')
    async def run_task(
        payload: ExecutionRunRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        """运行任务，支持通过 __debug.breakpoints 下发初始断点"""
        if execution_service is None:
            _service_unavailable('ExecutionService')
        bp_dict = payload.blueprint_data if payload.blueprint_data else None
        try:
            project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
            async def produce():
                return execution_service.run_task(
                    project_path, payload.task_id, payload.start_node_id, bp_dict, background_tasks
                )

            return await execute_idempotent(
                idempotency_key,
                'legacy.execution.run',
                payload.model_dump(mode='json'),
                produce,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('启动任务失败', e) from e

    @router.get('/api/execution/{execution_id}')
    async def get_execution_status(execution_id: str):
        if execution_service is None:
            _service_unavailable('ExecutionService')
        try:
            return execution_service.get_execution_status(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('获取执行状态失败', e) from e

    @router.post('/api/execution/{execution_id}/stop')
    async def stop_execution(execution_id: str):
        """停止正在运行的执行"""
        if execution_service is None:
            _service_unavailable('ExecutionService')
        try:
            return execution_service.stop_execution(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('停止执行失败', e) from e

    @router.get('/api/execution/{execution_id}/stream')
    async def stream_execution(execution_id: str):
        if execution_service is None:
            _service_unavailable('ExecutionService')
        status_data = execution_service.get_execution_status(execution_id)
        if not status_data:
            raise HTTPException(status_code=404, detail='执行记录不存在')

        return StreamingResponse(execution_service.stream_execution_logs(execution_id), media_type='text/event-stream')

    # ========== 调试路由（DebugService） ==========

    @router.post('/api/execution/{execution_id}/pause')
    async def pause_execution(execution_id: str):
        """请求暂停当前执行（命中下个检查点）"""
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            return debug_service.pause_session(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('暂停失败', e) from e

    @router.post('/api/execution/{execution_id}/resume')
    async def resume_execution(execution_id: str):
        """恢复已暂停的执行"""
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            return debug_service.resume_session(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('恢复失败', e) from e

    @router.post('/api/execution/{execution_id}/step')
    async def step_execution(
        execution_id: str,
        payload: ExecutionStepRequest = Body(default_factory=ExecutionStepRequest),
    ):
        """单步执行：step=over(单步跳过) / into(单步进入) / out(单步跳出)"""
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            return debug_service.step_session(execution_id, payload.step)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('单步失败', e) from e

    @router.get('/api/execution/{execution_id}/debug')
    async def get_debug_state(execution_id: str):
        """获取调试会话状态：status/current_node_id/callstack 等"""
        if debug_service is None:
            # 未启用调试时，回退到执行基本状态
            if execution_service is None:
                _service_unavailable('ExecutionService')
            s = execution_service.get_execution_status(execution_id)
            status = (s or {}).get('status', 'unknown')
            state_map = {
                'running': 'running',
                'success': 'success',
                'error': 'error',
                'stopped': 'stopped',
                'paused': 'paused',
            }
            return {'status': state_map.get(status, status), 'debug_enabled': False}
        try:
            return debug_service.get_session_state(execution_id)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('获取调试状态失败', e) from e

    @router.get('/api/execution/{execution_id}/variables')
    async def get_execution_variables(execution_id: str, level: int | None = 0):
        """获取调用栈某一层的局部变量快照"""
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            variables = debug_service.inspect_variables(execution_id, level or 0)
            return {'variables': variables or [], 'level': level or 0}
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('获取变量失败', e) from e

    @router.post('/api/execution/{execution_id}/breakpoints')
    async def set_breakpoints(
        execution_id: str,
        payload: ExecutionBreakpointsRequest = Body(default_factory=ExecutionBreakpointsRequest),
    ):
        """批量设置断点（覆盖所有旧断点）"""
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            return debug_service.set_breakpoints(execution_id, payload.breakpoints)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('设置断点失败', e) from e

    @router.post('/api/execution/{execution_id}/breakpoints/add')
    async def add_breakpoint(execution_id: str, payload: ExecutionBreakpointRequest):
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            debug_service.add_breakpoint(execution_id, payload.node_id)
            return {'ok': True, 'node_id': payload.node_id}
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('新增断点失败', e) from e

    @router.post('/api/execution/{execution_id}/breakpoints/remove')
    async def remove_breakpoint(execution_id: str, payload: ExecutionBreakpointRequest):
        if debug_service is None:
            _service_unavailable('DebugService')
        try:
            debug_service.remove_breakpoint(execution_id, payload.node_id)
            return {'ok': True, 'node_id': payload.node_id}
        except HTTPException:
            raise
        except Exception as e:
            raise internal_http_error('删除断点失败', e) from e

    return router
