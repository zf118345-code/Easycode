# core/config.py
"""集中式安全配置模块

所有敏感配置（密钥、Salt、CORS 来源等）统一从此模块读取，
底层从环境变量获取，避免硬编码凭据进入代码库。

环境变量说明（请在生产环境通过 .env 或系统环境变量注入）：
- APP_ENV                : 运行环境 (dev|prod)，默认 dev
- EASYCODE_MASTER_SALT   : 资产加密 PBKDF2 Salt（生产必填）
- EASYCODE_CORS_ORIGINS  : 允许的 CORS 来源，逗号分隔 (例如 "http://a.com,http://b.com")
- EASYCODE_RATE_LIMIT    : 全局速率限制 (例如 "60/minute")，默认 "120/minute"
"""
import os
from typing import Final


class SecurityConfig:
    """安全相关配置，仅在模块加载时读取一次环境变量"""

    APP_ENV: Final[str] = os.environ.get('APP_ENV', 'dev').lower()
    IS_PROD: Final[bool] = APP_ENV == 'prod'
    IS_DEV: Final[bool] = APP_ENV == 'dev'

    # ====== 资产加密 Salt ======
    _MASTER_SALT_ENV = 'EASYCODE_MASTER_SALT'
    _DEV_FALLBACK_SALT = b'EasycodeDRMSalt2026SecureStorage'

    # ====== CORS 来源 ======
    _CORS_ORIGINS_ENV = 'EASYCODE_CORS_ORIGINS'

    # ====== 速率限制 ======
    _RATE_LIMIT_ENV = 'EASYCODE_RATE_LIMIT'
    _DEFAULT_RATE_LIMIT = '120/minute'

    @classmethod
    def get_master_salt(cls) -> bytes:
        """获取资产加密 Salt

        - 生产环境：必须通过 EASYCODE_MASTER_SALT 注入，否则启动失败
        - 开发环境：允许使用内置兜底 Salt
        """
        salt = os.environ.get(cls._MASTER_SALT_ENV, '').strip()
        if salt:
            return salt.encode('utf-8')
        if cls.IS_PROD:
            raise RuntimeError(
                f'生产环境必须设置环境变量 {cls._MASTER_SALT_ENV}，禁止使用兜底 Salt'
            )
        return cls._DEV_FALLBACK_SALT

    @classmethod
    def get_cors_origins(cls) -> list[str]:
        """获取允许的 CORS 来源列表

        - 优先读取 EASYCODE_CORS_ORIGINS（逗号分隔）
        - 未配置时仅允许 EasyCode 本机开发/运行入口

        CORS 不是身份认证，但放开 ``*`` 会允许任意网页读取本机 IDE
        API。自定义开发端口必须通过环境变量显式加入。
        """
        raw = os.environ.get(cls._CORS_ORIGINS_ENV, '').strip()
        if raw:
            return [o.strip() for o in raw.split(',') if o.strip()]

        origins = [
            'http://127.0.0.1:8000',
            'http://localhost:8000',
        ]
        if cls.IS_DEV:
            origins.extend([
                'http://127.0.0.1:5173',
                'http://localhost:5173',
                'http://127.0.0.1:5174',
                'http://localhost:5174',
                'http://127.0.0.1:4173',
                'http://localhost:4173',
            ])
        return origins

    @classmethod
    def get_rate_limit(cls) -> str:
        """获取全局速率限制规则（slowapi 格式）"""
        return os.environ.get(cls._RATE_LIMIT_ENV, '').strip() or cls._DEFAULT_RATE_LIMIT

    @classmethod
    def get_security_headers(cls) -> dict[str, str]:
        """返回推荐的 HTTP 安全响应头"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
            # Production assets are self-hosted. Monaco workers use blob URLs
            # and Vue component styles require inline style declarations.
            'Content-Security-Policy': (
                "default-src 'self'; base-uri 'none'; object-src 'none'; "
                "script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; font-src 'self' data:; "
                "connect-src 'self' http://127.0.0.1:* http://localhost:* "
                "ws://127.0.0.1:* ws://localhost:*; "
                "worker-src 'self' blob:; frame-ancestors 'self'; form-action 'self'"
            ),
        }
