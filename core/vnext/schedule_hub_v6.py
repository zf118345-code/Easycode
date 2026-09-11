"""Per-user Windows Player Hub for durable local schedules.

This module is a host control plane.  It owns no ProgramDocument functions and
never edits ECIR.  It connects the durable schedule core to the exact same
signed Player bundle/runtime path used by an interactive Player, and exposes
Windows Task Scheduler only as a wake mechanism for one current-user Agent.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
from ctypes import wintypes
import getpass
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from xml.sax.saxutils import escape

from .player_bundle import PlayerBundleError
from .lan_control_v6 import LanControlPlaneV6
from .message_runtime_v6 import MessageRuntimeV6, default_message_database_path
from .lan_schedule_v6 import (
    LanDispatchRouterV6,
    LanScheduleInboundV6,
    LanScheduleReferenceResolverV6,
)
from .runtime import RuntimeFailure, vnext_runtime
from .schedule_registry_v6 import InstalledProductRegistryV6, RuntimeBinding, default_hub_root
from .schedule_v6 import (
    LocalDispatchRequest,
    ScheduleError,
    ScheduleServiceV6,
    SQLiteLocalDispatchGateway,
)


# ``schtasks.exe`` cannot create a missing Task Scheduler folder.  Keep the
# single task at the root with a namespaced name so first install is atomic.
HUB_TASK_NAME = r"\EasyCode.PlayerHub"
_ACTIVE = frozenset({"accepted", "starting", "running", "paused", "stopping"})
_TERMINAL_RUNTIME = frozenset({"completed", "failed", "cancelled"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _windows_error_message(code: int) -> str:
    with contextlib.suppress(Exception):
        return ctypes.FormatError(code).strip()
    return f"Windows error {code}"


class InteractiveSessionProbe:
    """Read current-user desktop availability without attempting input."""

    def inspect(self) -> dict[str, Any]:
        if os.name != "nt":
            return {
                "platform": sys.platform,
                "interactive_session": False,
                "desktop_available": False,
                "desktop_name": "",
                "state": "unsupported_host",
                "error_id": "schedule.windows_host_required",
            }
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        kernel32.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
        kernel32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.SwitchDesktop.argtypes = [wintypes.HANDLE]
        user32.SwitchDesktop.restype = wintypes.BOOL
        user32.CloseDesktop.argtypes = [wintypes.HANDLE]
        user32.CloseDesktop.restype = wintypes.BOOL
        user32.GetUserObjectInformationW.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetUserObjectInformationW.restype = wintypes.BOOL
        process_session = wintypes.DWORD(0)
        if not kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(process_session)):
            code = int(kernel32.GetLastError())
            return {
                "platform": "windows",
                "interactive_session": False,
                "desktop_available": False,
                "desktop_name": "",
                "state": "session_query_failed",
                "error_id": "schedule.interactive_session_unavailable",
                "message": _windows_error_message(code),
            }
        active_session = int(kernel32.WTSGetActiveConsoleSessionId())
        interactive = active_session != 0xFFFFFFFF and int(process_session.value) == active_session
        # DESKTOP_SWITCHDESKTOP is intentionally read-only here.  SwitchDesktop
        # reports false for an invisible/secure desktop (lock screen or UAC).
        desktop = user32.OpenInputDesktop(0, False, 0x0100)
        desktop_available = False
        desktop_name = ""
        if desktop:
            try:
                needed = wintypes.DWORD(0)
                user32.GetUserObjectInformationW(desktop, 2, None, 0, ctypes.byref(needed))
                if needed.value:
                    buffer = ctypes.create_unicode_buffer(
                        max(1, needed.value // ctypes.sizeof(ctypes.c_wchar) + 1)
                    )
                    if user32.GetUserObjectInformationW(
                        desktop, 2, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
                    ):
                        desktop_name = str(buffer.value)
                desktop_available = bool(user32.SwitchDesktop(desktop))
            finally:
                user32.CloseDesktop(desktop)
        state = "ready" if interactive and desktop_available else (
            "secure_or_locked_desktop" if interactive else "different_or_missing_session"
        )
        return {
            "platform": "windows",
            "process_session_id": int(process_session.value),
            "active_console_session_id": active_session,
            "interactive_session": interactive,
            "desktop_available": desktop_available,
            "desktop_name": desktop_name,
            "state": state,
            "error_id": "" if state == "ready" else "schedule.interactive_desktop_unavailable",
        }

    def require_for_target(self, target_type: str) -> dict[str, Any]:
        # ADB and no-target jobs can run while Windows is locked.  Windows
        # desktop/UIA/physical input must never be sent into a secure desktop.
        if target_type not in {"windows", "windows_desktop"}:
            return self.inspect()
        state = self.inspect()
        if not state.get("interactive_session") or not state.get("desktop_available"):
            raise ScheduleError(
                "Windows 当前用户桌面已锁定、处于 UAC 安全桌面或不可交互",
                error_id="schedule.interactive_desktop_unavailable",
                transient=True,
                action="unlock_windows_session",
                diagnostics=[{"desktop_state": str(state.get("state") or "unknown")}],
            )
        return state


@dataclass(slots=True)
class _MonitoredRun:
    dispatch_id: str
    run_id: str
    instance_id: str
    thread: threading.Thread


class WindowsTaskSchedulerBridge:
    """Install/update one per-user Task Scheduler wake entry, never one per plan."""

    def __init__(self, task_name: str = HUB_TASK_NAME) -> None:
        self.task_name = str(task_name)

    @staticmethod
    def _command() -> tuple[str, str, str]:
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
            return str(executable), "--player-hub-agent", str(executable.parent)
        project_root = Path(__file__).resolve().parents[2]
        return (
            str(Path(sys.executable).resolve()),
            "-m core.vnext.schedule_hub_v6 agent",
            str(project_root),
        )

    def _xml(self, next_wake: datetime | None = None) -> str:
        executable, arguments, working_directory = self._command()
        next_trigger = ""
        if next_wake is not None:
            boundary = next_wake.astimezone().isoformat(timespec="seconds")
            next_trigger = (
                "<TimeTrigger><StartBoundary>" + escape(boundary) +
                "</StartBoundary><Enabled>true</Enabled></TimeTrigger>"
            )
        user = escape(getpass.getuser())
        return (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            '<RegistrationInfo><Description>EasyCode 当前用户 Player Hub；只负责计划唤醒与普通任务派发。</Description></RegistrationInfo>'
            '<Triggers><LogonTrigger><Enabled>true</Enabled><UserId>' + user +
            '</UserId></LogonTrigger>' + next_trigger + '</Triggers>'
            '<Principals><Principal id="Author"><UserId>' + user +
            '</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
            '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'
            '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
            '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'
            '<StartWhenAvailable>true</StartWhenAvailable><WakeToRun>true</WakeToRun>'
            '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'
            '<RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure></Settings>'
            '<Actions Context="Author"><Exec><Command>' + escape(executable) +
            '</Command><Arguments>' + escape(arguments) + '</Arguments><WorkingDirectory>' +
            escape(working_directory) + '</WorkingDirectory></Exec></Actions></Task>'
        )

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        if os.name != "nt":
            raise ScheduleError(
                "Windows Task Scheduler 只在 Windows 宿主可用",
                error_id="schedule.windows_task_scheduler_unavailable",
            )
        try:
            return subprocess.run(
                ["schtasks.exe", *arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ScheduleError(
                "Windows Task Scheduler 调用失败",
                error_id="schedule.windows_task_scheduler_failed",
                action="check_windows_permissions",
            ) from exc

    def status(self) -> dict[str, Any]:
        if os.name != "nt":
            return {"available": False, "installed": False, "state": "unsupported_host"}
        result = self._run(["/Query", "/TN", self.task_name, "/FO", "LIST", "/V"])
        if result.returncode != 0:
            return {"available": True, "installed": False, "state": "not_installed"}
        return {"available": True, "installed": True, "state": "installed"}

    def install_or_update(self, next_wake: datetime | None = None) -> dict[str, Any]:
        previous: bytes | None = None
        if os.name == "nt":
            try:
                queried = subprocess.run(
                    ["schtasks.exe", "/Query", "/TN", self.task_name, "/XML"],
                    capture_output=True,
                    timeout=30,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if queried.returncode == 0 and queried.stdout:
                    previous = bytes(queried.stdout)
            except (OSError, subprocess.SubprocessError):
                previous = None
        temporary = Path(tempfile.gettempdir()) / f"easycode-player-hub-{os.getpid()}.xml"
        backup = temporary.with_suffix(".previous.xml")
        try:
            temporary.write_text(self._xml(next_wake), encoding="utf-16")
            if previous:
                backup.write_bytes(previous)
            result = self._run(["/Create", "/TN", self.task_name, "/XML", str(temporary), "/F"])
            if result.returncode != 0:
                if previous and backup.is_file():
                    self._run(["/Create", "/TN", self.task_name, "/XML", str(backup), "/F"])
                raise ScheduleError(
                    "无法安装当前用户 Player Hub 唤醒任务",
                    error_id="schedule.windows_task_install_failed",
                    action="check_windows_permissions",
                    diagnostics=[{"exit_code": result.returncode}],
                )
            return {"ok": True, "task_name": self.task_name, "state": "installed"}
        finally:
            temporary.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)

    def uninstall(self) -> dict[str, Any]:
        current = self.status()
        if not current.get("installed"):
            return {"ok": True, "task_name": self.task_name, "state": "not_installed"}
        result = self._run(["/Delete", "/TN", self.task_name, "/F"])
        if result.returncode != 0:
            raise ScheduleError(
                "无法卸载 Player Hub 唤醒任务",
                error_id="schedule.windows_task_uninstall_failed",
                action="check_windows_permissions",
            )
        return {"ok": True, "task_name": self.task_name, "state": "not_installed"}


class _HubOwnership:
    """A Windows named mutex prevents two Agent loops for the same user root."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._handle: Any = None

    def acquire(self) -> None:
        if os.name != "nt":
            return
        digest = hashlib.sha256(str(self._root).casefold().encode("utf-8")).hexdigest()[:24]
        name = f"Local\\EasyCode.PlayerHub.v6.{digest}"
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ScheduleError("无法创建 Player Hub 所有者互斥量", error_id="schedule.agent_lock_failed")
        if int(ctypes.windll.kernel32.GetLastError()) == 183:
            kernel32.CloseHandle(handle)
            raise ScheduleError(
                "当前 Windows 用户已经有一个 Player Hub Agent 在运行",
                error_id="schedule.agent_already_running",
                action="open_player_hub",
            )
        self._handle = handle

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


