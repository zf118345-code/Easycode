"""系统 API 集成测试

使用 TestClient 遍历 system_router 的端点，验证：
- /api/params 返回参数表
- /api/projects/verify 校验项目路径存在性
- 统一响应格式
"""




class TestSystemAPI:
    """系统路由集成测试"""

    def test_get_params(self, client):
        """GET /api/params 应返回参数表（可能为空 dict）"""
        resp = client.get('/api/params')
        assert resp.status_code == 200

    def test_verify_project_not_found(self, client):
        """不存在的项目路径应返回 404"""
        resp = client.get('/api/projects/verify', params={'project_path': '/nonexistent/path/xyz'})
        assert resp.status_code == 404

    def test_verify_project_exists(self, client, tmp_path):
        """存在的项目路径应返回项目信息"""
        # 创建一个模拟项目目录
        project_dir = tmp_path / 'test_project'
        project_dir.mkdir()
        (project_dir / 'project.json').write_text('{}', encoding='utf-8')

        resp = client.get('/api/projects/verify', params={'project_path': str(project_dir)})
        assert resp.status_code == 200
        data = resp.json()
        assert data['exists'] is True
        assert data['has_project_json'] is True
        assert data['name'] == 'test_project'


class TestSecurityHeaders:
    """验证安全响应头中间件"""

    def test_security_headers_present(self, client):
        """所有响应应包含安全响应头"""
        resp = client.get('/api/params')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
        assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    def test_cors_headers_on_get(self, client):
        """带 Origin 的 GET 请求应返回 CORS 允许来源头"""
        resp = client.get('/api/params', headers={'Origin': 'http://localhost:5173'})
        assert resp.status_code == 200
        # 开发环境 CORS 允许所有来源，应回传 Origin 或 *
        assert resp.headers.get('access-control-allow-origin') is not None
