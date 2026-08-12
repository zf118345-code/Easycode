# core/services/blueprint_service.py
import os
import json
import time
from fastapi import HTTPException
from core.security import atomic_write_json
from core.schemas import BlueprintSchema, TaskSchema, SaveTaskRequestSchema

BLUEPRINT_FILE = "project_blueprint.json"


class BlueprintService:

    @staticmethod
    def get_blueprint_path(project_path: str) -> str:
        return os.path.join(project_path, BLUEPRINT_FILE)

    @classmethod
    def load_blueprint(cls, project_path: str) -> dict:
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")
        bp_path = cls.get_blueprint_path(project_path)
        if os.path.exists(bp_path):
            with open(bp_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"project_name": os.path.basename(project_path), "tasks": [], "variables": {}}

    @classmethod
    def save_blueprint(cls, project_path: str, data: dict):
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")
        bp_path = cls.get_blueprint_path(project_path)
        atomic_write_json(bp_path, data)

    @classmethod
    def list_tasks(cls, project_path: str) -> dict:
        bp_data = cls.load_blueprint(project_path)
        task_list = [
            {
                "task_id": task.get("task_id"),
                "task_name": task.get("task_name"),
                "node_count": len(task.get("nodes", []))
            }
            for task in bp_data.get("tasks", [])
        ]
        order = [t["task_id"] for t in task_list]
        return {"tasks": task_list, "order": order}

    @classmethod
    def get_task(cls, task_id: str, project_path: str) -> dict:
        bp_data = cls.load_blueprint(project_path)
        if "tasks" in bp_data:
            for task in bp_data.get("tasks", []):
                if task.get("task_id") == task_id:
                    return task
            if bp_data["tasks"]:
                return bp_data["tasks"][0]
        return bp_data

    @classmethod
    def save_task(cls, task_id: str, request: SaveTaskRequestSchema) -> dict:
        bp_data = cls.load_blueprint(request.project_path)
        tasks = bp_data.setdefault("tasks", [])
        task_dict = request.task_data.model_dump()

        task_dict["task_id"] = task_id
        if "task_name" not in task_dict or not task_dict["task_name"]:
            task_dict["task_name"] = task_id

        found = False
        for i, t in enumerate(tasks):
            if t.get("task_id") == task_id:
                tasks[i] = task_dict
                found = True
                break
        if not found:
            tasks.append(task_dict)

        cls.save_blueprint(request.project_path, bp_data)
        return {"status": "success"}

    @classmethod
    def create_task(cls, request: SaveTaskRequestSchema) -> dict:
        bp_data = cls.load_blueprint(request.project_path)
        tasks = bp_data.setdefault("tasks", [])
        task_dict = request.task_data.model_dump()
        task_name = task_dict.get("task_name", "新任务组")

        if any(t.get("task_name") == task_name for t in tasks):
            raise HTTPException(status_code=400, detail="任务名称已存在")

        task_id = f"task_{int(time.time() * 1000)}"
        task_dict["task_id"] = task_id
        task_dict["task_name"] = task_name
        if "nodes" not in task_dict:
            task_dict["nodes"] = []

        tasks.append(task_dict)
        cls.save_blueprint(request.project_path, bp_data)
        return {"status": "success", "task_id": task_id}

    @classmethod
    def delete_task(cls, task_id: str, project_path: str) -> dict:
        bp_data = cls.load_blueprint(project_path)
        tasks = bp_data.get("tasks", [])

        new_tasks = [t for t in tasks if t.get("task_id") != task_id]
        if len(new_tasks) == len(tasks):
            raise HTTPException(status_code=404, detail="任务不存在")

        bp_data["tasks"] = new_tasks
        cls.save_blueprint(project_path, bp_data)
        return {"status": "success"}

    @classmethod
    def save_task_order(cls, project_path: str, order: list) -> dict:
        project_json_path = os.path.join(project_path, "project.json")
        if not os.path.exists(project_json_path):
            raise HTTPException(status_code=404, detail="项目不存在")

        with open(project_json_path, "r", encoding="utf-8") as f:
            project_data = json.load(f)
        project_data["task_order"] = order
        atomic_write_json(project_json_path, project_data)
        return {"status": "success"}