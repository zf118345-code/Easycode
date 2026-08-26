import json

import pytest

from core.project_schema import (
    PROJECT_SCHEMA_VERSION,
    ProjectFormatError,
    create_function_definition,
    load_project_documents,
    new_project_documents,
    validate_canvas_graph,
    validate_topology,
    validate_workflow,
)


def _write_documents(path, documents):
    for filename, value in documents.items():
        (path / filename).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def test_current_v3_project_loads_as_main_functions_and_flat_page_map(tmp_path):
    documents = new_project_documents('新版项目')
    fn = create_function_definition('登录')
    documents['workflow.json']['functions'].append(fn)
    _write_documents(tmp_path, documents)

    loaded = load_project_documents(str(tmp_path))

    assert loaded['project.json']['project_name'] == '新版项目'
    assert all(value['schema_version'] == PROJECT_SCHEMA_VERSION for value in loaded.values())
    assert loaded['workflow.json']['main_graph']['graph_id'] == 'main'
    assert loaded['workflow.json']['functions'][0]['function_id'] == fn['function_id']
    assert loaded['topology.json'] == {'schema_version': 3, 'nodes': [], 'edges': [], 'blocks': []}


def test_missing_or_unversioned_documents_are_rejected_without_mutation(tmp_path):
    documents = new_project_documents('坏项目')
    documents['project.json'].pop('schema_version')
    _write_documents(tmp_path, documents)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    with pytest.raises(ProjectFormatError, match='schema_version'):
        load_project_documents(str(tmp_path))

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert not list(tmp_path.glob('*.bak'))


def test_v2_tasks_cross_graph_edges_and_node_folders_are_rejected():
    documents = new_project_documents('严格项目')
    documents['workflow.json']['tasks'] = []
    with pytest.raises(ProjectFormatError, match='main_graph'):
        validate_workflow(documents['workflow.json'])

    graph = {'graph_id': 'main', 'nodes': [], 'edges': [], 'blocks': [], 'node_folders': []}
    with pytest.raises(ProjectFormatError, match='node_folders'):
        validate_canvas_graph(graph, 'graph', require_graph_id=True)

    nodes = [
        {'node_id': 'a', 'node_name': 'A', 'node_type': 'log', 'params': {}},
        {'node_id': 'b', 'node_name': 'B', 'node_type': 'log', 'params': {}},
    ]
    graph = {'graph_id': 'main', 'nodes': nodes, 'blocks': [], 'edges': [{
        'edge_id': 'e1', 'source_node': 'a', 'target_node': 'b',
        'source_port': 'success', 'source_port_id': 'success', 'target_task': 'other',
    }]}
    with pytest.raises(ProjectFormatError, match='跨画布'):
        validate_canvas_graph(graph, 'graph', require_graph_id=True)


def test_geometric_blocks_never_persist_node_membership():
    graph = {
        'graph_id': 'main', 'nodes': [], 'edges': [],
        'blocks': [{'block_id': 'b1', 'name': '阶段', 'x': 0, 'y': 0, 'width': 400, 'height': 260}],
    }
    assert validate_canvas_graph(graph, 'graph', require_graph_id=True) is graph
    graph['blocks'][0]['node_ids'] = ['node_a']
    with pytest.raises(ProjectFormatError, match='node_ids'):
        validate_canvas_graph(graph, 'graph', require_graph_id=True)


def test_geometric_blocks_require_grid_alignment_and_one_grid_gap():
    graph = {
        'graph_id': 'main', 'nodes': [], 'edges': [],
        'blocks': [
            {'block_id': 'a', 'name': 'A', 'x': 0, 'y': 0, 'width': 400, 'height': 260},
            {'block_id': 'b', 'name': 'B', 'x': 420, 'y': 0, 'width': 200, 'height': 160},
        ],
    }
    assert validate_canvas_graph(graph, 'graph', require_graph_id=True) is graph

    graph['blocks'][1]['x'] = 400
    with pytest.raises(ProjectFormatError, match='间距小于 20px'):
        validate_canvas_graph(graph, 'graph', require_graph_id=True)

    graph['blocks'][1]['x'] = 430
    with pytest.raises(ProjectFormatError, match='对齐 20px 网格'):
        validate_canvas_graph(graph, 'graph', require_graph_id=True)


def test_function_contract_and_flat_page_map_are_strict():
    workflow = new_project_documents('契约')['workflow.json']
    fn = create_function_definition('识别')
    fn['parameters'].append({
        'parameter_id': 'param_text', 'name': '文本', 'type': 'string',
        'required': True, 'default_value': None,
    })
    workflow['functions'].append(fn)
    assert validate_workflow(workflow) is workflow

    topology = {'schema_version': 3, 'nodes': [], 'edges': [], 'blocks': [], 'collections': []}
    with pytest.raises(ProjectFormatError, match='唯一扁平页面地图'):
        validate_topology(topology)
