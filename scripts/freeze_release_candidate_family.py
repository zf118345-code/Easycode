"""Create an exact, machine-verifiable lock for a cross-platform candidate family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"文件不存在：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON 无法读取：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def freeze_candidate_family(
    windows_manifest: Path,
    android_variants: dict[str, tuple[Path, Path]],
    evidence: dict[str, Path],
) -> dict:
    """Verify artifacts against their own evidence and return a deterministic lock."""

    windows_path = windows_manifest.resolve()
    windows = _load_json(windows_path)
    if windows.get("format") != "easycode-release-candidate-v1":
        raise ValueError("Windows 候选清单格式不受支持")
    if not windows.get("release_id") or not (windows.get("player_bundle") or {}).get(
        "core_runtime_sha256"
    ):
        raise ValueError("Windows 候选清单缺少 release_id 或核心 Runtime 哈希")

    android_rows: dict[str, dict] = {}
    for role, (apk_path, evidence_path) in sorted(android_variants.items()):
        if not role.strip():
            raise ValueError("Android 角色不能为空")
        apk = apk_path.resolve()
        report_path = evidence_path.resolve()
        if not apk.is_file():
            raise ValueError(f"Android APK 不存在：{apk}")
        report = _load_json(report_path)
        actual_hash = _sha256(apk)
        if report.get("apk_sha256") != actual_hash:
            raise ValueError(f"Android {role} APK 与证据哈希不一致")
        if report.get("apk_size") != apk.stat().st_size:
            raise ValueError(f"Android {role} APK 与证据大小不一致")
        if report.get("signature_verified") is not True:
            raise ValueError(f"Android {role} APK 未通过签名校验")
        if report.get("source_free_scan") is not True:
            raise ValueError(f"Android {role} APK 未通过源码隔离扫描")
        android_rows[role] = {
            "apk_sha256": actual_hash,
            "apk_size": apk.stat().st_size,
            "evidence_sha256": _sha256(report_path),
            "application_id": report.get("application_id"),
            "bundle_release_id": report.get("bundle_release_id"),
            "bundle_integrity_sha256": report.get("bundle_integrity_sha256"),
            "variant": report.get("variant"),
            "delivery_class": report.get("delivery_class"),
            "min_sdk": report.get("min_sdk"),
            "minimum_webview_major": report.get("minimum_webview_major"),
            "signature_verified": True,
            "source_free_scan": True,
        }

    evidence_rows = {
        name: {"sha256": _sha256(path.resolve()), "size": path.resolve().stat().st_size}
        for name, path in sorted(evidence.items())
        if path.resolve().is_file()
    }
    if len(evidence_rows) != len(evidence):
        missing = sorted(name for name, path in evidence.items() if not path.resolve().is_file())
        raise ValueError(f"验收证据不存在：{', '.join(missing)}")

    locked = {
        "format": "easycode-release-candidate-family-v1",
        "schema_version": 1,
        "windows": {
            "manifest_sha256": _sha256(windows_path),
            "release_id": windows["release_id"],
            "product_id": windows.get("product_id"),
            "signing_key_id": windows.get("signing_key_id"),
            "player_bundle": windows["player_bundle"],
            "installer_media": windows.get("installer_media"),
        },
        "android": android_rows,
        "acceptance_evidence": evidence_rows,
    }
    canonical = json.dumps(locked, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    locked["family_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return locked


def _parse_pair(value: str, *, separator: str, label: str) -> tuple[str, str]:
    if separator not in value:
        raise argparse.ArgumentTypeError(f"{label} 格式应为 name{separator}path")
    name, path = value.split(separator, 1)
    if not name.strip() or not path.strip():
        raise argparse.ArgumentTypeError(f"{label} 名称和路径不能为空")
    return name.strip(), path.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="冻结 EasyCode 跨平台候选家族")
    parser.add_argument("--windows-manifest", required=True)
    parser.add_argument(
        "--android",
        action="append",
        default=[],
        metavar="ROLE=APK,EVIDENCE",
        help="可重复；APK 证据必须包含匹配的哈希、大小和签名结果",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="可重复；锁定真实验收报告或截图",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    android: dict[str, tuple[Path, Path]] = {}
    for raw in args.android:
        role, paths = _parse_pair(raw, separator="=", label="Android 候选")
        if "," not in paths:
            parser.error("Android 候选格式应为 ROLE=APK,EVIDENCE")
        apk, report = paths.split(",", 1)
        if role in android:
            parser.error(f"Android 角色重复：{role}")
        android[role] = (Path(apk), Path(report))

    evidence: dict[str, Path] = {}
    for raw in args.evidence:
        name, path = _parse_pair(raw, separator="=", label="验收证据")
        if name in evidence:
            parser.error(f"验收证据名称重复：{name}")
        evidence[name] = Path(path)

    result = freeze_candidate_family(Path(args.windows_manifest), android, evidence)
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
