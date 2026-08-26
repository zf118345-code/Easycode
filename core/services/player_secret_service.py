"""Machine-local protection for Player fields declared as secrets."""

from __future__ import annotations

import base64
import copy
import json
import os
import tempfile
import threading
import uuid
from typing import Any

from core.player.schema import split_target


class PlayerSecretService:
    PREFIX = 'dpapi:'
    FALLBACK_PREFIX = 'fernet:'
    _fallback_key_lock = threading.Lock()

    @classmethod
    def _fallback_fernet(cls, storage_root: str | None = None):
        from cryptography.fernet import Fernet

        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        root = os.path.abspath(storage_root) if storage_root else os.path.join(base, 'EasyCode', 'PlayerSecrets')
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, '.secret-key')
        with cls._fallback_key_lock:
            if not os.path.isfile(path):
                # Publish a completely written key with an atomic hard-link.
                # Two Player processes may initialize simultaneously; only one
                # link wins and every process subsequently reads that same key.
                temporary = f'{path}.{uuid.uuid4().hex}.tmp'
                try:
                    with open(temporary, 'xb') as stream:
                        stream.write(Fernet.generate_key())
                        stream.flush()
                        os.fsync(stream.fileno())
                    try:
                        os.chmod(temporary, 0o600)
                    except OSError:
                        pass
                    try:
                        os.link(temporary, path)
                    except FileExistsError:
                        pass
                finally:
                    try:
                        os.remove(temporary)
                    except FileNotFoundError:
                        pass
        with open(path, 'rb') as stream:
            return Fernet(stream.read().strip())

    @classmethod
    def protect(cls, value: Any, storage_root: str | None = None) -> Any:
        if value in (None, '') or (isinstance(value, str) and value.startswith(cls.PREFIX)):
            return value
        raw = str(value).encode('utf-8')
        if os.name != 'nt':
            # Player is Windows-only today; this deterministic marker keeps unit
            # tests portable without pretending to provide non-Windows secrecy.
            return 'plain-test:' + base64.b64encode(raw).decode('ascii')
        try:
            import win32crypt

            protected = win32crypt.CryptProtectData(raw, None, None, None, None, 0)
            return cls.PREFIX + base64.b64encode(protected).decode('ascii')
        except Exception:
            # Some service/test accounts do not expose a usable DPAPI profile.
            # Keep values encrypted at rest with a per-user local key instead of
            # failing the whole Player configuration workflow.
            return cls.FALLBACK_PREFIX + cls._fallback_fernet(storage_root).encrypt(raw).decode('ascii')

    @classmethod
    def unprotect(cls, value: Any, storage_root: str | None = None) -> Any:
        if not isinstance(value, str):
            return value
        if value.startswith('plain-test:'):
            return base64.b64decode(value[11:]).decode('utf-8')
        if value.startswith(cls.FALLBACK_PREFIX):
            return cls._fallback_fernet(storage_root).decrypt(value[len(cls.FALLBACK_PREFIX):].encode('ascii')).decode('utf-8')
        if not value.startswith(cls.PREFIX):
            return value
        if os.name != 'nt':
            raise ValueError('DPAPI 密文只能在创建它的 Windows 用户环境中解密')
        import win32crypt

        protected = base64.b64decode(value[len(cls.PREFIX):])
        return win32crypt.CryptUnprotectData(protected, None, None, None, 0)[1].decode('utf-8')

    @staticmethod
    def secret_targets(schema: dict) -> set[str]:
        return {
            str(field.get('target') or '')
            for group in schema.get('groups', []) or []
            for field in group.get('fields', []) or []
            if field.get('ui_type') == 'secret' and field.get('target')
        }

    @classmethod
    def secret_values(cls, schema: dict, config: dict) -> list[Any]:
        values = []
        for target in cls.secret_targets(schema or {}):
            slot, key = split_target(target)
            value = (config or {}).get(slot, {}).get(key) if slot else None
            if value not in (None, ''):
                values.append(value)
        return values

    @classmethod
    def transform_config(
        cls, schema: dict, config: dict, *, decrypt: bool = False, storage_root: str | None = None,
    ) -> dict:
        result = copy.deepcopy(config or {})
        operation = cls.unprotect if decrypt else cls.protect
        for target in cls.secret_targets(schema or {}):
            slot, key = split_target(target)
            if slot and key in result.get(slot, {}):
                result[slot][key] = operation(result[slot][key], storage_root)
        return result

    @classmethod
    def protect_document(cls, value: dict, storage_root: str | None = None) -> dict:
        """Encrypt a complete Player runtime document (for example a checkpoint)."""
        serialized = json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)
        return {
            'schema_version': 1,
            'protected': cls.protect(serialized, storage_root),
        }

    @classmethod
    def unprotect_document(cls, value: dict, storage_root: str | None = None) -> dict:
        if not isinstance(value, dict):
            raise ValueError('受保护文档格式无效')
        protected = value.get('protected')
        if not protected:
            # Keep a narrow read path for checkpoints written immediately before
            # this protection shipped. New writes are always encrypted.
            return copy.deepcopy(value)
        decoded = cls.unprotect(protected, storage_root)
        result = json.loads(decoded)
        if not isinstance(result, dict):
            raise ValueError('受保护文档内容无效')
        return result

    @staticmethod
    def redact(value: Any, secret_values: list[Any] | tuple[Any, ...] | set[Any]) -> Any:
        """Recursively mask exact secret values and occurrences inside log text."""
        secrets = [str(item) for item in secret_values if item not in (None, '')]
        if isinstance(value, dict):
            return {key: PlayerSecretService.redact(item, secrets) for key, item in value.items()}
        if isinstance(value, list):
            return [PlayerSecretService.redact(item, secrets) for item in value]
        if isinstance(value, tuple):
            return tuple(PlayerSecretService.redact(item, secrets) for item in value)
        if not isinstance(value, str):
            return value
        result = value
        for secret in secrets:
            result = result.replace(secret, '***REDACTED***')
        return result
