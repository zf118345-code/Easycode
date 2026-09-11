"""Measure the frozen Windows Player at 1/2/4/8-instance scale.

The benchmark launches the exact packaged executable in ``--mode dev``.  That
mode disables only the native desktop shell; bundle verification, FastAPI,
runtime construction, frozen imports and the signed project remain identical
to the released Player.  Each process receives an isolated writable data root
and a unique loopback port so this benchmark also detects accidental state or
port sharing.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


INSTANCE_COUNTS = (1, 2, 4, 8)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _bootstrap(port: int, timeout: float = 30.0) -> tuple[float, dict[str, Any]]:
    url = f"http://127.0.0.1:{port}/api/vnext/player/runtime/bootstrap"
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return (time.perf_counter() - started) * 1000, payload
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"Player {port} 未在 {timeout:g}s 内就绪: {last_error}")


def _tree(process: psutil.Process) -> list[psutil.Process]:
    try:
        return [process, *process.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return [process]


def _sample_tree(processes: list[psutil.Process], seconds: float) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    tracked: dict[int, psutil.Process] = {}
    for root in processes:
        for item in _tree(root):
            tracked[item.pid] = item
    for item in tracked.values():
        try:
            item.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
        rss = 0
        cpu = 0.0
        alive = 0
        for item in list(tracked.values()):
            try:
                if item.is_running():
                    rss += item.memory_info().rss
                    cpu += item.cpu_percent(None)
                    alive += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        samples.append({"rss_bytes": rss, "cpu_percent": round(cpu, 3), "processes": alive})
    return {
        "samples": samples,
        "rss_peak_bytes": max(item["rss_bytes"] for item in samples),
        "rss_last_bytes": samples[-1]["rss_bytes"],
        "cpu_peak_percent": max(item["cpu_percent"] for item in samples),
        "cpu_average_percent": round(sum(item["cpu_percent"] for item in samples) / len(samples), 3),
        "process_count_peak": max(item["processes"] for item in samples),
    }


def _stop(processes: list[subprocess.Popen[bytes]]) -> None:
    roots: list[psutil.Process] = []
    for child in processes:
        try:
            roots.append(psutil.Process(child.pid))
        except psutil.NoSuchProcess:
            pass
    for root in roots:
        for item in reversed(_tree(root)):
            try:
                item.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    _, alive = psutil.wait_procs(
        [item for root in roots for item in _tree(root)], timeout=5.0,
    )
    for item in alive:
        try:
            item.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def run(bundle_root: Path, output: Path, sample_seconds: float) -> dict[str, Any]:
    executable = bundle_root / "EasycodePlayer.exe"
    bundle = bundle_root / "release" / "project.ecplayer"
    trust_root = bundle_root / "release" / "trust-root.json"
    for required in (executable, bundle, trust_root):
        if not required.is_file():
            raise FileNotFoundError(required)
    output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    stages: list[dict[str, Any]] = []
    for count in INSTANCE_COUNTS:
        processes: list[subprocess.Popen[bytes]] = []
        ports: list[int] = []
        stage_root = output / f"instances-{count}"
        stage_root.mkdir(parents=True, exist_ok=True)
        try:
            for index in range(count):
                port = _free_port()
                ports.append(port)
                data_root = stage_root / f"data-{index + 1}"
                data_root.mkdir(parents=True, exist_ok=True)
                environment = dict(os.environ)
                environment["LOCALAPPDATA"] = os.fspath(data_root.resolve())
                command = [
                    os.fspath(executable), "--mode", "dev", "--port", str(port),
                    "--player-bundle", os.fspath(bundle),
                    "--player-trust-root", os.fspath(trust_root),
                ]
                processes.append(subprocess.Popen(
                    command,
                    cwd=os.fspath(bundle_root),
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ))
            readiness: list[float] = []
            products: list[str] = []
            for port in ports:
                elapsed, bootstrap = _bootstrap(port)
                readiness.append(round(elapsed, 3))
                products.append(str(bootstrap.get("product", {}).get("product_id") or bootstrap.get("product_id") or ""))
            roots = [psutil.Process(item.pid) for item in processes]
            measurement = _sample_tree(roots, sample_seconds)
            stages.append({
                "instance_count": count,
                "ports": ports,
                "ready_ms": readiness,
                "ready_worst_ms": max(readiness),
                "product_ids": products,
                **measurement,
            })
        finally:
            _stop(processes)

    payload = {
        "schema_version": 1,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "machine": {
            "host": platform.node(),
            "os": platform.platform(),
            "python": platform.python_version(),
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "memory_total_bytes": psutil.virtual_memory().total,
        },
        "build": {
            "executable": os.fspath(executable.resolve()),
            "executable_size_bytes": executable.stat().st_size,
            "bundle": os.fspath(bundle.resolve()),
            "bundle_size_bytes": bundle.stat().st_size,
            "mode": "frozen-runtime-without-desktop-shell",
        },
        "sample_seconds_per_stage": sample_seconds,
        "stages": stages,
    }
    (output / "player-multi-instance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    lines = [
        "# G8 冻结版 Player 多实例基准", "",
        f"- 起止：{payload['started_at']} → {payload['ended_at']}",
        f"- 构建：`{payload['build']['executable']}`",
        f"- 每档空闲采样：{sample_seconds:g} 秒", "",
        "| 实例 | 最慢就绪 ms | RSS 峰值 MiB | 空闲 CPU 平均 % | CPU 峰值 % | 进程峰值 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for stage in stages:
        lines.append(
            f"| {stage['instance_count']} | {stage['ready_worst_ms']:.3f} | "
            f"{stage['rss_peak_bytes'] / 1024 / 1024:.2f} | {stage['cpu_average_percent']:.3f} | "
            f"{stage['cpu_peak_percent']:.3f} | {stage['process_count_peak']} |"
        )
    lines.append("")
    (output / "player-multi-instance.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle-root", type=Path,
        default=Path("output/g7-windows-player-current/Player_Bundle"),
    )
    parser.add_argument("--output", type=Path, default=Path("output/g8-performance"))
    parser.add_argument("--sample-seconds", type=float, default=10.0)
    args = parser.parse_args()
    result = run(args.bundle_root.resolve(), args.output.resolve(), max(2.0, args.sample_seconds))
    print(json.dumps(result["stages"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
