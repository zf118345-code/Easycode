"""Bounded Windows low-level input capture for OperationRecordingSessionV1."""

from __future__ import annotations

import ctypes
import queue
import threading
import time
from ctypes import wintypes
from typing import Any, Callable


class WindowsOperationRecorder:
    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_MOUSEWHEEL = 0x020A

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

    def __init__(self, callback: Callable[[dict[str, Any]], None], *, box: tuple[int, int, int, int], hwnd: int = 0) -> None:
        self.callback = callback
        self.box = box
        self.hwnd = int(hwnd or 0)
        self._thread: threading.Thread | None = None
        self._worker: threading.Thread | None = None
        self._thread_id = 0
        self._events: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=2048)
        self._mouse_hook = 0
        self._keyboard_hook = 0
        self._mouse_down: tuple[int, int, int] | None = None
        self._last_click_ms = 0
        self._last_click_point = (0, 0)
        self._callbacks: list[Any] = []

    def _inside(self, x: int, y: int) -> bool:
        left, top, right, bottom = self.box
        if not (left <= x < right and top <= y < bottom):
            return False
        if self.hwnd:
            foreground = int(ctypes.windll.user32.GetForegroundWindow() or 0)
            if foreground != self.hwnd:
                return False
        return True

    def _point(self, x: int, y: int) -> list[int]:
        return [x - self.box[0], y - self.box[1]]

    def _emit(self, event: dict[str, Any]) -> None:
        try:
            self._events.put_nowait({**event, "occurred_at_ms": int(time.time() * 1000)})
        except queue.Full:
            pass

    def _worker_loop(self) -> None:
        while True:
            event = self._events.get()
            if event is None:
                return
            try:
                self.callback(event)
            except Exception:
                continue

    @staticmethod
    def _key_name(vk: int) -> str:
        names = {8: "Backspace", 9: "Tab", 13: "Enter", 27: "Escape", 32: "Space", 46: "Delete", 112: "F1", 113: "F2", 114: "F3", 115: "F4", 116: "F5", 117: "F6", 118: "F7", 119: "F8", 120: "F9", 121: "F10", 122: "F11", 123: "F12"}
        if vk in names:
            return names[vk]
        if 0x30 <= vk <= 0x5A:
            return chr(vk)
        return f"VK_{vk}"

    def _hook_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        hook_proc = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def mouse_proc(code: int, message: int, pointer: int) -> int:
            if code >= 0:
                data = ctypes.cast(pointer, ctypes.POINTER(self.MSLLHOOKSTRUCT)).contents
                x, y, now = int(data.pt.x), int(data.pt.y), int(time.time() * 1000)
                if message == self.WM_LBUTTONDOWN and self._inside(x, y):
                    self._mouse_down = (x, y, now)
                elif message == self.WM_LBUTTONUP and self._mouse_down:
                    start_x, start_y, started = self._mouse_down
                    self._mouse_down = None
                    if self._inside(x, y):
                        if abs(x - start_x) + abs(y - start_y) >= 8:
                            self._emit({"kind": "drag", "points": [self._point(start_x, start_y), self._point(x, y)], "duration_ms": now - started})
                        else:
                            double = now - self._last_click_ms <= 500 and abs(x - self._last_click_point[0]) + abs(y - self._last_click_point[1]) <= 6
                            self._emit({"kind": "double_click" if double else "click", "point": self._point(x, y), "screen_point": [x, y]})
                            self._last_click_ms, self._last_click_point = now, (x, y)
                elif message == self.WM_RBUTTONUP and self._inside(x, y):
                    self._emit({"kind": "right_click", "point": self._point(x, y), "screen_point": [x, y]})
                elif message == self.WM_MOUSEWHEEL and self._inside(x, y):
                    delta = ctypes.c_short((int(data.mouseData) >> 16) & 0xFFFF).value / 120
                    self._emit({"kind": "scroll", "point": self._point(x, y), "delta": delta})
            return user32.CallNextHookEx(None, code, message, pointer)

        def keyboard_proc(code: int, message: int, pointer: int) -> int:
            if code >= 0 and message in {self.WM_KEYDOWN, self.WM_SYSKEYDOWN}:
                if not self.hwnd or int(user32.GetForegroundWindow() or 0) == self.hwnd:
                    data = ctypes.cast(pointer, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
                    vk = int(data.vkCode)
                    modifiers = []
                    for key, name in ((0x11, "Ctrl"), (0x12, "Alt"), (0x10, "Shift"), (0x5B, "Win"), (0x5C, "Win")):
                        if user32.GetAsyncKeyState(key) & 0x8000 and name not in modifiers:
                            modifiers.append(name)
                    key = self._key_name(vk)
                    self._emit({"kind": "shortcut" if modifiers else "key", "key": "+".join([*modifiers, key])})
            return user32.CallNextHookEx(None, code, message, pointer)

        mouse_callback, keyboard_callback = hook_proc(mouse_proc), hook_proc(keyboard_proc)
        self._callbacks = [mouse_callback, keyboard_callback]
        self._mouse_hook = int(user32.SetWindowsHookExW(self.WH_MOUSE_LL, mouse_callback, None, 0) or 0)
        self._keyboard_hook = int(user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, keyboard_callback, None, 0) or 0)
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="operation-recorder-worker")
        self._thread = threading.Thread(target=self._hook_loop, daemon=True, name="operation-recorder-hooks")
        self._worker.start()
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
        try:
            self._events.put_nowait(None)
        except queue.Full:
            pass
        if self._worker:
            self._worker.join(timeout=2.0)


__all__ = ["WindowsOperationRecorder"]
