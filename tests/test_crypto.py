"""SecureAssetCrypto 加解密单元测试

验证 AES-256-CBC 加解密回环与 PBKDF2 密钥派生：
- encrypt → decrypt 回环一致
- 不同 machine_code 派生不同 key
- 短字节流解密应报错
"""

import pytest

from core.security.crypto import SecureAssetCrypto


class TestEncryptDecrypt:
    def test_roundtrip_small_data(self):
        """小数据加解密回环"""
        key = b'0' * 32  # 32 字节 AES-256 密钥
        raw = b'hello world'
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        decrypted = SecureAssetCrypto.decrypt_ebp_stream(encrypted, key)
        assert decrypted == raw

    def test_roundtrip_large_data(self):
        """大数据加解密回环"""
        key = b'A' * 32
        raw = b'x' * 10000
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        decrypted = SecureAssetCrypto.decrypt_ebp_stream(encrypted, key)
        assert decrypted == raw

    def test_roundtrip_empty_data(self):
        """空数据加解密回环"""
        key = b'B' * 32
        raw = b''
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        decrypted = SecureAssetCrypto.decrypt_ebp_stream(encrypted, key)
        assert decrypted == raw

    def test_wrong_key_fails(self):
        """错误密钥解密应失败（PKCS7 去填充错误或数据损坏）"""
        key1 = b'C' * 32
        key2 = b'D' * 32
        raw = b'secret data'
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key1)
        # 错误密钥会导致 PKCS7 去填充失败或解密数据损坏，具体异常类型取决于失败位置
        with pytest.raises((ValueError, Exception)):  # noqa: B017
            SecureAssetCrypto.decrypt_ebp_stream(encrypted, key2)

    def test_encrypted_has_iv_prefix(self):
        """加密结果应包含 16 字节 IV 前缀"""
        key = b'E' * 32
        raw = b'test'
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        assert len(encrypted) >= 16  # 至少 IV 长度
        assert len(encrypted) > len(raw)  # 加密后应更长（IV + padding）

    def test_decrypt_short_data_raises(self):
        """小于 16 字节的密文应报错"""
        key = b'F' * 32
        with pytest.raises(ValueError, match='无效或长度不足'):
            SecureAssetCrypto.decrypt_ebp_stream(b'short', key)

    def test_iv_is_random(self):
        """同一明文多次加密应产生不同密文（IV 随机）"""
        key = b'G' * 32
        raw = b'same input'
        e1 = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        e2 = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        assert e1 != e2  # IV 不同 → 密文不同


class TestKeyDerivation:
    def test_different_machine_different_key(self):
        """不同机器码应派生不同密钥"""
        master_key = b'master_secret_key'
        key1 = SecureAssetCrypto.derive_key_from_machine(master_key, 'MACHINE_A')
        key2 = SecureAssetCrypto.derive_key_from_machine(master_key, 'MACHINE_B')
        assert key1 != key2

    def test_same_machine_same_key(self):
        """相同机器码应派生相同密钥（确定性）"""
        master_key = b'master_secret_key'
        key1 = SecureAssetCrypto.derive_key_from_machine(master_key, 'MACHINE_X')
        key2 = SecureAssetCrypto.derive_key_from_machine(master_key, 'MACHINE_X')
        assert key1 == key2

    def test_derived_key_length(self):
        """派生密钥应为 32 字节（AES-256）"""
        key = SecureAssetCrypto.derive_key_from_machine(b'mk', 'MC')
        assert len(key) == 32

    def test_derived_key_usable_for_encryption(self):
        """派生密钥应可直接用于加解密"""
        master_key = b'master_secret'
        machine_code = 'ABC-123'
        key = SecureAssetCrypto.derive_key_from_machine(master_key, machine_code)
        raw = b'test data for derived key'
        encrypted = SecureAssetCrypto.encrypt_ebp_stream(raw, key)
        decrypted = SecureAssetCrypto.decrypt_ebp_stream(encrypted, key)
        assert decrypted == raw
