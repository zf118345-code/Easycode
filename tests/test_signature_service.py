"""SignatureService 单元测试

验证蓝图签名/验签逻辑：
- 正常签名→验签通过
- 篡改数据→验签失败
- 无签名蓝图兼容旧数据
- 签名剥离
"""


from core.services.signature_service import SignatureService


class TestSignatureService:
    def test_sign_and_verify_ok(self):
        """签名后验签应通过"""
        data = {'project_name': 'test', 'count': 42, 'items': ['a', 'b']}
        signed = SignatureService.sign_blueprint(data)
        assert SignatureService.is_signed(signed)
        ok, msg = SignatureService.verify_blueprint(signed)
        assert ok is True
        assert '通过' in msg

    def test_tampered_data_fails(self):
        """篡改已签名数据后验签应失败"""
        data = {'project_name': 'test', 'count': 42}
        signed = SignatureService.sign_blueprint(data)
        # 篡改数据
        signed['count'] = 999
        ok, msg = SignatureService.verify_blueprint(signed)
        assert ok is False
        assert '篡改' in msg

    def test_unsigned_blueprint_compatible(self):
        """无签名的旧蓝图应视为可信"""
        data = {'project_name': 'old_project', 'count': 1}
        ok, msg = SignatureService.verify_blueprint(data)
        assert ok is True
        assert '兼容' in msg

    def test_strip_signature(self):
        """剥离签名字段后应不再含签名"""
        data = {'project_name': 'test'}
        signed = SignatureService.sign_blueprint(data)
        assert SignatureService.is_signed(signed)
        stripped = SignatureService.strip_signature(signed)
        assert not SignatureService.is_signed(stripped)
        assert stripped == {'project_name': 'test'}

    def test_invalid_signature_format(self):
        """签名格式损坏应返回失败"""
        data = {'project_name': 'test', '_signature': 'badformat'}
        ok, msg = SignatureService.verify_blueprint(data)
        assert ok is False

    def test_unsupported_version(self):
        """不支持的签名版本应返回失败"""
        data = {'project_name': 'test', '_signature': 'v999:abc123'}
        ok, msg = SignatureService.verify_blueprint(data)
        assert ok is False
        assert '版本' in msg

    def test_sign_does_not_mutate_original(self):
        """签名不应修改原始数据"""
        data = {'project_name': 'test'}
        original = dict(data)
        SignatureService.sign_blueprint(data)
        assert data == original

    def test_non_dict_input(self):
        """非字典输入应返回失败"""
        ok, msg = SignatureService.verify_blueprint('not a dict')
        assert ok is False

    def test_is_signed_false_for_plain_dict(self):
        """普通字典 is_signed 应为 False"""
        assert SignatureService.is_signed({'a': 1}) is False

    def test_consistent_signature(self):
        """相同数据多次签名应得到相同签名"""
        data = {'project_name': 'test', 'count': 5}
        s1 = SignatureService.sign_blueprint(data)
        s2 = SignatureService.sign_blueprint(data)
        assert s1['_signature'] == s2['_signature']
