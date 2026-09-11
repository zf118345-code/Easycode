import json
from pathlib import Path

import pytest

from scripts.freeze_vnext_candidate import freeze_candidate


def _candidate(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "Player_Bundle"
    release = root / "release"
    release.mkdir(parents=True)
    (root / "EasycodePlayer.exe").write_bytes(b"player")
    (root / "EasycodeUpdateHelper.exe").write_bytes(b"helper")
    (release / "project.ecplayer").write_bytes(b"project")
    (release / "trust-root.json").write_text("{}", encoding="utf-8")
    (root / "build_manifest.json").write_text(
        json.dumps({
            "project_id": "project_1",
            "release_id": "release_1",
            "signing_key_id": "key_1",
        }),
        encoding="utf-8",
    )
    media = tmp_path / "media"
    media.mkdir()
    archive = media / "application.zip"
    installer = media / "EasycodeInstaller.exe"
    archive.write_bytes(b"archive")
    installer.write_bytes(b"installer")
    import hashlib

    (media / "easycode-installer-media.json").write_text(
        json.dumps({
            "archive": archive.name,
            "archive_length": archive.stat().st_size,
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "installer": installer.name,
            "installer_length": installer.stat().st_size,
            "installer_sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
            "release_id": "release_1",
        }),
        encoding="utf-8",
    )
    return root, media


def test_freeze_candidate_locks_runtime_release_and_verified_installer(tmp_path: Path) -> None:
    root, media = _candidate(tmp_path)

    frozen = freeze_candidate(root, media)

    assert frozen["release_id"] == "release_1"
    assert frozen["player_bundle"]["file_count"] == 5
    assert frozen["player_bundle"]["core_runtime_file_count"] == 2
    assert frozen["installer_media"]["verified"] is True


def test_freeze_candidate_rejects_tampered_installer_media(tmp_path: Path) -> None:
    root, media = _candidate(tmp_path)
    (media / "application.zip").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="archive_sha256"):
        freeze_candidate(root, media)
