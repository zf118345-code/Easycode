# core/converters.py
# Schema ↔ Model 双向转换层，统一前后端数据格式
from typing import List, Dict, Any, Optional
from core.models import Node, Task, Project, Edge, Jump, TopologyNode, TopologyEdge, TopologyMap
from core.schemas import NodeSchema, TaskSchema, BlueprintSchema, EdgeSchema, TopologyNodeSchema, TopologyEdgeSchema, TopologyMapSchema, JumpSchema


# ====== Node 转换 ======

def node_to_dict(node: Node) -> dict:
    """Model Node -> dict（用于 JSON 序列化）"""
    return {
        "node_id": node.node_id,
        "node_name": node.node_name,
        "node_type": node.node_type,
        "params": node.params,
        "delay_before": node.delay_before,
        "loop_count": node.loop_count,
        "enabled": node.enabled,
        "on_success": node.on_success.to_dict() if node.on_success else None,
        "on_failure": node.on_failure.to_dict() if node.on_failure else None,
        "position": node.position,
        "positions": node.positions,
        "size": node.size,
        "canvas_ids": node.canvas_ids,
    }


def dict_to_node(d: dict) -> Node:
    """dict -> Model Node"""
    return Node(
        node_id=d.get("node_id", ""),
        node_name=d.get("node_name", ""),
        node_type=d.get("node_type", ""),
        params=d.get("params", {}),
        delay_before=d.get("delay_before", 0),
        loop_count=d.get("loop_count", 1),
        enabled=d.get("enabled", True),
        on_success=Jump.from_dict(d.get("on_success")) if d.get("on_success") else None,
        on_failure=Jump.from_dict(d.get("on_failure")) if d.get("on_failure") else None,
        position=d.get("position"),
        positions=d.get("positions", {}),
        size=d.get("size"),
        canvas_ids=d.get("canvas_ids", ["workflow"]),
    )


def node_schema_to_model(schema: NodeSchema) -> Node:
    """Pydantic NodeSchema -> Model Node"""
    return dict_to_node(schema.model_dump())


def node_model_to_schema(node: Node) -> NodeSchema:
    """Model Node -> Pydantic NodeSchema"""
    return NodeSchema(**node_to_dict(node))


# ====== Task 转换 ======

def task_to_dict(task: Task) -> dict:
    return {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "loop_count": task.loop_count,
        "loop_interval": task.loop_interval,
        "nodes": [node_to_dict(n) for n in task.nodes],
    }


def dict_to_task(d: dict) -> Task:
    return Task(
        task_id=d.get("task_id", ""),
        task_name=d.get("task_name", ""),
        loop_count=d.get("loop_count", 1),
        loop_interval=d.get("loop_interval", 0),
        nodes=[dict_to_node(n) for n in d.get("nodes", [])],
    )


def task_schema_to_model(schema: TaskSchema) -> Task:
    return dict_to_task(schema.model_dump())


def task_model_to_schema(task: Task) -> TaskSchema:
    return TaskSchema(**task_to_dict(task))


# ====== Edge 转换 ======

def edge_to_dict(edge: Edge) -> dict:
    return edge.to_dict()


def dict_to_edge(d: dict) -> Edge:
    return Edge.from_dict(d)


# ====== Project 转换 ======

def project_to_dict(project: Project) -> dict:
    return {
        "project_name": project.project_name,
        "tasks": {tid: task_to_dict(t) for tid, t in project.tasks.items()},
        "variables": project.variables,
        "edges": [edge_to_dict(e) for e in project.edges],
        "topology": project.topology.to_dict() if project.topology else {"nodes": [], "edges": []},
        "ui_state": project.ui_state,
    }


def dict_to_project(d: dict) -> Project:
    project = Project(
        project_name=d.get("project_name", "default"),
        variables=d.get("variables", {}),
        edges=[dict_to_edge(e) for e in d.get("edges", [])],
        topology=TopologyMap.from_dict(d.get("topology", {})),
        ui_state=d.get("ui_state", {}),
    )
    for tid, tdict in d.get("tasks", {}).items():
        project.tasks[tid] = dict_to_task(tdict)
    return project


# ====== BlueprintSchema 转换 ======

def blueprint_dict_to_project(d: dict) -> Project:
    """蓝图 dict（前端格式）-> Project model
    前端 tasks 是 list，后端 Project.tasks 是 dict
    """
    project = Project(
        project_name=d.get("project_name", "default"),
        variables=d.get("variables", {}),
        edges=[dict_to_edge(e) for e in d.get("edges", [])],
        topology=TopologyMap.from_dict(d.get("topology", {})),
        ui_state=d.get("ui_state", {}),
    )
    tasks_list = d.get("tasks", [])
    if isinstance(tasks_list, list):
        for tdict in tasks_list:
            task = dict_to_task(tdict)
            project.tasks[task.task_id] = task
    elif isinstance(tasks_list, dict):
        for tid, tdict in tasks_list.items():
            project.tasks[tid] = dict_to_task(tdict)
    return project


def project_to_blueprint_dict(project: Project) -> dict:
    """Project model -> 蓝图 dict（前端格式，tasks 为 list）"""
    return {
        "project_name": project.project_name,
        "tasks": [task_to_dict(t) for t in project.tasks.values()],
        "variables": project.variables,
        "edges": [edge_to_dict(e) for e in project.edges],
        "topology": project.topology.to_dict() if project.topology else {"nodes": [], "edges": []},
        "ui_state": project.ui_state,
    }
