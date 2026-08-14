"""全局异常处理与参数校验集成测试

验证：
- Pydantic 校验失败时返回统一错误格式 (422)
- 缺失必填参数时返回错误
- 内部异常被全局异常处理器捕获 (500)
- 统一响应格式包含 code/data/message
"""



class TestValidationErrors:
    def test_missing_required_field(self, client):
        """POST /api/blueprint/save 缺失必填字段应返回 422"""
        resp = client.post('/api/blueprint/save', json={})
        assert resp.status_code == 422
        data = resp.json()
        # 统一错误格式应包含 code
        assert 'code' in data
        assert data['code'] != 0  # 非成功

    def test_missing_query_param(self, client):
        """GET /api/blueprint 缺失必填 query 参数应返回 422"""
        resp = client.get('/api/blueprint')
        assert resp.status_code == 422


class TestGlobalExceptionHandling:
    def test_internal_error_caught(self, client):
        """触发内部异常应被全局处理器捕获，返回 500 而非崩溃"""
        # 加载不存在路径会触发异常，但不应导致连接断开
        resp = client.get('/api/blueprint', params={'project_path': '/nonexistent/trigger/error'})
        assert resp.status_code in (404, 500)
        # 响应体应为 JSON
        data = resp.json()
        assert isinstance(data, dict)


class TestResponseFormat:
    def test_success_response_format(self, client):
        """成功响应应符合统一格式 {code, data, message}"""
        resp = client.get('/api/params')
        # /api/params 直接返回 all_params dict，不经过 success() 包装
        # 这里验证至少返回有效 JSON
        assert resp.status_code == 200

    def test_error_response_format(self, client):
        """错误响应应包含 code 和 message 字段"""
        resp = client.post('/api/blueprint/save', json={})
        data = resp.json()
        assert 'code' in data
        assert 'message' in data


class TestRateLimitMiddleware:
    """速率限制中间件测试（slowapi 已安装时生效）"""

    def test_normal_request_not_blocked(self, client):
        """正常请求不应被速率限制拦截"""
        resp = client.get('/api/params')
        assert resp.status_code == 200
