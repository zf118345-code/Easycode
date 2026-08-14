# core/project_loader.py
# P1 改造：加载三文件结构（project.json / workflow.json / topology.json）
# 兼容回退：workflow.json / topology.json 缺失时回退旧格式 project.json 的 tasks/topology 字段

import os

from core.models import Edge, Node, Project, Task, TopologyMap
from core.services.migration import PROJECT_FILE, TOPOLOGY_FILE, WORKFLOW_FILE, ensure_migrated
from core.utils import load_json


def _load_json_optional(path):
    """文件存在则解析 JSON，否则返回 None"""
    if os.path.isfile(path):
        return load_json(path)
    return None


def load_project(project_dir):
    """
    加载项目蓝图（三文件结构）
    P1 增强：解析全局 edges、任务组化拓扑地图、调用 merge_defaults()
    """
    try:
        if not os.path.isdir(project_dir):
            return Project(project_name=os.path.basename(project_dir), variables={})

        # 懒迁移：旧版单文件 project_blueprint.json 存在时先拆分
        ensure_migrated(project_dir)

        project_path = os.path.join(project_dir, PROJECT_FILE)
        workflow_path = os.path.join(project_dir, WORKFLOW_FILE)
        topology_path = os.path.join(project_dir, TOPOLOGY_FILE)

        project_data = _load_json_optional(project_path) or {}
        workflow_data = _load_json_optional(workflow_path) or {}
        topology_data = _load_json_optional(topology_path) or {}

        project = Project(
            project_name=project_data.get('project_name', os.path.basename(project_dir)),
            variables=project_data.get('variables', {}),
        )

        # P1 新增：加载全局 edges（workflow.json；缺失时回退旧格式 project.json）
        edges_data = workflow_data.get('edges') or project_data.get('edges', [])
        for edge_data in edges_data or []:
            edge = Edge.from_dict(edge_data)
            if edge:
                project.edges.append(edge)

        # P1 新增：加载拓扑地图（topology.json；缺失时回退旧格式 project.json 的 topology）
        topo_data = None
        if topology_data and any(k in topology_data for k in ('tasks', 'edges', 'nodes')):
            topo_data = topology_data
        elif project_data.get('topology'):
            topo_data = project_data.get('topology')
        if topo_data:
            project.topology = TopologyMap.from_dict(topo_data)

        # P1 新增：加载 ui_state
        project.ui_state = project_data.get('ui_state', {})

        # 任务组（workflow.json；缺失时回退旧格式 project.json）
        tasks_data = workflow_data.get('tasks') or project_data.get('tasks', [])
        if not tasks_data and isinstance(project_data.get('nodes'), list):
            tasks_data = [
                {
                    'task_id': 'task_main',
                    'task_name': project_data.get('project_name', '主任务组'),
                    'loop_count': 1,
                    'loop_interval': 0,
                    'nodes': project_data.get('nodes', []),
                }
            ]

        for task_data in tasks_data or []:
            nodes = []
            raw_nodes = task_data.get('nodes', [])
            for node_data in raw_nodes:
                try:
                    node = Node(
                        node_id=node_data['node_id'],
                        node_name=node_data.get('node_name', node_data['node_id']),
                        node_type=node_data['node_type'],
                        params=node_data.get('params') or {},
                        delay_before=node_data.get('delay_before', 0),
                        loop_count=node_data.get('loop_count', 1),
                        enabled=node_data.get('enabled', True),
                        position=node_data.get('position'),
                        size=node_data.get('size'),
                    )

                    # P1 修复：加载时合并默认参数
                    try:
                        node.merge_defaults()
                    except Exception as e:
                        print(f'合并节点默认参数失败 [{node.node_id}]: {e}')

                    nodes.append(node)
                except Exception as e:
                    print(f'解析节点 [{node_data.get("node_id")}] 出错: {e}')
                    continue

            task = Task(
                task_id=task_data.get('task_id', 'task_main'),
                task_name=task_data.get('task_name', '主任务组'),
                loop_count=task_data.get('loop_count', 1),
                loop_interval=task_data.get('loop_interval', 0),
                nodes=nodes,
            )
            project.tasks[task.task_id] = task

        return project

    except Exception as e:
        print(f'加载项目蓝图失败: {e}')
        raise
