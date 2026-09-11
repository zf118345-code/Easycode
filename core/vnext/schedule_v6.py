"""Typed, durable scheduling primitives for the format-6 Player Hub.

This module is deliberately a host-control service.  It does not register a
ProgramDocument function and it never reads or mutates ECIR.  A schedule only
references an already installed signed product/profile through a narrow
``ScheduleReferenceResolver`` and submits an immutable dispatch snapshot
through an idempotent ``LocalDispatchPort``.

The coordinator remains the sole plan owner. Dispatch ports may route an
immutable ``dispatch_id`` to an explicitly paired LAN host; wake integration
and Android system scheduling remain separate host integrations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from datetime import time as wall_time
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .message_runtime_v6 import default_runtime_data_directory

SCHEDULE_SCHEMA_VERSION = 1
MAX_PLAN_ENTRIES = 512
MAX_DISPLAY_NAME_LENGTH = 160
MAX_STABLE_ID_LENGTH = 128
MAX_DUE_SCAN_POINTS = 100_000
DISPATCH_LEASE_MS = 30_000

_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_TERMINAL_DISPATCH_STATUSES = frozenset(
    {"completed", "failed", "stopped", "rejected", "skipped", "expired"}
)
_ACTIVE_OCCURRENCE_STATUSES = frozenset(
    {"pending", "dispatching", "accepted", "running", "queued_overlap"}
)


class ScheduleError(RuntimeError):
    """Stable, user-safe scheduling failure."""

    def __init__(
        self,
        message: str,
        *,
        error_id: str = "schedule.invalid",
        transient: bool = False,
        action: str = "fix_request",
        diagnostics: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = bool(transient)
        self.action = action
        self.diagnostics = copy.deepcopy(diagnostics or [])


def _translate_sqlite(exc: sqlite3.Error) -> ScheduleError:
    lowered = str(exc).lower()
    transient = any(token in lowered for token in ("locked", "busy", "temporarily"))
    return ScheduleError(
        "本地计划数据库暂时繁忙" if transient else "本地计划数据库读写失败",
        error_id="schedule.database_unavailable",
        transient=transient,
        action="retry" if transient else "export_diagnostics",
    )


def default_schedule_database_path() -> Path:
    override = os.environ.get("EASYCODE_VNEXT_SCHEDULE_DATABASE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return default_runtime_data_directory() / "schedules.sqlite3"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _validate_id(value: Any, label: str, *, prefix: str = "") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return _new_id(prefix) if prefix else normalized
    if len(normalized) > MAX_STABLE_ID_LENGTH or not _STABLE_ID.fullmatch(normalized):
        raise ScheduleError(
            f"{label}必须是 1-{MAX_STABLE_ID_LENGTH} 位稳定标识",
            error_id="schedule.identity_invalid",
        )
    return normalized


def _validate_name(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > MAX_DISPLAY_NAME_LENGTH:
        raise ScheduleError(
            f"计划名称必须是 1-{MAX_DISPLAY_NAME_LENGTH} 个字符",
            error_id="schedule.name_invalid",
        )
    return normalized


def _utc_ms(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("UTC conversion requires an aware datetime")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _from_utc_ms(value: int) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, timezone.utc)


def _iso_ms(value: int | None) -> str | None:
    if value is None:
        return None
    return _from_utc_ms(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_utc_datetime(value: datetime | str | None, *, label: str = "时间") -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).strip().replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        raise ScheduleError(
            f"{label}必须包含 UTC 偏移",
            error_id="schedule.time_invalid",
        )
    return parsed.astimezone(timezone.utc)


def _parse_local_datetime(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise ScheduleError(
            f"{label}格式无效，应为 YYYY-MM-DDTHH:MM:SS",
            error_id="schedule.trigger_invalid",
        ) from exc
    if parsed.tzinfo is not None:
        raise ScheduleError(
            f"{label}使用计划时区，不能再携带 UTC 偏移",
            error_id="schedule.trigger_invalid",
        )
    return parsed.replace(microsecond=0)


def _parse_wall_time(value: Any) -> wall_time:
    try:
        parsed = wall_time.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise ScheduleError(
            "每日时间格式无效，应为 HH:MM 或 HH:MM:SS",
            error_id="schedule.trigger_invalid",
        ) from exc
    if parsed.tzinfo is not None:
        raise ScheduleError(
            "每日时间使用计划时区，不能携带 UTC 偏移",
            error_id="schedule.trigger_invalid",
        )
    return parsed.replace(microsecond=0)


def _zone(timezone_id: Any) -> ZoneInfo:
    normalized = str(timezone_id or "").strip()
    if not normalized:
        raise ScheduleError(
            "计划必须声明 IANA 时区",
            error_id="schedule.timezone_invalid",
        )
    try:
        return ZoneInfo(normalized)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleError(
            f"IANA 时区不存在：{normalized}",
            error_id="schedule.timezone_invalid",
        ) from exc


def _local_to_first_valid_utc(local_value: datetime, zone: ZoneInfo) -> datetime:
    """Map a local wall time to one UTC instant.

    Ambiguous wall times choose the earlier UTC instant.  A nonexistent wall
    time (DST jump) advances to the first valid wall-clock instant, matching
    the schedule specification without inventing a second occurrence.
    """

    if local_value.tzinfo is not None:
        raise ValueError("local wall time must be naive")
    for offset_seconds in range(0, 6 * 60 * 60 + 1):
        candidate = local_value + timedelta(seconds=offset_seconds)
        instants: list[datetime] = []
        for fold in (0, 1):
            aware = candidate.replace(tzinfo=zone, fold=fold)
            utc_value = aware.astimezone(timezone.utc)
            roundtrip = utc_value.astimezone(zone).replace(tzinfo=None)
            if roundtrip == candidate and utc_value not in instants:
                instants.append(utc_value)
        if instants:
            return min(instants)
    raise ScheduleError(
        "计划时间无法映射到有效时区时刻",
        error_id="schedule.timezone_transition_invalid",
    )


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class VirtualClock:
    """Deterministic clock used by trigger, recovery and FIFO Harness tests."""

    def __init__(self, current: datetime | str) -> None:
        self._lock = threading.Lock()
        self._current = _parse_utc_datetime(current, label="虚拟时钟")

    def now(self) -> datetime:
        with self._lock:
            return self._current

    def set(self, value: datetime | str) -> datetime:
        with self._lock:
            self._current = _parse_utc_datetime(value, label="虚拟时钟")
            return self._current

    def advance(self, **delta: float) -> datetime:
        with self._lock:
            self._current += timedelta(**delta)
            return self._current


class ScheduleReferenceResolver(Protocol):
    """Resolve only installed signed products/profiles in an authorized scope."""

    def resolve(self, entry: Mapping[str, Any]) -> Mapping[str, Any]: ...


class UnavailableScheduleReferenceResolver:
    def resolve(self, _entry: Mapping[str, Any]) -> Mapping[str, Any]:
        raise ScheduleError(
            "本机已安装产品与运行方案注册表尚未连接，不能保存可执行计划",
            error_id="schedule.installed_registry_unavailable",
            action="open_player_hub",
        )


class StaticScheduleReferenceResolver:
    """Strict test/embedding resolver; callers provide authoritative records."""

    def __init__(self, records: Mapping[tuple[str, str, str, str], Mapping[str, Any]]) -> None:
        self._records = {tuple(map(str, key)): copy.deepcopy(dict(value)) for key, value in records.items()}

    def resolve(self, entry: Mapping[str, Any]) -> Mapping[str, Any]:
        key = tuple(
            str(entry.get(name) or "")
            for name in ("host_id", "instance_id", "product_id", "profile_id")
        )
        record = self._records.get(key)
        if record is None:
            raise ScheduleError(
                "计划条目引用的本机实例、产品或运行方案不存在",
                error_id="schedule.reference_unknown",
            )
        if str(record.get("dispatch_scope") or "local") not in {"local", "remote"}:
            raise ScheduleError(
                "计划引用解析器返回了未知派发范围",
                error_id="schedule.reference_invalid",
            )
        return copy.deepcopy(record)


@dataclass(frozen=True, slots=True)
class LocalDispatchRequest:
    dispatch_id: str
    occurrence_id: str
    schedule_id: str
    schedule_revision: int
    entry_id: str
    host_id: str
    instance_id: str
    product_id: str
    profile_id: str
    requested_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "occurrence_id": self.occurrence_id,
            "schedule_id": self.schedule_id,
            "schedule_revision": self.schedule_revision,
            "entry_id": self.entry_id,
            "host_id": self.host_id,
            "instance_id": self.instance_id,
            "product_id": self.product_id,
            "profile_id": self.profile_id,
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True, slots=True)
class DispatchAcceptance:
    dispatch_id: str
    run_id: str
    status: str = "accepted"


class LocalDispatchPort(Protocol):
    def accept(self, request: LocalDispatchRequest) -> DispatchAcceptance: ...


class UnavailableLocalDispatchPort:
    def accept(self, _request: LocalDispatchRequest) -> DispatchAcceptance:
        raise ScheduleError(
            "本机 Execution Service 尚未连接安全的计划启动接点",
            error_id="schedule.execution_adapter_unavailable",
            transient=True,
            action="open_player_hub",
        )


class SQLiteLocalDispatchGateway:
    """Idempotent local admission boundary with an injectable real launcher.

    ``launcher`` must accept the request and the supplied stable ``run_id``.
    It must use that run ID when starting the ordinary Execution Service.
    Re-entry after a crash therefore retries the same logical admission rather
    than manufacturing a second run.  No launcher means the gateway is
    unavailable and never reports a synthetic success.
    """

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        launcher: Callable[[LocalDispatchRequest, str], None] | None = None,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._launcher = launcher
        self._lock = threading.RLock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS local_dispatch_admissions (
                        dispatch_id TEXT PRIMARY KEY,
                        request_hash TEXT NOT NULL,
                        run_id TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL,
                        last_error_id TEXT,
                        launch_lease_until_ms INTEGER
                    )
                    """
                )
                columns = {
                    str(row["name"])
                    for row in connection.execute(
                        "PRAGMA table_info(local_dispatch_admissions)"
                    ).fetchall()
                }
                if "launch_lease_until_ms" not in columns:
                    connection.execute(
                        "ALTER TABLE local_dispatch_admissions ADD COLUMN launch_lease_until_ms INTEGER"
                    )
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def accept(self, request: LocalDispatchRequest) -> DispatchAcceptance:
        if self._launcher is None:
            raise ScheduleError(
                "本机 Execution Service 尚未连接安全的计划启动接点",
                error_id="schedule.execution_adapter_unavailable",
                transient=True,
                action="open_player_hub",
            )
        payload = request.as_dict()
        # requested_at is observation metadata and changes on a safe retry.  It
        # must not turn the same immutable dispatch into an identity conflict.
        identity_payload = {key: value for key, value in payload.items() if key != "requested_at"}
        request_hash = hashlib.sha256(_canonical_json(identity_payload).encode("utf-8")).hexdigest()
        run_id = _hash_id("run", request.dispatch_id)
        now_ms = int(time.time() * 1000)
        try:
            with self._lock:
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT * FROM local_dispatch_admissions WHERE dispatch_id=?",
                        (request.dispatch_id,),
                    ).fetchone()
                    if row is not None:
                        if str(row["request_hash"]) != request_hash:
                            connection.rollback()
                            raise ScheduleError(
                                "同一 dispatch_id 的派发内容发生变化",
                                error_id="schedule.dispatch_identity_conflict",
                            )
                        run_id = str(row["run_id"])
                        if str(row["status"]) == "started":
                            connection.commit()
                            return DispatchAcceptance(request.dispatch_id, run_id)
                        lease_until = int(row["launch_lease_until_ms"] or 0)
                        if str(row["status"]) == "launching" and lease_until > now_ms:
                            connection.rollback()
                            raise ScheduleError(
                                "同一本机派发正在接纳中",
                                error_id="schedule.dispatch_in_progress",
                                transient=True,
                                action="retry",
                            )
                        connection.execute(
                            """
                            UPDATE local_dispatch_admissions
                               SET status='launching', updated_at_ms=?,
                                   launch_lease_until_ms=?, last_error_id=NULL
                             WHERE dispatch_id=?
                            """,
                            (now_ms, now_ms + DISPATCH_LEASE_MS, request.dispatch_id),
                        )
                    else:
                        connection.execute(
                            """
                            INSERT INTO local_dispatch_admissions(
                                dispatch_id, request_hash, run_id, status,
                                created_at_ms, updated_at_ms, last_error_id,
                                launch_lease_until_ms
                            ) VALUES(?, ?, ?, 'launching', ?, ?, NULL, ?)
                            """,
                            (
                                request.dispatch_id,
                                request_hash,
                                run_id,
                                now_ms,
                                now_ms,
                                now_ms + DISPATCH_LEASE_MS,
                            ),
                        )
                    connection.commit()
                try:
                    self._launcher(request, run_id)
                except ScheduleError as exc:
                    with self._connect() as connection:
                        connection.execute(
                            """
                            UPDATE local_dispatch_admissions
                               SET status='launch_failed', updated_at_ms=?, last_error_id=?,
                                   launch_lease_until_ms=NULL
                             WHERE dispatch_id=?
                            """,
                            (int(time.time() * 1000), exc.error_id, request.dispatch_id),
                        )
                    raise
                except Exception as exc:
                    with self._connect() as connection:
                        connection.execute(
                            """
                            UPDATE local_dispatch_admissions
                               SET status='launch_failed', updated_at_ms=?, last_error_id=?,
                                   launch_lease_until_ms=NULL
                             WHERE dispatch_id=?
                            """,
                            (
                                int(time.time() * 1000),
                                "schedule.execution_start_failed",
                                request.dispatch_id,
                            ),
                        )
                    raise ScheduleError(
                        "Execution Service 拒绝了本机计划任务",
                        error_id="schedule.execution_start_failed",
                        transient=True,
                        action="retry",
                    ) from exc
                with self._connect() as connection:
                    connection.execute(
                        """
                        UPDATE local_dispatch_admissions
                           SET status='started', updated_at_ms=?, last_error_id=NULL,
                               launch_lease_until_ms=NULL
                         WHERE dispatch_id=?
                        """,
                        (int(time.time() * 1000), request.dispatch_id),
                    )
                return DispatchAcceptance(request.dispatch_id, run_id)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def recover_host_restart(self) -> int:
        """Make interrupted admissions retryable without changing their run ID.

        Runtime sessions are process-local and deliberately are not resumed
        after a Player Hub crash.  A dispatch that had not yet been ACKed by
        the schedule database may therefore be admitted again, but the row's
        stable ``run_id`` is retained.
        """

        now_ms = int(time.time() * 1000)
        try:
            with self._lock, self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE local_dispatch_admissions
                       SET status='launch_failed', updated_at_ms=?,
                           last_error_id='schedule.host_restarted',
                           launch_lease_until_ms=NULL
                     WHERE status IN ('launching','started')
                    """,
                    (now_ms,),
                )
                return int(cursor.rowcount)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def get_admission(self, dispatch_id: str) -> dict[str, Any]:
        """Return redacted admission state for an authenticated coordinator."""

        stable = _validate_id(dispatch_id, "派发 ID")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT dispatch_id,run_id,status,updated_at_ms,last_error_id
                       FROM local_dispatch_admissions WHERE dispatch_id=?""",
                    (stable,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc
        if row is None:
            raise ScheduleError(
                "远程派发接纳记录不存在",
                error_id="schedule.dispatch_not_found",
            )
        return {
            "dispatch_id": str(row["dispatch_id"]),
            "run_id": str(row["run_id"]),
            "status": str(row["status"]),
            "updated_at": _iso_ms(int(row["updated_at_ms"])),
            "error_id": str(row["last_error_id"] or ""),
        }


def _normalize_trigger(trigger: Mapping[str, Any], timezone_id: str) -> dict[str, Any]:
    trigger_type = str(trigger.get("type") or "").strip()
    zone = _zone(timezone_id)
    if trigger_type == "once":
        local = _parse_local_datetime(trigger.get("local_datetime"), "单次执行时间")
        return {
            "type": "once",
            "local_datetime": local.isoformat(timespec="seconds"),
            "resolved_at_ms": _utc_ms(_local_to_first_valid_utc(local, zone)),
        }
    if trigger_type == "daily":
        value = _parse_wall_time(trigger.get("local_time"))
        return {"type": "daily", "local_time": value.isoformat(timespec="seconds")}
    if trigger_type == "interval":
        anchor = _parse_local_datetime(trigger.get("anchor_local_datetime"), "间隔锚点")
        try:
            interval_seconds = int(trigger.get("interval_seconds"))
        except (TypeError, ValueError) as exc:
            raise ScheduleError(
                "固定间隔必须是整数秒",
                error_id="schedule.trigger_invalid",
            ) from exc
        if interval_seconds < 1:
            raise ScheduleError(
                "固定间隔必须至少为 1 秒",
                error_id="schedule.trigger_invalid",
            )
        return {
            "type": "interval",
            "anchor_local_datetime": anchor.isoformat(timespec="seconds"),
            "anchor_at_ms": _utc_ms(_local_to_first_valid_utc(anchor, zone)),
            "interval_seconds": interval_seconds,
        }
    raise ScheduleError(
        "计划触发器只能是 once、daily 或 interval",
        error_id="schedule.trigger_invalid",
    )


def _normalize_entry(
    value: Mapping[str, Any],
    resolver: ScheduleReferenceResolver,
    order: int,
) -> dict[str, Any]:
    entry = {
        "entry_id": _validate_id(value.get("entry_id"), "条目 ID", prefix="entry"),
        "order": order,
        "enabled": bool(value.get("enabled", True)),
        "host_id": _validate_id(value.get("host_id"), "主机 ID"),
        "instance_id": _validate_id(value.get("instance_id"), "实例 ID"),
        "product_id": _validate_id(value.get("product_id"), "产品 ID"),
        "profile_id": _validate_id(value.get("profile_id"), "运行方案 ID"),
    }
    if not all(entry[name] for name in ("host_id", "instance_id", "product_id", "profile_id")):
        raise ScheduleError(
            "计划条目必须指定主机、实例、产品和运行方案",
            error_id="schedule.reference_invalid",
        )
    try:
        offset = int(value.get("start_offset_seconds") or 0)
        deadline_value = value.get("start_deadline_seconds")
        deadline = None if deadline_value is None else int(deadline_value)
    except (TypeError, ValueError) as exc:
        raise ScheduleError(
            "条目错峰和截止时间必须是整数秒",
            error_id="schedule.entry_invalid",
        ) from exc
    if offset < 0 or (deadline is not None and deadline < 0):
        raise ScheduleError(
            "条目错峰和截止时间不能为负数",
            error_id="schedule.entry_invalid",
        )
    if deadline is not None and deadline < offset:
        raise ScheduleError(
            "条目启动截止时间不能早于错峰时间",
            error_id="schedule.entry_invalid",
        )
    entry["start_offset_seconds"] = offset
    entry["start_deadline_seconds"] = deadline
    resolved = dict(resolver.resolve(entry))
    dispatch_scope = str(resolved.get("dispatch_scope") or "local")
    if dispatch_scope not in {"local", "remote"}:
        raise ScheduleError(
            "计划引用解析器返回了未知派发范围",
            error_id="schedule.reference_invalid",
        )
    entry["dispatch_scope"] = dispatch_scope
    entry["validated_summary"] = {
        key: resolved[key]
        for key in ("host_name", "instance_name", "product_name", "profile_name", "release_id")
        if key in resolved and isinstance(resolved[key], (str, int, float, bool, type(None)))
    }
    return entry


def _normalize_plan(
    value: Mapping[str, Any],
    resolver: ScheduleReferenceResolver,
    *,
    schedule_id: str | None = None,
) -> dict[str, Any]:
    timezone_id = str(value.get("timezone_id") or "").strip()
    _zone(timezone_id)
    trigger_value = value.get("trigger")
    if not isinstance(trigger_value, Mapping):
        raise ScheduleError(
            "计划触发器必须是结构化对象",
            error_id="schedule.trigger_invalid",
        )
    entries_value = value.get("entries")
    if not isinstance(entries_value, (list, tuple)) or not entries_value:
        raise ScheduleError(
            "计划至少需要一个批次条目",
            error_id="schedule.entries_empty",
        )
    if len(entries_value) > MAX_PLAN_ENTRIES:
        raise ScheduleError(
            f"计划条目不能超过 {MAX_PLAN_ENTRIES} 项",
            error_id="schedule.entries_limit",
        )
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(entries_value):
        if not isinstance(item, Mapping):
            raise ScheduleError(
                "计划条目必须是结构化对象",
                error_id="schedule.entry_invalid",
            )
        entries.append(_normalize_entry(item, resolver, index))
    ids = [item["entry_id"] for item in entries]
    if len(ids) != len(set(ids)):
        raise ScheduleError(
            "计划条目 ID 不能重复",
            error_id="schedule.entry_duplicate",
        )
    misfire_policy = str(value.get("misfire_policy") or "skip")
    if misfire_policy not in {"skip", "catch_up_once"}:
        raise ScheduleError(
            "错过策略只能是 skip 或 catch_up_once",
            error_id="schedule.policy_invalid",
        )
    overlap_policy = str(value.get("overlap_policy") or "skip")
    if overlap_policy not in {"skip", "queue_once"}:
        raise ScheduleError(
            "重叠策略只能是 skip 或 queue_once",
            error_id="schedule.policy_invalid",
        )
    dispatch_mode = str(value.get("dispatch_mode") or "simultaneous")
    if dispatch_mode not in {"simultaneous", "staggered"}:
        raise ScheduleError(
            "批次派发方式只能是 simultaneous 或 staggered",
            error_id="schedule.policy_invalid",
        )
    if dispatch_mode == "simultaneous" and any(
        int(entry["start_offset_seconds"]) != 0 for entry in entries
    ):
        raise ScheduleError(
            "同时派发模式不能设置条目错峰时间",
            error_id="schedule.policy_invalid",
        )
    try:
        max_lateness_seconds = int(value.get("max_lateness_seconds") or 0)
    except (TypeError, ValueError) as exc:
        raise ScheduleError(
            "最大迟到时间必须是整数秒",
            error_id="schedule.policy_invalid",
        ) from exc
    if max_lateness_seconds < 0:
        raise ScheduleError(
            "最大迟到时间不能为负数",
            error_id="schedule.policy_invalid",
        )
    if misfire_policy == "catch_up_once" and max_lateness_seconds < 1:
        raise ScheduleError(
            "合并补跑必须设置大于 0 的最大迟到时间",
            error_id="schedule.policy_invalid",
        )
    return {
        "schedule_id": _validate_id(schedule_id or value.get("schedule_id"), "计划 ID", prefix="schedule"),
        "name": _validate_name(value.get("name")),
        "enabled": bool(value.get("enabled", True)),
        "timezone_id": timezone_id,
        "trigger": _normalize_trigger(trigger_value, timezone_id),
        "misfire_policy": misfire_policy,
        "max_lateness_seconds": max_lateness_seconds,
        "overlap_policy": overlap_policy,
        "dispatch_mode": dispatch_mode,
        "entries": entries,
        "created_by": _validate_id(value.get("created_by") or "local_user", "创建者 ID"),
    }


class ScheduleServiceV6:
    """SQLite-backed trigger, occurrence and local FIFO dispatch coordinator."""

    def __init__(
        self,
        database_path: str | os.PathLike[str] | None = None,
        *,
        clock: Clock | None = None,
        resolver: ScheduleReferenceResolver | None = None,
        dispatcher: LocalDispatchPort | None = None,
    ) -> int:
        self.database_path = Path(database_path or default_schedule_database_path()).resolve()
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ScheduleError(
                "本地计划数据目录不可写",
                error_id="schedule.database_unavailable",
                action="choose_data_directory",
            ) from exc
        self.clock = clock or SystemClock()
        self.resolver = resolver or UnavailableScheduleReferenceResolver()
        self.dispatcher = dispatcher or UnavailableLocalDispatchPort()
        self._lock = threading.RLock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS schedule_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS schedule_plans (
                        schedule_id TEXT PRIMARY KEY,
                        revision INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        enabled INTEGER NOT NULL,
                        timezone_id TEXT NOT NULL,
                        trigger_json TEXT NOT NULL,
                        misfire_policy TEXT NOT NULL,
                        max_lateness_seconds INTEGER NOT NULL,
                        overlap_policy TEXT NOT NULL,
                        dispatch_mode TEXT NOT NULL,
                        entries_json TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL,
                        next_due_at_ms INTEGER,
                        last_processed_due_at_ms INTEGER,
                        deleted_at_ms INTEGER
                    );
                    CREATE INDEX IF NOT EXISTS idx_schedule_due
                      ON schedule_plans(enabled, deleted_at_ms, next_due_at_ms);
                    CREATE TABLE IF NOT EXISTS schedule_occurrences (
                        occurrence_id TEXT PRIMARY KEY,
                        schedule_id TEXT NOT NULL,
                        schedule_revision INTEGER NOT NULL,
                        scheduled_at_ms INTEGER NOT NULL,
                        discovered_at_ms INTEGER NOT NULL,
                        first_due_at_ms INTEGER NOT NULL,
                        last_due_at_ms INTEGER NOT NULL,
                        collapsed_due_count INTEGER NOT NULL,
                        trigger_source TEXT NOT NULL,
                        entry_snapshot_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        reason_code TEXT,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_occurrence_schedule
                      ON schedule_occurrences(schedule_id, created_at_ms);
                    CREATE TABLE IF NOT EXISTS schedule_dispatches (
                        dispatch_id TEXT PRIMARY KEY,
                        occurrence_id TEXT NOT NULL REFERENCES schedule_occurrences(occurrence_id) ON DELETE CASCADE,
                        schedule_id TEXT NOT NULL,
                        schedule_revision INTEGER NOT NULL,
                        entry_id TEXT NOT NULL,
                        entry_order INTEGER NOT NULL,
                        host_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        profile_id TEXT NOT NULL,
                        request_json TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        not_before_at_ms INTEGER NOT NULL,
                        deadline_at_ms INTEGER,
                        status TEXT NOT NULL,
                        run_id TEXT,
                        error_id TEXT,
                        error_message TEXT,
                        lease_until_ms INTEGER,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_dispatch_ready
                      ON schedule_dispatches(status, not_before_at_ms, created_at_ms, entry_order);
                    CREATE INDEX IF NOT EXISTS idx_dispatch_instance
                      ON schedule_dispatches(host_id, instance_id, status, created_at_ms);
                    CREATE TABLE IF NOT EXISTS schedule_diagnostics (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        recorded_at_ms INTEGER NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        schedule_id TEXT,
                        occurrence_id TEXT,
                        dispatch_id TEXT,
                        run_id TEXT,
                        error_id TEXT,
                        details_json TEXT NOT NULL
                    );
                    """
                )
                row = connection.execute(
                    "SELECT value FROM schedule_meta WHERE key='schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO schedule_meta(key, value) VALUES('schema_version', ?)",
                        (str(SCHEDULE_SCHEMA_VERSION),),
                    )
                elif int(row["value"]) != SCHEDULE_SCHEMA_VERSION:
                    raise ScheduleError(
                        "本地计划数据库版本不受支持",
                        error_id="schedule.database_version",
                        action="export_diagnostics",
                    )
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def _now_ms(self) -> int:
        return _utc_ms(_parse_utc_datetime(self.clock.now(), label="调度时钟"))

    @staticmethod
    def _plan_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "schedule_id": str(row["schedule_id"]),
            "revision": int(row["revision"]),
            "name": str(row["name"]),
            "enabled": bool(row["enabled"]),
            "timezone_id": str(row["timezone_id"]),
            "trigger": json.loads(row["trigger_json"]),
            "misfire_policy": str(row["misfire_policy"]),
            "max_lateness_seconds": int(row["max_lateness_seconds"]),
            "overlap_policy": str(row["overlap_policy"]),
            "dispatch_mode": str(row["dispatch_mode"]),
            "entries": json.loads(row["entries_json"]),
            "created_by": str(row["created_by"]),
            "created_at": _iso_ms(int(row["created_at_ms"])),
            "updated_at": _iso_ms(int(row["updated_at_ms"])),
            "next_due_at": _iso_ms(row["next_due_at_ms"]),
            "last_processed_due_at": _iso_ms(row["last_processed_due_at_ms"]),
            "deleted_at": _iso_ms(row["deleted_at_ms"]),
        }

    @staticmethod
    def _occurrence_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "occurrence_id": str(row["occurrence_id"]),
            "schedule_id": str(row["schedule_id"]),
            "schedule_revision": int(row["schedule_revision"]),
            "scheduled_at": _iso_ms(int(row["scheduled_at_ms"])),
            "discovered_at": _iso_ms(int(row["discovered_at_ms"])),
            "first_due_at": _iso_ms(int(row["first_due_at_ms"])),
            "last_due_at": _iso_ms(int(row["last_due_at_ms"])),
            "collapsed_due_count": int(row["collapsed_due_count"]),
            "trigger_source": str(row["trigger_source"]),
            "entries": json.loads(row["entry_snapshot_json"]),
            "status": str(row["status"]),
            "reason_code": row["reason_code"],
            "created_at": _iso_ms(int(row["created_at_ms"])),
            "updated_at": _iso_ms(int(row["updated_at_ms"])),
        }

    @staticmethod
    def _dispatch_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "dispatch_id": str(row["dispatch_id"]),
            "occurrence_id": str(row["occurrence_id"]),
            "schedule_id": str(row["schedule_id"]),
            "schedule_revision": int(row["schedule_revision"]),
            "entry_id": str(row["entry_id"]),
            "entry_order": int(row["entry_order"]),
            "host_id": str(row["host_id"]),
            "instance_id": str(row["instance_id"]),
            "product_id": str(row["product_id"]),
            "profile_id": str(row["profile_id"]),
            "not_before_at": _iso_ms(int(row["not_before_at_ms"])),
            "deadline_at": _iso_ms(row["deadline_at_ms"]),
            "status": str(row["status"]),
            "run_id": row["run_id"],
            "error_id": row["error_id"],
            "error_message": row["error_message"],
            "created_at": _iso_ms(int(row["created_at_ms"])),
            "updated_at": _iso_ms(int(row["updated_at_ms"])),
        }

    def _next_due_after(self, plan: Mapping[str, Any], after_ms: int) -> int | None:
        trigger = dict(plan["trigger"])
        trigger_type = str(trigger["type"])
        if trigger_type == "once":
            due = int(trigger["resolved_at_ms"])
            return due if due > after_ms else None
        if trigger_type == "interval":
            anchor = int(trigger["anchor_at_ms"])
            interval_ms = int(trigger["interval_seconds"]) * 1000
            if after_ms < anchor:
                return anchor
            return anchor + ((after_ms - anchor) // interval_ms + 1) * interval_ms
        if trigger_type == "daily":
            zone = _zone(plan["timezone_id"])
            local_after = _from_utc_ms(after_ms).astimezone(zone)
            daily_time = _parse_wall_time(trigger["local_time"])
            for day_offset in range(0, 370):
                local_day = local_after.date() + timedelta(days=day_offset)
                local_candidate = datetime.combine(local_day, daily_time)
                due = _utc_ms(_local_to_first_valid_utc(local_candidate, zone))
                if due > after_ms:
                    return due
            raise ScheduleError(
                "无法计算每日计划的下次时间",
                error_id="schedule.trigger_calculation_failed",
            )
        raise ScheduleError("计划触发器损坏", error_id="schedule.trigger_invalid")

    def _initial_next_due(self, plan: Mapping[str, Any], now_ms: int) -> int | None:
        trigger = dict(plan["trigger"])
        if trigger["type"] == "once":
            return int(trigger["resolved_at_ms"])
        return self._next_due_after(plan, now_ms)

    def create_plan(self, value: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _normalize_plan(value, self.resolver)
        now_ms = self._now_ms()
        next_due = self._initial_next_due(normalized, now_ms) if normalized["enabled"] else None
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO schedule_plans(
                        schedule_id, revision, name, enabled, timezone_id,
                        trigger_json, misfire_policy, max_lateness_seconds,
                        overlap_policy, dispatch_mode, entries_json, created_by,
                        created_at_ms, updated_at_ms, next_due_at_ms,
                        last_processed_due_at_ms, deleted_at_ms
                    ) VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        normalized["schedule_id"], normalized["name"], int(normalized["enabled"]),
                        normalized["timezone_id"], _canonical_json(normalized["trigger"]),
                        normalized["misfire_policy"], normalized["max_lateness_seconds"],
                        normalized["overlap_policy"], normalized["dispatch_mode"],
                        _canonical_json(normalized["entries"]), normalized["created_by"],
                        now_ms, now_ms, next_due,
                    ),
                )
                self._diagnostic(
                    connection,
                    now_ms,
                    event_type="schedule.created",
                    schedule_id=normalized["schedule_id"],
                    details={"revision": 1, "entry_count": len(normalized["entries"])},
                )
                connection.commit()
                row = connection.execute(
                    "SELECT * FROM schedule_plans WHERE schedule_id=?",
                    (normalized["schedule_id"],),
                ).fetchone()
            return self._plan_from_row(row)
        except sqlite3.IntegrityError as exc:
            raise ScheduleError(
                "计划 ID 已存在",
                error_id="schedule.identity_conflict",
            ) from exc
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def update_plan(
        self,
        schedule_id: str,
        expected_revision: int,
        value: Mapping[str, Any],
    ) -> dict[str, Any]:
        schedule_id = _validate_id(schedule_id, "计划 ID")
        normalized = _normalize_plan(value, self.resolver, schedule_id=schedule_id)
        now_ms = self._now_ms()
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    "SELECT * FROM schedule_plans WHERE schedule_id=? AND deleted_at_ms IS NULL",
                    (schedule_id,),
                ).fetchone()
                if current is None:
                    connection.rollback()
                    raise ScheduleError(
                        "计划不存在",
                        error_id="schedule.not_found",
                        action="reload_schedules",
                    )
                actual_revision = int(current["revision"])
                if actual_revision != int(expected_revision):
                    connection.rollback()
                    raise ScheduleError(
                        "计划已被其他操作修改，当前内容未覆盖",
                        error_id="schedule.revision_conflict",
                        action="reload_schedules",
                        diagnostics=[{
                            "schedule_id": schedule_id,
                            "expected_revision": int(expected_revision),
                            "actual_revision": actual_revision,
                        }],
                    )
                revision = actual_revision + 1
                next_due = self._initial_next_due(normalized, now_ms) if normalized["enabled"] else None
                connection.execute(
                    """
                    UPDATE schedule_plans SET
                        revision=?, name=?, enabled=?, timezone_id=?, trigger_json=?,
                        misfire_policy=?, max_lateness_seconds=?, overlap_policy=?,
                        dispatch_mode=?, entries_json=?, updated_at_ms=?, next_due_at_ms=?,
                        last_processed_due_at_ms=NULL
                    WHERE schedule_id=?
                    """,
                    (
                        revision, normalized["name"], int(normalized["enabled"]),
                        normalized["timezone_id"], _canonical_json(normalized["trigger"]),
                        normalized["misfire_policy"], normalized["max_lateness_seconds"],
                        normalized["overlap_policy"], normalized["dispatch_mode"],
                        _canonical_json(normalized["entries"]), now_ms, next_due, schedule_id,
                    ),
                )
                self._diagnostic(
                    connection,
                    now_ms,
                    event_type="schedule.updated",
                    schedule_id=schedule_id,
                    details={"revision": revision, "entry_count": len(normalized["entries"])},
                )
                connection.commit()
                row = connection.execute(
                    "SELECT * FROM schedule_plans WHERE schedule_id=?",
                    (schedule_id,),
                ).fetchone()
            return self._plan_from_row(row)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def delete_plan(self, schedule_id: str, expected_revision: int) -> dict[str, Any]:
        schedule_id = _validate_id(schedule_id, "计划 ID")
        now_ms = self._now_ms()
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT revision FROM schedule_plans WHERE schedule_id=? AND deleted_at_ms IS NULL",
                    (schedule_id,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise ScheduleError(
                        "计划不存在",
                        error_id="schedule.not_found",
                        action="reload_schedules",
                    )
                actual_revision = int(row["revision"])
                if actual_revision != int(expected_revision):
                    connection.rollback()
                    raise ScheduleError(
                        "计划已被其他操作修改，删除未执行",
                        error_id="schedule.revision_conflict",
                        action="reload_schedules",
                        diagnostics=[{
                            "schedule_id": schedule_id,
                            "expected_revision": int(expected_revision),
                            "actual_revision": actual_revision,
                        }],
                    )
                connection.execute(
                    """
                    UPDATE schedule_plans
                       SET revision=revision+1, enabled=0, next_due_at_ms=NULL,
                           updated_at_ms=?, deleted_at_ms=?
                     WHERE schedule_id=?
                    """,
                    (now_ms, now_ms, schedule_id),
                )
                self._diagnostic(
                    connection,
                    now_ms,
                    event_type="schedule.deleted",
                    schedule_id=schedule_id,
                    details={"previous_revision": actual_revision},
                )
                connection.commit()
            return {"ok": True, "schedule_id": schedule_id, "deleted_at": _iso_ms(now_ms)}
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def get_plan(self, schedule_id: str, *, include_deleted: bool = False) -> dict[str, Any]:
        schedule_id = _validate_id(schedule_id, "计划 ID")
        condition = "" if include_deleted else " AND deleted_at_ms IS NULL"
        try:
            with self._connect() as connection:
                row = connection.execute(
                    f"SELECT * FROM schedule_plans WHERE schedule_id=?{condition}",
                    (schedule_id,),
                ).fetchone()
            if row is None:
                raise ScheduleError(
                    "计划不存在",
                    error_id="schedule.not_found",
                    action="reload_schedules",
                )
            return self._plan_from_row(row)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def list_plans(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        condition = "" if include_deleted else " WHERE deleted_at_ms IS NULL"
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    f"SELECT * FROM schedule_plans{condition} ORDER BY created_at_ms, schedule_id"
                ).fetchall()
            return [self._plan_from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def _due_span(
        self,
        plan: Mapping[str, Any],
        first_due_ms: int,
        now_ms: int,
    ) -> tuple[int, int, int, int | None]:
        trigger = dict(plan["trigger"])
        if first_due_ms > now_ms:
            return first_due_ms, first_due_ms, 0, first_due_ms
        if trigger["type"] == "once":
            return first_due_ms, first_due_ms, 1, None
        if trigger["type"] == "interval":
            interval_ms = int(trigger["interval_seconds"]) * 1000
            count = (now_ms - first_due_ms) // interval_ms + 1
            last_due = first_due_ms + (count - 1) * interval_ms
            return first_due_ms, last_due, int(count), last_due + interval_ms
        count = 0
        last_due = first_due_ms
        cursor = first_due_ms
        while cursor <= now_ms:
            count += 1
            last_due = cursor
            if count > MAX_DUE_SCAN_POINTS:
                raise ScheduleError(
                    "计划错过的到期点超过安全扫描上限",
                    error_id="schedule.trigger_history_limit",
                    action="edit_schedule",
                )
            next_due = self._next_due_after(plan, cursor)
            if next_due is None:
                return first_due_ms, last_due, count, None
            cursor = next_due
        return first_due_ms, last_due, count, cursor

    def process_due(
        self,
        *,
        trigger_source: str = "timer",
        now: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        """Materialize all due plans and submit eligible local dispatches.

        ``timer`` is the normal system wake path and runs one bounded latest
        occurrence.  ``recovery`` is explicit Agent restart/recovery and applies
        the configured skip/catch-up rule.  No background thread is created by
        this core; Windows/Android wake integration owns calling this method.
        """

        if trigger_source not in {"timer", "recovery"}:
            raise ScheduleError(
                "触发来源只能是 timer 或 recovery",
                error_id="schedule.trigger_source_invalid",
            )
        now_ms = _utc_ms(_parse_utc_datetime(now or self.clock.now(), label="发现时间"))
        created: list[str] = []
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM schedule_plans
                     WHERE enabled=1 AND deleted_at_ms IS NULL
                       AND next_due_at_ms IS NOT NULL AND next_due_at_ms <= ?
                     ORDER BY next_due_at_ms, schedule_id
                    """,
                    (now_ms,),
                ).fetchall()
                for row in rows:
                    plan = self._plan_from_row(row)
                    first_due, last_due, due_count, next_due = self._due_span(
                        plan,
                        int(row["next_due_at_ms"]),
                        now_ms,
                    )
                    if due_count < 1:
                        continue
                    should_dispatch = True
                    reason_code: str | None = None
                    occurrence_source = trigger_source
                    if trigger_source == "recovery":
                        lateness_ms = max(0, now_ms - last_due)
                        if plan["misfire_policy"] == "skip":
                            should_dispatch = False
                            reason_code = "schedule.misfire_skipped"
                        elif lateness_ms > int(plan["max_lateness_seconds"]) * 1000:
                            should_dispatch = False
                            reason_code = "schedule.catch_up_window_expired"
                        else:
                            occurrence_source = "recovery_catch_up"
                    active = connection.execute(
                        """
                        SELECT occurrence_id FROM schedule_occurrences
                         WHERE schedule_id=? AND status IN ('pending','dispatching','accepted','running','queued_overlap')
                         ORDER BY created_at_ms LIMIT 1
                        """,
                        (plan["schedule_id"],),
                    ).fetchone()
                    initial_status = "pending" if should_dispatch else "skipped"
                    if should_dispatch and active is not None:
                        if plan["overlap_policy"] == "skip":
                            should_dispatch = False
                            initial_status = "skipped"
                            reason_code = "schedule.overlap_skipped"
                        else:
                            already_queued = connection.execute(
                                """
                                SELECT occurrence_id FROM schedule_occurrences
                                 WHERE schedule_id=? AND status='queued_overlap' LIMIT 1
                                """,
                                (plan["schedule_id"],),
                            ).fetchone()
                            if already_queued is None:
                                initial_status = "queued_overlap"
                            else:
                                should_dispatch = False
                                initial_status = "skipped"
                                reason_code = "schedule.overlap_queue_already_exists"
                    occurrence_id = _hash_id(
                        "occurrence",
                        plan["schedule_id"],
                        str(plan["revision"]),
                        str(last_due),
                        occurrence_source,
                    )
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO schedule_occurrences(
                            occurrence_id, schedule_id, schedule_revision,
                            scheduled_at_ms, discovered_at_ms, first_due_at_ms,
                            last_due_at_ms, collapsed_due_count, trigger_source,
                            entry_snapshot_json, status, reason_code,
                            created_at_ms, updated_at_ms
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            occurrence_id, plan["schedule_id"], plan["revision"],
                            last_due, now_ms, first_due, last_due, due_count,
                            occurrence_source, _canonical_json(plan["entries"]),
                            initial_status, reason_code, now_ms, now_ms,
                        ),
                    )
                    inserted = connection.execute("SELECT changes()").fetchone()[0] == 1
                    if inserted:
                        created.append(occurrence_id)
                        self._diagnostic(
                            connection,
                            now_ms,
                            event_type="occurrence.created",
                            schedule_id=plan["schedule_id"],
                            occurrence_id=occurrence_id,
                            error_id=reason_code,
                            details={
                                "schedule_revision": plan["revision"],
                                "trigger_source": occurrence_source,
                                "collapsed_due_count": due_count,
                                "status": initial_status,
                            },
                            level="warning" if reason_code else "info",
                        )
                        if initial_status == "pending":
                            self._insert_dispatches(connection, plan, occurrence_id, last_due, now_ms)
                    enabled = int(bool(plan["enabled"]) and next_due is not None)
                    connection.execute(
                        """
                        UPDATE schedule_plans
                           SET enabled=?, next_due_at_ms=?, last_processed_due_at_ms=?, updated_at_ms=?
                         WHERE schedule_id=? AND revision=?
                        """,
                        (enabled, next_due, last_due, now_ms, plan["schedule_id"], plan["revision"]),
                    )
                connection.commit()
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc
        self.pump(now=now)
        return [self.get_occurrence(item) for item in created]

    def _insert_dispatches(
        self,
        connection: sqlite3.Connection,
        plan: Mapping[str, Any],
        occurrence_id: str,
        scheduled_at_ms: int,
        now_ms: int,
    ) -> None:
        inserted = 0
        for entry in plan["entries"]:
            if not entry.get("enabled", True):
                continue
            dispatch_id = _hash_id("dispatch", occurrence_id, str(entry["entry_id"]))
            offset_seconds = int(entry.get("start_offset_seconds") or 0)
            not_before = scheduled_at_ms + offset_seconds * 1000
            deadline_seconds = entry.get("start_deadline_seconds")
            deadline = None if deadline_seconds is None else scheduled_at_ms + int(deadline_seconds) * 1000
            request = {
                "dispatch_id": dispatch_id,
                "occurrence_id": occurrence_id,
                "schedule_id": plan["schedule_id"],
                "schedule_revision": plan["revision"],
                "entry_id": entry["entry_id"],
                "host_id": entry["host_id"],
                "instance_id": entry["instance_id"],
                "product_id": entry["product_id"],
                "profile_id": entry["profile_id"],
            }
            request_json = _canonical_json(request)
            connection.execute(
                """
                INSERT INTO schedule_dispatches(
                    dispatch_id, occurrence_id, schedule_id, schedule_revision,
                    entry_id, entry_order, host_id, instance_id, product_id,
                    profile_id, request_json, request_hash, not_before_at_ms,
                    deadline_at_ms, status, run_id, error_id, error_message,
                    lease_until_ms, created_at_ms, updated_at_ms
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending',
                         NULL, NULL, NULL, NULL, ?, ?)
                """,
                (
                    dispatch_id, occurrence_id, plan["schedule_id"], plan["revision"],
                    entry["entry_id"], int(entry["order"]), entry["host_id"],
                    entry["instance_id"], entry["product_id"], entry["profile_id"],
                    request_json, hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
                    not_before, deadline, now_ms, now_ms,
                ),
            )
            inserted += 1
        if inserted == 0:
            connection.execute(
                """
                UPDATE schedule_occurrences
                   SET status='completed', reason_code='schedule.no_enabled_entries', updated_at_ms=?
                 WHERE occurrence_id=?
                """,
                (now_ms, occurrence_id),
            )
        return inserted

    def _request_from_row(self, row: sqlite3.Row, now_ms: int) -> LocalDispatchRequest:
        payload = json.loads(row["request_json"])
        return LocalDispatchRequest(
            dispatch_id=str(payload["dispatch_id"]),
            occurrence_id=str(payload["occurrence_id"]),
            schedule_id=str(payload["schedule_id"]),
            schedule_revision=int(payload["schedule_revision"]),
            entry_id=str(payload["entry_id"]),
            host_id=str(payload["host_id"]),
            instance_id=str(payload["instance_id"]),
            product_id=str(payload["product_id"]),
            profile_id=str(payload["profile_id"]),
            requested_at=str(_iso_ms(now_ms)),
        )

    def _promote_overlap(self, connection: sqlite3.Connection, now_ms: int) -> None:
        queued = connection.execute(
            """
            SELECT * FROM schedule_occurrences
             WHERE status='queued_overlap'
             ORDER BY created_at_ms, occurrence_id
            """
        ).fetchall()
        for occurrence in queued:
            other = connection.execute(
                """
                SELECT 1 FROM schedule_occurrences
                 WHERE schedule_id=? AND occurrence_id<>?
                   AND status IN ('pending','dispatching','accepted','running')
                 LIMIT 1
                """,
                (occurrence["schedule_id"], occurrence["occurrence_id"]),
            ).fetchone()
            if other is not None:
                continue
            entries = json.loads(occurrence["entry_snapshot_json"])
            plan = {
                "schedule_id": occurrence["schedule_id"],
                "revision": int(occurrence["schedule_revision"]),
                "entries": entries,
            }
            inserted = self._insert_dispatches(
                connection,
                plan,
                str(occurrence["occurrence_id"]),
                int(occurrence["scheduled_at_ms"]),
                now_ms,
            )
            if inserted:
                connection.execute(
                    """
                    UPDATE schedule_occurrences
                       SET status='pending', reason_code=NULL, updated_at_ms=?
                     WHERE occurrence_id=? AND status='queued_overlap'
                    """,
                    (now_ms, occurrence["occurrence_id"]),
                )
            self._diagnostic(
                connection,
                now_ms,
                event_type="occurrence.overlap_promoted",
                schedule_id=str(occurrence["schedule_id"]),
                occurrence_id=str(occurrence["occurrence_id"]),
                details={"entry_count": len(entries)},
            )

    def _refresh_occurrence(self, connection: sqlite3.Connection, occurrence_id: str, now_ms: int) -> None:
        rows = connection.execute(
            "SELECT status FROM schedule_dispatches WHERE occurrence_id=?",
            (occurrence_id,),
        ).fetchall()
        if not rows:
            return
        statuses = [str(row["status"]) for row in rows]
        if any(status in {"running", "paused", "stopping"} for status in statuses):
            status = "running"
        elif any(status in {"accepted", "starting"} for status in statuses):
            status = "accepted"
        elif any(status in {"pending", "queued", "dispatching"} for status in statuses):
            status = "pending"
        elif all(item == "completed" for item in statuses):
            status = "completed"
        elif all(item in _TERMINAL_DISPATCH_STATUSES for item in statuses):
            status = "failed" if not any(item == "completed" for item in statuses) else "partial_failed"
        else:
            status = "pending"
        connection.execute(
            "UPDATE schedule_occurrences SET status=?, updated_at_ms=? WHERE occurrence_id=?",
            (status, now_ms, occurrence_id),
        )

    def pump(self, *, now: datetime | str | None = None) -> list[dict[str, Any]]:
        """Dispatch one FIFO head per currently free local instance."""

        now_ms = _utc_ms(_parse_utc_datetime(now or self.clock.now(), label="派发时间"))
        attempted: list[str] = []
        with self._lock:
            try:
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """
                        UPDATE schedule_dispatches
                           SET status='pending', lease_until_ms=NULL,
                               error_id='schedule.dispatch_lease_recovered',
                               error_message='上次派发交接中断，使用同一 dispatch_id 重新接纳',
                               updated_at_ms=?
                         WHERE status='dispatching' AND lease_until_ms IS NOT NULL AND lease_until_ms <= ?
                        """,
                        (now_ms, now_ms),
                    )
                    self._promote_overlap(connection, now_ms)
                    expired = connection.execute(
                        """
                        SELECT dispatch_id, occurrence_id FROM schedule_dispatches
                         WHERE status IN ('pending','queued')
                           AND deadline_at_ms IS NOT NULL AND deadline_at_ms < ?
                        """,
                        (now_ms,),
                    ).fetchall()
                    for row in expired:
                        connection.execute(
                            """
                            UPDATE schedule_dispatches
                               SET status='expired', error_id='schedule.dispatch_deadline_expired',
                                   error_message='条目已超过启动截止时间', updated_at_ms=?
                             WHERE dispatch_id=?
                            """,
                            (now_ms, row["dispatch_id"]),
                        )
                        self._refresh_occurrence(connection, str(row["occurrence_id"]), now_ms)
                    candidates = connection.execute(
                        """
                        SELECT * FROM schedule_dispatches
                         WHERE status IN ('pending','queued') AND not_before_at_ms <= ?
                           AND (deadline_at_ms IS NULL OR deadline_at_ms >= ?)
                         ORDER BY not_before_at_ms, created_at_ms, occurrence_id,
                                  entry_order, dispatch_id
                        """,
                        (now_ms, now_ms),
                    ).fetchall()
                    reserved: list[sqlite3.Row] = []
                    seen_instances: set[tuple[str, str]] = set()
                    for row in candidates:
                        instance_key = (str(row["host_id"]), str(row["instance_id"]))
                        if instance_key in seen_instances:
                            connection.execute(
                                "UPDATE schedule_dispatches SET status='queued', updated_at_ms=? WHERE dispatch_id=?",
                                (now_ms, row["dispatch_id"]),
                            )
                            continue
                        occupied = connection.execute(
                            """
                            SELECT 1 FROM schedule_dispatches
                             WHERE host_id=? AND instance_id=? AND dispatch_id<>?
                               AND status IN ('dispatching','accepted','starting','running','paused','stopping')
                             LIMIT 1
                            """,
                            (row["host_id"], row["instance_id"], row["dispatch_id"]),
                        ).fetchone()
                        if occupied is not None:
                            connection.execute(
                                "UPDATE schedule_dispatches SET status='queued', updated_at_ms=? WHERE dispatch_id=?",
                                (now_ms, row["dispatch_id"]),
                            )
                            continue
                        connection.execute(
                            """
                            UPDATE schedule_dispatches
                               SET status='dispatching', lease_until_ms=?, updated_at_ms=?
                             WHERE dispatch_id=? AND status IN ('pending','queued')
                            """,
                            (now_ms + DISPATCH_LEASE_MS, now_ms, row["dispatch_id"]),
                        )
                        if connection.execute("SELECT changes()").fetchone()[0] == 1:
                            reserved.append(row)
                            seen_instances.add(instance_key)
                    connection.commit()
                for row in reserved:
                    attempted.append(str(row["dispatch_id"]))
                    request = self._request_from_row(row, now_ms)
                    try:
                        accepted = self.dispatcher.accept(request)
                        if accepted.dispatch_id != request.dispatch_id or not accepted.run_id:
                            raise ScheduleError(
                                "Execution Service 返回了不匹配的派发身份",
                                error_id="schedule.execution_identity_mismatch",
                            )
                    except ScheduleError as exc:
                        status = "pending" if exc.transient else "rejected"
                        with self._connect() as connection:
                            connection.execute("BEGIN IMMEDIATE")
                            connection.execute(
                                """
                                UPDATE schedule_dispatches
                                   SET status=?, error_id=?, error_message=?, lease_until_ms=NULL,
                                       updated_at_ms=?
                                 WHERE dispatch_id=?
                                """,
                                (status, exc.error_id, str(exc), now_ms, request.dispatch_id),
                            )
                            self._refresh_occurrence(connection, request.occurrence_id, now_ms)
                            self._diagnostic(
                                connection,
                                now_ms,
                                level="warning" if exc.transient else "error",
                                event_type="dispatch.failed",
                                schedule_id=request.schedule_id,
                                occurrence_id=request.occurrence_id,
                                dispatch_id=request.dispatch_id,
                                error_id=exc.error_id,
                                details={"transient": exc.transient, "status": status},
                            )
                            connection.commit()
                        continue
                    except Exception:
                        wrapped = ScheduleError(
                            "本机派发接点发生未分类失败",
                            error_id="schedule.execution_adapter_failed",
                            transient=True,
                            action="retry",
                        )
                        with self._connect() as connection:
                            connection.execute("BEGIN IMMEDIATE")
                            connection.execute(
                                """
                                UPDATE schedule_dispatches
                                   SET status='pending', error_id=?, error_message=?, lease_until_ms=NULL,
                                       updated_at_ms=? WHERE dispatch_id=?
                                """,
                                (wrapped.error_id, str(wrapped), now_ms, request.dispatch_id),
                            )
                            self._refresh_occurrence(connection, request.occurrence_id, now_ms)
                            connection.commit()
                        continue
                    with self._connect() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        connection.execute(
                            """
                            UPDATE schedule_dispatches
                               SET status='accepted', run_id=?, error_id=NULL,
                                   error_message=NULL, lease_until_ms=NULL, updated_at_ms=?
                             WHERE dispatch_id=?
                            """,
                            (accepted.run_id, now_ms, request.dispatch_id),
                        )
                        self._refresh_occurrence(connection, request.occurrence_id, now_ms)
                        self._diagnostic(
                            connection,
                            now_ms,
                            event_type="dispatch.accepted",
                            schedule_id=request.schedule_id,
                            occurrence_id=request.occurrence_id,
                            dispatch_id=request.dispatch_id,
                            run_id=accepted.run_id,
                            details={"instance_id": request.instance_id},
                        )
                        connection.commit()
            except sqlite3.Error as exc:
                raise _translate_sqlite(exc) from exc
        return [self.get_dispatch(item) for item in attempted]

    def record_run_status(
        self,
        dispatch_id: str,
        run_id: str,
        status: str,
        *,
        error_id: str = "",
        error_message: str = "",
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Record an ordinary Execution Service state and release FIFO on terminal."""

        dispatch_id = _validate_id(dispatch_id, "派发 ID")
        run_id = _validate_id(run_id, "运行 ID")
        normalized_status = str(status or "").strip()
        allowed = {
            "accepted", "starting", "running", "paused", "stopping",
            "completed", "failed", "stopped",
        }
        if normalized_status not in allowed:
            raise ScheduleError(
                "运行状态不受支持",
                error_id="schedule.run_status_invalid",
            )
        now_ms = _utc_ms(_parse_utc_datetime(now or self.clock.now(), label="运行状态时间"))
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM schedule_dispatches WHERE dispatch_id=?",
                    (dispatch_id,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise ScheduleError(
                        "派发记录不存在",
                        error_id="schedule.dispatch_not_found",
                    )
                if str(row["run_id"] or "") != run_id:
                    connection.rollback()
                    raise ScheduleError(
                        "运行 ID 与派发记录不匹配",
                        error_id="schedule.run_identity_mismatch",
                    )
                current = str(row["status"])
                if current in _TERMINAL_DISPATCH_STATUSES:
                    if current != normalized_status:
                        connection.rollback()
                        raise ScheduleError(
                            "终态派发记录不能改写为其他结果",
                            error_id="schedule.run_terminal_conflict",
                        )
                    connection.commit()
                    return self._dispatch_from_row(row)
                connection.execute(
                    """
                    UPDATE schedule_dispatches
                       SET status=?, error_id=?, error_message=?, updated_at_ms=?
                     WHERE dispatch_id=?
                    """,
                    (
                        normalized_status,
                        str(error_id or "") or None,
                        str(error_message or "")[:500] or None,
                        now_ms,
                        dispatch_id,
                    ),
                )
                self._refresh_occurrence(connection, str(row["occurrence_id"]), now_ms)
                self._diagnostic(
                    connection,
                    now_ms,
                    level="error" if normalized_status == "failed" else "info",
                    event_type=f"run.{normalized_status}",
                    schedule_id=str(row["schedule_id"]),
                    occurrence_id=str(row["occurrence_id"]),
                    dispatch_id=dispatch_id,
                    run_id=run_id,
                    error_id=str(error_id or "") or None,
                    details={"status": normalized_status},
                )
                self._promote_overlap(connection, now_ms)
                connection.commit()
            if normalized_status in _TERMINAL_DISPATCH_STATUSES:
                self.pump(now=now)
            return self.get_dispatch(dispatch_id)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def get_occurrence(self, occurrence_id: str) -> dict[str, Any]:
        occurrence_id = _validate_id(occurrence_id, "Occurrence ID")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM schedule_occurrences WHERE occurrence_id=?",
                    (occurrence_id,),
                ).fetchone()
            if row is None:
                raise ScheduleError(
                    "Occurrence 不存在",
                    error_id="schedule.occurrence_not_found",
                )
            return self._occurrence_from_row(row)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def list_occurrences(
        self,
        *,
        schedule_id: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 2_000))
        try:
            with self._connect() as connection:
                if schedule_id:
                    rows = connection.execute(
                        """
                        SELECT * FROM schedule_occurrences WHERE schedule_id=?
                         ORDER BY created_at_ms DESC, occurrence_id DESC LIMIT ?
                        """,
                        (_validate_id(schedule_id, "计划 ID"), limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT * FROM schedule_occurrences
                         ORDER BY created_at_ms DESC, occurrence_id DESC LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
            return [self._occurrence_from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any]:
        dispatch_id = _validate_id(dispatch_id, "派发 ID")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM schedule_dispatches WHERE dispatch_id=?",
                    (dispatch_id,),
                ).fetchone()
            if row is None:
                raise ScheduleError(
                    "派发记录不存在",
                    error_id="schedule.dispatch_not_found",
                )
            return self._dispatch_from_row(row)
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def list_dispatches(
        self,
        *,
        occurrence_id: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 5_000))
        try:
            with self._connect() as connection:
                if occurrence_id:
                    rows = connection.execute(
                        """
                        SELECT * FROM schedule_dispatches WHERE occurrence_id=?
                         ORDER BY entry_order, dispatch_id LIMIT ?
                        """,
                        (_validate_id(occurrence_id, "Occurrence ID"), limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT * FROM schedule_dispatches
                         ORDER BY created_at_ms DESC, entry_order LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
            return [self._dispatch_from_row(row) for row in rows]
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc

    def _diagnostic(
        self,
        connection: sqlite3.Connection,
        recorded_at_ms: int,
        *,
        event_type: str,
        schedule_id: str | None = None,
        occurrence_id: str | None = None,
        dispatch_id: str | None = None,
        run_id: str | None = None,
        error_id: str | None = None,
        details: Mapping[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        safe_details: dict[str, Any] = {}
        for key, value in dict(details or {}).items():
            if key in {
                "profile_values", "message_content", "http_body", "pairing_code",
                "private_key", "authorization", "token", "secret",
            }:
                continue
            if isinstance(value, (str, int, float, bool, type(None))):
                safe_details[str(key)] = value
        connection.execute(
            """
            INSERT INTO schedule_diagnostics(
                recorded_at_ms, level, category, event_type, schedule_id,
                occurrence_id, dispatch_id, run_id, error_id, details_json
            ) VALUES(?, ?, 'schedule', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recorded_at_ms, level, event_type, schedule_id, occurrence_id,
                dispatch_id, run_id, error_id, _canonical_json(safe_details),
            ),
        )

    def list_diagnostics(self, *, after_sequence: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 5_000))
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM schedule_diagnostics WHERE sequence>?
                     ORDER BY sequence LIMIT ?
                    """,
                    (max(0, int(after_sequence)), limit),
                ).fetchall()
            return [{
                "sequence": int(row["sequence"]),
                "recorded_at": _iso_ms(int(row["recorded_at_ms"])),
                "level": str(row["level"]),
                "category": str(row["category"]),
                "event_type": str(row["event_type"]),
                "schedule_id": row["schedule_id"],
                "occurrence_id": row["occurrence_id"],
                "dispatch_id": row["dispatch_id"],
                "run_id": row["run_id"],
                "error_id": row["error_id"],
                "details": json.loads(row["details_json"]),
            } for row in rows]
        except sqlite3.Error as exc:
            raise _translate_sqlite(exc) from exc


_default_service_lock = threading.Lock()
_default_service: ScheduleServiceV6 | None = None


def get_schedule_service_v6() -> ScheduleServiceV6:
    global _default_service
    with _default_service_lock:
        expected_path = default_schedule_database_path().resolve()
        if _default_service is None or _default_service.database_path != expected_path:
            _default_service = ScheduleServiceV6(expected_path)
        return _default_service


def reset_schedule_service_v6_for_tests() -> None:
    global _default_service
    with _default_service_lock:
        _default_service = None
