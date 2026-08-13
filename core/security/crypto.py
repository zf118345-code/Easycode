# core/security/crypto.py
import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, kdf
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class SecureAssetCrypto:
    """
    高级 AES-256 动态加解密与 PBKDF2 密钥派生引擎
    """

    MASTER_SALT = b"EasycodeDRMSalt2026SecureStorage"

    @classmethod
    def derive_key_from_machine(cls, master_key: bytes, machine_code: str) -> bytes:
        """
        将 MasterKey 与本机 MachineCode 结合，通过 PBKDF2 派生本机专属解密 Key
        确保将 .ebp 密包拷贝到其他机器上也无法直接用通用 Key 解密
        """
        combined_seed = master_key + machine_code.encode("utf-8")
        kdf_engine = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=cls.MASTER_SALT,
            iterations=100000,
            backend=default_backend()
        )
        return kdf_engine.derive(combined_seed)

    @classmethod
    def encrypt_ebp_stream(cls, raw_data: bytes, key: bytes) -> bytes:
        """使用 AES-256-CBC 模式加密字节流并追加随机 16 字节 IV 头部"""
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(raw_data) + padder.finalize()

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        cipher_bytes = encryptor.update(padded_data) + encryptor.finalize()

        return iv + cipher_bytes

    @classmethod
    def decrypt_ebp_stream(cls, encrypted_bytes: bytes, key: bytes) -> bytes:
        """解密 AES-256-CBC 加密数据并去除 PKCS7 填充"""
        if len(encrypted_bytes) < 16:
            raise ValueError("加密字节流无效或长度不足")

        iv = encrypted_bytes[:16]
        cipher_data = encrypted_bytes[16:]

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(cipher_data) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        raw_data = unpadder.update(padded_data) + unpadder.finalize()
        return raw_data