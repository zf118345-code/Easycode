# core/services/execution_service.py
# P0 修复：线程安全（加锁）、停止机制（持有 executor 引用）

import asyncio
import json
import os
import threading
import time
from collections import OrderedDict

import pyautogui
from fastapi import BackgroundTasks, HTTPException

from core.executor import GraphExecutor
from core.project_loader import load_project
from core.services.blueprint_service import BlueprintService
from core.services.debug_service import DebugService, DebugSession
from core.services.execution_db import ExecutionDB

CONTEXT_FILE = 'context.json'
MAX_LOG_ENTRIES = 100

# ⚡ #7 SQLite 持久化兜底：落盘失败不影响主流程（内存态仍是权威数据源）
def _db_safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('ExecutionDB 操作失败: %s', e)
        return None

# P0 修复：全局状态加锁
_status_lock = threading.Lock()
_logs_lock = threading.Lock()

execution_status = OrderedDict()
execution_logs = OrderedDict()

# P0 修复：持有 executor 实例引用，用于停止机制
_active_executors: dict = {}


def record_execution(execution_id, status_data, logs_data):
    with _status_lock:
        if len(execution_status) >= MAX_LOG_ENTRIES:
            execution_status.popitem(last=False)
    with _logs_lock:
        if len(execution_logs) >= MAX_LOG_ENTRIES:
            execution_logs.popitem(last=False)
    with _status_lock:
        execution_status[execution_id] = status_data
    with _logs_lock:
        execution_logs[execution_id] = logs_data


