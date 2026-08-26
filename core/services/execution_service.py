# core/services/execution_service.py
# P0 修复：线程安全（加锁）、停止机制（持有 executor 引用）

import asyncio
import json
import os
import threading
import time
import tempfile
import uuid
from collections import OrderedDict

from fastapi import BackgroundTasks, HTTPException

from core.executor import GraphExecutor
from core.project_loader import load_project, project_from_dict
from core.security import atomic_write_json
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
_target_owners: dict[str, str] = {}


def record_execution(execution_id, status_data, logs_data):
    with _status_lock:
        execution_status[execution_id] = status_data
        while len(execution_status) > MAX_LOG_ENTRIES:
            execution_status.popitem(last=False)
    with _logs_lock:
        execution_logs[execution_id] = logs_data
        while len(execution_logs) > MAX_LOG_ENTRIES:
            execution_logs.popitem(last=False)


class ExecutionService:
    @staticmethod
    def has_active_execution() -> bool:
        """Running and debug-paused executors both keep their target lease."""
        with _status_lock:
            return bool(_active_executors)

    @staticmethod
    def run_task(
        project_path: str,
        task_id: str,
        start_node_id: str,
        blueprint_data: dict,
        background_tasks: BackgroundTasks,
        *,
        persist_blueprint: bool = True,
        runtime_dir: str | None = None,
        checkpoint_path: str | None = None,
        instance_id: str | None = None,
        isolate_process: bool = False,
        checkpoint_storage_root: str | None = None,
        redact_values: list | None = None,
    ) -> dict:
        try:
            from core.services import capture_mode
            from core.services.capture_session_service import capture_session_service

            if capture_mode.get_state().get('active') or capture_session_service.is_capture_active():
                raise HTTPException(status_code=409, detail='请先退出捕获模式，再运行任务')
        except HTTPException:
            raise
        except Exception:
            pass
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目不存在')

        if blueprint_data and persist_blueprint:
            BlueprintService.save_blueprint(project_path, blueprint_data)

        saved_context = {}
        if persist_blueprint:
            from core.services.workspace_service import WorkspaceService

            saved_context = WorkspaceService.load_runtime_context(project_path)

        # ⚡ Player 端上下文链路：密包内置 context + 客户表单 ctx 配置（_player_context）优先，
        # 回退磁盘 context.json（IDE 开发模式）。修复打包客户端窗口预热缺失问题。
        if isinstance(blueprint_data, dict) and blueprint_data.get('_player_context'):
            saved_context = {**saved_context, **blueprint_data['_player_context']}

        project = load_project(project_path) if persist_blueprint else project_from_dict(blueprint_data, 'player-runtime')
        execution_id = f'{task_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}'
        record_execution(
            execution_id,
            {'status': 'running', 'message': '执行中...', 'instance_id': instance_id},
            [],
        )
        # ⚡ #7 SQLite 持久化：执行记录落盘（失败不影响主流程）
        _db_safe(ExecutionDB.create_execution, execution_id, project_path, task_id, start_node_id)
        _db_safe(ExecutionDB.update_status, execution_id, 'running', '执行中...')

        # 调试能力：前端随 blueprint_data.__debug 下发（含 breakpoints；存在即启用暂停/单步/变量）
        debug_breakpoints = []
        debug_enabled = isinstance(blueprint_data, dict) and '__debug' in blueprint_data
        if debug_enabled:
            debug_breakpoints = (blueprint_data.get('__debug') or {}).get('breakpoints', []) or []

        if isolate_process and not debug_enabled:
            def execute_isolated_background():
                from core.services.execution_worker import next_worker_event, spawn_execution_worker

                proxy = None
                target_key = None
                final_event = None
                try:
                    proxy = spawn_execution_worker({
                        'execution_id': execution_id,
                        'instance_id': instance_id,
                        'project_path': project_path,
                        'task_id': task_id,
                        'start_node_id': start_node_id,
                        'blueprint': blueprint_data,
                        'context': saved_context,
                        'persist_blueprint': persist_blueprint,
                        'runtime_dir': runtime_dir,
                        'checkpoint_path': checkpoint_path,
                        'checkpoint_storage_root': checkpoint_storage_root,
                        'redact_values': list(redact_values or []),
                    })
                    with _status_lock:
                        _active_executors[execution_id] = proxy
                    ready_deadline = time.monotonic() + 20.0
                    while True:
                        event = next_worker_event(proxy, 0.2)
                        if event:
                            event_type = event.get('type')
                            if event_type == 'ready':
                                target_key = event.get('target_key')
                                with _status_lock:
                                    owner = _target_owners.get(target_key) if target_key else None
                                    if owner and owner != execution_id:
                                        raise RuntimeError(f'运行目标 [{target_key}] 已被执行实例 {owner} 占用')
                                    if target_key:
                                        _target_owners[target_key] = execution_id
                                proxy.target_key = target_key
                                proxy.start_event.set()
                            elif event_type == 'log':
                                with _logs_lock:
                                    logs = execution_logs.setdefault(execution_id, [])
                                    logs.append(event.get('log') or {})
                                    if len(logs) > 5000:
                                        del logs[:-5000]
                            elif event_type == 'final':
                                final_event = event
                                proxy.last_metrics = event.get('runtime_metrics') or {}
                                break
                        if not proxy.process.is_alive():
                            # Drain a final message that may have raced process exit.
                            trailing = next_worker_event(proxy, 0.2)
                            if trailing and trailing.get('type') == 'final':
                                final_event = trailing
                                proxy.last_metrics = trailing.get('runtime_metrics') or {}
                            break
                        if not proxy.start_event.is_set() and time.monotonic() >= ready_deadline:
                            raise RuntimeError('独立 Worker 初始化超时')
                    if final_event is None:
                        raise RuntimeError(f'独立 Worker 异常退出（代码 {proxy.process.exitcode}）')
                    status_value = str(final_event.get('status') or 'error')
                    status_payload = {
                        'status': status_value,
                        'message': final_event.get('message') or ('执行完成' if status_value == 'success' else 'Worker 运行失败'),
                        'instance_id': instance_id,
                        'worker_pid': proxy.process.pid,
                        'failure_screenshot': final_event.get('failure_screenshot'),
                        'latest_frame': final_event.get('latest_frame'),
                        'checkpoint_path': checkpoint_path,
                        'runtime_metrics': final_event.get('runtime_metrics') or {},
                    }
                    with _status_lock:
                        execution_status[execution_id] = status_payload
                    _db_safe(ExecutionDB.update_status, execution_id, status_value, status_payload['message'])
                except Exception as exc:
                    if proxy is not None:
                        proxy.stop()
                    with _status_lock:
                        execution_status[execution_id] = {
                            'status': 'error', 'message': str(exc), 'instance_id': instance_id,
                            'worker_pid': proxy.process.pid if proxy is not None else None,
                            'checkpoint_path': checkpoint_path,
                        }
                    with _logs_lock:
                        execution_logs.setdefault(execution_id, []).append({
                            'time': time.strftime('%H:%M:%S'), 'level': 'error',
                            'category': 'execution',
                            'message': f'独立 Worker 运行失败: {exc}',
                        })
                    _db_safe(ExecutionDB.update_status, execution_id, 'error', str(exc))
                finally:
                    if proxy is not None:
                        if proxy.process.is_alive():
                            proxy.stop()
                        proxy.process.join(timeout=3.0)
                        if proxy.process.is_alive():
                            proxy.process.terminate()
                            proxy.process.join(timeout=1.0)
                    with _status_lock:
                        _active_executors.pop(execution_id, None)
                        if target_key and _target_owners.get(target_key) == execution_id:
                            _target_owners.pop(target_key, None)
                    with _logs_lock:
                        final_logs = list(execution_logs.get(execution_id, []))
                    _db_safe(ExecutionDB.add_logs, execution_id, final_logs)
                    _db_safe(ExecutionDB.cleanup_old_executions)

            background_tasks.add_task(execute_isolated_background)
            return {'execution_id': execution_id, 'status': 'started', 'instance_id': instance_id, 'isolation': 'process'}

        def execute_background():
            executor = None
            debug_session = None
            target_key = None

            try:
                # 目标初始化错误必须进入执行状态，而不能让后台任务异常后永远停在 running。
                executor = GraphExecutor(
                    project,
                    project_dir=project_path,
                    text_log_enabled=True,
                    image_log_enabled=True,
                    initial_context=saved_context,
                )
                from core.services.platform_runtime_service import platform_runtime_service

                if persist_blueprint:
                    executor._platform_store = platform_runtime_service.register_project(project_path)
                else:
                    player_root = os.path.dirname(runtime_dir) if runtime_dir else os.path.dirname(project_path)
                    executor._platform_store = platform_runtime_service.register_player(player_root)

                uses_screen_target = any(
                    executor._node_requires_popup_check(node) or node.node_type in {'set_window', 'script_call'}
                    for task in executor.tasks.values()
                    for node in task.nodes
                )
                if uses_screen_target:
                    if executor.is_emulator:
                        target_key = f'adb:{executor.device_id}'
                    elif executor.window_hwnd:
                        target_key = f'hwnd:{int(executor.window_hwnd)}'
                    else:
                        target_key = 'desktop'

                # 同一目标只能由一个执行实例占用；防止多任务互相点击/覆盖截图状态。
                with _status_lock:
                    owner = _target_owners.get(target_key) if target_key else None
                    if owner and owner != execution_id:
                        raise RuntimeError(f'运行目标 [{target_key}] 已被执行实例 {owner} 占用')
                    if target_key:
                        _target_owners[target_key] = execution_id
                    _active_executors[execution_id] = executor

                if checkpoint_path:
                    checkpoint_dir = os.path.dirname(os.path.abspath(checkpoint_path))
                    os.makedirs(checkpoint_dir, exist_ok=True)

                    def save_checkpoint(active_task_id, active_node_id, variables):
                        # 子流程内部缺少完整调用者栈时不能安全恢复；保留最近的根流程恢复点。
                        if getattr(executor, '_active_frame', None) and executor._active_frame.get('call_depth', 0) > 0:
                            return
                        payload = {
                            'execution_id': execution_id,
                            'instance_id': instance_id,
                            'task_id': active_task_id,
                            'node_id': active_node_id,
                            'variables': variables,
                            'updated_at': time.time(),
                        }
                        if checkpoint_storage_root:
                            from core.services.player_secret_service import PlayerSecretService

                            payload = PlayerSecretService.protect_document(payload, checkpoint_storage_root)
                        atomic_write_json(
                            checkpoint_path,
                            payload,
                            clean_transient=False,
                            default=str,
                        )

                    executor.checkpoint_callback = save_checkpoint

                if isinstance(blueprint_data, dict) and blueprint_data.get('_memory_templates'):
                    executor._memory_templates = blueprint_data['_memory_templates']

                if debug_enabled:
                    debug_session = DebugSession(execution_id, executor, task_id, start_node_id)
                    for bp in debug_breakpoints:
                        debug_session.add_breakpoint(bp)
                    debug_session._is_running = True
                    executor.debug_session = debug_session
                    DebugService.register_session(debug_session)

                with _logs_lock:
                    execution_logs[execution_id] = executor.logs
                executor.run(task_id, start_node_id)

                if executor.is_stopped:
                    with _status_lock:
                        execution_status[execution_id] = {'status': 'stopped', 'message': '用户主动停止', 'instance_id': instance_id}
                    _db_safe(ExecutionDB.update_status, execution_id, 'stopped', '用户主动停止')
                else:
                    with _status_lock:
                        execution_status[execution_id] = {'status': 'success', 'message': '执行完成', 'instance_id': instance_id}
                    _db_safe(ExecutionDB.update_status, execution_id, 'success', '执行完成')
            except Exception as e:
                screenshot_path = None
                if executor is not None:
                    try:
                        from core.services.runtime_target import capture_workspace

                        target_dir = runtime_dir or os.path.join(tempfile.gettempdir(), 'EasycodePlayer', 'diagnostics')
                        os.makedirs(target_dir, exist_ok=True)
                        screenshot_path = os.path.join(target_dir, f'failure-{execution_id}.png')
                        capture_workspace(executor).save(screenshot_path)
                    except Exception:
                        screenshot_path = None
                with _status_lock:
                    execution_status[execution_id] = {
                        'status': 'error',
                        'message': str(e),
                        'instance_id': instance_id,
                        'failure_screenshot': screenshot_path,
                        'checkpoint_path': checkpoint_path,
                    }
                if executor is None:
                    with _logs_lock:
                        execution_logs[execution_id] = [
                            {
                                'time': time.strftime('%H:%M:%S'),
                                'message': f' 运行目标初始化失败: {e}',
                                'level': 'error',
                                'category': 'execution',
                            }
                        ]
                _db_safe(ExecutionDB.update_status, execution_id, 'error', str(e))
            finally:
                final_logs = executor.logs if executor is not None else execution_logs.get(execution_id, [])
                with _logs_lock:
                    execution_logs[execution_id] = final_logs
                _db_safe(ExecutionDB.add_logs, execution_id, final_logs)
                _db_safe(ExecutionDB.cleanup_old_executions)
                with _status_lock:
                    _active_executors.pop(execution_id, None)
                    if target_key and _target_owners.get(target_key) == execution_id:
                        _target_owners.pop(target_key, None)
                if debug_session is not None:
                    with DebugService._lock:
                        DebugService._sessions.pop(execution_id, None)

        background_tasks.add_task(execute_background)
        return {'execution_id': execution_id, 'status': 'started', 'instance_id': instance_id}

    @staticmethod
    def get_execution_status(execution_id: str) -> dict:
        with _status_lock:
            status = execution_status.get(execution_id)
            executor = _active_executors.get(execution_id)
        if not status:
            raise HTTPException(status_code=404, detail='执行记录不存在')
        status = dict(status)
        with _logs_lock:
            logs = list(execution_logs.get(execution_id, []))
        runtime_metrics = {}
        stream = getattr(executor, '_visual_frame_stream', None) if executor is not None else None
        if stream is not None and hasattr(stream, 'metrics'):
            try:
                runtime_metrics['frame_stream'] = stream.metrics()
            except Exception:
                pass
        capture_info = getattr(executor, '_last_capture_info', None) if executor is not None else None
        if isinstance(capture_info, dict):
            runtime_metrics['capture'] = dict(capture_info)
        input_profile = getattr(executor, '_input_capability_profile', None) if executor is not None else None
        if isinstance(input_profile, dict):
            runtime_metrics['input_capabilities'] = dict(input_profile)
        if executor is not None and hasattr(executor, 'metrics'):
            try:
                runtime_metrics['worker'] = executor.metrics()
            except Exception:
                pass
        if isinstance(status.get('runtime_metrics'), dict):
            runtime_metrics.update(status.get('runtime_metrics') or {})
        return {'status': status, 'logs': logs, 'runtime_metrics': runtime_metrics}

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
                status = dict(execution_status.get(execution_id, {'status': 'unknown'}))
            with _logs_lock:
                logs = execution_logs.get(execution_id, [])
                logs_copy = list(logs)

            # ⚡ #5 调试状态轻量快照（is_paused / current_node_id / pause_reason）
            debug_state = None
            try:
                with DebugService._lock:
                    session = DebugService._sessions.get(execution_id)
                if session is not None:
                    with session._lock:
                        if session._is_paused or session._current_node_id:
                            debug_state = {
                                'state': 'paused' if session._is_paused else 'running',
                                'previous_node_id': session._previous_node_id,
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
