"""Verified v6 update client, durable policy gate, and recoverable installers.

The client is deliberately transport-agnostic.  Production uses ordinary
HTTPS GET/Range requests while tests and embedded hosts may inject the same
small transport contract.  No request is constructed when the product is
disabled.
"""

from __future__ import annotations

import contextlib
import email.utils
import hashlib
import json
import os
import platform as platform_module
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Protocol

from .bundle_signing_v6 import canonical_json_bytes
from .update_protocol_v6 import (
    UPDATE_DOMAINS,
    UPDATE_STATES,
    UpdateProtocolError,
    format_utc,
    parse_utc,
    rollout_eligible,
    sha256_bytes,
    validate_artifact,
    validate_required_policy,
    validate_rollout_policy,
    validate_targets_signed,
    verify_initial_root,
    verify_metadata_bytes,
    verify_role_envelope,
    verify_rotated_root,
    version_in_range,
)


class UpdateClientError(UpdateProtocolError):
    pass


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(dict(value)) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, default: Mapping[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateClientError("UPD-STATE-001", f"更新状态记录损坏：{path.name}") from exc
    if not isinstance(value, dict):
        raise UpdateClientError("UPD-STATE-001", f"更新状态记录格式无效：{path.name}")
    return value


def _safe_relative(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    value = PurePosixPath(normalized)
    if not normalized or value.is_absolute() or ".." in value.parts or ":" in value.parts[0]:
        raise UpdateClientError("UPD-NET-001", "更新源相对路径无效")
    return normalized


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: dict[str, str]
    body: bytes = b""
    bytes_written: int = 0


class UpdateTransport(Protocol):
    request_count: int

    def get(
        self,
        relative_path: str,
        *,
        headers: Mapping[str, str] | None = None,
        sink: BinaryIO | None = None,
        maximum_bytes: int | None = None,
    ) -> TransportResponse: ...


class HttpsUpdateTransport:
    """Minimal static-feed transport with redirects constrained to HTTPS."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0, allow_local_http: bool = False) -> None:
        self.allow_local_http = bool(allow_local_http)
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.request_count = 0
        self.set_base_url(base_url)

    def set_base_url(self, base_url: str) -> None:
        raw = str(base_url or "").strip().rstrip("/") + "/"
        parsed = urllib.parse.urlsplit(raw)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (self.allow_local_http and parsed.scheme == "http" and local):
            raise UpdateClientError("UPD-SOURCE-001", "更新源必须是 HTTPS；仅测试宿主可显式允许本机 HTTP")
        if parsed.username or parsed.password or not parsed.netloc:
            raise UpdateClientError("UPD-SOURCE-001", "更新源 URL 无效或包含凭据")
        self.base_url = raw

    def _url(self, relative_path: str) -> str:
        safe = _safe_relative(relative_path)
        url = urllib.parse.urljoin(self.base_url, urllib.parse.quote(safe, safe="/.-_"))
        base = urllib.parse.urlsplit(self.base_url)
        target = urllib.parse.urlsplit(url)
        if target.scheme != base.scheme or target.netloc != base.netloc:
            raise UpdateClientError("UPD-SOURCE-001", "更新请求越过固定源边界")
        return url

    def get(
        self,
        relative_path: str,
        *,
        headers: Mapping[str, str] | None = None,
        sink: BinaryIO | None = None,
        maximum_bytes: int | None = None,
    ) -> TransportResponse:
        request_headers = {"Accept": "application/json, application/octet-stream;q=0.9"}
        request_headers.update({str(key): str(value) for key, value in (headers or {}).items()})
        request = urllib.request.Request(self._url(relative_path), headers=request_headers, method="GET")
        self.request_count += 1
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            body = exc.read(64 * 1024)
            return TransportResponse(int(exc.code), {key.lower(): value for key, value in exc.headers.items()}, body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateClientError("UPD-NET-001", f"更新源不可达：{exc}") from exc
        with response:
            final = urllib.parse.urlsplit(response.geturl())
            original = urllib.parse.urlsplit(self.base_url)
            if final.scheme != original.scheme or final.netloc != original.netloc:
                raise UpdateClientError("UPD-SOURCE-001", "更新源重定向越过固定 HTTPS 边界")
            normalized_headers = {key.lower(): value for key, value in response.headers.items()}
            status = int(getattr(response, "status", 200))
            if sink is None:
                limit = 8 * 1024 * 1024 if maximum_bytes is None else int(maximum_bytes)
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise UpdateClientError("UPD-LIMIT-001", "更新元数据超过允许大小")
                return TransportResponse(status, normalized_headers, body)
            written = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if maximum_bytes is not None and written > maximum_bytes:
                    raise UpdateClientError("UPD-LIMIT-001", "更新产物超过签名声明大小")
                sink.write(chunk)
            return TransportResponse(status, normalized_headers, bytes_written=written)


class DirectoryUpdateTransport:
    """Static directory transport used by the reference feed and offline Harness."""

    def __init__(self, root: str | Path, *, failure_status: int = 0) -> None:
        self.root = Path(root).expanduser().resolve()
        self.failure_status = int(failure_status)
        self.request_count = 0
        self.paths: list[str] = []

    def get(
        self,
        relative_path: str,
        *,
        headers: Mapping[str, str] | None = None,
        sink: BinaryIO | None = None,
        maximum_bytes: int | None = None,
    ) -> TransportResponse:
        safe = _safe_relative(relative_path)
        self.request_count += 1
        self.paths.append(safe)
        if self.failure_status:
            return TransportResponse(self.failure_status, {})
        path = (self.root / Path(*PurePosixPath(safe).parts)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise UpdateClientError("UPD-SOURCE-001", "更新目录请求越界") from exc
        if not path.is_file():
            return TransportResponse(404, {})
        stat = path.stat()
        etag = f'"sha256-{sha256_bytes(path.read_bytes())}"'
        response_headers = {
            "etag": etag,
            "content-length": str(stat.st_size),
            "last-modified": email.utils.formatdate(stat.st_mtime, usegmt=True),
            "date": email.utils.formatdate(time.time(), usegmt=True),
            "accept-ranges": "bytes",
        }
        request_headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        if request_headers.get("if-none-match") == etag:
            return TransportResponse(304, response_headers)
        offset = 0
        status = 200
        raw_range = request_headers.get("range", "")
        if raw_range.startswith("bytes=") and raw_range.endswith("-"):
            try:
                offset = int(raw_range[6:-1])
            except ValueError:
                return TransportResponse(416, response_headers)
            if offset >= stat.st_size:
                return TransportResponse(416, response_headers)
            status = 206
            response_headers["content-range"] = f"bytes {offset}-{stat.st_size - 1}/{stat.st_size}"
            response_headers["content-length"] = str(stat.st_size - offset)
        with path.open("rb") as source:
            source.seek(offset)
            if sink is None:
                limit = 8 * 1024 * 1024 if maximum_bytes is None else int(maximum_bytes)
                body = source.read(limit + 1)
                if len(body) > limit:
                    raise UpdateClientError("UPD-LIMIT-001", "更新对象超过允许大小")
                return TransportResponse(status, response_headers, body)
            written = 0
            while chunk := source.read(1024 * 1024):
                written += len(chunk)
                if maximum_bytes is not None and written > maximum_bytes:
                    raise UpdateClientError("UPD-LIMIT-001", "更新对象超过允许大小")
                sink.write(chunk)
            return TransportResponse(status, response_headers, bytes_written=written)


@dataclass(frozen=True)
class UpdateClientConfig:
    enabled: bool
    product_id: str
    domain: str
    platform: str
    architecture: str
    current_release_id: str
    current_release_sequence: int
    runtime_version: str = "6.0.0"
    ecir_version: str = "6.0.0"
    channel: str = "stable"
    automatic_checks: bool = True
    required_policy_capability: bool = False
    feed_base_url: str = ""
    pinned_root: dict[str, Any] | None = None

    def validate(self) -> None:
        if self.domain not in UPDATE_DOMAINS:
            raise UpdateClientError("UPD-CONFIG-001", "更新产品域无效")
        if self.platform not in {"windows", "android"} or not self.architecture:
            raise UpdateClientError("UPD-CONFIG-001", "更新平台或架构无效")
        if self.channel not in {"test", "stable"}:
            raise UpdateClientError("UPD-CONFIG-001", "更新通道无效")
        if self.current_release_sequence < 0:
            raise UpdateClientError("UPD-CONFIG-001", "当前发布序号无效")
        if self.enabled and (not self.product_id or not isinstance(self.pinned_root, dict)):
            raise UpdateClientError("UPD-CONFIG-001", "启用更新必须固定 product_id 与离线信任根")
        if not self.enabled and (self.feed_base_url or self.pinned_root):
            raise UpdateClientError("UPD-CONFIG-002", "disabled 配置不得携带更新源或信任根")


class ProductGroupIdentity:
    """Per-product random cohort code; never included in an HTTP request."""

    def __init__(self, durable_root: str | Path, product_id: str) -> None:
        digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()
        self.path = Path(durable_root).expanduser().resolve() / "identity" / f"{digest}.json"
        self.product_id = product_id

    def get(self) -> str:
        if self.path.is_file():
            value = _read_json(self.path, {})
            code = str(value.get("group_code") or "")
            if value.get("product_id") != self.product_id or len(code) < 32:
                raise UpdateClientError("UPD-IDENTITY-001", "更新分组身份记录损坏")
            return code
        code = secrets.token_urlsafe(32)
        _atomic_json(self.path, {"schema_version": 1, "product_id": self.product_id, "group_code": code})
        return code

    def reset(self) -> str:
        code = secrets.token_urlsafe(32)
        _atomic_json(self.path, {"schema_version": 1, "product_id": self.product_id, "group_code": code})
        return code


class UpdatePreferencesStore:
    """Terminal-owned ordinary-update preferences, isolated per product."""

    FIELDS = {"automatic_check", "automatic_download", "automatic_apply"}

    def __init__(self, durable_root: str | Path, product_id: str) -> None:
        digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()
        self.path = Path(durable_root).expanduser().resolve() / "preferences" / f"{digest}.json"
        self.product_id = product_id

    def get(self, initial: Mapping[str, Any]) -> dict[str, bool]:
        defaults = {field: bool(initial.get(field)) for field in self.FIELDS}
        if not self.path.is_file():
            _atomic_json(
                self.path,
                {"schema_version": 1, "product_id": self.product_id, "preferences": defaults},
            )
            return defaults
        value = _read_json(self.path, {})
        raw = value.get("preferences")
        if (
            value.get("schema_version") != 1
            or value.get("product_id") != self.product_id
            or not isinstance(raw, dict)
            or set(raw) != self.FIELDS
            or any(not isinstance(item, bool) for item in raw.values())
        ):
            raise UpdateClientError("UPD-PREFERENCES-001", "终端更新偏好记录损坏")
        return {field: bool(raw[field]) for field in self.FIELDS}

    def save(self, preferences: Mapping[str, Any]) -> dict[str, bool]:
        if set(preferences) != self.FIELDS or any(not isinstance(item, bool) for item in preferences.values()):
            raise UpdateClientError("UPD-PREFERENCES-001", "终端更新偏好字段无效")
        normalized = {field: bool(preferences[field]) for field in self.FIELDS}
        _atomic_json(
            self.path,
            {"schema_version": 1, "product_id": self.product_id, "preferences": normalized},
        )
        return normalized


class CrossProcessFileLock:
    """One-byte advisory lock used to serialize download and slot transitions."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 10.0) -> None:
        self.path = Path(path)
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self._stream: BinaryIO | None = None

    def __enter__(self) -> CrossProcessFileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        stream.seek(0)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._stream = stream
                return self
            except OSError as exc:
                if time.monotonic() >= deadline:
                    stream.close()
                    raise UpdateClientError("UPD-LOCK-001", "另一个实例正在处理同一更新") from exc
                time.sleep(0.05)

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()
            self._stream = None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class ProcessLeaseRegistry:
    """Conservative multi-instance safe-point registry for one product domain."""

    def __init__(self, root: str | Path, product_id: str, domain: str) -> None:
        suffix = hashlib.sha256(f"{product_id}:{domain}".encode()).hexdigest()
        self.root = Path(root).expanduser().resolve() / "leases" / suffix
        self.lease_id = f"{os.getpid()}-{uuid.uuid4().hex}"
        self.path = self.root / f"{self.lease_id}.json"

    def register(self, *, release_id: str, safe: bool = True, uncommitted_draft: bool = False) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_json(
            self.path,
            {
                "schema_version": 1,
                "lease_id": self.lease_id,
                "pid": os.getpid(),
                "release_id": release_id,
                "safe": bool(safe),
                "uncommitted_draft": bool(uncommitted_draft),
                "heartbeat_at": format_utc(datetime.now(timezone.utc)),
            },
        )
        return self.lease_id

    def update(self, *, release_id: str, safe: bool, uncommitted_draft: bool = False) -> None:
        self.register(release_id=release_id, safe=safe, uncommitted_draft=uncommitted_draft)

    def unregister(self) -> None:
        self.path.unlink(missing_ok=True)

    def all_safe(self) -> bool:
        if not self.root.is_dir():
            return True
        for path in self.root.glob("*.json"):
            try:
                value = _read_json(path, {})
                pid = int(value.get("pid") or 0)
            except (UpdateClientError, ValueError, TypeError):
                return False
            if not _pid_alive(pid):
                path.unlink(missing_ok=True)
                continue
            if not bool(value.get("safe")) or bool(value.get("uncommitted_draft")):
                return False
        return True


@dataclass
class UpdateSnapshot:
    root: dict[str, Any]
    timestamp: dict[str, Any]
    snapshot: dict[str, Any]
    targets: dict[str, Any] | None
    rollout: dict[str, Any] | None
    policy: dict[str, Any]
    not_modified: bool = False


@dataclass
class PlatformInstallResult:
    accepted: bool
    completed: bool = False
    requires_user_action: bool = False
    message: str = ""


class PlatformInstaller(Protocol):
    def stage(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any]) -> PlatformInstallResult: ...

    def apply(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any]) -> PlatformInstallResult: ...


