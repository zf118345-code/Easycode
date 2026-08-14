"""蓝图 API 集成测试

使用 TestClient + 临时项目目录验证三文件蓝图加载/保存流程：
- GET /api/blueprint 加载项目元数据（project.json）
- POST /api/blueprint/save 按字段拆分写入三个文件
- GET /api/workflow、POST /api/workflow/save 流程画布往返
- GET /api/topology、POST /api/topology/save 拓扑地图往返
- GET /api/tasks/{task_id}/nodes 获取节点列表
- 错误场景：项目不存在、任务不存在
- 迁移：写入旧版 project_blueprint.json 后访问自动拆分为三文件
"""

import json

from core.services.migration import ensure_migrated


class TestBlueprintAPI:
    def test_load_blueprint_ok(self, client, tmp_path, sample_blueprint):
        """写入旧版蓝图后访问应触发迁移并返回项目元数据"""
        pdir = tmp_path / 'bp_project'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(
            json.dumps(sample_blueprint, ensure_ascii=False), encoding='utf-8'
        )
        resp = client.get('/api/blueprint', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['project_name'] == 'test_project'
        assert 'tasks' not in data  # project.json 不含 tasks
        # 迁移后三个文件已生成
        assert (pdir / 'project.json').exists()
        assert (pdir / 'workflow.json').exists()
        assert (pdir / 'topology.json').exists()
        assert (pdir / 'project_blueprint.json.bak').exists()

    def test_load_blueprint_empty_project(self, client, tmp_path):
        """项目存在但无任何文件时返回默认元数据"""
        pdir = tmp_path / 'empty_project'
        pdir.mkdir()
        resp = client.get('/api/blueprint', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['project_name'] == 'empty_project'
        assert data['variables'] == {}
        assert data['ui_state'] == {}

    def test_load_blueprint_not_found(self, client):
        """加载不存在的项目应返回错误"""
        resp = client.get('/api/blueprint', params={'project_path': '/nonexistent/xyz'})
        # 应返回 4xx/5xx 错误
        assert resp.status_code >= 400

    def test_save_blueprint_split(self, client, tmp_path, sample_blueprint):
        """保存合并蓝图应拆分写入三个文件"""
        pdir = tmp_path / 'save_project'
        pdir.mkdir()
        resp = client.post(
            '/api/blueprint/save',
            json={'project_path': str(pdir), 'blueprint_data': sample_blueprint},
        )
        assert resp.status_code == 200
        # 验证三个文件已写入
        saved_project = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        assert saved_project['project_name'] == 'test_project'
        assert 'tasks' not in saved_project
        saved_workflow = json.loads((pdir / 'workflow.json').read_text(encoding='utf-8'))
        assert saved_workflow['tasks'][0]['task_id'] == 'task_main'
        assert saved_workflow['edges'] == []
        saved_topology = json.loads((pdir / 'topology.json').read_text(encoding='utf-8'))
        assert saved_topology == {'tasks': [], 'edges': []}
        # 旧文件名不再生成
        assert not (pdir / 'project_blueprint.json').exists()

    def test_workflow_roundtrip(self, client, tmp_path):
        """workflow.json 的 GET/POST 往返"""
        pdir = tmp_path / 'wf_project'
        pdir.mkdir()
        workflow_data = {
            'tasks': [{'task_id': 't1', 'task_name': '任务', 'nodes': []}],
            'edges': [{'edge_id': 'e1', 'source_node': 'a', 'target_node': 'b'}],
        }
        resp = client.post('/api/workflow/save', json={'project_path': str(pdir), 'workflow_data': workflow_data})
        assert resp.status_code == 200
        resp = client.get('/api/workflow', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['tasks'][0]['task_id'] == 't1'
        assert data['edges'][0]['edge_id'] == 'e1'

    def test_workflow_empty_default(self, client, tmp_path):
        """workflow.json 缺失时返回空模板"""
        pdir = tmp_path / 'wf_empty'
        pdir.mkdir()
        resp = client.get('/api/workflow', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        assert resp.json() == {'tasks': [], 'edges': []}

    def test_topology_roundtrip(self, client, tmp_path):
        """topology.json 的 GET/POST 往返"""
        pdir = tmp_path / 'topo_project'
        pdir.mkdir()
        topology_data = {
            'tasks': [
                {
                    'task_id': 'task_topology',
                    'task_name': '页面拓扑组',
                    'nodes': [
                        {
                            'node_id': 'topo_1',
                            'node_name': '登录页',
                            'node_type': 'page_state',
                            'params': {'page_id': 'login_page', 'features': [], 'feature_mode': 'and', 'exits': []},
                            'position': {'x': 10, 'y': 20},
                        }
                    ],
                }
            ],
            'edges': [{'edge_id': 'e1', 'source_node': 'topo_1', 'target_node': 'topo_2', 'canvas': 'topology'}],
        }
        resp = client.post('/api/topology/save', json={'project_path': str(pdir), 'topology_data': topology_data})
        assert resp.status_code == 200
        resp = client.get('/api/topology', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['tasks'][0]['nodes'][0]['node_id'] == 'topo_1'
        assert data['edges'][0]['source_node'] == 'topo_1'

    def test_topology_empty_default(self, client, tmp_path):
        """topology.json 缺失时返回空模板"""
        pdir = tmp_path / 'topo_empty'
        pdir.mkdir()
        resp = client.get('/api/topology', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        assert resp.json() == {'tasks': [], 'edges': []}

    def test_get_task_nodes_ok(self, client, tmp_path, sample_blueprint):
        """获取任务节点列表应返回节点信息（旧蓝图先自动迁移）"""
        pdir = tmp_path / 'nodes_project'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(
            json.dumps(sample_blueprint, ensure_ascii=False), encoding='utf-8'
        )
        resp = client.get(
            '/api/tasks/task_main/nodes',
            params={'project_path': str(pdir)},
        )
        assert resp.status_code == 200
        nodes = resp.json()
        assert len(nodes) == 1
        assert nodes[0]['node_id'] == 'node_1'

    def test_get_task_nodes_project_not_found(self, client):
        """项目不存在时获取节点应返回 404"""
        resp = client.get(
            '/api/tasks/task_main/nodes',
            params={'project_path': '/nonexistent/xyz'},
        )
        assert resp.status_code == 404

    def test_get_task_nodes_task_not_found(self, client, tmp_path, sample_blueprint):
        """任务不存在时获取节点应返回 404"""
        pdir = tmp_path / 'task_missing'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(
            json.dumps(sample_blueprint, ensure_ascii=False), encoding='utf-8'
        )
        resp = client.get(
            '/api/tasks/nonexistent_task/nodes',
            params={'project_path': str(pdir)},
        )
        assert resp.status_code == 404


class TestMigrationIdempotent:
    def test_second_migration_is_noop(self, tmp_path, sample_blueprint):
        """迁移幂等：第二次调用不再改变文件"""
        pdir = tmp_path / 'twice'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(
            json.dumps(sample_blueprint, ensure_ascii=False), encoding='utf-8'
        )
        assert ensure_migrated(str(pdir)) is True
        workflow_before = (pdir / 'workflow.json').read_text(encoding='utf-8')
        assert ensure_migrated(str(pdir)) is False
        assert (pdir / 'workflow.json').read_text(encoding='utf-8') == workflow_before
