
# core/services/blueprint_service.py

# 修复：移除 core.security 依赖（该模块不存在导致服务端 500）

# 修复：内联实现原子写入（tempfile + os.replace）

# 修复：_sanitize_for_json 保留 None 值（避免丢失合法的 null 字段）

# 修复：load/save 全面错误处理，支持 edges 和 topology 字段持久化

import os
import json
import time
import tempfile
import logging
from fastapi import HTTPException
from core.schemas import SaveTaskRequestSchema

logger = logging.getLogger(__name__)

BLUEPRINT_FILE = "project_blueprint.json"

def _atomic_write_json(file_path: str, data: dict):
    """
    原子写入 JSON 文件
    先写入临时文件，再 rename 替换原文件，避免写入中途崩溃导致文件损坏
    """
    dir_path = os.path.dirname(os.path.abspath(file_path))
    fd, tmp_path = tempfile.mkstemp(
        suffix='.tmp',
        prefix='blueprint_',
        dir=dir_path
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows 下 os.replace 会原子替换；Linux 下 rename 也是原子的
        os.replace(tmp_path, file_path)
    except Exception:
        # 清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        raise

class BlueprintService:

    @staticmethod
    def get_blueprint_path(project_path: str) -> str:
        return os.path.join(project_path, BLUEPRINT_FILE)

    @classmethod
    def load_blueprint(cls, project_path: str) -> dict:
        """
        加载蓝图 JSON
        修复：全面 try/except，文件损坏时返回默认结构而非 500
        """
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f"项目路径不存在: {project_path}")

        bp_path = cls.get_blueprint_path(project_path)

        if not os.path.exists(bp_path):
            # 蓝图不存在，返回默认结构
            return {
                "project_name": os.path.basename(project_path),
                "tasks": [],
                "variables": {},
                "edges": [],
                "topology": {"nodes": [], "edges": []},
                "ui_state": {}
            }

        try:
            with open(bp_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"蓝图 JSON 解析失败 [{bp_path}]: {e}")
            # 返回默认结构，不崩溃前端
            return {
                "project_name": os.path.basename(project_path),
                "tasks": [],
                "variables": {},
                "edges": [],
                "topology": {"nodes": [], "edges": []},
                "ui_state": {},
                "_error": f"蓝图文件解析失败: {e}"
            }
        except Exception as e:
            logger.error(f"蓝图加载失败 [{bp_path}]: {e}")
            raise HTTPException(status_code=500, detail=f"蓝图加载失败: {str(e)}")

        # 兜底：确保关键字段存在
        if not isinstance(data, dict):
            logger.warning(f"蓝图文件内容非 dict [{bp_path}], 返回默认结构")
            return {
                "project_name": os.path.basename(project_path),
                "tasks": [],
                "variables": {},
                "edges": [],
                "topology": {"nodes": [], "edges": []},
                "ui_state": {}
            }

        if "tasks" not in data or not isinstance(data["tasks"], list):
            data["tasks"] = []
        if "variables" not in data or not isinstance(data["variables"], dict):
            data["variables"] = {}
        if "edges" not in data or not isinstance(data["edges"], list):
            data["edges"] = []
        if "topology" not in data or not isinstance(data["topology"], dict):
            data["topology"] = {"nodes": [], "edges": []}
        else:
            # 确保 topology 内部结构正确
            topo = data["topology"]
            if not isinstance(topo.get("nodes"), list):
                topo["nodes"] = []
            if not isinstance(topo.get("edges"), list):
                topo["edges"] = []
        if "ui_state" not in data or not isinstance(data["ui_state"], dict):
            data["ui_state"] = {}

        return data

    @classmethod
    def save_blueprint(cls, project_path: str, data: dict):
        """
        保存蓝图 JSON
        修复：全面 try/except，序列化前清理不可 JSON 序列化的字段
        修复：确保 edges 和 topology 字段被持久化
        """
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f"项目路径不存在: {project_path}")

        bp_path = cls.get_blueprint_path(project_path)

        # 确保 data 是 dict
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="蓝图数据必须是字典类型")

        # 清理可能存在的不可序列化字段（保留 None 值）
        clean_data = cls._sanitize_for_json(data)

        # 确保关键字段存在
        if "tasks" not in clean_data:
            clean_data["tasks"] = []
        if "variables" not in clean_data:
            clean_data["variables"] = {}
        if "edges" not in clean_data:
            clean_data["edges"] = []
        if "topology" not in clean_data:
            clean_data["topology"] = {"nodes": [], "edges": []}

        try:
            _atomic_write_json(bp_path, clean_data)
        except TypeError as e:
            # 序列化类型错误：尝试用 default=str 兜底
            logger.warning(f"蓝图序列化遇到类型问题，使用 default=str 兜底: {e}")
            try:
                with open(bp_path, "w", encoding="utf-8") as f:
                    json.dump(clean_data, f, ensure_ascii=False, indent=2, default=str)
            except Exception as e2:
                logger.error(f"蓝图保存失败(兜底) [{bp_path}]: {e2}")
                raise HTTPException(status_code=500, detail=f"蓝图保存失败: {str(e2)}")
        except Exception as e:
            logger.error(f"蓝图保存失败 [{bp_path}]: {e}")
            raise HTTPException(status_code=500, detail=f"蓝图保存失败: {str(e)}")

    @staticmethod
    def _sanitize_for_json(obj):
        """
        递归清理不可 JSON 序列化的字段
        防止 numpy int64/float64、datetime 等类型导致 json.dump 失败
        修复：保留 None 值（之前 v is not None 过滤会丢失合法的 null 字段）
        修复：只过滤以 _ 开头的内部字段
        """
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.startswith("_"):
                    continue
                result[k] = BlueprintService._sanitize_for_json(v)
            return result
        elif isinstance(obj, list):
            return [BlueprintService._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            # 不可序列化的对象转为字符串
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

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
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        return bp_data

    @classmethod
    def save_task(cls, task_id: str, request: SaveTaskRequestSchema) -> dict:
        bp_data = cls.load_blueprint(request.project_path)
        tasks = bp_data.setdefault("tasks", [])
        task_dict = request.task_data.model_dump() if hasattr(request.task_data, 'model_dump') else dict(request.task_data)

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
        task_dict = request.task_data.model_dump() if hasattr(request.task_data, 'model_dump') else dict(request.task_data)
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
        bp_data = cls.load_blueprint(project_path)
        bp_data["task_order"] = order
        cls.save_blueprint(project_path, bp_data)
        return {"status": "success"}
