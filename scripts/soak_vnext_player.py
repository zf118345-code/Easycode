"""Run a resumable-evidence 24-hour frozen Player soak.

Progress is atomically replaced after every sample.  A machine interruption
therefore leaves a valid partial report instead of an unreadable JSON file.
The released executable runs without its desktop shell, but otherwise uses the
same signed bundle, frozen imports, API and isolated execution workers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

try:
    from benchmark_vnext_player import _bootstrap, _free_port, _stop, _tree
except ModuleNotFoundError:  # Imported as ``scripts.soak_vnext_player`` in tests/tools.
    from scripts.benchmark_vnext_player import _bootstrap, _free_port, _stop, _tree


TERMINAL_STATES = {"completed", "failed", "cancelled", "stopped"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request(url: str, *, method: str = "GET", body: dict[str, Any] | None = None,
             headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _process_sample(root: psutil.Process) -> dict[str, Any]:
    rss = handles = threads = 0
    cpu = 0.0
    count = 0
    for item in _tree(root):
        try:
            if not item.is_running():
                continue
            count += 1
            rss += item.memory_info().rss
            cpu += item.cpu_percent(None)
            threads += item.num_threads()
            handles += item.num_handles()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": 0.0,
        "rss_bytes": rss,
        "cpu_percent": round(cpu, 3),
        "handle_count": handles,
        "thread_count": threads,
        "process_count": count,
    }


def _wait_for_worker_cleanup(
    root: psutil.Process, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05,
) -> float:
    """Wait until a terminal run has released its isolated worker process.

    The runtime publishes the business terminal state before the monitor thread
    finishes joining and closing the worker.  Sampling at that boundary makes a
    healthy short-lived worker look like a leaked process.  The soak harness is
    stricter: every exercise must return to the single long-lived Player process
    within a bounded grace period, otherwise the run fails immediately.
    """

    started = time.monotonic()
    deadline = started + max(0.1, float(timeout_seconds))
    while True:
        live_children = []
        try:
            live_children = [item for item in root.children(recursive=True) if item.is_running()]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            raise RuntimeError("冻结版 Player 在等待 Worker 清理时退出")
        if not live_children:
            return time.monotonic() - started
        if time.monotonic() >= deadline:
            pids = ", ".join(str(item.pid) for item in live_children)
            raise RuntimeError(f"运行终态后 Worker 未在时限内退出：{pids}")
        time.sleep(max(0.01, float(poll_seconds)))


def _directory_size(root: Path) -> int:
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except (FileNotFoundError, PermissionError, OSError):
                        continue
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
    return total


def _ensure_fixture_window_ready(title: str) -> dict[str, Any] | None:
    """Keep an explicitly named test fixture capturable during unattended soak.

    This is test-harness behavior only.  Product runtime deliberately reports a
    minimized target instead of changing a user's window state behind their back.
    """

    expected = str(title or "").strip()
    if not expected:
        return None
    import win32con
    import win32gui

    matches: list[int] = []

    def visit(hwnd: int, _context: object) -> None:
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == expected:
            matches.append(int(hwnd))

    win32gui.EnumWindows(visit, None)
    if len(matches) != 1:
        raise RuntimeError(f"长稳测试窗口“{expected}”应唯一存在，实际为 {len(matches)} 个")
    hwnd = matches[0]
    restored = bool(win32gui.IsIconic(hwnd))
    if restored:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    if win32gui.IsIconic(hwnd):
        raise RuntimeError(f"长稳测试窗口“{expected}”无法从最小化状态恢复")
    return {"title": expected, "window_handle": hwnd, "restored": restored}


def _exercise(base_url: str, sequence: int) -> dict[str, Any]:
    key = f"g8-soak-{sequence}-{uuid.uuid4().hex}"
    started = _request(
        f"{base_url}/api/vnext/player/runtime/run",
        method="POST", body={}, headers={"Idempotency-Key": key},
    )
    execution_id = str(started["execution_id"])
    deadline = time.monotonic() + 60.0
    latest = started
    while time.monotonic() < deadline:
        latest = _request(f"{base_url}/api/vnext/runs/{execution_id}")
        if str(latest.get("status")) in TERMINAL_STATES:
            break
        time.sleep(0.1)
    status = str(latest.get("status") or "")
    if status != "completed":
        raise RuntimeError(
            f"长稳任务 {execution_id} 未正常完成: {status or 'unknown'} "
            f"{latest.get('error_id') or latest.get('error') or ''}"
        )
    return {"at": datetime.now(timezone.utc).isoformat(), "execution_id": execution_id, "status": status}


def run(bundle_root: Path, output: Path, *, hours: float, sample_seconds: float,
        exercise_seconds: float, fixture_window_title: str = "") -> dict[str, Any]:
    executable = bundle_root / "EasycodePlayer.exe"
    bundle = bundle_root / "release" / "project.ecplayer"
    trust_root = bundle_root / "release" / "trust-root.json"
    for required in (executable, bundle, trust_root):
        if not required.is_file():
            raise FileNotFoundError(required)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "player-soak-24h.json"
    data_root = output / "player-soak-data"
    data_root.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    environment = dict(os.environ)
    environment["LOCALAPPDATA"] = os.fspath(data_root.resolve())
    process = subprocess.Popen(
        [
            os.fspath(executable), "--mode", "dev", "--port", str(port),
            "--player-bundle", os.fspath(bundle),
            "--player-trust-root", os.fspath(trust_root),
        ],
        cwd=os.fspath(bundle_root), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    root = psutil.Process(process.pid)
    started_wall = datetime.now(timezone.utc)
    started = time.monotonic()
    requested_seconds = max(1.0, hours * 3600.0)
    base_url = f"http://127.0.0.1:{port}"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "started_at": started_wall.isoformat(),
        "ended_at": None,
        "requested_hours": hours,
        "sample_seconds": sample_seconds,
        "exercise_seconds": exercise_seconds,
        "build": os.fspath(executable.resolve()),
        "build_sha256": _sha256(executable),
        "bundle": os.fspath(bundle.resolve()),
        "bundle_sha256": _sha256(bundle),
        "port": port,
        "pid": process.pid,
        "samples": [],
        "exercises": [],
        "failures": [],
        "summary": {},
    }
    try:
        ready_ms, bootstrap = _bootstrap(port)
        payload["ready_ms"] = round(ready_ms, 3)
        payload["release_id"] = str(bootstrap.get("bundle", {}).get("release_id") or "")
        for item in _tree(root):
            try:
                item.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        next_exercise = started
        while True:
            now = time.monotonic()
            elapsed = now - started
            if elapsed >= requested_seconds:
                break
            if process.poll() is not None:
                raise RuntimeError(f"冻结版 Player 提前退出，退出码 {process.returncode}")
            try:
                _request(f"{base_url}/api/vnext/player/runtime/bootstrap")
                if now >= next_exercise:
                    fixture = _ensure_fixture_window_ready(fixture_window_title)
                    exercise = _exercise(base_url, len(payload["exercises"]) + 1)
                    exercise["worker_cleanup_ms"] = round(
                        _wait_for_worker_cleanup(root) * 1000.0, 3,
                    )
                    if fixture is not None:
                        exercise["fixture"] = fixture
                    payload["exercises"].append(exercise)
                    next_exercise = now + exercise_seconds
            except Exception as exc:
                payload["failures"].append({
                    "at": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": round(elapsed, 3),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                raise
            measurement = _process_sample(root)
            measurement["elapsed_seconds"] = round(elapsed, 3)
            measurement["data_root_bytes"] = _directory_size(data_root)
            payload["samples"].append(measurement)
            samples = payload["samples"]
            payload["summary"] = {
                "sample_count": len(samples),
                "exercise_count": len(payload["exercises"]),
                "elapsed_seconds": round(elapsed, 3),
                "rss_first_bytes": samples[0]["rss_bytes"],
                "rss_last_bytes": samples[-1]["rss_bytes"],
                "rss_peak_bytes": max(item["rss_bytes"] for item in samples),
                "rss_growth_bytes": samples[-1]["rss_bytes"] - samples[0]["rss_bytes"],
                "handle_first": samples[0]["handle_count"],
                "handle_last": samples[-1]["handle_count"],
                "handle_growth": samples[-1]["handle_count"] - samples[0]["handle_count"],
                "thread_first": samples[0]["thread_count"],
                "thread_last": samples[-1]["thread_count"],
                "thread_growth": samples[-1]["thread_count"] - samples[0]["thread_count"],
                "data_root_first_bytes": samples[0]["data_root_bytes"],
                "data_root_last_bytes": samples[-1]["data_root_bytes"],
                "data_root_growth_bytes": (
                    samples[-1]["data_root_bytes"] - samples[0]["data_root_bytes"]
                ),
                "cpu_average_percent": round(
                    sum(item["cpu_percent"] for item in samples) / len(samples), 3,
                ),
            }
            _atomic_json(report_path, payload)
            print(
                f"[{measurement['elapsed_seconds']:>10.1f}s] samples={len(samples)} "
                f"runs={len(payload['exercises'])} rss={measurement['rss_bytes']} "
                f"handles={measurement['handle_count']} disk={measurement['data_root_bytes']}",
                flush=True,
            )
            time.sleep(min(sample_seconds, max(0.0, requested_seconds - (time.monotonic() - started))))
        payload["status"] = "completed"
    except BaseException as exc:
        payload["status"] = "failed"
        payload["fatal_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        payload["ended_at"] = datetime.now(timezone.utc).isoformat()
        payload.setdefault("summary", {})["elapsed_seconds"] = round(time.monotonic() - started, 3)
        _atomic_json(report_path, payload)
        _stop([process])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle-root", type=Path,
        default=Path("output/g7-windows-player-current/Player_Bundle"),
    )
    parser.add_argument("--output", type=Path, default=Path("output/g8-performance"))
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--sample-seconds", type=float, default=30.0)
    parser.add_argument("--exercise-seconds", type=float, default=300.0)
    parser.add_argument(
        "--fixture-window-title", default="",
        help="精确命名的测试夹具窗口；若被最小化则在每次任务前恢复",
    )
    args = parser.parse_args()
    result = run(
        args.bundle_root.resolve(), args.output.resolve(),
        hours=max(1 / 3600, args.hours),
        sample_seconds=max(1.0, args.sample_seconds),
        exercise_seconds=max(5.0, args.exercise_seconds),
        fixture_window_title=args.fixture_window_title,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
