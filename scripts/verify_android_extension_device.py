"""Verify signed Android extension success/failure/timeout on an installed debug Player."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Device:
    def __init__(self, adb: Path, serial: str, package: str) -> None:
        self.adb = adb
        self.serial = serial
        self.package = package
        self.component = f"{package}/com.easycode.player.PlayerActivity"

    def command(self, *arguments: str, check: bool = True, timeout: float = 60) -> str:
        completed = subprocess.run(
            [str(self.adb), "-s", self.serial, *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if check and completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout).strip())
        return completed.stdout.strip()

    def shell(self, *arguments: str, **kwargs: Any) -> str:
        return self.command("shell", *arguments, **kwargs)

    def state(self) -> dict[str, Any]:
        raw = self.shell("run-as", self.package, "cat", "files/runtime-state/current.json", check=False)
        return json.loads(raw) if raw else {}

    def pid(self, process: str) -> int | None:
        raw = self.shell("pidof", process, check=False).split()
        return int(raw[0]) if raw else None

    def install_content(self, bundle: Path, trust_root: Path) -> dict[str, Any]:
        external = f"/sdcard/Android/data/{self.package}/files/inbox"
        self.shell("mkdir", "-p", external)
        self.command("push", str(bundle), f"{external}/project.ecplayer")
        self.command("push", str(trust_root), f"{external}/trust-root.json")
        return {"bundle": str(bundle), "size": bundle.stat().st_size}

    def run(self, *, timeout: float = 15) -> dict[str, Any]:
        previous = str(self.state().get("run_id") or "")
        self.shell("am", "force-stop", self.package)
        time.sleep(0.35)
        self.shell("am", "start", "-n", self.component)
        time.sleep(1.8)
        size = self.shell("wm", "size")
        match = re.search(r"(\d+)x(\d+)", size)
        if match is None:
            raise RuntimeError(f"无法读取屏幕尺寸：{size}")
        width, height = (int(value) for value in match.groups())
        self.shell("input", "tap", str(round(width * 0.5)), str(round(height * 0.91)))
        deadline = time.monotonic() + timeout
        state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            state = self.state()
            if (
                state.get("run_id")
                and state.get("run_id") != previous
                and state.get("status") in {"completed", "failed", "cancelled"}
            ):
                break
            time.sleep(0.15)
        else:
            raise RuntimeError(f"限时内没有新的运行终态：{state}")
        time.sleep(0.25)
        event_log = self.shell(
            "run-as", self.package, "cat", str(state.get("event_log_path") or ""), check=False,
        )
        return {
            "state": state,
            "main_pid": self.pid(self.package),
            "worker_pid": self.pid(f"{self.package}:extension_worker"),
            "event_log": [line for line in event_log.splitlines() if line.strip()],
        }


def verify(arguments: argparse.Namespace) -> dict[str, Any]:
    device = Device(arguments.adb.resolve(), arguments.serial, arguments.package)
    if device.command("get-state") != "device":
        raise RuntimeError("设备不在 device 状态")
    harness = arguments.harness.resolve()
    root = harness.parent if harness.is_file() else harness
    trust_root = root / "trust-root.json"
    results: dict[str, Any] = {}
    expectations = {
        "success": ("completed", ""),
        "failure": ("failed", "extension.execution_failed"),
        "timeout": ("failed", "extension.timeout"),
        "recovery": ("completed", ""),
    }
    for mode, bundle_name in (
        ("success", "success.ecplayer"),
        ("failure", "failure.ecplayer"),
        ("timeout", "timeout.ecplayer"),
        ("recovery", "success.ecplayer"),
    ):
        transfer = device.install_content(root / bundle_name, trust_root)
        run = device.run()
        expected_status, expected_error = expectations[mode]
        state = run["state"]
        if state.get("status") != expected_status or str(state.get("error_id") or "") != expected_error:
            raise RuntimeError(f"{mode} 结果不符合预期：{state}")
        if run["main_pid"] is None:
            raise RuntimeError(f"{mode} 后 Player 主进程不存在")
        if mode in {"success", "recovery"} and (
            run["worker_pid"] is None or run["worker_pid"] == run["main_pid"]
        ):
            raise RuntimeError(f"{mode} 没有使用独立 Worker 进程")
        if mode == "timeout" and run["worker_pid"] is not None:
            raise RuntimeError("扩展超时后 Worker 进程仍存活")
        results[mode] = {"transfer": transfer, **run}
    payload = {
        "schema_version": 1,
        "status": "passed",
        "verified_at": now(),
        "serial": arguments.serial,
        "package": arguments.package,
        "device": {
            "api": device.shell("getprop", "ro.build.version.sdk"),
            "android": device.shell("getprop", "ro.build.version.release"),
            "manufacturer": device.shell("getprop", "ro.product.manufacturer"),
            "model": device.shell("getprop", "ro.product.model"),
            "abi": device.shell("getprop", "ro.product.cpu.abi"),
        },
        "results": results,
    }
    atomic_json(arguments.output.resolve(), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Android extension worker on a device")
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument(
        "--harness", type=Path, required=True,
        help="Harness 输出目录，或该目录中的 harness.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    result = verify(parser.parse_args())
    print(json.dumps({
        "status": result["status"],
        "device": result["device"],
        "runs": {
            key: {
                "status": value["state"]["status"],
                "error_id": value["state"].get("error_id"),
                "main_pid": value["main_pid"],
                "worker_pid": value["worker_pid"],
            }
            for key, value in result["results"].items()
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
