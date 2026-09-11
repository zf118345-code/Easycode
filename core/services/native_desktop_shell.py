"""Launch the packaged Vue Player inside the native WebView2 desktop owner."""

from __future__ import annotations

import logging
import os
import subprocess
import threading

from core.services.native_capture_overlay import NativeCaptureOverlay


logger = logging.getLogger(__name__)
_PROCESS_LOCK = threading.Lock()
_desktop_shell_process_id = 0


def _attach_kill_on_parent_close(process: subprocess.Popen):
    """Put the native shell in a private job so a crashed host leaves no orphan UI."""

    if os.name != 'nt':
        return None
    try:
        import win32job

        job = win32job.CreateJobObject(None, '')
        information = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation,
        )
        information['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation, information,
        )
        win32job.AssignProcessToJobObject(job, process._handle)  # noqa: SLF001 - pywin32 requires the native handle
        return job
    except Exception as exc:
        logger.warning('无法为原生桌面宿主建立父进程故障边界: %s', exc)
        return None


def desktop_shell_process_id() -> int:
    """Return the live native Player shell PID so capture cannot bind itself."""

    with _PROCESS_LOCK:
        return int(_desktop_shell_process_id)


def run_native_desktop_shell(
    url: str,
    *,
    title: str = 'Easycode 自动化运行助手',
    icon_path: str = '',
    width: int = 960,
    height: int = 720,
) -> bool:
    """Run the shell until its native window closes.

    The native executable is a build artifact in frozen packages.  Source-mode
    builds may compile it through ``ensure_binary``; frozen releases explicitly
    reject a missing artifact instead of compiling on an end-user machine.
    """

    global _desktop_shell_process_id

    try:
        binary = NativeCaptureOverlay.ensure_binary()
        process = subprocess.Popen(
            [
                str(binary),
                '--desktop-shell',
                '--url',
                str(url),
                '--title',
                str(title),
                '--icon',
                str(icon_path or ''),
                '--width',
                str(max(800, int(width))),
                '--height',
                str(max(600, int(height))),
            ],
            cwd=str(binary.parent),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except Exception as exc:
        logger.error('原生桌面宿主启动失败: %s', exc)
        return False

    with _PROCESS_LOCK:
        _desktop_shell_process_id = int(process.pid)
    job = _attach_kill_on_parent_close(process)
    try:
        return_code = process.wait()
    finally:
        if job is not None:
            try:
                job.Close()
            except Exception:
                pass
        with _PROCESS_LOCK:
            if _desktop_shell_process_id == int(process.pid):
                _desktop_shell_process_id = 0
    if return_code != 0:
        logger.error('原生桌面宿主异常退出（代码 %s）', return_code)
        return False
    return True
