# core/services/execution_service.py
# P0 修复：线程安全（加锁）、停止机制（持有 executor 引用）

import os
import json
import time
import asyncio
import threading
import pyautogui
from collections import OrderedDict
from fastapi import HTTPException, BackgroundTasks
from core.executor import GraphExecutor
from core.project_loader import load_project
from core.services.blueprint_service import BlueprintService

CONTEXT_FILE = "context.json"
MAX_LOG_ENTRIES = 100

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
    def run_task(project_path: str, task_id: str, start_node_id: str,
                 blueprint_data: dict, background_tasks: BackgroundTasks) -> dict:
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目不存在")

        if blueprint_data:
            BlueprintService.save_blueprint(project_path, blueprint_data)

        context_path = os.path.join(project_path, CONTEXT_FILE)
        saved_context = {}
        if os.path.exists(context_path):
            with open(context_path, "r", encoding="utf-8") as f:
                saved_context = json.load(f)

        project = load_project(project_path)
        execution_id = f"{task_id}_{int(time.time() * 1000)}"
        record_execution(execution_id, {"status": "running", "message": "执行中..."}, [])

        def execute_background():
            original_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            executor = GraphExecutor(
                project,
                project_dir=project_path,
                text_log_enabled=True,
                image_log_enabled=True,
                initial_context=saved_context
            )

            # P0 修复：注册 executor 实例，供 stop_execution 使用
            with _status_lock:
                _active_executors[execution_id] = executor

            try:
                with _logs_lock:
                    execution_logs[execution_id] = executor.logs
                executor.run(task_id, start_node_id)

                if executor.is_stopped:
                    execution_status[execution_id] = {"status": "stopped", "message": "用户主动停止"}
                else:
                    execution_status[execution_id] = {"status": "success", "message": "执行完成"}
            except Exception as e:
                execution_status[execution_id] = {"status": "error", "message": str(e)}
            finally:
                with _logs_lock:
                    execution_logs[execution_id] = executor.logs
                with _status_lock:
                    _active_executors.pop(execution_id, None)
                pyautogui.FAILSAFE = original_failsafe

        background_tasks.add_task(execute_background)
        return {"execution_id": execution_id, "status": "started"}

    @staticmethod
    def get_execution_status(execution_id: str) -> dict:
        with _status_lock:
            status = execution_status.get(execution_id)
        if not status:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        with _logs_lock:
            logs = execution_logs.get(execution_id, [])
        return {"status": status, "logs": logs}

    @staticmethod
    def stop_execution(execution_id: str) -> dict:
        """P0 修复：实际停止正在运行的执行"""
        with _status_lock:
            executor = _active_executors.get(execution_id)

        if executor:
            executor.stop()
            return {"status": "success", "message": f"已向执行器 {execution_id} 下发停止信号"}
        else:
            # 如果执行已结束，直接标记状态
            with _status_lock:
                if execution_id in execution_status:
                    current = execution_status[execution_id]
                    if current.get("status") == "running":
                        execution_status[execution_id] = {"status": "stopped", "message": "强制标记停止"}
                        return {"status": "success", "message": "执行已不在运行，标记为停止"}
            return {"status": "warning", "message": f"未找到活跃的执行器: {execution_id}"}

    @staticmethod
    async def stream_execution_logs(execution_id: str):
        """异步 SSE 日志流生成器"""
        last_sent_index = 0
        while True:
            with _status_lock:
                status = execution_status.get(execution_id, {"status": "unknown"})
            with _logs_lock:
                logs = execution_logs.get(execution_id, [])
                logs_copy = list(logs)

            # 推送未发送的新日志
            if len(logs_copy) > last_sent_index:
                new_logs = logs_copy[last_sent_index:]
                last_sent_index = len(logs_copy)
                payload = {
                    "status": status,
                    "logs": new_logs
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 如果任务已结束且日志发送完毕，安全退出流
            if status.get("status") in ["success", "error", "stopped"] and last_sent_index >= len(logs_copy):
                yield f"data: {json.dumps({'status': status, 'logs': []}, ensure_ascii=False)}\n\n"
                break

            await asyncio.sleep(0.2)