class PlayerHubV6:
    """Installed-product registry, scheduler, dispatcher and run monitor."""

    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
        *,
        session_probe: InteractiveSessionProbe | None = None,
        task_scheduler: WindowsTaskSchedulerBridge | None = None,
        lan_control: LanControlPlaneV6 | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve() if root else default_hub_root()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ScheduleError(
                "Player Hub 数据目录不可写",
                error_id="schedule.registry_database_unavailable",
                action="choose_data_directory",
            ) from exc
        self.registry = InstalledProductRegistryV6(
            self.root / "registry.sqlite3", data_root=self.root / "data"
        )
        lan_port = int(str(os.environ.get("EASYCODE_LAN_PORT") or "41663"))
        self.lan_control = lan_control or LanControlPlaneV6(
            self.root / "lan", port=lan_port
        )
        self.registry.bind_host_identity(self.lan_control.identity.host_id)
        message_database = (
            default_message_database_path()
            if self.root == default_hub_root()
            else self.root / "messages.sqlite3"
        )
        self.message_runtime = MessageRuntimeV6(
            message_database, lan_control=self.lan_control
        )
        self.session_probe = session_probe or InteractiveSessionProbe()
        self.task_scheduler = task_scheduler or WindowsTaskSchedulerBridge()
        self._monitor_lock = threading.RLock()
        self._monitors: dict[str, _MonitoredRun] = {}
        self._closed = False
        self.gateway = SQLiteLocalDispatchGateway(
            self.root / "dispatch-admissions.sqlite3", launcher=self._launch
        )
        self._lan_inbound = LanScheduleInboundV6(self.lan_control, self.gateway)
        resolver = LanScheduleReferenceResolverV6(
            self.registry, self.registry.host_id, self.lan_control
        )
        dispatcher = LanDispatchRouterV6(
            self.registry.host_id, self.gateway, self.lan_control
        )
        self.lan_control.set_status_provider(self._lan_status_catalog)
        schedule_override = str(os.environ.get("EASYCODE_VNEXT_SCHEDULE_DATABASE") or "").strip()
        self.schedule = ScheduleServiceV6(
            Path(schedule_override).expanduser().resolve() if schedule_override else self.root / "schedules.sqlite3",
            resolver=resolver,
            dispatcher=dispatcher,
        )

    def _lan_status_catalog(self) -> dict[str, Any]:
        instances: list[dict[str, Any]] = []
        for item in self.registry.list_instances(include_profiles=True):
            installation = dict(item.get("installation") or {})
            product_id = str(item.get("product_id") or installation.get("product_id") or "")
            release_id = str(installation.get("release_id") or "")
            profiles = [
                {**dict(profile), "release_id": release_id}
                for profile in (item.get("profiles") or [])
                if isinstance(profile, Mapping)
            ]
            instances.append(
                {
                    "project_namespace": product_id,
                    "host_id": self.registry.host_id,
                    "instance_id": str(item.get("instance_id") or ""),
                    "display_name": str(item.get("display_name") or ""),
                    "product_id": product_id,
                    "product_name": str(installation.get("display_name") or product_id),
                    "release_id": release_id,
                    "profiles": profiles,
                    "status": str(item.get("status") or "unknown"),
                }
            )
        known = {
            (str(item["project_namespace"]), str(item["instance_id"]))
            for item in instances
        }
        instances.extend(
            item
            for item in self.message_runtime.catalog_instances()
            if (str(item["project_namespace"]), str(item["instance_id"])) not in known
        )
        return {
            "host_id": self.registry.host_id,
            "instances": instances,
            "observed_at": _now(),
        }

    @staticmethod
    def _target_type(binding: RuntimeBinding) -> str:
        target_id = str(binding.profile.get("target_id") or "")
        if not target_id:
            return "none"
        bootstrap = binding.manager.bootstrap()
        target = next(
            (
                item for item in (bootstrap.get("targets") or [])
                if str(item.get("target_id") or "") == target_id
            ),
            None,
        )
        return str((target or {}).get("type") or "unknown")

    def _launch(self, request: LocalDispatchRequest, run_id: str) -> None:
        binding = self.registry.resolve_runtime(request.as_dict())
        profile_revision = int(binding.profile.get("revision") or 0)
        target_id = str(binding.profile.get("target_id") or "")
        target_type = self._target_type(binding)
        self.session_probe.require_for_target(target_type)
        payload = {
            "profile_id": str(binding.profile["profile_id"]),
            "profile_revision": profile_revision,
            "target_id": target_id,
            "message_instance_id": str(binding.instance["instance_id"]),
        }
        try:
            dangerous = binding.manager.dangerous_operation_requirements(payload).get("operations") or []
            if dangerous:
                raise ScheduleError(
                    "该运行方案包含需要终端用户逐次确认的危险操作，不能无人值守启动",
                    error_id="schedule.dangerous_confirmation_required",
                    action="run_interactively",
                    diagnostics=[{"operation_count": len(dangerous)}],
                )
            preflight = binding.manager.preflight(target_id)
            if not preflight.get("ready"):
                failed = next(
                    (item for item in (preflight.get("checks") or []) if item.get("status") == "fail"),
                    {},
                )
                raise ScheduleError(
                    str(failed.get("message") or "操作目标或权限预检失败"),
                    error_id="schedule.target_preflight_failed",
                    transient=True,
                    action="check_target",
                )
            result = binding.manager.start(payload, execution_id=run_id)
        except ScheduleError:
            raise
        except (PlayerBundleError, RuntimeFailure, ValueError) as exc:
            error_id = str(getattr(exc, "error_id", "") or "schedule.execution_start_failed")
            transient = error_id in {
                "target.busy", "target.missing", "target.driver_unavailable",
                "schedule.target_preflight_failed",
            }
            raise ScheduleError(
                str(exc),
                error_id=error_id,
                transient=transient,
                action="check_target" if transient else "open_player_profiles",
            ) from exc
        actual_id = str(result.get("execution_id") or "")
        if actual_id != run_id:
            raise ScheduleError(
                "普通 Runtime 未保留计划派发的稳定运行身份",
                error_id="schedule.execution_identity_mismatch",
            )
        thread = threading.Thread(
            target=self._monitor_run,
            args=(request.dispatch_id, run_id, request.instance_id),
            name=f"player-hub-run-{run_id[-8:]}",
            daemon=True,
        )
        with self._monitor_lock:
            self._monitors[run_id] = _MonitoredRun(
                request.dispatch_id, run_id, request.instance_id, thread
            )
        thread.start()

    def _monitor_run(self, dispatch_id: str, run_id: str, instance_id: str) -> None:
        cursor = 0
        last_status = ""
        try:
            # The launcher returns before the gateway/scheduler writes its ACK.
            # Wait for that transaction before publishing ordinary run states.
            for _ in range(100):
                try:
                    row = self.schedule.get_dispatch(dispatch_id)
                    if str(row.get("run_id") or "") == run_id:
                        break
                except ScheduleError:
                    pass
                time.sleep(0.02)
            while not self._closed:
                snapshot = vnext_runtime.wait_snapshot(run_id, cursor, 2.0)
                cursor = int(snapshot.get("event_cursor") or cursor)
                runtime_status = str(snapshot.get("status") or "")
                schedule_status = {
                    "queued": "starting",
                    "running": "running",
                    "paused": "paused",
                    "completed": "completed",
                    "failed": "failed",
                    "cancelled": "stopped",
                }.get(runtime_status, "running")
                if schedule_status != last_status:
                    try:
                        self.schedule.record_run_status(
                            dispatch_id,
                            run_id,
                            schedule_status,
                            error_id=str(snapshot.get("error_id") or ""),
                            error_message=str(snapshot.get("error") or ""),
                        )
                    except ScheduleError as exc:
                        # A transient ACK race is retried; identity conflicts are
                        # preserved in the schedule diagnostics by the core.
                        if exc.error_id not in {
                            "schedule.run_identity_mismatch", "schedule.dispatch_not_found"
                        }:
                            raise
                    last_status = schedule_status
                if runtime_status in _TERMINAL_RUNTIME:
                    return
        except (RuntimeFailure, ScheduleError) as exc:
            with contextlib.suppress(ScheduleError):
                row = self.schedule.get_dispatch(dispatch_id)
                if str(row.get("run_id") or "") == run_id and str(row.get("status") or "") not in {
                    "completed", "failed", "stopped", "rejected", "skipped", "expired"
                }:
                    self.schedule.record_run_status(
                        dispatch_id,
                        run_id,
                        "failed",
                        error_id=str(getattr(exc, "error_id", "schedule.runtime_monitor_failed")),
                        error_message=str(exc),
                    )
        finally:
            with self._monitor_lock:
                self._monitors.pop(run_id, None)

    def recover_after_restart(self) -> dict[str, Any]:
        failed = 0
        for row in self.schedule.list_dispatches(limit=5_000):
            if str(row.get("status") or "") not in _ACTIVE or not row.get("run_id"):
                continue
            with contextlib.suppress(ScheduleError):
                self.schedule.record_run_status(
                    str(row["dispatch_id"]),
                    str(row["run_id"]),
                    "failed",
                    error_id="schedule.host_restarted",
                    error_message="Player Hub 重启；旧 GUI 调用栈不会自动恢复",
                )
                failed += 1
        recovered = self.gateway.recover_host_restart()
        return {"failed_interrupted_runs": failed, "reset_admissions": recovered}

    def run_once(self, *, recovery: bool = False) -> dict[str, Any]:
        occurrences = self.schedule.process_due(
            trigger_source="recovery" if recovery else "timer"
        )
        dispatched = self.schedule.pump()
        return {
            "checked_at": _now(),
            "occurrences": occurrences,
            "dispatches": dispatched,
        }

    def status(self) -> dict[str, Any]:
        try:
            installations = self.registry.list_installations(include_profiles=True)
            registry_ready = True
            registry_error = None
        except ScheduleError as exc:
            installations = []
            registry_ready = False
            registry_error = {"error_id": exc.error_id, "message": str(exc)}
        with self._monitor_lock:
            active_runs = len(self._monitors)
        lan_status = self.lan_control.status()
        authorized_remote_start = sum(
            1
            for peer in self.lan_control.directory.list_peers()
            if bool(peer["remote_permissions"].get("remote_start"))
        )
        return {
            "available": True,
            "ready": registry_ready,
            "host_id": self.registry.host_id,
            "owner_scope": "current_windows_user",
            "checked_at": _now(),
            "installations": installations,
            "active_run_count": active_runs,
            "interactive_session": self.session_probe.inspect(),
            "wake_agent": self.task_scheduler.status(),
            "remote_dispatch": {
                "available": bool(lan_status.get("running")) and authorized_remote_start > 0,
                "state": (
                    "ready"
                    if bool(lan_status.get("running")) and authorized_remote_start > 0
                    else "listener_stopped"
                    if not bool(lan_status.get("running"))
                    else "no_authorized_device"
                ),
                "error_id": (
                    ""
                    if bool(lan_status.get("running")) and authorized_remote_start > 0
                    else "schedule.remote_dispatch_unavailable"
                ),
                "listener": lan_status,
                "authorized_peer_count": authorized_remote_start,
            },
            "android_system_scheduler": {
                "available": False,
                "state": "not_implemented",
                "error_id": "schedule.android_scheduler_unavailable",
            },
            "registry_error": registry_error,
        }

    def next_due(self) -> datetime | None:
        values = [
            str(item.get("next_due_at") or "")
            for item in self.schedule.list_plans()
            if item.get("enabled") and item.get("next_due_at")
        ]
        if not values:
            return None
        return min(datetime.fromisoformat(item.replace("Z", "+00:00")) for item in values)

    def refresh_wake_registration(self) -> dict[str, Any]:
        return self.task_scheduler.install_or_update(self.next_due())

    def refresh_wake_if_installed(self) -> dict[str, Any]:
        state = self.task_scheduler.status()
        if not state.get("installed"):
            return {"ok": True, "state": "not_installed"}
        return self.refresh_wake_registration()

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stopper = stop_event or threading.Event()
        ownership = _HubOwnership(self.root)
        ownership.acquire()
        try:
            self.recover_after_restart()
            self.run_once(recovery=True)
            with contextlib.suppress(ScheduleError):
                self.refresh_wake_if_installed()
            while not stopper.is_set():
                due = self.next_due()
                seconds = 60.0
                if due is not None:
                    seconds = max(0.1, min(60.0, (due - datetime.now(timezone.utc)).total_seconds()))
                if stopper.wait(seconds):
                    break
                self.run_once()
                with contextlib.suppress(ScheduleError):
                    self.refresh_wake_if_installed()
        finally:
            ownership.release()

    def shutdown(self) -> None:
        self._closed = True
        self.lan_control.stop()
        self.registry.shutdown()


