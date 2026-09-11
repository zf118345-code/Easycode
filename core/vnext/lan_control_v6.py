"""Local-first authenticated LAN control plane for EasyCode v6.

The transport is intentionally narrow.  It provides stable device identity,
explicit short-lived pairing, a mutually authenticated encrypted request
channel and three independent permissions (messages, status and remote start).
Business protocols register handlers; this module never treats an ordinary
message as a privileged dispatch command.

There is no cloud discovery or relay fallback.  TCP and UDP sockets are bound
only when ``start`` is explicitly called and are closed deterministically by
``stop``/``close``.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import platform
import secrets
import socket
import sqlite3
import struct
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


LAN_SCHEMA_VERSION = 1
LAN_PROTOCOL_VERSION = 1
DEFAULT_PAIRING_TTL_MS = 5 * 60 * 1000
MAX_PAIRING_TTL_MS = 15 * 60 * 1000
MAX_CLOCK_SKEW_MS = 60_000
MAX_REQUEST_TTL_MS = 7 * 24 * 60 * 60 * 1000
MAX_FRAME_BYTES = 2 * 1024 * 1024
DISCOVERY_MAGIC = "easycode.lan.discovery.v6"
PERMISSIONS = frozenset({"messages", "status", "remote_start"})


class LanControlError(RuntimeError):
    """Stable, user-safe LAN control failure."""

    def __init__(
        self,
        message: str,
        *,
        error_id: str = "lan.transport_unavailable",
        transient: bool = False,
        action: str = "retry",
    ) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = bool(transient)
        self.action = action


class _ClosingConnection(sqlite3.Connection):
    """Commit/rollback like sqlite3's context manager, then release Windows locks."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _iso(milliseconds: int | None = None) -> str:
    value = _now_ms() if milliseconds is None else int(milliseconds)
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: Any) -> bytes:
    text = str(value or "")
    try:
        return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise LanControlError(
            "安全传输字段编码无效", error_id="lan.protocol_invalid", action="export_diagnostics"
        ) from exc


def _fingerprint(public_key: bytes) -> str:
    digest = hashlib.sha256(public_key).hexdigest().upper()
    return "-".join(digest[index : index + 4] for index in range(0, 32, 4))


def _request_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalize_permissions(value: Mapping[str, Any] | Iterable[str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "messages": False,
        "status": False,
        "remote_start": False,
        "allowed_products": [],
        "allowed_instances": [],
    }
    if value is None:
        return result
    if isinstance(value, Mapping):
        for name in PERMISSIONS:
            result[name] = bool(value.get(name, False))
        for name in ("allowed_products", "allowed_instances"):
            raw = value.get(name) or []
            if not isinstance(raw, (list, tuple, set)):
                raise LanControlError(
                    f"{name} 必须是稳定 ID 列表", error_id="lan.permission_invalid", action="fix_request"
                )
            result[name] = sorted({str(item).strip() for item in raw if str(item).strip()})
    else:
        selected = {str(item) for item in value}
        unknown = selected - PERMISSIONS
        if unknown:
            raise LanControlError(
                "设备权限包含未知动作", error_id="lan.permission_invalid", action="fix_request"
            )
        for name in selected:
            result[name] = True
    if not result["remote_start"]:
        result["allowed_products"] = []
        result["allowed_instances"] = []
    return result


def _pairing_key(code: str, session_id: str) -> bytes:
    normalized = "".join(ch for ch in str(code).upper() if ch.isalnum())
    if len(normalized) < 8:
        raise LanControlError(
            "配对码格式无效", error_id="lan.pairing_code_invalid", action="enter_pairing_code"
        )
    return hashlib.pbkdf2_hmac(
        "sha256", normalized.encode("ascii"), session_id.encode("utf-8"), 120_000, dklen=32
    )


def _protect_private_key(raw: bytes) -> tuple[str, str]:
    """Use the current Windows user boundary; CI/dev fallback is mode-0600."""

    if os.name == "nt":
        try:
            import win32crypt

            protected = win32crypt.CryptProtectData(raw, None, None, None, None, 0)
            return "dpapi-current-user-v1", base64.b64encode(protected).decode("ascii")
        except Exception as exc:  # pragma: no cover - depends on Windows profile
            raise LanControlError(
                "当前 Windows 用户的安全凭据存储不可用",
                error_id="lan.identity_keystore_unavailable",
                action="check_windows_profile",
            ) from exc
    return "file-user-only-v1", base64.b64encode(raw).decode("ascii")


def _unprotect_private_key(kind: str, value: str) -> bytes:
    try:
        encoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise LanControlError(
            "设备私钥记录已损坏", error_id="lan.identity_corrupt", action="export_diagnostics"
        ) from exc
    if kind == "dpapi-current-user-v1":
        if os.name != "nt":
            raise LanControlError(
                "设备私钥只能由创建它的 Windows 用户读取",
                error_id="lan.identity_keystore_unavailable",
                action="open_on_original_user",
            )
        try:
            import win32crypt

            return bytes(win32crypt.CryptUnprotectData(encoded, None, None, None, 0)[1])
        except Exception as exc:  # pragma: no cover - depends on Windows profile
            raise LanControlError(
                "设备私钥无法由当前 Windows 用户解密",
                error_id="lan.identity_keystore_unavailable",
                action="check_windows_profile",
            ) from exc
    if kind == "file-user-only-v1" and os.name != "nt":
        return encoded
    raise LanControlError(
        "设备私钥保护格式不受支持", error_id="lan.identity_corrupt", action="export_diagnostics"
    )


@dataclass(frozen=True, slots=True)
class DeviceIdentityV6:
    host_id: str
    device_name: str
    platform: str
    private_key: Ed25519PrivateKey
    public_key: bytes
    fingerprint: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "host_id": self.host_id,
            "device_name": self.device_name,
            "platform": self.platform,
            "public_key": _b64(self.public_key),
            "fingerprint": self.fingerprint,
        }


