"""不含项目路径状态的系统级 API 回归测试。"""

import pytest

from api.app import main


def test_packaged_cli_entrypoint_is_callable():
    with pytest.raises(SystemExit) as exited:
        main(['--help'])
    assert exited.value.code == 0


class TestSystemAPI:
    """系统路由集成测试"""

    def test_get_params(self, client):
        """GET /api/params 应返回参数表（可能为空 dict）"""
        resp = client.get('/api/params')
        assert resp.status_code == 200


class TestSecurityHeaders:
    """验证安全响应头中间件"""

    def test_security_headers_present(self, client):
        """所有响应应包含安全响应头"""
        resp = client.get('/api/params')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
        assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
        assert "script-src 'self'" in resp.headers.get('Content-Security-Policy', '')
        assert resp.headers.get('Permissions-Policy', '').startswith('camera=()')

    def test_cors_headers_on_get(self, client):
        """带 Origin 的 GET 请求应返回 CORS 允许来源头"""
        resp = client.get('/api/params', headers={'Origin': 'http://localhost:5173'})
        assert resp.status_code == 200
        assert resp.headers.get('access-control-allow-origin') == 'http://localhost:5173'

    def test_cors_rejects_untrusted_web_origin(self, client):
        resp = client.get('/api/params', headers={'Origin': 'https://untrusted.example'})
        assert resp.status_code == 200
        assert resp.headers.get('access-control-allow-origin') is None
