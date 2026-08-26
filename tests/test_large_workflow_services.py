import json
import os

from PIL import Image

from core.project_schema import create_function_definition, new_project_documents
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService
from core.services.function_package_service import FunctionPackageService
from core.services.snapshot_service import SnapshotService


def _create_project(path):
    os.makedirs(path, exist_ok=True)
    documents = new_project_documents('large-test')
    template_path = os.path.join(path, 'templates', 'image', 'login-button.png')
    os.makedirs(os.path.dirname(template_path), exist_ok=True)
    Image.new('RGB', (4, 4), (20, 30, 40)).save(template_path)
    record = AssetService.register_file(path, 'image/login-button.png', 'image')
    documents['workflow.json']['main_graph']['nodes'] = [{
        'node_id': 'n1', 'node_name': '识图', 'node_type': 'image_recognition',
        'params': {'image_source': AssetService.reference(record['id'])},
        'loop_count': 1, 'delay_before': 0,
    }]
    for filename, value in documents.items():
        with open(os.path.join(path, filename), 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)


def test_snapshots_deduplicate_restore_and_keep_limit(tmp_path, monkeypatch):
    project = str(tmp_path / 'project')
    _create_project(project)
    first = SnapshotService.capture_current(project, 'save')
    second = SnapshotService.capture_current(project, 'save')
    assert second['snapshot_id'] == first['snapshot_id']
    assert second['deduplicated'] is True

    BlueprintService.save_project_meta(project, {'project_name': 'changed', 'variables': {}, 'ui_state': {}, 'settings': {}})
    SnapshotService.restore(project, first['snapshot_id'])
    assert BlueprintService.load_project_meta(project)['project_name'] == 'large-test'

    monkeypatch.setattr(SnapshotService, 'MAX_SNAPSHOTS', 3)
    for index in range(6):
        data = BlueprintService.load_blueprint(project)
        data['variables'] = {'index': index}
        BlueprintService.save_blueprint(project, data)
    assert len(SnapshotService.list(project)) == 3


def test_ecf_export_import_clones_function_ids_and_keeps_assets(tmp_path):
    project = str(tmp_path / 'project')
    _create_project(project)
    workflow = BlueprintService.load_workflow(project)
    function = create_function_definition('通用登录')
    function['graph']['nodes'].insert(1, {
        'node_id': 'fn_image', 'node_name': '识别按钮', 'node_type': 'image_recognition',
        'params': {'image_source': workflow['main_graph']['nodes'][0]['params']['image_source']},
    })
    # Use the stable reference from the main graph; the package contains data,
    # while the project asset registry remains the source of truth.
    workflow['functions'].append(function)
    BlueprintService.save_workflow(project, workflow)

    package = FunctionPackageService.export_function(project, function['function_id'])
    result = FunctionPackageService.import_function(project, package)
    updated = BlueprintService.load_workflow(project)
    imported = next(item for item in updated['functions'] if item['function_id'] == result['root_function_id'])

    assert package.endswith('.ecf')
    assert result['imported'] == 1
    assert imported['function_id'] != function['function_id']
    assert imported['graph']['graph_id'] == imported['function_id']
    assert set(node['node_id'] for node in imported['graph']['nodes']).isdisjoint(
        node['node_id'] for node in function['graph']['nodes']
    )
    assert len(updated['functions']) == 2


