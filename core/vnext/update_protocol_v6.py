"""Open, signed EasyCode update-feed protocol.

The protocol deliberately keeps transport and trust separate.  A repository may
be served by EasyCode hosting or by an ordinary static HTTPS origin; clients
accept metadata only through the pinned, role-separated Ed25519 root below.
"""

from __future__ import annotations

import base64
import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .bundle_signing_v6 import AuthorSigningIdentity, canonical_json_bytes, public_key_id

UPDATE_PROTOCOL = "easycode-update-feed"
UPDATE_PROTOCOL_VERSION = 1
UPDATE_SIGNATURE_ALGORITHM = "Ed25519"
UPDATE_HASH_ALGORITHM = "SHA-256"
UPDATE_DOMAINS = ("ide", "player_application", "project_content")
UPDATE_ROLES = ("root", "targets", "snapshot", "timestamp", "rollout", "policy")
UPDATE_STATES = (
    "disabled",
    "idle",
    "checking",
    "available",
    "downloading",
    "staged",
    "waiting_safe_point",
    "awaiting_platform_install",
    "applying",
    "verifying",
    "complete",
    "failed",
    "rolled_back",
)

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


class UpdateProtocolError(ValueError):
    """A signed feed or author operation violates the frozen protocol."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: Any, *, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise UpdateProtocolError("UPD-META-001", f"{field} 不能为空")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UpdateProtocolError("UPD-META-001", f"{field} 不是有效 UTC 时间") from exc
    if parsed.tzinfo is None:
        raise UpdateProtocolError("UPD-META-001", f"{field} 必须包含时区")
    return parsed.astimezone(timezone.utc)


def _strict_dict(value: Any, *, owner: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UpdateProtocolError("UPD-META-001", f"{owner} 必须是对象")
    extra = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if extra or missing:
        raise UpdateProtocolError(
            "UPD-META-001",
            f"{owner} 字段无效：extra={extra}, missing={missing}",
        )
    return value


def _nonempty_id(value: Any, *, field: str) -> str:
    result = str(value or "").strip()
    if not _ID.fullmatch(result):
        raise UpdateProtocolError("UPD-META-001", f"{field} 不是有效稳定 ID")
    return result


def _positive_int(value: Any, *, field: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise UpdateProtocolError("UPD-META-001", f"{field} 必须是有效整数")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def group_code_hash(product_id: str, group_code: str) -> str:
    """Return the product-domain whitelist hash; the raw code never enters a feed."""

    return sha256_bytes((str(product_id) + str(group_code)).encode("utf-8"))


def rollout_bucket(product_id: str, rollout_id: str, group_code: str) -> int:
    """Frozen cross-platform bucket algorithm from UPDATES.md (0..9999)."""

    payload = (str(product_id) + str(rollout_id) + str(group_code)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest(), "big") % 10_000


@dataclass(frozen=True)
class UpdateSigningIdentity:
    key_id: str
    private_key: Ed25519PrivateKey
    public_key_bytes: bytes

    @classmethod
    def generate(cls) -> UpdateSigningIdentity:
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return cls(public_key_id(public), key, public)

    @classmethod
    def from_author(cls, identity: AuthorSigningIdentity) -> UpdateSigningIdentity:
        return cls(identity.key_id, identity.private_key, identity.public_key_bytes)

    @property
    def public_key_base64(self) -> str:
        return base64.b64encode(self.public_key_bytes).decode("ascii")


def key_document(identity: UpdateSigningIdentity) -> dict[str, Any]:
    return {
        "keytype": "ed25519",
        "scheme": "ed25519",
        "keyval": {"public": identity.public_key_base64},
    }


def sign_envelope(signed: Mapping[str, Any], identities: Iterable[UpdateSigningIdentity]) -> dict[str, Any]:
    payload = canonical_json_bytes(dict(signed))
    signatures = [
        {
            "keyid": identity.key_id,
            "sig": base64.b64encode(identity.private_key.sign(payload)).decode("ascii"),
        }
        for identity in identities
    ]
    if not signatures:
        raise UpdateProtocolError("UPD-SIGN-001", "签名角色没有可用私钥")
    signatures.sort(key=lambda item: item["keyid"])
    return {"signatures": signatures, "signed": dict(signed)}


def _public_key(record: Mapping[str, Any]) -> Ed25519PublicKey:
    try:
        if record.get("keytype") != "ed25519" or record.get("scheme") != "ed25519":
            raise ValueError
        raw = base64.b64decode(str((record.get("keyval") or {}).get("public") or ""), validate=True)
        if len(raw) != 32:
            raise ValueError
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:
        raise UpdateProtocolError("UPD-SIGN-002", "更新公钥格式无效") from exc


def verify_signatures(
    envelope: Mapping[str, Any],
    *,
    keys: Mapping[str, Mapping[str, Any]],
    key_ids: Iterable[str],
    threshold: int,
) -> dict[str, Any]:
    value = _strict_dict(
        dict(envelope), owner="签名信封", allowed={"signatures", "signed"}, required={"signatures", "signed"}
    )
    signed = value["signed"]
    signatures = value["signatures"]
    if not isinstance(signed, dict) or not isinstance(signatures, list):
        raise UpdateProtocolError("UPD-SIGN-002", "更新签名信封格式无效")
    allowed = set(key_ids)
    valid: set[str] = set()
    payload = canonical_json_bytes(signed)
    for item in signatures:
        if not isinstance(item, dict) or set(item) != {"keyid", "sig"}:
            raise UpdateProtocolError("UPD-SIGN-002", "更新签名记录格式无效")
        key_id = str(item.get("keyid") or "")
        if key_id not in allowed or key_id in valid:
            continue
        record = keys.get(key_id)
        if record is None:
            continue
        try:
            signature = base64.b64decode(str(item.get("sig") or ""), validate=True)
            _public_key(record).verify(signature, payload)
        except (ValueError, InvalidSignature, UpdateProtocolError):
            continue
        valid.add(key_id)
    if len(valid) < threshold:
        raise UpdateProtocolError("UPD-SIGN-003", "更新元数据没有达到角色签名阈值")
    return dict(signed)


def create_root_signed(
    *,
    product_id: str,
    version: int,
    expires: datetime,
    role_identities: Mapping[str, Iterable[UpdateSigningIdentity]],
    thresholds: Mapping[str, int] | None = None,
    mirrors: Iterable[str] = (),
) -> dict[str, Any]:
    product_id = _nonempty_id(product_id, field="product_id")
    version = _positive_int(version, field="root.version")
    threshold_values = dict(thresholds or {})
    keys: dict[str, Any] = {}
    roles: dict[str, Any] = {}
    for role in UPDATE_ROLES:
        identities = list(role_identities.get(role) or [])
        if not identities:
            raise UpdateProtocolError("UPD-ROOT-001", f"根元数据缺少 {role} 角色")
        for identity in identities:
            keys[identity.key_id] = key_document(identity)
        threshold = int(threshold_values.get(role, 1))
        if threshold < 1 or threshold > len(identities):
            raise UpdateProtocolError("UPD-ROOT-001", f"{role} 签名阈值无效")
        roles[role] = {"keyids": sorted(identity.key_id for identity in identities), "threshold": threshold}
    normalized_mirrors = sorted({str(item).strip().rstrip("/") for item in mirrors if str(item).strip()})
    return {
        "_type": "root",
        "spec_version": UPDATE_PROTOCOL_VERSION,
        "product_id": product_id,
        "version": version,
        "expires": format_utc(expires),
        "consistent_snapshot": True,
        "keys": keys,
        "roles": roles,
        "mirrors": normalized_mirrors,
    }


def validate_root_signed(value: Mapping[str, Any], *, expected_product_id: str = "") -> dict[str, Any]:
    root = _strict_dict(
        dict(value),
        owner="root",
        allowed={
            "_type", "spec_version", "product_id", "version", "expires",
            "consistent_snapshot", "keys", "roles", "mirrors",
        },
        required={
            "_type", "spec_version", "product_id", "version", "expires",
            "consistent_snapshot", "keys", "roles", "mirrors",
        },
    )
    if root["_type"] != "root" or root["spec_version"] != UPDATE_PROTOCOL_VERSION:
        raise UpdateProtocolError("UPD-ROOT-001", "根元数据版本不受支持")
    product_id = _nonempty_id(root["product_id"], field="root.product_id")
    if expected_product_id and product_id != expected_product_id:
        raise UpdateProtocolError("UPD-ROOT-002", "根元数据与当前产品不匹配")
    _positive_int(root["version"], field="root.version")
    parse_utc(root["expires"], field="root.expires")
    if root["consistent_snapshot"] is not True:
        raise UpdateProtocolError("UPD-ROOT-001", "更新源必须启用一致性快照")
    if not isinstance(root["keys"], dict) or not isinstance(root["roles"], dict):
        raise UpdateProtocolError("UPD-ROOT-001", "根元数据角色结构无效")
    if set(root["roles"]) != set(UPDATE_ROLES):
        raise UpdateProtocolError("UPD-ROOT-001", "根元数据角色集合不完整")
    for key_id, record in root["keys"].items():
        public = _public_key(record)
        raw = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        if key_id != public_key_id(raw):
            raise UpdateProtocolError("UPD-ROOT-003", "根元数据公钥指纹不一致")
    for role, record in root["roles"].items():
        _strict_dict(record, owner=f"root.roles.{role}", allowed={"keyids", "threshold"}, required={"keyids", "threshold"})
        ids = record["keyids"]
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or any(item not in root["keys"] for item in ids):
            raise UpdateProtocolError("UPD-ROOT-001", f"root.roles.{role}.keyids 无效")
        threshold = _positive_int(record["threshold"], field=f"root.roles.{role}.threshold")
        if threshold > len(ids):
            raise UpdateProtocolError("UPD-ROOT-001", f"root.roles.{role}.threshold 超出密钥数量")
    if not isinstance(root["mirrors"], list) or len(root["mirrors"]) != len(set(root["mirrors"])):
        raise UpdateProtocolError("UPD-ROOT-001", "root.mirrors 无效")
    return root


def verify_initial_root(
    envelope: Mapping[str, Any], *, product_id: str, pinned_public_key: bytes | str | None = None
) -> dict[str, Any]:
    unsigned = envelope.get("signed") if isinstance(envelope, Mapping) else None
    if not isinstance(unsigned, Mapping):
        raise UpdateProtocolError("UPD-ROOT-001", "根元数据签名信封无效")
    root = validate_root_signed(unsigned, expected_product_id=product_id)
    role = root["roles"]["root"]
    verified = verify_signatures(
        envelope,
        keys=root["keys"],
        key_ids=role["keyids"],
        threshold=role["threshold"],
    )
    root = validate_root_signed(verified, expected_product_id=product_id)
    if pinned_public_key is not None:
        try:
            raw = (
                base64.b64decode(pinned_public_key, validate=True)
                if isinstance(pinned_public_key, str)
                else bytes(pinned_public_key)
            )
        except Exception as exc:
            raise UpdateProtocolError("UPD-ROOT-003", "固定更新信任根格式无效") from exc
        if public_key_id(raw) not in set(root["roles"]["root"]["keyids"]):
            raise UpdateProtocolError("UPD-ROOT-003", "更新根与已安装发布者身份不匹配")
    return root


def verify_rotated_root(
    previous_root: Mapping[str, Any], envelope: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    old = validate_root_signed(previous_root)
    candidate_unsigned = envelope.get("signed") if isinstance(envelope, Mapping) else None
    if not isinstance(candidate_unsigned, Mapping):
        raise UpdateProtocolError("UPD-ROOT-001", "新根元数据签名信封无效")
    candidate = validate_root_signed(candidate_unsigned, expected_product_id=old["product_id"])
    if candidate["version"] != old["version"] + 1:
        raise UpdateProtocolError("UPD-ROLLBACK-001", "根元数据必须逐版本轮换")
    old_role = old["roles"]["root"]
    verify_signatures(envelope, keys=old["keys"], key_ids=old_role["keyids"], threshold=old_role["threshold"])
    new_role = candidate["roles"]["root"]
    verified = verify_signatures(
        envelope,
        keys=candidate["keys"],
        key_ids=new_role["keyids"],
        threshold=new_role["threshold"],
    )
    result = validate_root_signed(verified, expected_product_id=old["product_id"])
    if now is not None and parse_utc(result["expires"], field="root.expires") <= now.astimezone(timezone.utc):
        raise UpdateProtocolError("UPD-EXPIRED-001", "新根元数据已过期")
    return result


def verify_role_envelope(
    envelope: Mapping[str, Any],
    *,
    root: Mapping[str, Any],
    role: str,
    product_id: str,
    domain: str | None = None,
    minimum_version: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    trusted = validate_root_signed(root, expected_product_id=product_id)
    if role not in UPDATE_ROLES or role == "root":
        raise UpdateProtocolError("UPD-META-001", "更新元数据角色无效")
    descriptor = trusted["roles"][role]
    signed = verify_signatures(
        envelope,
        keys=trusted["keys"],
        key_ids=descriptor["keyids"],
        threshold=descriptor["threshold"],
    )
    required = {"_type", "spec_version", "product_id", "version", "expires", "issued_at"}
    if not required.issubset(signed):
        raise UpdateProtocolError("UPD-META-001", f"{role} 元数据缺少基础字段")
    if signed["_type"] != role or signed["spec_version"] != UPDATE_PROTOCOL_VERSION:
        raise UpdateProtocolError("UPD-META-001", f"{role} 元数据版本不受支持")
    if signed["product_id"] != product_id:
        raise UpdateProtocolError("UPD-META-002", f"{role} 元数据产品身份不一致")
    if domain is not None and signed.get("domain") != domain:
        raise UpdateProtocolError("UPD-META-002", f"{role} 元数据产品域不一致")
    version = _positive_int(signed["version"], field=f"{role}.version")
    if version < minimum_version:
        raise UpdateProtocolError("UPD-ROLLBACK-001", f"拒绝重放旧 {role} 元数据")
    issued_at = parse_utc(signed["issued_at"], field=f"{role}.issued_at")
    expires = parse_utc(signed["expires"], field=f"{role}.expires")
    reference = (now or utc_now()).astimezone(timezone.utc)
    if expires <= reference:
        raise UpdateProtocolError("UPD-EXPIRED-001", f"{role} 元数据已过期")
    if issued_at > reference.replace(microsecond=0):
        # A modest future tolerance belongs to the caller's trusted clock;
        # role verification itself never accepts metadata from the future.
        raise UpdateProtocolError("UPD-FREEZE-001", f"{role} 元数据签发时间晚于可信时间")
    return signed


def metadata_record(content: bytes, version: int) -> dict[str, Any]:
    return {
        "version": _positive_int(version, field="metadata.version"),
        "length": len(content),
        "hashes": {"sha256": sha256_bytes(content)},
    }


def verify_metadata_bytes(content: bytes, record: Mapping[str, Any], *, name: str) -> None:
    if int(record.get("length") or -1) != len(content):
        raise UpdateProtocolError("UPD-MIXMATCH-001", f"{name} 元数据长度与快照不一致")
    digest = str((record.get("hashes") or {}).get("sha256") or "")
    if not _HEX_64.fullmatch(digest) or digest != sha256_bytes(content):
        raise UpdateProtocolError("UPD-MIXMATCH-001", f"{name} 元数据哈希与快照不一致")


def validate_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    artifact = _strict_dict(
        dict(value),
        owner="artifact",
        allowed={
            "artifact_id", "kind", "platform", "architecture", "path", "length", "hashes",
            "runtime_min", "runtime_max", "ecir_min", "ecir_max", "application_fingerprint",
            "content_fingerprint", "permissions_fingerprint", "abi", "android_version_code",
            "android_certificate_sha256", "install_boundary",
        },
        required={
            "artifact_id", "kind", "platform", "architecture", "path", "length", "hashes",
            "runtime_min", "runtime_max", "ecir_min", "ecir_max", "application_fingerprint",
            "content_fingerprint", "permissions_fingerprint", "abi", "install_boundary",
        },
    )
    _nonempty_id(artifact["artifact_id"], field="artifact_id")
    if artifact["kind"] not in {"ide_package", "windows_bundle", "android_apk", "project_content"}:
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.kind 无效")
    if artifact["platform"] not in {"windows", "android"}:
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.platform 无效")
    if not isinstance(artifact["architecture"], str) or not artifact["architecture"]:
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.architecture 无效")
    path = str(artifact["path"] or "").replace("\\", "/")
    if not path.startswith("artifacts/") or path.startswith("/") or ".." in path.split("/"):
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.path 必须是仓库内不可变相对路径")
    _positive_int(artifact["length"], field="artifact.length")
    digest = str((artifact.get("hashes") or {}).get("sha256") or "")
    if not _HEX_64.fullmatch(digest):
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.sha256 无效")
    for field in ("application_fingerprint", "content_fingerprint", "permissions_fingerprint"):
        if not _HEX_64.fullmatch(str(artifact.get(field) or "")):
            raise UpdateProtocolError("UPD-TARGET-001", f"artifact.{field} 无效")
    if not isinstance(artifact["abi"], list) or len(artifact["abi"]) != len(set(artifact["abi"])):
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.abi 无效")
    expected_boundary = {
        "project_content": "atomic_content_slot",
        "android_apk": "android_package_installer",
        "windows_bundle": "windows_update_helper",
        "ide_package": "windows_update_helper",
    }[artifact["kind"]]
    if artifact["install_boundary"] != expected_boundary:
        raise UpdateProtocolError("UPD-TARGET-001", "artifact.install_boundary 与产物种类不一致")
    if artifact["kind"] == "android_apk":
        _positive_int(artifact.get("android_version_code"), field="artifact.android_version_code")
        if not _HEX_64.fullmatch(str(artifact.get("android_certificate_sha256") or "")):
            raise UpdateProtocolError("UPD-TARGET-001", "Android APK 缺少签名证书指纹")
    return artifact


def validate_release(value: Mapping[str, Any], *, product_id: str, domain: str) -> dict[str, Any]:
    release = _strict_dict(
        dict(value),
        owner="release",
        allowed={
            "release_id", "release_sequence", "display_version", "created_at", "notes",
            "artifacts", "supersedes", "immutable",
        },
        required={
            "release_id", "release_sequence", "display_version", "created_at", "notes",
            "artifacts", "supersedes", "immutable",
        },
    )
    _nonempty_id(release["release_id"], field="release_id")
    _positive_int(release["release_sequence"], field="release_sequence")
    parse_utc(release["created_at"], field="release.created_at")
    if release["immutable"] is not True:
        raise UpdateProtocolError("UPD-TARGET-001", "发布必须标记为不可变")
    if not isinstance(release["artifacts"], list) or not release["artifacts"]:
        raise UpdateProtocolError("UPD-TARGET-001", "发布没有平台产物")
    artifacts = [validate_artifact(item) for item in release["artifacts"]]
    ids = [item["artifact_id"] for item in artifacts]
    if len(ids) != len(set(ids)):
        raise UpdateProtocolError("UPD-TARGET-001", "发布包含重复 artifact_id")
    expected_kinds = {
        "ide": {"ide_package"},
        "player_application": {"windows_bundle", "android_apk"},
        "project_content": {"project_content"},
    }
    if domain not in UPDATE_DOMAINS or any(item["kind"] not in expected_kinds[domain] for item in artifacts):
        raise UpdateProtocolError("UPD-TARGET-002", "发布产物与更新产品域混搭")
    return release


def validate_targets_signed(value: Mapping[str, Any], *, product_id: str, domain: str) -> dict[str, Any]:
    targets = dict(value)
    if targets.get("_type") != "targets" or targets.get("domain") != domain:
        raise UpdateProtocolError("UPD-TARGET-001", "targets 元数据类型或产品域无效")
    releases = targets.get("releases")
    if not isinstance(releases, list):
        raise UpdateProtocolError("UPD-TARGET-001", "targets.releases 必须是列表")
    validated = [validate_release(item, product_id=product_id, domain=domain) for item in releases]
    sequences = [item["release_sequence"] for item in validated]
    release_ids = [item["release_id"] for item in validated]
    if len(sequences) != len(set(sequences)) or len(release_ids) != len(set(release_ids)):
        raise UpdateProtocolError("UPD-TARGET-001", "发布序号或 release_id 重复")
    if sequences != sorted(sequences):
        raise UpdateProtocolError("UPD-TARGET-001", "发布必须按序号递增排列")
    return targets


def validate_rollout_policy(value: Mapping[str, Any], *, product_id: str, release_ids: set[str]) -> dict[str, Any]:
    policy = _strict_dict(
        dict(value),
        owner="rollout policy",
        allowed={
            "policy_revision", "rollout_id", "release_id", "channel", "percent_bps",
            "whitelist_hashes", "paused", "issued_at",
        },
        required={
            "policy_revision", "rollout_id", "release_id", "channel", "percent_bps",
            "whitelist_hashes", "paused", "issued_at",
        },
    )
    _positive_int(policy["policy_revision"], field="policy_revision")
    _nonempty_id(policy["rollout_id"], field="rollout_id")
    if policy["release_id"] not in release_ids:
        raise UpdateProtocolError("UPD-ROLLOUT-001", "灰度策略引用未知 release_id")
    if policy["channel"] not in {"test", "stable"}:
        raise UpdateProtocolError("UPD-ROLLOUT-001", "灰度通道无效")
    percent = _positive_int(policy["percent_bps"], field="percent_bps", allow_zero=True)
    if percent > 10_000 or (policy["channel"] == "test" and percent != 0):
        raise UpdateProtocolError("UPD-ROLLOUT-001", "灰度比例无效")
    hashes = policy["whitelist_hashes"]
    if (
        not isinstance(hashes, list)
        or hashes != sorted(hashes)
        or len(hashes) != len(set(hashes))
        or any(not _HEX_64.fullmatch(str(item)) for item in hashes)
    ):
        raise UpdateProtocolError("UPD-ROLLOUT-001", "灰度白名单哈希无效")
    if not isinstance(policy["paused"], bool):
        raise UpdateProtocolError("UPD-ROLLOUT-001", "paused 必须是布尔值")
    parse_utc(policy["issued_at"], field="rollout.issued_at")
    return policy


def rollout_eligible(policy: Mapping[str, Any], *, product_id: str, group_code: str) -> bool:
    if bool(policy.get("paused")):
        return False
    hashed = group_code_hash(product_id, group_code)
    if hashed in set(policy.get("whitelist_hashes") or []):
        return True
    if policy.get("channel") == "test":
        return False
    percent = int(policy.get("percent_bps") or 0)
    return rollout_bucket(product_id, str(policy.get("rollout_id") or ""), group_code) < percent


def validate_required_policy(value: Mapping[str, Any], *, product_id: str, domain: str) -> dict[str, Any]:
    policy = _strict_dict(
        dict(value),
        owner="required policy",
        allowed={
            "policy_revision", "minimum_release_sequence", "target_release_id", "effective_at",
            "grace_deadline", "reason", "platform_targets", "issued_at", "revoked",
        },
        required={
            "policy_revision", "minimum_release_sequence", "target_release_id", "effective_at",
            "grace_deadline", "reason", "platform_targets", "issued_at", "revoked",
        },
    )
    _positive_int(policy["policy_revision"], field="required.policy_revision")
    _positive_int(policy["minimum_release_sequence"], field="required.minimum_release_sequence", allow_zero=True)
    if policy["minimum_release_sequence"] and not str(policy["target_release_id"] or ""):
        raise UpdateProtocolError("UPD-POLICY-001", "强制策略缺少目标 release_id")
    effective = parse_utc(policy["effective_at"], field="required.effective_at")
    deadline = parse_utc(policy["grace_deadline"], field="required.grace_deadline")
    if deadline < effective:
        raise UpdateProtocolError("UPD-POLICY-001", "强制策略宽限截止早于生效时间")
    if not isinstance(policy["reason"], str) or len(policy["reason"].strip()) > 500:
        raise UpdateProtocolError("UPD-POLICY-001", "强制策略原因无效")
    if not isinstance(policy["platform_targets"], list) or len(policy["platform_targets"]) != len(set(policy["platform_targets"])):
        raise UpdateProtocolError("UPD-POLICY-001", "强制策略平台目标无效")
    if not isinstance(policy["revoked"], bool):
        raise UpdateProtocolError("UPD-POLICY-001", "required.revoked 必须是布尔值")
    parse_utc(policy["issued_at"], field="required.issued_at")
    return policy


def version_in_range(current: str, minimum: str, maximum: str) -> bool:
    """Compare dotted numeric contracts without pulling packaging into Player."""

    def parts(value: str) -> tuple[int, ...]:
        result: list[int] = []
        for item in str(value or "0").split("."):
            match = re.match(r"^(\d+)", item)
            result.append(int(match.group(1)) if match else 0)
        return tuple((result + [0, 0, 0])[:3])

    value = parts(current)
    return parts(minimum) <= value <= parts(maximum)


def stable_probability_threshold(percent: float) -> int:
    if not math.isfinite(percent) or percent < 0 or percent > 100:
        raise UpdateProtocolError("UPD-ROLLOUT-001", "灰度百分比必须在 0 到 100 之间")
    return int(round(percent * 100))


__all__ = [
    "UPDATE_DOMAINS",
    "UPDATE_PROTOCOL",
    "UPDATE_PROTOCOL_VERSION",
    "UPDATE_ROLES",
    "UPDATE_STATES",
    "UpdateProtocolError",
    "UpdateSigningIdentity",
    "create_root_signed",
    "format_utc",
    "group_code_hash",
    "key_document",
    "metadata_record",
    "parse_utc",
    "rollout_bucket",
    "rollout_eligible",
    "sha256_bytes",
    "sign_envelope",
    "stable_probability_threshold",
    "utc_now",
    "validate_artifact",
    "validate_release",
    "validate_required_policy",
    "validate_rollout_policy",
    "validate_root_signed",
    "validate_targets_signed",
    "verify_initial_root",
    "verify_metadata_bytes",
    "verify_role_envelope",
    "verify_rotated_root",
    "verify_signatures",
    "version_in_range",
]
