import json

from PIL import Image

from core.project_schema import PROJECT_SCHEMA_VERSION, create_function_definition, new_project_documents
from core.services.asset_service import AssetService
from core.services.preflight_service import PreflightService


def _write_project(path, workflow, topology=None):
    documents = new_project_documents('preflight')
    # Test cases describe the main graph compactly; persist only strict v3.
    if 'tasks' in workflow:
        nodes = [node for task in workflow.get('tasks') or [] for node in task.get('nodes') or []]
        documents['workflow.json']['main_graph'].update({
            'nodes': nodes,
            'edges': workflow.get('edges') or [],
            'blocks': workflow.get('blocks') or [],
        })
    else:
        documents['workflow.json'].update(workflow)
    if topology is not None:
        documents['topology.json'].update(topology)
    for filename, value in documents.items():
        (path / filename).write_text(json.dumps(value), encoding='utf-8')


def test_preflight_blocks_missing_stable_template(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务', 'nodes': [{
                'node_id': 'n1', 'node_name': '识图', 'node_type': 'image_recognition',
                'loop_count': 1, 'params': {'image_source': 'asset://missing'}
            }, {
                'node_id': 'n2', 'node_name': '结束', 'node_type': 'log',
                'loop_count': 1, 'params': {'message': 'done'},
            }]
        }],
        'edges': [{
            'edge_id': 'e1', 'source_node': 'n1', 'target_node': 'n2',
            'source_port': 'success', 'source_port_id': 'success',
        }]
    })

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main', 'node_id': 'n1'}, 'groups': []})

    codes = {issue['code'] for issue in report['issues']}
    assert report['can_publish'] is False
    assert 'TEMPLATE_MISSING' in codes


def test_preflight_allows_clean_minimal_project(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务', 'loop_count': 1,
            'nodes': [{'node_id': 'n1', 'node_name': '等待', 'node_type': 'wait', 'loop_count': 1, 'params': {'duration_ms': 0}}]
        }],
        'edges': []
    })

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main', 'node_id': 'n1'}, 'groups': []})

    assert report['counts']['error'] == 0
    assert report['can_publish'] is True


def test_preflight_accepts_braced_function_output_target(tmp_path):
    function = create_function_definition('计数加一')
    function['outputs'] = [{'output_id': 'output_result', 'name': 'result', 'type': 'number'}]
    _write_project(tmp_path, {
        'main_graph': {
            'graph_id': 'main',
            'nodes': [{
                'node_id': 'call', 'node_name': '调用函数', 'node_type': 'call_function',
                'loop_count': 1, 'params': {
                    'function_id': function['function_id'], 'input_bindings': [],
                    'output_bindings': [{'output_id': 'output_result', 'target': '$var{run_count}'}],
                },
            }],
            'edges': [], 'blocks': [],
        },
        'functions': [function],
        'function_folders': [],
    })

    report = PreflightService.check(str(tmp_path), {
        'schema_version': PROJECT_SCHEMA_VERSION,
        'entry': {'task_id': 'main', 'node_id': 'call'},
        'groups': [],
    })

    assert 'CALL_FUNCTION_OUTPUT_TARGET_INVALID' not in {issue['code'] for issue in report['issues']}


def test_preflight_blocks_screen_action_without_background_target(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务',
            'nodes': [{
                'node_id': 'n1', 'node_name': '点击', 'node_type': 'click', 'loop_count': 1,
                'params': {'position': [10, 20], 'position_reference_size': [1280, 720]},
            }],
        }],
        'edges': [],
    })
    (tmp_path / 'context.json').write_text(
        json.dumps({'work_mode': 'desktop', 'window_title': ''}), encoding='utf-8',
    )

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main'}, 'groups': []})
    codes = {issue['code'] for issue in report['issues']}
    assert 'BACKGROUND_TARGET_MISSING' not in codes
    assert 'DESKTOP_PHYSICAL_INPUT' in codes
    assert report['capabilities']['physical_fallback'] == 'blocked'


def test_preflight_blocks_emulator_without_adb_serial(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务',
            'nodes': [{'node_id': 'n1', 'node_name': '等待', 'node_type': 'wait', 'loop_count': 1, 'params': {}}],
        }],
        'edges': [],
    })
    (tmp_path / 'context.json').write_text(
        json.dumps({'work_mode': 'window', 'window_title': '模拟器', 'is_emulator': True}), encoding='utf-8',
    )

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main'}, 'groups': []})
    assert 'ADB_SERIAL_MISSING' in {issue['code'] for issue in report['issues']}


