"""Frozen per-user Windows installer entry point for EasyCode Player media."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.vnext.windows_installation_v6 import (
    INSTALL_MARKER,
    WindowsInstallationError,
    WindowsInstallerMediaV6,
    WindowsPerUserInstallerV6,
)

_LOG_LIMIT = 1024 * 1024
_log_lock = threading.Lock()


def _installer_log(event: str, status: str, **details: Any) -> None:
    """Append one bounded diagnostic record without project/profile values."""

    root = Path(str(os.environ.get("LOCALAPPDATA") or Path.home())) / "EasyCode" / "Installer" / "logs"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "latest.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "status": status,
        **{key: value for key, value in details.items() if value not in (None, "")},
    }
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with _log_lock:
        if path.is_file() and path.stat().st_size + len(payload.encode("utf-8")) > _LOG_LIMIT:
            previous = root / "previous.jsonl"
            previous.unlink(missing_ok=True)
            os.replace(path, previous)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)


def _base() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))


def _media_default() -> Path:
    beside = Path(sys.executable).resolve().parent
    if (beside / "easycode-installer-media.json").is_file():
        return beside
    nested = beside / "Windows_Installer"
    return nested if nested.is_dir() else _base() / "Windows_Installer"


def _hidden_run(command: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Run a non-critical integration command without blocking installation.

    The application directory has already been committed before Hub registration
    runs.  A wedged or damaged Hub must therefore be reported as a repairable
    integration failure, not turn a successful atomic install into a 120-second
    apparent failure.  The same rule lets uninstall remove the product even when
    the old runtime can no longer start to disable its registry entry.
    """

    try:
        return subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return subprocess.CompletedProcess(command, 124, stdout, stderr or f"命令在 {timeout:g} 秒后超时")


def _shortcut(path: Path, executable: Path, arguments: list[str], working_directory: Path) -> None:
    import win32com.client  # Bundled into the frozen installer; not required on the customer machine.

    path.parent.mkdir(parents=True, exist_ok=True)
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(path))
    shortcut.Targetpath = str(executable)
    shortcut.Arguments = subprocess.list2cmdline(arguments)
    shortcut.WorkingDirectory = str(working_directory)
    shortcut.IconLocation = f"{executable},0"
    shortcut.save()


def _integration_paths(product_id: str, display_name: str) -> dict[str, Path]:
    appdata = Path(str(os.environ.get("APPDATA") or "")).resolve()
    local = Path(str(os.environ.get("LOCALAPPDATA") or "")).resolve()
    if not str(os.environ.get("APPDATA") or "").strip() or not str(os.environ.get("LOCALAPPDATA") or "").strip():
        raise WindowsInstallationError("WIN-INSTALL-HOST-001", "当前用户目录不可用")
    safe_name = "".join(character for character in display_name if character not in '<>:"/\\|?*').strip() or product_id
    start_menu = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    desktop = Path(str(os.environ.get("USERPROFILE") or local)) / "Desktop"
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        start_menu = Path(str(shell.SpecialFolders("Programs")))
        desktop = Path(str(shell.SpecialFolders("Desktop")))
    except Exception:
        # Known-folder discovery is preferred, but redirected folders are not
        # allowed to make the actual installation fail.
        pass
    return {
        "start_menu": start_menu / "EasyCode" / f"{safe_name}.lnk",
        "desktop": desktop / f"{safe_name}.lnk",
        "installer": local / "Programs" / "EasyCode" / "Installer" / "EasycodeInstaller.exe",
    }


def _write_uninstall_entry(result: dict[str, Any], uninstaller: Path) -> None:
    import winreg

    key_name = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\EasyCode.{result['product_id']}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_name, 0, winreg.KEY_WRITE) as key:
        values = {
            "DisplayName": result["display_name"],
            "DisplayVersion": result["release_id"],
            "Publisher": "EasyCode",
            "InstallLocation": result["install_root"],
            "DisplayIcon": result["executable"],
            "UninstallString": subprocess.list2cmdline([str(uninstaller), "--uninstall", result["install_root"]]),
            "QuietUninstallString": subprocess.list2cmdline([str(uninstaller), "--uninstall", result["install_root"], "--quiet"]),
        }
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)


def _delete_uninstall_entry(product_id: str) -> None:
    import winreg

    key_name = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\EasyCode.{product_id}"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_name)
    except FileNotFoundError:
        pass


