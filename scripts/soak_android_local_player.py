"""Soak a real Android-local Player through its installed native runtime.

ADB is used only as the test harness: it brings the already-installed Player
to the foreground, presses the visible Run button, reads debug-candidate
diagnostics, and samples the Android process.  Capture, Accessibility input,
ECIR execution, files, and recording remain inside the APK.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL = {"completed", "failed", "cancelled", "stopped"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _optional_max(values: list[int | float | None]) -> int | float | None:
    available = [value for value in values if value is not None]
    return max(available) if available else None


class Harness:
    def __init__(self, adb: Path, serial: str, package: str) -> None:
        self.adb = adb
        self.serial = serial
        self.package = package
        self.component = f"{package}/com.easycode.player.PlayerActivity"

    def command(self, *arguments: str, timeout: float = 30.0, check: bool = True) -> str:
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
            raise RuntimeError((completed.stderr or completed.stdout).strip() or f"ADB exit {completed.returncode}")
        return completed.stdout

    def shell(self, *arguments: str, timeout: float = 30.0, check: bool = True) -> str:
        return self.command("shell", *arguments, timeout=timeout, check=check)

    def state(self) -> dict[str, Any]:
        raw = self.shell(
            "run-as", self.package, "cat", "files/runtime-state/current.json",
            check=False,
        ).strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"运行状态不是有效 JSON：{raw[-300:]}") from error
        if not isinstance(value, dict):
            raise RuntimeError("运行状态不是 JSON 对象")
        return value

    def exercise(self, tap_x: int, tap_y: int, timeout_seconds: float) -> dict[str, Any]:
        previous = str(self.state().get("run_id") or "")
        self.shell("am", "start", "-n", self.component, timeout=60.0)
        time.sleep(1.0)
        self.shell("input", "tap", str(tap_x), str(tap_y))
        started = time.monotonic()
        latest: dict[str, Any] = {}
        while time.monotonic() - started < timeout_seconds:
            latest = self.state()
            run_id = str(latest.get("run_id") or "")
            if run_id and run_id != previous and str(latest.get("status") or "") in TERMINAL:
                break
            time.sleep(0.25)
        else:
            top = self.shell("dumpsys", "activity", "activities", check=False)
            resumed = next((line.strip() for line in top.splitlines() if "topResumedActivity" in line), "")
            raise RuntimeError(f"限时内没有产生新的终态运行；top={resumed or 'unknown'}")
        if latest.get("status") != "completed":
            raise RuntimeError(
                f"运行 {latest.get('run_id')} 终态为 {latest.get('status')}："
                f"{latest.get('error_id') or latest.get('error_message') or 'unknown'}"
            )
        return {
            "at": _now(),
            "run_id": latest["run_id"],
            "status": latest["status"],
            "sequence": latest.get("sequence"),
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        }

    def sample(self, elapsed_seconds: float) -> dict[str, Any]:
        pid = self.shell("pidof", self.package, check=False).strip().split()
        if not pid:
            raise RuntimeError("Android Player 进程不存在")
        memory = self.shell("dumpsys", "meminfo", self.package, timeout=60.0)
        total = re.search(r"TOTAL PSS:\s*(\d+).*?TOTAL RSS:\s*(\d+).*?TOTAL SWAP PSS:\s*(\d+)", memory)
        if total is None:
            raise RuntimeError("无法解析 Android meminfo TOTAL")
        battery = self.shell("dumpsys", "battery")
        thermal = self.shell("dumpsys", "thermalservice", check=False)
        disk = self.shell("run-as", self.package, "du", "-sk", "files", check=False).strip().split()

        def battery_value(name: str) -> int | None:
            match = re.search(rf"^\s*{re.escape(name)}:\s*(\d+)\s*$", battery, flags=re.MULTILINE)
            return int(match.group(1)) if match else None

        thermal_status = re.search(r"Thermal Status:\s*(\d+)", thermal)
        return {
            "at": _now(),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "pid": int(pid[0]),
            "process_count": len(pid),
            "pss_bytes": int(total.group(1)) * 1024,
            "rss_bytes": int(total.group(2)) * 1024,
            "swap_pss_bytes": int(total.group(3)) * 1024,
            "private_data_bytes": (int(disk[0]) * 1024) if disk and disk[0].isdigit() else None,
            "battery_level": battery_value("level"),
            "battery_temperature_c": (
                battery_value("temperature") / 10.0
                if battery_value("temperature") is not None else None
            ),
            "battery_voltage_mv": battery_value("voltage"),
            "thermal_status": int(thermal_status.group(1)) if thermal_status else None,
        }


def run(arguments: argparse.Namespace) -> int:
    apk = arguments.apk.resolve()
    if not apk.is_file():
        raise FileNotFoundError(apk)
    harness = Harness(arguments.adb.resolve(), arguments.serial, arguments.package)
    device_state = harness.command("get-state").strip()
    if device_state != "device":
        raise RuntimeError(f"设备不可用：{device_state or 'missing'}")
    properties = {
        "sdk": harness.shell("getprop", "ro.build.version.sdk").strip(),
        "release": harness.shell("getprop", "ro.build.version.release").strip(),
        "manufacturer": harness.shell("getprop", "ro.product.manufacturer").strip(),
        "model": harness.shell("getprop", "ro.product.model").strip(),
        "abi": harness.shell("getprop", "ro.product.cpu.abi").strip(),
    }
    started = time.monotonic()
    requested_seconds = max(1.0, arguments.hours * 3600.0)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "started_at": _now(),
        "ended_at": None,
        "requested_hours": arguments.hours,
        "sample_seconds": arguments.sample_seconds,
        "exercise_seconds": arguments.exercise_seconds,
        "serial": arguments.serial,
        "package": arguments.package,
        "apk_path": str(apk),
        "apk_sha256": _sha256(apk),
        "device": properties,
        "samples": [],
        "exercises": [],
        "failures": [],
        "summary": {},
    }
    next_exercise = started
    try:
        while True:
            now = time.monotonic()
            elapsed = now - started
            if elapsed >= requested_seconds:
                payload["status"] = "completed"
                break
            if now >= next_exercise:
                payload["exercises"].append(
                    harness.exercise(arguments.tap_x, arguments.tap_y, arguments.run_timeout_seconds)
                )
                next_exercise = now + arguments.exercise_seconds
            payload["samples"].append(harness.sample(elapsed))
            samples = payload["samples"]
            payload["summary"] = {
                "elapsed_seconds": round(elapsed, 3),
                "sample_count": len(samples),
                "exercise_count": len(payload["exercises"]),
                "pss_first_bytes": samples[0]["pss_bytes"],
                "pss_last_bytes": samples[-1]["pss_bytes"],
                "pss_peak_bytes": max(item["pss_bytes"] for item in samples),
                "rss_first_bytes": samples[0]["rss_bytes"],
                "rss_last_bytes": samples[-1]["rss_bytes"],
                "rss_peak_bytes": max(item["rss_bytes"] for item in samples),
                "private_data_first_bytes": samples[0]["private_data_bytes"],
                "private_data_last_bytes": samples[-1]["private_data_bytes"],
                # Battery and thermal telemetry are optional Android capabilities.
                # Some vendor builds omit one or both dumpsys fields; that must not
                # turn an otherwise valid runtime soak into a vendor-specific failure.
                "max_temperature_c": _optional_max([
                    item["battery_temperature_c"] for item in samples
                ]),
                "max_thermal_status": _optional_max([
                    item["thermal_status"] for item in samples
                ]),
            }
            _atomic_json(arguments.output.resolve(), payload)
            print(
                f"[{elapsed:9.1f}s] samples={len(samples)} runs={len(payload['exercises'])} "
                f"pss={samples[-1]['pss_bytes']} rss={samples[-1]['rss_bytes']} "
                f"temp={samples[-1]['battery_temperature_c']}",
                flush=True,
            )
            time.sleep(max(1.0, arguments.sample_seconds))
    except BaseException as error:
        payload["status"] = "failed"
        payload["failures"].append({"at": _now(), "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        payload["ended_at"] = _now()
        _atomic_json(arguments.output.resolve(), payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Soak the installed Android-local Player")
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", default="com.easycode.player.debug")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=4.0)
    parser.add_argument("--sample-seconds", type=float, default=60.0)
    parser.add_argument("--exercise-seconds", type=float, default=300.0)
    parser.add_argument("--run-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--tap-x", type=int, default=540)
    parser.add_argument("--tap-y", type=int, default=2190)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
