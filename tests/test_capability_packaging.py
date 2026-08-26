import json

from core.builder.exporter import ProjectExporter
from core.player.loader import PlayerAssetLoader
from core.project_schema import new_project_documents
from core.services.asset_service import AssetService


def test_export_and_player_loader_include_only_referenced_capability_packages(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    documents = new_project_documents('能力打包测试')
    documents['workflow.json']['main_graph']['nodes'] = [{
            'node_id': 'call-1', 'node_name': '调用能力', 'node_type': 'script_call',
            'params': {'call_mode': 'capability', 'capability_id': 'used.run'},
            'delay_before': 0, 'loop_count': 1, 'enabled': True,
        }]
    for filename, document in documents.items():
        (project / filename).write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    AssetService.ensure_structure(str(project))

    for package, capability_id in (('used', 'used.run'), ('unused', 'unused.run')):
        root = project / 'capabilities' / package
        root.mkdir(parents=True)
        (root / 'capability.json').write_text(json.dumps({
            'package_id': package,
            'functions': [{'id': capability_id, 'entry': 'main.py:run'}],
        }), encoding='utf-8')
        (root / 'main.py').write_text("def run(context, **inputs):\n    return {'success': True}\n", encoding='utf-8')

    exported = ProjectExporter.build_export_bundle(str(project), {'entry': {'task_id': 'main', 'node_id': 'call-1'}})
    _blueprint, _schema, _config, _images, context = PlayerAssetLoader.load_bundle_from_ebp(exported['ebp_file'])
    runtime_files = context['_runtime_files']
    assert 'capabilities/used/capability.json' in runtime_files
    assert 'capabilities/used/main.py' in runtime_files
    assert not any(name.startswith('capabilities/unused/') for name in runtime_files)


def test_release_keeps_page_map_when_player_exposes_a_page_node_property():
    blueprint = {
        'schema_version': 3,
        'main_graph': {
            'graph_id': 'main',
            'nodes': [{'node_id': 'wait', 'node_name': '等待', 'node_type': 'wait', 'params': {'duration_ms': 0}}],
            'edges': [],
        },
        'functions': [],
        'function_folders': [],
        'page_map': {
            'schema_version': 3,
            'nodes': [{
                'node_id': 'page_login',
                'node_name': '登录页',
                'node_type': 'page_state',
                'params': {'page_id': 'page_login_stable', 'features': [], 'feature_mode': 'and'},
            }],
            'edges': [],
        },
    }
    schema = {'groups': [{'fields': [{
        'target': '$node.page_login.params.feature_mode',
        'ui_type': 'select',
        'options': ['and', 'or'],
    }]}]}

    trimmed = ProjectExporter._trim_blueprint(blueprint, schema)

    assert trimmed['page_map']['nodes'][0]['node_id'] == 'page_login'


def test_release_drops_unused_page_map_without_smart_jump_or_player_binding():
    blueprint = {
        'main_graph': {'graph_id': 'main', 'nodes': [], 'edges': []},
        'functions': [],
        'function_folders': [],
        'page_map': {
            'schema_version': 3,
            'nodes': [{'node_id': 'unused_page', 'node_type': 'page_state', 'params': {}}],
            'edges': [],
        },
    }

    trimmed = ProjectExporter._trim_blueprint(blueprint, {'groups': []})

    assert trimmed['page_map'] == {'schema_version': 3, 'nodes': [], 'edges': []}


def test_release_keeps_transitive_function_closure_and_drops_unused_functions():
    def function(function_id, called_function_id=None, node_type='wait'):
        nodes = [{
            'node_id': f'{function_id}_node',
            'node_name': function_id,
            'node_type': node_type,
            'params': ({'function_id': called_function_id} if called_function_id else {}),
        }]
        return {
            'function_id': function_id,
            'name': function_id,
            'graph': {'graph_id': function_id, 'nodes': nodes, 'edges': []},
        }

    blueprint = {
        'schema_version': 3,
        'main_graph': {
            'graph_id': 'main',
            'nodes': [{
                'node_id': 'call_parent',
                'node_name': '调用父函数',
                'node_type': 'call_function',
                'params': {'function_id': 'parent'},
            }],
            'edges': [],
        },
        'functions': [
            function('parent', 'child', 'call_function'),
            function('child', 'grandchild', 'call_function'),
            function('grandchild', node_type='smart_jump'),
            function('unused'),
        ],
        'function_folders': [],
        'page_map': {
            'schema_version': 3,
            'nodes': [{'node_id': 'page_login', 'node_type': 'page_state', 'params': {}}],
            'edges': [],
        },
    }

    trimmed = ProjectExporter._trim_blueprint(blueprint, {'groups': []})

    assert [item['function_id'] for item in trimmed['functions']] == ['parent', 'child', 'grandchild']
    assert trimmed['page_map']['nodes'][0]['node_id'] == 'page_login'
