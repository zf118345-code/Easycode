"""迁移逻辑测试

覆盖：
1. 含 workflow+topology 字段的旧版蓝图 -> 拆分后 workflow.json / topology.json 内容完整一致
2. 纯旧版蓝图（只有 tasks）-> project.json 不含 tasks，workflow.json 含 tasks，topology.json 空模板
3. 旧版顶层 nodes（无 tasks）-> 包装为 task_main
4. 损坏文件不迁移、幂等
5. 迁移后 load_project 可正常解析（Task/Node/TopologyMap）
"""

import json

from core.project_loader import load_project
from core.services.migration import ensure_migrated

LEGACY_BLUEPRINT = {
    'project_name': 'legacy_project',
    'tasks': [
        {
            'task_id': 'task_main',
            'task_name': '主任务',
            'loop_count': 1,
            'loop_interval': 0,
            'nodes': [
                {
                    'node_id': 'node_1',
                    'node_name': '点击',
                    'node_type': 'click',
                    'params': {'x': 1, 'on_success': {'target_node': 'node_2'}},
                    'position': {'x': 10, 'y': 20},
                    'on_success': None,
                    'on_failure': None,
                    'positions': {},
                    'canvas_ids': ['workflow'],
                },
                {'node_id': 'node_2', 'node_name': '等待', 'node_type': 'wait', 'params': {}, 'position': None},
            ],
        }
    ],
    'variables': {'count': 5},
    'edges': [
        {'edge_id': 'e1', 'source_node': 'node_1', 'target_node': 'node_2', 'source_port': 'success', 'canvas': 'workflow'}
    ],
    'topology': {
        'nodes': [
            {
                'node_id': 'topo_1',
                'node_name': '登录页',
                'type': 'page_state',
                'page_id': 'login_page',
                'label': '',
                'position': {'x': 100, 'y': 200},
                'features': [{'feature_type': 'image_exists', 'params': {'image_source': 'login_btn'}}],
                'feature_mode': 'and',
                'exits': [{'exit_action': '点击登录', 'target_page_id': 'main_page'}],
                'params': {},
                'condition': None,
            },
            {
                'node_id': 'topo_2',
                'node_name': '点击动作',
                'type': 'click',
                'page_id': '',
                'label': '',
                'position': {'x': 300, 'y': 100},
                'features': [],
                'feature_mode': 'and',
                'exits': [],
                'params': {},
                'condition': None,
            },
        ],
        'edges': [
            {
                'edge_id': 'te1',
                'source': 'topo_1',
                'target': 'topo_2',
                'source_exit': 'default',
                'source_port': 'success',
                'label': '',
                'condition': None,
                'action': '',
            }
        ],
    },
    'ui_state': {'canvasMode': 'topology'},
}


