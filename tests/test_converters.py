"""测试 Schema ↔ Model 转换器"""
import pytest
from core.converters import (
    dict_to_node, node_to_dict, dict_to_task, task_to_dict,
    dict_to_edge, edge_to_dict, dict_to_project, project_to_dict,
    blueprint_dict_to_project, project_to_blueprint_dict
)
from core.models import Node, Task, Project, Edge


class TestNodeConverter:
    def test_dict_to_node_basic(self):
        d = {"node_id": "n1", "node_name": "测试", "node_type": "click", "params": {"x": 1}}
        node = dict_to_node(d)
        assert node.node_id == "n1"
        assert node.node_name == "测试"
        assert node.node_type == "click"
        assert node.params == {"x": 1}

    def test_dict_to_node_defaults(self):
        d = {"node_id": "n1", "node_name": "测试", "node_type": "click"}
        node = dict_to_node(d)
        assert node.delay_before == 0
        assert node.loop_count == 1
        assert node.enabled is True
        assert node.canvas_ids == ["workflow"]

    def test_node_to_dict_roundtrip(self):
        node = Node(node_id="n1", node_name="测试", node_type="click", params={"x": 1})
        d = node_to_dict(node)
        assert d["node_id"] == "n1"
        assert d["params"] == {"x": 1}
        node2 = dict_to_node(d)
        assert node2.node_id == node.node_id
        assert node2.params == node.params


class TestTaskConverter:
    def test_dict_to_task(self):
        d = {
            "task_id": "t1", "task_name": "任务1",
            "nodes": [{"node_id": "n1", "node_name": "节点", "node_type": "click"}]
        }
        task = dict_to_task(d)
        assert task.task_id == "t1"
        assert len(task.nodes) == 1
        assert task.nodes[0].node_id == "n1"

    def test_task_to_dict_roundtrip(self):
        task = Task(task_id="t1", task_name="任务1",
                     nodes=[Node(node_id="n1", "node_name": "节点", "node_type": "click")])
        d = task_to_dict(task)
        assert d["task_id"] == "t1"
        task2 = dict_to_task(d)
        assert task2.task_id == task.task_id


class TestProjectConverter:
    def test_blueprint_dict_to_project(self):
        bp = {
            "project_name": "test",
            "tasks": [{"task_id": "t1", "task_name": "任务1", "nodes": []}],
            "variables": {"x": 1},
            "edges": [],
            "topology": {"nodes": [], "edges": []}
        }
        project = blueprint_dict_to_project(bp)
        assert project.project_name == "test"
        assert "t1" in project.tasks
        assert project.variables == {"x": 1}

    def test_project_to_blueprint_dict(self):
        project = Project(project_name="test")
        project.tasks["t1"] = Task(task_id="t1", task_name="任务1", nodes=[])
        project.variables = {"x": 1}
        bp = project_to_blueprint_dict(project)
        assert bp["project_name"] == "test"
        assert isinstance(bp["tasks"], list)
        assert bp["tasks"][0]["task_id"] == "t1"
