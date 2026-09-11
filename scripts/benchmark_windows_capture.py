"""Measure the real Windows window-capture provider and resource stability."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
import platform
from pathlib import Path
import statistics
import time

import psutil
import win32gui

from core.services.screenshot_service import capture_window_with_info


def _window(title: str) -> int:
    matches: list[int] = []

    def visit(hwnd: int, _extra: object) -> None:
        if win32gui.IsWindowVisible(hwnd) and title.casefold() in win32gui.GetWindowText(hwnd).casefold():
            matches.append(hwnd)

    win32gui.EnumWindows(visit, None)
    if not matches:
        raise RuntimeError(f"找不到窗口：{title}")
    return int(matches[0])


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="EasyCode Capture Harness")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--warmup-frames", type=int, default=10)
    parser.add_argument("--interval-ms", type=float, default=16.0)
    parser.add_argument("--output", type=Path, default=Path("output/g8-performance/windows-capture.json"))
    args = parser.parse_args()
    hwnd = _window(args.title)
    # WGC creates its Direct3D device, frame pool and WinRT dispatcher lazily.
    # Treat those persistent session resources as startup cost, not a leak.
    for _ in range(max(1, args.warmup_frames)):
        image, info = capture_window_with_info(hwnd)
        if image is None:
            raise RuntimeError(str(info))
        time.sleep(0.01)
    gc.collect()
    process = psutil.Process()
    rss_before = process.memory_info().rss
    handles_before = process.num_handles()
    durations: list[float] = []
    ages: list[float] = []
    providers: dict[str, int] = {}
    image_size: list[int] = []
    started = time.perf_counter()
    for _ in range(max(1, args.frames)):
        image, info = capture_window_with_info(hwnd)
        if image is None:
            raise RuntimeError(str(info))
        image_size = [int(image.width), int(image.height)]
        duration = float(info.get("capture_duration_ms") or 0.0)
        durations.append(duration)
        if info.get("frame_age_ms") is not None:
            ages.append(float(info["frame_age_ms"]))
        provider = str(info.get("provider") or "unknown")
        providers[provider] = providers.get(provider, 0) + 1
        if args.interval_ms > 0:
            time.sleep(args.interval_ms / 1000.0)
    elapsed = time.perf_counter() - started
    rss_after = process.memory_info().rss
    handles_after = process.num_handles()
    payload = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "machine": {"host": platform.node(), "os": platform.platform(), "python": platform.python_version()},
        "window": {"title": win32gui.GetWindowText(hwnd), "hwnd": hwnd, "image_size": image_size},
        "frames": len(durations),
        "elapsed_ms": round(elapsed * 1000, 3),
        "providers": providers,
        "capture_duration_p50_ms": round(statistics.median(durations), 3),
        "capture_duration_p95_ms": round(_percentile(durations, 0.95), 3),
        "capture_duration_worst_ms": round(max(durations), 3),
        "frame_age_p95_ms": round(_percentile(ages, 0.95), 3) if ages else None,
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "rss_growth_bytes": rss_after - rss_before,
        "handles_before": handles_before,
        "handles_after": handles_after,
        "handle_growth": handles_after - handles_before,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
