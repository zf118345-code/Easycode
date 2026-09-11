import hashlib
import json
from pathlib import Path

import pytest

from scripts.freeze_release_candidate_family import freeze_candidate_family


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    windows = tmp_path / "windows.json"
    _write_json(
        windows,
        {
            "format": "easycode-release-candidate-v1",
            "release_id": "release_windows",
            "product_id": "project_test",
            "player_bundle": {"core_runtime_sha256": "1" * 64},
        },
    )
    apk = tmp_path / "player.apk"
    apk.write_bytes(b"apk")
    android_evidence = tmp_path / "player.apk.evidence.json"
    _write_json(
        android_evidence,
        {
            "apk_sha256": hashlib.sha256(b"apk").hexdigest(),
            "apk_size": 3,
            "signature_verified": True,
            "source_free_scan": True,
            "bundle_release_id": "release_android",
            "application_id": "com.easycode.player.debug",
        },
    )
    run_evidence = tmp_path / "run.json"
    _write_json(run_evidence, {"status": "completed"})
    return windows, apk, android_evidence, run_evidence


def test_freezes_deterministic_cross_platform_family(tmp_path: Path) -> None:
    windows, apk, android_evidence, run_evidence = _fixture(tmp_path)
    first = freeze_candidate_family(
        windows,
        {"receiver": (apk, android_evidence)},
        {"android_lan": run_evidence},
    )
    second = freeze_candidate_family(
        windows,
        {"receiver": (apk, android_evidence)},
        {"android_lan": run_evidence},
    )

    assert first == second
    assert first["format"] == "easycode-release-candidate-family-v1"
    assert first["android"]["receiver"]["bundle_release_id"] == "release_android"
    assert len(first["family_sha256"]) == 64


def test_rejects_apk_changed_after_evidence(tmp_path: Path) -> None:
    windows, apk, android_evidence, run_evidence = _fixture(tmp_path)
    apk.write_bytes(b"changed")

    with pytest.raises(ValueError, match="哈希不一致"):
        freeze_candidate_family(
            windows,
            {"receiver": (apk, android_evidence)},
            {"android_lan": run_evidence},
        )


def test_rejects_unsigned_or_source_leaking_android_candidate(tmp_path: Path) -> None:
    windows, apk, android_evidence, run_evidence = _fixture(tmp_path)
    report = json.loads(android_evidence.read_text(encoding="utf-8"))
    report["source_free_scan"] = False
    _write_json(android_evidence, report)

    with pytest.raises(ValueError, match="源码隔离"):
        freeze_candidate_family(
            windows,
            {"receiver": (apk, android_evidence)},
            {"android_lan": run_evidence},
        )