_default_lock = threading.Lock()
_default_hub: PlayerHubV6 | None = None


def get_player_hub_v6() -> PlayerHubV6:
    global _default_hub
    schedule_override = str(os.environ.get("EASYCODE_VNEXT_SCHEDULE_DATABASE") or "").strip()
    explicit_root = str(os.environ.get("EASYCODE_PLAYER_HUB_DATA_DIR") or "").strip()
    root = (
        Path(schedule_override).expanduser().resolve().parent
        if schedule_override and not explicit_root
        else default_hub_root()
    )
    with _default_lock:
        if _default_hub is None or _default_hub.root != root:
            if _default_hub is not None:
                _default_hub.shutdown()
            _default_hub = PlayerHubV6(root)
        return _default_hub


def reset_player_hub_v6_for_tests() -> None:
    global _default_hub
    with _default_lock:
        if _default_hub is not None:
            _default_hub.shutdown()
        _default_hub = None


def shutdown_player_hub_v6() -> None:
    """Shutdown the singleton only when it was actually initialized."""

    reset_player_hub_v6_for_tests()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EasyCode 当前用户 Player Hub Agent")
    parser.add_argument("command", nargs="?", default="agent", choices=["agent", "once", "status"])
    args = parser.parse_args(argv)
    hub = get_player_hub_v6()
    try:
        if args.command == "status":
            print(json.dumps(hub.status(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "once":
            print(json.dumps(hub.run_once(recovery=True), ensure_ascii=False, indent=2))
            return 0
        hub.run_forever()
        return 0
    except ScheduleError as exc:
        print(json.dumps({"error_id": exc.error_id, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        hub.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
