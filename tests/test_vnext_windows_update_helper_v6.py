from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from core.vnext.update_client_v6 import CommandPlatformInstaller
from core.vnext.windows_update_helper_v6 import (
    WindowsApplicationPackage,
    WindowsUpdateHelper,
    WindowsUpdateHelperError,
)


def _handoff(tmp_path: Path, artifact: Path, *, release_id: str = "release:windows/v2") -> Path:
    payload = artifact.read_bytes()
    path = tmp_path / "handoffs" / "apply.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version": 2,
        "action": "apply",
        "artifact_path": str(artifact),
        "artifact_sha256": hashlib.sha256(payload).hexdigest(),
        "artifact_length": len(payload),
        "release_id": release_id,
        "release_sequence": 2,
        "install_boundary": "windows_update_helper",
        "install_root": str(tmp_path / "installed"),
        "restart_command": ["EasycodePlayer.exe", "--mode", "prod"],
        "parent_pid": 0,
        "handoff_root": str(tmp_path / "handoffs"),
    }), encoding="utf-8")
    return path


def _package(tmp_path: Path, *, healthy_name: str = "new") -> Path:
    source = tmp_path / f"source-{healthy_name}"
    source.mkdir()
    (source / "EasycodePlayer.exe").write_bytes(healthy_name.encode("utf-8"))
    (source / "release").mkdir()
    (source / "release" / "version.txt").write_text("2", encoding="utf-8")
    package = tmp_path / f"{healthy_name}.zip"
    WindowsApplicationPackage.build(
        source, package, release_id="release:windows/v2", entrypoint="EasycodePlayer.exe",
    )
    return package


class _Process:
    def __init__(self, _command, *, env=None, healthy: bool, **_kwargs) -> None:
        self._healthy = healthy
        self._terminated = False
        if healthy and env and env.get("EASYCODE_WINDOWS_UPDATE_RECEIPT"):
            path = Path(env["EASYCODE_WINDOWS_UPDATE_RECEIPT"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "schema_version": 1,
                "status": "healthy",
                "token": env["EASYCODE_WINDOWS_UPDATE_TOKEN"],
                "pid": 123,
            }), encoding="utf-8")

    def poll(self):
        return None if self._healthy and not self._terminated else 1

    def terminate(self) -> None:
        self._terminated = True


def test_package_is_strict_and_rejects_unlisted_member(tmp_path: Path) -> None:
    package = _package(tmp_path)
    inspected = WindowsApplicationPackage.inspect(package, expected_release_id="release:windows/v2")
    assert inspected["manifest"]["entrypoint"] == "EasycodePlayer.exe"

    with zipfile.ZipFile(package, "a") as archive:
        archive.writestr("surprise.dll", b"not listed")
    with pytest.raises(WindowsUpdateHelperError, match="未列入清单"):
        WindowsApplicationPackage.inspect(package)


def test_successful_directory_swap_requires_health_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _package(tmp_path)
    handoff = _handoff(tmp_path, package)
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "EasycodePlayer.exe").write_bytes(b"old")
    helper = WindowsUpdateHelper(handoff)
    helper.stage()
    monkeypatch.setattr(
        "core.vnext.windows_update_helper_v6.subprocess.Popen",
        lambda *args, **kwargs: _Process(*args, healthy=True, **kwargs),
    )

    helper.execute(health_seconds=0.2)

    assert (installed / "EasycodePlayer.exe").read_bytes() == b"new"
    assert (helper.backup / "EasycodePlayer.exe").read_bytes() == b"old"
    receipt = json.loads(helper.receipt.read_text(encoding="utf-8"))
    assert receipt["status"] == "healthy"
    assert receipt["release_sequence"] == 2


def test_failed_start_rolls_back_old_directory_and_records_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package(tmp_path, healthy_name="broken")
    handoff = _handoff(tmp_path, package)
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "EasycodePlayer.exe").write_bytes(b"old")
    helper = WindowsUpdateHelper(handoff)
    helper.stage()
    monkeypatch.setattr(
        "core.vnext.windows_update_helper_v6.subprocess.Popen",
        lambda *args, **kwargs: _Process(*args, healthy=False, **kwargs),
    )

    with pytest.raises(WindowsUpdateHelperError, match="启动健康"):
        helper.execute(health_seconds=0.02)

    assert (installed / "EasycodePlayer.exe").read_bytes() == b"old"
    assert (helper.failed / "EasycodePlayer.exe").read_bytes() == b"broken"
    receipt = json.loads(helper.receipt.read_text(encoding="utf-8"))
    assert receipt["status"] == "rolled_back"
    assert receipt["code"] == "UPD-HEALTH-001"


def test_host_handoff_paths_are_hashed_and_receipt_is_verified(tmp_path: Path) -> None:
    artifact_path = tmp_path / "payload.zip"
    artifact_path.write_bytes(b"payload")
    digest = hashlib.sha256(b"payload").hexdigest()
    release = {
        "release_id": "release:windows/v2",
        "release_sequence": 2,
        "artifacts": [{"hashes": {"sha256": digest}}],
    }
    artifact = {
        "length": len(b"payload"),
        "hashes": {"sha256": digest},
        "install_boundary": "windows_update_helper",
    }
    installer = CommandPlatformInstaller(
        ["helper.exe"], tmp_path / "handoffs",
        install_root=tmp_path / "installed",
        restart_command=["EasycodePlayer.exe"],
        parent_pid=0,
    )

    handoff = installer._handoff(artifact_path, artifact, release, "stage")
    assert ":" not in handoff.name and "/" not in handoff.name
    document = json.loads(handoff.read_text(encoding="utf-8"))
    assert document["schema_version"] == 2
    assert document["install_root"] == str((tmp_path / "installed").resolve())
    assert installer.confirmation(release) is None

    release_key = hashlib.sha256(release["release_id"].encode("utf-8")).hexdigest()
    receipt = tmp_path / "handoffs" / "receipts" / f"{release_key}.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "schema_version": 1,
        "release_id": release["release_id"],
        "release_sequence": 2,
        "artifact_sha256": digest,
        "status": "healthy",
    }), encoding="utf-8")
    assert installer.confirmation(release) is True
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["artifact_sha256"] = "0" * 64
    receipt.write_text(json.dumps(value), encoding="utf-8")
    assert installer.confirmation(release) is False