class TestMigrationFull:
    def test_migrate_full_blueprint(self, tmp_path):
        pdir = tmp_path / 'proj'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(json.dumps(LEGACY_BLUEPRINT, ensure_ascii=False), encoding='utf-8')

        assert ensure_migrated(str(pdir)) is True

        # 旧文件已备份且不再存在
        assert not (pdir / 'project_blueprint.json').exists()
        bak = json.loads((pdir / 'project_blueprint.json.bak').read_text(encoding='utf-8'))
        assert bak['project_name'] == 'legacy_project'

        # project.json：只含元数据
        project = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        assert project == {
            'project_name': 'legacy_project',
            'variables': {'count': 5},
            'ui_state': {'canvasMode': 'topology'},
        }

        # workflow.json：内容完整、节点废弃字段已清理、params 边已提取为 edges 实体
        workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        assert workflow['tasks'][0]['task_id'] == 'task_main'
        node_1 = workflow['tasks'][0]['nodes'][0]
        assert node_1['params'] == {'x': 1}
        assert node_1['position'] == {'x': 10, 'y': 20}
        for key in ('on_success', 'on_failure', 'positions', 'canvas_ids'):
            assert key not in node_1
        # on_success 已提取为实体边（canvas=workflow），原实体边保留
        assert workflow['_migrated_edges'] is True
        workflow_edges = {e['source_port']: e for e in workflow['edges']}
        assert workflow_edges['success']['target_node'] == 'node_2'
        assert workflow_edges['success']['source_node'] == 'node_1'
        assert workflow_edges['success']['canvas'] == 'workflow'
        for legacy_edge in LEGACY_BLUEPRINT['edges']:
            assert any(e.get('edge_id') == legacy_edge.get('edge_id') for e in workflow['edges'])

        # topology.json：任务组结构，节点折叠进 params、连线键名映射
        topology = json.loads((pdir / 'topology.json').read_text(encoding='utf-8'))
        assert len(topology['tasks']) == 1
        task = topology['tasks'][0]
        assert task['task_id'] == 'task_topology'
        assert len(task['nodes']) == 2

        topo_1 = task['nodes'][0]
        assert topo_1['node_id'] == 'topo_1'
        assert topo_1['node_type'] == 'page_state'
        assert topo_1['params']['page_id'] == 'login_page'
        # 特征已展平为新条件结构（condition_type + 平铺字段）
        assert topo_1['params']['features'] == [
            {'condition_type': 'image_exists', 'image_source': 'login_btn'}
        ]
        assert topo_1['params']['feature_mode'] == 'and'
        # 出口参数已退役（出口 = 画布连线），旧 exits 中不可解析的目标页被丢弃
        assert 'exits' not in topo_1['params']
        assert 'page_name' not in topo_1['params']
        assert topo_1['position'] == {'x': 100, 'y': 200}
        assert topo_1['label'] == ''
        assert topo_1['condition'] is None
        assert 'page_id' not in topo_1  # 已折叠进 params

        topo_2 = task['nodes'][1]
        assert topo_2['node_type'] == 'click'
        assert topo_2['params']['page_id'] == ''

        # 旧 success 边（page_state 源）在新模式下清理：出口由 exit_N 边表达
        assert topology['edges'] == []

    def test_migrate_backs_up_legacy_project_json(self, tmp_path):
        """旧格式 project.json（含 tasks）在迁移时先备份再覆盖"""
        pdir = tmp_path / 'proj2'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(json.dumps(LEGACY_BLUEPRINT, ensure_ascii=False), encoding='utf-8')
        (pdir / 'project.json').write_text(
            json.dumps({'project_name': 'old', 'tasks': [], 'variables': {'old': True}}, ensure_ascii=False),
            encoding='utf-8',
        )

        assert ensure_migrated(str(pdir)) is True

        assert (pdir / 'project.json.bak').exists()
        old_backup = json.loads((pdir / 'project.json.bak').read_text(encoding='utf-8'))
        assert old_backup['project_name'] == 'old'
        new_project = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        assert new_project['project_name'] == 'legacy_project'
        assert 'tasks' not in new_project


class TestMigrationLegacyOnly:
    def test_tasks_only_blueprint(self, tmp_path):
        """纯旧版蓝图（只有 tasks，无 topology）-> project.json 不含 tasks，workflow.json 含 tasks，topology.json 空模板"""
        pdir = tmp_path / 'proj3'
        pdir.mkdir()
        legacy = {
            'project_name': 'tasks_only',
            'tasks': [{'task_id': 't1', 'task_name': '任务', 'loop_count': 1, 'loop_interval': 0, 'nodes': []}],
            'variables': {'v': 1},
            'ui_state': {'minimapExpanded': True},
        }
        (pdir / 'project_blueprint.json').write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')

        assert ensure_migrated(str(pdir)) is True

        project = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        assert project['project_name'] == 'tasks_only'
        assert 'tasks' not in project
        workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        assert workflow['tasks'][0]['task_id'] == 't1'
        assert workflow['edges'] == []
        topology = json.loads((pdir / 'topology.json').read_text(encoding='utf-8'))
        assert topology == {'tasks': [], 'edges': []}

    def test_top_level_nodes_wrapped_into_task_main(self, tmp_path):
        """旧版顶层 nodes（无 tasks）-> 包装为 task_main"""
        pdir = tmp_path / 'proj4'
        pdir.mkdir()
        legacy = {
            'project_name': 'nodes_only',
            'nodes': [{'node_id': 'n1', 'node_name': '节点', 'node_type': 'click', 'params': {}}],
            'variables': {},
        }
        (pdir / 'project_blueprint.json').write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')

        assert ensure_migrated(str(pdir)) is True

        workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        assert workflow['tasks'][0]['task_id'] == 'task_main'
        assert workflow['tasks'][0]['nodes'][0]['node_id'] == 'n1'