def test_preflight_accepts_recorded_region_from_asset_metadata(tmp_path):
    AssetService.ensure_structure(str(tmp_path))
    Image.new('RGB', (20, 10), (1, 2, 3)).save(tmp_path / 'templates' / 'image' / 'button.png')
    record = AssetService.register_file(
        str(tmp_path),
        'image/button.png',
        'image',
        capture={
            'region': [10, 20, 20, 10],
            'reference_size': [960, 540],
            'coordinate_space': 'workspace_px',
        },
    )
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务',
            'nodes': [{
                'node_id': 'n1', 'node_name': '识图', 'node_type': 'image_recognition', 'loop_count': 1,
                'params': {
                    'image_source': AssetService.reference(record['id']),
                    'region_type': 'recorded',
                    'region_value': [0, 0, 0, 0],
                    'region_reference_size': [0, 0],
                    'execution_mode': 'wait_present',
                },
            }],
        }],
        'edges': [],
    })

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main'}, 'groups': []})
    codes = {issue['code'] for issue in report['issues']}
    assert 'REGION_INVALID' not in codes
    assert 'REGION_REFERENCE_MISSING' not in codes


def test_preflight_blocks_zero_sized_custom_region(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务',
            'nodes': [{
                'node_id': 'n1', 'node_name': 'OCR', 'node_type': 'ocr_recognition', 'loop_count': 1,
                'params': {
                    'region_type': 'custom',
                    'region_value': [0, 0, 0, 0],
                    'region_reference_size': [960, 540],
                },
            }],
        }],
        'edges': [],
    })

    report = PreflightService.check(str(tmp_path), {'entry': {'task_id': 'main'}, 'groups': []})
    assert 'REGION_INVALID' in {issue['code'] for issue in report['issues']}


def test_debug_preflight_ignores_invalid_unreachable_nodes(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务', 'nodes': [
                {'node_id': 'start', 'node_name': '当前日志', 'node_type': 'log', 'loop_count': 1, 'params': {'message': 'ok'}},
                {'node_id': 'unfinished', 'node_name': '未完成识图', 'node_type': 'image_recognition', 'loop_count': 1,
                 'params': {'image_source': 'asset://missing', 'region_type': 'custom', 'region_value': [0, 0, 0, 0]}},
            ],
        }],
        'edges': [],
    })
    report = PreflightService.check(str(tmp_path), {'groups': []}, 'main', 'start', 'debug')
    assert report['can_run'] is True
    assert report['scope'] == 'debug'
    assert not {'TEMPLATE_MISSING', 'REGION_INVALID'} & {issue['code'] for issue in report['issues']}


def test_debug_preflight_keeps_invalid_reachable_nodes(tmp_path):
    _write_project(tmp_path, {
        'tasks': [{
            'task_id': 'main', 'task_name': '主任务', 'nodes': [
                {'node_id': 'start', 'node_name': '当前日志', 'node_type': 'log', 'loop_count': 1, 'params': {'message': 'ok'}},
                {'node_id': 'broken', 'node_name': '后续识图', 'node_type': 'image_recognition', 'loop_count': 1,
                 'params': {'image_source': 'asset://missing'}},
            ],
        }],
        'edges': [{'edge_id': 'e1', 'source_node': 'start', 'target_node': 'broken', 'source_port': 'success', 'source_port_id': 'success'}],
    })
    report = PreflightService.check(str(tmp_path), {'groups': []}, 'main', 'start', 'debug')
    assert report['can_run'] is False
    assert 'TEMPLATE_MISSING' in {issue['code'] for issue in report['issues']}


def test_preflight_accepts_nested_page_feature_player_binding(tmp_path):
    topology = {
        'nodes': [{
            'node_id': 'page_login',
            'node_name': '登录页',
            'node_type': 'page_state',
            'params': {
                'page_id': 'page_login_stable',
                'feature_mode': 'and',
                'features': [{'condition_type': 'variable_check', 'threshold': 85}],
            },
        }],
        'edges': [],
        'blocks': [],
    }
    _write_project(tmp_path, {
        'tasks': [{'task_id': 'main', 'task_name': '主流程', 'nodes': [{
            'node_id': 'start', 'node_name': '开始', 'node_type': 'log',
            'loop_count': 1, 'params': {'message': 'ok'},
        }]}],
        'edges': [],
    }, topology)
    target = '$node.page_login.params.features.0.threshold'
    schema = {
        'entry': {'task_id': 'main', 'node_id': 'start'},
        'groups': [{'fields': [{'label': '页面阈值', 'target': target, 'ui_type': 'number', 'default': 85}]}],
    }

    report = PreflightService.check(str(tmp_path), schema)

    assert 'SCHEMA_NODE_PARAM_UNKNOWN' not in {issue['code'] for issue in report['issues']}