def install(media: Path, *, desktop: bool) -> dict[str, Any]:
    _installer_log("install", "started", media=str(media), desktop_shortcut=desktop)
    result = WindowsPerUserInstallerV6().install(media)
    paths = _integration_paths(result["product_id"], result["display_name"])
    executable = Path(result["executable"])
    registered = _hidden_run([
        str(executable), "--register-installation", result["install_root"], "--instance-name", "实例 1",
    ])
    result["hub_registered"] = registered.returncode == 0
    result["hub_error"] = "" if registered.returncode == 0 else (registered.stderr or registered.stdout)[-1200:]
    arguments = (
        ["--mode", "prod", "--port", "0", "--player-console", "--select-product", result["product_id"]]
        if result["hub_registered"] else [
            "--mode", "prod", "--player-bundle", result["bundle"],
            "--player-trust-root", result["trust_root"],
        ]
    )
    _shortcut(paths["start_menu"], executable, arguments, Path(result["install_root"]))
    if desktop:
        _shortcut(paths["desktop"], executable, arguments, Path(result["install_root"]))
    elif paths["desktop"].exists():
        paths["desktop"].unlink()
    current = Path(sys.executable).resolve()
    paths["installer"].parent.mkdir(parents=True, exist_ok=True)
    if current != paths["installer"].resolve():
        temporary = paths["installer"].with_suffix(".new.exe")
        shutil.copy2(current, temporary)
        os.replace(temporary, paths["installer"])
    _write_uninstall_entry(result, paths["installer"])
    result["shortcut"] = str(paths["start_menu"])
    result["desktop_shortcut"] = str(paths["desktop"]) if desktop else ""
    _installer_log(
        "install", "completed", product_id=result["product_id"], release_id=result["release_id"],
        install_root=result["install_root"], hub_registered=result["hub_registered"],
    )
    return result


def uninstall(install_root: Path) -> dict[str, Any]:
    _installer_log("uninstall", "started", install_root=str(install_root))
    marker = json.loads((install_root / INSTALL_MARKER).read_text(encoding="utf-8-sig"))
    product_id = str(marker.get("product_id") or "")
    display_name = str(marker.get("display_name") or product_id)
    paths = _integration_paths(product_id, display_name)
    executable = install_root / "EasycodePlayer.exe"
    if executable.is_file():
        _hidden_run([str(executable), "--disable-installation", str(install_root)])
    for shortcut in (paths["start_menu"], paths["desktop"]):
        if shortcut.is_file():
            shortcut.unlink()
    _delete_uninstall_entry(product_id)
    result = WindowsPerUserInstallerV6().uninstall(install_root)
    _installer_log("uninstall", "completed", product_id=product_id, install_root=str(install_root), data_preserved=True)
    return result


