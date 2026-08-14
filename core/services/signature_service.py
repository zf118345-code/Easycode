# core/services/signature_service.py
# 项目级签名校验：防止用户手动修改 JSON 导致崩溃
import hashlib
import hmac
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 签名密钥（生产环境应从环境变量或安全存储中获取）
_DEFAULT_SECRET = b'easycode_blueprint_signature_v1'
_SIGNATURE_FIELD = '_signature'
_SIGNATURE_VERSION = 'v1'


class SignatureService:
    """蓝图签名校验服务"""

    @staticmethod
    def _get_secret() -> bytes:
        """获取签名密钥"""
        return os.environ.get('EASYCODE_SIGN_SECRET', '').encode('utf-8') or _DEFAULT_SECRET

    @staticmethod
    def _compute_signature(data: dict[str, Any], secret: bytes) -> str:
        """计算数据的 HMAC-SHA256 签名
        排除 _signature 字段本身
        """
        # 移除已有签名字段
        clean_data = {k: v for k, v in data.items() if k != _SIGNATURE_FIELD}
        raw = json.dumps(clean_data, ensure_ascii=False, sort_keys=True)
        return hmac.new(secret, raw.encode('utf-8'), hashlib.sha256).hexdigest()

    @staticmethod
    def sign_blueprint(data: dict[str, Any]) -> dict[str, Any]:
        """为蓝图数据添加签名"""
        secret = SignatureService._get_secret()
        signature = SignatureService._compute_signature(data, secret)
        result = dict(data)
        result[_SIGNATURE_FIELD] = f'{_SIGNATURE_VERSION}:{signature}'
        logger.debug(f'蓝图已签名: {signature[:16]}...')
        return result

    @staticmethod
    def verify_blueprint(data: dict[str, Any]) -> tuple[bool, str]:
        """验证蓝图签名
        Returns: (is_valid, message)
        """
        if not isinstance(data, dict):
            return False, '数据格式无效'

        sig_field = data.get(_SIGNATURE_FIELD)
        if not sig_field:
            # 无签名的蓝图视为可信（向后兼容旧蓝图）
            return True, '无签名（兼容旧蓝图）'

        try:
            version, stored_sig = sig_field.split(':', 1)
        except (ValueError, AttributeError):
            return False, '签名格式无效'

        if version != _SIGNATURE_VERSION:
            return False, f'不支持的签名版本: {version}'

        secret = SignatureService._get_secret()
        computed_sig = SignatureService._compute_signature(data, secret)

        if hmac.compare_digest(stored_sig, computed_sig):
            return True, '签名验证通过'
        else:
            return False, '签名校验失败：蓝图可能已被手动篡改'

    @staticmethod
    def strip_signature(data: dict[str, Any]) -> dict[str, Any]:
        """移除签名字段"""
        return {k: v for k, v in data.items() if k != _SIGNATURE_FIELD}

    @staticmethod
    def is_signed(data: dict[str, Any]) -> bool:
        """检查蓝图是否已签名"""
        return isinstance(data, dict) and _SIGNATURE_FIELD in data
