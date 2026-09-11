"""Reproducible vNext release-gate benchmark.

The generated project lives under ``output`` by default and contains no large
binary fixtures: resource rows deliberately share metadata-only test paths so
the benchmark measures catalog scale without consuming the user's system disk.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

from core.vnext.program_repository import ProgramDocumentRepository
from core.vnext.program_serialization import canonical_json_bytes
from core.vnext.program_types import ProgramDocument, ProgramFunction, ReturnStatement
from core.vnext.program_validation import validate_program_document
from core.vnext.workspace import VNextWorkspaceManager


DEFAULT_FUNCTION_COUNT = 1_000
DEFAULT_HEAVY_STATEMENT_COUNT = 10_000
DEFAULT_RESOURCE_COUNT = 10_000


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def sample(operation: Callable[[], Any], *, count: int = 7, warmups: int = 2) -> tuple[dict[str, Any], Any]:
    result: Any = None
    for _ in range(warmups):
        result = operation()
    timings: list[float] = []
    for _ in range(count):
        started = time.perf_counter()
        result = operation()
        timings.append((time.perf_counter() - started) * 1_000)
    return ({
        "samples": count,
        "p50_ms": round(statistics.median(timings), 3),
        "p95_ms": round(percentile(timings, 0.95), 3),
        "worst_ms": round(max(timings), 3),
        "values_ms": [round(value, 3) for value in timings],
    }, result)


def document(function_id: str, display_name: str, statement_count: int, *, needle: bool = False) -> ProgramDocument:
    statements = tuple(
        ReturnStatement(
            statement_id=f"statement_{function_id}_{index:05d}",
            step_label=("G8-唯一搜索针" if needle and index == statement_count - 1 else f"步骤 {index + 1}"),
        )
        for index in range(statement_count)
    )
    return ProgramDocument(
        document_id=f"document_{function_id}",
        function=ProgramFunction(
            function_id=function_id,
            display_name=display_name,
            return_type="null",
            statements=statements,
        ),
    )


def build_dataset(root: Path, function_count: int, heavy_statement_count: int, resource_count: int) -> str:
    if root.exists():
        shutil.rmtree(root)
    manager = VNextWorkspaceManager()
    initialized = manager.open(str(root), initialize=True, project_name="G8 性能基准")
    if initialized.get("workspace") is None:
        raise RuntimeError(f"cannot initialize benchmark project: {initialized.get('inspection')}")

    repository = ProgramDocumentRepository(root)
    # Keep the initialized entry function: project.json owns its stable ID and
    # the benchmark must exercise the same referential-integrity gate as users.
    for index in range(max(0, function_count - 1)):
        item = document(
            f"function_catalog_{index:04d}",
            f"目录函数 {index:04d}",
            1,
            needle=index == function_count - 2,
        )
        repository.create(item)
    repository.create(document("function_heavy", "一万语句函数", heavy_statement_count))

    assets: dict[str, dict[str, Any]] = {}
    timestamp = "2026-09-03T00:00:00+00:00"
    shared_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    shared_relative_path = "assets/image/benchmark/shared.png"
    shared_path = root / shared_relative_path
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    shared_path.write_bytes(shared_png)
    shared_digest = hashlib.sha256(shared_png).hexdigest()
    for index in range(resource_count):
        asset_id = f"asset_benchmark_{index:05d}"
        assets[asset_id] = {
            "asset_id": asset_id,
            "display_name": f"性能资源 {index:05d}",
            "category": ("image", "ocr", "page")[index % 3],
            "folder": f"批次/{index // 1000:02d}",
            "path": shared_relative_path,
            "extension": ".png",
            "mime_type": "image/png",
            "size_bytes": 68,
            "width": 1,
            "height": 1,
            "sha256": shared_digest,
            "source": "benchmark",
            "created_at": timestamp,
            "updated_at": timestamp,
            "aliases": [],
            "capture": None,
        }
    (root / "assets" / "registry.json").write_text(
        json.dumps({"schema_version": 1, "folders": {}, "assets": assets}, ensure_ascii=False),
        encoding="utf-8",
    )

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.json"), key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def machine_payload() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.cwd().anchor))
    return {
        "host": platform.node(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or platform.machine(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "memory_total_bytes": memory.total,
        "workspace_storage": str(Path.cwd().anchor),
        "workspace_storage_free_bytes": disk.free,
    }


def run(root: Path, output: Path, *, function_count: int, heavy_statement_count: int, resource_count: int, rebuild: bool) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    dataset_hash = build_dataset(root, function_count, heavy_statement_count, resource_count) if rebuild or not root.exists() else "reused"
    ProgramDocumentRepository.clear_snapshot_cache()
    process = psutil.Process()
    rss_before = process.memory_info().rss

    cold_started = time.perf_counter()
    manager = VNextWorkspaceManager()
    opened = manager.open(str(root))
    cold_open_ms = (time.perf_counter() - cold_started) * 1_000
    workspace = opened["workspace"]
    workspace_id = workspace["workspace_id"]
    generation = workspace["generation"]

    list_metric, programs = sample(lambda: manager.list_programs(workspace_id, generation), count=7, warmups=1)
    asset_metric, assets = sample(lambda: manager.list_assets(workspace_id, generation), count=7, warmups=1)
    search_metric, search_result = sample(
        lambda: manager.search_workspace(workspace_id, generation, "G8-唯一搜索针", limit=20),
        count=7,
        warmups=1,
    )

    heavy_snapshot = ProgramDocumentRepository(root).load("function_heavy")
    validation_metric, diagnostics = sample(
        lambda: validate_program_document(heavy_snapshot.document),
        count=7,
        warmups=1,
    )
    heavy_load_metric, heavy_loaded = sample(
        lambda: manager.load_program(workspace_id, generation, "function_heavy"),
        count=5,
        warmups=1,
    )
    compile_metric, compiled = sample(
        lambda: manager.compile_program(workspace_id, generation, "function_heavy"),
        count=3,
        warmups=1,
    )

    rss_after = process.memory_info().rss
    payload = {
        "schema_version": 1,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "machine": machine_payload(),
        "dataset": {
            "path": str(root),
            "sha256": dataset_hash,
            "project_function_count": function_count + 1,
            "catalog_statement_count": max(0, function_count - 1),
            "heavy_function_statement_count": heavy_statement_count,
            "resource_count": resource_count,
        },
        "metrics": {
            "workspace_cold_open": {"samples": 1, "p50_ms": round(cold_open_ms, 3), "p95_ms": round(cold_open_ms, 3), "worst_ms": round(cold_open_ms, 3)},
            "program_catalog": list_metric,
            "resource_catalog": asset_metric,
            "workspace_full_text_search": search_metric,
            "heavy_document_local_validation": validation_metric,
            "heavy_document_linked_load": heavy_load_metric,
            "heavy_document_compile": compile_metric,
        },
        "observations": {
            "programs_returned": len(programs),
            "assets_returned": len(assets["assets"]),
            "search_hits": len(search_result["results"]),
            "diagnostics": len(diagnostics),
            "linked_load_statement_count": len(heavy_loaded["document"]["function"]["statements"]),
            "compile_valid": bool(compiled.get("valid")),
            "rss_before_bytes": rss_before,
            "rss_after_bytes": rss_after,
            "rss_delta_bytes": rss_after - rss_before,
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# G8 vNext 性能基准",
        "",
        f"- 开始：{payload['started_at']}",
        f"- 结束：{payload['ended_at']}",
        f"- 数据集 SHA-256：`{dataset_hash}`",
        f"- 项目函数：{function_count + 1}；重型函数语句：{heavy_statement_count}；资源：{resource_count}",
        "",
        "| 场景 | 样本 | P50 ms | P95 ms | 最差 ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, metric in payload["metrics"].items():
        lines.append(f"| {name} | {metric['samples']} | {metric['p50_ms']} | {metric['p95_ms']} | {metric['worst_ms']} |")
    lines.extend(["", f"进程 RSS 变化：{payload['observations']['rss_delta_bytes']} bytes。", ""])
    (output / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path("output/g8-performance/large-project"))
    parser.add_argument("--output", type=Path, default=Path("output/g8-performance"))
    parser.add_argument("--function-count", type=int, default=DEFAULT_FUNCTION_COUNT)
    parser.add_argument("--statement-count", type=int, default=DEFAULT_HEAVY_STATEMENT_COUNT)
    parser.add_argument("--resource-count", type=int, default=DEFAULT_RESOURCE_COUNT)
    parser.add_argument("--reuse", action="store_true")
    args = parser.parse_args()
    result = run(
        args.project.resolve(), args.output.resolve(),
        function_count=max(1, args.function_count),
        heavy_statement_count=max(1, args.statement_count),
        resource_count=max(1, args.resource_count),
        rebuild=not args.reuse,
    )
    print(json.dumps({"metrics": result["metrics"], "observations": result["observations"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
