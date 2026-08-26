"""Persistent Windows.Graphics.Capture sessions keyed by target HWND.

The optional ``windows-capture`` wheel is a Rust/PyO3 wrapper over the native
Windows Graphics Capture API.  Sessions are intentionally long lived: opening a
new Direct3D capture session for every visual-node poll would be slower than the
legacy path and would leak native resources under multi-instance workloads.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WgcFrame:
    image: Image.Image
    sequence: int
    captured_at_ns: int


class WgcWindowSession:
    def __init__(self, hwnd: int, *, minimum_update_interval_ms: int = 0):
        self.hwnd = int(hwnd)
        self.minimum_update_interval_ms = max(0, int(minimum_update_interval_ms or 0))
        self._condition = threading.Condition()
        self._latest: WgcFrame | None = None
        self._sequence = 0
        self._capture: Any = None
        self._control: Any = None
        self._error: Exception | None = None
        self._started = False

    @staticmethod
    def available() -> tuple[bool, str]:
        if os.name != 'nt':
            return False, 'Windows Graphics Capture 仅支持 Windows'
        try:
            import windows_capture  # noqa: F401
        except Exception as exc:
            return False, f'未安装 windows-capture: {exc}'
        try:
            version = tuple(int(value) for value in os.sys.getwindowsversion()[:3])
            if version[2] < 18362:
                return False, '按 HWND 捕获要求 Windows 10 1903（Build 18362）或更高版本'
        except Exception:
            pass
        return True, 'Windows Graphics Capture 可用'

    def start(self) -> 'WgcWindowSession':
        with self._condition:
            if self._started:
                return self
            self._started = True
        try:
            from windows_capture import Frame, InternalCaptureControl, WindowsCapture

            capture = WindowsCapture(
                cursor_capture=False,
                draw_border=False,
                minimum_update_interval=self.minimum_update_interval_ms or None,
                window_hwnd=self.hwnd,
            )

            @capture.event
            def on_frame_arrived(frame: Frame, _capture_control: InternalCaptureControl):
                try:
                    # Native memory is valid only for the callback lifetime.  Copy
                    # once into RGB and publish an immutable PIL image.
                    array = frame.frame_buffer
                    if array is None or getattr(array, 'size', 0) <= 0:
                        return
                    if array.shape[2] == 4:
                        rgb = cv2.cvtColor(array, cv2.COLOR_BGRA2RGB)
                    else:
                        rgb = cv2.cvtColor(array[:, :, :3], cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(rgb.copy(), 'RGB')
                    with self._condition:
                        self._sequence += 1
                        self._latest = WgcFrame(image, self._sequence, time.monotonic_ns())
                        self._error = None
                        self._condition.notify_all()
                except Exception as exc:  # callback errors must wake waiters
                    with self._condition:
                        self._error = exc
                        self._condition.notify_all()

            @capture.event
            def on_closed():
                with self._condition:
                    self._error = RuntimeError('目标窗口已关闭，WGC 会话已结束')
                    self._condition.notify_all()

            self._capture = capture
            self._control = capture.start_free_threaded()
            return self
        except Exception as exc:
            with self._condition:
                self._error = exc
                self._condition.notify_all()
            self.close()
            raise

    def latest(self, *, timeout_s: float = 0.45, after_sequence: int | None = None) -> WgcFrame:
        self.start()
        deadline = time.monotonic() + max(0.01, float(timeout_s))
        with self._condition:
            while True:
                if self._latest is not None and (
                    after_sequence is None or self._latest.sequence > int(after_sequence)
                ):
                    return self._latest
                if self._error is not None:
                    raise RuntimeError(f'WGC 捕获失败: {self._error}') from self._error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('WGC 等待首帧超时')
                self._condition.wait(remaining)

    def close(self):
        control = self._control
        self._control = None
        self._capture = None
        with self._condition:
            self._started = False
            self._condition.notify_all()
        if control is not None:
            try:
                control.stop()
            except Exception:
                pass


class WgcSessionRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: dict[int, WgcWindowSession] = {}

    def get(self, hwnd: int) -> WgcWindowSession:
        hwnd = int(hwnd)
        with self._lock:
            session = self._sessions.get(hwnd)
            if session is None:
                session = WgcWindowSession(hwnd)
                self._sessions[hwnd] = session
            return session

    def discard(self, hwnd: int):
        with self._lock:
            session = self._sessions.pop(int(hwnd), None)
        if session is not None:
            session.close()

    def close_all(self):
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


wgc_sessions = WgcSessionRegistry()

