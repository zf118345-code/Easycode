from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.update_feed_app import create_update_feed_app
from core.vnext.update_client_v6 import (
    DirectoryUpdateTransport,
    PlatformInstallResult,
    ProcessLeaseRegistry,
    UpdateClient,
    UpdateClientConfig,
    UpdateClientError,
)
from core.vnext.update_protocol_v6 import (
    UPDATE_ROLES,
    UpdateProtocolError,
    UpdateSigningIdentity,
    create_root_signed,
    group_code_hash,
    rollout_bucket,
    sign_envelope,
    verify_initial_root,
    verify_rotated_root,
)
from core.vnext.update_repository_v6 import StaticUpdateRepository, UpdateRepositorySigner


def _signer(product_id: str) -> UpdateRepositorySigner:
    return UpdateRepositorySigner(
        product_id,
        {role: UpdateSigningIdentity.generate() for role in UPDATE_ROLES},
    )


def _feed(tmp_path: Path, *, domain: str = "project_content") -> tuple[Path, dict, dict]:
    product_id = "project_update_test"
    signer = _signer(product_id)
    root = tmp_path / "feed"
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"signed project content v2")
    repository = StaticUpdateRepository(root, signer)
    published = repository.publish_release(
        domain,
        [{"source": str(payload), "platform": "windows", "architecture": "x86_64"}],
        display_version="2.0",
    )
    repository.set_rollout(
        domain,
        release_id=published["release"]["release_id"],
        channel="stable",
        percent_bps=10_000,
    )
    root_envelope = json.loads(
        (root / product_id / domain / "metadata" / "root.json").read_text(encoding="utf-8")
    )
    return root / product_id / domain, root_envelope, published


def _client(
    tmp_path: Path,
    feed: Path,
    root: dict,
    *,
    enabled: bool = True,
    current_sequence: int = 0,
    now=None,
) -> tuple[UpdateClient, DirectoryUpdateTransport]:
    transport = DirectoryUpdateTransport(feed)
    config = UpdateClientConfig(
        enabled=enabled,
        product_id="project_update_test" if enabled else "",
        domain="project_content",
        platform="windows",
        architecture="x86_64",
        current_release_id="release_old",
        current_release_sequence=current_sequence,
        feed_base_url="https://updates.invalid/feed" if enabled else "",
        pinned_root=root if enabled else None,
        required_policy_capability=enabled,
    )
    client = UpdateClient(
        config,
        durable_root=tmp_path / "durable",
        cache_root=tmp_path / "cache",
        transport=transport,
        now=now,
        random_seconds=lambda low, _high: low,
    )
    return client, transport


def test_static_feed_check_download_and_ab_apply(tmp_path: Path) -> None:
    feed, root, published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)

    checked = client.check(manual=True)
    assert checked.available is True
    assert checked.release["release_id"] == published["release"]["release_id"]
    downloaded = client.download()
    assert downloaded.read_bytes() == b"signed project content v2"
    applied = client.apply()

    assert applied["state"] == "complete"
    assert applied["current_release_id"] == published["release"]["release_id"]
    assert Path(applied["active_bundle_path"]).read_bytes() == b"signed project content v2"


def test_application_install_waits_for_final_receipt_then_reconciles(tmp_path: Path) -> None:
    feed, root, published = _feed(tmp_path, domain="player_application")

    class DeferredInstaller:
        healthy = None

        def stage(self, *_args):
            return PlatformInstallResult(True, completed=True)

        def apply(self, *_args):
            return PlatformInstallResult(
                True, requires_user_action=True, message="关闭 Player 后完成替换",
            )

        def confirmation(self, _release):
            return self.healthy

    installer = DeferredInstaller()
    client = UpdateClient(
        UpdateClientConfig(
            enabled=True,
            product_id="project_update_test",
            domain="player_application",
            platform="windows",
            architecture="x86_64",
            current_release_id="release_old",
            current_release_sequence=0,
            feed_base_url="https://updates.invalid/feed",
            pinned_root=root,
            required_policy_capability=True,
        ),
        durable_root=tmp_path / "durable",
        cache_root=tmp_path / "cache",
        transport=DirectoryUpdateTransport(feed),
        installer=installer,
    )
    assert client.check(manual=True).available
    client.download()

    waiting = client.apply()
    assert waiting["state"] == "awaiting_platform_install"
    assert waiting["platform_message"] == "关闭 Player 后完成替换"

    installer.healthy = True
    complete = client.status()
    assert complete["state"] == "complete"
    assert complete["current_release_id"] == published["release"]["release_id"]


