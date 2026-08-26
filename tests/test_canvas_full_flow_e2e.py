"""Canvas-to-backend smoke flow using the same HTTP contract as the IDE."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _workspace_headers(workspace: dict) -> dict[str, str]:
    return {
        'X-Workspace-Id': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def test_canvas_project_asset_topology_and_execution_roundtrip(client, tmp_path):
    project = tmp_path / 'canvas-e2e'

    # Entry page: create/open an empty folder as a new project.
    opened = client.post('/api/workspaces/open', json={
        'path': str(project),
        'initialize': True,
        'project_name': '画布全流程',
    })
    assert opened.status_code == 200, opened.text
    workspace = opened.json()['workspace']
    headers = _workspace_headers(workspace)

    # Resource manager / inspector preview path, including recorded-region data.
    image_path = project / 'templates' / 'image' / 'button.png'
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (24, 16), (40, 120, 220)).save(image_path)
    registered = client.post('/api/templates/register', headers=headers, json={
        'project_path': str(project),
        'relative_path': 'image/button.png',
        'kind': 'image',
    })
    assert registered.status_code == 200, registered.text
    asset = registered.json()
    reference = asset['asset_ref']

    # A capture may add location metadata after registration.
    from core.services.asset_service import AssetService

    AssetService.update_capture(str(project), reference, {
        'region': [10, 20, 24, 16],
        'reference_size': [960, 540],
        'coordinate_space': 'workspace',
    })
    resolved = client.get('/api/templates/resolve', headers=headers, params={
        'project_path': str(project), 'reference': reference,
    })
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()['capture']['region'] == [10, 20, 24, 16]
    thumb = client.get('/api/image/thumb', headers=headers, params={
        'project_path': str(project), 'name': reference,
    })
    assert thumb.status_code == 200
    assert thumb.headers['content-type'].startswith('image/png')

    # Main-flow canvas: block, positioned nodes, stable edge ports and an image node.
    workflow = {
        'main_graph': {
            'graph_id': 'main',
            'nodes': [
                {
                    'node_id': 'node_log', 'node_name': '开始日志', 'node_type': 'log',
                    'params': {'message': 'canvas-e2e-start'}, 'position': {'x': 80, 'y': 100},
                    'delay_before': 0, 'loop_count': 1, 'enabled': True,
                },
                {
                    'node_id': 'node_var', 'node_name': '变量操作', 'node_type': 'variable_op',
                    'params': {'target_var': '$var{count}', 'new_value': '1'},
                    'position': {'x': 300, 'y': 100}, 'delay_before': 0,
                    'loop_count': 1, 'enabled': True,
                },
                {
                    'node_id': 'node_wait', 'node_name': '短等待', 'node_type': 'wait',
                    'params': {'duration_ms': 1}, 'position': {'x': 520, 'y': 100},
                    'delay_before': 0, 'loop_count': 1, 'enabled': True,
                },
                {
                    'node_id': 'node_image', 'node_name': '预览资源', 'node_type': 'image_recognition',
                    'params': {
                        'image_source': reference, 'region_type': 'recorded',
                        'region_value': [0, 0, 0, 0], 'region_reference_size': [0, 0],
                    },
                    'position': {'x': 740, 'y': 100}, 'delay_before': 0,
                    'loop_count': 1, 'enabled': True,
                },
            ],
            'edges': [
                {
                    'edge_id': 'edge_log_var', 'source_node': 'node_log', 'target_node': 'node_var',
                    'source_port': 'success', 'source_port_id': 'success',
                },
                {
                    'edge_id': 'edge_var_wait', 'source_node': 'node_var', 'target_node': 'node_wait',
                    'source_port': 'success', 'source_port_id': 'success',
                },
            ],
            'blocks': [{
                'block_id': 'block_prepare', 'name': '准备阶段',
                'x': 40, 'y': 40, 'width': 720, 'height': 220,
            }],
        },
        'functions': [],
        'function_folders': [],
    }
    saved_workflow = client.post('/api/workflow/save', headers=headers, json={
        'project_path': str(project), 'workflow_data': workflow,
    })
    assert saved_workflow.status_code == 200, saved_workflow.text

    # Topology canvas is persisted separately and can reference the same stable asset.
    topology = {
        'nodes': [{
                'node_id': 'page_home', 'node_name': '主页', 'node_type': 'page_state',
                'params': {
                    'page_id': 'page_stable_home', 'feature_mode': 'and',
                    'features': [{
                        'condition_type': 'image_exists', 'image_source': reference,
                        'threshold': 85, 'region_type': 'recorded',
                    }],
                },
                'position': {'x': 120, 'y': 160}, 'delay_before': 0,
                'loop_count': 1, 'enabled': True,
        }],
        'edges': [],
        'blocks': [],
    }
    saved_topology = client.post('/api/topology/save', headers=headers, json={
        'project_path': str(project), 'topology_data': topology,
    })
    assert saved_topology.status_code == 200, saved_topology.text

    loaded_workflow = client.get('/api/workflow', headers=headers, params={'project_path': str(project)})
    loaded_topology = client.get('/api/topology', headers=headers, params={'project_path': str(project)})
    assert [node['node_id'] for node in loaded_workflow.json()['main_graph']['nodes']] == [
        'node_log', 'node_var', 'node_wait', 'node_image',
    ]
    assert [edge['edge_id'] for edge in loaded_workflow.json()['main_graph']['edges']] == [
        'edge_log_var', 'edge_var_wait',
    ]
    assert loaded_topology.json()['nodes'][0]['params']['page_id'] == 'page_stable_home'

    # "Run from current node": starts at the selected log node and follows canvas edges.
    run = client.post('/api/run', headers=headers, json={
        'project_path': str(project),
        'task_id': 'main',
        'start_node_id': 'node_log',
    })
    assert run.status_code == 200, run.text
    execution_id = run.json()['execution_id']
    status = client.get(f'/api/execution/{execution_id}')
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload['status']['status'] == 'success'
    log_text = '\n'.join(str(item) for item in payload['logs'])
    assert 'canvas-e2e-start' in log_text
    assert '等待 1 ms' in log_text