class UnavailablePlatformInstaller:
    def __init__(self, boundary: str) -> None:
        self.boundary = boundary

    def stage(self, _artifact_path: Path, _artifact: Mapping[str, Any], _release: Mapping[str, Any]) -> PlatformInstallResult:
        return PlatformInstallResult(False, message=f"{self.boundary} 尚未接入当前宿主")

    def apply(self, _artifact_path: Path, _artifact: Mapping[str, Any], _release: Mapping[str, Any]) -> PlatformInstallResult:
        return PlatformInstallResult(False, message=f"{self.boundary} 尚未接入当前宿主")


class CommandPlatformInstaller:
    """External installer boundary with an explicit, durable handoff contract.

    ``install_root`` and ``restart_command`` are supplied by the installed host,
    never by signed feed metadata, so an update cannot choose arbitrary local
    paths or executables.
    """

    def __init__(
        self,
        command: list[str],
        handoff_root: str | Path,
        *,
        install_root: str | Path | None = None,
        restart_command: list[str] | None = None,
        parent_pid: int | None = None,
    ) -> None:
        if not command:
            raise ValueError("command is required")
        self.command = [str(item) for item in command]
        self.handoff_root = Path(handoff_root).expanduser().resolve()
        self.install_root = Path(install_root).expanduser().resolve() if install_root else None
        self.restart_command = [str(item) for item in (restart_command or [])]
        self.parent_pid = os.getpid() if parent_pid is None else int(parent_pid)

    def _handoff(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any], action: str) -> Path:
        self.handoff_root.mkdir(parents=True, exist_ok=True)
        release_key = hashlib.sha256(str(release["release_id"]).encode("utf-8")).hexdigest()
        path = self.handoff_root / f"{release_key}-{action}.json"
        document: dict[str, Any] = {
                "schema_version": 2 if self.install_root is not None else 1,
                "action": action,
                "artifact_path": str(artifact_path.resolve()),
                "artifact_sha256": str((artifact.get("hashes") or {}).get("sha256") or ""),
                "artifact_length": int(artifact.get("length") or 0),
                "release_id": str(release.get("release_id") or ""),
                "release_sequence": int(release.get("release_sequence") or 0),
                "install_boundary": str(artifact.get("install_boundary") or ""),
        }
        if self.install_root is not None:
            if not self.restart_command:
                raise ValueError("restart_command is required for a Windows install handoff")
            document.update(
                install_root=str(self.install_root),
                restart_command=list(self.restart_command),
                parent_pid=self.parent_pid,
                handoff_root=str(self.handoff_root),
            )
        _atomic_json(path, document)
        return path

    def confirmation(self, release: Mapping[str, Any]) -> bool | None:
        """Return a verified helper result, or ``None`` while still pending."""

        release_key = hashlib.sha256(str(release.get("release_id") or "").encode("utf-8")).hexdigest()
        receipt = self.handoff_root / "receipts" / f"{release_key}.json"
        if not receipt.is_file():
            return None
        try:
            value = _read_json(receipt, {})
        except UpdateClientError:
            return False
        expected = {
            "schema_version", "release_id", "release_sequence", "artifact_sha256", "status",
        }
        artifact_hashes = {
            str((item.get("hashes") or {}).get("sha256") or "")
            for item in (release.get("artifacts") or [])
            if isinstance(item, Mapping)
        }
        identity_matches = bool(
            expected.issubset(value)
            and value.get("schema_version") == 1
            and value.get("release_id") == release.get("release_id")
            and int(value.get("release_sequence") or 0) == int(release.get("release_sequence") or 0)
            and value.get("artifact_sha256") in artifact_hashes
        )
        if not identity_matches:
            return False
        return value.get("status") == "healthy"

    def _run(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any], action: str) -> PlatformInstallResult:
        handoff = self._handoff(artifact_path, artifact, release, action)
        try:
            result = subprocess.run(
                [*self.command, "--handoff", str(handoff)],
                capture_output=True,
                text=True,
                timeout=600 if action == "stage" else 30,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PlatformInstallResult(False, message=f"平台安装边界调用失败：{exc}")
        message = (result.stdout or result.stderr or "").strip()[:1000]
        if result.returncode == 10:
            return PlatformInstallResult(True, requires_user_action=True, message=message or "等待平台安装确认")
        return PlatformInstallResult(result.returncode == 0, completed=result.returncode == 0, message=message)

    def stage(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any]) -> PlatformInstallResult:
        return self._run(artifact_path, artifact, release, "stage")

    def apply(self, artifact_path: Path, artifact: Mapping[str, Any], release: Mapping[str, Any]) -> PlatformInstallResult:
        return self._run(artifact_path, artifact, release, "apply")


