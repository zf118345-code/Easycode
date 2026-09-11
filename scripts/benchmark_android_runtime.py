"""Measure Easycode's Android video and input hot paths on a real device.

This is intentionally a small operational diagnostic rather than a benchmark
framework.  It exercises the exact runtime providers used by visual nodes and
always restores the adb forward/server session in ``finally``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import platform
from pathlib import Path
import statistics
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.services.android_stream import ScrcpyVideoSession, validate_scrcpy_runtime
from core.services.runtime_session import PersistentAdbInputSession


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return float(ordered[index])


def benchmark_video(device_id: str, frame_count: int, max_size: int, max_fps: int) -> dict:
    session = ScrcpyVideoSession(device_id, max_size=max_size, max_fps=max_fps)
    waits_ms: list[float] = []
    frame_intervals_ms: list[float] = []
    sequence = 0
    previous_arrival_ns: int | None = None
    first_shape = None
    started_ns = time.monotonic_ns()
    try:
        session.start()
        for _ in range(frame_count):
            wait_started_ns = time.monotonic_ns()
            packet = session.next(sequence, timeout_s=8.0)
            arrived_ns = time.monotonic_ns()
            sequence = packet.sequence
            waits_ms.append((arrived_ns - wait_started_ns) / 1_000_000.0)
            if previous_arrival_ns is not None:
                frame_intervals_ms.append((arrived_ns - previous_arrival_ns) / 1_000_000.0)
            previous_arrival_ns = arrived_ns
            first_shape = first_shape or list(packet.image.shape)
    finally:
        session.close()
    elapsed_s = (time.monotonic_ns() - started_ns) / 1_000_000_000.0
    return {
        'provider': 'scrcpy_stream',
        'frames': frame_count,
        'elapsed_ms': round(elapsed_s * 1000, 2),
        'effective_fps': round(frame_count / elapsed_s, 2) if elapsed_s else 0.0,
        'frame_shape': first_shape,
        'next_wait_p50_ms': round(statistics.median(waits_ms), 2) if waits_ms else 0.0,
        'next_wait_p95_ms': round(_percentile(waits_ms, 0.95), 2),
        'frame_interval_p50_ms': round(statistics.median(frame_intervals_ms), 2) if frame_intervals_ms else 0.0,
        'frame_interval_p95_ms': round(_percentile(frame_intervals_ms, 0.95), 2),
    }


def benchmark_input(device_id: str, tap_count: int, x: int, y: int) -> dict:
    session = PersistentAdbInputSession(device_id)
    latencies_ms: list[float] = []
    methods: set[str] = set()
    try:
        session.start()
        for _ in range(tap_count):
            started_ns = time.monotonic_ns()
            result = session.tap(x, y)
            latencies_ms.append((time.monotonic_ns() - started_ns) / 1_000_000.0)
            methods.add(str(result.get('method') or 'unknown'))
            if not result.get('ok'):
                raise RuntimeError(result.get('message') or 'input benchmark failed')
    finally:
        session.close()
    return {
        'provider': ','.join(sorted(methods)),
        'taps': tap_count,
        'tap_ack_p50_ms': round(statistics.median(latencies_ms), 2) if latencies_ms else 0.0,
        'tap_ack_p95_ms': round(_percentile(latencies_ms, 0.95), 2),
        'note': 'ACK measures transport completion, not visual UI response.',
    }


def benchmark_scrcpy_input(
    device_id: str,
    tap_count: int,
    x: int,
    y: int,
    max_size: int,
    max_fps: int,
) -> dict:
    session = ScrcpyVideoSession(device_id, max_size=max_size, max_fps=max_fps)
    latencies_ms: list[float] = []
    try:
        session.start()
        first = session.next(0, timeout_s=8.0)
        height, width = first.image.shape[:2]
        for _ in range(tap_count):
            started_ns = time.monotonic_ns()
            result = session.tap(x, y, width, height)
            latencies_ms.append((time.monotonic_ns() - started_ns) / 1_000_000.0)
            if not result.get('ok'):
                raise RuntimeError(result.get('message') or 'scrcpy input benchmark failed')
    finally:
        session.close()
    return {
        'provider': 'scrcpy_control',
        'taps': tap_count,
        'tap_send_p50_ms': round(statistics.median(latencies_ms), 3) if latencies_ms else 0.0,
        'tap_send_p95_ms': round(_percentile(latencies_ms, 0.95), 3),
        'note': 'Send latency measures socket delivery, not visual UI response.',
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', required=True)
    parser.add_argument('--frames', type=int, default=60)
    parser.add_argument('--max-size', type=int, default=1280)
    parser.add_argument('--max-fps', type=int, default=60)
    parser.add_argument('--input-taps', type=int, default=0)
    parser.add_argument('--scrcpy-input-taps', type=int, default=0)
    parser.add_argument('--tap-x', type=int, default=1)
    parser.add_argument('--tap-y', type=int, default=1)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()

    valid, detail = validate_scrcpy_runtime()
    if not valid:
        raise RuntimeError(detail)
    result = {
        'schema_version': 1,
        'measured_at': datetime.now(timezone.utc).isoformat(),
        'machine': {
            'host': platform.node(),
            'os': platform.platform(),
            'python': platform.python_version(),
        },
        'device_id': args.device,
        'runtime': detail,
        'video': benchmark_video(args.device, max(1, args.frames), args.max_size, args.max_fps),
    }
    if args.input_taps > 0:
        result['input'] = benchmark_input(
            args.device,
            args.input_taps,
            args.tap_x,
            args.tap_y,
        )
    if args.scrcpy_input_taps > 0:
        result['scrcpy_input'] = benchmark_scrcpy_input(
            args.device,
            args.scrcpy_input_taps,
            args.tap_x,
            args.tap_y,
            args.max_size,
            args.max_fps,
        )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