def test_disabled_client_makes_zero_requests_and_creates_no_identity(tmp_path: Path) -> None:
    transport = DirectoryUpdateTransport(tmp_path)
    client, _ = _client(tmp_path, tmp_path, {}, enabled=False)
    client.transport = transport

    result = client.check(manual=True)

    assert result.state == "disabled"
    assert transport.request_count == 0
    assert not (tmp_path / "durable" / "identity").exists()


def test_etag_304_revalidates_cached_chain(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, transport = _client(tmp_path, feed, root)
    assert client.check(manual=True).checked
    before = transport.request_count

    result = client.check(manual=True)

    assert result.checked
    assert result.not_modified
    assert transport.request_count > before


def test_partial_download_resumes_with_range(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, transport = _client(tmp_path, feed, root)
    checked = client.check(manual=True)
    assert checked.artifact is not None
    partial = client.download_root / f"{checked.release['release_id']}-{checked.artifact['artifact_id']}.payload.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"signed ")

    client.download()

    assert any(path.startswith("artifacts/") for path in transport.paths)
    assert client.status()["state"] == "staged"


def test_tampered_metadata_is_rejected_and_old_install_remains(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    timestamp = feed / "metadata" / "timestamp.json"
    document = json.loads(timestamp.read_text(encoding="utf-8"))
    document["signed"]["version"] += 1
    timestamp.write_text(json.dumps(document), encoding="utf-8")
    client, _transport = _client(tmp_path, feed, root)

    result = client.check(manual=True)

    assert result.state == "failed"
    assert client.status()["current_release_id"] == "release_old"


def test_root_rotation_requires_old_and_new_thresholds() -> None:
    now = datetime.now(timezone.utc)
    old = {role: UpdateSigningIdentity.generate() for role in UPDATE_ROLES}
    new = {role: UpdateSigningIdentity.generate() for role in UPDATE_ROLES}
    old_signed = create_root_signed(
        product_id="root_rotation_test",
        version=1,
        expires=now + timedelta(days=30),
        role_identities={role: [identity] for role, identity in old.items()},
    )
    old_root = sign_envelope(old_signed, [old["root"]])
    trusted = verify_initial_root(old_root, product_id="root_rotation_test")
    new_signed = create_root_signed(
        product_id="root_rotation_test",
        version=2,
        expires=now + timedelta(days=60),
        role_identities={role: [identity] for role, identity in new.items()},
    )

    with pytest.raises(UpdateProtocolError):
        verify_rotated_root(trusted, sign_envelope(new_signed, [new["root"]]), now=now)

    rotated = sign_envelope(new_signed, [old["root"], new["root"]])
    assert verify_rotated_root(trusted, rotated, now=now)["version"] == 2


def test_rollout_bucket_is_stable_and_whitelist_is_product_scoped() -> None:
    assert rollout_bucket("p", "r", "secret") == rollout_bucket("p", "r", "secret")
    assert group_code_hash("p", "secret") != group_code_hash("other", "secret")


def test_clock_rollback_does_not_undo_cached_required_policy(tmp_path: Path) -> None:
    feed, root, published = _feed(tmp_path)
    # Required-policy behavior is covered by directly persisting the already
    # verified durable trust record; changing wall clock may never reduce the
    # client's trusted time or clear that policy.
    now = [datetime.now(timezone.utc)]
    client, _transport = _client(tmp_path, feed, root, now=lambda: now[0])
    trust = client._trust()
    deadline = now[0] - timedelta(hours=1)
    trust["last_required_policy"] = {
        "policy_revision": 1,
        "minimum_release_sequence": 1,
        "target_release_id": published["release"]["release_id"],
        "effective_at": (deadline - timedelta(hours=1)).isoformat(),
        "grace_deadline": deadline.isoformat(),
        "reason": "security update",
        "platform_targets": ["windows:x86_64"],
        "issued_at": (deadline - timedelta(hours=2)).isoformat(),
        "revoked": False,
    }
    client._write_trust(trust)
    assert client.task_start_block() is not None

    now[0] -= timedelta(days=365)

    assert client.task_start_block() is not None
    with pytest.raises(UpdateClientError):
        client.assert_task_start_allowed()


def test_static_reference_host_supports_etag_head_and_range(tmp_path: Path) -> None:
    feed, _root, _published = _feed(tmp_path)
    host = TestClient(create_update_feed_app(tmp_path / "feed"))
    prefix = "/feed/project_update_test/project_content"
    first = host.get(f"{prefix}/metadata/timestamp.json")
    assert first.status_code == 200
    assert first.headers["etag"].startswith('"sha256-')
    assert host.get(
        f"{prefix}/metadata/timestamp.json",
        headers={"If-None-Match": first.headers["etag"]},
    ).status_code == 304
    artifact = next((feed / "artifacts").rglob("*.*"))
    relative = artifact.relative_to(feed).as_posix()
    ranged = host.get(f"{prefix}/{relative}", headers={"Range": "bytes=1-5"})
    assert ranged.status_code == 206
    assert ranged.content == artifact.read_bytes()[1:6]
    assert host.head(f"{prefix}/{relative}").headers["content-length"] == str(artifact.stat().st_size)


def test_network_5xx_is_failure_not_up_to_date(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, transport = _client(tmp_path, feed, root)
    transport.failure_status = 503

    result = client.check(manual=True)

    assert result.state == "failed"
    assert result.checked is False
    assert "503" in result.message
    assert client.status()["last_verified_fresh"] is False


def test_ab_health_failure_restores_previous_pointer(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    client.health_check = lambda _path: False
    assert client.check(manual=True).available
    client.download()
    before = client.slots.status()

    result = client.apply()

    assert result["state"] == "rolled_back"
    assert client.slots.status()["active_slot"] == before["active_slot"]
    assert result["current_release_id"] == "release_old"


def test_live_second_instance_forces_waiting_safe_point(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    assert client.check(manual=True).available
    client.download()
    other = ProcessLeaseRegistry(client.durable_root, client.config.product_id, client.config.domain)
    other.register(release_id="release_old", safe=False)
    try:
        result = client.apply()
        assert result["state"] == "waiting_safe_point"
        other.update(release_id="release_old", safe=True)
        assert client.apply()["state"] == "complete"
    finally:
        other.unregister()


def test_required_policy_checker_ignores_optional_preference_and_downloads_no_artifact(tmp_path: Path) -> None:
    product_id = "project_update_test"
    signer = _signer(product_id)
    root_dir = tmp_path / "feed"
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"required update")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    repository = StaticUpdateRepository(root_dir, signer, now=lambda: now)
    published = repository.publish_release(
        "project_content",
        [{"source": str(payload), "platform": "windows", "architecture": "x86_64"}],
        display_version="2.0",
    )
    release_id = published["release"]["release_id"]
    repository.set_rollout("project_content", release_id=release_id, channel="stable", percent_bps=10_000)
    repository.publish_required_policy(
        "project_content",
        release_id=release_id,
        effective_at=now - timedelta(hours=2),
        grace_deadline=now - timedelta(hours=1),
        reason="签名安全修复",
        platform_targets=["windows:x86_64"],
    )
    feed = root_dir / product_id / "project_content"
    root = json.loads((feed / "metadata" / "root.json").read_text(encoding="utf-8"))
    transport = DirectoryUpdateTransport(feed)
    client = UpdateClient(
        UpdateClientConfig(
            enabled=True,
            product_id=product_id,
            domain="project_content",
            platform="windows",
            architecture="x86_64",
            current_release_id="release_old",
            current_release_sequence=0,
            automatic_checks=False,
            required_policy_capability=True,
            feed_base_url="https://updates.invalid/feed",
            pinned_root=root,
        ),
        durable_root=tmp_path / "durable",
        cache_root=tmp_path / "cache",
        transport=transport,
        now=lambda: now,
    )

    assert client.check().checked is False
    result = client.check(policy_only=True)

    assert result.checked is True
    assert client.task_start_block()["target_release_id"] == release_id
    assert not any(path.startswith("artifacts/") for path in transport.paths)
    assert "targets" not in " ".join(transport.paths)
    assert "rollout" not in " ".join(transport.paths)


def test_rollout_cannot_shrink_and_force_requires_stable_full_release(tmp_path: Path) -> None:
    product_id = "project_update_test"
    signer = _signer(product_id)
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"rollout")
    repository = StaticUpdateRepository(tmp_path / "feed", signer)
    published = repository.publish_release(
        "project_content",
        [{"source": str(payload), "platform": "windows", "architecture": "x86_64"}],
        display_version="2",
    )
    release_id = published["release"]["release_id"]
    repository.set_rollout("project_content", release_id=release_id, channel="stable", percent_bps=5000)
    with pytest.raises(UpdateProtocolError, match="只能扩大"):
        repository.set_rollout("project_content", release_id=release_id, channel="stable", percent_bps=4000)
    with pytest.raises(UpdateProtocolError, match="100%"):
        repository.publish_required_policy(
            "project_content",
            release_id=release_id,
            effective_at=datetime.now(timezone.utc),
            grace_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="required",
            platform_targets=["windows:x86_64"],
        )


def test_root_rotation_reissues_metadata_under_new_online_roles(tmp_path: Path) -> None:
    product_id = "rotation_repository"
    old_signer = _signer(product_id)
    repository = StaticUpdateRepository(tmp_path / "feed", old_signer)
    repository.initialize(["project_content"])
    new_identities = {role: UpdateSigningIdentity.generate() for role in UPDATE_ROLES}
    # The offline root identity may remain stable while every online role is
    # revoked and replaced.
    new_identities["root"] = old_signer.identities["root"]
    new_signer = UpdateRepositorySigner(product_id, new_identities, root_version=2)

    result = repository.rotate_root(new_signer, domains=["project_content"])

    assert result["root_version"] == 2
    feed = tmp_path / "feed" / product_id / "project_content"
    old_root = json.loads((feed / "metadata" / "1.root.json").read_text(encoding="utf-8"))
    rotated = json.loads((feed / "metadata" / "2.root.json").read_text(encoding="utf-8"))
    trusted = verify_initial_root(old_root, product_id=product_id)
    assert verify_rotated_root(trusted, rotated)["version"] == 2
    timestamp = json.loads((feed / "metadata" / "timestamp.json").read_text(encoding="utf-8"))
    assert timestamp["signatures"][0]["keyid"] == new_identities["timestamp"].key_id

    later = tmp_path / "after-rotation.bin"
    later.write_bytes(b"signed by the rotated online roles")
    repository.publish_release(
        "project_content",
        [{"source": str(later), "platform": "windows", "architecture": "x86_64"}],
        display_version="after-root-rotation",
    )
    timestamp = json.loads((feed / "metadata" / "timestamp.json").read_text(encoding="utf-8"))
    assert timestamp["signatures"][0]["keyid"] == new_identities["timestamp"].key_id


def test_same_metadata_version_with_different_signed_content_is_rejected(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    assert client.check(manual=True).checked
    timestamp = feed / "metadata" / "timestamp.json"
    envelope = json.loads(timestamp.read_text(encoding="utf-8"))
    # Re-signing is intentionally omitted: signature failure is the first of
    # the two independent protections against same-version mix-and-match.
    envelope["signed"]["issued_at"] = "2020-01-01T00:00:00Z"
    timestamp.write_text(json.dumps(envelope), encoding="utf-8")
    assert client.check(manual=True).state == "failed"


def test_artifact_tamper_is_rejected_before_staging(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    checked = client.check(manual=True)
    artifact_path = feed / checked.artifact["path"]
    artifact_path.write_bytes(artifact_path.read_bytes() + b"tampered")

    with pytest.raises(UpdateClientError, match="超过|哈希|不完整"):
        client.download()

    assert client.status()["state"] == "failed"
    assert client.status()["current_release_id"] == "release_old"


def test_disk_space_failure_preserves_partial_download_for_resume(tmp_path: Path, monkeypatch) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    checked = client.check(manual=True)
    partial = client.download_root / f"{checked.release['release_id']}-{checked.artifact['artifact_id']}.payload.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"sig")
    usage = shutil.disk_usage(tmp_path)
    monkeypatch.setattr(
        "core.vnext.update_client_v6.shutil.disk_usage",
        lambda _path: type(usage)(usage.total, usage.used, 0),
    )

    with pytest.raises(UpdateClientError, match="磁盘空间不足"):
        client.download()

    assert partial.read_bytes() == b"sig"


def test_android_apk_version_and_certificate_boundaries(tmp_path: Path) -> None:
    signer = _signer("android.application.test")
    repository = StaticUpdateRepository(tmp_path / "feed", signer)
    certificate = "a" * 64
    fingerprint = "b" * 64

    def publish(name: str, version_code: int, cert: str = certificate):
        artifact = tmp_path / name
        artifact.write_bytes(name.encode("utf-8"))
        return repository.publish_release(
            "player_application",
            [{
                "source": str(artifact),
                "platform": "android",
                "architecture": "arm64-v8a",
                "application_fingerprint": fingerprint,
                "permissions_fingerprint": "c" * 64,
                "abi": ["arm64-v8a"],
                "android_version_code": version_code,
                "android_certificate_sha256": cert,
            }],
            display_version=str(version_code),
        )

    publish("one.apk", 1)
    publish("two.apk", 2)
    with pytest.raises(UpdateProtocolError, match="versionCode"):
        publish("lower.apk", 2)
    with pytest.raises(UpdateProtocolError, match="签名证书"):
        publish("other.apk", 3, "d" * 64)


def test_signed_older_timestamp_is_rejected_after_newer_revision_seen(tmp_path: Path) -> None:
    feed, root, _published = _feed(tmp_path)
    client, _transport = _client(tmp_path, feed, root)
    assert client.check(manual=True).checked
    metadata = feed / "metadata"
    current_version = json.loads((metadata / "timestamp.json").read_text(encoding="utf-8"))["signed"]["version"]
    assert current_version > 1
    older = metadata / f"{current_version - 1}.timestamp.json"
    assert older.is_file()
    (metadata / "timestamp.json").write_bytes(older.read_bytes())

    result = client.check(manual=True)

    assert result.state == "failed"
    assert "重放" in result.message


def test_expired_timestamp_fails_without_disabling_installed_release(tmp_path: Path) -> None:
    old = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=3)
    signer = _signer("project_update_test")
    root_dir = tmp_path / "feed"
    repository = StaticUpdateRepository(root_dir, signer, now=lambda: old)
    repository.initialize(["project_content"])
    feed = root_dir / "project_update_test" / "project_content"
    root = json.loads((feed / "metadata" / "root.json").read_text(encoding="utf-8"))
    client, _transport = _client(tmp_path, feed, root)

    result = client.check(manual=True)

    assert result.state == "failed"
    assert "过期" in result.message
    assert client.status()["current_release_id"] == "release_old"
