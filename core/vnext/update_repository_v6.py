"""Author-side immutable release repository and static-feed publisher."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from .bundle_signing_v6 import (
    AuthorSigningIdentity,
    AuthorSigningKeyStore,
    BundleSignatureError,
    canonical_json_bytes,
    public_key_id,
    verify_signed_archive,
)
from .update_protocol_v6 import (
    UPDATE_DOMAINS,
    UPDATE_PROTOCOL_VERSION,
    UpdateProtocolError,
    UpdateSigningIdentity,
    create_root_signed,
    format_utc,
    group_code_hash,
    metadata_record,
    sha256_bytes,
    sign_envelope,
    utc_now,
    validate_artifact,
    validate_release,
    validate_required_policy,
    validate_rollout_policy,
    verify_initial_root,
    verify_rotated_root,
)


class UpdateRepositoryError(UpdateProtocolError):
    pass


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _safe_relative(value: str) -> str:
    normalized = str(value or "").replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise UpdateRepositoryError("UPD-REPO-001", "更新仓库相对路径无效")
    return normalized


def _file_sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


class UpdateSigningKeyStore:
    """DPAPI-protected online role keys, outside project/Git/feed artifacts."""

    SCHEMA_VERSION = 1

    def __init__(self, root: str | Path | None = None) -> None:
        configured = str(os.environ.get("EASYCODE_UPDATE_SIGNING_KEY_DIR") or "").strip()
        self.root = Path(
            configured
            or root
            or Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "EasyCode" / "UpdateSigningKeys"
        ).expanduser().resolve()

    def _path(self, product_id: str) -> Path:
        return self.root / f"{hashlib.sha256(product_id.encode('utf-8')).hexdigest()}.json"

    @staticmethod
    def _private_bytes(key: Ed25519PrivateKey) -> bytes:
        return key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    @staticmethod
    def _identity(private: Ed25519PrivateKey) -> UpdateSigningIdentity:
        public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return UpdateSigningIdentity(public_key_id(public), private, public)

    def get_or_create(
        self,
        product_id: str,
        *,
        root_identity: AuthorSigningIdentity,
    ) -> dict[str, UpdateSigningIdentity]:
        clean = str(product_id or "").strip()
        if not clean or root_identity.product_id != clean:
            raise UpdateRepositoryError("UPD-KEY-001", "更新签名身份与 product_id 不一致")
        path = self._path(clean)
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                if value.get("schema_version") != self.SCHEMA_VERSION or value.get("product_id") != clean:
                    raise ValueError
                roles: dict[str, UpdateSigningIdentity] = {"root": UpdateSigningIdentity.from_author(root_identity)}
                protected = value.get("roles")
                if not isinstance(protected, dict) or set(protected) != {"targets", "snapshot", "timestamp", "rollout", "policy"}:
                    raise ValueError
                for role, record in protected.items():
                    if not isinstance(record, dict) or set(record) != {"key_id", "protected_private_key"}:
                        raise ValueError
                    private = Ed25519PrivateKey.from_private_bytes(
                        AuthorSigningKeyStore._unprotect(str(record["protected_private_key"]))
                    )
                    identity = self._identity(private)
                    if identity.key_id != record["key_id"]:
                        raise ValueError
                    roles[role] = identity
                return roles
            except (BundleSignatureError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise UpdateRepositoryError("UPD-KEY-002", "在线更新角色私钥记录已损坏") from exc

        roles = {role: UpdateSigningIdentity.generate() for role in ("targets", "snapshot", "timestamp", "rollout", "policy")}
        document = {
            "schema_version": self.SCHEMA_VERSION,
            "product_id": clean,
            "roles": {
                role: {
                    "key_id": identity.key_id,
                    "protected_private_key": AuthorSigningKeyStore._protect(self._private_bytes(identity.private_key)),
                }
                for role, identity in roles.items()
            },
        }
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(path, json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        return {"root": UpdateSigningIdentity.from_author(root_identity), **roles}

    def rotate_online_roles(
        self,
        product_id: str,
        *,
        root_identity: AuthorSigningIdentity,
        roles: Iterable[str] = ("targets", "snapshot", "timestamp", "rollout", "policy"),
    ) -> dict[str, UpdateSigningIdentity]:
        current = self.get_or_create(product_id, root_identity=root_identity)
        selected = set(str(item) for item in roles)
        allowed = {"targets", "snapshot", "timestamp", "rollout", "policy"}
        if not selected or not selected.issubset(allowed):
            raise UpdateRepositoryError("UPD-KEY-001", "在线更新密钥轮换角色无效")
        for role in selected:
            current[role] = UpdateSigningIdentity.generate()
        document = {
            "schema_version": self.SCHEMA_VERSION,
            "product_id": product_id,
            "roles": {
                role: {
                    "key_id": current[role].key_id,
                    "protected_private_key": AuthorSigningKeyStore._protect(
                        self._private_bytes(current[role].private_key)
                    ),
                }
                for role in sorted(allowed)
            },
        }
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(
            self._path(product_id),
            json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
        )
        return current


@dataclass
class UpdateRepositorySigner:
    product_id: str
    identities: dict[str, UpdateSigningIdentity]
    root_version: int = 1
    mirrors: tuple[str, ...] = ()

    @classmethod
    def from_author_store(
        cls,
        product_id: str,
        *,
        author_store: AuthorSigningKeyStore | None = None,
        update_store: UpdateSigningKeyStore | None = None,
        mirrors: Iterable[str] = (),
    ) -> UpdateRepositorySigner:
        author = (author_store or AuthorSigningKeyStore()).get_or_create(product_id)
        identities = (update_store or UpdateSigningKeyStore()).get_or_create(product_id, root_identity=author)
        return cls(product_id, identities, mirrors=tuple(mirrors))

    def root_envelope(self, *, now: datetime | None = None, expires_days: int = 3650) -> dict[str, Any]:
        current = now or utc_now()
        roles = {name: [identity] for name, identity in self.identities.items()}
        signed = create_root_signed(
            product_id=self.product_id,
            version=self.root_version,
            expires=current + timedelta(days=expires_days),
            role_identities=roles,
            mirrors=self.mirrors,
        )
        return sign_envelope(signed, [self.identities["root"]])

    def sign(self, role: str, signed: Mapping[str, Any]) -> dict[str, Any]:
        identity = self.identities.get(role)
        if identity is None:
            raise UpdateRepositoryError("UPD-KEY-001", f"缺少 {role} 更新签名角色")
        return sign_envelope(signed, [identity])


def analyze_ecplayer_artifact(
    path: str | Path,
    *,
    expected_public_key: str | bytes | Path | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the immutable content/application boundary of a signed bundle."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise UpdateRepositoryError("UPD-ARTIFACT-001", "项目内容产物不存在")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            signature = verify_signed_archive(archive, expected_public_key)
            manifest = json.loads(archive.read("manifest.json"))
            report = json.loads(archive.read("publish-report.json"))
            integrity = json.loads(archive.read("META-INF/integrity.json"))
            update_configuration = (
                json.loads(archive.read("update/config.json"))
                if "update/config.json" in archive.namelist()
                else None
            )
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, BundleSignatureError) as exc:
        raise UpdateRepositoryError("UPD-ARTIFACT-001", f"项目内容产物验证失败：{exc}") from exc
    records = integrity.get("entries") if isinstance(integrity, dict) else None
    if not isinstance(records, list):
        raise UpdateRepositoryError("UPD-ARTIFACT-001", "项目内容缺少完整性文件清单")
    by_path = {str(item.get("path") or ""): item for item in records if isinstance(item, dict)}
    content_records = [
        item
        for name, item in sorted(by_path.items())
        if name in {"runtime/ecir.json", "runtime/project.json", "player/form.json"} or name.startswith("assets/")
    ]
    application_records = [
        item
        for name, item in sorted(by_path.items())
        if name in {"runtime/easycode.lock", "update/config.json"} or name.startswith("runtime/extensions/")
    ]
    permissions = {
        "required_capabilities": sorted(str(item) for item in report.get("required_capabilities") or []),
        "terminal_capabilities": sorted(str(item) for item in report.get("player_terminal_capabilities") or []),
        "extension_permissions": sorted(str(item) for item in report.get("extension_permissions") or []),
    }
    permissions_fingerprint = sha256_bytes(canonical_json_bytes(permissions))
    content_fingerprint = sha256_bytes(canonical_json_bytes(content_records))
    application_fingerprint = sha256_bytes(canonical_json_bytes({
        "minimum_runtime_version": str(manifest.get("minimum_runtime_version") or ""),
        "application_files": application_records,
        "permissions_fingerprint": permissions_fingerprint,
    }))
    size, digest = _file_sha256(source)
    return {
        "path": str(source),
        "length": size,
        "sha256": digest,
        "release_id": str(manifest.get("release_id") or ""),
        "project_id": str(manifest.get("project_id") or ""),
        "minimum_runtime_version": str(manifest.get("minimum_runtime_version") or "0.0.0"),
        "application_fingerprint": application_fingerprint,
        "content_fingerprint": content_fingerprint,
        "permissions_fingerprint": permissions_fingerprint,
        "signing_key_id": signature["key_id"],
        "source_included": manifest.get("source_included"),
        "update_product_ids": {
            str(domain): str(record.get("product_id") or "")
            for domain, record in ((update_configuration or {}).get("domains") or {}).items()
            if isinstance(record, dict)
        },
    }


class StaticUpdateRepository:
    """Produce a deployable, serverless signed feed tree.

    Metadata pointers are atomically replaced, while artifacts and versioned
    metadata are immutable.  The same tree can be mounted by the reference
    service or copied verbatim to any HTTPS object store/CDN.
    """

    METADATA_TTL = {
        "targets": timedelta(days=30),
        "snapshot": timedelta(days=7),
        "timestamp": timedelta(days=1),
        "rollout": timedelta(days=7),
        "policy": timedelta(days=7),
    }

    def __init__(
        self,
        root: str | Path,
        signer: UpdateRepositorySigner,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.signer = signer
        self.product_id = signer.product_id
        self._now = now or utc_now

    def _domain_root(self, domain: str) -> Path:
        if domain not in UPDATE_DOMAINS:
            raise UpdateRepositoryError("UPD-REPO-001", "更新产品域无效")
        return self.root / self.product_id / domain

    def _metadata_path(self, domain: str, name: str) -> Path:
        return self._domain_root(domain) / "metadata" / _safe_relative(name)

    def _read_envelope(self, domain: str, name: str) -> dict[str, Any] | None:
        path = self._metadata_path(domain, name)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise UpdateRepositoryError("UPD-REPO-002", f"更新仓库元数据损坏：{name}") from exc
        if not isinstance(value, dict):
            raise UpdateRepositoryError("UPD-REPO-002", f"更新仓库元数据格式无效：{name}")
        return value

    def _role_version(self, domain: str, role: str) -> int:
        envelope = self._read_envelope(domain, f"{role}.json")
        return int(((envelope or {}).get("signed") or {}).get("version") or 0)

    def _base(self, role: str, domain: str, version: int) -> dict[str, Any]:
        now = self._now().astimezone(timezone.utc)
        return {
            "_type": role,
            "spec_version": UPDATE_PROTOCOL_VERSION,
            "product_id": self.product_id,
            "domain": domain,
            "version": version,
            "issued_at": format_utc(now),
            "expires": format_utc(now + self.METADATA_TTL[role]),
        }

    def _write_role(self, domain: str, role: str, envelope: Mapping[str, Any]) -> bytes:
        content = _json_bytes(envelope)
        version = int((envelope.get("signed") or {}).get("version") or 0)
        if version < 1:
            raise UpdateRepositoryError("UPD-REPO-003", f"{role} 元数据缺少版本")
        versioned = self._metadata_path(domain, f"{version}.{role}.json")
        if versioned.exists() and versioned.read_bytes() != content:
            raise UpdateRepositoryError("UPD-IMMUTABLE-001", f"拒绝覆盖不可变 {role} revision {version}")
        if not versioned.exists():
            _atomic_write_bytes(versioned, content)
        _atomic_write_bytes(self._metadata_path(domain, f"{role}.json"), content)
        return content

    def initialize(self, domains: Iterable[str] = UPDATE_DOMAINS) -> dict[str, Any]:
        initialized: list[str] = []
        for domain in domains:
            domain_root = self._domain_root(domain)
            (domain_root / "artifacts").mkdir(parents=True, exist_ok=True)
            root_path = self._metadata_path(domain, "root.json")
            if root_path.exists():
                try:
                    existing = json.loads(root_path.read_text(encoding="utf-8-sig"))
                    trusted = verify_initial_root(
                        existing,
                        product_id=self.product_id,
                        pinned_public_key=self.signer.identities["root"].public_key_bytes,
                    )
                except (OSError, json.JSONDecodeError, UpdateProtocolError) as exc:
                    raise UpdateRepositoryError("UPD-ROOT-001", "现有更新信任根验证失败") from exc
                existing_version = int(trusted["version"])
                if existing_version != self.signer.root_version:
                    identities_match = all(
                        self.signer.identities[role].key_id
                        in set((trusted.get("roles", {}).get(role) or {}).get("keyids") or [])
                        for role in self.signer.identities
                    )
                    if not identities_match or existing_version < self.signer.root_version:
                        raise UpdateRepositoryError(
                            "UPD-ROOT-ROTATION-001",
                            "信任根版本变化必须使用双重签名的显式轮换流程",
                        )
                    self.signer.root_version = existing_version
            else:
                root_envelope = self.signer.root_envelope(now=self._now())
                root_content = _json_bytes(root_envelope)
                _atomic_write_bytes(root_path, root_content)
                versioned_root = self._metadata_path(domain, f"{self.signer.root_version}.root.json")
                if not versioned_root.exists():
                    _atomic_write_bytes(versioned_root, root_content)
            if self._read_envelope(domain, "targets.json") is None:
                self._commit(domain, releases=[], rollouts=[], required_policy=None, action="initialize", actor="local-author")
            initialized.append(domain)
        return {"initialized": initialized, "root": str(self.root), "product_id": self.product_id}

    def rotate_root(
        self,
        new_signer: UpdateRepositorySigner,
        *,
        domains: Iterable[str] = UPDATE_DOMAINS,
        actor: str = "local-author",
    ) -> dict[str, Any]:
        if new_signer.product_id != self.product_id:
            raise UpdateRepositoryError("UPD-ROOT-002", "新信任根属于其他 product_id")
        rotated: list[str] = []
        for domain in domains:
            current_envelope = self._read_envelope(domain, "root.json")
            if current_envelope is None:
                raise UpdateRepositoryError("UPD-ROOT-001", f"{domain} 尚未初始化信任根")
            current = verify_initial_root(current_envelope, product_id=self.product_id)
            if new_signer.root_version != int(current["version"]) + 1:
                raise UpdateRepositoryError("UPD-ROOT-ROTATION-001", "新信任根必须逐版本轮换")
            now = self._now()
            role_identities = {
                role: [identity] for role, identity in new_signer.identities.items()
            }
            candidate_signed = create_root_signed(
                product_id=self.product_id,
                version=new_signer.root_version,
                expires=now + timedelta(days=3650),
                role_identities=role_identities,
                mirrors=new_signer.mirrors,
            )
            candidate = sign_envelope(
                candidate_signed,
                [self.signer.identities["root"], new_signer.identities["root"]],
            )
            verify_rotated_root(current, candidate, now=now)
            content = _json_bytes(candidate)
            versioned = self._metadata_path(domain, f"{new_signer.root_version}.root.json")
            if versioned.exists() and versioned.read_bytes() != content:
                raise UpdateRepositoryError("UPD-IMMUTABLE-001", "目标 root revision 已存在不同内容")
            if not versioned.exists():
                _atomic_write_bytes(versioned, content)
            _atomic_write_bytes(self._metadata_path(domain, "root.json"), content)
            self._append_audit(
                domain,
                "root.rotate",
                actor,
                {"version": current["version"], "roles": current["roles"]},
                {"version": new_signer.root_version, "roles": candidate_signed["roles"]},
            )
            releases, rollouts, required_policy = self._current_payloads(domain)
            previous_signer = self.signer
            self.signer = new_signer
            try:
                self._commit(
                    domain,
                    releases=releases,
                    rollouts=rollouts,
                    required_policy=required_policy,
                    action="metadata.resign_after_root_rotation",
                    actor=actor,
                    audit_old={"root_version": current["version"]},
                    audit_new={"root_version": new_signer.root_version},
                )
            finally:
                self.signer = previous_signer
            rotated.append(domain)
        # A successful rotation changes the authority used by every later
        # publication through this repository instance. Keeping the old
        # signer here would create metadata that the newly installed root can
        # no longer verify.
        self.signer = new_signer
        return {"product_id": self.product_id, "root_version": new_signer.root_version, "rotated": rotated}

    def _current_payloads(self, domain: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
        targets = self._read_envelope(domain, "targets.json") or {}
        rollout = self._read_envelope(domain, "rollout.json") or {}
        policy = self._read_envelope(domain, "policy.json") or {}
        return (
            copy.deepcopy((targets.get("signed") or {}).get("releases") or []),
            copy.deepcopy((rollout.get("signed") or {}).get("policies") or []),
            copy.deepcopy((policy.get("signed") or {}).get("required_policy")),
        )

    def _commit(
        self,
        domain: str,
        *,
        releases: list[dict[str, Any]],
        rollouts: list[dict[str, Any]],
        required_policy: dict[str, Any] | None,
        action: str,
        actor: str,
        audit_old: Any = None,
        audit_new: Any = None,
    ) -> dict[str, Any]:
        target_version = self._role_version(domain, "targets") + 1
        rollout_version = self._role_version(domain, "rollout") + 1
        policy_version = self._role_version(domain, "policy") + 1
        targets_signed = {**self._base("targets", domain, target_version), "releases": releases}
        rollout_signed = {**self._base("rollout", domain, rollout_version), "policies": rollouts}
        policy_signed = {**self._base("policy", domain, policy_version), "required_policy": required_policy}
        targets_envelope = self.signer.sign("targets", targets_signed)
        rollout_envelope = self.signer.sign("rollout", rollout_signed)
        policy_envelope = self.signer.sign("policy", policy_signed)
        targets_content = self._write_role(domain, "targets", targets_envelope)
        rollout_content = self._write_role(domain, "rollout", rollout_envelope)
        policy_content = self._write_role(domain, "policy", policy_envelope)

        snapshot_version = self._role_version(domain, "snapshot") + 1
        snapshot_signed = {
            **self._base("snapshot", domain, snapshot_version),
            "meta": {
                "targets.json": metadata_record(targets_content, target_version),
                "rollout.json": metadata_record(rollout_content, rollout_version),
                "policy.json": metadata_record(policy_content, policy_version),
            },
        }
        snapshot_content = self._write_role(
            domain, "snapshot", self.signer.sign("snapshot", snapshot_signed)
        )
        timestamp_version = self._role_version(domain, "timestamp") + 1
        timestamp_signed = {
            **self._base("timestamp", domain, timestamp_version),
            "meta": {"snapshot.json": metadata_record(snapshot_content, snapshot_version)},
        }
        self._write_role(domain, "timestamp", self.signer.sign("timestamp", timestamp_signed))
        self._append_audit(domain, action, actor, audit_old, audit_new)
        return {
            "product_id": self.product_id,
            "domain": domain,
            "versions": {
                "targets": target_version,
                "rollout": rollout_version,
                "policy": policy_version,
                "snapshot": snapshot_version,
                "timestamp": timestamp_version,
            },
        }

    def _append_audit(self, domain: str, action: str, actor: str, old: Any, new: Any) -> None:
        audit = self._domain_root(domain) / "audit.ndjson"
        record = {
            "audit_id": f"audit_{uuid.uuid4().hex}",
            "at": format_utc(self._now()),
            "actor": str(actor or "local-author"),
            "action": action,
            "old": old,
            "new": new,
        }
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("ab") as stream:
            stream.write(_json_bytes(record))
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _artifact_kind_for_domain(domain: str, platform: str) -> str:
        if domain == "project_content":
            return "project_content"
        if domain == "ide":
            return "ide_package"
        return "android_apk" if platform == "android" else "windows_bundle"

    def publish_release(
        self,
        domain: str,
        artifacts: Iterable[Mapping[str, Any]],
        *,
        display_version: str,
        notes: str = "",
        release_sequence: int | None = None,
        supersedes: str = "",
        release_id_override: str = "",
        actor: str = "local-author",
    ) -> dict[str, Any]:
        self.initialize([domain])
        releases, rollouts, policy = self._current_payloads(domain)
        max_sequence = max((int(item.get("release_sequence") or 0) for item in releases), default=0)
        sequence = release_sequence if release_sequence is not None else max_sequence + 1
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= max_sequence:
            raise UpdateRepositoryError("UPD-ROLLBACK-001", "release_sequence 必须严格单调递增")

        prepared: list[tuple[Path, dict[str, Any]]] = []
        seed: list[dict[str, Any]] = []
        for raw in artifacts:
            source = Path(str(raw.get("source") or "")).expanduser().resolve()
            if not source.is_file():
                raise UpdateRepositoryError("UPD-ARTIFACT-001", f"更新产物不存在：{source}")
            platform = str(raw.get("platform") or "")
            architecture = str(raw.get("architecture") or "")
            kind = str(raw.get("kind") or self._artifact_kind_for_domain(domain, platform))
            size, digest = _file_sha256(source)
            record = {
                "artifact_id": str(raw.get("artifact_id") or f"artifact_{digest[:24]}"),
                "kind": kind,
                "platform": platform,
                "architecture": architecture,
                "length": size,
                "hashes": {"sha256": digest},
                "runtime_min": str(raw.get("runtime_min") or "0.0.0"),
                "runtime_max": str(raw.get("runtime_max") or "9999.0.0"),
                "ecir_min": str(raw.get("ecir_min") or "0.0.0"),
                "ecir_max": str(raw.get("ecir_max") or "9999.0.0"),
                "application_fingerprint": str(raw.get("application_fingerprint") or digest),
                "content_fingerprint": str(raw.get("content_fingerprint") or digest),
                "permissions_fingerprint": str(raw.get("permissions_fingerprint") or sha256_bytes(b"[]")),
                "abi": sorted({str(item) for item in raw.get("abi") or []}),
                "install_boundary": {
                    "project_content": "atomic_content_slot",
                    "android_apk": "android_package_installer",
                    "windows_bundle": "windows_update_helper",
                    "ide_package": "windows_update_helper",
                }.get(kind, ""),
            }
            if kind == "android_apk":
                record["android_version_code"] = raw.get("android_version_code")
                record["android_certificate_sha256"] = raw.get("android_certificate_sha256")
                previous_android = [
                    artifact
                    for release in releases
                    for artifact in release.get("artifacts") or []
                    if artifact.get("kind") == "android_apk"
                    and artifact.get("architecture") == architecture
                ]
                if previous_android:
                    latest_android = max(
                        previous_android,
                        key=lambda item: int(item.get("android_version_code") or 0),
                    )
                    if int(record.get("android_version_code") or 0) <= int(latest_android.get("android_version_code") or 0):
                        raise UpdateRepositoryError("UPD-ANDROID-001", "Android versionCode 必须严格递增")
                    if record.get("android_certificate_sha256") != latest_android.get("android_certificate_sha256"):
                        raise UpdateRepositoryError("UPD-ANDROID-002", "Android 更新 APK 签名证书与已发布应用不兼容")
            seed.append({key: value for key, value in record.items() if key != "path"})
            prepared.append((source, record))

        release_id = str(release_id_override or "").strip() or (
            f"release_{sha256_bytes(canonical_json_bytes({'domain': domain, 'sequence': sequence, 'artifacts': seed}))[:32]}"
        )
        if release_id in {str(item.get("release_id") or "") for item in releases}:
            raise UpdateRepositoryError("UPD-IMMUTABLE-001", "同一 release_id 已经发布，不能重复或原地覆盖")
        for source, record in prepared:
            suffix = "".join(source.suffixes[-2:]) if source.name.endswith(".tar.gz") else source.suffix
            name = f"{record['artifact_id']}{suffix or '.bin'}"
            relative = f"artifacts/{release_id}/{name}"
            record["path"] = relative
            validate_artifact(record)
        release = {
            "release_id": release_id,
            "release_sequence": sequence,
            "display_version": str(display_version or "").strip(),
            "created_at": format_utc(self._now()),
            "notes": str(notes or "")[:4000],
            "artifacts": [record for _source, record in prepared],
            "supersedes": str(supersedes or ""),
            "immutable": True,
        }
        validate_release(release, product_id=self.product_id, domain=domain)
        for source, record in prepared:
            destination = self._domain_root(domain) / record["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                existing = _file_sha256(destination)
                if existing != (record["length"], record["hashes"]["sha256"]):
                    raise UpdateRepositoryError("UPD-IMMUTABLE-001", "不可变发布路径已存在不同内容")
            else:
                temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
                try:
                    shutil.copyfile(source, temporary)
                    if _file_sha256(temporary) != (record["length"], record["hashes"]["sha256"]):
                        raise UpdateRepositoryError("UPD-ARTIFACT-002", "复制后的更新产物哈希不一致")
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
        releases.append(release)
        result = self._commit(
            domain,
            releases=releases,
            rollouts=rollouts,
            required_policy=policy,
            action="release.publish",
            actor=actor,
            audit_old={"max_sequence": max_sequence},
            audit_new={"release_id": release_id, "release_sequence": sequence},
        )
        return {**result, "release": release}

    def publish_project_content(
        self,
        bundle_path: str | Path,
        *,
        display_version: str,
        platform: str,
        architecture: str,
        expected_public_key: str | bytes | Path | Mapping[str, Any] | None = None,
        baseline_application_fingerprint: str = "",
        release_sequence: int | None = None,
        notes: str = "",
        actor: str = "local-author",
    ) -> dict[str, Any]:
        self.initialize(["project_content"])
        analysis = analyze_ecplayer_artifact(bundle_path, expected_public_key=expected_public_key)
        content_product_id = str(
            analysis.get("update_product_ids", {}).get("project_content")
            or analysis["project_id"]
        )
        if content_product_id != self.product_id:
            raise UpdateRepositoryError("UPD-TARGET-002", "项目内容产物属于其他 product_id")
        existing, _rollouts, _policy = self._current_payloads("project_content")
        previous_fingerprint = ""
        if existing:
            latest = max(existing, key=lambda item: int(item.get("release_sequence") or 0))
            previous_fingerprint = str((latest.get("artifacts") or [{}])[0].get("application_fingerprint") or "")
        baseline = str(
            baseline_application_fingerprint
            or previous_fingerprint
            or analysis["application_fingerprint"]
        )
        if analysis["application_fingerprint"] != baseline:
            raise UpdateRepositoryError(
                "UPD-CONTENT-001",
                "项目内容更新包含 Runtime、原生扩展、权限或宿主闭包变化，必须发布应用更新",
            )
        return self.publish_release(
            "project_content",
            [{
                "source": str(bundle_path),
                "platform": platform,
                "architecture": architecture,
                "kind": "project_content",
                "runtime_min": analysis["minimum_runtime_version"],
                "application_fingerprint": analysis["application_fingerprint"],
                "content_fingerprint": analysis["content_fingerprint"],
                "permissions_fingerprint": analysis["permissions_fingerprint"],
            }],
            display_version=display_version,
            notes=notes,
            release_sequence=release_sequence,
            release_id_override=analysis["release_id"],
            actor=actor,
        )

    def set_rollout(
        self,
        domain: str,
        *,
        release_id: str,
        channel: str,
        percent_bps: int = 0,
        whitelist_codes: Iterable[str] = (),
        whitelist_hashes: Iterable[str] = (),
        paused: bool = False,
        rollout_id: str = "",
        actor: str = "local-author",
    ) -> dict[str, Any]:
        releases, policies, required = self._current_payloads(domain)
        if release_id not in {item.get("release_id") for item in releases}:
            raise UpdateRepositoryError("UPD-ROLLOUT-001", "灰度策略引用未知发布")
        existing = next((item for item in policies if item.get("channel") == channel), None)
        hashes = [str(item).strip().lower() for item in whitelist_hashes]
        codes = [str(item).strip() for item in whitelist_codes]
        if any(not item for item in codes) or len(codes) != len(set(codes)):
            raise UpdateRepositoryError("UPD-ROLLOUT-001", "测试分组码包含空值或重复值")
        hashes.extend(group_code_hash(self.product_id, item) for item in codes)
        hashes = sorted(set(hashes))
        if existing:
            old_percent = int(existing.get("percent_bps") or 0)
            if release_id == existing.get("release_id") and percent_bps < old_percent:
                raise UpdateRepositoryError("UPD-ROLLOUT-002", "同一灰度发布的比例只能扩大")
            if release_id == existing.get("release_id") and rollout_id and rollout_id != existing.get("rollout_id"):
                raise UpdateRepositoryError("UPD-ROLLOUT-002", "继续或扩大灰度不能更换 rollout_id")
            revision = int(existing.get("policy_revision") or 0) + 1
            selected_rollout_id = str(existing.get("rollout_id")) if release_id == existing.get("release_id") else (
                rollout_id or f"rollout_{uuid.uuid4().hex}"
            )
        else:
            revision = 1
            selected_rollout_id = rollout_id or f"rollout_{uuid.uuid4().hex}"
        next_policy = {
            "policy_revision": revision,
            "rollout_id": selected_rollout_id,
            "release_id": release_id,
            "channel": channel,
            "percent_bps": percent_bps,
            "whitelist_hashes": hashes,
            "paused": paused,
            "issued_at": format_utc(self._now()),
        }
        validate_rollout_policy(next_policy, product_id=self.product_id, release_ids={item["release_id"] for item in releases})
        next_policies = [item for item in policies if item.get("channel") != channel] + [next_policy]
        next_policies.sort(key=lambda item: str(item.get("channel")))
        result = self._commit(
            domain,
            releases=releases,
            rollouts=next_policies,
            required_policy=required,
            action="rollout.update",
            actor=actor,
            audit_old=existing,
            audit_new=next_policy,
        )
        return {**result, "rollout": next_policy}

    def pause_rollout(self, domain: str, channel: str, *, actor: str = "local-author") -> dict[str, Any]:
        releases, policies, _required = self._current_payloads(domain)
        current = next((item for item in policies if item.get("channel") == channel), None)
        if current is None:
            raise UpdateRepositoryError("UPD-ROLLOUT-001", "当前通道没有可暂停的发布")
        return self.set_rollout(
            domain,
            release_id=str(current["release_id"]),
            channel=channel,
            percent_bps=int(current["percent_bps"]),
            whitelist_hashes=current["whitelist_hashes"],
            paused=True,
            rollout_id=str(current["rollout_id"]),
            actor=actor,
        )

    def resume_rollout(self, domain: str, channel: str, *, actor: str = "local-author") -> dict[str, Any]:
        _releases, policies, _required = self._current_payloads(domain)
        current = next((item for item in policies if item.get("channel") == channel), None)
        if current is None:
            raise UpdateRepositoryError("UPD-ROLLOUT-001", "当前通道没有可继续的发布")
        return self.set_rollout(
            domain,
            release_id=str(current["release_id"]),
            channel=channel,
            percent_bps=int(current["percent_bps"]),
            whitelist_hashes=current["whitelist_hashes"],
            paused=False,
            rollout_id=str(current["rollout_id"]),
            actor=actor,
        )

    def publish_required_policy(
        self,
        domain: str,
        *,
        release_id: str,
        effective_at: datetime,
        grace_deadline: datetime,
        reason: str,
        platform_targets: Iterable[str],
        actor: str = "local-author",
    ) -> dict[str, Any]:
        releases, rollouts, previous = self._current_payloads(domain)
        release = next((item for item in releases if item.get("release_id") == release_id), None)
        if release is None:
            raise UpdateRepositoryError("UPD-POLICY-001", "强制策略引用未知发布")
        stable = next((item for item in rollouts if item.get("channel") == "stable"), None)
        if (
            stable is None
            or stable.get("release_id") != release_id
            or stable.get("paused")
            or int(stable.get("percent_bps") or 0) != 10_000
        ):
            raise UpdateRepositoryError("UPD-POLICY-002", "目标发布必须先在稳定通道完成 100% 全量")
        requested = sorted(set(str(item) for item in platform_targets))
        available = {f"{item['platform']}:{item['architecture']}" for item in release["artifacts"]}
        missing = sorted(set(requested) - available)
        if not requested or missing:
            raise UpdateRepositoryError("UPD-POLICY-003", f"强制策略缺少兼容目标产物：{missing}")
        revision = int((previous or {}).get("policy_revision") or 0) + 1
        required = {
            "policy_revision": revision,
            "minimum_release_sequence": int(release["release_sequence"]),
            "target_release_id": release_id,
            "effective_at": format_utc(effective_at),
            "grace_deadline": format_utc(grace_deadline),
            "reason": str(reason or "").strip(),
            "platform_targets": requested,
            "issued_at": format_utc(self._now()),
            "revoked": False,
        }
        validate_required_policy(required, product_id=self.product_id, domain=domain)
        result = self._commit(
            domain,
            releases=releases,
            rollouts=rollouts,
            required_policy=required,
            action="required_policy.publish",
            actor=actor,
            audit_old=previous,
            audit_new=required,
        )
        return {**result, "required_policy": required}

    def revoke_required_policy(self, domain: str, *, actor: str = "local-author") -> dict[str, Any]:
        releases, rollouts, previous = self._current_payloads(domain)
        revision = int((previous or {}).get("policy_revision") or 0) + 1
        now = self._now()
        revoked = {
            "policy_revision": revision,
            "minimum_release_sequence": 0,
            "target_release_id": "",
            "effective_at": format_utc(now),
            "grace_deadline": format_utc(now),
            "reason": "",
            "platform_targets": [],
            "issued_at": format_utc(now),
            "revoked": True,
        }
        validate_required_policy(revoked, product_id=self.product_id, domain=domain)
        result = self._commit(
            domain,
            releases=releases,
            rollouts=rollouts,
            required_policy=revoked,
            action="required_policy.revoke",
            actor=actor,
            audit_old=previous,
            audit_new=revoked,
        )
        return {**result, "required_policy": revoked}


__all__ = [
    "StaticUpdateRepository",
    "UpdateRepositoryError",
    "UpdateRepositorySigner",
    "UpdateSigningKeyStore",
    "analyze_ecplayer_artifact",
]
