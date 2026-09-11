"""Real-host smoke harness for the format-6 cross-platform control slice.

This is intentionally separate from pytest: it opens and operates real host UI.
It never treats a green model test as Windows UIA or ADB UIAutomator evidence.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _center(bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = bounds
    return (left + right) // 2, (top + bottom) // 2


def verify_windows() -> dict[str, Any]:
    import win32gui

    from core.vnext.runtime import RuntimeFailure
    from core.vnext.target_runtime import WindowsTargetDriver

    title = f"EasyCode Control Harness {os.getpid()}"
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = '{title}'
$form.Width = 420
$form.Height = 180
$form.StartPosition = 'CenterScreen'
$input = New-Object System.Windows.Forms.TextBox
$input.Left = 24
$input.Top = 24
$input.Width = 350
$input.Name = 'HarnessInput'
$input.Text = 'EasyCode Initial'
$button = New-Object System.Windows.Forms.Button
$button.Left = 24
$button.Top = 68
$button.Width = 140
$button.Text = 'Apply Control'
$button.Add_Click({{ $form.Controls['HarnessInput'].Text = 'EasyCode Clicked' }})
$form.Controls.Add($input)
$form.Controls.Add($button)
[System.Windows.Forms.Application]::Run($form)
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    process = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        hwnd = 0
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not hwnd:
            found: list[int] = []
            win32gui.EnumWindows(
                lambda candidate, _: found.append(candidate)
                if win32gui.IsWindowVisible(candidate) and win32gui.GetWindowText(candidate) == title
                else None,
                None,
            )
            hwnd = found[0] if found else 0
            if not hwnd:
                time.sleep(0.1)
        if not hwnd:
            raise RuntimeError("Windows UIA Harness 窗口未启动")

        driver = object.__new__(WindowsTargetDriver)
        driver.project_path = ""
        driver.target = {
            "target_id": "target.windows.harness",
            "window_title": title,
            "work_area": {"mode": "client"},
            "allow_physical_fallback": False,
        }
        driver.hwnd = hwnd
        driver._last_message = ""
        driver._control_references = {}
        driver._window_references = {}

        window_ref = driver.execute(
            "window.find",
            {
                "official.window.find.parameter.selector": {
                    "window_selector.field.title": title,
                    "window_selector.field.match_mode": "exact",
                },
            },
            lambda: False,
        )
        if not isinstance(window_ref, dict):
            raise RuntimeError("Windows Harness 未形成真实窗口引用")
        activation = {"status": "passed", "error_id": None, "message": None}
        try:
            driver.execute(
                "window.activate",
                {"official.window.activate.parameter.window": window_ref},
                lambda: False,
            )
        except RuntimeFailure as exc:
            activation = {
                "status": "blocked_by_foreground_policy",
                "error_id": exc.error_id,
                "message": str(exc),
            }
        before_window = driver.execute(
            "window.status",
            {"official.window.read_status.parameter.window": window_ref},
            lambda: False,
        )
        driver.execute(
            "window.move",
            {
                "official.window.move.parameter.window": window_ref,
                "official.window.move.parameter.position": {"kind": "point", "x": 80, "y": 80},
            },
            lambda: False,
        )
        driver.execute(
            "window.resize",
            {
                "official.window.resize.parameter.window": window_ref,
                "official.window.resize.parameter.size": {"width": 520, "height": 260},
            },
            lambda: False,
        )
        time.sleep(0.25)
        placed_window = driver.execute(
            "window.status",
            {"official.window.read_status.parameter.window": window_ref},
            lambda: False,
        )
        placed_position = placed_window.get("window_status.field.position") or {}
        placed_size = placed_window.get("window_status.field.size") or {}
        if placed_position != {"kind": "point", "x": 80, "y": 80}:
            raise RuntimeError(f"Windows 窗口移动未生效：{placed_position!r}")
        if placed_size != {"width": 520, "height": 260}:
            raise RuntimeError(f"Windows 窗口调整大小未生效：{placed_size!r}")
        display_states: list[str] = []
        for state in ("maximized", "minimized", "restored"):
            driver.execute(
                "window.set_display_state",
                {
                    "official.window.set_display_state.parameter.window": window_ref,
                    "official.window.set_display_state.parameter.state": state,
                },
                lambda: False,
            )
            time.sleep(0.25)
            display_states.append(state)

        edit_selector = {
            "control_selector.field.schema_version": 1,
            "control_selector.field.provider": "windows_uia",
            "control_selector.field.target_id": "target.windows.harness",
            "control_selector.field.control_type": "edit",
            "control_selector.field.index": 0,
        }
        edit_ref = driver.execute(
            "control.find", {"official.control.find.parameter.selector": edit_selector}, lambda: False,
        )
        if not isinstance(edit_ref, dict):
            raise RuntimeError("Windows UIA 未找到真实文本框")
        edit_status = driver.execute(
            "control.read_status",
            {"official.control.read_status.parameter.control": edit_ref},
            lambda: False,
        )
        if edit_status.get("control_status.field.enabled") is not True:
            raise RuntimeError(f"Windows UIA 文本框状态读取异常：{edit_status!r}")
        driver.execute(
            "control.focus",
            {"official.control.focus.parameter.control": edit_ref},
            lambda: False,
        )
        before = driver.execute(
            "control.read_text", {"official.control.read_text.parameter.control": edit_ref}, lambda: False,
        )
        driver.execute(
            "control.set_value",
            {
                "official.control.set_value.parameter.control": edit_ref,
                "official.control.set_value.parameter.value": "EasyCode SetValue Verified",
            },
            lambda: False,
        )
        after_set_value = driver.execute(
            "control.read_text", {"official.control.read_text.parameter.control": edit_ref}, lambda: False,
        )
        driver.execute(
            "control.input_text",
            {
                "official.control.type_text.parameter.control": edit_ref,
                "official.control.type_text.parameter.content": "EasyCode Input Verified",
                "official.control.type_text.parameter.mode": "auto",
            },
            lambda: False,
        )
        after_input = driver.execute(
            "control.read_text", {"official.control.read_text.parameter.control": edit_ref}, lambda: False,
        )

        button_selector = {
            "control_selector.field.schema_version": 1,
            "control_selector.field.provider": "windows_uia",
            "control_selector.field.target_id": "target.windows.harness",
            "control_selector.field.name": "Apply Control",
            "control_selector.field.index": 0,
        }
        button_ref = driver.execute(
            "control.find", {"official.control.find.parameter.selector": button_selector}, lambda: False,
        )
        if not isinstance(button_ref, dict):
            raise RuntimeError("Windows UIA 未找到真实按钮")
        driver.execute(
            "control.click",
            {
                "official.control.click.parameter.control": button_ref,
                "official.control.click.parameter.mode": "auto",
            },
            lambda: False,
        )
        click_delivery = driver.consume_message()
        time.sleep(1.0)
        after_click = driver.execute(
            "control.read_text", {"official.control.read_text.parameter.control": edit_ref}, lambda: False,
        )
        if (
            before != "EasyCode Initial"
            or after_set_value != "EasyCode SetValue Verified"
            or after_input != "EasyCode Input Verified"
            or after_click != "EasyCode Clicked"
        ):
            raise RuntimeError(
                f"Windows UIA 实际效果不一致：before={before!r}, set={after_set_value!r}, input={after_input!r}, "
                f"click={after_click!r}, delivery={click_delivery!r}"
            )
        driver.execute(
            "window.close",
            {"official.window.close.parameter.window": window_ref},
            lambda: False,
        )
        process.wait(timeout=3)
        return {
            "host": "windows_uia",
            "status": "passed" if activation["status"] == "passed" else "partial",
            "window": {
                "activation": activation,
                "initial_status_read": bool(before_window),
                "position": placed_position,
                "size": placed_size,
                "display_states": display_states,
                "closed_by_runtime": True,
            },
            "read_before": before,
            "read_after_set_value": after_set_value,
            "read_after_input": after_input,
            "read_after_click": after_click,
            "control_status": {
                "enabled": edit_status.get("control_status.field.enabled"),
                "editable": edit_status.get("control_status.field.editable"),
                "focusable": edit_status.get("control_status.field.focusable"),
            },
            "focused": True,
            "physical_fallback": False,
        }
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def verify_adb(serial: str) -> dict[str, Any]:
    from core.vnext.android_control_v6 import AdbUiAutomatorAdapter, meaningful_nodes, scale_point
    from core.vnext.target_runtime import AndroidAdbTargetDriver

    adb = os.environ.get("ANDROID_ADB") or r"D:\EasyCodeToolchains\android-sdk\platform-tools\adb.exe"
    subprocess.run(
        [adb, "-s", serial, "shell", "am", "start", "-a", "android.settings.SETTINGS"],
        check=True, capture_output=True, timeout=10,
    )
    time.sleep(0.8)
    target_id = f"target.adb.{serial.replace(':', '_')}"
    adapter = AdbUiAutomatorAdapter(serial)
    initial = meaningful_nodes(adapter.snapshot())
    readable = next(
        (node for node in initial if node.text and node.class_name.endswith("TextView")),
        None,
    )
    search = next(
        (
            node for node in initial
            if node.clickable and (
                "search" in f"{node.resource_id} {node.content_description} {node.text}".lower()
                or node.resource_id.endswith(":id/header_view")
            )
        ),
        None,
    )
    if readable is None or search is None:
        raise RuntimeError("系统设置页没有暴露可读文本或搜索控件")

    driver = AndroidAdbTargetDriver(".", {"target_id": target_id, "device_serial": serial})
    try:
        driver.capture_frame()
        readable_point = scale_point(_center(readable.bounds), adapter.display_size, driver._size)
        readable_selector = driver.capture_control_selector({"kind": "point", "x": readable_point[0], "y": readable_point[1]})
        readable_ref = driver.execute(
            "control.find", {"official.control.find.parameter.selector": readable_selector}, lambda: False,
        )
        read_value = driver.execute(
            "control.read_text", {"official.control.read_text.parameter.control": readable_ref}, lambda: False,
        )
        if not str(read_value).strip():
            raise RuntimeError("ADB 控件读取返回空值")

        search_point = scale_point(_center(search.bounds), adapter.display_size, driver._size)
        search_selector = driver.capture_control_selector({"kind": "point", "x": search_point[0], "y": search_point[1]})
        search_ref = driver.execute(
            "control.find", {"official.control.find.parameter.selector": search_selector}, lambda: False,
        )
        driver.execute(
            "control.click",
            {
                "official.control.click.parameter.control": search_ref,
                "official.control.click.parameter.mode": "auto",
            },
            lambda: False,
        )
        time.sleep(0.8)
        search_nodes = meaningful_nodes(adapter.snapshot())
        editable = next((node for node in search_nodes if node.editable), None)
        if editable is None:
            raise RuntimeError("点击搜索后没有出现可编辑控件")
        editable_point = scale_point(_center(editable.bounds), adapter.display_size, driver._size)
        editable_selector = driver.capture_control_selector({
            "kind": "point", "x": editable_point[0], "y": editable_point[1],
        })
        editable_ref = driver.execute(
            "control.find", {"official.control.find.parameter.selector": editable_selector}, lambda: False,
        )
        probe = "EasyCodeControlProbe"
        driver.execute(
            "control.input_text",
            {
                "official.control.type_text.parameter.control": editable_ref,
                "official.control.type_text.parameter.content": probe,
                "official.control.type_text.parameter.mode": "auto",
            },
            lambda: False,
        )
        time.sleep(0.5)
        after = meaningful_nodes(adapter.snapshot())
        typed = next((node.text for node in after if node.editable), "")
        if probe not in typed:
            raise RuntimeError(f"ADB 控件输入未在真实控件树回读：{typed!r}")
        return {
            "host": "adb_uiautomator",
            "serial": serial,
            "status": "passed",
            "read_text_nonempty": True,
            "clicked_search": True,
            "input_roundtrip": typed,
        }
    finally:
        driver.close()
        subprocess.run([adb, "-s", serial, "shell", "input", "keyevent", "4"], capture_output=True, timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--adb", action="append", default=[])
    parser.add_argument("--output")
    arguments = parser.parse_args()
    results: list[dict[str, Any]] = []
    if arguments.windows:
        results.append(verify_windows())
    for serial in arguments.adb:
        results.append(verify_adb(serial))
    report = {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        output = Path(arguments.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
