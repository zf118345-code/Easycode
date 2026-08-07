# core/project_loader.py
import os
import json
from core.models import Project, Task, Node, Jump  # ⭐ 必须导入 Jump
from core.utils import load_json


def load_project(project_dir):
    """
    修正版：绝对扁平化解析项目蓝图，支持同屏多任务组平铺读取
    （纯连线驱动：废弃 jump_type，通过 target_node 和 target_task 统一路由）
    """
    try:
        for fname in ["project_blueprint.json", "project.json"]:
            blueprint_path = os.path.join(project_dir, fname)
            if os.path.exists(blueprint_path):
                blueprint_data = load_json(blueprint_path)

                project = Project(
                    project_name=blueprint_data.get("project_name", os.path.basename(project_dir)),
                    variables=blueprint_data.get("variables", {}),
                )

                tasks_data = blueprint_data.get("tasks", [])
                if not tasks_data and "nodes" in blueprint_data:
                    tasks_data = [{
                        "task_id": "task_main",
                        "task_name": blueprint_data.get("project_name", "主任务组"),
                        "loop_count": 1,
                        "loop_interval": 0,
                        "nodes": blueprint_data.get("nodes", [])
                    }]

                def parse_jump(jump_data):
                    if not isinstance(jump_data, dict):
                        return Jump(type="end")

                    target_node = jump_data.get("target_node")
                    target_task = jump_data.get("target_task") or jump_data.get("target")

                    if target_node:
                        return Jump(type="node", target_node=target_node, target=target_task)
                    else:
                        return Jump(type="end")

                for task_data in tasks_data:
                    nodes = []
                    raw_nodes = task_data.get("nodes", [])
                    for node_data in raw_nodes:
                        try:
                            params_data = node_data.get("params", {})
                            on_success = params_data.get("on_success", {})
                            on_failure = params_data.get("on_failure", {})

                            node = Node(
                                node_id=node_data["node_id"],
                                node_name=node_data.get("node_name", node_data["node_id"]),
                                node_type=node_data["node_type"],
                                params=params_data,
                                delay_before=node_data.get("delay_before", 0),
                                loop_count=node_data.get("loop_count", 1),
                                enabled=node_data.get("enabled", True),
                                on_success=parse_jump(on_success),
                                on_failure=parse_jump(on_failure),
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

        return Project(project_name=os.path.basename(project_dir), variables={})

    except Exception as e:
        print(f"加载项目蓝图失败: {e}")
        raise