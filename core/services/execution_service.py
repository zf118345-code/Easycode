# core/services/execution_service.py
import os
import json
import time
import asyncio
import pyautogui
from collections import OrderedDict
from fastapi import HTTPException, BackgroundTasks
from core.executor import GraphExecutor
from core.project_loader import load_project
from core.services.blueprint_service import BlueprintService

CONTEXT_FILE = "context.json"
MAX_LOG_ENTRIES = 100

execution_status = OrderedDict()
execution_logs = OrderedDict()


def record_execution(execution_id, status_data, logs_data):
    if len(execution_status) >= MAX_LOG_ENTRIES:
        execution_status.popitem(last=False)
        execution_logs.popitem(last=False)
    execution_status[execution_id] = status_data
    execution_logs[execution_id] = logs_data


class ExecutionService:

    @staticmethod
    def run_task(project_path: str, task_id: str, start_node_id: str, blueprint_data: dict, background_tasks: BackgroundTasks) -> dict:
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
            try:
                execution_logs[execution_id] = executor.logs
                executor.run(task_id, start_node_id)
                execution_status[execution_id] = {"status": "success", "message": "执行完成"}
            except Exception as e:
                execution_status[execution_id] = {"status": "error", "message": str(e)}
            finally:
                execution_logs[execution_id] = executor.logs
                pyautogui.FAILSAFE = original_failsafe

        background_tasks.add_task(execute_background)
        return {"execution_id": execution_id, "status": "started"}

    @staticmethod
    def get_execution_status(execution_id: str) -> dict:
        status = execution_status.get(execution_id)
        if not status:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        logs = execution_logs.get(execution_id, [])
        return {"status": status, "logs": logs}

    @staticmethod
    async def stream_execution_logs(execution_id: str):
        """
        ⚡ 异步 SSE 日志流生成器
        """
        last_sent_index = 0
        while True:
            status = execution_status.get(execution_id, {"status": "unknown"})
            logs = execution_logs.get(execution_id, [])

            # 推送未发送的新日志
            if len(logs) > last_sent_index:
                new_logs = logs[last_sent_index:]
                last_sent_index = len(logs)
                payload = {
                    "status": status,
                    "logs": new_logs
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 如果任务已结束且日志发送完毕，安全退出流
            if status.get("status") in ["success", "error"] and last_sent_index >= len(logs):
                # 发送最终状态包
                yield f"data: {json.dumps({'status': status, 'logs': []}, ensure_ascii=False)}\n\n"
                break

            await asyncio.sleep(0.2)