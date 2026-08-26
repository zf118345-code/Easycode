from api.error_handling import internal_http_error


def test_internal_error_is_traceable_without_leaking_exception_text(caplog):
    secret = 'C:/private/customer/token.txt'

    error = internal_http_error('保存流程画布失败', RuntimeError(secret))

    assert error.status_code == 500
    assert error.detail['message'] == '保存流程画布失败，请查看后端日志'
    assert len(error.detail['error_id']) == 12
    assert secret not in str(error.detail)
    assert secret in caplog.text
    assert error.detail['error_id'] in caplog.text
