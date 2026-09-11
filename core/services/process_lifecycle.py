"""Exact-PID child process cleanup shared by build and runtime services."""

from __future__ import annotations

import contextlib
import os
import subprocess
from typing import Any


def terminate_process_tree(process: subprocess.Popen[Any] | None, *, grace_seconds: float = 1.5) -> dict[str, Any]:
    """Terminate one known child and, on Windows, every descendant of its PID."""

    if process is None:
        return {'terminated': False, 'reason': 'missing_process'}
    pid = int(getattr(process, 'pid', 0) or 0)
    if pid <= 0:
        return {'terminated': False, 'reason': 'missing_pid'}
    if process.poll() is not None:
        return {'terminated': False, 'reason': 'already_exited', 'pid': pid}

    used_tree_kill = False
    if os.name == 'nt':
        try:
            subprocess.run(
                ['taskkill', '/PID', str(pid), '/T', '/F'],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            used_tree_kill = True
        except (OSError, subprocess.SubprocessError):
            used_tree_kill = False
    else:
        with contextlib.suppress(OSError):
            process.terminate()

    try:
        process.wait(timeout=max(0.1, float(grace_seconds)))
    except (OSError, subprocess.TimeoutExpired):
        with contextlib.suppress(OSError):
            process.kill()
        try:
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            return {'terminated': False, 'reason': 'still_running', 'pid': pid, 'tree_kill': used_tree_kill}
    return {'terminated': process.poll() is not None, 'pid': pid, 'tree_kill': used_tree_kill}