class LanDirectoryV6:
    """Durable identity, peer pins, permissions, pairing and replay ledger."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LanControlError(
                "LAN 控制面数据目录不可写",
                error_id="lan.database_unavailable",
                action="choose_data_directory",
            ) from exc
        self.database_path = self.root / "lan-control.sqlite3"
        self.identity_path = self.root / "device-identity.json"
        self._lock = threading.RLock()
        self._ensure_schema()
        self.identity = self._load_or_create_identity()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=10,
            isolation_level=None,
            factory=_ClosingConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS lan_meta(
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS lan_peers(
                        host_id TEXT PRIMARY KEY,
                        device_name TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        public_key TEXT NOT NULL,
                        fingerprint TEXT NOT NULL,
                        addresses_json TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        permissions_json TEXT NOT NULL,
                        remote_permissions_json TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL,
                        last_connected_at_ms INTEGER,
                        last_error_id TEXT,
                        revoked_at_ms INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS lan_pairing_sessions(
                        session_id TEXT PRIMARY KEY,
                        code_digest TEXT NOT NULL,
                        pairing_key TEXT NOT NULL,
                        addresses_json TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        expires_at_ms INTEGER NOT NULL,
                        used_at_ms INTEGER,
                        cancelled_at_ms INTEGER,
                        attempts INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS lan_pairing_pending(
                        pending_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        remote_host_id TEXT NOT NULL,
                        remote_device_name TEXT NOT NULL,
                        remote_platform TEXT NOT NULL,
                        remote_public_key TEXT NOT NULL,
                        remote_fingerprint TEXT NOT NULL,
                        remote_address TEXT NOT NULL,
                        remote_port INTEGER NOT NULL,
                        initiator_permissions_json TEXT NOT NULL,
                        local_permissions_json TEXT,
                        status TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        confirmed_at_ms INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS lan_seen_requests(
                        peer_host_id TEXT NOT NULL,
                        request_id TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        expires_at_ms INTEGER NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        PRIMARY KEY(peer_host_id, request_id)
                    );
                    CREATE TABLE IF NOT EXISTS lan_remote_instances(
                        host_id TEXT NOT NULL,
                        project_namespace TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        profiles_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        observed_at_ms INTEGER NOT NULL,
                        PRIMARY KEY(host_id, project_namespace, instance_id)
                    );
                    CREATE TABLE IF NOT EXISTS lan_diagnostics(
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        recorded_at_ms INTEGER NOT NULL,
                        level TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        peer_host_id TEXT,
                        request_id TEXT,
                        correlation_id TEXT,
                        error_id TEXT,
                        details_json TEXT NOT NULL
                    );
                    """
                )
                row = connection.execute(
                    "SELECT value FROM lan_meta WHERE key='schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO lan_meta(key,value) VALUES('schema_version',?)",
                        (str(LAN_SCHEMA_VERSION),),
                    )
                elif int(row["value"]) != LAN_SCHEMA_VERSION:
                    raise LanControlError(
                        "LAN 控制面数据库版本不受支持",
                        error_id="lan.database_version",
                        action="export_diagnostics",
                    )
        except sqlite3.Error as exc:
            raise LanControlError(
                "LAN 控制面数据库不可用",
                error_id="lan.database_unavailable",
                transient="locked" in str(exc).lower(),
                action="retry",
            ) from exc

    def _load_or_create_identity(self) -> DeviceIdentityV6:
        with self._lock:
            if self.identity_path.is_file():
                try:
                    document = json.loads(self.identity_path.read_text(encoding="utf-8-sig"))
                    if int(document.get("schema_version") or 0) != 1:
                        raise ValueError("schema")
                    private = Ed25519PrivateKey.from_private_bytes(
                        _unprotect_private_key(
                            str(document.get("protection") or ""),
                            str(document.get("protected_private_key") or ""),
                        )
                    )
                    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                    if _b64(public) != str(document.get("public_key") or ""):
                        raise ValueError("public key")
                    host_id = str(document.get("host_id") or "")
                    if not host_id.startswith("host_"):
                        raise ValueError("host id")
                    return DeviceIdentityV6(
                        host_id,
                        str(document.get("device_name") or socket.gethostname()),
                        str(document.get("platform") or platform.system().lower()),
                        private,
                        public,
                        _fingerprint(public),
                    )
                except LanControlError:
                    raise
                except Exception as exc:
                    raise LanControlError(
                        "设备身份记录已损坏",
                        error_id="lan.identity_corrupt",
                        action="export_diagnostics",
                    ) from exc
            private = Ed25519PrivateKey.generate()
            raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            protection, protected = _protect_private_key(raw)
            document = {
                "schema_version": 1,
                "host_id": _stable_id("host"),
                "device_name": socket.gethostname() or "EasyCode 设备",
                "platform": platform.system().lower() or "unknown",
                "algorithm": "ed25519",
                "public_key": _b64(public),
                "fingerprint": _fingerprint(public),
                "protection": protection,
                "protected_private_key": protected,
                "created_at": _iso(),
            }
            temporary = self.identity_path.with_name(
                f".{self.identity_path.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                with contextlib.suppress(OSError):
                    os.chmod(temporary, 0o600)
                os.replace(temporary, self.identity_path)
            finally:
                temporary.unlink(missing_ok=True)
            return DeviceIdentityV6(
                str(document["host_id"]),
                str(document["device_name"]),
                str(document["platform"]),
                private,
                public,
                _fingerprint(public),
            )

    def diagnostic(
        self,
        event_type: str,
        *,
        level: str = "info",
        peer_host_id: str = "",
        request_id: str = "",
        correlation_id: str = "",
        error_id: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        safe: dict[str, Any] = {}
        for key, value in dict(details or {}).items():
            if key in {"code", "pairing_key", "private_key", "session_key", "body", "content"}:
                continue
            if isinstance(value, (str, int, float, bool, type(None))):
                safe[str(key)] = value
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO lan_diagnostics(
                           recorded_at_ms,level,event_type,peer_host_id,request_id,
                           correlation_id,error_id,details_json
                       ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        _now_ms(), str(level), str(event_type), str(peer_host_id or "") or None,
                        str(request_id or "") or None, str(correlation_id or "") or None,
                        str(error_id or "") or None, _canonical(safe).decode("utf-8"),
                    ),
                )
        except sqlite3.Error:
            return

    @staticmethod
    def _peer_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "host_id": str(row["host_id"]),
            "device_name": str(row["device_name"]),
            "platform": str(row["platform"]),
            "public_key": str(row["public_key"]),
            "fingerprint": str(row["fingerprint"]),
            "addresses": json.loads(str(row["addresses_json"])),
            "port": int(row["port"]),
            "permissions": json.loads(str(row["permissions_json"])),
            "remote_permissions": json.loads(str(row["remote_permissions_json"])),
            "created_at": _iso(int(row["created_at_ms"])),
            "updated_at": _iso(int(row["updated_at_ms"])),
            "last_connected_at": (
                _iso(int(row["last_connected_at_ms"])) if row["last_connected_at_ms"] else None
            ),
            "last_error_id": str(row["last_error_id"] or ""),
            "revoked": row["revoked_at_ms"] is not None,
            "revoked_at": _iso(int(row["revoked_at_ms"])) if row["revoked_at_ms"] else None,
        }

    def list_peers(self, *, include_revoked: bool = False) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM lan_peers "
                + ("" if include_revoked else "WHERE revoked_at_ms IS NULL ")
                + "ORDER BY device_name,host_id"
            ).fetchall()
        return [self._peer_row(row) for row in rows]

    def peer(self, host_id: str, *, allow_revoked: bool = False) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM lan_peers WHERE host_id=?", (str(host_id),)
            ).fetchone()
        if row is None or (row["revoked_at_ms"] is not None and not allow_revoked):
            raise LanControlError(
                "设备未知、未配对或已撤销", error_id="lan.peer_unknown", action="pair_device"
            )
        return self._peer_row(row)

    def _save_peer(
        self,
        identity: Mapping[str, Any],
        *,
        address: str,
        port: int,
        permissions: Mapping[str, Any] | Iterable[str] | None,
        remote_permissions: Mapping[str, Any] | Iterable[str] | None,
    ) -> dict[str, Any]:
        host_id = str(identity.get("host_id") or "").strip()
        public_key = str(identity.get("public_key") or "")
        public_bytes = _unb64(public_key)
        if len(public_bytes) != 32 or not host_id or host_id == self.identity.host_id:
            raise LanControlError(
                "远端设备身份无效", error_id="lan.identity_invalid", action="cancel_pairing"
            )
        claimed = str(identity.get("fingerprint") or "")
        actual = _fingerprint(public_bytes)
        if claimed and not hmac.compare_digest(claimed, actual):
            raise LanControlError(
                "远端设备公钥指纹不一致",
                error_id="lan.fingerprint_mismatch",
                action="cancel_pairing",
            )
        clean_address = str(address or "").strip()
        if not clean_address or not (1 <= int(port) <= 65535):
            raise LanControlError(
                "远端 LAN 地址无效", error_id="lan.address_invalid", action="enter_manual_address"
            )
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT public_key FROM lan_peers WHERE host_id=?", (host_id,)
            ).fetchone()
            if existing is not None and str(existing["public_key"]) != public_key:
                connection.rollback()
                raise LanControlError(
                    "设备稳定身份的固定公钥发生变化",
                    error_id="lan.pinned_key_mismatch",
                    action="revoke_and_pair_again",
                )
            connection.execute(
                """INSERT INTO lan_peers(
                       host_id,device_name,platform,public_key,fingerprint,addresses_json,port,
                       permissions_json,remote_permissions_json,created_at_ms,updated_at_ms,
                       last_connected_at_ms,last_error_id,revoked_at_ms
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
                   ON CONFLICT(host_id) DO UPDATE SET
                       device_name=excluded.device_name,platform=excluded.platform,
                       addresses_json=excluded.addresses_json,port=excluded.port,
                       permissions_json=excluded.permissions_json,
                       remote_permissions_json=excluded.remote_permissions_json,
                       updated_at_ms=excluded.updated_at_ms,revoked_at_ms=NULL,last_error_id=NULL""",
                (
                    host_id,
                    str(identity.get("device_name") or host_id)[:160],
                    str(identity.get("platform") or "unknown")[:80],
                    public_key,
                    actual,
                    _canonical([clean_address]).decode("utf-8"),
                    int(port),
                    _canonical(_normalize_permissions(permissions)).decode("utf-8"),
                    _canonical(_normalize_permissions(remote_permissions)).decode("utf-8"),
                    now,
                    now,
                    None,
                    None,
                ),
            )
            connection.commit()
        return self.peer(host_id)

    def set_permissions(
        self, host_id: str, permissions: Mapping[str, Any] | Iterable[str]
    ) -> dict[str, Any]:
        normalized = _normalize_permissions(permissions)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE lan_peers SET permissions_json=?,updated_at_ms=?
                   WHERE host_id=? AND revoked_at_ms IS NULL""",
                (_canonical(normalized).decode("utf-8"), _now_ms(), str(host_id)),
            )
            if changed.rowcount != 1:
                connection.rollback()
                raise LanControlError(
                    "设备未知或已撤销", error_id="lan.peer_unknown", action="reload_devices"
                )
            connection.commit()
        self.diagnostic("permission.changed", peer_host_id=host_id, details=normalized)
        return self.peer(host_id)

    def update_remote_permissions(
        self, host_id: str, permissions: Mapping[str, Any] | Iterable[str]
    ) -> dict[str, Any]:
        """Cache the grants the remote host says it currently gives this host."""
        normalized = _normalize_permissions(permissions)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE lan_peers SET remote_permissions_json=?,updated_at_ms=?
                   WHERE host_id=? AND revoked_at_ms IS NULL""",
                (_canonical(normalized).decode("utf-8"), _now_ms(), str(host_id)),
            )
            if changed.rowcount != 1:
                connection.rollback()
                raise LanControlError("设备未知或已撤销", error_id="lan.peer_unknown")
            connection.commit()
        return self.peer(host_id)

    def revoke(self, host_id: str) -> dict[str, Any]:
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE lan_peers SET revoked_at_ms=?,updated_at_ms=?,
                       permissions_json=?,remote_permissions_json=? WHERE host_id=?""",
                (
                    now,
                    now,
                    _canonical(_normalize_permissions(None)).decode("utf-8"),
                    _canonical(_normalize_permissions(None)).decode("utf-8"),
                    str(host_id),
                ),
            )
            if changed.rowcount != 1:
                connection.rollback()
                raise LanControlError(
                    "设备不存在", error_id="lan.peer_unknown", action="reload_devices"
                )
            connection.execute("DELETE FROM lan_seen_requests WHERE peer_host_id=?", (str(host_id),))
            connection.execute("DELETE FROM lan_remote_instances WHERE host_id=?", (str(host_id),))
            connection.commit()
        self.diagnostic("device.revoked", peer_host_id=host_id)
        return {"ok": True, "host_id": str(host_id), "revoked_at": _iso(now)}

    def authorize(
        self,
        host_id: str,
        permission: str,
        *,
        product_id: str = "",
        instance_id: str = "",
    ) -> dict[str, Any]:
        if permission not in PERMISSIONS:
            raise LanControlError(
                "安全协议请求了未知权限", error_id="lan.permission_invalid", action="export_diagnostics"
            )
        peer = self.peer(host_id)
        grants = peer["permissions"]
        if not bool(grants.get(permission)):
            raise LanControlError(
                "此设备未获得当前动作权限",
                error_id=f"lan.permission_{permission}_denied",
                action="review_device_permissions",
            )
        if permission == "remote_start":
            products = set(grants.get("allowed_products") or [])
            instances = set(grants.get("allowed_instances") or [])
            if products and product_id not in products:
                raise LanControlError(
                    "远程启动产品不在授权范围",
                    error_id="lan.remote_product_denied",
                    action="review_device_permissions",
                )
            if instances and instance_id not in instances:
                raise LanControlError(
                    "远程启动实例不在授权范围",
                    error_id="lan.remote_instance_denied",
                    action="review_device_permissions",
                )
        return peer

    def mark_connection(self, host_id: str, *, error_id: str = "") -> None:
        with contextlib.suppress(sqlite3.Error):
            with self._connect() as connection:
                connection.execute(
                    """UPDATE lan_peers SET last_connected_at_ms=?,last_error_id=?,updated_at_ms=?
                       WHERE host_id=? AND revoked_at_ms IS NULL""",
                    (
                        None if error_id else _now_ms(),
                        str(error_id or "") or None,
                        _now_ms(),
                        str(host_id),
                    ),
                )

    def create_pairing_session(
        self,
        *,
        addresses: Iterable[str],
        port: int,
        ttl_ms: int = DEFAULT_PAIRING_TTL_MS,
    ) -> dict[str, Any]:
        ttl = int(ttl_ms)
        if ttl <= 0 or ttl > MAX_PAIRING_TTL_MS:
            raise LanControlError(
                "配对会话有效期超出限制",
                error_id="lan.pairing_ttl_invalid",
                action="fix_request",
            )
        clean_addresses = sorted({str(item).strip() for item in addresses if str(item).strip()})
        if not clean_addresses or not (1 <= int(port) <= 65535):
            raise LanControlError(
                "监听器尚未提供可连接的 LAN 地址",
                error_id="lan.listener_not_running",
                action="start_lan_listener",
            )
        session_id = _stable_id("pair")
        raw = f"{secrets.randbelow(100_000_000):08d}"
        code = f"{raw[:4]}-{raw[4:]}"
        key = _pairing_key(code, session_id)
        created = _now_ms()
        expires = created + ttl
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO lan_pairing_sessions(
                       session_id,code_digest,pairing_key,addresses_json,port,
                       created_at_ms,expires_at_ms,attempts
                   ) VALUES(?,?,?,?,?,?,?,0)""",
                (
                    session_id,
                    hashlib.sha256(raw.encode("ascii")).hexdigest(),
                    _b64(key),
                    _canonical(clean_addresses).decode("utf-8"),
                    int(port),
                    created,
                    expires,
                ),
            )
        payload = {
            "version": LAN_PROTOCOL_VERSION,
            "kind": "easycode_pairing",
            "session_id": session_id,
            "code": code,
            "addresses": clean_addresses,
            "port": int(port),
            **self.identity.public_dict(),
            "expires_at": _iso(expires),
        }
        self.diagnostic("pairing.session_created", correlation_id=session_id)
        return {
            **payload,
            "qr_payload": _canonical(payload).decode("utf-8"),
            "short_fingerprint": self.identity.fingerprint,
        }

    def list_pairing_sessions(self) -> list[dict[str, Any]]:
        now = _now_ms()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT session_id,created_at_ms,expires_at_ms,used_at_ms,cancelled_at_ms,
                          addresses_json,port FROM lan_pairing_sessions
                   WHERE expires_at_ms>? ORDER BY created_at_ms DESC""",
                (now,),
            ).fetchall()
            pending = connection.execute(
                """SELECT pending_id,session_id,remote_host_id,remote_device_name,
                          remote_platform,remote_fingerprint,status,created_at_ms
                   FROM lan_pairing_pending ORDER BY created_at_ms DESC"""
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in pending:
            grouped.setdefault(str(row["session_id"]), []).append(
                {
                    "pending_id": str(row["pending_id"]),
                    "host_id": str(row["remote_host_id"]),
                    "device_name": str(row["remote_device_name"]),
                    "platform": str(row["remote_platform"]),
                    "fingerprint": str(row["remote_fingerprint"]),
                    "status": str(row["status"]),
                    "created_at": _iso(int(row["created_at_ms"])),
                }
            )
        return [
            {
                "session_id": str(row["session_id"]),
                "created_at": _iso(int(row["created_at_ms"])),
                "expires_at": _iso(int(row["expires_at_ms"])),
                "used": row["used_at_ms"] is not None,
                "cancelled": row["cancelled_at_ms"] is not None,
                "addresses": json.loads(str(row["addresses_json"])),
                "port": int(row["port"]),
                "pending": grouped.get(str(row["session_id"]), []),
            }
            for row in rows
        ]

    def cancel_pairing_session(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            changed = connection.execute(
                """UPDATE lan_pairing_sessions SET cancelled_at_ms=?
                   WHERE session_id=? AND used_at_ms IS NULL AND cancelled_at_ms IS NULL""",
                (_now_ms(), str(session_id)),
            )
        if changed.rowcount != 1:
            raise LanControlError(
                "配对会话不存在或已经结束",
                error_id="lan.pairing_session_inactive",
                action="create_pairing_session",
            )
        return {"ok": True, "session_id": str(session_id)}

    def _pairing_session_for_request(
        self,
        session_id: str,
        code_digest: str,
        *,
        count_attempt: bool = True,
    ) -> sqlite3.Row:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if session_id:
                row = connection.execute(
                    "SELECT * FROM lan_pairing_sessions WHERE session_id=?", (session_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT * FROM lan_pairing_sessions WHERE code_digest=?
                       ORDER BY created_at_ms DESC LIMIT 1""",
                    (str(code_digest),),
                ).fetchone()
            if row is not None and count_attempt:
                connection.execute(
                    "UPDATE lan_pairing_sessions SET attempts=attempts+1 WHERE session_id=?",
                    (str(row["session_id"]),),
                )
            connection.commit()
        if (
            row is None
            or row["cancelled_at_ms"] is not None
            or int(row["expires_at_ms"]) <= _now_ms()
            or int(row["attempts"]) >= 12
        ):
            raise LanControlError(
                "配对码错误、过期或尝试次数过多",
                error_id="lan.pairing_code_invalid",
                action="create_pairing_session",
            )
        return row

    def accept_pairing_request(
        self, request: Mapping[str, Any], *, remote_address: str
    ) -> dict[str, Any]:
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            raise LanControlError("配对请求格式无效", error_id="lan.protocol_invalid")
        session = self._pairing_session_for_request(
            str(request.get("session_id") or ""), str(request.get("code_digest") or "")
        )
        key = _unb64(session["pairing_key"])
        expected = hmac.new(key, _canonical(payload), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(request.get("mac"))):
            raise LanControlError(
                "配对码验证失败", error_id="lan.pairing_code_invalid", action="check_pairing_code"
            )
        identity = payload.get("identity")
        if not isinstance(identity, Mapping):
            raise LanControlError("发起设备身份无效", error_id="lan.identity_invalid")
        public = _unb64(identity.get("public_key"))
        if len(public) != 32 or str(identity.get("host_id") or "") == self.identity.host_id:
            raise LanControlError("发起设备身份无效", error_id="lan.identity_invalid")
        actual = _fingerprint(public)
        if not hmac.compare_digest(str(identity.get("fingerprint") or ""), actual):
            raise LanControlError(
                "发起设备公钥指纹不一致", error_id="lan.fingerprint_mismatch", action="reject_pairing"
            )
        pending_id = _stable_id("pending")
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT pending_id,status FROM lan_pairing_pending
                   WHERE session_id=? AND remote_host_id=? ORDER BY created_at_ms DESC LIMIT 1""",
                (str(session["session_id"]), str(identity["host_id"])),
            ).fetchone()
            if existing is not None:
                pending_id = str(existing["pending_id"])
            else:
                connection.execute(
                    """INSERT INTO lan_pairing_pending(
                           pending_id,session_id,remote_host_id,remote_device_name,
                           remote_platform,remote_public_key,remote_fingerprint,
                           remote_address,remote_port,initiator_permissions_json,status,created_at_ms
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pending_id,
                        str(session["session_id"]),
                        str(identity["host_id"]),
                        str(identity.get("device_name") or identity["host_id"])[:160],
                        str(identity.get("platform") or "unknown")[:80],
                        str(identity["public_key"]),
                        actual,
                        str(remote_address),
                        int(payload.get("listener_port") or 0),
                        _canonical(
                            _normalize_permissions(payload.get("initiator_permissions"))
                        ).decode("utf-8"),
                        "pending",
                        now,
                    ),
                )
            connection.commit()
        self.diagnostic(
            "pairing.requested",
            peer_host_id=str(identity["host_id"]),
            correlation_id=pending_id,
        )
        response = {
            "status": "pending_confirmation",
            "session_id": str(session["session_id"]),
            "pending_id": pending_id,
            "receiver": self.identity.public_dict(),
            "fingerprint": self.identity.fingerprint,
            "expires_at": _iso(int(session["expires_at_ms"])),
        }
        response["proof"] = _b64(
            hmac.new(key, _canonical(response), hashlib.sha256).digest()
        )
        return response

    def pairing_status(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            raise LanControlError("配对状态请求无效", error_id="lan.protocol_invalid")
        session = self._pairing_session_for_request(
            str(request.get("session_id") or ""),
            str(request.get("code_digest") or ""),
            count_attempt=False,
        )
        key = _unb64(session["pairing_key"])
        expected = hmac.new(key, _canonical(payload), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(request.get("mac"))):
            raise LanControlError("配对码验证失败", error_id="lan.pairing_code_invalid")
        pending_id = str(payload.get("pending_id") or "")
        host_id = str(payload.get("host_id") or "")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM lan_pairing_pending
                   WHERE pending_id=? AND session_id=? AND remote_host_id=?""",
                (pending_id, str(session["session_id"]), host_id),
            ).fetchone()
        if row is None:
            raise LanControlError(
                "配对确认不存在", error_id="lan.pairing_pending_unknown", action="begin_pairing"
            )
        response: dict[str, Any] = {
            "status": str(row["status"]),
            "session_id": str(session["session_id"]),
            "pending_id": pending_id,
            "receiver": self.identity.public_dict(),
        }
        if str(row["status"]) == "confirmed":
            response["receiver_permissions"] = json.loads(str(row["local_permissions_json"]))
            response["address"] = json.loads(str(session["addresses_json"]))[0]
            response["port"] = int(session["port"])
        response["proof"] = _b64(
            hmac.new(key, _canonical(response), hashlib.sha256).digest()
        )
        return response

    def confirm_pairing(
        self,
        pending_id: str,
        permissions: Mapping[str, Any] | Iterable[str] | None,
    ) -> dict[str, Any]:
        local_permissions = _normalize_permissions(permissions)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT p.*,s.expires_at_ms,s.cancelled_at_ms,s.used_at_ms
                   FROM lan_pairing_pending p JOIN lan_pairing_sessions s USING(session_id)
                   WHERE p.pending_id=?""",
                (str(pending_id),),
            ).fetchone()
            if (
                row is None
                or str(row["status"]) != "pending"
                or row["cancelled_at_ms"] is not None
                or int(row["expires_at_ms"]) <= _now_ms()
            ):
                connection.rollback()
                raise LanControlError(
                    "配对确认已失效",
                    error_id="lan.pairing_session_inactive",
                    action="create_pairing_session",
                )
            remote_identity = {
                "host_id": str(row["remote_host_id"]),
                "device_name": str(row["remote_device_name"]),
                "platform": str(row["remote_platform"]),
                "public_key": str(row["remote_public_key"]),
                "fingerprint": str(row["remote_fingerprint"]),
            }
            initiator_permissions = json.loads(str(row["initiator_permissions_json"]))
            connection.commit()
        peer = self._save_peer(
            remote_identity,
            address=str(row["remote_address"]),
            port=int(row["remote_port"]),
            permissions=local_permissions,
            remote_permissions=initiator_permissions,
        )
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE lan_pairing_pending SET status='confirmed',local_permissions_json=?,
                       confirmed_at_ms=? WHERE pending_id=?""",
                (_canonical(local_permissions).decode("utf-8"), now, str(pending_id)),
            )
            connection.execute(
                "UPDATE lan_pairing_sessions SET used_at_ms=? WHERE session_id=?",
                (now, str(row["session_id"])),
            )
            connection.commit()
        self.diagnostic(
            "pairing.confirmed", peer_host_id=peer["host_id"], correlation_id=str(pending_id)
        )
        return peer

    def seen_response(
        self, peer_host_id: str, request_id: str, request_hash: str
    ) -> dict[str, Any] | None:
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("DELETE FROM lan_seen_requests WHERE expires_at_ms<=?", (now,))
            row = connection.execute(
                "SELECT * FROM lan_seen_requests WHERE peer_host_id=? AND request_id=?",
                (str(peer_host_id), str(request_id)),
            ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise LanControlError(
                "相同请求 ID 的内容发生变化",
                error_id="lan.replay_conflict",
                action="export_diagnostics",
            )
        return json.loads(str(row["response_json"]))

    def remember_response(
        self,
        peer_host_id: str,
        request_id: str,
        request_hash: str,
        response: Mapping[str, Any],
        expires_at_ms: int,
    ) -> None:
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO lan_seen_requests(
                           peer_host_id,request_id,request_hash,response_json,expires_at_ms,created_at_ms
                       ) VALUES(?,?,?,?,?,?)""",
                    (
                        str(peer_host_id), str(request_id), request_hash,
                        _canonical(dict(response)).decode("utf-8"), int(expires_at_ms), _now_ms(),
                    ),
                )
            except sqlite3.IntegrityError:
                existing = self.seen_response(peer_host_id, request_id, request_hash)
                if existing is None:
                    raise

    def update_remote_catalog(self, host_id: str, catalog: Mapping[str, Any]) -> None:
        instances = catalog.get("instances") or []
        if not isinstance(instances, list):
            return
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for raw in instances:
                if not isinstance(raw, Mapping):
                    continue
                project = str(raw.get("project_namespace") or raw.get("product_id") or "").strip()
                instance_id = str(raw.get("instance_id") or "").strip()
                if not project or not instance_id:
                    continue
                connection.execute(
                    """INSERT INTO lan_remote_instances(
                           host_id,project_namespace,instance_id,display_name,product_id,
                           profiles_json,status,observed_at_ms
                       ) VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(host_id,project_namespace,instance_id) DO UPDATE SET
                           display_name=excluded.display_name,product_id=excluded.product_id,
                           profiles_json=excluded.profiles_json,status=excluded.status,
                           observed_at_ms=excluded.observed_at_ms""",
                    (
                        str(host_id), project, instance_id,
                        str(raw.get("display_name") or instance_id)[:160],
                        str(raw.get("product_id") or project),
                        _canonical(raw.get("profiles") or []).decode("utf-8"),
                        str(raw.get("status") or "unknown"), now,
                    ),
                )
            connection.commit()

    def list_remote_instances(self, *, host_id: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM lan_remote_instances"
        params: tuple[Any, ...] = ()
        if host_id:
            query += " WHERE host_id=?"
            params = (str(host_id),)
        query += " ORDER BY host_id,display_name,instance_id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "host_id": str(row["host_id"]),
                "project_namespace": str(row["project_namespace"]),
                "instance_id": str(row["instance_id"]),
                "display_name": str(row["display_name"]),
                "product_id": str(row["product_id"]),
                "profiles": json.loads(str(row["profiles_json"])),
                "status": str(row["status"]),
                "observed_at": _iso(int(row["observed_at_ms"])),
            }
            for row in rows
        ]

    def remote_instance(self, project: str, host_id: str, instance_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM lan_remote_instances
                   WHERE host_id=? AND project_namespace=? AND instance_id=?""",
                (str(host_id), str(project), str(instance_id)),
            ).fetchone()
        if row is None:
            raise LanControlError(
                "远端实例未知；请先取得设备状态",
                error_id="lan.remote_instance_unknown",
                action="refresh_device_status",
            )
        return {
            "host_id": str(row["host_id"]),
            "project_namespace": str(row["project_namespace"]),
            "instance_id": str(row["instance_id"]),
            "display_name": str(row["display_name"]),
            "product_id": str(row["product_id"]),
            "profiles": json.loads(str(row["profiles_json"])),
            "status": str(row["status"]),
            "observed_at": _iso(int(row["observed_at_ms"])),
        }

    def diagnostics(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM lan_diagnostics ORDER BY sequence DESC LIMIT ?",
                (max(1, min(int(limit), 5000)),),
            ).fetchall()
        return [
            {
                "sequence": int(row["sequence"]),
                "recorded_at": _iso(int(row["recorded_at_ms"])),
                "level": str(row["level"]),
                "event_type": str(row["event_type"]),
                "peer_host_id": str(row["peer_host_id"] or ""),
                "request_id": str(row["request_id"] or ""),
                "correlation_id": str(row["correlation_id"] or ""),
                "error_id": str(row["error_id"] or ""),
                "details": json.loads(str(row["details_json"])),
            }
            for row in rows
        ]


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        block = connection.recv(remaining)
        if not block:
            raise LanControlError(
                "LAN 连接在完整帧到达前关闭",
                error_id="lan.connection_interrupted",
                transient=True,
            )
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def _send_frame(connection: socket.socket, value: Mapping[str, Any]) -> None:
    encoded = _canonical(dict(value))
    if len(encoded) > MAX_FRAME_BYTES:
        raise LanControlError("LAN 帧超过大小限制", error_id="lan.frame_too_large")
    connection.sendall(struct.pack("!I", len(encoded)) + encoded)


def _recv_frame(connection: socket.socket) -> dict[str, Any]:
    size = struct.unpack("!I", _recv_exact(connection, 4))[0]
    if size <= 0 or size > MAX_FRAME_BYTES:
        raise LanControlError("LAN 帧长度无效", error_id="lan.protocol_invalid")
    try:
        value = json.loads(_recv_exact(connection, size).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LanControlError("LAN 帧 JSON 无效", error_id="lan.protocol_invalid") from exc
    if not isinstance(value, dict):
        raise LanControlError("LAN 帧必须是对象", error_id="lan.protocol_invalid")
    return value


def _hello_signing_bytes(value: Mapping[str, Any]) -> bytes:
    return _canonical({key: item for key, item in value.items() if key != "signature"})


@dataclass(slots=True)
class _SessionKeys:
    send_key: bytes
    receive_key: bytes
    session_id: str


class LanControlPlaneV6:
    """True socket server/client around a shared durable LAN directory."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        bind_host: str = "0.0.0.0",
        port: int = 0,
        advertised_addresses: Iterable[str] | None = None,
    ) -> None:
        self.directory = LanDirectoryV6(root)
        self.bind_host = str(bind_host)
        self.requested_port = int(port)
        self._advertised_addresses = list(advertised_addresses or [])
        self._handlers: dict[
            str, Callable[[dict[str, Any], dict[str, Any]], Mapping[str, Any]]
        ] = {}
        self._tick_handlers: list[Callable[[], Any]] = []
        self._status_provider: Callable[[], Mapping[str, Any]] = lambda: {"instances": []}
        self._tcp: socket.socket | None = None
        self._udp: socket.socket | None = None
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._clients: set[socket.socket] = set()
        self._client_lock = threading.RLock()
        self.port = 0

    @property
    def identity(self) -> DeviceIdentityV6:
        return self.directory.identity

    def set_status_provider(self, provider: Callable[[], Mapping[str, Any]]) -> None:
        self._status_provider = provider

    def register_handler(
        self,
        request_type: str,
        handler: Callable[[dict[str, Any], dict[str, Any]], Mapping[str, Any]],
    ) -> None:
        clean = str(request_type or "").strip()
        if not clean or clean in {"status.query"}:
            raise LanControlError("协议处理器名称无效", error_id="lan.handler_invalid")
        self._handlers[clean] = handler

    def register_tick_handler(self, handler: Callable[[], Any]) -> None:
        if handler not in self._tick_handlers:
            self._tick_handlers.append(handler)

    def _local_addresses(self) -> list[str]:
        values = {item for item in self._advertised_addresses if item}
        if self.bind_host not in {"0.0.0.0", "::", ""}:
            values.add(self.bind_host)
        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                address = str(item[4][0])
                if address and not address.startswith("169.254."):
                    values.add(address)
        except socket.gaierror:
            pass
        if not values:
            values.add("127.0.0.1")
        return sorted(values)

    def start(self) -> dict[str, Any]:
        if self._tcp is not None:
            return self.status()
        self._stop.clear()
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            tcp.bind((self.bind_host, self.requested_port))
            tcp.listen(32)
            tcp.settimeout(0.25)
            self.port = int(tcp.getsockname()[1])
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind((self.bind_host, self.port))
            udp.settimeout(0.25)
        except OSError as exc:
            tcp.close()
            raise LanControlError(
                "LAN 监听器无法绑定地址或端口",
                error_id="lan.listener_bind_failed",
                action="check_firewall_or_port",
            ) from exc
        self._tcp, self._udp = tcp, udp
        self._threads = [
            threading.Thread(target=self._accept_loop, name="easycode-lan-tcp", daemon=True),
            threading.Thread(target=self._discovery_loop, name="easycode-lan-udp", daemon=True),
            threading.Thread(
                target=self._maintenance_loop,
                name="easycode-lan-maintenance",
                daemon=True,
            ),
        ]
        for thread in self._threads:
            thread.start()
        self.directory.diagnostic("listener.started", details={"port": self.port})
        return self.status()

    def stop(self) -> None:
        self._stop.set()
        for sock in (self._tcp, self._udp):
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
        self._tcp = self._udp = None
        with self._client_lock:
            for client in list(self._clients):
                with contextlib.suppress(OSError):
                    client.shutdown(socket.SHUT_RDWR)
                    client.close()
        for thread in list(self._threads):
            thread.join(timeout=2.0)
        self._threads.clear()
        self.directory.diagnostic("listener.stopped")

    close = stop

    def status(self) -> dict[str, Any]:
        peers = self.directory.list_peers()
        now = _now_ms()
        for peer in peers:
            seen = peer.get("last_connected_at")
            peer["connection_state"] = "unknown"
            if seen:
                try:
                    milliseconds = int(
                        datetime.fromisoformat(str(seen).replace("Z", "+00:00")).timestamp() * 1000
                    )
                    peer["connection_state"] = "online" if now - milliseconds < 30_000 else "offline"
                except ValueError:
                    pass
        return {
            "available": True,
            "running": self._tcp is not None,
            "identity": self.identity.public_dict(),
            "addresses": self._local_addresses() if self._tcp is not None else [],
            "port": self.port,
            "permissions": sorted(PERMISSIONS),
            "paired_devices": peers,
            "remote_instances": self.directory.list_remote_instances(),
            "pairing_sessions": self.directory.list_pairing_sessions(),
            "cloud_relay": {"available": False, "state": "not_in_product_scope"},
        }

    def _accept_loop(self) -> None:
        assert self._tcp is not None
        while not self._stop.is_set():
            try:
                client, address = self._tcp.accept()
                client.settimeout(10.0)
            except socket.timeout:
                continue
            except OSError:
                break
            with self._client_lock:
                self._clients.add(client)
            thread = threading.Thread(
                target=self._serve_client,
                args=(client, str(address[0])),
                name="easycode-lan-client",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def _maintenance_loop(self) -> None:
        while not self._stop.wait(0.5):
            for handler in list(self._tick_handlers):
                try:
                    handler()
                except Exception:
                    self.directory.diagnostic(
                        "maintenance.failed",
                        level="warning",
                        error_id="lan.maintenance_failed",
                    )

    def _discovery_loop(self) -> None:
        assert self._udp is not None
        while not self._stop.is_set():
            try:
                data, address = self._udp.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                request = json.loads(data.decode("utf-8"))
                if request.get("magic") != DISCOVERY_MAGIC or int(request.get("version") or 0) != 1:
                    continue
                response = {
                    "magic": DISCOVERY_MAGIC,
                    "version": 1,
                    **self.identity.public_dict(),
                    "address": str(address[0]) if self.bind_host == "0.0.0.0" else self.bind_host,
                    "port": self.port,
                    "pairable": bool(self.directory.list_pairing_sessions()),
                }
                self._udp.sendto(_canonical(response), address)
            except (ValueError, OSError, UnicodeError, AttributeError):
                continue

    def discover(
        self,
        *,
        timeout_seconds: float = 0.5,
        addresses: Iterable[str] | None = None,
        port: int | None = None,
    ) -> list[dict[str, Any]]:
        targets = list(addresses or ["255.255.255.255"])
        target_port = int(port or self.port or self.requested_port)
        if not target_port:
            raise LanControlError(
                "发现需要已知监听端口；请使用手工地址回退",
                error_id="lan.discovery_port_unknown",
                action="enter_manual_address",
            )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(max(0.05, float(timeout_seconds)))
        request = _canonical({"magic": DISCOVERY_MAGIC, "version": 1, "nonce": _b64(secrets.token_bytes(12))})
        try:
            for address in targets:
                with contextlib.suppress(OSError):
                    sock.sendto(request, (str(address), target_port))
            deadline = time.monotonic() + max(0.05, float(timeout_seconds))
            found: dict[str, dict[str, Any]] = {}
            while time.monotonic() < deadline:
                try:
                    data, source = sock.recvfrom(8192)
                except socket.timeout:
                    break
                value = json.loads(data.decode("utf-8"))
                if value.get("magic") != DISCOVERY_MAGIC:
                    continue
                value["address"] = str(source[0])
                found[str(value.get("host_id") or source)] = value
            return list(found.values())
        finally:
            sock.close()

    def create_pairing_session(self, ttl_ms: int = DEFAULT_PAIRING_TTL_MS) -> dict[str, Any]:
        if self._tcp is None:
            raise LanControlError(
                "请先启动 LAN 监听器",
                error_id="lan.listener_not_running",
                action="start_lan_listener",
            )
        return self.directory.create_pairing_session(
            addresses=self._local_addresses(), port=self.port, ttl_ms=ttl_ms
        )

    @staticmethod
    def _pairing_request(
        *,
        message_type: str,
        session_id: str,
        code: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        raw = "".join(ch for ch in str(code).upper() if ch.isalnum())
        key = _pairing_key(code, session_id)
        return {
            "type": message_type,
            "version": 1,
            "session_id": session_id,
            "code_digest": hashlib.sha256(raw.encode("ascii")).hexdigest(),
            "payload": dict(payload),
            "mac": _b64(hmac.new(key, _canonical(payload), hashlib.sha256).digest()),
        }

    @staticmethod
    def _plain_request(address: str, port: int, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            with socket.create_connection((str(address), int(port)), timeout=5.0) as connection:
                connection.settimeout(10.0)
                _send_frame(connection, request)
                response = _recv_frame(connection)
        except (OSError, socket.timeout) as exc:
            raise LanControlError(
                "无法连接配对设备；可检查防火墙或使用手工地址",
                error_id="lan.device_unreachable",
                transient=True,
                action="check_firewall_or_address",
            ) from exc
        if not response.get("ok"):
            error = response.get("error") or {}
            raise LanControlError(
                str(error.get("message") or "配对请求失败"),
                error_id=str(error.get("error_id") or "lan.pairing_failed"),
                transient=bool(error.get("transient")),
                action=str(error.get("action") or "retry"),
            )
        return dict(response.get("result") or {})

    def begin_pairing(
        self,
        *,
        address: str,
        port: int,
        code: str,
        session_id: str,
        permissions: Mapping[str, Any] | Iterable[str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "identity": self.identity.public_dict(),
            "listener_port": int(self.port or 0),
            "initiator_permissions": _normalize_permissions(permissions),
            "nonce": _b64(secrets.token_bytes(16)),
            "timestamp_ms": _now_ms(),
        }
        response = self._plain_request(
            address,
            port,
            self._pairing_request(
                message_type="pair.request", session_id=session_id, code=code, payload=payload
            ),
        )
        self._verify_pairing_response(
            response, session_id=session_id, code=code
        )
        return {
            **response,
            "address": str(address),
            "port": int(port),
            "code": str(code),
            "initiator_permissions": payload["initiator_permissions"],
        }

    def complete_pairing(
        self,
        pairing: Mapping[str, Any],
        *,
        expected_fingerprint: str = "",
    ) -> dict[str, Any]:
        payload = {
            "pending_id": str(pairing.get("pending_id") or ""),
            "host_id": self.identity.host_id,
            "nonce": _b64(secrets.token_bytes(16)),
            "timestamp_ms": _now_ms(),
        }
        response = self._plain_request(
            str(pairing.get("address") or ""),
            int(pairing.get("port") or 0),
            self._pairing_request(
                message_type="pair.status",
                session_id=str(pairing.get("session_id") or ""),
                code=str(pairing.get("code") or ""),
                payload=payload,
            ),
        )
        self._verify_pairing_response(
            response,
            session_id=str(pairing.get("session_id") or ""),
            code=str(pairing.get("code") or ""),
        )
        if response.get("status") != "confirmed":
            return response
        receiver = response.get("receiver")
        if not isinstance(receiver, Mapping):
            raise LanControlError("配对确认缺少设备身份", error_id="lan.protocol_invalid")
        actual = str(receiver.get("fingerprint") or "")
        if expected_fingerprint and not hmac.compare_digest(expected_fingerprint, actual):
            raise LanControlError(
                "用户确认的设备指纹与连接设备不一致",
                error_id="lan.fingerprint_mismatch",
                action="cancel_pairing",
            )
        peer = self.directory._save_peer(
            receiver,
            address=str(pairing.get("address") or ""),
            port=int(pairing.get("port") or 0),
            permissions=pairing.get("initiator_permissions"),
            remote_permissions=response.get("receiver_permissions"),
        )
        self.directory.diagnostic(
            "pairing.completed",
            peer_host_id=peer["host_id"],
            correlation_id=str(pairing.get("pending_id") or ""),
        )
        return peer

    @staticmethod
    def _verify_pairing_response(
        response: Mapping[str, Any], *, session_id: str, code: str
    ) -> None:
        proof = _unb64(response.get("proof"))
        unsigned = {key: value for key, value in response.items() if key != "proof"}
        expected = hmac.new(
            _pairing_key(code, session_id),
            _canonical(unsigned),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(proof, expected):
            raise LanControlError(
                "配对应答认证失败",
                error_id="lan.authentication_failed",
                action="cancel_pairing",
            )

    def _serve_client(self, connection: socket.socket, remote_address: str) -> None:
        try:
            first = _recv_frame(connection)
            message_type = str(first.get("type") or "")
            if message_type == "pair.request":
                result = self.directory.accept_pairing_request(first, remote_address=remote_address)
                _send_frame(connection, {"ok": True, "result": result})
                return
            if message_type == "pair.status":
                result = self.directory.pairing_status(first)
                _send_frame(connection, {"ok": True, "result": result})
                return
            if message_type != "secure.hello":
                raise LanControlError("未知 LAN 协议入口", error_id="lan.protocol_invalid")
            peer, keys = self._server_handshake(connection, first)
            encrypted = _recv_frame(connection)
            request = self._decrypt(keys.receive_key, keys.session_id, encrypted, expected_sequence=1)
            response = self._handle_secure_request(peer, request)
            _send_frame(
                connection,
                self._encrypt(keys.send_key, keys.session_id, response, sequence=1),
            )
            self.directory.mark_connection(peer["host_id"])
        except LanControlError as exc:
            self.directory.diagnostic(
                "connection.failed",
                level="warning",
                error_id=exc.error_id,
                details={"remote_address": remote_address, "transient": exc.transient},
            )
            with contextlib.suppress(Exception):
                _send_frame(
                    connection,
                    {
                        "ok": False,
                        "error": {
                            "error_id": exc.error_id,
                            "message": str(exc),
                            "transient": exc.transient,
                            "action": exc.action,
                        },
                    },
                )
        except Exception:
            self.directory.diagnostic(
                "connection.failed", level="error", error_id="lan.internal_error"
            )
        finally:
            with self._client_lock:
                self._clients.discard(connection)
            with contextlib.suppress(OSError):
                connection.close()

    def _server_handshake(
        self, connection: socket.socket, hello: Mapping[str, Any]
    ) -> tuple[dict[str, Any], _SessionKeys]:
        if int(hello.get("version") or 0) != LAN_PROTOCOL_VERSION:
            raise LanControlError("LAN 协议版本不兼容", error_id="lan.protocol_version")
        timestamp = int(hello.get("timestamp_ms") or 0)
        if abs(_now_ms() - timestamp) > MAX_CLOCK_SKEW_MS:
            raise LanControlError("安全握手已过期", error_id="lan.handshake_expired")
        peer = self.directory.peer(str(hello.get("host_id") or ""))
        if str(hello.get("public_key") or "") != peer["public_key"]:
            raise LanControlError(
                "连接设备公钥与配对固定值不一致",
                error_id="lan.pinned_key_mismatch",
                action="revoke_and_pair_again",
            )
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(peer["public_key"])).verify(
                _unb64(hello.get("signature")), _hello_signing_bytes(hello)
            )
        except (InvalidSignature, ValueError) as exc:
            raise LanControlError("设备握手签名无效", error_id="lan.authentication_failed") from exc
        client_nonce = _unb64(hello.get("nonce"))
        client_ephemeral = _unb64(hello.get("ephemeral_key"))
        if len(client_nonce) != 24 or len(client_ephemeral) != 32:
            raise LanControlError("安全握手字段无效", error_id="lan.protocol_invalid")
        ephemeral = X25519PrivateKey.generate()
        server_ephemeral = ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        server_nonce = secrets.token_bytes(24)
        response: dict[str, Any] = {
            "type": "secure.hello.reply",
            "version": LAN_PROTOCOL_VERSION,
            "host_id": self.identity.host_id,
            "public_key": _b64(self.identity.public_key),
            "ephemeral_key": _b64(server_ephemeral),
            "nonce": _b64(server_nonce),
            "client_nonce": _b64(client_nonce),
            "timestamp_ms": _now_ms(),
            "transcript_hash": _request_hash(hello),
        }
        response["signature"] = _b64(
            self.identity.private_key.sign(_hello_signing_bytes(response))
        )
        _send_frame(connection, response)
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(client_ephemeral))
        material = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=hashlib.sha256(client_nonce + server_nonce).digest(),
            info=(
                f"easycode-lan-v6|{peer['host_id']}|{self.identity.host_id}"
            ).encode("utf-8"),
        ).derive(shared)
        session_id = hashlib.sha256(client_nonce + server_nonce + shared).hexdigest()[:32]
        return peer, _SessionKeys(material[32:], material[:32], session_id)

    def _client_handshake(self, connection: socket.socket, peer: Mapping[str, Any]) -> _SessionKeys:
        ephemeral = X25519PrivateKey.generate()
        ephemeral_public = ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        client_nonce = secrets.token_bytes(24)
        hello: dict[str, Any] = {
            "type": "secure.hello",
            "version": LAN_PROTOCOL_VERSION,
            "host_id": self.identity.host_id,
            "public_key": _b64(self.identity.public_key),
            "ephemeral_key": _b64(ephemeral_public),
            "nonce": _b64(client_nonce),
            "timestamp_ms": _now_ms(),
        }
        hello["signature"] = _b64(self.identity.private_key.sign(_hello_signing_bytes(hello)))
        _send_frame(connection, hello)
        response = _recv_frame(connection)
        if response.get("type") != "secure.hello.reply":
            error = response.get("error") or {}
            raise LanControlError(
                str(error.get("message") or "安全握手失败"),
                error_id=str(error.get("error_id") or "lan.authentication_failed"),
            )
        if (
            str(response.get("host_id") or "") != peer["host_id"]
            or str(response.get("public_key") or "") != peer["public_key"]
            or str(response.get("client_nonce") or "") != _b64(client_nonce)
            or str(response.get("transcript_hash") or "") != _request_hash(hello)
        ):
            raise LanControlError(
                "连接设备身份或握手上下文不匹配",
                error_id="lan.pinned_key_mismatch",
                action="revoke_and_pair_again",
            )
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(peer["public_key"])).verify(
                _unb64(response.get("signature")), _hello_signing_bytes(response)
            )
        except (InvalidSignature, ValueError) as exc:
            raise LanControlError("设备握手签名无效", error_id="lan.authentication_failed") from exc
        server_nonce = _unb64(response.get("nonce"))
        server_ephemeral = _unb64(response.get("ephemeral_key"))
        if len(server_nonce) != 24 or len(server_ephemeral) != 32:
            raise LanControlError("安全握手字段无效", error_id="lan.protocol_invalid")
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(server_ephemeral))
        material = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=hashlib.sha256(client_nonce + server_nonce).digest(),
            info=(f"easycode-lan-v6|{self.identity.host_id}|{peer['host_id']}").encode("utf-8"),
        ).derive(shared)
        session_id = hashlib.sha256(client_nonce + server_nonce + shared).hexdigest()[:32]
        return _SessionKeys(material[:32], material[32:], session_id)

    @staticmethod
    def _encrypt(
        key: bytes, session_id: str, payload: Mapping[str, Any], *, sequence: int
    ) -> dict[str, Any]:
        nonce = hashlib.sha256((session_id + ":nonce").encode("ascii")).digest()[:4] + int(
            sequence
        ).to_bytes(8, "big")
        aad = f"easycode-lan-v6|{session_id}|{sequence}".encode("ascii")
        ciphertext = ChaCha20Poly1305(key).encrypt(nonce, _canonical(dict(payload)), aad)
        return {
            "type": "secure.frame",
            "session_id": session_id,
            "sequence": int(sequence),
            "ciphertext": _b64(ciphertext),
        }

    @staticmethod
    def _decrypt(
        key: bytes,
        session_id: str,
        frame: Mapping[str, Any],
        *,
        expected_sequence: int,
    ) -> dict[str, Any]:
        if (
            frame.get("type") != "secure.frame"
            or str(frame.get("session_id") or "") != session_id
            or int(frame.get("sequence") or 0) != expected_sequence
        ):
            raise LanControlError("安全帧序号或会话无效", error_id="lan.replay_detected")
        nonce = hashlib.sha256((session_id + ":nonce").encode("ascii")).digest()[:4] + int(
            expected_sequence
        ).to_bytes(8, "big")
        aad = f"easycode-lan-v6|{session_id}|{expected_sequence}".encode("ascii")
        try:
            raw = ChaCha20Poly1305(key).decrypt(nonce, _unb64(frame.get("ciphertext")), aad)
            value = json.loads(raw.decode("utf-8"))
        except (InvalidTag, UnicodeError, json.JSONDecodeError) as exc:
            raise LanControlError(
                "安全帧认证失败", error_id="lan.authentication_failed", action="export_diagnostics"
            ) from exc
        if not isinstance(value, dict):
            raise LanControlError("安全帧正文无效", error_id="lan.protocol_invalid")
        return value

    @staticmethod
    def _permission_for(request_type: str) -> str | None:
        if request_type == "permissions.query":
            return None
        if request_type.startswith("message."):
            return "messages"
        if request_type == "status.query" or request_type == "dispatch.status":
            return "status"
        if request_type == "dispatch.start":
            return "remote_start"
        raise LanControlError(
            "安全通道请求类型未知", error_id="lan.request_unknown", action="update_easycode"
        )

    def _handle_secure_request(
        self, peer: dict[str, Any], request: Mapping[str, Any]
    ) -> dict[str, Any]:
        request_id = str(request.get("request_id") or "")
        request_type = str(request.get("request_type") or "")
        timestamp = int(request.get("timestamp_ms") or 0)
        expires = int(request.get("expires_at_ms") or 0)
        if not request_id or not request_type or timestamp > _now_ms() + MAX_CLOCK_SKEW_MS:
            raise LanControlError("安全请求字段无效", error_id="lan.protocol_invalid")
        if expires <= _now_ms() or expires - timestamp > MAX_REQUEST_TTL_MS:
            raise LanControlError("安全请求已经过期", error_id="lan.request_expired")
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            raise LanControlError("安全请求正文无效", error_id="lan.protocol_invalid")
        permission = self._permission_for(request_type)
        if permission is not None:
            self.directory.authorize(
                peer["host_id"],
                permission,
                product_id=str(payload.get("product_id") or ""),
                instance_id=str(payload.get("instance_id") or ""),
            )
        # Idempotency is keyed to the semantic operation, not the fresh transport
        # timestamp.  A lost response can therefore be retried with the same
        # request_id without executing a second message import or dispatch.
        request_hash = _request_hash(
            {"request_type": request_type, "payload": dict(payload)}
        )
        cached = self.directory.seen_response(peer["host_id"], request_id, request_hash)
        if cached is not None:
            return cached
        try:
            if request_type == "permissions.query":
                result = {"permissions": dict(peer["permissions"])}
            elif request_type == "status.query":
                result = dict(self._status_provider())
            else:
                handler = self._handlers.get(request_type)
                if handler is None:
                    raise LanControlError(
                        "当前宿主没有接入该安全协议处理器",
                        error_id="lan.handler_unavailable",
                        transient=True,
                    )
                result = dict(handler(peer, dict(payload)))
            response: dict[str, Any] = {
                "ok": True,
                "request_id": request_id,
                "request_type": request_type,
                "result": result,
                "responded_at_ms": _now_ms(),
            }
        except LanControlError as exc:
            response = {
                "ok": False,
                "request_id": request_id,
                "request_type": request_type,
                "error": {
                    "error_id": exc.error_id,
                    "message": str(exc),
                    "transient": exc.transient,
                    "action": exc.action,
                },
                "responded_at_ms": _now_ms(),
            }
        self.directory.remember_response(
            peer["host_id"], request_id, request_hash, response, expires
        )
        self.directory.diagnostic(
            "request.handled",
            peer_host_id=peer["host_id"],
            request_id=request_id,
            correlation_id=str(payload.get("dispatch_id") or payload.get("message_id") or ""),
            details={"request_type": request_type, "ok": bool(response.get("ok"))},
        )
        return response

    def secure_request(
        self,
        host_id: str,
        request_type: str,
        payload: Mapping[str, Any],
        *,
        request_id: str = "",
        ttl_ms: int = 30_000,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        peer = self.directory.peer(host_id)
        permission = self._permission_for(request_type)
        remote = peer["remote_permissions"]
        if permission is not None and not bool(remote.get(permission)):
            raise LanControlError(
                "远端设备没有授予当前动作权限",
                error_id=f"lan.remote_permission_{permission}_denied",
                action="ask_remote_to_grant_permission",
            )
        if permission == "remote_start":
            products = set(remote.get("allowed_products") or [])
            instances = set(remote.get("allowed_instances") or [])
            if products and str(payload.get("product_id") or "") not in products:
                raise LanControlError(
                    "远端授权不包含此产品", error_id="lan.remote_product_denied"
                )
            if instances and str(payload.get("instance_id") or "") not in instances:
                raise LanControlError(
                    "远端授权不包含此实例", error_id="lan.remote_instance_denied"
                )
        ttl = max(1, min(int(ttl_ms), MAX_REQUEST_TTL_MS))
        now = _now_ms()
        request = {
            "request_id": str(request_id or _stable_id("request")),
            "request_type": str(request_type),
            "timestamp_ms": now,
            "expires_at_ms": now + ttl,
            "payload": dict(payload),
        }
        failures: list[LanControlError] = []
        for address in peer["addresses"]:
            try:
                with socket.create_connection(
                    (str(address), int(peer["port"])), timeout=float(timeout_seconds)
                ) as connection:
                    connection.settimeout(float(timeout_seconds))
                    keys = self._client_handshake(connection, peer)
                    frame = self._encrypt(keys.send_key, keys.session_id, request, sequence=1)
                    _send_frame(connection, frame)
                    encrypted = _recv_frame(connection)
                    if encrypted.get("type") != "secure.frame":
                        error = encrypted.get("error") or {}
                        raise LanControlError(
                            str(error.get("message") or "远端安全请求失败"),
                            error_id=str(error.get("error_id") or "lan.request_failed"),
                        )
                    response = self._decrypt(
                        keys.receive_key, keys.session_id, encrypted, expected_sequence=1
                    )
                self.directory.mark_connection(host_id)
                if not response.get("ok"):
                    error = response.get("error") or {}
                    raise LanControlError(
                        str(error.get("message") or "远端拒绝请求"),
                        error_id=str(error.get("error_id") or "lan.request_failed"),
                        transient=bool(error.get("transient")),
                        action=str(error.get("action") or "retry"),
                    )
                result = dict(response.get("result") or {})
                if request_type == "permissions.query":
                    self.directory.update_remote_permissions(
                        host_id, result.get("permissions") or {}
                    )
                elif request_type == "status.query":
                    self.directory.update_remote_catalog(host_id, result)
                self.directory.diagnostic(
                    "request.completed",
                    peer_host_id=host_id,
                    request_id=str(request["request_id"]),
                    correlation_id=str(payload.get("dispatch_id") or payload.get("message_id") or ""),
                    details={"request_type": request_type},
                )
                return result
            except LanControlError as exc:
                failures.append(exc)
                if not exc.transient and exc.error_id not in {
                    "lan.device_unreachable", "lan.connection_interrupted"
                }:
                    self.directory.mark_connection(host_id, error_id=exc.error_id)
                    raise
            except (OSError, socket.timeout):
                failures.append(
                    LanControlError(
                        "配对设备当前不可达",
                        error_id="lan.device_unreachable",
                        transient=True,
                        action="check_lan_or_firewall",
                    )
                )
                self.directory.mark_connection(host_id, error_id="lan.device_unreachable")
        failure = failures[-1] if failures else LanControlError("配对设备没有可用地址")
        self.directory.mark_connection(host_id, error_id=failure.error_id)
        raise failure

    def refresh_peer_status(self, host_id: str) -> dict[str, Any]:
        self.secure_request(host_id, "permissions.query", {}, ttl_ms=15_000)
        return self.secure_request(host_id, "status.query", {}, ttl_ms=15_000)


__all__ = [
    "DEFAULT_PAIRING_TTL_MS",
    "DeviceIdentityV6",
    "LanControlError",
    "LanControlPlaneV6",
    "LanDirectoryV6",
    "PERMISSIONS",
]
