"""Durable local and authenticated-LAN messaging for format-6 runtimes.

The database is deliberately outside the project tree.  ProgramDocument only
stores stable ``instance_ref`` values; queue state belongs to the runtime data
directory and is shared by isolated execution workers.

LAN copies use the same durable per-recipient state machine after an explicit
device pairing. Cooperative listen scheduling lives in ``runtime.py`` and uses
the private candidate/claim methods below so condition checks never acknowledge
an unread message.
"""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lan_control_v6 import LanControlError, LanControlPlaneV6

MESSAGE_SCHEMA_VERSION = 1
DEFAULT_TTL_MS = 300_000
MAX_TTL_MS = 7 * 24 * 60 * 60 * 1000
MAX_RECIPIENTS = 64
MAX_CONTENT_BYTES = 256 * 1024
MAX_CONTENT_DEPTH = 64
MAX_CONTENT_ITEMS = 10_000
POLL_INTERVAL_SECONDS = 0.05

_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_OPCODES = frozenset({
    "message.send",
    "message.wait_receive",
    "message.wait_read",
    "message.cancel",
})


class MessageRuntimeError(RuntimeError):
    """Structured error propagated through the normal RuntimeFailure path."""

    def __init__(
        self,
        message: str,
        *,
        error_id: str = "message.transport_unavailable",
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = transient


class _ClosingMessageConnection(sqlite3.Connection):
    """Release SQLite handles promptly so Windows restart tests are deterministic."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


def _translate_sqlite_errors(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MessageRuntimeError:
            raise
        except sqlite3.Error as exc:
            text = str(exc).lower()
            transient = "locked" in text or "busy" in text or "temporarily" in text
            raise MessageRuntimeError(
                "消息本地队列暂时不可用" if transient else "消息本地队列读写失败",
                error_id="message.transport_unavailable",
                transient=transient,
            ) from exc

    return wrapped


def default_runtime_data_directory() -> Path:
    override = os.environ.get("EASYCODE_VNEXT_RUNTIME_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    root = Path(local_app_data) if local_app_data else Path.home() / ".easycode"
    return root / "EasyCode" / "Runtime" / "v6"


def default_message_database_path() -> Path:
    return default_runtime_data_directory() / "messages.sqlite3"


def default_lan_data_directory() -> Path:
    override = os.environ.get("EASYCODE_LAN_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    runtime_override = os.environ.get("EASYCODE_VNEXT_RUNTIME_DATA_DIR", "").strip()
    if runtime_override:
        return Path(runtime_override).expanduser().resolve() / "lan"
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    root = Path(local_app_data) if local_app_data else Path.home() / ".easycode"
    return (root / "EasyCode" / "PlayerHub" / "lan").resolve()


def program_uses_messages(ecir: dict[str, Any]) -> bool:
    """Return whether an ECIR closure contains a verified message opcode."""

    def visit(instructions: list[dict[str, Any]]) -> bool:
        for instruction in instructions:
            if str(instruction.get("opcode") or "").startswith("message.") or str(
                instruction.get("opcode") or ""
            ) == "control.listen":
                return True
            arguments = instruction.get("arguments") or {}
            nested: list[list[dict[str, Any]]] = []
            for name in ("then", "otherwise", "body", "finally"):
                value = arguments.get(name)
                if isinstance(value, list):
                    nested.append(value)
            nested.extend(
                branch.get("body") or []
                for branch in arguments.get("additional_branches") or []
                if isinstance(branch, dict)
            )
            nested.extend(
                clause.get("body") or []
                for clause in arguments.get("catches") or []
                if isinstance(clause, dict)
            )
            if any(visit(list(block)) for block in nested):
                return True
        return False

    return any(
        visit(list(definition.get("instructions") or []))
        for definition in ecir.get("functions") or []
        if isinstance(definition, dict)
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _iso_timestamp(milliseconds: int) -> str:
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat(
        timespec="milliseconds"
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _display_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def _encode_reference_part(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_reference_part(value: str) -> str:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise MessageRuntimeError(
            "实例引用编码无效",
            error_id="message.instance_unknown",
        ) from exc


def _validate_stable_id(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not _STABLE_ID.fullmatch(normalized):
        raise MessageRuntimeError(
            f"{label}必须是 1-128 位稳定标识",
            error_id="message.instance_invalid",
        )
    return normalized


def _validate_project_namespace(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 256 or any(ord(ch) < 32 for ch in normalized):
        raise MessageRuntimeError(
            "消息运行缺少有效项目命名空间",
            error_id="message.project_invalid",
        )
    return normalized


def _validate_display_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 160 or any(ord(ch) < 32 for ch in normalized):
        raise MessageRuntimeError(
            "实例显示名不能为空且不能包含控制字符",
            error_id="message.instance_invalid",
        )
    return normalized


def _validate_message_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or len(name) > 160 or any(ord(ch) < 32 for ch in name):
        raise MessageRuntimeError(
            "消息名称不能为空且不能包含控制字符",
            error_id="message.content_invalid",
        )
    return name


def _validate_message_value(
    value: Any,
    *,
    depth: int = 0,
    counter: list[int] | None = None,
) -> Any:
    """Validate and return a deep by-value copy of the message payload."""

    if counter is None:
        counter = [0]
    counter[0] += 1
    if depth > MAX_CONTENT_DEPTH or counter[0] > MAX_CONTENT_ITEMS:
        raise MessageRuntimeError(
            "消息内容层级或项目数量超过限制",
            error_id="message.content_invalid",
        )
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if value < -(2**63) or value > 2**63 - 1:
            raise MessageRuntimeError(
                "消息整数超出 int64 范围",
                error_id="message.content_invalid",
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MessageRuntimeError(
                "消息内容不能包含 NaN 或无穷数",
                error_id="message.content_invalid",
            )
        return value
    if isinstance(value, (list, tuple)):
        return [
            _validate_message_value(item, depth=depth + 1, counter=counter)
            for item in value
        ]
    if isinstance(value, dict):
        copied: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise MessageRuntimeError(
                    "消息字典的键必须是文本",
                    error_id="message.content_invalid",
                )
            copied[key] = _validate_message_value(
                item,
                depth=depth + 1,
                counter=counter,
            )
        return copied
    raise MessageRuntimeError(
        f"消息内容不支持进程内对象类型：{type(value).__name__}",
        error_id="message.content_invalid",
    )


class MessageRuntimeV6:
    """SQLite-backed local/LAN message transport shared by worker processes."""

    def __init__(
        self,
        database_path: str | os.PathLike[str] | None = None,
        *,
        lan_control: LanControlPlaneV6 | None = None,
        lan_root: str | os.PathLike[str] | None = None,
    ) -> None:
        self.database_path = Path(database_path or default_message_database_path()).resolve()
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise MessageRuntimeError(
                "消息运行数据目录不可写",
                error_id="message.transport_unavailable",
            ) from exc
        self._schema_lock = threading.Lock()
        self._schema_ready = False
        effective_lan_root = (
            lan_root
            if lan_root is not None
            else default_lan_data_directory()
            if lan_control is None and database_path is None
            else None
        )
        self.lan_control = lan_control or (
            LanControlPlaneV6(effective_lan_root)
            if effective_lan_root is not None
            else None
        )
        self._ensure_schema()
        if self.lan_control is not None:
            self.lan_control.register_handler("message.offer", self._handle_lan_offer)
            self.lan_control.register_handler("message.status", self._handle_lan_status)
            self.lan_control.register_handler("message.cancel", self._handle_lan_cancel)
            self.lan_control.register_tick_handler(self.flush_outbox)

    @staticmethod
    def supports(opcode: str) -> bool:
        return str(opcode) in _OPCODES

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=10.0,
            isolation_level=None,
            factory=_ClosingMessageConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            last_error: Exception | None = None
            for attempt in range(5):
                try:
                    with self._connect() as connection:
                        connection.execute("PRAGMA journal_mode = WAL")
                        connection.executescript(
                            """
                            CREATE TABLE IF NOT EXISTS message_meta (
                                key TEXT PRIMARY KEY,
                                value TEXT NOT NULL
                            );
                            CREATE TABLE IF NOT EXISTS message_instances (
                                project_namespace TEXT NOT NULL,
                                host_id TEXT NOT NULL,
                                instance_id TEXT NOT NULL,
                                endpoint_key TEXT NOT NULL,
                                endpoint_kind TEXT NOT NULL,
                                trust_domain TEXT NOT NULL DEFAULT '',
                                display_name TEXT NOT NULL,
                                display_name_key TEXT NOT NULL,
                                created_at INTEGER NOT NULL,
                                last_seen_at INTEGER NOT NULL,
                                PRIMARY KEY (project_namespace, host_id, instance_id),
                                UNIQUE (host_id, instance_id),
                                UNIQUE (project_namespace, host_id, endpoint_key),
                                UNIQUE (project_namespace, display_name_key)
                            );
                            CREATE TABLE IF NOT EXISTS message_batches (
                                batch_id TEXT PRIMARY KEY,
                                project_namespace TEXT NOT NULL,
                                sender_host_id TEXT NOT NULL,
                                sender_instance_id TEXT NOT NULL,
                                sender_display_name TEXT NOT NULL DEFAULT '',
                                name TEXT NOT NULL,
                                content_json TEXT NOT NULL,
                                content_hash TEXT NOT NULL,
                                created_at INTEGER NOT NULL,
                                expires_at INTEGER NOT NULL,
                                request_fingerprint TEXT NOT NULL
                            );
                            CREATE TABLE IF NOT EXISTS message_copies (
                                message_id TEXT PRIMARY KEY,
                                batch_id TEXT NOT NULL REFERENCES message_batches(batch_id) ON DELETE CASCADE,
                                project_namespace TEXT NOT NULL,
                                recipient_host_id TEXT NOT NULL,
                                recipient_instance_id TEXT NOT NULL,
                                recipient_display_name TEXT NOT NULL,
                                status TEXT NOT NULL,
                                created_at INTEGER NOT NULL,
                                expires_at INTEGER NOT NULL,
                                read_at INTEGER,
                                cancelled_at INTEGER,
                                failure_code TEXT,
                                transport_kind TEXT NOT NULL DEFAULT 'local',
                                remote_accepted_at INTEGER,
                                last_transport_at INTEGER,
                                transport_attempts INTEGER NOT NULL DEFAULT 0,
                                transport_error TEXT,
                                cancel_requested_at INTEGER,
                                UNIQUE (batch_id, recipient_host_id, recipient_instance_id)
                            );
                            CREATE INDEX IF NOT EXISTS idx_message_receive
                              ON message_copies(project_namespace, recipient_host_id, recipient_instance_id, status, created_at);
                            CREATE INDEX IF NOT EXISTS idx_message_batch
                              ON message_copies(batch_id, status);
                            """
                        )
                        batch_columns = {
                            str(row["name"])
                            for row in connection.execute(
                                "PRAGMA table_info(message_batches)"
                            ).fetchall()
                        }
                        if "sender_display_name" not in batch_columns:
                            connection.execute(
                                "ALTER TABLE message_batches ADD COLUMN sender_display_name "
                                "TEXT NOT NULL DEFAULT ''"
                            )
                        instance_columns = {
                            str(row["name"])
                            for row in connection.execute(
                                "PRAGMA table_info(message_instances)"
                            ).fetchall()
                        }
                        if "trust_domain" not in instance_columns:
                            connection.execute(
                                "ALTER TABLE message_instances ADD COLUMN trust_domain "
                                "TEXT NOT NULL DEFAULT ''"
                            )
                        copy_columns = {
                            str(row["name"])
                            for row in connection.execute(
                                "PRAGMA table_info(message_copies)"
                            ).fetchall()
                        }
                        additions = {
                            "transport_kind": "TEXT NOT NULL DEFAULT 'local'",
                            "remote_accepted_at": "INTEGER",
                            "last_transport_at": "INTEGER",
                            "transport_attempts": "INTEGER NOT NULL DEFAULT 0",
                            "transport_error": "TEXT",
                            "cancel_requested_at": "INTEGER",
                        }
                        for column, declaration in additions.items():
                            if column not in copy_columns:
                                connection.execute(
                                    f"ALTER TABLE message_copies ADD COLUMN {column} {declaration}"
                                )
                        current = connection.execute(
                            "SELECT value FROM message_meta WHERE key='schema_version'"
                        ).fetchone()
                        if current is None:
                            connection.execute(
                                "INSERT INTO message_meta(key, value) VALUES('schema_version', ?)",
                                (str(MESSAGE_SCHEMA_VERSION),),
                            )
                        elif int(current["value"]) != MESSAGE_SCHEMA_VERSION:
                            raise MessageRuntimeError(
                                "消息数据库版本不受支持",
                                error_id="message.database_version",
                            )
                    self._schema_ready = True
                    return
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
                    last_error = exc
                    time.sleep(0.05 * (attempt + 1))
            raise MessageRuntimeError(
                f"消息数据库初始化失败：{last_error}",
                error_id="message.transport_unavailable",
                transient=True,
            ) from last_error

    @_translate_sqlite_errors
    def host_id(self) -> str:
        lan_host_id = self.lan_control.identity.host_id if self.lan_control is not None else ""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM message_meta WHERE key='host_id'"
            ).fetchone()
            if row is None:
                value = lan_host_id or _new_id("host")
                connection.execute(
                    "INSERT INTO message_meta(key, value) VALUES('host_id', ?)",
                    (value,),
                )
            else:
                value = str(row["value"])
                if lan_host_id and value != lan_host_id:
                    connection.execute(
                        "UPDATE message_instances SET host_id=? WHERE host_id=?",
                        (lan_host_id, value),
                    )
                    connection.execute(
                        "UPDATE message_batches SET sender_host_id=? WHERE sender_host_id=?",
                        (lan_host_id, value),
                    )
                    connection.execute(
                        "UPDATE message_copies SET recipient_host_id=? WHERE recipient_host_id=?",
                        (lan_host_id, value),
                    )
                    connection.execute(
                        "UPDATE message_meta SET value=? WHERE key='host_id'",
                        (lan_host_id,),
                    )
                    value = lan_host_id
            connection.commit()
            return value

    @staticmethod
    def _reference(host_id: str, instance_id: str, _display_name: str = "") -> dict[str, Any]:
        return {
            "kind": "entity_ref",
            "reference_type": "instance_ref",
            "reference_id": (
                f"instance_ref.v1.{_encode_reference_part(host_id)}."
                f"{_encode_reference_part(instance_id)}"
            ),
        }

    @staticmethod
    def _reference_parts(value: Any) -> tuple[str, str]:
        if not isinstance(value, dict):
            raise MessageRuntimeError(
                "接收实例必须是 instance_ref",
                error_id="message.instance_unknown",
            )
        if value.get("kind") not in {None, "entity_ref"} or value.get(
            "reference_type"
        ) not in {None, "instance_ref"}:
            raise MessageRuntimeError(
                "接收实例必须是 instance_ref",
                error_id="message.instance_unknown",
            )
        host_id = str(value.get("host_id") or "").strip()
        instance_id = str(value.get("instance_id") or "").strip()
        reference_id = str(value.get("reference_id") or "")
        if (not host_id or not instance_id) and reference_id.startswith("instance_ref.v1."):
            parts = reference_id.split(".", 3)
            if len(parts) == 4:
                host_id = _decode_reference_part(parts[2])
                instance_id = _decode_reference_part(parts[3])
        if not host_id or not instance_id:
            raise MessageRuntimeError(
                "实例引用缺少稳定 host_id + instance_id",
                error_id="message.instance_unknown",
            )
        return _validate_stable_id(host_id, "host_id"), _validate_stable_id(
            instance_id,
            "instance_id",
        )

    @_translate_sqlite_errors
    def register_instance(
        self,
        project_namespace: str,
        display_name: str,
        *,
        instance_id: str = "",
        endpoint_key: str = "",
        endpoint_kind: str = "ide_debug",
        trust_domain: str = "",
    ) -> dict[str, Any]:
        project = _validate_project_namespace(project_namespace)
        display = _validate_display_name(display_name)
        host_id = self.host_id()
        endpoint = _validate_stable_id(endpoint_key or f"instance-{instance_id or 'default'}", "endpoint_key")
        kind = _validate_stable_id(endpoint_kind, "endpoint_kind")
        trust = _validate_stable_id(
            trust_domain or project,
            "trust_domain",
        )
        now = _now_ms()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                by_endpoint = connection.execute(
                    """SELECT * FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND endpoint_key=?""",
                    (project, host_id, endpoint),
                ).fetchone()
                if by_endpoint is not None:
                    if instance_id and str(by_endpoint["instance_id"]) != instance_id:
                        raise MessageRuntimeError(
                            "运行端点已绑定另一个稳定实例",
                            error_id="message.instance_conflict",
                        )
                    if str(by_endpoint["display_name"]) != display:
                        raise MessageRuntimeError(
                            "实例已存在；请使用重命名操作修改显示名",
                            error_id="message.instance_conflict",
                        )
                    existing_trust = str(by_endpoint["trust_domain"] or project)
                    if existing_trust != trust:
                        raise MessageRuntimeError(
                            "运行端点的签名产品信任域发生变化",
                            error_id="message.instance_conflict",
                        )
                    connection.execute(
                        """UPDATE message_instances SET last_seen_at=?
                           WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                        (now, project, host_id, str(by_endpoint["instance_id"])),
                    )
                    connection.commit()
                    return self._instance_row(by_endpoint)
                stable_instance_id = _validate_stable_id(
                    instance_id or _new_id("instance"),
                    "instance_id",
                )
                connection.execute(
                    """INSERT INTO message_instances(
                           project_namespace,host_id,instance_id,endpoint_key,endpoint_kind,
                           trust_domain,display_name,display_name_key,created_at,last_seen_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        project,
                        host_id,
                        stable_instance_id,
                        endpoint,
                        kind,
                        trust,
                        display,
                        _display_key(display),
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    """SELECT * FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (project, host_id, stable_instance_id),
                ).fetchone()
                connection.commit()
                return self._instance_row(row)
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise MessageRuntimeError(
                    "当前项目已存在同名实例或相同稳定实例",
                    error_id="message.instance_conflict",
                ) from exc

    @_translate_sqlite_errors
    def rename_instance(
        self,
        project_namespace: str,
        instance_id: str,
        display_name: str,
    ) -> dict[str, Any]:
        project = _validate_project_namespace(project_namespace)
        stable_instance_id = _validate_stable_id(instance_id, "instance_id")
        display = _validate_display_name(display_name)
        host_id = self.host_id()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """UPDATE message_instances
                       SET display_name=?,display_name_key=?,last_seen_at=?
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (
                        display,
                        _display_key(display),
                        _now_ms(),
                        project,
                        host_id,
                        stable_instance_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise MessageRuntimeError(
                        "实例不存在",
                        error_id="message.instance_unknown",
                    )
                row = connection.execute(
                    """SELECT * FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (project, host_id, stable_instance_id),
                ).fetchone()
                connection.commit()
                return self._instance_row(row)
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise MessageRuntimeError(
                    "当前项目已存在同名实例",
                    error_id="message.instance_conflict",
                ) from exc

    @staticmethod
    def _instance_row(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise MessageRuntimeError(
                "实例不存在",
                error_id="message.instance_unknown",
            )
        reference = MessageRuntimeV6._reference(
            str(row["host_id"]),
            str(row["instance_id"]),
            str(row["display_name"]),
        )
        return {
            "project_namespace": str(row["project_namespace"]),
            "host_id": str(row["host_id"]),
            "instance_id": str(row["instance_id"]),
            "endpoint_key": str(row["endpoint_key"]),
            "endpoint_kind": str(row["endpoint_kind"]),
            "trust_domain": str(row["trust_domain"] or row["project_namespace"]),
            "display_name": str(row["display_name"]),
            "created_at": _iso_timestamp(int(row["created_at"])),
            "last_seen_at": _iso_timestamp(int(row["last_seen_at"])),
            "reference": reference,
        }

    @_translate_sqlite_errors
    def list_instances(self, project_namespace: str) -> list[dict[str, Any]]:
        project = _validate_project_namespace(project_namespace)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM message_instances WHERE project_namespace=?
                   ORDER BY display_name_key,instance_id""",
                (project,),
            ).fetchall()
        return [self._instance_row(row) for row in rows]

    @_translate_sqlite_errors
    def catalog_instances(self) -> list[dict[str, Any]]:
        """Return routing metadata for the authenticated status catalog."""

        now = _now_ms()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM message_instances ORDER BY project_namespace,display_name_key"
            ).fetchall()
        return [
            {
                "project_namespace": str(row["project_namespace"]),
                "host_id": str(row["host_id"]),
                "instance_id": str(row["instance_id"]),
                "display_name": str(row["display_name"]),
                "product_id": str(row["project_namespace"]),
                "profiles": [],
                "status": (
                    "online" if now - int(row["last_seen_at"]) < 30_000 else "offline"
                ),
            }
            for row in rows
        ]

    @_translate_sqlite_errors
    def instance_context(
        self,
        project_namespace: str,
        *,
        instance_id: str = "",
        default_display_name: str = "IDE调试-1",
        endpoint_key: str = "ide-debug-1",
    ) -> dict[str, Any]:
        project = _validate_project_namespace(project_namespace)
        if instance_id:
            stable = _validate_stable_id(instance_id, "instance_id")
            host_id = self.host_id()
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """UPDATE message_instances SET last_seen_at=?
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (_now_ms(), project, host_id, stable),
                )
                row = connection.execute(
                    """SELECT * FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (project, host_id, stable),
                ).fetchone()
                connection.commit()
            identity = self._instance_row(row)
        else:
            identity = self.register_instance(
                project,
                default_display_name,
                endpoint_key=endpoint_key,
                endpoint_kind="ide_debug",
            )
        return {
            "database_path": str(self.database_path),
            "lan_root": (
                str(self.lan_control.directory.root) if self.lan_control is not None else ""
            ),
            "project_namespace": project,
            "host_id": identity["host_id"],
            "instance_id": identity["instance_id"],
            "display_name": identity["display_name"],
            "trust_domain": identity["trust_domain"],
        }

    def _require_identity(self, context: dict[str, Any]) -> dict[str, str]:
        project = _validate_project_namespace(str(context.get("project_namespace") or ""))
        host_id = _validate_stable_id(str(context.get("host_id") or ""), "host_id")
        instance_id = _validate_stable_id(str(context.get("instance_id") or ""), "instance_id")
        if host_id != self.host_id():
            raise MessageRuntimeError(
                "当前运行身份不属于本机消息宿主",
                error_id="message.transport_unavailable",
            )
        with self._connect() as connection:
            row = connection.execute(
                """SELECT display_name,trust_domain FROM message_instances
                   WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                (project, host_id, instance_id),
            ).fetchone()
        if row is None:
            raise MessageRuntimeError(
                "当前消息运行实例未登记",
                error_id="message.instance_unknown",
            )
        return {
            "project_namespace": project,
            "host_id": host_id,
            "instance_id": instance_id,
            "display_name": str(row["display_name"]),
            "trust_domain": str(row["trust_domain"] or project),
        }

    def _resolve_recipients(
        self,
        project: str,
        recipients: Any,
        trust_domain: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(recipients, list) or not recipients:
            raise MessageRuntimeError(
                "接收实例列表不能为空",
                error_id="message.instance_unknown",
            )
        if len(recipients) > MAX_RECIPIENTS:
            raise MessageRuntimeError(
                f"一次最多发送给 {MAX_RECIPIENTS} 个明确实例",
                error_id="message.instance_unknown",
            )
        host_id = self.host_id()
        resolved: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        with self._connect() as connection:
            for value in recipients:
                target_host, target_instance = self._reference_parts(value)
                key = (target_host, target_instance)
                if key in seen:
                    raise MessageRuntimeError(
                        "接收实例列表包含重复实例",
                        error_id="message.instance_unknown",
                    )
                seen.add(key)
                if target_host == host_id:
                    row = connection.execute(
                        """SELECT * FROM message_instances
                           WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                        (project, target_host, target_instance),
                    ).fetchone()
                    if row is None:
                        raise MessageRuntimeError(
                            "接收实例未知或不属于当前项目",
                            error_id="message.instance_unknown",
                        )
                    if str(row["trust_domain"] or project) != trust_domain:
                        raise MessageRuntimeError(
                            "本机实例不属于同一签名产品信任域",
                            error_id="message.instance_unknown",
                        )
                    local = self._instance_row(row)
                    local["transport_kind"] = "local"
                    resolved.append(local)
                    continue
                if self.lan_control is None:
                    raise MessageRuntimeError(
                        "跨设备实例未接入 LAN 控制面",
                        error_id="message.instance_unknown",
                    )
                try:
                    peer = self.lan_control.directory.peer(target_host)
                    if not bool(peer["remote_permissions"].get("messages")):
                        raise LanControlError(
                            "远端设备未授予普通消息权限",
                            error_id="lan.remote_permission_messages_denied",
                        )
                    remote = self.lan_control.directory.remote_instance(
                        project, target_host, target_instance
                    )
                except LanControlError as exc:
                    raise MessageRuntimeError(
                        "接收实例未知、已撤销或未获普通消息权限",
                        error_id="message.instance_unknown",
                    ) from exc
                resolved.append(
                    {
                        **remote,
                        "display_name": str(remote.get("display_name") or target_instance),
                        "transport_kind": "lan",
                    }
                )
        return resolved

    @staticmethod
    def _batch_fingerprint(
        identity: dict[str, str],
        recipients: list[dict[str, Any]],
        name: str,
        content_json: str,
        ttl_ms: int,
    ) -> str:
        value = {
            "project": identity["project_namespace"],
            "sender": [identity["host_id"], identity["instance_id"]],
            "recipients": sorted(
                [item["host_id"], item["instance_id"]] for item in recipients
            ),
            "name": name,
            "content": json.loads(content_json),
            "ttl_ms": ttl_ms,
        }
        return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

    @_translate_sqlite_errors
    def send(
        self,
        context: dict[str, Any],
        recipients: Any,
        name: Any,
        content: Any,
        ttl_ms: Any = DEFAULT_TTL_MS,
        *,
        batch_id: str = "",
    ) -> dict[str, Any]:
        identity = self._require_identity(context)
        message_name = _validate_message_name(name)
        if not isinstance(ttl_ms, (int, float)) or isinstance(ttl_ms, bool) or not math.isfinite(ttl_ms):
            raise MessageRuntimeError("消息有效期必须是持续时间", error_id="message.content_invalid")
        ttl = int(ttl_ms)
        if ttl <= 0 or ttl > MAX_TTL_MS:
            raise MessageRuntimeError(
                f"消息有效期必须在 1 到 {MAX_TTL_MS} 毫秒之间",
                error_id="message.content_invalid",
            )
        copied_content = _validate_message_value(content)
        content_json = _canonical_json(copied_content)
        if len(content_json.encode("utf-8")) > MAX_CONTENT_BYTES:
            raise MessageRuntimeError(
                f"消息内容超过 {MAX_CONTENT_BYTES} 字节限制",
                error_id="message.content_invalid",
            )
        resolved = self._resolve_recipients(
            identity["project_namespace"], recipients, identity["trust_domain"]
        )
        stable_batch_id = _validate_stable_id(batch_id, "batch_id") if batch_id else _new_id("batch")
        fingerprint = self._batch_fingerprint(identity, resolved, message_name, content_json, ttl)
        created_at = _now_ms()
        expires_at = created_at + ttl
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM message_batches WHERE batch_id=?",
                (stable_batch_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["request_fingerprint"]) != fingerprint
                    or str(existing["project_namespace"]) != identity["project_namespace"]
                    or str(existing["sender_host_id"]) != identity["host_id"]
                    or str(existing["sender_instance_id"]) != identity["instance_id"]
                ):
                    connection.rollback()
                    raise MessageRuntimeError(
                        "相同批次 ID 已用于不同消息",
                        error_id="message.idempotency_conflict",
                    )
                self._expire(connection, identity["project_namespace"])
                result = self._batch_result(connection, stable_batch_id)
                connection.commit()
                if self.lan_control is not None:
                    self.flush_outbox(batch_id=stable_batch_id)
                    with self._connect() as refreshed:
                        result = self._batch_result(refreshed, stable_batch_id)
                return result
            connection.execute(
                """INSERT INTO message_batches(
                       batch_id,project_namespace,sender_host_id,sender_instance_id,
                       sender_display_name,name,
                       content_json,content_hash,created_at,expires_at,request_fingerprint
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    stable_batch_id,
                    identity["project_namespace"],
                    identity["host_id"],
                    identity["instance_id"],
                    identity["display_name"],
                    message_name,
                    content_json,
                    "sha256:" + hashlib.sha256(content_json.encode("utf-8")).hexdigest(),
                    created_at,
                    expires_at,
                    fingerprint,
                ),
            )
            for index, recipient in enumerate(resolved):
                message_id = f"message_{stable_batch_id}_{index + 1}"
                connection.execute(
                    """INSERT INTO message_copies(
                           message_id,batch_id,project_namespace,recipient_host_id,
                           recipient_instance_id,recipient_display_name,status,
                           created_at,expires_at,transport_kind
                       ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        message_id,
                        stable_batch_id,
                        identity["project_namespace"],
                        recipient["host_id"],
                        recipient["instance_id"],
                        recipient["display_name"],
                        (
                            "waiting_read"
                            if recipient.get("transport_kind") == "local"
                            else "waiting_send"
                        ),
                        created_at,
                        expires_at,
                        str(recipient.get("transport_kind") or "local"),
                    ),
                )
            result = self._batch_result(connection, stable_batch_id)
            connection.commit()
            if self.lan_control is not None:
                self.flush_outbox(batch_id=stable_batch_id)
                with self._connect() as refreshed:
                    result = self._batch_result(refreshed, stable_batch_id)
            return result

    @staticmethod
    def _expire(connection: sqlite3.Connection, project: str = "") -> None:
        if project:
            connection.execute(
                """UPDATE message_copies SET status='expired'
                   WHERE project_namespace=? AND status IN ('waiting_send','waiting_read')
                     AND expires_at<=?""",
                (project, _now_ms()),
            )
        else:
            connection.execute(
                """UPDATE message_copies SET status='expired'
                   WHERE status IN ('waiting_send','waiting_read') AND expires_at<=?""",
                (_now_ms(),),
            )

    def _batch_result(self, connection: sqlite3.Connection, batch_id: str) -> dict[str, Any]:
        batch = connection.execute(
            "SELECT * FROM message_batches WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise MessageRuntimeError("发送批次不存在", error_id="message.batch_unknown")
        copies = connection.execute(
            "SELECT * FROM message_copies WHERE batch_id=? ORDER BY rowid",
            (batch_id,),
        ).fetchall()
        return {
            "batch_id": str(batch["batch_id"]),
            "name": str(batch["name"]),
            "created_at": _iso_timestamp(int(batch["created_at"])),
            "expires_at": _iso_timestamp(int(batch["expires_at"])),
            "recipients": [self._copy_result(row) for row in copies],
        }

    @staticmethod
    def _copy_result(row: sqlite3.Row) -> dict[str, Any]:
        reference = MessageRuntimeV6._reference(
            str(row["recipient_host_id"]),
            str(row["recipient_instance_id"]),
            str(row["recipient_display_name"]),
        )
        return {
            "message_id": str(row["message_id"]),
            "recipient": reference,
            "recipient_display_name": str(row["recipient_display_name"]),
            "status": str(row["status"]),
            "transport": str(row["transport_kind"]),
            "transport_error": str(row["transport_error"] or ""),
            "created_at": _iso_timestamp(int(row["created_at"])),
            "expires_at": _iso_timestamp(int(row["expires_at"])),
        }

    @staticmethod
    def _lan_error(exc: MessageRuntimeError) -> LanControlError:
        return LanControlError(
            str(exc),
            error_id=exc.error_id,
            transient=bool(exc.transient),
            action="fix_message_or_instance",
        )

    @staticmethod
    def _wire_status(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "message_id": str(row["message_id"]),
            "batch_id": str(row["batch_id"]),
            "status": str(row["status"]),
            "read_at_ms": int(row["read_at"]) if row["read_at"] is not None else None,
            "cancelled_at_ms": (
                int(row["cancelled_at"]) if row["cancelled_at"] is not None else None
            ),
            "failure_code": str(row["failure_code"] or ""),
            "expires_at_ms": int(row["expires_at"]),
        }

    def _handle_lan_offer(
        self, peer: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Idempotently import exactly one addressed recipient copy."""

        try:
            message_id = _validate_stable_id(str(payload.get("message_id") or ""), "message_id")
            batch_id = _validate_stable_id(str(payload.get("batch_id") or ""), "batch_id")
            project = _validate_project_namespace(str(payload.get("project_namespace") or ""))
            sender_host = _validate_stable_id(str(payload.get("sender_host_id") or ""), "host_id")
            sender_instance = _validate_stable_id(
                str(payload.get("sender_instance_id") or ""), "instance_id"
            )
            recipient_host = _validate_stable_id(
                str(payload.get("recipient_host_id") or ""), "host_id"
            )
            recipient_instance = _validate_stable_id(
                str(payload.get("recipient_instance_id") or ""), "instance_id"
            )
            if sender_host != str(peer.get("host_id") or ""):
                raise MessageRuntimeError(
                    "消息发送者与认证设备不一致", error_id="message.instance_unknown"
                )
            if recipient_host != self.host_id():
                raise MessageRuntimeError(
                    "消息不是发给当前设备", error_id="message.instance_unknown"
                )
            message_name = _validate_message_name(payload.get("name"))
            content = _validate_message_value(payload.get("content"))
            content_json = _canonical_json(content)
            if len(content_json.encode("utf-8")) > MAX_CONTENT_BYTES:
                raise MessageRuntimeError(
                    "消息内容超过上限", error_id="message.content_invalid"
                )
            created_at = int(payload.get("created_at_ms") or 0)
            expires_at = int(payload.get("expires_at_ms") or 0)
            now = _now_ms()
            if created_at <= 0 or created_at > now + 60_000:
                raise MessageRuntimeError(
                    "消息创建时间无效", error_id="message.content_invalid"
                )
            if expires_at <= created_at or expires_at - created_at > MAX_TTL_MS:
                raise MessageRuntimeError(
                    "消息有效期无效", error_id="message.content_invalid"
                )
            sender_display = _validate_display_name(
                str(payload.get("sender_display_name") or sender_instance)
            )
            expected_content_hash = "sha256:" + hashlib.sha256(
                content_json.encode("utf-8")
            ).hexdigest()
            if str(payload.get("content_hash") or "") != expected_content_hash:
                raise MessageRuntimeError(
                    "消息内容摘要不匹配", error_id="message.decode_failed"
                )
            wire_fingerprint = "sha256:" + hashlib.sha256(
                _canonical_json(
                    {
                        "batch_id": batch_id,
                        "project": project,
                        "sender": [sender_host, sender_instance],
                        "name": message_name,
                        "content_hash": expected_content_hash,
                        "created_at_ms": created_at,
                        "expires_at_ms": expires_at,
                    }
                ).encode("utf-8")
            ).hexdigest()
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                instance = connection.execute(
                    """SELECT display_name FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (project, recipient_host, recipient_instance),
                ).fetchone()
                if instance is None:
                    connection.rollback()
                    raise MessageRuntimeError(
                        "已授权接收实例当前未登记在线；保留发送方副本等待重试",
                        error_id="message.transport_unavailable",
                        transient=True,
                    )
                batch = connection.execute(
                    "SELECT * FROM message_batches WHERE batch_id=?", (batch_id,)
                ).fetchone()
                if batch is None:
                    connection.execute(
                        """INSERT INTO message_batches(
                               batch_id,project_namespace,sender_host_id,sender_instance_id,
                               sender_display_name,name,content_json,content_hash,created_at,
                               expires_at,request_fingerprint
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            batch_id,
                            project,
                            sender_host,
                            sender_instance,
                            sender_display,
                            message_name,
                            content_json,
                            expected_content_hash,
                            created_at,
                            expires_at,
                            wire_fingerprint,
                        ),
                    )
                elif (
                    str(batch["request_fingerprint"]) != wire_fingerprint
                    or str(batch["sender_host_id"]) != sender_host
                    or str(batch["sender_instance_id"]) != sender_instance
                ):
                    connection.rollback()
                    raise MessageRuntimeError(
                        "相同批次 ID 已用于不同消息",
                        error_id="message.idempotency_conflict",
                    )
                existing = connection.execute(
                    "SELECT * FROM message_copies WHERE message_id=?", (message_id,)
                ).fetchone()
                if existing is None:
                    initial_status = "expired" if expires_at <= now else "waiting_read"
                    connection.execute(
                        """INSERT INTO message_copies(
                               message_id,batch_id,project_namespace,recipient_host_id,
                               recipient_instance_id,recipient_display_name,status,
                               created_at,expires_at,transport_kind,remote_accepted_at
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            message_id,
                            batch_id,
                            project,
                            recipient_host,
                            recipient_instance,
                            str(instance["display_name"]),
                            initial_status,
                            created_at,
                            expires_at,
                            "lan_inbound",
                            now,
                        ),
                    )
                    existing = connection.execute(
                        "SELECT * FROM message_copies WHERE message_id=?", (message_id,)
                    ).fetchone()
                elif (
                    str(existing["batch_id"]) != batch_id
                    or str(existing["recipient_host_id"]) != recipient_host
                    or str(existing["recipient_instance_id"]) != recipient_instance
                ):
                    connection.rollback()
                    raise MessageRuntimeError(
                        "相同消息 ID 已用于不同收件副本",
                        error_id="message.idempotency_conflict",
                    )
                self._expire(connection, project)
                existing = connection.execute(
                    "SELECT * FROM message_copies WHERE message_id=?", (message_id,)
                ).fetchone()
                connection.commit()
            return self._wire_status(existing)
        except MessageRuntimeError as exc:
            raise self._lan_error(exc) from exc

    def _lan_copy_for_peer(
        self, connection: sqlite3.Connection, peer: dict[str, Any], payload: dict[str, Any]
    ) -> sqlite3.Row:
        message_id = _validate_stable_id(str(payload.get("message_id") or ""), "message_id")
        row = connection.execute(
            """SELECT c.*,b.sender_host_id FROM message_copies c
               JOIN message_batches b ON b.batch_id=c.batch_id WHERE c.message_id=?""",
            (message_id,),
        ).fetchone()
        if row is None or str(row["sender_host_id"]) != str(peer.get("host_id") or ""):
            raise MessageRuntimeError(
                "消息副本不存在或不属于认证设备", error_id="message.instance_unknown"
            )
        return row

    def _handle_lan_status(
        self, peer: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._lan_copy_for_peer(connection, peer, payload)
                self._expire(connection, str(row["project_namespace"]))
                row = self._lan_copy_for_peer(connection, peer, payload)
                connection.commit()
            return self._wire_status(row)
        except MessageRuntimeError as exc:
            raise self._lan_error(exc) from exc

    def _handle_lan_cancel(
        self, peer: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._lan_copy_for_peer(connection, peer, payload)
                self._expire(connection, str(row["project_namespace"]))
                connection.execute(
                    """UPDATE message_copies SET status='cancelled',cancelled_at=?
                       WHERE message_id=? AND status='waiting_read'""",
                    (_now_ms(), str(row["message_id"])),
                )
                row = self._lan_copy_for_peer(connection, peer, payload)
                connection.commit()
            return self._wire_status(row)
        except MessageRuntimeError as exc:
            raise self._lan_error(exc) from exc

    @staticmethod
    def _remote_status_value(value: Any) -> str:
        status = str(value or "")
        return status if status in {"waiting_read", "read", "expired", "cancelled", "failed"} else "failed"

    def _apply_remote_status(
        self, message_id: str, result: dict[str, Any], *, accepted: bool
    ) -> None:
        status = self._remote_status_value(result.get("status"))
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE message_copies SET status=?,read_at=?,cancelled_at=?,
                       failure_code=?,remote_accepted_at=COALESCE(remote_accepted_at,?),
                       last_transport_at=?,transport_attempts=transport_attempts+1,
                       transport_error=NULL WHERE message_id=? AND transport_kind='lan'""",
                (
                    status,
                    result.get("read_at_ms"),
                    result.get("cancelled_at_ms"),
                    str(result.get("failure_code") or "") or None,
                    now if accepted else None,
                    now,
                    str(message_id),
                ),
            )
            connection.commit()

    def _record_transport_failure(self, message_id: str, exc: LanControlError) -> None:
        permanent = (
            not exc.transient
            and exc.error_id
            not in {"lan.device_unreachable", "lan.connection_interrupted", "lan.handler_unavailable"}
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE message_copies SET status=CASE WHEN ? THEN 'failed' ELSE status END,
                       failure_code=CASE WHEN ? THEN ? ELSE failure_code END,
                       last_transport_at=?,transport_attempts=transport_attempts+1,
                       transport_error=? WHERE message_id=? AND transport_kind='lan'
                       AND status IN ('waiting_send','waiting_read')""",
                (
                    1 if permanent else 0,
                    1 if permanent else 0,
                    exc.error_id,
                    _now_ms(),
                    exc.error_id,
                    str(message_id),
                ),
            )
            connection.commit()

    @_translate_sqlite_errors
    def flush_outbox(self, *, batch_id: str = "", force: bool = False) -> dict[str, int]:
        """Attempt each remote copy independently; known offline copies remain durable."""

        if self.lan_control is None:
            return {"attempted": 0, "delivered": 0, "deferred": 0, "failed": 0}
        now = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection)
            params: list[Any] = []
            batch_filter = ""
            if batch_id:
                batch_filter = " AND c.batch_id=?"
                params.append(str(batch_id))
            throttle = "" if force else " AND (c.last_transport_at IS NULL OR c.last_transport_at<=?)"
            if not force:
                params.append(now - 100)
            rows = connection.execute(
                """SELECT c.*,b.sender_host_id,b.sender_instance_id,b.sender_display_name,
                          b.name,b.content_json,b.content_hash
                   FROM message_copies c JOIN message_batches b ON b.batch_id=c.batch_id
                   WHERE c.transport_kind='lan' AND c.status IN ('waiting_send','waiting_read')"""
                + batch_filter
                + throttle
                + " ORDER BY c.created_at,c.rowid",
                tuple(params),
            ).fetchall()
            connection.commit()
        counts = {"attempted": 0, "delivered": 0, "deferred": 0, "failed": 0}
        for row in rows:
            message_id = str(row["message_id"])
            remaining = int(row["expires_at"]) - _now_ms()
            if remaining <= 0:
                continue
            counts["attempted"] += 1
            try:
                if row["cancel_requested_at"] is not None:
                    result = self.lan_control.secure_request(
                        str(row["recipient_host_id"]),
                        "message.cancel",
                        {"message_id": message_id},
                        request_id=f"cancel_{message_id}",
                        ttl_ms=remaining,
                    )
                    self._apply_remote_status(message_id, result, accepted=True)
                elif row["remote_accepted_at"] is None:
                    result = self.lan_control.secure_request(
                        str(row["recipient_host_id"]),
                        "message.offer",
                        {
                            "message_id": message_id,
                            "batch_id": str(row["batch_id"]),
                            "project_namespace": str(row["project_namespace"]),
                            "sender_host_id": str(row["sender_host_id"]),
                            "sender_instance_id": str(row["sender_instance_id"]),
                            "sender_display_name": str(row["sender_display_name"]),
                            "recipient_host_id": str(row["recipient_host_id"]),
                            "recipient_instance_id": str(row["recipient_instance_id"]),
                            "name": str(row["name"]),
                            "content": json.loads(str(row["content_json"])),
                            "content_hash": str(row["content_hash"]),
                            "created_at_ms": int(row["created_at"]),
                            "expires_at_ms": int(row["expires_at"]),
                        },
                        request_id=f"offer_{message_id}",
                        ttl_ms=remaining,
                    )
                    self._apply_remote_status(message_id, result, accepted=True)
                else:
                    result = self.lan_control.secure_request(
                        str(row["recipient_host_id"]),
                        "message.status",
                        {"message_id": message_id},
                        ttl_ms=min(30_000, remaining),
                    )
                    self._apply_remote_status(message_id, result, accepted=True)
                counts["delivered"] += 1
            except LanControlError as exc:
                self._record_transport_failure(message_id, exc)
                if exc.transient:
                    counts["deferred"] += 1
                else:
                    counts["failed"] += 1
        return counts

    @_translate_sqlite_errors
    def wait_receive(
        self,
        context: dict[str, Any],
        name: Any,
        sender: Any = None,
        timeout_ms: Any = 60_000,
        *,
        cancelled: Callable[[], bool] = lambda: False,
        safe_checkpoint: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        identity, message_name, sender_parts = self._receive_filter(
            context,
            name,
            sender,
        )
        timeout = self._timeout(timeout_ms)
        deadline = time.monotonic() + timeout / 1000
        while True:
            if safe_checkpoint is not None:
                safe_checkpoint()
            if cancelled():
                raise MessageRuntimeError("任务已取消", error_id="runtime.cancelled")
            candidates = self._peek_receive_candidates_prevalidated(
                identity,
                message_name,
                sender_parts,
                limit=1,
            )
            if candidates:
                claimed = self._claim_receive_candidate_prevalidated(
                    identity,
                    str(candidates[0]["message_id"]),
                    expected_name=message_name,
                    expected_sender=sender_parts,
                )
                if claimed is not None:
                    return claimed
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

    @_translate_sqlite_errors
    def _receive_filter(
        self,
        context: dict[str, Any],
        name: Any,
        sender: Any,
    ) -> tuple[dict[str, str], str, tuple[str, str] | None]:
        """Validate one receive filter without consuming or exposing a message."""

        identity = self._require_identity(context)
        message_name = _validate_message_name(name)
        sender_parts = self._reference_parts(sender) if sender is not None else None
        if sender_parts is not None:
            sender_host, sender_instance = sender_parts
            with self._connect() as connection:
                known = connection.execute(
                    """SELECT 1 FROM message_instances
                       WHERE project_namespace=? AND host_id=? AND instance_id=?""",
                    (identity["project_namespace"], sender_host, sender_instance),
                ).fetchone()
            if known is None:
                raise MessageRuntimeError(
                    "来源实例未知或不属于当前项目",
                    error_id="message.instance_unknown",
                )
        return identity, message_name, sender_parts

    @_translate_sqlite_errors
    def _receive_snapshot_cursor(self, context: dict[str, Any]) -> int:
        """Return the current recipient queue cursor for one safe-point batch."""

        identity = self._require_identity(context)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, identity["project_namespace"])
            row = connection.execute(
                """SELECT COALESCE(MAX(rowid), 0) AS cursor FROM message_copies
                   WHERE project_namespace=? AND recipient_host_id=?
                     AND recipient_instance_id=? AND status='waiting_read'""",
                (
                    identity["project_namespace"],
                    identity["host_id"],
                    identity["instance_id"],
                ),
            ).fetchone()
            connection.commit()
        return int(row["cursor"] if row is not None else 0)

    def _peek_receive_candidates(
        self,
        context: dict[str, Any],
        name: Any,
        sender: Any = None,
        *,
        max_rowid: int | None = None,
        limit: int = MAX_CONTENT_ITEMS,
    ) -> list[dict[str, Any]]:
        """Decode matching candidates without changing their unread status.

        This is deliberately not part of ``execute`` or the public message
        function catalog.  The cooperative scheduler uses it only after a
        listener declaration has been registered in the current run.
        """

        identity, message_name, sender_parts = self._receive_filter(
            context,
            name,
            sender,
        )
        return self._peek_receive_candidates_prevalidated(
            identity,
            message_name,
            sender_parts,
            max_rowid=max_rowid,
            limit=limit,
        )

    @_translate_sqlite_errors
    def _peek_receive_candidates_prevalidated(
        self,
        identity: dict[str, str],
        message_name: str,
        sender_parts: tuple[str, str] | None,
        *,
        max_rowid: int | None = None,
        limit: int = MAX_CONTENT_ITEMS,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(0, min(int(limit), MAX_CONTENT_ITEMS))
        if bounded_limit == 0:
            return []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, identity["project_namespace"])
            params: list[Any] = [
                identity["project_namespace"],
                identity["host_id"],
                identity["instance_id"],
                message_name,
            ]
            filters = ""
            if sender_parts is not None:
                filters += " AND b.sender_host_id=? AND b.sender_instance_id=?"
                params.extend(sender_parts)
            if max_rowid is not None:
                filters += " AND c.rowid<=?"
                params.append(max(0, int(max_rowid)))
            params.append(bounded_limit)
            rows = connection.execute(
                """SELECT c.rowid AS queue_rowid,c.*,b.name,b.content_json,
                          b.sender_host_id,b.sender_instance_id,b.sender_display_name
                   FROM message_copies c JOIN message_batches b ON b.batch_id=c.batch_id
                   WHERE c.project_namespace=? AND c.recipient_host_id=?
                     AND c.recipient_instance_id=? AND c.status='waiting_read'
                     AND b.name=?""" + filters + " ORDER BY c.rowid LIMIT ?",
                tuple(params),
            ).fetchall()
            candidates = [self._decoded_receive_row(connection, row) for row in rows]
            connection.commit()
        return candidates

    def _claim_receive_candidate(
        self,
        context: dict[str, Any],
        message_id: str,
        *,
        expected_name: Any | None = None,
        expected_sender: Any = None,
    ) -> dict[str, Any] | None:
        """Atomically decode and acknowledge exactly one candidate by ID."""

        if expected_name is None:
            identity = self._require_identity(context)
            message_name = None
            sender_parts = None
        else:
            identity, message_name, sender_parts = self._receive_filter(
                context,
                expected_name,
                expected_sender,
            )
        return self._claim_receive_candidate_prevalidated(
            identity,
            str(message_id or ""),
            expected_name=message_name,
            expected_sender=sender_parts,
        )

    @_translate_sqlite_errors
    def _claim_receive_candidate_prevalidated(
        self,
        identity: dict[str, str],
        message_id: str,
        *,
        expected_name: str | None,
        expected_sender: tuple[str, str] | None,
    ) -> dict[str, Any] | None:
        stable_message_id = _validate_stable_id(message_id, "message_id")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, identity["project_namespace"])
            params: list[Any] = [
                stable_message_id,
                identity["project_namespace"],
                identity["host_id"],
                identity["instance_id"],
            ]
            filters = ""
            if expected_name is not None:
                filters += " AND b.name=?"
                params.append(expected_name)
            if expected_sender is not None:
                filters += " AND b.sender_host_id=? AND b.sender_instance_id=?"
                params.extend(expected_sender)
            row = connection.execute(
                """SELECT c.rowid AS queue_rowid,c.*,b.name,b.content_json,
                          b.sender_host_id,b.sender_instance_id,b.sender_display_name
                   FROM message_copies c JOIN message_batches b ON b.batch_id=c.batch_id
                   WHERE c.message_id=? AND c.project_namespace=?
                     AND c.recipient_host_id=? AND c.recipient_instance_id=?
                     AND c.status='waiting_read'""" + filters,
                tuple(params),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            decoded = self._decoded_receive_row(connection, row)
            read_at = _now_ms()
            updated = connection.execute(
                """UPDATE message_copies SET status='read',read_at=?
                   WHERE message_id=? AND status='waiting_read'""",
                (read_at, stable_message_id),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            connection.commit()
        decoded["read_at"] = _iso_timestamp(read_at)
        return decoded

    def _decoded_receive_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        try:
            content = json.loads(str(row["content_json"]))
            content = _validate_message_value(content)
        except (json.JSONDecodeError, MessageRuntimeError) as exc:
            raise MessageRuntimeError(
                "消息内容解码失败，未产生已读确认",
                error_id="message.decode_failed",
            ) from exc
        sender_row = connection.execute(
            """SELECT display_name FROM message_instances
               WHERE project_namespace=? AND host_id=? AND instance_id=?""",
            (
                str(row["project_namespace"]),
                str(row["sender_host_id"]),
                str(row["sender_instance_id"]),
            ),
        ).fetchone()
        sender_display_name = (
            str(sender_row["display_name"])
            if sender_row
            else str(row["sender_display_name"] or "")
        )
        return {
            "record_type": "received_message",
            "message_id": str(row["message_id"]),
            "batch_id": str(row["batch_id"]),
            "name": str(row["name"]),
            "content": copy.deepcopy(content),
            "sender": self._reference(
                str(row["sender_host_id"]),
                str(row["sender_instance_id"]),
                str(sender_row["display_name"]) if sender_row else "",
            ),
            "sender_display_name": sender_display_name,
            "created_at": _iso_timestamp(int(row["created_at"])),
            "expires_at": _iso_timestamp(int(row["expires_at"])),
        }

    @staticmethod
    def _timeout(value: Any) -> int:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise MessageRuntimeError("超时必须是持续时间", error_id="message.content_invalid")
        timeout = int(value)
        if timeout < 0 or timeout > MAX_TTL_MS:
            raise MessageRuntimeError("超时超出允许范围", error_id="message.content_invalid")
        return timeout

    def _require_batch_owner(
        self,
        connection: sqlite3.Connection,
        identity: dict[str, str],
        batch: Any,
    ) -> sqlite3.Row:
        batch_id = str((batch or {}).get("batch_id") or "") if isinstance(batch, dict) else ""
        if not batch_id:
            raise MessageRuntimeError("发送批次无效", error_id="message.batch_unknown")
        row = connection.execute(
            "SELECT * FROM message_batches WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if row is None or (
            str(row["project_namespace"]) != identity["project_namespace"]
            or str(row["sender_host_id"]) != identity["host_id"]
            or str(row["sender_instance_id"]) != identity["instance_id"]
        ):
            raise MessageRuntimeError(
                "发送批次不存在或不属于当前实例",
                error_id="message.batch_unknown",
            )
        return row

    def _wait_read_result(
        self,
        connection: sqlite3.Connection,
        batch_id: str,
        mode: str,
    ) -> dict[str, Any]:
        rows = connection.execute(
            "SELECT * FROM message_copies WHERE batch_id=? ORDER BY rowid",
            (batch_id,),
        ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {
            "read_instances": [],
            "unread_instances": [],
            "expired_instances": [],
            "failed_instances": [],
            "cancelled_instances": [],
        }
        for row in rows:
            status = str(row["status"])
            reference = self._reference(
                str(row["recipient_host_id"]),
                str(row["recipient_instance_id"]),
                str(row["recipient_display_name"]),
            )
            if status == "read":
                grouped["read_instances"].append(reference)
            elif status == "expired":
                grouped["expired_instances"].append(reference)
            elif status == "failed":
                grouped["failed_instances"].append(reference)
            elif status == "cancelled":
                grouped["cancelled_instances"].append(reference)
            else:
                grouped["unread_instances"].append(reference)
        condition_met = (
            bool(grouped["read_instances"])
            if mode == "any"
            else bool(rows) and len(grouped["read_instances"]) == len(rows)
        )
        terminal = not grouped["unread_instances"]
        return {
            "batch_id": batch_id,
            "mode": mode,
            "condition_met": condition_met,
            "terminal": terminal,
            **grouped,
        }

    @_translate_sqlite_errors
    def wait_read(
        self,
        context: dict[str, Any],
        batch: Any,
        mode: Any = "all",
        timeout_ms: Any = 60_000,
        *,
        cancelled: Callable[[], bool] = lambda: False,
        safe_checkpoint: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        identity = self._require_identity(context)
        read_mode = str(mode or "all")
        if read_mode not in {"all", "any"}:
            raise MessageRuntimeError(
                "等待方式只能是 all 或 any",
                error_id="message.content_invalid",
            )
        timeout = self._timeout(timeout_ms)
        deadline = time.monotonic() + timeout / 1000
        while True:
            if safe_checkpoint is not None:
                safe_checkpoint()
            if cancelled():
                raise MessageRuntimeError("任务已取消", error_id="runtime.cancelled")
            if self.lan_control is not None:
                self.flush_outbox(batch_id=str((batch or {}).get("batch_id") or ""))
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_batch_owner(connection, identity, batch)
                self._expire(connection, identity["project_namespace"])
                result = self._wait_read_result(connection, str(row["batch_id"]), read_mode)
                connection.commit()
            if result["condition_met"] or result["terminal"]:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return result
            time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

    @_translate_sqlite_errors
    def cancel(
        self,
        context: dict[str, Any],
        batch: Any,
        recipient: Any = None,
    ) -> dict[str, Any]:
        identity = self._require_identity(context)
        recipient_parts = self._reference_parts(recipient) if recipient is not None else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_batch_owner(connection, identity, batch)
            self._expire(connection, identity["project_namespace"])
            params: list[Any] = [_now_ms(), str(row["batch_id"])]
            recipient_filter = ""
            if recipient_parts is not None:
                recipient_filter = " AND recipient_host_id=? AND recipient_instance_id=?"
                params.extend(recipient_parts)
            connection.execute(
                """UPDATE message_copies SET status='cancelled',cancelled_at=?
                   WHERE batch_id=? AND status='waiting_read' AND transport_kind='local'"""
                + recipient_filter,
                tuple(params),
            )
            remote_params = [_now_ms(), str(row["batch_id"]), *params[2:]]
            connection.execute(
                """UPDATE message_copies SET cancel_requested_at=?
                   WHERE batch_id=? AND status IN ('waiting_send','waiting_read')
                     AND transport_kind='lan'"""
                + recipient_filter,
                tuple(remote_params),
            )
            select_params: list[Any] = [str(row["batch_id"])]
            select_filter = ""
            if recipient_parts is not None:
                select_filter = " AND recipient_host_id=? AND recipient_instance_id=?"
                select_params.extend(recipient_parts)
            rows = connection.execute(
                "SELECT * FROM message_copies WHERE batch_id=?" + select_filter
                + " ORDER BY rowid",
                tuple(select_params),
            ).fetchall()
            if recipient_parts is not None and not rows:
                connection.rollback()
                raise MessageRuntimeError(
                    "指定实例不属于此发送批次",
                    error_id="message.instance_unknown",
                )
            connection.commit()
        if self.lan_control is not None:
            self.flush_outbox(batch_id=str(row["batch_id"]), force=True)
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM message_copies WHERE batch_id=?" + select_filter
                    + " ORDER BY rowid",
                    tuple(select_params),
                ).fetchall()
        cancelled_instances: list[dict[str, Any]] = []
        not_cancelled_instances: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        for copy_row in rows:
            details.append(self._copy_result(copy_row))
            reference = self._reference(
                str(copy_row["recipient_host_id"]),
                str(copy_row["recipient_instance_id"]),
                str(copy_row["recipient_display_name"]),
            )
            if str(copy_row["status"]) == "cancelled":
                cancelled_instances.append(reference)
            else:
                not_cancelled_instances.append(reference)
        return {
            "batch_id": str(row["batch_id"]),
            "cancelled_instances": cancelled_instances,
            "not_cancelled_instances": not_cancelled_instances,
            "recipients": details,
        }

    def execute(
        self,
        opcode: str,
        function_id: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
        cancelled: Callable[[], bool],
        diagnostic: Callable[[str], None] | None = None,
        safe_checkpoint: Callable[[], None] | None = None,
    ) -> Any:
        if opcode not in _OPCODES:
            raise MessageRuntimeError(
                f"消息运行器不支持指令：{opcode}",
                error_id="message.transport_unavailable",
            )

        def argument(name: str, fallback: str, default: Any = None) -> Any:
            return arguments.get(f"{function_id}.parameter.{name}", arguments.get(fallback, default))

        if opcode == "message.send":
            result = self.send(
                context,
                argument("recipients", "接收实例"),
                argument("name", "消息名称"),
                argument("content", "内容"),
                argument("ttl", "有效期", DEFAULT_TTL_MS),
            )
            summary = f"消息批次 {result['batch_id']} 已原子保存 {len(result['recipients'])} 个本机副本"
        elif opcode == "message.wait_receive":
            result = self.wait_receive(
                context,
                argument("name", "消息名称"),
                argument("sender", "来源实例"),
                argument("timeout", "超时", 60_000),
                cancelled=cancelled,
                safe_checkpoint=safe_checkpoint,
            )
            summary = (
                f"消息 {result['message_id']} 已读取并确认"
                if result is not None
                else "等待接收消息超时"
            )
        elif opcode == "message.wait_read":
            result = self.wait_read(
                context,
                argument("batch", "发送批次"),
                argument("mode", "等待方式", "all"),
                argument("timeout", "超时", 60_000),
                cancelled=cancelled,
                safe_checkpoint=safe_checkpoint,
            )
            summary = f"批次 {result['batch_id']} 已读条件={'满足' if result['condition_met'] else '未满足'}"
        else:
            result = self.cancel(
                context,
                argument("batch", "发送批次"),
                argument("recipient", "接收实例"),
            )
            summary = f"批次 {result['batch_id']} 已取消 {len(result['cancelled_instances'])} 个未读副本"
        if diagnostic is not None:
            diagnostic(summary)
        return result

    @_translate_sqlite_errors
    def diagnostic_snapshot(self, project_namespace: str) -> dict[str, Any]:
        """Return routing metadata only; names and message bodies stay redacted."""

        project = _validate_project_namespace(project_namespace)
        with self._connect() as connection:
            self._expire(connection, project)
            rows = connection.execute(
                """SELECT c.batch_id,c.message_id,c.recipient_host_id,
                          c.recipient_instance_id,c.status,c.created_at,c.expires_at,
                          b.sender_host_id,b.sender_instance_id
                   FROM message_copies c JOIN message_batches b ON b.batch_id=c.batch_id
                   WHERE c.project_namespace=? ORDER BY c.rowid""",
                (project,),
            ).fetchall()
        return {
            "project_namespace": project,
            "messages": [dict(row) for row in rows],
            "redacted_fields": ["name", "content", "display_name"],
        }


__all__ = [
    "DEFAULT_TTL_MS",
    "MAX_CONTENT_BYTES",
    "MAX_RECIPIENTS",
    "MessageRuntimeError",
    "MessageRuntimeV6",
    "default_message_database_path",
    "default_lan_data_directory",
    "default_runtime_data_directory",
    "program_uses_messages",
]
