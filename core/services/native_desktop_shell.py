"""Launch the packaged Vue Player inside the native WebView2 desktop owner."""

from __future__ import annotations

import logging
import subprocess

from core.services.native_capture_overlay import NativeCaptureOverlay


logger = logging.getLogger(__name__)


def run_native_desktop_shell(
    url: str,
    *,
    title: str = 'Easycode 自动化运行助手',
    width: int = 960,
    height: int = 720,
) -> bool:
    """Run the shell until its native window closes.

    The native executable is a build artifact in frozen packages.  Source-mode
    builds may compile it through ``ensure_binary``; frozen releases explicitly
    reject a missing artifact instead of compiling on an end-user machine.
    """

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

    return_code = process.wait()
    if return_code != 0:
        logger.error('原生桌面宿主异常退出（代码 %s）', return_code)
        return False
    return True
