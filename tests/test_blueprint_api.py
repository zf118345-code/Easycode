"""蓝图 API 集成测试

使用 TestClient + 临时项目目录验证蓝图加载/保存流程：
- GET /api/blueprint 加载蓝图
- POST /api/blueprint/save 保存蓝图
- GET /api/tasks/{task_id}/nodes 获取节点列表
- 错误场景：项目不存在、任务不存在
"""

import json


class TestBlueprintAPI:
    def test_load_blueprint_ok(self, client, tmp_path, sample_blueprint):
        """加载合法蓝图应返回数据"""
        pdir = tmp_path / 'bp_project'
        pdir.mkdir()
        (pdir / 'project_blueprint.json').write_text(
            json.dumps(sample_blueprint, ensure_ascii=False), encoding='utf-8'
        )
        resp = client.get('/api/blueprint', params={'project_path': str(pdir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['project_name'] == 'test_project'

    def test_load_blueprint_not_found(self, client):
        """加载不存在的项目应返回错误"""
        resp = client.get('/api/blueprint', params={'project_path': '/nonexistent/xyz'})
        # 应返回 4xx/5xx 错误
        assert resp.status_code >= 400

    def test_save_blueprint_ok(self, client, tmp_path, sample_blueprint):
        """保存蓝图应成功"""
        pdir = tmp_path / 'save_project'
        pdir.mkdir()
        resp = client.post(
            '/api/blueprint/save',
            json={'project_path': str(pdir), 'blueprint_data': sample_blueprint},
        )
        assert resp.status_code == 200
        # 验证文件已写入
        saved = json.loads((pdir / 'project_blueprint.json').read_text(encoding='utf-8'))
        assert saved['project_name'] == 'test_project'

    def test_get_task_nodes_ok(self, client, tmp_path, sample_blueprint):
        """获取任务节点列表应返回节点信息"""
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
