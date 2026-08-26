"""Windows DPI 坐标契约初始化。"""

from __future__ import annotations

import ctypes
import os


def enable_per_monitor_v2() -> bool:
    """尽可能早地启用 Per-Monitor-V2，使 Win32/UIA/截图使用同一物理像素空间。"""
    if os.name != 'nt':
        return False
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = (HANDLE)-4
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return True
    except Exception:
        pass
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:
        pass
    try:
        return bool(ctypes.windll.user32.SetProcessDPIAware())
    except Exception:
        return False
