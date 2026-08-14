# core/project_loader.py
# P1 改造：加载全局 edges 列表、拓扑地图数据、调用 merge_defaults()

import os

from core.models import Edge, Jump, Node, Project, Task, TopologyMap
from core.utils import load_json


def load_project(project_dir):
    """
    加载项目蓝图
    P1 增强：解析全局 edges、拓扑地图、多画布坐标
    """
    try:
        for fname in ['project_blueprint.json', 'project.json']:
            blueprint_path = os.path.join(project_dir, fname)
            if os.path.exists(blueprint_path):
                blueprint_data = load_json(blueprint_path)

                project = Project(
                    project_name=blueprint_data.get('project_name', os.path.basename(project_dir)),
                    variables=blueprint_data.get('variables', {}),
                )

                # P1 新增：加载全局 edges
                edges_data = blueprint_data.get('edges', [])
                for edge_data in edges_data:
                    edge = Edge.from_dict(edge_data)
                    if edge:
                        project.edges.append(edge)

                # P1 新增：加载拓扑地图
                topology_data = blueprint_data.get('topology')
                if topology_data:
                    project.topology = TopologyMap.from_dict(topology_data)

                # P1 新增：加载 ui_state
                project.ui_state = blueprint_data.get('ui_state', {})

                tasks_data = blueprint_data.get('tasks', [])
                if not tasks_data and 'nodes' in blueprint_data:
                    tasks_data = [
                        {
                            'task_id': 'task_main',
                            'task_name': blueprint_data.get('project_name', '主任务组'),
                            'loop_count': 1,
                            'loop_interval': 0,
                            'nodes': blueprint_data.get('nodes', []),
                        }
                    ]

                for task_data in tasks_data:
                    nodes = []
                    raw_nodes = task_data.get('nodes', [])
                    for node_data in raw_nodes:
                        try:
                            params_data = node_data.get('params', {})
                            on_success = params_data.get('on_success', {})
                            on_failure = params_data.get('on_failure', {})

                            node = Node(
                                node_id=node_data['node_id'],
                                node_name=node_data.get('node_name', node_data['node_id']),
                                node_type=node_data['node_type'],
                                params=params_data,
                                delay_before=node_data.get('delay_before', 0),
                                loop_count=node_data.get('loop_count', 1),
                                enabled=node_data.get('enabled', True),
                                on_success=Jump.from_dict(on_success),
                                on_failure=Jump.from_dict(on_failure),
                                position=node_data.get('position'),
                                # P1 新增：多画布坐标
                                positions=node_data.get('positions', {}),
                                size=node_data.get('size'),
                                canvas_ids=node_data.get('canvas_ids', ['workflow']),
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

        return Project(project_name=os.path.basename(project_dir), variables={})

    except Exception as e:
        print(f'加载项目蓝图失败: {e}')
        raise
