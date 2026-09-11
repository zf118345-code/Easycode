"""High-level IDE contract smoke test across the user-facing backend surfaces."""

from __future__ import annotations


def _headers(workspace: dict) -> dict[str, str]:
    return {
        'X-Workspace-Id': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def test_ide_project_authoring_delivery_and_runtime_roundtrip(client, tmp_path):
    project = tmp_path / 'full-ide-roundtrip'
    opened = client.post('/api/workspaces/open', json={
        'path': str(project),
        'initialize': True,
        'project_name': '联通测试项目',
    })
    assert opened.status_code == 200, opened.text
    headers = _headers(opened.json()['workspace'])

    # Project shell and parameter registry used to render the editor.
    assert client.get('/api/params', headers=headers).status_code == 200
    meta = client.get('/api/blueprint', headers=headers, params={'project_path': str(project)})
    assert meta.status_code == 200, meta.text
    assert meta.json()['project_name'] == '联通测试项目'

    workflow = {
        'schema_version': 3,
        'main_graph': {
            'graph_id': 'main',
            'nodes': [
                {
                    'node_id': 'node_log', 'node_name': '开始', 'node_type': 'log',
                    'params': {'message': 'roundtrip'}, 'delay_before': 0,
                    'loop_count': 1, 'enabled': True, 'position': {'x': 80, 'y': 100},
                },
                {
                    'node_id': 'node_wait', 'node_name': '等待', 'node_type': 'wait',
                    'params': {'duration_ms': 1}, 'delay_before': 0,
                    'loop_count': 1, 'enabled': True, 'position': {'x': 300, 'y': 100},
                },
            ],
            'edges': [{
                'edge_id': 'edge_main', 'source_node': 'node_log', 'target_node': 'node_wait',
                'source_port': 'success', 'source_port_id': 'success',
            }],
        },
        'functions': [],
        'function_folders': [],
    }
    saved = client.post('/api/workflow/save', headers=headers, json={
        'project_path': str(project), 'workflow_data': workflow,
    })
    assert saved.status_code == 200, saved.text
    loaded_workflow = client.get('/api/workflow', headers=headers, params={'project_path': str(project)})
    assert loaded_workflow.status_code == 200, loaded_workflow.text
    assert loaded_workflow.json()['main_graph']['nodes'][0]['node_id'] == 'node_log'

    topology = {
        'schema_version': 3,
        'nodes': [{
                'node_id': 'page_home', 'node_name': '主页', 'node_type': 'page_state',
                'params': {'page_id': 'page_home_stable', 'feature_mode': 'and', 'features': []},
                'delay_before': 0, 'loop_count': 1, 'enabled': True,
                'position': {'x': 120, 'y': 140},
            }],
        'edges': [],
    }
    assert client.post('/api/topology/save', headers=headers, json={
        'project_path': str(project), 'topology_data': topology,
    }).status_code == 200
    loaded_topology = client.get('/api/topology', headers=headers, params={'project_path': str(project)})
    assert loaded_topology.json()['nodes'][0]['params']['page_id'] == 'page_home_stable'

    # Project settings must round-trip through the same project document used by autosave.
    settings = client.get('/api/project/settings', headers=headers, params={'project_path': str(project)})
    assert settings.status_code == 200, settings.text
    changed_settings = {**settings.json()['settings'], 'popup_cooldown_ms': 1234}
    updated = client.put('/api/project/settings', headers=headers, json={
        'project_path': str(project), 'settings': changed_settings,
    })
    assert updated.status_code == 200, updated.text
    assert client.get('/api/project/settings', headers=headers).json()['settings']['popup_cooldown_ms'] == 1234

    # Reusable logic is an explicit callable function. It has its own canvas and
    # can be duplicated or exported as a data-only .ecf package.
    created_function = client.post('/api/functions', headers=headers, json={
        'project_path': str(project), 'name': '可复用逻辑', 'folder_id': None,
    })
    assert created_function.status_code == 200, created_function.text
    function_id = created_function.json()['function_id']
    functions = client.get('/api/functions', headers=headers, params={'project_path': str(project)})
    assert functions.status_code == 200, functions.text
    assert functions.json()['functions'][0]['function_id'] == function_id
    duplicated = client.post(
        f'/api/functions/{function_id}/duplicate',
        headers=headers,
        params={'project_path': str(project)},
    )
    assert duplicated.status_code == 200, duplicated.text
    assert duplicated.json()['function_id'] != function_id
    exported = client.get(
        f'/api/functions/{function_id}/export',
        headers=headers,
        params={'project_path': str(project)},
    )
    assert exported.status_code == 200, exported.text
    assert '.ecf' in exported.headers['content-disposition'].lower()

    # The legacy capability editor was retired in favor of signed vNext
    # extensions; keeping a dead frontend entry would be a false promise.
    assert client.get('/api/capabilities', headers=headers).status_code == 404
    overview = client.get('/api/platform/overview', headers=headers)
    assert overview.status_code == 200, overview.text
    history = client.get('/api/history', headers=headers, params={'project_path': str(project)})
    assert history.status_code == 200, history.text
    snapshots = history.json()['snapshots']
    assert snapshots
    restored = client.post(
        f"/api/history/{snapshots[-1]['snapshot_id']}/restore",
        headers=headers,
        params={'project_path': str(project)},
    )
    assert restored.status_code == 200, restored.text

    closed = client.post('/api/workspaces/close')
    assert closed.status_code == 200, closed.text
    stale = client.get('/api/blueprint', headers=headers, params={'project_path': str(project)})
    assert stale.status_code == 409
