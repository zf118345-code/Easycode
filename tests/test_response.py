"""统一响应格式与错误码单元测试"""


from core.error_codes import ERROR_MESSAGES, ErrorCode
from core.response import error, error_response, success


class TestSuccessResponse:
    def test_success_default(self):
        resp = success()
        assert resp['code'] == ErrorCode.SUCCESS
        assert resp['data'] is None
        assert resp['message'] == 'success'

    def test_success_with_data(self):
        resp = success(data={'key': 'value'})
        assert resp['code'] == 0
        assert resp['data'] == {'key': 'value'}

    def test_success_custom_message(self):
        resp = success(message='操作完成')
        assert resp['message'] == '操作完成'


class TestErrorResponse:
    def test_error_with_message(self):
        resp = error(ErrorCode.BAD_REQUEST, '参数缺失')
        assert resp['code'] == ErrorCode.BAD_REQUEST
        assert resp['message'] == '参数缺失'

    def test_error_default_message_from_code(self):
        """未提供 message 时应从 ERROR_MESSAGES 取默认"""
        resp = error(ErrorCode.NOT_FOUND)
        assert resp['message'] == ERROR_MESSAGES[ErrorCode.NOT_FOUND]

    def test_error_unknown_code_default(self):
        """未知错误码且无 message 时应返回'未知错误'"""
        resp = error(99999)
        assert resp['message'] == '未知错误'

    def test_error_response_returns_jsonresponse(self):
        """error_response 应返回 JSONResponse"""
        from fastapi.responses import JSONResponse

        resp = error_response(ErrorCode.VALIDATION_ERROR, '校验失败', status_code=422)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 422

    def test_error_response_content(self):
        import json

        resp = error_response(ErrorCode.INTERNAL_ERROR, '内部错误', status_code=500)
        body = json.loads(resp.body)
        assert body['code'] == ErrorCode.INTERNAL_ERROR
        assert body['message'] == '内部错误'


class TestErrorCodes:
    def test_error_code_ranges(self):
        """验证错误码分段合理性"""
        assert 0 <= ErrorCode.SUCCESS < 100
        assert 100 <= ErrorCode.INTERNAL_ERROR < 200
        assert 200 <= ErrorCode.UNAUTHORIZED < 300
        assert 500 <= ErrorCode.BLUEPRINT_LOAD_FAILED < 600
        assert 600 <= ErrorCode.FILE_NOT_FOUND < 700

    def test_error_messages_cover_common_codes(self):
        """常见错误码应有默认消息"""
        for code in [ErrorCode.SUCCESS, ErrorCode.INTERNAL_ERROR, ErrorCode.NOT_FOUND,
                     ErrorCode.VALIDATION_ERROR, ErrorCode.UNAUTHORIZED]:
            assert code in ERROR_MESSAGES
            assert len(ERROR_MESSAGES[code]) > 0
