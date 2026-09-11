"""Signed installed-product, instance and reusable batch registry for Player Hub.

The registry is deliberately local to the current operating-system user.  It
does not discover arbitrary executables, trust display names, or copy editable
project data into the schedule control plane.  Every runnable record points at
an assembled Player distribution and is re-verified against its fixed trust
root before a profile can be scheduled.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .player_bundle import PlayerBundleError, VNextPlayerBundleManager
from .schedule_v6 import ScheduleError, ScheduleReferenceResolver


REGISTRY_SCHEMA_VERSION = 1
MAX_BATCH_ENTRIES = 512
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _checked_id(value: Any, label: str, *, prefix: str = "") -> str:
    normalized = str(value or "").strip() or (_stable_id(prefix) if prefix else "")
    if not normalized or not _STABLE_ID.fullmatch(normalized):
        raise ScheduleError(
            f"{label}必须是 1-128 位稳定标识",
            error_id="schedule.identity_invalid",
        )
    return normalized


def _profile_summary(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return only catalog metadata; profile values may contain user secrets."""

    recording = profile.get("recording") if isinstance(profile.get("recording"), Mapping) else {}
    return {
        "profile_id": str(profile.get("profile_id") or ""),
        "name": str(profile.get("name") or ""),
        "target_id": profile.get("target_id"),
        "revision": int(profile.get("revision") or 0),
        "recording_enabled": bool(recording.get("enabled")),
        "created_at": str(profile.get("created_at") or ""),
        "updated_at": str(profile.get("updated_at") or ""),
    }


def _safe_relative(root: Path, raw: Any, label: str) -> Path:
    text = str(raw or "").strip().replace("\\", "/")
    relative = Path(text)
    if not text or relative.is_absolute() or ".." in relative.parts:
        raise ScheduleError(
            f"{label}不是交付目录内的安全相对路径",
            error_id="schedule.installation_manifest_invalid",
        )
    resolved = root.joinpath(*relative.parts).resolve()
    if resolved != root and root not in resolved.parents:
        raise ScheduleError(
            f"{label}越出交付目录",
            error_id="schedule.installation_manifest_invalid",
        )
    return resolved