def _run_gui(media: Path, uninstall_root: Path | None = None) -> int:
    import tkinter as tk
    from tkinter import ttk

    metadata = (
        json.loads((uninstall_root / INSTALL_MARKER).read_text(encoding="utf-8-sig"))
        if uninstall_root else WindowsInstallerMediaV6.inspect(media)["manifest"]
    )
    window = tk.Tk()
    window.title("EasyCode 安装程序")
    window.geometry("520x330")
    window.resizable(False, False)
    window.configure(bg="#10110f")
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("TCheckbutton", background="#10110f", foreground="#d8ddd4")
    frame = tk.Frame(window, bg="#10110f", padx=30, pady=26)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text=metadata.get("display_name", "EasyCode Player"), bg="#10110f", fg="#f1f4ed", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
    action_text = "卸载后默认保留运行方案、日志和录制。" if uninstall_root else "安装到当前 Windows 用户，不需要管理员权限。"
    tk.Label(frame, text=action_text, bg="#10110f", fg="#98a095", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(8, 18))
    tk.Label(frame, text=f"版本  {metadata.get('release_id', '')}", bg="#10110f", fg="#c7cdc3", font=("Microsoft YaHei UI", 10)).pack(anchor="w")
    install_location = uninstall_root
    if install_location is None:
        install_location = WindowsPerUserInstallerV6().products_root / str(metadata.get("product_id") or "")
    tk.Label(
        frame, text=f"位置  {install_location}", bg="#10110f", fg="#c7cdc3",
        wraplength=450, justify="left", font=("Microsoft YaHei UI", 9),
    ).pack(anchor="w", pady=(6, 0))
    desktop = tk.BooleanVar(value=True)
    if not uninstall_root:
        ttk.Checkbutton(frame, text="创建桌面快捷方式", variable=desktop).pack(anchor="w", pady=(20, 0))
    status = tk.Label(frame, text="", bg="#10110f", fg="#f09a62", wraplength=450, justify="left", font=("Microsoft YaHei UI", 9))
    status.pack(anchor="w", pady=(20, 8))
    buttons = tk.Frame(frame, bg="#10110f")
    buttons.pack(side="bottom", fill="x")
    primary = tk.Button(buttons, text="卸载" if uninstall_root else "安装", bg="#e85d19", fg="white", activebackground="#ff7130", relief="flat", padx=24, pady=9)
    primary.pack(side="right")
    cancel = tk.Button(buttons, text="取消", command=window.destroy, bg="#20221f", fg="#d8ddd4", activebackground="#2c2f2a", relief="flat", padx=20, pady=9)
    cancel.pack(side="right", padx=(0, 10))
    outcome = {"code": 1}
    busy = {"value": False}

    def request_close() -> None:
        if busy["value"]:
            status.configure(text="安装目录正在原子更新，请等待当前步骤完成。", fg="#f09a62")
            return
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", request_close)
    cancel.configure(command=request_close)

    def execute() -> None:
        busy["value"] = True
        primary.configure(state="disabled")
        cancel.configure(state="disabled")
        status.configure(text="正在处理，请稍候…", fg="#98a095")
        create_desktop = desktop.get()
        def worker() -> None:
            try:
                result = uninstall(uninstall_root) if uninstall_root else install(media, desktop=create_desktop)
                outcome["code"] = 0
                text = "卸载完成，用户数据已保留。" if uninstall_root else (
                    "安装完成。" if result.get("hub_registered") else "安装完成；计划中心登记失败，可直接运行并稍后修复。"
                )
                def completed() -> None:
                    busy["value"] = False
                    status.configure(text=text, fg="#7fcf8b")
                    primary.configure(text="完成", state="normal", command=window.destroy)
                    cancel.configure(state="disabled")
                window.after(0, completed)
            except Exception as exc:
                _installer_log(
                    "uninstall" if uninstall_root else "install", "failed",
                    error_code=getattr(exc, "code", exc.__class__.__name__), message=str(exc),
                    trace=traceback.format_exc(limit=12),
                )
                def failed() -> None:
                    busy["value"] = False
                    status.configure(text=str(exc), fg="#ff796f")
                    primary.configure(state="normal")
                    cancel.configure(state="normal")
                window.after(0, failed)
        threading.Thread(target=worker, name="easycode-installer", daemon=True).start()

    primary.configure(command=execute)
    window.mainloop()
    return int(outcome["code"])


def main(argv: list[str] | None = None) -> int:
    supplied = list(sys.argv[1:] if argv is None else argv)
    # A windowed PyInstaller executable has no usable stdout.  argparse's
    # default help/error exits can otherwise trigger a hidden traceback dialog.
    if any(value in {"-h", "--help"} for value in supplied):
        return 0
    parser = argparse.ArgumentParser(description="EasyCode Windows Player 安装程序", add_help=False, exit_on_error=False)
    parser.add_argument("--media", default=str(_media_default()))
    parser.add_argument("--uninstall", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-desktop", action="store_true")
    try:
        args = parser.parse_args(supplied)
    except (argparse.ArgumentError, SystemExit) as exc:
        _installer_log("command_line", "failed", error_code="WIN-INSTALL-CLI-001", message=str(exc))
        return 2
    try:
        if args.quiet:
            result = uninstall(Path(args.uninstall).resolve()) if args.uninstall else install(Path(args.media).resolve(), desktop=not args.no_desktop)
            if sys.stdout is not None:
                print(json.dumps(result, ensure_ascii=False))
            return 0
        return _run_gui(Path(args.media).resolve(), Path(args.uninstall).resolve() if args.uninstall else None)
    except Exception:
        error = sys.exc_info()[1]
        _installer_log(
            "uninstall" if args.uninstall else "install", "failed",
            error_code=getattr(error, "code", error.__class__.__name__ if error else "unknown"),
            message=str(error or "unknown"), trace=traceback.format_exc(limit=12),
        )
        if sys.stderr is not None:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