class AtomicContentSlots:
    """A/B bundle slots with an atomic pointer and local health rollback."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.pointer = self.root / "active-slot.json"

    def _pointer(self) -> dict[str, Any]:
        value = _read_json(
            self.pointer,
            {"schema_version": 1, "active_slot": "A", "previous_slot": "", "slots": {"A": None, "B": None}},
        )
        if value.get("active_slot") not in {"A", "B"} or not isinstance(value.get("slots"), dict):
            raise UpdateClientError("UPD-SLOT-001", "内容槽指针损坏")
        return value

    def status(self) -> dict[str, Any]:
        return self._pointer()

    def inactive_slot(self) -> str:
        return "B" if self._pointer()["active_slot"] == "A" else "A"

    def stage(self, artifact_path: Path, release: Mapping[str, Any]) -> tuple[str, Path]:
        pointer = self._pointer()
        slot = "B" if pointer["active_slot"] == "A" else "A"
        directory = self.root / "slots" / slot
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / "bundle.ecplayer"
        temporary = directory / f".bundle.{uuid.uuid4().hex}.tmp"
        try:
            shutil.copyfile(artifact_path, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        slot_record = {
            "release_id": str(release["release_id"]),
            "release_sequence": int(release["release_sequence"]),
            "bundle_path": str(destination),
            "verified": False,
        }
        slots = dict(pointer["slots"])
        slots[slot] = slot_record
        pointer["slots"] = slots
        _atomic_json(self.pointer, pointer)
        return slot, destination

    def activate(self, slot: str, *, health_check: Callable[[Path], bool]) -> dict[str, Any]:
        pointer = self._pointer()
        if slot not in {"A", "B"} or not isinstance(pointer["slots"].get(slot), dict):
            raise UpdateClientError("UPD-SLOT-001", "待切换内容槽不存在")
        previous = str(pointer["active_slot"])
        bundle = Path(str(pointer["slots"][slot]["bundle_path"]))
        slots = dict(pointer["slots"])
        slots[slot] = {**slots[slot], "verified": True}
        next_pointer = {
            "schema_version": 1,
            "active_slot": slot,
            "previous_slot": previous,
            "slots": slots,
        }
        _atomic_json(self.pointer, next_pointer)
        if not health_check(bundle):
            # Restore the exact previous pointer, including the first-install
            # case where the packaged bundle is not represented as a slot.
            _atomic_json(self.pointer, pointer)
            raise UpdateClientError("UPD-HEALTH-001", "新内容槽启动健康检查失败，已恢复上一槽")
        return next_pointer

    def rollback(self) -> dict[str, Any]:
        pointer = self._pointer()
        previous = str(pointer.get("previous_slot") or "")
        if previous not in {"A", "B"} or not isinstance(pointer["slots"].get(previous), dict):
            raise UpdateClientError("UPD-ROLLBACK-002", "没有可恢复的上一正常内容槽")
        current = pointer["active_slot"]
        pointer["active_slot"] = previous
        pointer["previous_slot"] = current
        _atomic_json(self.pointer, pointer)
        return pointer


@dataclass
class UpdateCheckResult:
    state: str
    checked: bool
    available: bool
    release: dict[str, Any] | None = None
    artifact: dict[str, Any] | None = None
    required_policy: dict[str, Any] | None = None
    message: str = ""
    not_modified: bool = False


class UpdateClient:
    """One update product/domain state machine.

    ``durable_root`` contains trust floors and the last verified required
    policy.  ``cache_root`` may be deleted without weakening that policy.
    """

    STATE_SCHEMA_VERSION = 1
    MAX_METADATA_BYTES = 4 * 1024 * 1024
    DOWNLOAD_RESERVE_BYTES = 32 * 1024 * 1024

    def __init__(
        self,
        config: UpdateClientConfig,
        *,
        durable_root: str | Path,
        cache_root: str | Path,
        transport: UpdateTransport | None = None,
        installer: PlatformInstaller | None = None,
        health_check: Callable[[Path], bool] | None = None,
        now: Callable[[], datetime] | None = None,
        random_seconds: Callable[[float, float], float] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.durable_root = Path(durable_root).expanduser().resolve()
        self.cache_root = Path(cache_root).expanduser().resolve()
        suffix = hashlib.sha256(f"{config.product_id}:{config.domain}".encode()).hexdigest()
        self.durable_domain = self.durable_root / "updates" / suffix
        self.cache_domain = self.cache_root / "updates" / suffix
        self.trust_path = self.durable_domain / "trust.json"
        self.state_path = self.durable_domain / "state.json"
        self.events_path = self.durable_domain / "events.ndjson"
        self.download_root = self.cache_domain / "downloads"
        self.metadata_root = self.cache_domain / "metadata"
        self.lock_path = self.durable_domain / "update.lock"
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._random_seconds = random_seconds or __import__("random").uniform
        self.transport = transport
        if config.enabled and self.transport is None:
            self.transport = HttpsUpdateTransport(config.feed_base_url)
        self.installer = installer or UnavailablePlatformInstaller(
            "Android PackageInstaller" if config.platform == "android" else "Windows Update Helper"
        )
        self.health_check = health_check or (lambda path: path.is_file() and path.stat().st_size > 0)
        self.identity = ProductGroupIdentity(self.durable_root, config.product_id) if config.enabled else None
        self.leases = ProcessLeaseRegistry(self.durable_root, config.product_id, config.domain)
        self.slots = AtomicContentSlots(self.durable_domain / "content")
        self._thread_lock = threading.RLock()
        if not config.enabled:
            self._state = self._default_state("disabled")
            return
        self.durable_domain.mkdir(parents=True, exist_ok=True)
        self.cache_domain.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()
        self._ensure_trust()
        schedule_changed = False
        scheduled_now = self.trusted_now()
        if config.automatic_checks and not self._state.get("next_optional_check_at"):
            self._state["next_optional_check_at"] = format_utc(
                scheduled_now + timedelta(seconds=self._random_seconds(60, 600))
            )
            schedule_changed = True
        if config.required_policy_capability and not self._state.get("next_policy_check_at"):
            self._state["next_policy_check_at"] = format_utc(
                scheduled_now + timedelta(seconds=self._random_seconds(600, 3600))
            )
            schedule_changed = True
        if schedule_changed:
            self._save_state()

    def _default_state(self, state: str = "idle") -> dict[str, Any]:
        return {
            "schema_version": self.STATE_SCHEMA_VERSION,
            "state": state,
            "current_release_id": self.config.current_release_id,
            "current_release_sequence": self.config.current_release_sequence,
            "selected_release": None,
            "selected_artifact": None,
            "download_path": "",
            "staged_slot": "",
            "platform_message": "",
            "last_error": None,
            "last_checked_at": "",
            "last_verified_fresh": False,
            "optional_failures": 0,
            "policy_failures": 0,
            "next_optional_check_at": "",
            "next_policy_check_at": "",
        }

    def _load_state(self) -> dict[str, Any]:
        value = _read_json(self.state_path, self._default_state())
        if value.get("schema_version") != self.STATE_SCHEMA_VERSION or value.get("state") not in UPDATE_STATES:
            raise UpdateClientError("UPD-STATE-001", "更新状态版本或生命周期状态无效")
        # The installed host is authoritative after an out-of-band platform install.
        if self.config.current_release_sequence > int(value.get("current_release_sequence") or 0):
            value.update(
                current_release_id=self.config.current_release_id,
                current_release_sequence=self.config.current_release_sequence,
                selected_release=None,
                selected_artifact=None,
                download_path="",
                staged_slot="",
                state="idle",
            )
            self._save_state(value)
        return value

    def _save_state(self, value: Mapping[str, Any] | None = None) -> None:
        if not self.config.enabled:
            return
        _atomic_json(self.state_path, dict(value or self._state))

    def _event(self, event: str, **details: Any) -> None:
        if not self.config.enabled:
            return
        record = {
            "at": format_utc(self.trusted_now()),
            "event": event,
            "product_id": self.config.product_id,
            "domain": self.config.domain,
            "details": details,
        }
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("ab") as stream:
            stream.write(canonical_json_bytes(record) + b"\n")

    def _transition(self, state: str, *, error: UpdateProtocolError | None = None, **updates: Any) -> None:
        if state not in UPDATE_STATES:
            raise UpdateClientError("UPD-STATE-002", f"未知更新状态：{state}")
        self._state.update(updates)
        self._state["state"] = state
        self._state["last_error"] = (
            {"code": error.code, "message": str(error)} if error is not None else None
        )
        self._save_state()
        self._event("state.transition", state=state, error=self._state["last_error"])

    def status(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                **self._state,
                "enabled": False,
                "automatic_checks": False,
                "required_policy_capability": False,
                "can_start_task": True,
                "policy_block": None,
            }
        self._reconcile_platform_install()
        block = self.task_start_block()
        return {
            **self._state,
            "enabled": True,
            "automatic_checks": self.config.automatic_checks,
            "required_policy_capability": self.config.required_policy_capability,
            "can_start_task": block is None,
            "policy_block": block,
            "group_code_present": True,
            "active_content": self.slots.status(),
        }

    def _reconcile_platform_install(self) -> None:
        if self._state.get("state") not in {"awaiting_platform_install", "verifying"}:
            return
        release = self._state.get("selected_release")
        confirmation = getattr(self.installer, "confirmation", None)
        if not isinstance(release, dict) or not callable(confirmation):
            return
        healthy = confirmation(release)
        if healthy is None:
            return
        self.confirm_platform_install(
            release_id=str(release.get("release_id") or ""),
            release_sequence=int(release.get("release_sequence") or 0),
            healthy=bool(healthy),
        )

    def _default_trust(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "product_id": self.config.product_id,
            "domain": self.config.domain,
            "root": self.config.pinned_root,
            "highest_versions": {role: 0 for role in ("root", "timestamp", "snapshot", "targets", "rollout", "policy")},
            "role_hashes": {},
            "last_trusted_time": format_utc(_utc(self._now())),
            "last_required_policy": None,
            "initial_root_hash": sha256_bytes(canonical_json_bytes(self.config.pinned_root)),
            "highest_release_sequence": self.config.current_release_sequence,
            "rollout_policies": {},
            "etag": "",
        }

    def _ensure_trust(self) -> dict[str, Any]:
        if not self.config.enabled:
            raise UpdateClientError("UPD-DISABLED-001", "更新能力未启用")
        if self.trust_path.is_file():
            trust = _read_json(self.trust_path, {})
            if trust.get("product_id") != self.config.product_id or trust.get("domain") != self.config.domain:
                raise UpdateClientError("UPD-TRUST-001", "更新信任记录与产品域不匹配")
            root = trust.get("root")
            if not isinstance(root, dict):
                raise UpdateClientError("UPD-TRUST-001", "更新信任根记录缺失")
            expected_initial_hash = sha256_bytes(canonical_json_bytes(self.config.pinned_root))
            if trust.get("initial_root_hash") != expected_initial_hash:
                raise UpdateClientError("UPD-TRUST-001", "更新信任记录不源自安装时固定的信任根")
            verify_initial_root(root, product_id=self.config.product_id)
            return trust
        assert self.config.pinned_root is not None
        root_signed = verify_initial_root(self.config.pinned_root, product_id=self.config.product_id)
        mirrors = set(root_signed.get("mirrors") or [])
        if mirrors and self.config.feed_base_url.rstrip("/") not in {str(item).rstrip("/") for item in mirrors}:
            raise UpdateClientError("UPD-SOURCE-002", "安装时 Feed 不在固定信任根允许的镜像列表中")
        trust = self._default_trust()
        trust["highest_versions"]["root"] = int(root_signed["version"])
        _atomic_json(self.trust_path, trust)
        return trust

    def _trust(self) -> dict[str, Any]:
        return self._ensure_trust()

    def _write_trust(self, trust: Mapping[str, Any]) -> None:
        _atomic_json(self.trust_path, dict(trust))

    def trusted_now(self) -> datetime:
        current = _utc(self._now())
        if not self.config.enabled or not self.trust_path.is_file():
            return current
        trust = _read_json(self.trust_path, {})
        previous = parse_utc(trust.get("last_trusted_time"), field="last_trusted_time")
        return max(current, previous)

    def _advance_trust_time(self, trust: dict[str, Any], *candidates: Any) -> None:
        values = [self.trusted_now()]
        for candidate in candidates:
            if isinstance(candidate, datetime):
                values.append(_utc(candidate))
            elif candidate:
                with contextlib.suppress(UpdateProtocolError):
                    values.append(parse_utc(candidate, field="trusted_time"))
        trust["last_trusted_time"] = format_utc(max(values))

    def _parse_response_date(self, headers: Mapping[str, str]) -> datetime | None:
        raw = str(headers.get("date") or "")
        if not raw:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        return _utc(parsed)

    def _require_transport(self) -> UpdateTransport:
        if not self.config.enabled:
            raise UpdateClientError("UPD-DISABLED-001", "更新能力未启用；不会创建网络请求")
        if self.transport is None:
            raise UpdateClientError("UPD-NET-001", "更新传输未配置")
        return self.transport

    def _fetch_bytes(
        self,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        allow_not_modified: bool = False,
    ) -> TransportResponse:
        response = self._require_transport().get(
            path,
            headers=headers,
            maximum_bytes=self.MAX_METADATA_BYTES,
        )
        if response.status == 304 and allow_not_modified:
            return response
        if response.status != 200:
            if response.status >= 500:
                raise UpdateClientError("UPD-NET-5XX", f"更新源返回 {response.status}")
            raise UpdateClientError("UPD-NET-HTTP", f"更新源返回 {response.status}：{path}")
        return response

    @staticmethod
    def _decode_envelope(response: TransportResponse, *, name: str) -> dict[str, Any]:
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateClientError("UPD-META-001", f"{name} 不是有效 JSON") from exc
        if not isinstance(value, dict):
            raise UpdateClientError("UPD-META-001", f"{name} 签名信封格式无效")
        return value

    def _cache_metadata(self, name: str, content: bytes) -> None:
        path = self.metadata_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _cached_bytes(self, name: str) -> bytes:
        path = self.metadata_root / name
        if not path.is_file():
            raise UpdateClientError("UPD-CACHE-001", f"缓存缺少 {name}")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise UpdateClientError("UPD-CACHE-001", f"缓存 {name} 无法读取") from exc

    def _cached_envelope(self, name: str) -> dict[str, Any]:
        try:
            value = json.loads(self._cached_bytes(name))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise UpdateClientError("UPD-CACHE-001", f"缓存 {name} 损坏") from exc
        if not isinstance(value, dict):
            raise UpdateClientError("UPD-CACHE-001", f"缓存 {name} 格式无效")
        return value

    def _rotate_roots(self, trust: dict[str, Any]) -> dict[str, Any]:
        root = verify_initial_root(trust["root"], product_id=self.config.product_id)
        while True:
            next_version = int(root["version"]) + 1
            response = self._require_transport().get(
                f"metadata/{next_version}.root.json",
                maximum_bytes=self.MAX_METADATA_BYTES,
            )
            if response.status == 404:
                break
            if response.status != 200:
                raise UpdateClientError("UPD-NET-HTTP", f"信任根轮换检查返回 {response.status}")
            candidate = self._decode_envelope(response, name=f"{next_version}.root.json")
            root = verify_rotated_root(root, candidate, now=self.trusted_now())
            trust["root"] = candidate
            trust["highest_versions"]["root"] = int(root["version"])
            self._write_trust(trust)
            self._event("trust.root_rotated", version=root["version"])
        mirrors = [str(item).rstrip("/") for item in root.get("mirrors") or []]
        if mirrors and isinstance(self.transport, HttpsUpdateTransport):
            current = self.transport.base_url.rstrip("/")
            if current not in mirrors:
                self.transport.set_base_url(mirrors[0])
                self._event("source.migrated", base_url=mirrors[0])
        return root

    def _verify_role(
        self,
        envelope: Mapping[str, Any],
        *,
        root: Mapping[str, Any],
        role: str,
        trust: dict[str, Any],
    ) -> dict[str, Any]:
        floor = int((trust.get("highest_versions") or {}).get(role) or 0)
        signed = verify_role_envelope(
            envelope,
            root=root,
            role=role,
            product_id=self.config.product_id,
            domain=self.config.domain,
            minimum_version=floor,
            now=self.trusted_now(),
        )
        version = int(signed["version"])
        digest = sha256_bytes(canonical_json_bytes(signed))
        previous_hash = (trust.get("role_hashes") or {}).get(role)
        if (
            isinstance(previous_hash, dict)
            and int(previous_hash.get("version") or 0) == version
            and str(previous_hash.get("sha256") or "") != digest
        ):
            raise UpdateClientError("UPD-MIXMATCH-001", f"同一 {role} 元数据版本出现不同内容")
        trust.setdefault("role_hashes", {})[role] = {"version": version, "sha256": digest}
        trust["highest_versions"][role] = max(floor, int(signed["version"]))
        self._advance_trust_time(trust, signed.get("issued_at"))
        return signed

    def _load_cached_snapshot(self, *, policy_only: bool, root: Mapping[str, Any], trust: dict[str, Any]) -> UpdateSnapshot:
        snapshot_bytes = self._cached_bytes("snapshot.json")
        policy_bytes = self._cached_bytes("policy.json")
        timestamp_envelope = self._cached_envelope("timestamp.json")
        snapshot_envelope = self._cached_envelope("snapshot.json")
        policy_envelope = self._cached_envelope("policy.json")
        timestamp = self._verify_role(timestamp_envelope, root=root, role="timestamp", trust=trust)
        snapshot_record = (timestamp.get("meta") or {}).get("snapshot.json")
        if not isinstance(snapshot_record, dict):
            raise UpdateClientError("UPD-CACHE-001", "缓存 timestamp 缺少 snapshot 记录")
        verify_metadata_bytes(snapshot_bytes, snapshot_record, name="snapshot.json")
        snapshot = self._verify_role(snapshot_envelope, root=root, role="snapshot", trust=trust)
        meta = snapshot.get("meta")
        if not isinstance(meta, dict):
            raise UpdateClientError("UPD-CACHE-001", "缓存 snapshot.meta 无效")
        policy_record = meta.get("policy.json")
        if not isinstance(policy_record, dict):
            raise UpdateClientError("UPD-CACHE-001", "缓存 snapshot 缺少 policy.json")
        verify_metadata_bytes(policy_bytes, policy_record, name="policy.json")
        policy = self._verify_role(policy_envelope, root=root, role="policy", trust=trust)
        targets = rollout = None
        if not policy_only:
            targets_bytes = self._cached_bytes("targets.json")
            rollout_bytes = self._cached_bytes("rollout.json")
            for name, content in (("targets.json", targets_bytes), ("rollout.json", rollout_bytes)):
                record = meta.get(name)
                if not isinstance(record, dict):
                    raise UpdateClientError("UPD-CACHE-001", f"缓存 snapshot 缺少 {name}")
                verify_metadata_bytes(content, record, name=name)
            targets = self._verify_role(self._cached_envelope("targets.json"), root=root, role="targets", trust=trust)
            rollout = self._verify_role(self._cached_envelope("rollout.json"), root=root, role="rollout", trust=trust)
        return UpdateSnapshot(dict(root), timestamp, snapshot, targets, rollout, policy, not_modified=True)

    def _fetch_metadata(self, *, policy_only: bool) -> UpdateSnapshot:
        trust = self._trust()
        root = self._rotate_roots(trust)
        etag = str(trust.get("etag") or "")
        response = self._fetch_bytes(
            "metadata/timestamp.json",
            headers={"If-None-Match": etag} if etag else None,
            allow_not_modified=True,
        )
        if response.status == 304:
            try:
                cached = self._load_cached_snapshot(policy_only=policy_only, root=root, trust=trust)
            except UpdateProtocolError:
                # A policy-only pass intentionally does not fetch targets or
                # rollout. Re-fetch the pointer without an ETag when the full
                # cached chain is therefore incomplete or mismatched.
                response = self._fetch_bytes("metadata/timestamp.json")
            else:
                self._advance_trust_time(trust, self._parse_response_date(response.headers))
                self._write_trust(trust)
                return cached
        timestamp_envelope = self._decode_envelope(response, name="timestamp.json")
        timestamp = self._verify_role(timestamp_envelope, root=root, role="timestamp", trust=trust)
        snapshot_record = (timestamp.get("meta") or {}).get("snapshot.json")
        if not isinstance(snapshot_record, dict):
            raise UpdateClientError("UPD-META-001", "timestamp 缺少 snapshot 记录")
        snapshot_version = int(snapshot_record.get("version") or 0)
        snapshot_response = self._fetch_bytes(f"metadata/{snapshot_version}.snapshot.json")
        verify_metadata_bytes(snapshot_response.body, snapshot_record, name="snapshot.json")
        snapshot_envelope = self._decode_envelope(snapshot_response, name="snapshot.json")
        snapshot = self._verify_role(snapshot_envelope, root=root, role="snapshot", trust=trust)
        meta = snapshot.get("meta")
        if not isinstance(meta, dict):
            raise UpdateClientError("UPD-META-001", "snapshot.meta 无效")

        fetched: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        names = ["policy.json"] if policy_only else ["targets.json", "rollout.json", "policy.json"]
        for name in names:
            record = meta.get(name)
            if not isinstance(record, dict):
                raise UpdateClientError("UPD-META-001", f"snapshot 缺少 {name}")
            version = int(record.get("version") or 0)
            item_response = self._fetch_bytes(f"metadata/{version}.{name}")
            verify_metadata_bytes(item_response.body, record, name=name)
            envelope = self._decode_envelope(item_response, name=name)
            role = name.removesuffix(".json")
            fetched[name] = (envelope, self._verify_role(envelope, root=root, role=role, trust=trust))

        self._cache_metadata("timestamp.json", response.body)
        self._cache_metadata("snapshot.json", snapshot_response.body)
        for name, (envelope, _signed) in fetched.items():
            self._cache_metadata(name, canonical_json_bytes(envelope) + b"\n")
        trust["etag"] = str(response.headers.get("etag") or "")
        self._advance_trust_time(
            trust,
            self._parse_response_date(response.headers),
            timestamp.get("issued_at"),
            snapshot.get("issued_at"),
        )
        self._write_trust(trust)
        return UpdateSnapshot(
            dict(root),
            timestamp,
            snapshot,
            fetched.get("targets.json", (None, None))[1],
            fetched.get("rollout.json", (None, None))[1],
            fetched["policy.json"][1],
        )

    def _accept_required_policy(self, signed_policy: Mapping[str, Any]) -> dict[str, Any] | None:
        policy = signed_policy.get("required_policy")
        trust = self._trust()
        previous = trust.get("last_required_policy")
        if policy is None:
            return previous if isinstance(previous, dict) else None
        validated = validate_required_policy(policy, product_id=self.config.product_id, domain=self.config.domain)
        if isinstance(previous, dict) and int(validated["policy_revision"]) < int(previous.get("policy_revision") or 0):
            raise UpdateClientError("UPD-ROLLBACK-001", "拒绝旧强制更新策略重放")
        if (
            isinstance(previous, dict)
            and int(validated["policy_revision"]) == int(previous.get("policy_revision") or 0)
            and canonical_json_bytes(validated) != canonical_json_bytes(previous)
        ):
            raise UpdateClientError("UPD-MIXMATCH-001", "同一强制策略 revision 出现不同内容")
        trust["last_required_policy"] = dict(validated)
        self._advance_trust_time(trust, validated.get("issued_at"))
        self._write_trust(trust)
        return dict(validated)

    def _accept_targets(self, targets: Mapping[str, Any]) -> None:
        validate_targets_signed(targets, product_id=self.config.product_id, domain=self.config.domain)
        highest_seen = int(self._trust().get("highest_release_sequence") or 0)
        highest_present = max((int(item["release_sequence"]) for item in targets.get("releases") or []), default=0)
        if highest_present < highest_seen:
            raise UpdateClientError("UPD-ROLLBACK-001", "新 targets 元数据删除了已经信任的最高发布序号")
        trust = self._trust()
        trust["highest_release_sequence"] = max(highest_seen, highest_present)
        self._write_trust(trust)

    def _accept_rollout(self, rollout: Mapping[str, Any], *, release_ids: set[str]) -> None:
        raw = rollout.get("policies")
        if not isinstance(raw, list):
            raise UpdateClientError("UPD-ROLLOUT-001", "rollout.policies 必须是列表")
        trust = self._trust()
        previous = dict(trust.get("rollout_policies") or {})
        accepted: dict[str, Any] = {}
        for item in raw:
            value = validate_rollout_policy(item, product_id=self.config.product_id, release_ids=release_ids)
            channel = str(value["channel"])
            old = previous.get(channel)
            if isinstance(old, dict):
                old_revision = int(old.get("policy_revision") or 0)
                revision = int(value["policy_revision"])
                if revision < old_revision:
                    raise UpdateClientError("UPD-ROLLBACK-001", f"拒绝旧 {channel} 灰度策略重放")
                if revision == old_revision and canonical_json_bytes(value) != canonical_json_bytes(old):
                    raise UpdateClientError("UPD-MIXMATCH-001", f"同一 {channel} 灰度 revision 出现不同内容")
                if (
                    value["release_id"] == old.get("release_id")
                    and value["rollout_id"] == old.get("rollout_id")
                    and int(value["percent_bps"]) < int(old.get("percent_bps") or 0)
                ):
                    raise UpdateClientError("UPD-ROLLOUT-002", "同一灰度发布的比例不能缩小")
            accepted[channel] = dict(value)
        # A newer rollout role may intentionally remove a channel. Retain its
        # revision floor so replaying that removed pointer remains detectable.
        trust["rollout_policies"] = {**previous, **accepted}
        self._write_trust(trust)

    def last_required_policy(self) -> dict[str, Any] | None:
        if not self.config.enabled or not self.trust_path.is_file():
            return None
        value = self._trust().get("last_required_policy")
        return dict(value) if isinstance(value, dict) else None

    def task_start_block(self) -> dict[str, Any] | None:
        policy = self.last_required_policy()
        if not policy or policy.get("revoked"):
            return None
        target = f"{self.config.platform}:{self.config.architecture}"
        if target not in set(policy.get("platform_targets") or []):
            return None
        if int(self._state.get("current_release_sequence") or 0) >= int(policy["minimum_release_sequence"]):
            return None
        now = self.trusted_now()
        if now < parse_utc(policy["grace_deadline"], field="required.grace_deadline"):
            return None
        return {
            "code": "UPD-REQUIRED-001",
            "message": str(policy.get("reason") or "当前版本低于作者要求的最低安全版本"),
            "target_release_id": str(policy.get("target_release_id") or ""),
            "minimum_release_sequence": int(policy["minimum_release_sequence"]),
            "grace_deadline": str(policy["grace_deadline"]),
        }

    def assert_task_start_allowed(self) -> str:
        block = self.task_start_block()
        if block:
            raise UpdateClientError(str(block["code"]), str(block["message"]))
        return str(self._state.get("current_release_id") or self.config.current_release_id)

    def _compatible_artifact(self, release: Mapping[str, Any]) -> dict[str, Any] | None:
        for raw in release.get("artifacts") or []:
            artifact = validate_artifact(raw)
            if artifact["platform"] != self.config.platform or artifact["architecture"] != self.config.architecture:
                continue
            if not version_in_range(self.config.runtime_version, artifact["runtime_min"], artifact["runtime_max"]):
                continue
            if not version_in_range(self.config.ecir_version, artifact["ecir_min"], artifact["ecir_max"]):
                continue
            return dict(artifact)
        return None

    def _select_update(
        self,
        targets: Mapping[str, Any],
        rollout: Mapping[str, Any],
        required_policy: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        self._accept_targets(targets)
        releases = {str(item["release_id"]): dict(item) for item in targets.get("releases") or []}
        release_ids = set(releases)
        self._accept_rollout(rollout, release_ids=release_ids)
        policies: list[dict[str, Any]] = []
        raw_policies = rollout.get("policies")
        if not isinstance(raw_policies, list):
            raise UpdateClientError("UPD-ROLLOUT-001", "rollout.policies 必须是列表")
        for item in raw_policies:
            policies.append(validate_rollout_policy(item, product_id=self.config.product_id, release_ids=release_ids))
        required_release = ""
        if required_policy and not required_policy.get("revoked"):
            target = f"{self.config.platform}:{self.config.architecture}"
            if (
                target in set(required_policy.get("platform_targets") or [])
                and int(self._state.get("current_release_sequence") or 0)
                < int(required_policy["minimum_release_sequence"])
            ):
                required_release = str(required_policy.get("target_release_id") or "")
        candidates: list[dict[str, Any]] = []
        if required_release and required_release in releases:
            candidates.append(releases[required_release])
        group_code = self.identity.get() if self.identity else ""
        policy = next((item for item in policies if item["channel"] == self.config.channel), None)
        if policy and rollout_eligible(policy, product_id=self.config.product_id, group_code=group_code):
            release = releases.get(str(policy["release_id"]))
            if release is not None and release not in candidates:
                candidates.append(release)
        candidates.sort(key=lambda item: int(item["release_sequence"]), reverse=True)
        current = int(self._state.get("current_release_sequence") or 0)
        for release in candidates:
            if int(release["release_sequence"]) <= current:
                continue
            artifact = self._compatible_artifact(release)
            if artifact is not None:
                return dict(release), artifact
        return None

    def _schedule_success(self, *, policy_only: bool) -> None:
        now = self.trusted_now()
        if policy_only:
            self._state["policy_failures"] = 0
            delay = timedelta(hours=self._random_seconds(18, 30))
            self._state["next_policy_check_at"] = format_utc(now + delay)
        else:
            self._state["optional_failures"] = 0
            delay = timedelta(hours=self._random_seconds(4, 12))
            self._state["next_optional_check_at"] = format_utc(now + delay)

    def _schedule_failure(self, *, policy_only: bool) -> None:
        field_name = "policy_failures" if policy_only else "optional_failures"
        next_name = "next_policy_check_at" if policy_only else "next_optional_check_at"
        failures = min(10, int(self._state.get(field_name) or 0) + 1)
        self._state[field_name] = failures
        base_minutes = 60 if policy_only else 15
        maximum_hours = 48 if policy_only else 24
        seconds = min(maximum_hours * 3600, base_minutes * 60 * (2 ** (failures - 1)))
        jitter = self._random_seconds(seconds * 0.75, seconds * 1.25)
        self._state[next_name] = format_utc(self.trusted_now() + timedelta(seconds=jitter))

    def check(self, *, manual: bool = False, policy_only: bool = False) -> UpdateCheckResult:
        if not self.config.enabled:
            return UpdateCheckResult("disabled", checked=False, available=False, message="更新能力未启用")
        if policy_only and not self.config.required_policy_capability:
            return UpdateCheckResult(self._state["state"], checked=False, available=False, message="未启用强制策略能力")
        if not policy_only and not manual and not self.config.automatic_checks:
            return UpdateCheckResult(self._state["state"], checked=False, available=False, message="普通自动检查已关闭")
        with self._thread_lock, CrossProcessFileLock(self.lock_path):
            self._transition("checking")
            try:
                snapshot = self._fetch_metadata(policy_only=policy_only)
                required = self._accept_required_policy(snapshot.policy)
                self._state["last_checked_at"] = format_utc(self.trusted_now())
                self._state["last_verified_fresh"] = True
                self._schedule_success(policy_only=policy_only)
                if policy_only:
                    next_state = "staged" if self._state.get("download_path") else "idle"
                    self._transition(next_state)
                    return UpdateCheckResult(next_state, True, False, required_policy=required, not_modified=snapshot.not_modified)
                assert snapshot.targets is not None and snapshot.rollout is not None
                selected = self._select_update(snapshot.targets, snapshot.rollout, required)
                if selected is None:
                    self._transition(
                        "idle",
                        selected_release=None,
                        selected_artifact=None,
                        download_path="",
                        staged_slot="",
                    )
                    return UpdateCheckResult(
                        "idle", True, False, required_policy=required,
                        message="签名元数据验证完成，当前分组没有可用更新",
                        not_modified=snapshot.not_modified,
                    )
                release, artifact = selected
                self._transition("available", selected_release=release, selected_artifact=artifact)
                return UpdateCheckResult(
                    "available", True, True, release, artifact, required,
                    not_modified=snapshot.not_modified,
                )
            except UpdateProtocolError as exc:
                self._state["last_verified_fresh"] = False
                self._schedule_failure(policy_only=policy_only)
                self._transition("failed", error=exc)
                return UpdateCheckResult("failed", checked=False, available=False, required_policy=self.last_required_policy(), message=str(exc))
            except Exception as exc:
                wrapped = UpdateClientError("UPD-CHECK-001", f"更新检查失败：{exc}")
                self._state["last_verified_fresh"] = False
                self._schedule_failure(policy_only=policy_only)
                self._transition("failed", error=wrapped)
                return UpdateCheckResult("failed", checked=False, available=False, required_policy=self.last_required_policy(), message=str(wrapped))

    def due_checks(self) -> list[str]:
        if not self.config.enabled:
            return []
        now = self.trusted_now()
        due: list[str] = []
        optional = str(self._state.get("next_optional_check_at") or "")
        policy = str(self._state.get("next_policy_check_at") or "")
        if self.config.automatic_checks and (not optional or parse_utc(optional, field="next_optional_check_at") <= now):
            due.append("optional")
        if self.config.required_policy_capability and (not policy or parse_utc(policy, field="next_policy_check_at") <= now):
            due.append("policy")
        return due

    def run_due_checks(self) -> list[UpdateCheckResult]:
        results: list[UpdateCheckResult] = []
        for kind in self.due_checks():
            results.append(self.check(policy_only=kind == "policy"))
        return results

    @staticmethod
    def _file_digest(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()

    def download(self) -> Path:
        if not self.config.enabled:
            raise UpdateClientError("UPD-DISABLED-001", "更新能力未启用")
        release = self._state.get("selected_release")
        artifact = self._state.get("selected_artifact")
        if not isinstance(release, dict) or not isinstance(artifact, dict):
            raise UpdateClientError("UPD-DOWNLOAD-001", "没有已验证的可下载更新")
        validate_artifact(artifact)
        with self._thread_lock, CrossProcessFileLock(self.lock_path, timeout_seconds=30):
            self._transition("downloading")
            expected_size = int(artifact["length"])
            expected_hash = str(artifact["hashes"]["sha256"])
            self.download_root.mkdir(parents=True, exist_ok=True)
            destination = self.download_root / f"{release['release_id']}-{artifact['artifact_id']}.payload"
            partial = destination.with_suffix(destination.suffix + ".part")
            offset = partial.stat().st_size if partial.is_file() else 0
            if offset > expected_size:
                partial.unlink(missing_ok=True)
                offset = 0
            free = shutil.disk_usage(self.download_root).free
            if free < (expected_size - offset) + self.DOWNLOAD_RESERVE_BYTES:
                error = UpdateClientError("UPD-DISK-001", "磁盘空间不足，已保留部分下载以便恢复")
                self._transition("failed", error=error)
                raise error
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            mode = "ab" if offset else "wb"
            try:
                with partial.open(mode) as sink:
                    response = self._require_transport().get(
                        str(artifact["path"]),
                        headers=headers,
                        sink=sink,
                        maximum_bytes=expected_size - offset,
                    )
                    if response.status not in {200, 206}:
                        raise UpdateClientError("UPD-NET-HTTP", f"更新下载返回 {response.status}")
                    sink.flush()
                    os.fsync(sink.fileno())
                if offset and response.status == 200:
                    # Origin ignored Range. The appended result is discarded
                    # and fetched once from byte zero without re-entering the
                    # cross-process lock.
                    partial.unlink(missing_ok=True)
                    with partial.open("wb") as sink:
                        response = self._require_transport().get(
                            str(artifact["path"]),
                            sink=sink,
                            maximum_bytes=expected_size,
                        )
                        if response.status != 200:
                            raise UpdateClientError("UPD-NET-HTTP", f"更新下载返回 {response.status}")
                        sink.flush()
                        os.fsync(sink.fileno())
                size, digest = self._file_digest(partial)
                if size != expected_size:
                    raise UpdateClientError("UPD-DOWNLOAD-PARTIAL", f"更新下载不完整：{size}/{expected_size}")
                if digest != expected_hash:
                    partial.unlink(missing_ok=True)
                    raise UpdateClientError("UPD-HASH-001", "更新产物哈希校验失败")
                os.replace(partial, destination)
                self._transition("staged", download_path=str(destination))
                return destination
            except UpdateProtocolError as exc:
                self._transition("failed", error=exc)
                raise
            except OSError as exc:
                wrapped = UpdateClientError("UPD-DISK-002", f"更新写入失败：{exc}")
                self._transition("failed", error=wrapped)
                raise wrapped from exc

    def apply(self) -> dict[str, Any]:
        release = self._state.get("selected_release")
        artifact = self._state.get("selected_artifact")
        raw_path = str(self._state.get("download_path") or "")
        if not self.config.enabled or not isinstance(release, dict) or not isinstance(artifact, dict) or not raw_path:
            raise UpdateClientError("UPD-APPLY-001", "没有已验证并暂存的更新")
        artifact_path = Path(raw_path)
        if not artifact_path.is_file():
            raise UpdateClientError("UPD-APPLY-001", "暂存更新文件已丢失")
        with self._thread_lock, CrossProcessFileLock(self.lock_path, timeout_seconds=30):
            if not self.leases.all_safe():
                self._transition("waiting_safe_point")
                return self.status()
            if self.config.domain == "project_content":
                self._transition("applying")
                try:
                    slot, bundle = self.slots.stage(artifact_path, release)
                    self._state["staged_slot"] = slot
                    self._transition("verifying")
                    self.slots.activate(slot, health_check=self.health_check)
                    self._transition(
                        "complete",
                        current_release_id=str(release["release_id"]),
                        current_release_sequence=int(release["release_sequence"]),
                        selected_release=None,
                        selected_artifact=None,
                        download_path="",
                        staged_slot="",
                    )
                    return {**self.status(), "active_bundle_path": str(bundle)}
                except UpdateProtocolError as exc:
                    self._transition("rolled_back", error=exc)
                    return self.status()
                except Exception as exc:
                    wrapped = UpdateClientError("UPD-HEALTH-001", f"新内容槽验证失败：{exc}")
                    self._transition("rolled_back", error=wrapped)
                    return self.status()

            stage_result = self.installer.stage(artifact_path, artifact, release)
            if not stage_result.accepted:
                error = UpdateClientError("UPD-PLATFORM-UNAVAILABLE", stage_result.message or "平台安装边界不可用")
                self._transition("awaiting_platform_install", error=error)
                return self.status()
            self._transition("awaiting_platform_install", platform_message=stage_result.message)
            if stage_result.requires_user_action or not stage_result.completed:
                return self.status()
            self._transition("applying")
            result = self.installer.apply(artifact_path, artifact, release)
            if result.accepted and result.requires_user_action:
                self._transition("awaiting_platform_install", platform_message=result.message)
                return {**self.status(), "platform_message": result.message}
            if not result.accepted or not result.completed:
                error = UpdateClientError("UPD-PLATFORM-INSTALL", result.message or "平台安装未完成")
                self._transition("failed", error=error)
                return self.status()
            # Application files may now be replaced by the platform; the next
            # process start confirms installed release/version from its host.
            self._transition("verifying")
            return self.status()

    def confirm_platform_install(self, *, release_id: str, release_sequence: int, healthy: bool) -> dict[str, Any]:
        release = self._state.get("selected_release")
        if not isinstance(release, dict) or str(release.get("release_id")) != str(release_id):
            raise UpdateClientError("UPD-PLATFORM-INSTALL", "平台安装回执与待安装发布不匹配")
        if int(release.get("release_sequence") or 0) != int(release_sequence):
            raise UpdateClientError("UPD-PLATFORM-INSTALL", "平台安装回执序号不匹配")
        if not healthy:
            error = UpdateClientError("UPD-HEALTH-001", "平台更新启动健康检查失败，需由平台恢复上一槽")
            self._transition("rolled_back", error=error)
            return self.status()
        self._transition(
            "complete",
            current_release_id=release_id,
            current_release_sequence=release_sequence,
            selected_release=None,
            selected_artifact=None,
            download_path="",
            staged_slot="",
            platform_message="",
        )
        return self.status()

    def reset_group_code(self) -> str:
        if not self.config.enabled or self.identity is None:
            raise UpdateClientError("UPD-DISABLED-001", "更新能力未启用")
        code = self.identity.reset()
        self._event("identity.group_reset")
        return code

    def set_automatic_checks(self, enabled: bool) -> None:
        self.config = replace(self.config, automatic_checks=bool(enabled))

    def mark_runtime_state(self, *, running_or_paused: bool, uncommitted_draft: bool = False) -> str:
        release_id = str(self._state.get("current_release_id") or self.config.current_release_id)
        self.leases.update(
            release_id=release_id,
            safe=not running_or_paused and not uncommitted_draft,
            uncommitted_draft=uncommitted_draft,
        )
        return release_id

    def close(self) -> None:
        self.leases.unregister()


class UpdateScheduler:
    """Bounded scheduler facade; hosts decide when to call ``tick``."""

    def __init__(self, clients: Mapping[str, UpdateClient]) -> None:
        self.clients = dict(clients)

    def tick(self) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        for name, client in self.clients.items():
            entries = client.run_due_checks()
            if entries:
                results[name] = [asdict(entry) for entry in entries]
        return results


def native_platform() -> tuple[str, str]:
    system = platform_module.system().lower()
    platform_name = "android" if "android" in system else "windows"
    machine = platform_module.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64-v8a" if platform_name == "android" else "arm64",
        "aarch64": "arm64-v8a" if platform_name == "android" else "arm64",
    }.get(machine, machine or "unknown")
    return platform_name, architecture


__all__ = [
    "AtomicContentSlots",
    "CommandPlatformInstaller",
    "CrossProcessFileLock",
    "DirectoryUpdateTransport",
    "HttpsUpdateTransport",
    "PlatformInstallResult",
    "ProcessLeaseRegistry",
    "ProductGroupIdentity",
    "TransportResponse",
    "UnavailablePlatformInstaller",
    "UpdateCheckResult",
    "UpdateClient",
    "UpdateClientConfig",
    "UpdateClientError",
    "UpdateScheduler",
    "UpdatePreferencesStore",
    "native_platform",
]