class TestWorkflowEdgeMigration:
    """workflow 边实体化：params.on_success/on_failure/candidates[].on_success → edges 实体"""

    def test_extract_params_edges(self, tmp_path):
        """纯 params 连线（无现成实体边）提取为 edges 实体，params 清理"""
        pdir = tmp_path / 'proj_edges'
        pdir.mkdir()
        legacy = {
            'project_name': 'edge_proj',
            'tasks': [
                {
                    'task_id': 'task_main',
                    'task_name': '主任务',
                    'nodes': [
                        {
                            'node_id': 'n_a',
                            'node_name': 'a',
                            'node_type': 'click',
                            'params': {'on_success': {'target_node': 'n_b', 'target_task': 'task_main'}},
                            'position': None,
                        },
                        {
                            'node_id': 'n_b',
                            'node_name': 'b',
                            'node_type': 'wait',
                            'params': {'on_failure': {'target_node': 'n_c'}},
                            'position': None,
                        },
                        {
                            'node_id': 'n_c',
                            'node_name': 'c',
                            'node_type': 'branch',
                            'params': {
                                'candidates': [
                                    {'condition': {}, 'on_success': {'target_node': 'n_a'}},
                                    {'condition': {}, 'on_success': {'target_node': 'n_b'}},
                                ]
                            },
                            'position': None,
                        },
                    ],
                }
            ],
            'variables': {},
            'edges': [],
        }
        (pdir / 'project_blueprint.json').write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')

        assert ensure_migrated(str(pdir)) is True

        workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        assert workflow['_migrated_edges'] is True
        ports = {e['source_port']: e for e in workflow['edges']}
        assert ports['success']['source_node'] == 'n_a'
        assert ports['success']['target_node'] == 'n_b'
        assert ports['success']['target_task'] == 'task_main'
        assert ports['failure']['source_node'] == 'n_b'
        assert ports['failure']['target_node'] == 'n_c'
        assert ports['branch_0']['target_node'] == 'n_a'
        assert ports['branch_1']['target_node'] == 'n_b'
        for e in workflow['edges']:
            assert e['canvas'] == 'workflow'

        # params 已清理
        params_a = workflow['tasks'][0]['nodes'][0]['params']
        params_b = workflow['tasks'][0]['nodes'][1]['params']
        params_c = workflow['tasks'][0]['nodes'][2]['params']
        assert 'on_success' not in params_a
        assert 'on_failure' not in params_b
        assert all('on_success' not in (c or {}) for c in params_c['candidates'])

        # 幂等：再次迁移无变化
        before = (pdir / 'workflow.json').read_text(encoding='utf-8')
        assert ensure_migrated(str(pdir)) is False
        assert (pdir / 'workflow.json').read_text(encoding='utf-8') == before


class TestMigrationSafety:
    def test_corrupt_legacy_not_migrated(self, tmp_path):
        """损坏的旧蓝图跳过迁移且保留原文件"""
        pdir = tmp_path / 'proj5'
        pdir.mkdir()
        legacy_path = pdir / 'project_blueprint.json'
        legacy_path.write_text('{invalid json', encoding='utf-8')

        assert ensure_migrated(str(pdir)) is False
        assert legacy_path.exists()
        assert not (pdir / 'workflow.json').exists()

    def test_idempotent(self, tmp_path):
        """迁移幂等"""
        pdir = tmp_path / 'proj6'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(json.dumps(LEGACY_BLUEPRINT, ensure_ascii=False), encoding='utf-8')

        assert ensure_migrated(str(pdir)) is True
        workflow_before = (pdir / 'workflow.json').read_text(encoding='utf-8')
        assert ensure_migrated(str(pdir)) is False
        assert (pdir / 'workflow.json').read_text(encoding='utf-8') == workflow_before


class TestMigrationLoadProject:
    def test_load_project_after_migration(self, tmp_path):
        """迁移后 load_project 可正常解析三文件（Task/Node/TopologyMap）"""
        pdir = tmp_path / 'proj7'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(json.dumps(LEGACY_BLUEPRINT, ensure_ascii=False), encoding='utf-8')

        project = load_project(str(pdir))

        assert project.project_name == 'legacy_project'
        assert project.variables == {'count': 5}
        assert project.ui_state == {'canvasMode': 'topology'}
        assert 'task_main' in project.tasks
        assert project.tasks['task_main'].nodes[0].node_id == 'node_1'
        # 节点已合并默认参数，且无废弃字段
        node_1 = project.tasks['task_main'].nodes[0]
        assert not hasattr(node_1, 'canvas_ids')
        # 连线已实体化：params 不再含 on_success；同端口已有实体边时提取幂等跳过
        assert 'on_success' not in node_1.params
        # 全局连线：原实体边即代表 success 连线（提取不重复）
        assert len(project.edges) == 1
        assert project.edges[0].source_port == 'success'
        assert project.edges[0].target_node == 'node_2'
        assert project.edges[0].canvas == 'workflow'
        # 拓扑地图：任务组化，页面数据在 params 内
        assert len(project.topology.tasks) == 1
        topo_nodes = list(project.topology.iter_nodes())
        assert len(topo_nodes) == 2
        login_node = project.topology.get_node_by_page('login_page')
        assert login_node is not None
        assert login_node.node_id == 'topo_1'
        assert login_node.params['features'][0]['condition_type'] == 'image_exists'
        # 旧 success 边已清理（新模式：出口 = exit_N 边）
        assert project.topology.edges == []


