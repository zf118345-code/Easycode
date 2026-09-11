"""Read-only ADB device discovery for the format-6 authoring workspace.

Discovery is deliberately separate from target resolution.  It may suggest an
explicit serial to the author, but it never selects, persists, or rebinds a
target on their behalf.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdbCommandResult:
    returncode: int
    stdout: str
    stderr: str


AdbRunner = Callable[[Sequence[str], float], AdbCommandResult]


def _run_adb(command: Sequence[str], timeout_seconds: float) -> AdbCommandResult:
    startupinfo = None
    creationflags = 0
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout_seconds,
        check=False,
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    return AdbCommandResult(completed.returncode, completed.stdout, completed.stderr)


def _parse_details(tokens: Sequence[str]) -> dict[str, str]:
    details: dict[str, str] = {}
    for token in tokens:
        key, separator, value = token.partition(':')
        if separator and key and value:
            details[key] = value
    return details


def parse_adb_devices(output: str) -> list[dict[str, Any]]:
    """Parse ``adb devices -l`` without interpreting a candidate as a binding."""

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in output.replace('\r', '').split('\n'):
        line = raw_line.strip()
        if not line or line.startswith('List of devices attached') or line.startswith('*'):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue
        serial, state = tokens[0], tokens[1]
        if not serial or serial in seen:
            continue
        seen.add(serial)
        details = _parse_details(tokens[2:])
        model = details.get('model', '').replace('_', ' ')
        product = details.get('product', '').replace('_', ' ')
        candidates.append({
            'serial': serial,
            'state': state,
            'selectable': state == 'device',
            'model': model,
            'product': product,
            'transport_id': details.get('transport_id', ''),
            'display_name': model or product or serial,
        })
    return candidates


def discover_adb_candidates(
    *,
    runner: AdbRunner = _run_adb,
    adb_path: str | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    executable = adb_path or shutil.which('adb')
    if not executable:
        return {
            'available': False,
            'code': 'adb_not_installed',
            'message': '未找到 ADB。仍可手动填写序列号，或安装并配置 ADB 后重新扫描。',
            'candidates': [],
        }
    try:
        result = runner((executable, 'devices', '-l'), timeout_seconds)
    except subprocess.TimeoutExpired:
        return {
            'available': False,
            'code': 'adb_scan_timeout',
            'message': 'ADB 设备扫描超时。请检查 ADB 服务后重试。',
            'candidates': [],
        }
    except OSError as exc:
        return {
            'available': False,
            'code': 'adb_start_failed',
            'message': f'无法启动 ADB：{exc}',
            'candidates': [],
        }
    if result.returncode != 0:
        reason = (result.stderr or result.stdout).strip()
        return {
            'available': False,
            'code': 'adb_scan_failed',
            'message': f'ADB 扫描失败：{reason}' if reason else 'ADB 扫描失败。',
            'candidates': [],
        }
    candidates = parse_adb_devices(result.stdout)
    return {
        'available': True,
        'code': 'ok',
        'message': '没有发现已连接的 ADB 设备。' if not candidates else '',
        'candidates': candidates,
    }
