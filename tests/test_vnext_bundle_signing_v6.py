from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.vnext.bundle_signing_v6 import (
    INTEGRITY_PATH,
    SIGNATURE_PATH,
    AuthorSigningIdentity,
    BundleSignatureError,
    canonical_json_bytes,
    public_key_id,
    sign_entries,
    verify_signed_archive,
)


def _identity(product_id: str = 'product_test') -> AuthorSigningIdentity:
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return AuthorSigningIdentity(
        product_id=product_id,
        key_id=public_key_id(public_bytes),
        private_key=private_key,
        public_key_bytes=public_bytes,
    )


def _bundle(path: Path, entries: dict[str, bytes], identity: AuthorSigningIdentity) -> None:
    integrity, signature = sign_entries(entries, identity)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
        archive.writestr(INTEGRITY_PATH, canonical_json_bytes(integrity))
        archive.writestr(SIGNATURE_PATH, canonical_json_bytes(signature))


def test_signed_archive_verifies_every_file_and_pinned_author(tmp_path: Path) -> None:
    identity = _identity()
    bundle = tmp_path / 'signed.ecplayer'
    _bundle(
        bundle,
        {
            'manifest.json': b'{"bundle_format":2}',
            'runtime/ecir.json': b'{"functions":[]}',
        },
        identity,
    )

    with zipfile.ZipFile(bundle) as archive:
        verified = verify_signed_archive(archive, identity.public_key_base64)

    assert verified['verified'] is True
    assert verified['key_id'] == identity.key_id
    assert verified['files'] == 2


def test_tampered_file_is_rejected_before_extraction(tmp_path: Path) -> None:
    identity = _identity()
    original = tmp_path / 'original.ecplayer'
    tampered = tmp_path / 'tampered.ecplayer'
    _bundle(original, {'manifest.json': b'original'}, identity)
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(tampered, 'w') as destination:
        for info in source.infolist():
            content = b'tampered' if info.filename == 'manifest.json' else source.read(info.filename)
            destination.writestr(info, content)

    with zipfile.ZipFile(tampered) as archive, pytest.raises(
        BundleSignatureError,
        match='哈希校验失败',
    ):
        verify_signed_archive(archive)


def test_self_signed_replacement_is_rejected_by_pinned_trust_root(tmp_path: Path) -> None:
    trusted = _identity('product_trusted')
    attacker = _identity('product_attacker')
    bundle = tmp_path / 'attacker.ecplayer'
    _bundle(bundle, {'manifest.json': b'{}'}, attacker)

    with zipfile.ZipFile(bundle) as archive, pytest.raises(
        BundleSignatureError,
        match='固定信任根不匹配',
    ):
        verify_signed_archive(archive, trusted.public_key_base64)


def test_unsigned_and_unlisted_files_are_rejected(tmp_path: Path) -> None:
    unsigned = tmp_path / 'unsigned.ecplayer'
    with zipfile.ZipFile(unsigned, 'w') as archive:
        archive.writestr('manifest.json', '{}')
    with zipfile.ZipFile(unsigned) as archive, pytest.raises(
        BundleSignatureError,
        match='缺少完整性清单',
    ):
        verify_signed_archive(archive)

    identity = _identity()
    smuggled = tmp_path / 'smuggled.ecplayer'
    integrity, signature = sign_entries({'manifest.json': b'{}'}, identity)
    with zipfile.ZipFile(smuggled, 'w') as archive:
        archive.writestr('manifest.json', '{}')
        archive.writestr('hidden/payload.bin', b'not signed')
        archive.writestr(INTEGRITY_PATH, json.dumps(integrity))
        archive.writestr(SIGNATURE_PATH, json.dumps(signature))
    with zipfile.ZipFile(smuggled) as archive, pytest.raises(
        BundleSignatureError,
        match='未签名文件',
    ):
        verify_signed_archive(archive)
