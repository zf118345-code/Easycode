from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import installer as installer_entry

from core.vnext.windows_installation_v6 import (
    INSTALL_MARKER,
    MEDIA_MANIFEST,
    WindowsInstallationError,
    WindowsInstallerMediaV6,
    WindowsPerUserInstallerV6,
)


def _distribution(root: Path, *, release_id: str = "release_windows_1", payload: bytes = b"player-v1") -> Path:
    root.mkdir(parents=True)
    (root / "EasycodePlayer.exe").write_bytes(payload)
    (root / "EasycodeUpdateHelper.exe").write_bytes(b"helper")
    release = root / "release"
    release.mkdir()
    (release / "project.ecplayer").write_bytes(b"signed-project-placeholder")
    (release / "trust-root.json").write_text("{}\n", encoding="utf-8")
    (root / "build_manifest.json").write_text(json.dumps({
        "product": "EasyCode Player",
        "project": "自动组队",
        "project_id": "product.install.test",
        "release_id": release_id,
        "bundle": "release/project.ecplayer",
        "trust_root": "release/trust-root.json",
    }, ensure_ascii=False), encoding="utf-8")
    return root


def _installer(root: Path) -> Path:
    executable = root / "EasycodeInstaller.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"frozen-installer")
    return executable


def test_media_install_upgrade_and_uninstall_preserve_user_data(tmp_path: Path) -> None:
    first_media = WindowsInstallerMediaV6.build(
        _distribution(tmp_path / "distribution-v1"), tmp_path / "media-v1",
        installer_executable=_installer(tmp_path / "installer-v1"),
    )
    installer = WindowsPerUserInstallerV6(tmp_path / "local-app-data")
    installed = installer.install(first_media["path"])
    install_root = Path(installed["install_root"])
    assert (install_root / "EasycodePlayer.exe").read_bytes() == b"player-v1"
    assert json.loads((install_root / INSTALL_MARKER).read_text(encoding="utf-8"))["product_id"] == "product.install.test"

    data = tmp_path / "local-app-data" / "EasyCode" / "products" / "product.install.test"
    data.mkdir(parents=True)
    (data / "profiles.json").write_text("keep", encoding="utf-8")
    second_media = WindowsInstallerMediaV6.build(
        _distribution(tmp_path / "distribution-v2", release_id="release_windows_2", payload=b"player-v2"),
        tmp_path / "media-v2",
        installer_executable=_installer(tmp_path / "installer-v2"),
    )
    upgraded = installer.install(second_media["path"])
    assert upgraded["release_id"] == "release_windows_2"
    assert (install_root / "EasycodePlayer.exe").read_bytes() == b"player-v2"

    removed = installer.uninstall(install_root)
    assert removed == {"uninstalled": True, "product_id": "product.install.test", "data_preserved": True}
    assert not install_root.exists()
    assert (data / "profiles.json").read_text(encoding="utf-8") == "keep"


def test_media_tamper_is_rejected_before_install_root_changes(tmp_path: Path) -> None:
    media = WindowsInstallerMediaV6.build(
        _distribution(tmp_path / "distribution"), tmp_path / "media",
        installer_executable=_installer(tmp_path / "installer"),
    )
    archive = Path(media["archive"])
    archive.write_bytes(archive.read_bytes() + b"tampered")
    installer = WindowsPerUserInstallerV6(tmp_path / "local-app-data")

    with pytest.raises(WindowsInstallationError) as error:
        installer.install(media["path"])

    assert error.value.code == "WIN-INSTALL-MEDIA-003"
    assert not installer.products_root.exists()


def test_media_installer_tamper_or_absence_is_rejected(tmp_path: Path) -> None:
    media = WindowsInstallerMediaV6.build(
        _distribution(tmp_path / "distribution"), tmp_path / "media",
        installer_executable=_installer(tmp_path / "installer"),
    )
    frozen_installer = Path(media["installer"])
    frozen_installer.write_bytes(frozen_installer.read_bytes() + b"tampered")
    with pytest.raises(WindowsInstallationError) as error:
        WindowsInstallerMediaV6.inspect(media["path"])
    assert error.value.code == "WIN-INSTALL-MEDIA-003"

    frozen_installer.unlink()
    with pytest.raises(WindowsInstallationError) as error:
        WindowsInstallerMediaV6.inspect(media["path"])
    assert error.value.code == "WIN-INSTALL-MEDIA-002"


def test_media_build_requires_a_real_installer(tmp_path: Path) -> None:
    with pytest.raises(WindowsInstallationError) as error:
        WindowsInstallerMediaV6.build(
            _distribution(tmp_path / "distribution"), tmp_path / "media",
            installer_executable=tmp_path / "missing.exe",
        )
    assert error.value.code == "WIN-INSTALL-MEDIA-001"


def test_uninstall_refuses_unmarked_or_out_of_boundary_directories(tmp_path: Path) -> None:
    installer = WindowsPerUserInstallerV6(tmp_path / "local-app-data")
    outside = tmp_path / "unrelated"
    outside.mkdir()
    with pytest.raises(WindowsInstallationError, match="不属于"):
        installer.uninstall(outside)

    fake = installer.products_root / "fake.product"
    fake.mkdir(parents=True)
    (fake / MEDIA_MANIFEST).write_text("{}", encoding="utf-8")
    with pytest.raises(WindowsInstallationError) as error:
        installer.uninstall(fake)
    assert error.value.code == "WIN-UNINSTALL-MARKER-001"
    assert fake.exists()


def test_installer_diagnostics_are_structured_and_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert installer_entry.main(["--unknown-option"]) == 2
    log = tmp_path / "local" / "EasyCode" / "Installer" / "logs" / "latest.jsonl"
    first = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert first["event"] == "command_line"
    assert first["error_code"] == "WIN-INSTALL-CLI-001"

    for index in range(12):
        installer_entry._installer_log("bounded", "failed", sequence=index, message="x" * 100_000)
    previous = log.with_name("previous.jsonl")
    assert log.stat().st_size <= installer_entry._LOG_LIMIT
    assert previous.is_file()
    assert previous.stat().st_size <= installer_entry._LOG_LIMIT


def test_noncritical_hub_command_timeout_is_bounded_and_reportable(monkeypatch) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["player.exe", "--register-installation"], 0.01)

    monkeypatch.setattr(installer_entry.subprocess, "run", timeout)
    result = installer_entry._hidden_run(
        ["player.exe", "--register-installation"], timeout=0.01,
    )

    assert result.returncode == 124
    assert "超时" in result.stderr
