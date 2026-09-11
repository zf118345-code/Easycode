"""SecurityConfig 单元测试

验证 Salt/CORS/速率限制配置在不同环境下的行为：
- dev 模式：允许兜底 Salt
- prod 模式：缺失环境变量时必须抛异常
"""

import importlib

import pytest


def _reload_config():
    """重新加载 core.config 模块以使环境变量变更生效（类属性在导入时读取）"""
    import core.config

    importlib.reload(core.config)
    return core.config.SecurityConfig


class TestSecurityConfigDev:
    """开发环境配置测试"""

    def test_dev_env_default(self, monkeypatch):
        monkeypatch.delenv('APP_ENV', raising=False)
        monkeypatch.delenv('EASYCODE_MASTER_SALT', raising=False)
        cls = _reload_config()
        assert cls.APP_ENV == 'dev'
        assert cls.IS_PROD is False
        assert cls.IS_DEV is True

    def test_dev_master_salt_fallback(self, monkeypatch):
        monkeypatch.setenv('APP_ENV', 'dev')
        monkeypatch.delenv('EASYCODE_MASTER_SALT', raising=False)
        cls = _reload_config()
        salt = cls.get_master_salt()
        assert isinstance(salt, bytes)
        assert len(salt) > 0

    def test_dev_cors_is_limited_to_local_origins(self, monkeypatch):
        monkeypatch.setenv('APP_ENV', 'dev')
        monkeypatch.delenv('EASYCODE_CORS_ORIGINS', raising=False)
        cls = _reload_config()
        origins = cls.get_cors_origins()
        assert '*' not in origins
        assert 'http://localhost:5173' in origins
        assert 'http://127.0.0.1:8000' in origins

    def test_default_rate_limit(self, monkeypatch):
        monkeypatch.delenv('EASYCODE_RATE_LIMIT', raising=False)
        cls = _reload_config()
        assert cls.get_rate_limit() == '120/minute'


class TestSecurityConfigProd:
    """生产环境配置测试 —— 缺失加密 Salt 必须启动失败"""

    def test_prod_master_salt_missing_raises(self, monkeypatch):
        monkeypatch.setenv('APP_ENV', 'prod')
        monkeypatch.delenv('EASYCODE_MASTER_SALT', raising=False)
        cls = _reload_config()
        with pytest.raises(RuntimeError, match='EASYCODE_MASTER_SALT'):
            cls.get_master_salt()

    def test_prod_cors_loopback_default(self, monkeypatch):
        monkeypatch.setenv('APP_ENV', 'prod')
        monkeypatch.delenv('EASYCODE_CORS_ORIGINS', raising=False)
        cls = _reload_config()
        origins = cls.get_cors_origins()
        assert 'http://127.0.0.1:8000' in origins
        assert 'http://localhost:8000' in origins

    def test_prod_cors_from_env(self, monkeypatch):
        monkeypatch.setenv('APP_ENV', 'prod')
        monkeypatch.setenv('EASYCODE_CORS_ORIGINS', 'https://a.com,https://b.com')
        cls = _reload_config()
        assert cls.get_cors_origins() == ['https://a.com', 'https://b.com']


class TestSecurityHeaders:
    """安全响应头测试"""

    def test_security_headers_present(self, monkeypatch):
        monkeypatch.delenv('APP_ENV', raising=False)
        cls = _reload_config()
        headers = cls.get_security_headers()
        assert headers['X-Content-Type-Options'] == 'nosniff'
        assert headers['X-Frame-Options'] == 'SAMEORIGIN'
        assert 'X-XSS-Protection' in headers
        assert 'Referrer-Policy' in headers
        assert "script-src 'self'" in headers['Content-Security-Policy']
        assert headers['Permissions-Policy'].startswith('camera=()')
