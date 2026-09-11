"""Author signing and strict integrity verification for format-6 Player bundles.

The editable project never contains a private key.  Windows authoring stores an
Ed25519 key under the current user's DPAPI boundary; the published bundle only
contains the public identity, a deterministic content manifest and a signature.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import tempfile
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

BUNDLE_FORMAT_V6 = 2
INTEGRITY_PATH = "META-INF/integrity.json"
SIGNATURE_PATH = "META-INF/signature.json"
SIGNATURE_ALGORITHM = "Ed25519"
HASH_ALGORITHM = "SHA-256"


class BundleSignatureError(ValueError):
    """Raised before extraction when a bundle cannot be trusted."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one signing representation shared by publisher and loader."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def public_key_id(public_key_bytes: bytes) -> str:
    return f"ed25519-sha256:{sha256_hex(public_key_bytes)}"


@dataclass(frozen=True)
class AuthorSigningIdentity:
    product_id: str
    key_id: str
    private_key: Ed25519PrivateKey
    public_key_bytes: bytes

    @property
    def public_key_base64(self) -> str:
        return base64.b64encode(self.public_key_bytes).decode("ascii")


class AuthorSigningKeyStore:
    """Windows-user protected author keys kept outside project and repository."""

    SCHEMA_VERSION = 1
    PREFIX = "dpapi-user:"

    def __init__(self, root: str | Path | None = None) -> None:
        configured = str(os.environ.get("EASYCODE_SIGNING_KEY_DIR") or "").strip()
        base = Path(
            configured
            or root
            or (
                Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
                / "EasyCode"
                / "SigningKeys"
            )
        )
        self.root = base.expanduser().resolve()

    @staticmethod
    def _protect(raw: bytes) -> str:
        if os.name != "nt":
            raise BundleSignatureError("发布私钥需要 Windows 当前用户安全凭据存储")
        try:
            import win32crypt

            protected = win32crypt.CryptProtectData(raw, None, None, None, None, 0)
        except Exception as exc:  # pragma: no cover - depends on Windows profile
            raise BundleSignatureError("当前 Windows 用户的安全凭据存储不可用") from exc
        return AuthorSigningKeyStore.PREFIX + base64.b64encode(protected).decode("ascii")

    @staticmethod
    def _unprotect(value: str) -> bytes:
        if not isinstance(value, str) or not value.startswith(AuthorSigningKeyStore.PREFIX):
            raise BundleSignatureError("发布私钥记录格式无效")
        if os.name != "nt":
            raise BundleSignatureError("发布私钥只能由创建它的 Windows 用户读取")
        try:
            import win32crypt

            protected = base64.b64decode(value[len(AuthorSigningKeyStore.PREFIX) :], validate=True)
            return bytes(win32crypt.CryptUnprotectData(protected, None, None, None, 0)[1])
        except Exception as exc:
            raise BundleSignatureError("发布私钥无法由当前 Windows 用户解密") from exc

    def _path(self, product_id: str) -> Path:
        digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    @staticmethod
    def _private_bytes(private_key: Ed25519PrivateKey) -> bytes:
        return private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    @staticmethod
    def _public_bytes(private_key: Ed25519PrivateKey) -> bytes:
        return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def get_or_create(self, product_id: str) -> AuthorSigningIdentity:
        clean_product_id = str(product_id or "").strip()
        if not clean_product_id:
            raise BundleSignatureError("项目缺少稳定 product_id，不能建立发布签名身份")
        path = self._path(clean_product_id)
        if path.is_file():
            try:
                document = json.loads(path.read_text(encoding="utf-8-sig"))
                if int(document.get("schema_version") or 0) != self.SCHEMA_VERSION:
                    raise BundleSignatureError("发布私钥记录版本不受支持")
                if str(document.get("product_id") or "") != clean_product_id:
                    raise BundleSignatureError("发布私钥记录与当前产品不匹配")
                private_key = Ed25519PrivateKey.from_private_bytes(
                    self._unprotect(str(document.get("protected_private_key") or ""))
                )
            except BundleSignatureError:
                raise
            except Exception as exc:
                raise BundleSignatureError("发布私钥记录已损坏") from exc
            public_bytes = self._public_bytes(private_key)
            key_id = public_key_id(public_bytes)
            if str(document.get("key_id") or "") != key_id:
                raise BundleSignatureError("发布私钥记录的公钥指纹不一致")
            return AuthorSigningIdentity(clean_product_id, key_id, private_key, public_bytes)

        self.root.mkdir(parents=True, exist_ok=True)
        private_key = Ed25519PrivateKey.generate()
        private_bytes = self._private_bytes(private_key)
        public_bytes = self._public_bytes(private_key)
        key_id = public_key_id(public_bytes)
        document = {
            "schema_version": self.SCHEMA_VERSION,
            "product_id": clean_product_id,
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id": key_id,
            "public_key": base64.b64encode(public_bytes).decode("ascii"),
            "protected_private_key": self._protect(private_bytes),
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            with contextlib.suppress(OSError):
                os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return AuthorSigningIdentity(clean_product_id, key_id, private_key, public_bytes)


def create_integrity_document(entries: Mapping[str, bytes]) -> dict[str, Any]:
    if not entries:
        raise BundleSignatureError("Player 包没有可签名内容")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_path, content in sorted(entries.items()):
        path = str(raw_path).replace("\\", "/")
        parsed = PurePosixPath(path)
        if (
            not path
            or parsed.is_absolute()
            or ".." in parsed.parts
            or path in {INTEGRITY_PATH, SIGNATURE_PATH}
            or path in seen
        ):
            raise BundleSignatureError(f"Player 包签名路径无效：{raw_path}")
        seen.add(path)
        records.append({"path": path, "size": len(content), "sha256": sha256_hex(content)})
    return {
        "schema_version": 1,
        "hash_algorithm": HASH_ALGORITHM,
        "entries": records,
    }


def create_integrity_document_from_records(
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate publisher-produced streaming records without loading assets."""

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda item: str(item.get("path") or "")):
        path = str(record.get("path") or "").replace("\\", "/")
        parsed = PurePosixPath(path)
        size = record.get("size")
        digest = str(record.get("sha256") or "")
        if (
            not path
            or parsed.is_absolute()
            or ".." in parsed.parts
            or path in {INTEGRITY_PATH, SIGNATURE_PATH}
            or path in seen
            or not isinstance(size, int)
            or size < 0
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise BundleSignatureError(f"Player 包完整性记录无效：{path or '<empty>'}")
        seen.add(path)
        normalized.append({"path": path, "size": size, "sha256": digest})
    if not normalized:
        raise BundleSignatureError("Player 包没有可签名内容")
    return {
        "schema_version": 1,
        "hash_algorithm": HASH_ALGORITHM,
        "entries": normalized,
    }


def sign_integrity_document(
    integrity: Mapping[str, Any], identity: AuthorSigningIdentity,
) -> dict[str, Any]:
    payload = canonical_json_bytes(dict(integrity))
    signature = identity.private_key.sign(payload)
    return {
        "schema_version": 1,
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": identity.key_id,
        "public_key": identity.public_key_base64,
        "signed_document": INTEGRITY_PATH,
        "signed_sha256": sha256_hex(payload),
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def sign_entries(
    entries: Mapping[str, bytes], identity: AuthorSigningIdentity,
) -> tuple[dict[str, Any], dict[str, Any]]:
    integrity = create_integrity_document(entries)
    return integrity, sign_integrity_document(integrity, identity)


def _decode_public_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(str(value or ""), validate=True)
    except Exception as exc:
        raise BundleSignatureError("Player 包发布公钥格式无效") from exc
    if len(decoded) != 32:
        raise BundleSignatureError("Player 包发布公钥长度无效")
    return decoded


def parse_trust_root(value: str | bytes | Path | Mapping[str, Any] | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return _decode_public_key(str(value.get("public_key") or ""))
    path: Path | None = value if isinstance(value, Path) else None
    if isinstance(value, str):
        candidate = Path(value)
        try:
            if candidate.is_file():
                path = candidate
        except OSError:
            path = None
    if path is not None:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise BundleSignatureError("Player 发布信任根无法读取") from exc
        if not isinstance(document, dict):
            raise BundleSignatureError("Player 发布信任根格式无效")
        return _decode_public_key(str(document.get("public_key") or ""))
    if isinstance(value, bytes):
        if len(value) != 32:
            raise BundleSignatureError("Player 发布信任根长度无效")
        return value
    return _decode_public_key(str(value))


def verify_signed_archive(
    archive: zipfile.ZipFile,
    expected_public_key: str | bytes | Path | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    names = [item.filename.replace("\\", "/") for item in archive.infolist() if not item.is_dir()]
    if len(names) != len(set(names)):
        raise BundleSignatureError("Player 包包含重复文件路径")
    if INTEGRITY_PATH not in names or SIGNATURE_PATH not in names:
        raise BundleSignatureError("Player 包缺少完整性清单或发布签名")
    try:
        integrity = json.loads(archive.read(INTEGRITY_PATH))
        envelope = json.loads(archive.read(SIGNATURE_PATH))
    except Exception as exc:
        raise BundleSignatureError("Player 包签名元数据无法读取") from exc
    if not isinstance(integrity, dict) or not isinstance(envelope, dict):
        raise BundleSignatureError("Player 包签名元数据格式无效")
    if int(integrity.get("schema_version") or 0) != 1:
        raise BundleSignatureError("Player 包完整性清单版本不受支持")
    if str(integrity.get("hash_algorithm") or "") != HASH_ALGORITHM:
        raise BundleSignatureError("Player 包哈希算法不受支持")
    if int(envelope.get("schema_version") or 0) != 1:
        raise BundleSignatureError("Player 包签名格式版本不受支持")
    if str(envelope.get("algorithm") or "") != SIGNATURE_ALGORITHM:
        raise BundleSignatureError("Player 包签名算法不受支持")
    if str(envelope.get("signed_document") or "") != INTEGRITY_PATH:
        raise BundleSignatureError("Player 包签名范围无效")

    public_bytes = _decode_public_key(str(envelope.get("public_key") or ""))
    key_id = public_key_id(public_bytes)
    if str(envelope.get("key_id") or "") != key_id:
        raise BundleSignatureError("Player 包发布者公钥指纹不一致")
    expected = parse_trust_root(expected_public_key)
    if expected is not None and expected != public_bytes:
        raise BundleSignatureError("Player 包发布者与已固定信任根不匹配")
    payload = canonical_json_bytes(integrity)
    if str(envelope.get("signed_sha256") or "") != sha256_hex(payload):
        raise BundleSignatureError("Player 包签名载荷哈希不一致")
    try:
        signature = base64.b64decode(str(envelope.get("signature") or ""), validate=True)
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, payload)
    except (ValueError, InvalidSignature) as exc:
        raise BundleSignatureError("Player 包发布签名验证失败") from exc

    records = integrity.get("entries")
    if not isinstance(records, list) or not records:
        raise BundleSignatureError("Player 包完整性清单没有文件记录")
    expected_names = set(names) - {INTEGRITY_PATH, SIGNATURE_PATH}
    listed_names: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise BundleSignatureError("Player 包完整性记录格式无效")
        path = str(record.get("path") or "").replace("\\", "/")
        if path in listed_names or path not in expected_names:
            raise BundleSignatureError(f"Player 包完整性记录路径无效：{path or '<empty>'}")
        listed_names.add(path)
        content = archive.read(path)
        if int(record.get("size") or -1) != len(content):
            raise BundleSignatureError(f"Player 包文件大小校验失败：{path}")
        if str(record.get("sha256") or "") != sha256_hex(content):
            raise BundleSignatureError(f"Player 包文件哈希校验失败：{path}")
    missing = sorted(expected_names - listed_names)
    if missing:
        raise BundleSignatureError(f"Player 包存在未签名文件：{missing[0]}")
    return {
        "verified": True,
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "public_key": base64.b64encode(public_bytes).decode("ascii"),
        "integrity_sha256": sha256_hex(payload),
        "files": len(records),
    }


def trust_root_document(signature: Mapping[str, Any], product_id: str) -> dict[str, Any]:
    public_bytes = _decode_public_key(str(signature.get("public_key") or ""))
    key_id = public_key_id(public_bytes)
    if str(signature.get("key_id") or "") != key_id:
        raise BundleSignatureError("Player 包签名无法生成信任根")
    return {
        "schema_version": 1,
        "product_id": str(product_id or ""),
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "public_key": base64.b64encode(public_bytes).decode("ascii"),
    }