class ExecutionService:
    @staticmethod
    def run_task(
        project_path: str, task_id: str, start_node_id: str, blueprint_data: dict, background_tasks: BackgroundTasks
    ) -> dict:
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目不存在')

        if blueprint_data:
            BlueprintService.save_blueprint(project_path, blueprint_data)

        context_path = os.path.join(project_path, CONTEXT_FILE)
        saved_context = {}
        if os.path.exists(context_path):
            with open(context_path, encoding='utf-8') as f:
                saved_context = json.load(f)

        project = load_project(project_path)
        execution_id = f'{task_id}_{int(time.time() * 1000)}'
        record_execution(execution_id, {'status': 'running', 'message': '执行中...'}, [])
        # ⚡ #7 SQLite 持久化：执行记录落盘（失败不影响主流程）
        _db_safe(ExecutionDB.create_execution, execution_id, project_path, task_id, start_node_id)
        _db_safe(ExecutionDB.update_status, execution_id, 'running', '执行中...')

        # 调试能力：前端随 blueprint_data.__debug 下发（含 breakpoints；存在即启用暂停/单步/变量）
        debug_breakpoints = []
        debug_enabled = isinstance(blueprint_data, dict) and '__debug' in blueprint_data
        if debug_enabled:
            debug_breakpoints = (blueprint_data.get('__debug') or {}).get('breakpoints', []) or []

        def execute_background():
            original_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            executor = GraphExecutor(
                project,
                project_dir=project_path,
                text_log_enabled=True,
                image_log_enabled=True,
                initial_context=saved_context,
            )

            # 调试会话：session_id 与 execution_id 对齐，注入执行器（断点/暂停/单步/变量）
            debug_session = None
            if debug_enabled:
                debug_session = DebugSession(execution_id, executor, task_id, start_node_id)
                for bp in debug_breakpoints:
                    debug_session.add_breakpoint(bp)
                debug_session._is_running = True
                executor.debug_session = debug_session
                DebugService.register_session(debug_session)

            # P0 修复：注册 executor 实例，供 stop_execution 使用
            with _status_lock:
                _active_executors[execution_id] = executor

            try:
                with _logs_lock:
                    execution_logs[execution_id] = executor.logs
                executor.run(task_id, start_node_id)

                if executor.is_stopped:
                    execution_status[execution_id] = {'status': 'stopped', 'message': '用户主动停止'}
                    _db_safe(ExecutionDB.update_status, execution_id, 'stopped', '用户主动停止')
                else:
                    execution_status[execution_id] = {'status': 'success', 'message': '执行完成'}
                    _db_safe(ExecutionDB.update_status, execution_id, 'success', '执行完成')
            except Exception as e:
                execution_status[execution_id] = {'status': 'error', 'message': str(e)}
                _db_safe(ExecutionDB.update_status, execution_id, 'error', str(e))
            finally:
                with _logs_lock:
                    execution_logs[execution_id] = executor.logs
                # ⚡ #7 增量落盘日志 + 清理历史记录上限
                _db_safe(ExecutionDB.add_logs, execution_id, executor.logs)
                _db_safe(ExecutionDB.cleanup_old_executions)
                with _status_lock:
                    _active_executors.pop(execution_id, None)
                if debug_session is not None:
                    with DebugService._lock:
                        DebugService._sessions.pop(execution_id, None)
                pyautogui.FAILSAFE = original_failsafe

        background_tasks.add_task(execute_background)
        return {'execution_id': execution_id, 'status': 'started'}

    @staticmethod
    def get_execution_status(execution_id: str) -> dict:
        with _status_lock:
            status = execution_status.get(execution_id)
        if not status:
            raise HTTPException(status_code=404, detail='执行记录不存在')
        with _logs_lock:
            logs = execution_logs.get(execution_id, [])
        return {'status': status, 'logs': logs}

    @staticmethod
    def stop_execution(execution_id: str) -> dict:
        """P0 修复：实际停止正在运行的执行"""
        with _status_lock:
            executor = _active_executors.get(execution_id)

        if executor:
            executor.stop()
            # ⚡ 关键：若调试会话正阻塞在断点暂停（_resume_event.wait()），
            # 仅置停止标志无法唤醒执行线程——必须释放暂停阻塞，
            # 线程才能在 on_node_enter 返回后检查 is_stopped 并退出。
            with DebugService._lock:
                debug_session = DebugService._sessions.get(execution_id)
            if debug_session is not None:
                debug_session.resume()
            _db_safe(ExecutionDB.update_status, execution_id, 'stopped', '用户主动停止')
            return {'status': 'success', 'message': f'已向执行器 {execution_id} 下发停止信号'}
        else:
            # 如果执行已结束，直接标记状态
            with _status_lock:
                if execution_id in execution_status:
                    current = execution_status[execution_id]
                    if current.get('status') == 'running':
                        execution_status[execution_id] = {'status': 'stopped', 'message': '强制标记停止'}
                        _db_safe(ExecutionDB.update_status, execution_id, 'stopped', '强制标记停止')
                        return {'status': 'success', 'message': '执行已不在运行，标记为停止'}
            return {'status': 'warning', 'message': f'未找到活跃的执行器: {execution_id}'}

    @staticmethod
    async def stream_execution_logs(execution_id: str):
        """异步 SSE 日志流生成器（⚡ #5 同时推送调试状态：暂停/恢复/单步即时反映，前端不再 1s 轮询）"""
        last_sent_index = 0
        last_debug_state = None
        while True:
            with _status_lock:
                status = execution_status.get(execution_id, {'status': 'unknown'})
            with _logs_lock:
                logs = execution_logs.get(execution_id, [])
                logs_copy = list(logs)

            # ⚡ #5 调试状态轻量快照（is_paused / current_node_id / pause_reason）
            debug_state = None
            try:
                session = DebugService._sessions.get(execution_id)
                if session is not None:
                    with session._lock:
                        if session._is_paused or session._current_node_id:
                            debug_state = {
                                'state': 'paused' if session._is_paused else 'running',
                                'node_id': session._current_node_id,
                                'pause_reason': session._pause_reason,
                            }
            except Exception:
                pass

            # 推送未发送的新日志
            if len(logs_copy) > last_sent_index:
                new_logs = logs_copy[last_sent_index:]
                last_sent_index = len(logs_copy)
                payload = {'status': status, 'logs': new_logs}
                if debug_state:
                    payload['debug_state'] = debug_state
                yield f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'
            elif debug_state and debug_state != last_debug_state:
                # ⚡ 无新日志但调试状态变化（暂停/恢复/单步）→ 即时推送
                last_debug_state = debug_state
                yield f'data: {json.dumps({"status": status, "logs": [], "debug_state": debug_state}, ensure_ascii=False)}\n\n'
            elif debug_state:
                last_debug_state = debug_state

            # 如果任务已结束且日志发送完毕，安全退出流
            if status.get('status') in ['success', 'error', 'stopped'] and last_sent_index >= len(logs_copy):
                yield f'data: {json.dumps({"status": status, "logs": []}, ensure_ascii=False)}\n\n'
                break

            await asyncio.sleep(0.2)
