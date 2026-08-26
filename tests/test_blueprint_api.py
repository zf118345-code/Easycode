"""Strict v3 project API integration tests."""

import json

from core.project_schema import PROJECT_SCHEMA_VERSION, new_project_documents
from core.services.asset_service import AssetService


def _write_project(path, name='test_project'):
    path.mkdir(exist_ok=True)
    for filename, value in new_project_documents(name).items():
        (path / filename).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    AssetService.ensure_structure(str(path))


def _open(client, path):
    response = client.post('/api/workspaces/open', json={'path': str(path)})
    assert response.status_code == 200, response.text
    workspace = response.json()['workspace']
    return {
        'X-Workspace-Id': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


class TestBlueprintAPI:
    def test_load_current_project_documents(self, client, tmp_path):
        project = tmp_path / 'project'
        _write_project(project)
        headers = _open(client, project)

        meta = client.get('/api/blueprint', params={'project_path': str(project)}, headers=headers)
        workflow = client.get('/api/workflow', params={'project_path': str(project)}, headers=headers)
        topology = client.get('/api/topology', params={'project_path': str(project)}, headers=headers)

        assert meta.status_code == workflow.status_code == topology.status_code == 200
        assert meta.json()['schema_version'] == PROJECT_SCHEMA_VERSION
        assert workflow.json()['main_graph']['graph_id'] == 'main'
        assert workflow.json()['functions'] == []
        assert topology.json() == {'schema_version': 3, 'nodes': [], 'edges': []}

    def test_empty_project_is_rejected_without_writing_back(self, client, tmp_path):
        empty = tmp_path / 'empty'
        empty.mkdir()
        response = client.post('/api/workspaces/inspect', json={'path': str(empty)})
        assert response.status_code == 200
        assert response.json()['status'] == 'empty'
        assert not list(empty.iterdir())

    def test_workflow_and_page_map_roundtrip(self, client, tmp_path):
        project = tmp_path / 'roundtrip'
        _write_project(project)
        headers = _open(client, project)
        workflow = {
            'main_graph': {
                'graph_id': 'main',
                'nodes': [
                    {'node_id': 'a', 'node_name': '起点', 'node_type': 'log', 'params': {}},
                    {'node_id': 'b', 'node_name': '终点', 'node_type': 'log', 'params': {}},
                ],
                'edges': [{
                    'edge_id': 'e1', 'source_node': 'a', 'target_node': 'b',
                    'source_port': 'success', 'source_port_id': 'success',
                    'routing': {
                        'mode': 'manual',
                        'waypoints': [{'id': 'waypoint_1', 'x': 240, 'y': 160}],
                    },
                }],
            },
            'functions': [], 'function_folders': [],
        }
        topology = {
            'nodes': [{'node_id': 'page_node', 'node_name': '登录页', 'node_type': 'page_state', 'params': {'page_id': 'page_login', 'features': [], 'feature_mode': 'and'}}],
            'edges': [],
        }

        saved_flow = client.post('/api/workflow/save', json={'project_path': str(project), 'workflow_data': workflow}, headers=headers)
        saved_map = client.post('/api/topology/save', json={'project_path': str(project), 'topology_data': topology}, headers=headers)

        assert saved_flow.status_code == saved_map.status_code == 200
        loaded_flow = client.get('/api/workflow', params={'project_path': str(project)}, headers=headers).json()
        loaded_map = client.get('/api/topology', params={'project_path': str(project)}, headers=headers).json()
        assert loaded_flow['main_graph']['edges'][0]['edge_id'] == 'e1'
        assert loaded_flow['main_graph']['edges'][0]['routing']['waypoints'][0] == {
            'id': 'waypoint_1', 'x': 240, 'y': 160,
        }
        assert loaded_map['nodes'][0]['params']['page_id'] == 'page_login'

    def test_v2_tasks_and_page_collections_are_rejected(self, client, tmp_path):
        project = tmp_path / 'strict'
        _write_project(project)
        headers = _open(client, project)
        old_workflow = {'tasks': [], 'edges': []}
        old_topology = {'tasks': [], 'edges': []}
        flow_response = client.post('/api/workflow/save', json={'project_path': str(project), 'workflow_data': old_workflow}, headers=headers)
        map_response = client.post('/api/topology/save', json={'project_path': str(project), 'topology_data': old_topology}, headers=headers)
        assert flow_response.status_code == 400
        assert map_response.status_code == 400

    def test_function_crud_and_reference_protection(self, client, tmp_path):
        project = tmp_path / 'functions'
        _write_project(project)
        headers = _open(client, project)

        created = client.post('/api/functions', json={'project_path': str(project), 'name': '登录'}, headers=headers)
        assert created.status_code == 200, created.text
        function = created.json()
        function_id = function['function_id']
        assert function['graph']['entry_node_id']
        assert any(item['outcome_id'] == 'system_exception' for item in function['outcomes'])

        duplicate = client.post(f'/api/functions/{function_id}/duplicate', params={'project_path': str(project)}, headers=headers)
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()['function_id'] != function_id
        assert duplicate.json()['graph']['graph_id'] == duplicate.json()['function_id']

        workflow = client.get('/api/workflow', params={'project_path': str(project)}, headers=headers).json()
        workflow['main_graph']['nodes'].append({
            'node_id': 'call_login', 'node_name': '调用登录', 'node_type': 'call_function',
            'params': {'function_id': function_id, 'input_bindings': [], 'output_bindings': []},
        })
        assert client.post('/api/workflow/save', json={'project_path': str(project), 'workflow_data': workflow}, headers=headers).status_code == 200
        blocked = client.delete(f'/api/functions/{function_id}', params={'project_path': str(project)}, headers=headers)
        assert blocked.status_code == 409

    def test_missing_workflow_is_reported_invalid(self, client, tmp_path):
        project = tmp_path / 'missing_workflow'
        _write_project(project)
        (project / 'workflow.json').unlink()
        response = client.post('/api/workspaces/inspect', json={'path': str(project)})
        assert response.status_code == 200
        assert response.json()['status'] == 'invalid'
        assert 'workflow.json' in str(response.json()['errors'])
