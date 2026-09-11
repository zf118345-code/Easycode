"""Freeze and verify one Windows Player release candidate by exact hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hash(root: Path, files: Iterable[Path]) -> tuple[str, int]:
    rows = []
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        rows.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest(), len(rows)


def freeze_candidate(player_bundle: Path, installer_media: Path | None = None) -> dict:
    root = player_bundle.resolve()
    required = {
        "player": root / "EasycodePlayer.exe",
        "update_helper": root / "EasycodeUpdateHelper.exe",
        "project_bundle": root / "release" / "project.ecplayer",
        "trust_root": root / "release" / "trust-root.json",
        "build_manifest": root / "build_manifest.json",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(f"Player 候选缺少文件：{', '.join(missing)}")

    build_manifest = json.loads(required["build_manifest"].read_text(encoding="utf-8"))
    all_files = [path for path in root.rglob("*") if path.is_file()]
    runtime_files = [
        path
        for path in all_files
        if path != required["build_manifest"] and "release" not in path.relative_to(root).parts
    ]
    tree_sha256, tree_file_count = _tree_hash(root, all_files)
    runtime_sha256, runtime_file_count = _tree_hash(root, runtime_files)
    result = {
        "format": "easycode-release-candidate-v1",
        "schema_version": 1,
        "product_id": build_manifest.get("project_id"),
        "release_id": build_manifest.get("release_id"),
        "signing_key_id": build_manifest.get("signing_key_id"),
        "player_bundle": {
            "tree_sha256": tree_sha256,
            "file_count": tree_file_count,
            "core_runtime_sha256": runtime_sha256,
            "core_runtime_file_count": runtime_file_count,
            "player_sha256": _sha256(required["player"]),
            "update_helper_sha256": _sha256(required["update_helper"]),
            "project_bundle_sha256": _sha256(required["project_bundle"]),
            "trust_root_sha256": _sha256(required["trust_root"]),
        },
    }

    if installer_media is not None:
        media = installer_media.resolve()
        manifest_path = media / "easycode-installer-media.json"
        if not manifest_path.is_file():
            raise ValueError("安装介质缺少 easycode-installer-media.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive = media / str(manifest.get("archive") or "")
        installer = media / str(manifest.get("installer") or "")
        if not archive.is_file() or not installer.is_file():
            raise ValueError("安装介质清单引用的文件不存在")
        checks = {
            "archive_sha256": _sha256(archive),
            "archive_length": archive.stat().st_size,
            "installer_sha256": _sha256(installer),
            "installer_length": installer.stat().st_size,
        }
        for field, actual in checks.items():
            if manifest.get(field) != actual:
                raise ValueError(f"安装介质校验失败：{field}")
        if manifest.get("release_id") != result["release_id"]:
            raise ValueError("安装介质与 Player 候选 release_id 不一致")
        result["installer_media"] = {
            "manifest_sha256": _sha256(manifest_path),
            **checks,
            "verified": True,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="冻结并校验 EasyCode Windows Player 候选")
    parser.add_argument("--player-bundle", required=True)
    parser.add_argument("--installer-media")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = freeze_candidate(
        Path(args.player_bundle),
        Path(args.installer_media) if args.installer_media else None,
    )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