class TestTopologyModernMigration:
    """新版拓扑语义迁移：exits→边、旧 success/failure 边清理、features 展平、page_name→node_name"""

    LEGACY_TOPO = {
        'project_name': 'modern_topo',
        'tasks': [],
        'topology': {
            'tasks': [
                {
                    'task_id': 'task_topology',
                    'task_name': '拓扑地图',
                    'nodes': [
                        {
                            'node_id': 'topo_a',
                            'node_name': '页面状态_1',
                            'node_type': 'page_state',
                            'params': {
                                'page_id': 'shop',
                                'page_name': '商城页',
                                'features': [
                                    {'feature_type': 'image_exists', 'params': {'template': 'shop_btn', 'threshold': 0.8}},
                                    {'feature_type': 'text_contains', 'params': {'text': '今日特惠'}, 'negate': True},
                                ],
                                'feature_mode': 'and',
                                'exits': [
                                    {'exit_action': '点击商城按钮', 'target_page_id': 'main'},
                                    {'exit_action': '点击背包按钮', 'target_page_id': 'unknown_page'},
                                ],
                            },
                        },
                        {
                            'node_id': 'topo_b',
                            'node_name': '主城页',
                            'node_type': 'page_state',
                            'params': {'page_id': 'main', 'features': [], 'feature_mode': 'and'},
                        },
                    ],
                    'edges': [
                        {'edge_id': 'te_old_succ', 'source_node': 'topo_a', 'target_node': 'topo_b',
                         'source_port': 'success', 'canvas': 'topology'},
                        {'edge_id': 'te_old_fail', 'source_node': 'topo_a', 'target_node': 'topo_b',
                         'source_port': 'failure', 'canvas': 'topology'},
                    ],
                }
            ]
        },
    }

    def _write_three_files(self, pdir):
        (pdir / 'project.json').write_text(
            json.dumps({'project_name': 'modern_topo', 'variables': {}, 'ui_state': {}}, ensure_ascii=False),
            encoding='utf-8')
        (pdir / 'workflow.json').write_text(
            json.dumps({'tasks': [], 'edges': []}, ensure_ascii=False), encoding='utf-8')
        (pdir / 'topology.json').write_text(
            json.dumps(self.LEGACY_TOPO['topology'], ensure_ascii=False), encoding='utf-8')

    def test_modern_topology_migration(self, tmp_path):
        pdir = tmp_path / 'proj_modern'
        pdir.mkdir()
        self._write_three_files(pdir)

        # 无旧蓝图文件 → ensure_migrated 返回 False，但现代化迁移仍执行
        ensure_migrated(str(pdir))

        topo = json.loads((pdir / 'topology.json').read_text(encoding='utf-8'))
        task = topo['tasks'][0]
        page_a = next(n for n in task['nodes'] if n['node_id'] == 'topo_a')

        # 1) page_name → node_name（默认名才覆盖）
        assert page_a['node_name'] == '商城页'
        assert 'page_name' not in page_a['params']

        # 2) features 展平为新条件结构
        features = page_a['params']['features']
        assert features == [
            {'condition_type': 'image_exists', 'image_source': 'shop_btn', 'threshold': 0.8},
            {'condition_type': 'text_contains', 'target_text': '今日特惠', 'negate': True},
        ]

        # 3) exits → 边：可解析目标建 exit_N 边（动作挂 label），不可解析目标丢弃
        assert 'exits' not in page_a['params']
        edges = {e['source_port']: e for e in topo['edges']}
        assert 'exit_0' in edges
        assert edges['exit_0']['target_node'] == 'topo_b'
        assert edges['exit_0']['label'] == '点击商城按钮'
        assert edges['exit_0']['canvas'] == 'topology'
        assert 'exit_1' not in edges  # unknown_page 不可解析 → 丢弃

        # 4) 旧 success/failure 边（page_state 源）清理
        assert 'success' not in edges
        assert 'failure' not in edges

    def test_modern_migration_idempotent(self, tmp_path):
        pdir = tmp_path / 'proj_modern2'
        pdir.mkdir()
        self._write_three_files(pdir)

        ensure_migrated(str(pdir))
        before = (pdir / 'topology.json').read_text(encoding='utf-8')
        # 再次迁移无变化、不写盘
        assert ensure_migrated(str(pdir)) is False
        assert (pdir / 'topology.json').read_text(encoding='utf-8') == before

    def test_branch_success_edges_cleaned(self, tmp_path):
        """workflow 中 branch 节点的旧 success/failure 边被清理"""
        pdir = tmp_path / 'proj_modern3'
        pdir.mkdir()
        self._write_three_files(pdir)
        (pdir / 'workflow.json').write_text(
            json.dumps({
                'tasks': [
                    {
                        'task_id': 'task_main',
                        'task_name': '主任务',
                        'nodes': [
                            {'node_id': 'n_branch', 'node_name': '分支', 'node_type': 'branch',
                             'params': {'candidates': [{'condition': {}}, {'condition': {}}]}},
                            {'node_id': 'n_click', 'node_name': '点击', 'node_type': 'click', 'params': {}},
                        ],
                    }
                ],
                'edges': [
                    {'edge_id': 'b_succ', 'source_node': 'n_branch', 'target_node': 'n_click',
                     'source_port': 'success', 'canvas': 'workflow'},
                    {'edge_id': 'b_branch0', 'source_node': 'n_branch', 'target_node': 'n_click',
                     'source_port': 'branch_0', 'canvas': 'workflow'},
                    {'edge_id': 'c_succ', 'source_node': 'n_click', 'target_node': 'n_branch',
                     'source_port': 'success', 'canvas': 'workflow'},
                ],
            }, ensure_ascii=False),
            encoding='utf-8')

        ensure_migrated(str(pdir))

        workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        ports = {e['source_port']: e for e in workflow['edges']}
        # branch 的 success 边清理；branch_0 与 click 的 success 边保留
        assert 'success' in ports
        assert ports['success']['source_node'] == 'n_click'
        assert ports['branch_0']['source_node'] == 'n_branch'
        assert all(e['source_port'] != 'success' or e['source_node'] != 'n_branch' for e in workflow['edges'])

    def test_feature_combine_mode_normalized(self, tmp_path):
        """特征组合方式归一化：旧默认 'and' 清空（跟随全局），显式 'or' 保留"""
        pdir = tmp_path / 'proj_combine'
        pdir.mkdir()
        (pdir / 'project.json').write_text(
            json.dumps({'project_name': 'combine', 'variables': {}, 'ui_state': {}}, ensure_ascii=False),
            encoding='utf-8')
        (pdir / 'workflow.json').write_text(
            json.dumps({'tasks': [], 'edges': []}, ensure_ascii=False), encoding='utf-8')
        (pdir / 'topology.json').write_text(
            json.dumps({
                'tasks': [
                    {
                        'task_id': 'task_topology',
                        'nodes': [
                            {
                                'node_id': 'topo_a',
                                'node_name': '页面A',
                                'node_type': 'page_state',
                                'params': {
                                    'page_id': 'page_a',
                                    'feature_mode': 'or',
                                    'features': [
                                        {'condition_type': 'image_exists', 'image_source': 'img1', 'combine_mode': 'and'},
                                        {'condition_type': 'image_exists', 'image_source': 'img2', 'combine_mode': 'or'},
                                    ],
                                },
                            }
                        ],
                    }
                ],
                'edges': [],
            }, ensure_ascii=False),
            encoding='utf-8')

        ensure_migrated(str(pdir))

        topo = json.loads((pdir / 'topology.json').read_text(encoding='utf-8'))
        features = topo['tasks'][0]['nodes'][0]['params']['features']
        # 旧默认 'and' 被清空 → 跟随全局 or；显式 'or' 保留
        assert 'combine_mode' not in features[0]
        assert features[1]['combine_mode'] == 'or'

        # 幂等：再次迁移无变化
        before = (pdir / 'topology.json').read_text(encoding='utf-8')
        assert ensure_migrated(str(pdir)) is False
        assert (pdir / 'topology.json').read_text(encoding='utf-8') == before