def default_hub_root() -> Path:
    configured = str(os.environ.get("EASYCODE_PLAYER_HUB_DATA_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return (base / "EasyCode" / "PlayerHub").resolve()


class _InstanceBundleManager(VNextPlayerBundleManager):
    """Bundle manager with an explicit per-instance durable data root."""

    def __init__(self, instance_data_root: Path, trust_root: Path) -> None:
        self._instance_data_root = instance_data_root.resolve()
        super().__init__(expected_public_key=trust_root, require_trusted_key=True)

    def _data_root(self) -> Path:  # noqa: SLF001 - intentional host adapter seam
        project_id = str(self._manifest.get("project_id") or "unknown")
        safe_id = "".join(ch for ch in project_id if ch.isalnum() or ch in {"-", "_"}) or "unknown"
        root = (self._instance_data_root / safe_id).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root


@dataclass(slots=True)
class RuntimeBinding:
    installation: dict[str, Any]
    instance: dict[str, Any]
    profile: dict[str, Any]
    manager: VNextPlayerBundleManager


class InstalledProductRegistryV6(ScheduleReferenceResolver):
    """Authoritative current-user registry consumed by schedule save and run."""

    def __init__(self, database_path: str | os.PathLike[str], *, data_root: str | os.PathLike[str] | None = None) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.data_root = Path(data_root).expanduser().resolve() if data_root else self.database_path.parent
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._managers: dict[tuple[str, str, str], _InstanceBundleManager] = {}
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS hub_meta(
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS installations(
                        installation_id TEXT PRIMARY KEY,
                        product_id TEXT NOT NULL,
                        release_id TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        root_path TEXT NOT NULL UNIQUE,
                        executable_path TEXT NOT NULL,
                        bundle_path TEXT NOT NULL,
                        trust_root_path TEXT NOT NULL,
                        manifest_sha256 TEXT NOT NULL,
                        executable_sha256 TEXT NOT NULL,
                        bundle_sha256 TEXT NOT NULL,
                        trust_root_sha256 TEXT NOT NULL,
                        signing_key_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        enabled INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS installations_product_release
                    ON installations(product_id, release_id);
                    CREATE TABLE IF NOT EXISTS instances(
                        instance_id TEXT PRIMARY KEY,
                        installation_id TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        data_root TEXT NOT NULL UNIQUE,
                        revision INTEGER NOT NULL,
                        enabled INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(installation_id) REFERENCES installations(installation_id)
                    );
                    CREATE TABLE IF NOT EXISTS batches(
                        batch_id TEXT PRIMARY KEY,
                        revision INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        dispatch_mode TEXT NOT NULL,
                        entries_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                row = connection.execute("SELECT value FROM hub_meta WHERE key='host_id'").fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO hub_meta(key,value) VALUES('host_id',?)",
                        (_stable_id("host"),),
                    )
                connection.execute(
                    "INSERT OR REPLACE INTO hub_meta(key,value) VALUES('schema_version',?)",
                    (str(REGISTRY_SCHEMA_VERSION),),
                )
        except sqlite3.Error as exc:
            raise ScheduleError(
                "Player Hub 注册表读写失败",
                error_id="schedule.registry_database_unavailable",
                transient="locked" in str(exc).lower() or "busy" in str(exc).lower(),
                action="retry",
            ) from exc

    @property
    def host_id(self) -> str:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM hub_meta WHERE key='host_id'").fetchone()
        if row is None:
            raise ScheduleError("Player Hub 主机身份缺失", error_id="schedule.host_identity_missing")
        return str(row["value"])

    def bind_host_identity(self, host_id: str) -> str:
        """Use the shared per-user device identity for schedules and LAN control."""

        stable = _checked_id(host_id, "主机 ID")
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO hub_meta(key,value) VALUES('host_id',?)",
                    (stable,),
                )
        except sqlite3.Error as exc:
            raise ScheduleError(
                "Player Hub 无法绑定共享设备身份",
                error_id="schedule.registry_database_unavailable",
                transient=True,
                action="retry",
            ) from exc
        return stable

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("enabled",):
            if key in value:
                value[key] = bool(value[key])
        return value

    def _read_manifest(self, distribution_root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
        root = distribution_root.expanduser().resolve()
        if not root.is_dir() or root.is_symlink():
            raise ScheduleError(
                "请选择真实的 Windows Player_Bundle 交付目录",
                error_id="schedule.installation_root_invalid",
                action="select_distribution",
            )
        manifest_path = root / "build_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise ScheduleError(
                "交付目录缺少有效 build_manifest.json",
                error_id="schedule.installation_manifest_invalid",
                action="rebuild_player",
            ) from exc
        if not isinstance(manifest, dict):
            raise ScheduleError("交付清单必须是对象", error_id="schedule.installation_manifest_invalid")
        paths = {
            "manifest": manifest_path.resolve(),
            "bundle": _safe_relative(root, manifest.get("bundle"), "Player 包路径"),
            "trust": _safe_relative(root, manifest.get("trust_root"), "信任根路径"),
            "executable": (root / "EasycodePlayer.exe").resolve(),
        }
        for label, path in paths.items():
            if not path.is_file() or path.is_symlink():
                raise ScheduleError(
                    f"交付目录缺少或替换了必要文件：{label}",
                    error_id="schedule.installation_incomplete",
                    action="rebuild_player",
                )
        return manifest, paths

    def _verify_distribution(self, root: Path) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
        manifest, paths = self._read_manifest(root)
        manager = _InstanceBundleManager(self.data_root / "verification", paths["trust"])
        try:
            bootstrap = manager.load(str(paths["bundle"]), expected_public_key=paths["trust"])
        except PlayerBundleError as exc:
            raise ScheduleError(
                f"Player 交付签名或运行闭包无效：{exc}",
                error_id="schedule.installation_signature_invalid",
                action="rebuild_player",
            ) from exc
        finally:
            manager.shutdown()
        bundle = bootstrap.get("bundle") or {}
        product_id = str(bundle.get("project_id") or "")
        release_id = str(bundle.get("release_id") or "")
        if not product_id or not release_id:
            raise ScheduleError("Player 包缺少产品或发布身份", error_id="schedule.installation_manifest_invalid")
        if str(manifest.get("project_id") or "") != product_id or str(manifest.get("release_id") or "") != release_id:
            raise ScheduleError(
                "交付清单与签名 Player 包身份不一致",
                error_id="schedule.installation_identity_mismatch",
            )
        return manifest, paths, bootstrap

    def register_distribution(
        self,
        distribution_root: str | os.PathLike[str],
        *,
        instance_name: str = "实例 1",
        instance_id: str = "",
        instance_data_root: str | os.PathLike[str] | None = None,
    ) -> dict[str, Any]:
        root = Path(distribution_root).expanduser().resolve()
        manifest, paths, bootstrap = self._verify_distribution(root)
        bundle = bootstrap["bundle"]
        product_id = str(bundle["project_id"])
        release_id = str(bundle["release_id"])
        now = _now()
        hashes = {name: _sha256(path) for name, path in paths.items()}
        signing_key_id = str((bundle.get("signature") or {}).get("key_id") or manifest.get("signing_key_id") or "")
        display_name = str(bundle.get("name") or manifest.get("project") or manifest.get("product") or product_id).strip()
        if not display_name:
            display_name = product_id
        with self._lock:
            try:
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing_release = connection.execute(
                        "SELECT * FROM installations WHERE product_id=? AND release_id=?",
                        (product_id, release_id),
                    ).fetchone()
                    existing_root = connection.execute(
                        "SELECT * FROM installations WHERE root_path=?",
                        (str(root),),
                    ).fetchone()
                    if existing_root is not None and str(existing_root["product_id"]) != product_id:
                        raise ScheduleError(
                            "同一安装目录不能切换为其他产品",
                            error_id="schedule.installation_identity_conflict",
                        )
                    if (
                        existing_release is not None
                        and existing_root is not None
                        and str(existing_release["installation_id"]) != str(existing_root["installation_id"])
                    ):
                        raise ScheduleError(
                            "同一产品版本不能同时占用两个安装身份",
                            error_id="schedule.installation_identity_conflict",
                        )
                    if existing_release is not None and existing_root is None:
                        raise ScheduleError(
                            "同一产品版本已经登记在其他安装目录",
                            error_id="schedule.installation_identity_conflict",
                        )
                    # An installation is the stable per-user product location,
                    # not one immutable release.  The Windows installer atomically
                    # replaces that location during upgrade, so reuse its identity
                    # and rebind existing instances to the newly verified release.
                    existing = existing_root or existing_release
                    pinned_author = connection.execute(
                        "SELECT signing_key_id FROM installations WHERE product_id=? ORDER BY created_at LIMIT 1",
                        (product_id,),
                    ).fetchone()
                    if pinned_author is not None and str(pinned_author["signing_key_id"]) != signing_key_id:
                        raise ScheduleError(
                            "同一产品不能用另一把作者签名密钥替换",
                            error_id="schedule.product_signing_identity_conflict",
                            action="verify_publisher_identity",
                        )
                    installation_id = str(existing["installation_id"]) if existing else _stable_id("install")
                    revision = int(existing["revision"]) + 1 if existing else 1
                    created_at = str(existing["created_at"]) if existing else now
                    connection.execute(
                        """
                        INSERT INTO installations(
                            installation_id,product_id,release_id,display_name,root_path,
                            executable_path,bundle_path,trust_root_path,manifest_sha256,
                            executable_sha256,bundle_sha256,trust_root_sha256,signing_key_id,
                            revision,enabled,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
                        ON CONFLICT(installation_id) DO UPDATE SET
                            product_id=excluded.product_id,
                            release_id=excluded.release_id,
                            display_name=excluded.display_name,
                            root_path=excluded.root_path,
                            executable_path=excluded.executable_path,
                            bundle_path=excluded.bundle_path,
                            trust_root_path=excluded.trust_root_path,
                            manifest_sha256=excluded.manifest_sha256,
                            executable_sha256=excluded.executable_sha256,
                            bundle_sha256=excluded.bundle_sha256,
                            trust_root_sha256=excluded.trust_root_sha256,
                            signing_key_id=excluded.signing_key_id,
                            revision=excluded.revision,
                            enabled=1,
                            updated_at=excluded.updated_at
                        """,
                        (
                            installation_id, product_id, release_id, display_name, str(root),
                            str(paths["executable"]), str(paths["bundle"]), str(paths["trust"]),
                            hashes["manifest"], hashes["executable"], hashes["bundle"], hashes["trust"],
                            signing_key_id, revision, created_at, now,
                        ),
                    )
                    clean_instance_id = str(instance_id or "").strip()
                    current_instance = None
                    if clean_instance_id:
                        current_instance = connection.execute(
                            "SELECT * FROM instances WHERE instance_id=?", (clean_instance_id,),
                        ).fetchone()
                    else:
                        current_instance = connection.execute(
                            "SELECT * FROM instances WHERE product_id=? ORDER BY created_at LIMIT 1",
                            (product_id,),
                        ).fetchone()
                        clean_instance_id = str(current_instance["instance_id"]) if current_instance else _stable_id("instance")
                    clean_instance_id = _checked_id(clean_instance_id, "实例 ID")
                    if current_instance and str(current_instance["product_id"]) != product_id:
                        raise ScheduleError("实例不能切换到其他产品", error_id="schedule.instance_identity_conflict")
                    clean_name = str(instance_name or "").strip()
                    if not clean_name or len(clean_name) > 120:
                        raise ScheduleError("实例名称必须是 1-120 个字符", error_id="schedule.instance_name_invalid")
                    data_root = Path(instance_data_root).expanduser().resolve() if instance_data_root else (
                        Path(str(current_instance["data_root"])).resolve()
                        if current_instance
                        else (self.data_root / "instances" / clean_instance_id).resolve()
                    )
                    instance_revision = int(current_instance["revision"]) + 1 if current_instance else 1
                    instance_created = str(current_instance["created_at"]) if current_instance else now
                    connection.execute(
                        """
                        INSERT INTO instances(
                            instance_id,installation_id,product_id,display_name,data_root,
                            revision,enabled,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,1,?,?)
                        ON CONFLICT(instance_id) DO UPDATE SET
                            installation_id=excluded.installation_id,
                            product_id=excluded.product_id,
                            display_name=excluded.display_name,
                            data_root=excluded.data_root,
                            revision=excluded.revision,
                            enabled=1,
                            updated_at=excluded.updated_at
                        """,
                        (
                            clean_instance_id, installation_id, product_id, clean_name,
                            str(data_root), instance_revision, instance_created, now,
                        ),
                    )
                    # A newly registered release becomes the active release for
                    # every existing instance of this product.  Each instance
                    # keeps its stable identity/data root and can be rolled back
                    # explicitly by rebinding to an older verified release.
                    connection.execute(
                        """
                        UPDATE instances
                           SET installation_id=?, revision=revision+1, updated_at=?
                         WHERE product_id=? AND instance_id<>?
                        """,
                        (installation_id, now, product_id, clean_instance_id),
                    )
                    connection.commit()
            except sqlite3.Error as exc:
                raise ScheduleError("Player Hub 注册交付失败", error_id="schedule.registry_database_unavailable") from exc
        self._invalidate_product(product_id)
        return self.get_installation(installation_id, include_profiles=True)

    def create_instance(
        self,
        installation_id: str,
        *,
        name: str = "",
        instance_id: str = "",
        data_root: str | os.PathLike[str] | None = None,
    ) -> dict[str, Any]:
        """Create another isolated Player profile/data namespace for a product."""

        installation = self._installation(_checked_id(installation_id, "安装 ID"))
        clean_id = _checked_id(instance_id, "实例 ID", prefix="instance")
        requested_name = str(name or "").strip()
        if len(requested_name) > 120:
            raise ScheduleError("实例名称不能超过 120 个字符", error_id="schedule.instance_name_invalid")
        root = (
            Path(data_root).expanduser().resolve()
            if data_root
            else (self.data_root / "instances" / clean_id).resolve()
        )
        root.mkdir(parents=True, exist_ok=True)
        now = _now()
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if requested_name:
                    clean_name = requested_name
                else:
                    names = {
                        str(row["display_name"])
                        for row in connection.execute(
                            "SELECT display_name FROM instances WHERE product_id=?",
                            (installation["product_id"],),
                        ).fetchall()
                    }
                    suffix = 1
                    while f"实例 {suffix}" in names:
                        suffix += 1
                    clean_name = f"实例 {suffix}"
                connection.execute(
                    """
                    INSERT INTO instances(
                        instance_id,installation_id,product_id,display_name,data_root,
                        revision,enabled,created_at,updated_at
                    ) VALUES(?,?,?,?,?,1,1,?,?)
                    """,
                    (
                        clean_id,
                        installation["installation_id"],
                        installation["product_id"],
                        clean_name,
                        str(root),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ScheduleError(
                "实例 ID 或数据目录已经被使用",
                error_id="schedule.instance_identity_conflict",
            ) from exc
        except sqlite3.Error as exc:
            raise ScheduleError(
                "Player Hub 注册实例失败",
                error_id="schedule.registry_database_unavailable",
            ) from exc
        return self.get_instance(clean_id, include_profiles=True)

    def delete_instance(self, instance_id: str, *, expected_revision: int) -> dict[str, Any]:
        """Delete an idle unreferenced instance and quarantine its default data."""

        clean_id = _checked_id(instance_id, "实例 ID")
        instance = self._instance(clean_id)
        product_id = str(instance["product_id"])
        data_root = Path(str(instance["data_root"])).resolve()
        expected_default_root = (self.data_root / "instances" / clean_id).resolve()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT revision FROM instances WHERE instance_id=?", (clean_id,),
            ).fetchone()
            if current is None:
                connection.rollback()
                raise ScheduleError("Player 实例不存在", error_id="schedule.instance_not_found")
            if int(current["revision"]) != int(expected_revision):
                connection.rollback()
                raise ScheduleError(
                    "实例已被其他操作修改，请刷新后重试",
                    error_id="schedule.instance_revision_conflict",
                    action="reload_instances",
                )
            for row in connection.execute("SELECT batch_id,name,entries_json FROM batches").fetchall():
                try:
                    entries = json.loads(str(row["entries_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    entries = []
                if any(str(item.get("instance_id") or "") == clean_id for item in entries if isinstance(item, dict)):
                    connection.rollback()
                    raise ScheduleError(
                        f"实例仍被批次“{row['name']}”引用，请先移除该条目",
                        error_id="schedule.instance_reference_conflict",
                        action="open_batches",
                    )
            connection.execute("DELETE FROM instances WHERE instance_id=?", (clean_id,))
            connection.commit()

        self._invalidate_product(product_id)
        retained_path = str(data_root) if data_root.exists() else ""
        recovery_path = ""
        if data_root == expected_default_root and data_root.exists():
            recovery_root = (self.data_root / "deleted-instances").resolve()
            recovery_root.mkdir(parents=True, exist_ok=True)
            recovery = (recovery_root / f"{clean_id}-{uuid.uuid4().hex[:8]}").resolve()
            try:
                shutil.move(str(data_root), str(recovery))
                recovery_path = str(recovery)
                retained_path = ""
            except OSError:
                # Registry deletion has committed, but user data remains intact
                # at the original path and is reported for manual recovery.
                retained_path = str(data_root)
        return {
            "ok": True,
            "instance_id": clean_id,
            "recovery_path": recovery_path,
            "retained_path": retained_path,
        }

    def get_instance(self, instance_id: str, *, include_profiles: bool = False) -> dict[str, Any]:
        instance = self._instance(_checked_id(instance_id, "实例 ID"))
        installation = self._installation(str(instance["installation_id"]))
        result = {**instance, "installation": {
            key: installation[key]
            for key in (
                "installation_id", "product_id", "release_id", "display_name",
                "revision", "enabled", "updated_at",
            )
        }}
        if include_profiles:
            try:
                result["profiles"] = [
                    _profile_summary(item)
                    for item in self._manager(instance, installation).profiles()["profiles"]
                ]
                result["status"] = "ready"
            except (ScheduleError, PlayerBundleError) as exc:
                result["profiles"] = []
                result["status"] = "blocked"
                result["error_id"] = getattr(exc, "error_id", "schedule.profile_document_invalid")
                result["error_message"] = str(exc)
        return result

    def list_instances(self, *, include_profiles: bool = True) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT instance_id FROM instances ORDER BY display_name,instance_id"
            ).fetchall()
        return [
            self.get_instance(str(row["instance_id"]), include_profiles=include_profiles)
            for row in rows
        ]

    def bind_instance_release(
        self,
        instance_id: str,
        installation_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Atomically switch an instance to a verified release (upgrade/rollback)."""

        instance = self._instance(_checked_id(instance_id, "实例 ID"))
        installation = self._installation(_checked_id(installation_id, "安装 ID"))
        if str(instance["product_id"]) != str(installation["product_id"]):
            raise ScheduleError(
                "实例只能切换同一产品的已验证发布",
                error_id="schedule.instance_identity_conflict",
            )
        # Verify before committing so a bad rollback never replaces the known
        # runnable binding.  A temporary manager is cached only after success.
        self._manager(instance, installation)
        now = _now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision FROM instances WHERE instance_id=?", (instance_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ScheduleError("Player 实例不存在", error_id="schedule.instance_not_found")
            if int(row["revision"]) != int(expected_revision):
                connection.rollback()
                raise ScheduleError(
                    "实例已被其他操作修改",
                    error_id="schedule.instance_revision_conflict",
                    action="reload_instances",
                )
            connection.execute(
                """
                UPDATE instances
                   SET installation_id=?, revision=revision+1, updated_at=?
                 WHERE instance_id=?
                """,
                (installation_id, now, instance_id),
            )
            connection.commit()
        self._invalidate_product(str(instance["product_id"]))
        return self.get_instance(instance_id, include_profiles=True)

    def launch_instance_player(self, instance_id: str) -> dict[str, Any]:
        """Open the real standalone Player against this instance's data root."""

        instance, process = self._spawn_instance_player(instance_id)
        return {
            "ok": True,
            "instance_id": str(instance["instance_id"]),
            "process_id": int(process.pid),
        }

    def launch_player_console(self, *, product_id: str = '') -> dict[str, Any]:
        """Open the native multi-instance console from one verified install."""

        installations = [
            item for item in self.list_installations(include_profiles=False)
            if bool(item.get('enabled', True))
            and (not product_id or str(item.get('product_id') or '') == product_id)
        ]
        if not installations:
            raise ScheduleError(
                '没有可用于打开 Player 控制台的已验证安装',
                error_id='schedule.installation_not_found',
                action='register_installation',
            )
        installation = installations[-1]
        self._verify_hashes(installation)
        executable = Path(str(installation['executable_path'])).resolve()
        try:
            process = subprocess.Popen(
                [
                    str(executable), '--mode', 'prod', '--port', '0', '--player-console',
                    *(['--select-product', product_id] if product_id else []),
                ],
                cwd=str(Path(str(installation['root_path'])).resolve()),
                close_fds=True,
            )
        except OSError as exc:
            raise ScheduleError(
                '无法打开 Player 控制台',
                error_id='schedule.player_console_launch_failed',
                action='verify_installation',
            ) from exc
        return {'ok': True, 'process_id': int(process.pid), 'product_id': product_id}

    def launch_instance_console_worker(
        self,
        instance_id: str,
        *,
        descriptor_path: str | os.PathLike[str],
        console_origin_path: str | os.PathLike[str],
        console_origin: str,
        console_parent_pid: int,
    ) -> subprocess.Popen:
        """Start one invisible Player host owned by the native console.

        The descriptor is constrained to the instance data root so neither a
        caller nor a compromised registry row can turn worker startup into an
        arbitrary file write.
        """

        instance = self._instance(_checked_id(instance_id, "实例 ID"))
        data_root = Path(str(instance["data_root"])).resolve()
        descriptor = Path(descriptor_path).resolve()
        origin_path = Path(console_origin_path).resolve()
        if (
            descriptor == data_root
            or data_root not in descriptor.parents
            or origin_path == data_root
            or data_root not in origin_path.parents
        ):
            raise ScheduleError(
                "Player 控制台工作进程描述文件越出实例目录",
                error_id="schedule.instance_worker_descriptor_invalid",
            )
        descriptor.parent.mkdir(parents=True, exist_ok=True)
        instance, process = self._spawn_instance_player(
            instance_id,
            extra_arguments=(
                "--console-worker",
                "--runtime-descriptor", str(descriptor),
                "--console-origin-file", str(origin_path),
                "--console-parent-pid", str(max(1, int(console_parent_pid))),
            ),
            extra_environment={
                "EASYCODE_PLAYER_CONSOLE_ORIGIN": str(console_origin),
                "EASYCODE_PLAYER_CONSOLE_ORIGIN_FILE": str(origin_path),
            },
        )
        return process

    def _spawn_instance_player(
        self,
        instance_id: str,
        *,
        extra_arguments: tuple[str, ...] = (),
        extra_environment: Mapping[str, str] | None = None,
    ) -> tuple[dict[str, Any], subprocess.Popen]:
        """Verify and start one instance process with its isolated root."""

        instance = self._instance(_checked_id(instance_id, "实例 ID"))
        installation = self._installation(str(instance["installation_id"]))
        self._verify_hashes(installation)
        executable = Path(str(installation["executable_path"])).resolve()
        bundle = Path(str(installation["bundle_path"])).resolve()
        trust = Path(str(installation["trust_root_path"])).resolve()
        environment = os.environ.copy()
        environment.update({
            "EASYCODE_PLAYER_DATA_DIR": str(instance["data_root"]),
            "EASYCODE_PLAYER_INSTANCE_ID": str(instance["instance_id"]),
            "EASYCODE_PLAYER_INSTANCE_NAME": str(instance["display_name"]),
        })
        if extra_environment:
            environment.update({str(key): str(value) for key, value in extra_environment.items()})
        try:
            process = subprocess.Popen(
                [
                    str(executable), "--mode", "prod",
                    "--port", "0",
                    "--player-bundle", str(bundle),
                    "--player-trust-root", str(trust),
                    *extra_arguments,
                ],
                cwd=str(Path(str(installation["root_path"])).resolve()),
                env=environment,
                close_fds=True,
            )
        except OSError as exc:
            raise ScheduleError(
                "无法打开该实例的独立 Player",
                error_id="schedule.instance_player_launch_failed",
                action="verify_installation",
            ) from exc
        return instance, process

    def _invalidate_product(self, product_id: str) -> None:
        with self._lock:
            for key, manager in list(self._managers.items()):
                if key[1] == product_id:
                    manager.shutdown()
                    self._managers.pop(key, None)

    def _installation(self, installation_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM installations WHERE installation_id=?", (installation_id,),
            ).fetchone()
        if row is None:
            raise ScheduleError("已安装产品不存在", error_id="schedule.installation_not_found")
        return self._row(row)

    def _instance(self, instance_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM instances WHERE instance_id=?", (instance_id,)).fetchone()
        if row is None:
            raise ScheduleError("Player 实例不存在", error_id="schedule.instance_not_found")
        return self._row(row)

    def _verify_hashes(self, installation: Mapping[str, Any]) -> None:
        checks = {
            "manifest_sha256": Path(str(installation["root_path"])) / "build_manifest.json",
            "executable_sha256": Path(str(installation["executable_path"])),
            "bundle_sha256": Path(str(installation["bundle_path"])),
            "trust_root_sha256": Path(str(installation["trust_root_path"])),
        }
        for field, path in checks.items():
            if not path.is_file() or path.is_symlink() or _sha256(path) != str(installation[field]):
                raise ScheduleError(
                    f"已安装产品文件在登记后发生变化：{path.name}",
                    error_id="schedule.installation_drift",
                    action="verify_installation",
                )

    def _manager(self, instance: Mapping[str, Any], installation: Mapping[str, Any]) -> _InstanceBundleManager:
        self._verify_hashes(installation)
        key = (
            str(instance["instance_id"]),
            str(installation["product_id"]),
            str(installation["bundle_sha256"]),
        )
        with self._lock:
            manager = self._managers.get(key)
            if manager is not None:
                return manager
            manager = _InstanceBundleManager(
                Path(str(instance["data_root"])),
                Path(str(installation["trust_root_path"])),
            )
            try:
                manager.load(
                    str(installation["bundle_path"]),
                    expected_public_key=Path(str(installation["trust_root_path"])),
                )
            except PlayerBundleError as exc:
                manager.shutdown()
                raise ScheduleError(
                    f"已安装 Player 无法通过签名复验：{exc}",
                    error_id="schedule.installation_signature_invalid",
                    action="verify_installation",
                ) from exc
            self._managers[key] = manager
            return manager

    def get_installation(self, installation_id: str, *, include_profiles: bool = False) -> dict[str, Any]:
        installation = self._installation(installation_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM instances WHERE installation_id=? ORDER BY display_name,instance_id",
                (installation_id,),
            ).fetchall()
        instances = [self._row(row) for row in rows]
        result = {**installation, "instances": instances}
        if include_profiles:
            for instance in result["instances"]:
                try:
                    manager = self._manager(instance, installation)
                    instance["profiles"] = [
                        _profile_summary(item) for item in manager.profiles()["profiles"]
                    ]
                    instance["status"] = "ready"
                except ScheduleError as exc:
                    instance["profiles"] = []
                    instance["status"] = "blocked"
                    instance["error_id"] = exc.error_id
                    instance["error_message"] = str(exc)
                except PlayerBundleError as exc:
                    instance["profiles"] = []
                    instance["status"] = "blocked"
                    instance["error_id"] = "schedule.profile_document_invalid"
                    instance["error_message"] = str(exc)
        return result

    def list_installations(self, *, include_profiles: bool = True) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT installation_id FROM installations ORDER BY display_name,release_id"
            ).fetchall()
        return [self.get_installation(str(row["installation_id"]), include_profiles=include_profiles) for row in rows]

    def disable_distribution(self, distribution_root: str | os.PathLike[str]) -> dict[str, Any]:
        """Disable one exact installed root without deleting user data or schedule history."""

        root = Path(distribution_root).expanduser().resolve()
        if not root.is_absolute():
            raise ScheduleError(
                "Player 安装目录必须是绝对路径",
                error_id="schedule.installation_root_invalid",
            )
        now = _now()
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                installation = connection.execute(
                    "SELECT * FROM installations WHERE root_path=?", (str(root),),
                ).fetchone()
                if installation is None:
                    connection.rollback()
                    return {"disabled": False, "reason": "not_registered", "root_path": str(root)}
                installation_id = str(installation["installation_id"])
                product_id = str(installation["product_id"])
                connection.execute(
                    "UPDATE installations SET enabled=0,revision=revision+1,updated_at=? WHERE installation_id=?",
                    (now, installation_id),
                )
                connection.execute(
                    "UPDATE instances SET enabled=0,revision=revision+1,updated_at=? WHERE installation_id=?",
                    (now, installation_id),
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise ScheduleError(
                "Player Hub 无法停用已卸载产品",
                error_id="schedule.registry_database_unavailable",
                transient=True,
                action="retry",
            ) from exc
        self._invalidate_product(product_id)
        return {
            "disabled": True,
            "installation_id": installation_id,
            "product_id": product_id,
            "root_path": str(root),
        }

    def resolve_runtime(self, entry: Mapping[str, Any]) -> RuntimeBinding:
        host_id = str(entry.get("host_id") or "")
        if host_id != self.host_id:
            raise ScheduleError(
                "局域网远程派发尚未获得授权或当前不可用",
                error_id="schedule.remote_dispatch_unavailable",
                action="open_instances",
            )
        instance = self._instance(str(entry.get("instance_id") or ""))
        if not instance["enabled"]:
            raise ScheduleError("Player 实例已停用", error_id="schedule.instance_disabled")
        product_id = str(entry.get("product_id") or "")
        if str(instance["product_id"]) != product_id:
            raise ScheduleError("实例与产品身份不一致", error_id="schedule.reference_unknown")
        installation = self._installation(str(instance["installation_id"]))
        if not installation["enabled"]:
            raise ScheduleError("已安装产品已停用", error_id="schedule.installation_disabled")
        manager = self._manager(instance, installation)
        profile_id = str(entry.get("profile_id") or "")
        try:
            profiles = manager.profiles()["profiles"]
        except PlayerBundleError as exc:
            raise ScheduleError(
                f"运行方案文档不可用：{exc}",
                error_id="schedule.profile_document_invalid",
                action="open_player_profiles",
            ) from exc
        profile = next((item for item in profiles if str(item.get("profile_id") or "") == profile_id), None)
        if profile is None:
            raise ScheduleError(
                "计划引用的运行方案不存在",
                error_id="schedule.profile_not_found",
                action="choose_profile",
            )
        return RuntimeBinding(installation, instance, copy.deepcopy(profile), manager)

    def resolve(self, entry: Mapping[str, Any]) -> Mapping[str, Any]:
        binding = self.resolve_runtime(entry)
        return {
            "dispatch_scope": "local",
            "host_name": "此电脑",
            "instance_name": binding.instance["display_name"],
            "product_name": binding.installation["display_name"],
            "profile_name": binding.profile["name"],
            "profile_revision": binding.profile["revision"],
            "release_id": binding.installation["release_id"],
            "installation_revision": binding.installation["revision"],
        }

    @staticmethod
    def _normalize_batch_entries(entries: Any, resolver: ScheduleReferenceResolver) -> list[dict[str, Any]]:
        if not isinstance(entries, list) or not entries or len(entries) > MAX_BATCH_ENTRIES:
            raise ScheduleError("批次必须包含 1-512 个条目", error_id="schedule.batch_entries_invalid")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(entries):
            if not isinstance(raw, Mapping):
                raise ScheduleError("批次条目必须是对象", error_id="schedule.batch_entries_invalid")
            entry_id = _checked_id(raw.get("entry_id"), "条目 ID", prefix="entry")
            if entry_id in seen:
                raise ScheduleError("批次包含重复 entry_id", error_id="schedule.batch_entries_invalid")
            seen.add(entry_id)
            item = {
                "entry_id": entry_id,
                "enabled": bool(raw.get("enabled", True)),
                "host_id": str(raw.get("host_id") or "").strip(),
                "instance_id": str(raw.get("instance_id") or "").strip(),
                "product_id": str(raw.get("product_id") or "").strip(),
                "profile_id": str(raw.get("profile_id") or "").strip(),
                "start_offset_seconds": int(raw.get("start_offset_seconds") or 0),
                "start_deadline_seconds": (
                    int(raw["start_deadline_seconds"])
                    if raw.get("start_deadline_seconds") is not None else None
                ),
                "order": index,
            }
            if min(item["start_offset_seconds"], item["start_deadline_seconds"] or 0) < 0:
                raise ScheduleError("批次时间不能为负数", error_id="schedule.batch_entries_invalid")
            summary = resolver.resolve(item)
            item["validated_summary"] = {
                key: value for key, value in summary.items()
                if isinstance(value, (str, int, float, bool)) or value is None
            }
            normalized.append(item)
        return normalized

    def save_batch(self, value: Mapping[str, Any], *, expected_revision: int | None = None) -> dict[str, Any]:
        name = str(value.get("name") or "").strip()
        if not name or len(name) > 160:
            raise ScheduleError("批次名称必须是 1-160 个字符", error_id="schedule.batch_name_invalid")
        mode = str(value.get("dispatch_mode") or "simultaneous")
        if mode not in {"simultaneous", "staggered"}:
            raise ScheduleError("批次派发模式无效", error_id="schedule.batch_mode_invalid")
        entries = self._normalize_batch_entries(value.get("entries"), self)
        batch_id = _checked_id(value.get("batch_id"), "批次 ID", prefix="batch")
        now = _now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            if row is not None:
                if expected_revision is None or int(row["revision"]) != expected_revision:
                    connection.rollback()
                    raise ScheduleError(
                        "批次已被其他操作修改",
                        error_id="schedule.batch_revision_conflict",
                        diagnostics=[{"actual_revision": int(row["revision"])}],
                        action="reload_batches",
                    )
                revision, created_at = int(row["revision"]) + 1, str(row["created_at"])
            else:
                if expected_revision is not None:
                    connection.rollback()
                    raise ScheduleError("批次不存在", error_id="schedule.batch_not_found")
                revision, created_at = 1, now
            connection.execute(
                """
                INSERT OR REPLACE INTO batches(batch_id,revision,name,dispatch_mode,entries_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (batch_id, revision, name, mode, _canonical(entries), created_at, now),
            )
            connection.commit()
        return self.get_batch(batch_id)

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        if row is None:
            raise ScheduleError("批次不存在", error_id="schedule.batch_not_found")
        return {
            "batch_id": str(row["batch_id"]),
            "revision": int(row["revision"]),
            "name": str(row["name"]),
            "dispatch_mode": str(row["dispatch_mode"]),
            "entries": json.loads(str(row["entries_json"])),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def list_batches(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT batch_id FROM batches ORDER BY name,batch_id").fetchall()
        return [self.get_batch(str(row["batch_id"])) for row in rows]

    def delete_batch(self, batch_id: str, expected_revision: int) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            if row is None:
                connection.rollback()
                raise ScheduleError("批次不存在", error_id="schedule.batch_not_found")
            if int(row["revision"]) != int(expected_revision):
                connection.rollback()
                raise ScheduleError("批次已被其他操作修改", error_id="schedule.batch_revision_conflict")
            connection.execute("DELETE FROM batches WHERE batch_id=?", (batch_id,))
            connection.commit()
        return {"ok": True, "batch_id": batch_id}

    def shutdown(self) -> None:
        with self._lock:
            for manager in self._managers.values():
                manager.shutdown()
            self._managers.clear()
