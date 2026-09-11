"""Evaluate a frozen Player soak report with explicit, reproducible gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


MIB = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slope_per_hour(samples: list[dict[str, Any]], field: str) -> float:
    points = [
        (float(item["elapsed_seconds"]) / 3600.0, float(item[field]))
        for item in samples
    ]
    if len(points) < 2:
        return 0.0
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0:
        return 0.0
    return sum(
        (point[0] - mean_x) * (point[1] - mean_y) for point in points
    ) / denominator


def _quartile_delta(samples: list[dict[str, Any]], field: str) -> float:
    width = max(1, len(samples) // 4)
    return median(float(item[field]) for item in samples[-width:]) - median(
        float(item[field]) for item in samples[:width]
    )


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    samples = list(payload.get("samples") or [])
    failures = list(payload.get("failures") or [])
    summary = dict(payload.get("summary") or {})
    requested_seconds = float(payload.get("requested_hours") or 0.0) * 3600.0
    elapsed_seconds = float(summary.get("elapsed_seconds") or 0.0)
    warmup_seconds = min(600.0, requested_seconds * 0.1)
    steady_samples = [
        item for item in samples if float(item.get("elapsed_seconds") or 0.0) >= warmup_seconds
    ]
    if len(steady_samples) < 8:
        steady_samples = samples

    rss_slope = _slope_per_hour(steady_samples, "rss_bytes")
    handle_slope = _slope_per_hour(steady_samples, "handle_count")
    rss_quartile_delta = _quartile_delta(steady_samples, "rss_bytes") if steady_samples else 0.0
    handle_quartile_delta = (
        _quartile_delta(steady_samples, "handle_count") if steady_samples else 0.0
    )
    has_disk_samples = bool(samples) and all("data_root_bytes" in item for item in samples)
    disk_growth = (
        float(samples[-1]["data_root_bytes"]) - float(samples[0]["data_root_bytes"])
        if has_disk_samples else None
    )
    process_counts = sorted({int(item.get("process_count") or 0) for item in samples})
    requested_exercises = max(
        1,
        math.floor(requested_seconds / max(1.0, float(payload.get("exercise_seconds") or 1.0))),
    )
    duration_complete = (
        payload.get("status") == "completed"
        and elapsed_seconds + max(1.0, float(payload.get("sample_seconds") or 1.0))
        >= requested_seconds
    )

    checks = [
        {
            "id": "duration",
            "passed": duration_complete,
            "actual": round(elapsed_seconds, 3),
            "required": requested_seconds,
        },
        {"id": "failures", "passed": not failures, "actual": len(failures), "required": 0},
        {
            "id": "process_count",
            "passed": bool(process_counts) and process_counts == [1],
            "actual": process_counts,
            "required": [1],
        },
        {
            "id": "exercise_coverage",
            "passed": len(payload.get("exercises") or []) >= requested_exercises,
            "actual": len(payload.get("exercises") or []),
            "required": requested_exercises,
        },
        {
            "id": "rss_trend",
            "passed": rss_slope <= 4 * MIB and rss_quartile_delta <= 32 * MIB,
            "actual": {
                "slope_bytes_per_hour": round(rss_slope, 3),
                "last_minus_first_quartile_bytes": round(rss_quartile_delta, 3),
            },
            "required": {
                "slope_bytes_per_hour_max": 4 * MIB,
                "last_minus_first_quartile_bytes_max": 32 * MIB,
            },
        },
        {
            "id": "handle_trend",
            "passed": handle_slope <= 1.0 and handle_quartile_delta <= 8,
            "actual": {
                "slope_per_hour": round(handle_slope, 3),
                "last_minus_first_quartile": round(handle_quartile_delta, 3),
            },
            "required": {"slope_per_hour_max": 1.0, "last_minus_first_quartile_max": 8},
        },
        {
            "id": "data_root_growth",
            "passed": disk_growth is not None and disk_growth <= 64 * MIB,
            "actual": None if disk_growth is None else round(disk_growth, 3),
            "required": {"growth_bytes_max": 64 * MIB},
        },
    ]
    status = "passed" if all(item["passed"] for item in checks) else (
        "incomplete" if not duration_complete and not failures else "failed"
    )
    return {
        "schema_version": 1,
        "status": status,
        "source_status": payload.get("status"),
        "source_build": payload.get("build"),
        "sample_count": len(samples),
        "steady_sample_count": len(steady_samples),
        "warmup_seconds": warmup_seconds,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        help="Optional final Player_Bundle root whose exact bytes must match the soaked candidate.",
    )
    args = parser.parse_args()
    payload = json.loads(args.report.read_text(encoding="utf-8"))
    result = evaluate(payload)
    source_build = Path(str(payload.get("build") or ""))
    source_bundle = Path(str(payload.get("bundle") or ""))
    result["source_hashes"] = {
        "build_sha256": str(payload.get("build_sha256") or "") or _sha256(source_build),
        "bundle_sha256": str(payload.get("bundle_sha256") or "") or _sha256(source_bundle),
    }
    if args.candidate_root:
        candidate_root = args.candidate_root.resolve()
        candidate_hashes = {
            "build_sha256": _sha256(candidate_root / "EasycodePlayer.exe"),
            "bundle_sha256": _sha256(candidate_root / "release" / "project.ecplayer"),
        }
        matches = candidate_hashes == result["source_hashes"]
        result["candidate_match"] = {
            "root": str(candidate_root),
            "hashes": candidate_hashes,
            "passed": matches,
        }
        result["checks"].append(
            {
                "id": "candidate_hash",
                "passed": matches,
                "actual": candidate_hashes,
                "required": result["source_hashes"],
            }
        )
        if not matches:
            result["status"] = "failed"
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
