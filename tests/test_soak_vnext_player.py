from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import pytest

from scripts import soak_vnext_player as soak


def test_fixture_window_is_restored_without_stealing_product_semantics(monkeypatch) -> None:
    state = {"iconic": True, "restores": 0}

    def enumerate_windows(callback, context) -> None:
        callback(42, context)

    def show_window(hwnd: int, command: int) -> None:
        assert hwnd == 42
        assert command == 9
        state["iconic"] = False
        state["restores"] += 1

    fake_gui = SimpleNamespace(
        EnumWindows=enumerate_windows,
        IsWindowVisible=lambda _hwnd: True,
        GetWindowText=lambda _hwnd: "EasyCode Capture Harness",
        IsIconic=lambda _hwnd: state["iconic"],
        ShowWindow=show_window,
    )
    monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(SW_RESTORE=9))

    result = soak._ensure_fixture_window_ready("EasyCode Capture Harness")

    assert result == {
        "title": "EasyCode Capture Harness",
        "window_handle": 42,
        "restored": True,
    }
    assert state["restores"] == 1


def test_fixture_window_must_be_unique(monkeypatch) -> None:
    fake_gui = SimpleNamespace(
        EnumWindows=lambda callback, context: (
            callback(41, context), callback(42, context)
        ),
        IsWindowVisible=lambda _hwnd: True,
        GetWindowText=lambda _hwnd: "EasyCode Capture Harness",
    )
    monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(SW_RESTORE=9))

    with pytest.raises(RuntimeError, match="应唯一存在"):
        soak._ensure_fixture_window_ready("EasyCode Capture Harness")


def test_worker_cleanup_waits_for_terminal_child_to_exit() -> None:
    states = iter([[SimpleNamespace(pid=81, is_running=lambda: True)], []])
    root = SimpleNamespace(children=lambda recursive: next(states))

    elapsed = soak._wait_for_worker_cleanup(
        root, timeout_seconds=0.5, poll_seconds=0.001,
    )

    assert elapsed >= 0


def test_worker_cleanup_fails_closed_when_child_remains(monkeypatch) -> None:
    child = SimpleNamespace(pid=82, is_running=lambda: True)
    root = SimpleNamespace(children=lambda recursive: [child])
    ticks = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Worker 未在时限内退出：82"):
        soak._wait_for_worker_cleanup(root, timeout_seconds=0.1)
