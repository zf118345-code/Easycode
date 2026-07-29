# core/project_loader.py
import os
import json
from core.models import Project, Task, Node, Jump
from core.utils import load_json

def load_project(project_dir):
    project_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(project_path):
        project = Project(project_name=os.path.basename(project_dir), variables={})
        return project
    project_data = load_json(project_path)
    project = Project(
        project_name=project_data.get("project_name", "default"),
        variables=project_data.get("variables", {}),
    )
    tasks_dir = os.path.join(project_dir, "tasks")
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
        return project
    for filename in os.listdir(tasks_dir):
        if filename.endswith(".json"):
            task_path = os.path.join(tasks_dir, filename)
            task_data = load_json(task_path)
            nodes = []
            for node_data in task_data.get("nodes", []):
                on_success = node_data.get("on_success")
                if on_success is None:
                    on_success = Jump()
                else:
                    on_success = Jump(type=on_success.get("type", "next"),
                                      target=on_success.get("target"),
                                      target_node=on_success.get("target_node"),
                                      return_on_complete=on_success.get("return_on_complete", False))
                on_failure = node_data.get("on_failure")
                if on_failure is None:
                    on_failure = Jump()
                else:
                    on_failure = Jump(type=on_failure.get("type", "next"),
                                      target=on_failure.get("target"),
                                      target_node=on_failure.get("target_node"),
                                      return_on_complete=on_failure.get("return_on_complete", False))
                params = node_data.get("params", {})
                node_name = node_data.get("node_name")
                if not node_name:
                    node_name = node_data.get("node_id", "")
                node = Node(
                    node_id=node_data["node_id"],
                    node_name=node_name,
                    node_type=node_data["node_type"],
                    params=params,
                    delay_before=node_data.get("delay_before", 0),
                    loop_count=node_data.get("loop_count", 1),
                    enabled=node_data.get("enabled", True),
                    on_success=on_success,
                    on_failure=on_failure,
                    position=node_data.get("position")
                )
                node.params.pop("loop_interval", None)
                node.merge_defaults()
                nodes.append(node)
            task = Task(
                task_id=task_data["task_id"],
                task_name=task_data.get("task_name", task_data["task_id"]),
                loop_count=task_data.get("loop_count", 1),
                loop_interval=task_data.get("loop_interval", 0),
                nodes=nodes
            )
            project.tasks[task.task_id] = task
    return project