def test_ecf_dependency_closure_remaps_called_function_contract_ids(tmp_path):
    project = str(tmp_path / 'project')
    _create_project(project)
    workflow = BlueprintService.load_workflow(project)

    child = create_function_definition('子函数')
    child_success = next(item['outcome_id'] for item in child['outcomes'] if item['outcome_id'] != 'system_exception')
    child['parameters'] = [{
        'parameter_id': 'parameter_old', 'name': 'amount', 'type': 'number',
        'required': True, 'default_value': None,
    }]
    child['outputs'] = [{'output_id': 'output_old', 'name': 'result', 'type': 'number'}]
    child_return = next(node for node in child['graph']['nodes'] if node['node_type'] == 'function_return')
    child_return['params']['output_bindings'] = [{'output_id': 'output_old', 'value': '$param.amount'}]
    child['test_cases'] = [{
        'test_id': 'test_old', 'name': '默认用例',
        'inputs': {'parameter_old': 3}, 'expected_outcome_id': child_success,
    }]

    parent = create_function_definition('父函数')
    entry = next(node for node in parent['graph']['nodes'] if node['node_type'] == 'function_entry')
    returned = next(node for node in parent['graph']['nodes'] if node['node_type'] == 'function_return')
    parent['graph']['nodes'].insert(1, {
        'node_id': 'call_child', 'node_name': '调用子函数', 'node_type': 'call_function',
        'params': {
            'function_id': child['function_id'],
            'input_bindings': [{'parameter_id': 'parameter_old', 'value': 7}],
            'output_bindings': [{'output_id': 'output_old', 'target': '$local.child_result'}],
        },
    })
    parent['local_variables'] = [{
        'local_id': 'local_child_result', 'name': 'child_result', 'type': 'number', 'default_value': 0,
    }]
    parent['graph']['edges'] = [
        {
            'edge_id': 'edge_entry_call', 'source_node': entry['node_id'], 'target_node': 'call_child',
            'source_port': 'success', 'source_port_id': 'success',
        },
        {
            'edge_id': 'edge_call_return', 'source_node': 'call_child', 'target_node': returned['node_id'],
            'source_port': 'outcome_0', 'source_port_id': child_success,
        },
    ]
    workflow['functions'].extend([child, parent])
    BlueprintService.save_workflow(project, workflow)

    package = FunctionPackageService.export_function(project, parent['function_id'])
    result = FunctionPackageService.import_function(project, package)
    updated = BlueprintService.load_workflow(project)
    imported_parent = next(item for item in updated['functions'] if item['function_id'] == result['root_function_id'])
    imported_call = next(node for node in imported_parent['graph']['nodes'] if node['node_type'] == 'call_function')
    imported_child = next(item for item in updated['functions'] if item['function_id'] == imported_call['params']['function_id'])

    parameter_id = imported_child['parameters'][0]['parameter_id']
    output_id = imported_child['outputs'][0]['output_id']
    outcome_id = next(item['outcome_id'] for item in imported_child['outcomes'] if item['outcome_id'] != 'system_exception')
    call_edge = next(edge for edge in imported_parent['graph']['edges'] if edge['source_node'] == imported_call['node_id'])
    assert imported_call['params']['input_bindings'][0]['parameter_id'] == parameter_id
    assert imported_call['params']['output_bindings'][0]['output_id'] == output_id
    assert call_edge['source_port_id'] == outcome_id
    assert list(imported_child['test_cases'][0]['inputs']) == [parameter_id]
    assert imported_child['test_cases'][0]['expected_outcome_id'] == outcome_id


def test_function_names_are_automatically_unique(tmp_path):
    project = str(tmp_path / 'project')
    _create_project(project)
    first = BlueprintService.create_function(project, '登录')
    second = BlueprintService.create_function(project, '登录')
    assert first['name'] == '登录'
    assert second['name'] == '登录1'


def test_blocks_are_geometry_only_and_normal_nodes_may_remain_unblocked(tmp_path):
    project = str(tmp_path / 'project')
    _create_project(project)
    workflow = BlueprintService.load_workflow(project)
    workflow['main_graph']['blocks'] = [{
        'block_id': 'prepare', 'name': '准备阶段', 'x': 0, 'y': 0, 'width': 400, 'height': 260,
    }]
    BlueprintService.save_workflow(project, workflow)
    saved = BlueprintService.load_workflow(project)['main_graph']
    assert saved['blocks'][0]['block_id'] == 'prepare'
    assert 'folder_id' not in saved['nodes'][0]
    assert 'node_ids' not in saved['blocks'][0]
