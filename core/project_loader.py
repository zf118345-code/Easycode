"""Load version-3 documents into the executor's compact runtime model."""

from __future__ import annotations

import os
from typing import Any

from core.models import Edge, Node, Project, Task, TopologyMap
from core.project_schema import MAIN_GRAPH_ID, PROJECT_FILE, TOPOLOGY_FILE, WORKFLOW_FILE, load_project_documents
from core.settings import merge_settings


def _node_from_dict(node_data: dict[str, Any]) -> Node:
    node = Node(
        node_id=node_data['node_id'],
        node_name=node_data.get('node_name', node_data['node_id']),
        node_type=node_data['node_type'],
        params=dict(node_data.get('params') or {}),
        delay_before=node_data.get('delay_before', 0),
        loop_count=node_data.get('loop_count', 1),
        enabled=node_data.get('enabled', True),
        position=node_data.get('position'),
        size=node_data.get('size'),
    )
    try:
        node.merge_defaults()
    except Exception:
        # Contract/control nodes intentionally have no registry defaults.
        pass
    return node


def _edge_from_dict(edge_data: dict[str, Any]) -> Edge | None:
    runtime = dict(edge_data)
    runtime.setdefault('canvas', 'workflow')
    return Edge.from_dict(runtime)


def _task_from_graph(
    graph: dict[str, Any], *, graph_id: str, name: str, role: str,
    description: str = '', parameters: list | None = None,
    local_variables: list | None = None, outputs: list | None = None,
    outcomes: list | None = None,
) -> Task:
    return Task(
        task_id=graph_id,
        task_name=name,
        nodes=[_node_from_dict(item) for item in graph.get('nodes') or [] if isinstance(item, dict)],
        role=role,
        description=description,
        inputs=list(parameters or []),
        local_variables=list(local_variables or []),
        outputs=list(outputs or []),
        outcomes=list(outcomes or []),
        entry_node_id=graph.get('entry_node_id'),
    )


def project_from_documents(meta: dict[str, Any], workflow: dict[str, Any], topology: dict[str, Any], fallback_name: str = 'runtime') -> Project:
    project = Project(
        project_name=meta.get('project_name', fallback_name),
        variables=dict(meta.get('variables') or {}),
    )
    project.ui_state = dict(meta.get('ui_state') or {})
    project.settings = merge_settings(meta.get('settings'))

    main_graph = workflow.get('main_graph') or {'nodes': [], 'edges': []}
    main_task = _task_from_graph(main_graph, graph_id=MAIN_GRAPH_ID, name='主流程', role='main')
    project.tasks[main_task.task_id] = main_task
    for edge_data in main_graph.get('edges') or []:
        edge = _edge_from_dict(edge_data)
        if edge:
            project.edges.append(edge)

    for function in workflow.get('functions') or []:
        if not isinstance(function, dict):
            continue
        function_id = str(function.get('function_id') or '')
        graph = function.get('graph') or {}
        task = _task_from_graph(
            graph,
            graph_id=function_id,
            name=str(function.get('name') or function_id),
            role='function',
            description=str(function.get('description') or ''),
            parameters=function.get('parameters'),
            local_variables=function.get('local_variables'),
            outputs=function.get('outputs'),
            outcomes=function.get('outcomes'),
        )
        project.tasks[function_id] = task
        for edge_data in graph.get('edges') or []:
            edge = _edge_from_dict(edge_data)
            if edge:
                project.edges.append(edge)

    project.topology = TopologyMap.from_dict(topology)
    return project


def project_from_dict(data: dict, fallback_name: str = 'runtime') -> Project:
    """Build a runtime project from the merged v3 blueprint used by Player."""
    data = data if isinstance(data, dict) else {}
    workflow = data.get('workflow') if isinstance(data.get('workflow'), dict) else {
        'main_graph': data.get('main_graph') or {},
        'functions': data.get('functions') or [],
        'function_folders': data.get('function_folders') or [],
    }
    topology = data.get('page_map') or data.get('topology') or {'nodes': [], 'edges': []}
    return project_from_documents(data, workflow, topology, fallback_name)


def load_project(project_dir: str) -> Project:
    documents = load_project_documents(project_dir)
    return project_from_documents(
        documents[PROJECT_FILE],
        documents[WORKFLOW_FILE],
        documents[TOPOLOGY_FILE],
        os.path.basename(project_dir),
    )
