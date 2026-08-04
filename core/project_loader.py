# core/project_loader.py
import os
import json
from core.models import Project, Task, Node, Jump
from core.utils import load_json


def load_project(project_dir):
    """
    强制优先读取 project_blueprint.json 或 project.json 大文件蓝图
    """
    try:
        # 优先找蓝图大文件或标准 project.json
        for fname in ["project_blueprint.json", "project.json"]:
            blueprint_path = os.path.join(project_dir, fname)
            if os.path.exists(blueprint_path):
                blueprint_data = load_json(blueprint_path)

                project = Project(
                    project_name=blueprint_data.get("project_name", os.path.basename(project_dir)),
                    variables=blueprint_data.get("variables", {}),
                )

                # 兼容处理：如果里面有 tasks 数组
                tasks_data = blueprint_data.get("tasks", [])
                if not tasks_data and "nodes" in blueprint_data:
                    # 如果整个文件本身就是一个大 Task
                    tasks_data = [{
                        "task_id": "task_main",
                        "task_name": blueprint_data.get("project_name", "主任务组"),
                        "loop_count": 1,
                        "loop_interval": 0,
                        "nodes": blueprint_data.get("nodes", [])
                    }]

                for task_data in tasks_data:
                    nodes = []
                    for node_data in task_data.get("nodes", []):
                        try:
                            on_success = node_data.get("on_success", {})
                            on_failure = node_data.get("on_failure", {})

                            node = Node(
                                node_id=node_data["node_id"],
                                node_name=node_data.get("node_name", node_data["node_id"]),
                                node_type=node_data["node_type"],
                                params=node_data.get("params", {}),
                                delay_before=node_data.get("delay_before", 0),
                                loop_count=node_data.get("loop_count", 1),
                                enabled=node_data.get("enabled", True),
                                on_success=Jump(**on_success) if isinstance(on_success, dict) else Jump(),
                                on_failure=Jump(**on_failure) if isinstance(on_failure, dict) else Jump(),
                                position=node_data.get("position")
                            )
                            nodes.append(node)
                        except Exception as e:
                            print(f"解析节点出错: {e}")
                            continue

                    task = Task(
                        task_id=task_data.get("task_id", "task_main"),
                        task_name=task_data.get("task_name", "主任务组"),
                        loop_count=task_data.get("loop_count", 1),
                        loop_interval=task_data.get("loop_interval", 0),
                        nodes=nodes
                    )
                    project.tasks[task.task_id] = task
                return project

        # 兜底空项目
        return Project(project_name=os.path.basename(project_dir), variables={})

    except Exception as e:
        print(f"加载项目蓝图失败: {e}")
        raise