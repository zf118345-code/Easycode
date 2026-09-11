"""Versioned project triggers with bounded Windows subscriptions."""

from __future__ import annotations

import copy
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


class TriggerError(RuntimeError):
    def __init__(self, error_id: str, message: str) -> None:
        super().__init__(message)
        self.error_id = error_id


def _revision(triggers: list[dict[str, Any]]) -> str:
    payload = json.dumps(triggers, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _path(project_path: str) -> Path:
    return Path(project_path).resolve() / "automation" / "triggers.json"


def _read(project_path: str) -> dict[str, Any]:
    target = _path(project_path)
    if not target.is_file():
        return {"schema_version": 1, "revision": _revision([]), "triggers": []}
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("triggers"), list):
        raise TriggerError("trigger.configuration_corrupt", "触发器配置已损坏")
    actual = _revision(value["triggers"])
    if value.get("revision") != actual:
        raise TriggerError("trigger.configuration_corrupt", "触发器配置校验失败")
    return value


def _write(project_path: str, triggers: list[dict[str, Any]]) -> dict[str, Any]:
    target = _path(project_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    value = {"schema_version": 1, "revision": _revision(triggers), "triggers": triggers}
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return value


def _validate(raw: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(raw)
    kind = str(item.get("kind") or "")
    if kind not in {"global_hotkey", "application", "filesystem", "system"}:
        raise TriggerError("trigger.kind_invalid", "当前触发器类型不受支持")
    function_id = str(item.get("entry_function_id") or "").strip()
    if not function_id:
        raise TriggerError("trigger.entry_required", "请选择要启动的项目函数")
    config = item.get("kind_config")
    if not isinstance(config, dict):
        raise TriggerError("trigger.configuration_invalid", "触发条件配置无效")
    if kind == "global_hotkey" and not str(config.get("shortcut") or "").strip():
        raise TriggerError("trigger.shortcut_required", "请设置全局快捷键")
    if kind == "application" and (not str(config.get("process_name") or "").strip() or config.get("event") not in {"start", "exit", "focus"}):
        raise TriggerError("trigger.application_invalid", "请选择应用进程和启动、退出或获得焦点事件")
    if kind == "filesystem" and not str(config.get("path") or "").strip():
        raise TriggerError("trigger.path_required", "请选择要监视的文件或目录")
    if kind == "system" and config.get("event") not in {"system_start", "user_login"}:
        raise TriggerError("trigger.system_event_invalid", "系统事件无效")
    debounce_raw = item.get("debounce_ms", 300)
    cooldown_raw = item.get("cooldown_ms", 1000)
    item.update({
        "schema_version": 1,
        "trigger_id": str(item.get("trigger_id") or f"trigger_{uuid.uuid4().hex}"),
        "display_name": str(item.get("display_name") or "启动方式").strip()[:160],
        "enabled": bool(item.get("enabled", False)),
        "entry_function_id": function_id,
        "target_id": str(item.get("target_id") or ""),
        "debounce_ms": max(0, min(600_000, int(300 if debounce_raw is None else debounce_raw))),
        "cooldown_ms": max(0, min(86_400_000, int(1000 if cooldown_raw is None else cooldown_raw))),
        "concurrency_policy": str(item.get("concurrency_policy") or "skip_if_running"),
        "permission_requirements": list(item.get("permission_requirements") or []),
    })
    if item["concurrency_policy"] not in {"skip_if_running", "queue_one", "parallel"}:
        raise TriggerError("trigger.concurrency_invalid", "触发器并发策略无效")
    return item


class _WindowsHotkeyHost:
    MODIFIERS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "win": 0x0008}

    def __init__(self, triggers: list[dict[str, Any]], callback: Callable[[dict[str, Any]], None]) -> None:
        self.triggers = triggers
        self.callback = callback
        self.thread_id = 0
        self.thread: threading.Thread | None = None
        self.registered: dict[int, dict[str, Any]] = {}
        self.errors: list[dict[str, str]] = []
        self.ready = threading.Event()

    @classmethod
    def _parse(cls, shortcut: str) -> tuple[int, int]:
        parts = [item.strip().casefold() for item in shortcut.split("+") if item.strip()]
        modifiers = 0
        for part in parts[:-1]:
            modifiers |= cls.MODIFIERS.get(part, 0)
        key = parts[-1] if parts else ""
        if len(key) == 1:
            vk = ord(key.upper())
        elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            vk = 0x6F + int(key[1:])
        else:
            vk = {"enter": 0x0D, "space": 0x20, "tab": 0x09, "escape": 0x1B}.get(key, 0)
        if not vk:
            raise TriggerError("trigger.shortcut_invalid", f"无法识别快捷键：{shortcut}")
        return modifiers | 0x4000, vk

    def _loop(self) -> None:
        user32 = ctypes.windll.user32
        self.thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())
        for index, trigger in enumerate(self.triggers, 1):
            try:
                modifiers, vk = self._parse(str(trigger["kind_config"]["shortcut"]))
                if not user32.RegisterHotKey(None, index, modifiers, vk):
                    self.errors.append({"trigger_id": trigger["trigger_id"], "error_id": "trigger.shortcut_conflict", "message": "快捷键被系统或其他应用占用"})
                    continue
                self.registered[index] = trigger
            except TriggerError as exc:
                self.errors.append({"trigger_id": trigger["trigger_id"], "error_id": exc.error_id, "message": str(exc)})
        self.ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == 0x0312:
                trigger = self.registered.get(int(message.wParam))
                if trigger:
                    self.callback(trigger)
        for hotkey_id in self.registered:
            user32.UnregisterHotKey(None, hotkey_id)

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, daemon=True, name="easycode-trigger-hotkeys")
        self.thread.start()
        self.ready.wait(timeout=2.0)

    def stop(self) -> None:
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread:
            self.thread.join(timeout=2.0)


class TriggerRuntimeV1:
    def __init__(self, project_path: str, callback: Callable[[dict[str, Any]], dict[str, Any]], is_running: Callable[[str], bool] | None = None) -> None:
        self.project_path = project_path
        self.callback = callback
        self.is_running = is_running or (lambda _execution_id: False)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_seen: dict[str, Any] = {}
        self._last_fired: dict[str, int] = {}
        self._last_signal: dict[str, int] = {}
        self._active: dict[str, str] = {}
        self._queued: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        self._dispatch_lock = threading.RLock()
        self.events: list[dict[str, Any]] = []
        self._hotkeys: _WindowsHotkeyHost | None = None
        self._configuration_revision = ""

    def _record_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        del self.events[:-500]

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="easycode-trigger-runtime")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._hotkeys:
            self._hotkeys.stop()
        if self._thread:
            self._thread.join(timeout=2.0)

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
            if path.is_dir():
                latest = max((item.stat().st_mtime_ns for item in path.rglob("*") if item.is_file()), default=stat.st_mtime_ns)
                return latest, sum(1 for item in path.rglob("*") if item.is_file())
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def dispatch(self, trigger: dict[str, Any], evidence: dict[str, Any]) -> None:
        with self._dispatch_lock:
            now = int(time.time() * 1000)
            trigger_id = trigger["trigger_id"]
            if now - self._last_signal.get(trigger_id, 0) < trigger["debounce_ms"]:
                self._record_event({"trigger_id": trigger_id, "status": "skipped_debounce", "at_ms": now})
                return
            self._last_signal[trigger_id] = now
            active_id = self._active.get(trigger_id, "")
            if active_id and not self.is_running(active_id):
                self._active.pop(trigger_id, None)
            if trigger["concurrency_policy"] == "skip_if_running" and trigger_id in self._active:
                self._record_event({"trigger_id": trigger_id, "status": "skipped_running", "at_ms": now})
                return
            if trigger["concurrency_policy"] == "queue_one" and trigger_id in self._active:
                self._queued[trigger_id] = (copy.deepcopy(trigger), copy.deepcopy(evidence))
                self._record_event({"trigger_id": trigger_id, "status": "queued_once", "at_ms": now})
                return
            if now - self._last_fired.get(trigger_id, 0) < trigger["cooldown_ms"]:
                self._record_event({"trigger_id": trigger_id, "status": "skipped_cooldown", "at_ms": now})
                return
        try:
            result = self.callback(trigger)
            execution_id = str(result.get("execution_id") or "")
            if execution_id and trigger["concurrency_policy"] != "parallel":
                self._active[trigger_id] = execution_id
            self._last_fired[trigger_id] = now
            self._record_event({"trigger_id": trigger_id, "status": "started", "execution_id": execution_id, "evidence": evidence, "at_ms": now})
        except Exception as exc:
            self._record_event({"trigger_id": trigger_id, "status": "failed", "message": str(exc), "at_ms": now})

    def _loop(self) -> None:
        fired_system: set[str] = set()
        while not self._stop.wait(0.5):
            with self._dispatch_lock:
                ready_queue = []
                for trigger_id, (queued_trigger, queued_evidence) in list(self._queued.items()):
                    active_id = self._active.get(trigger_id, "")
                    if active_id and self.is_running(active_id):
                        continue
                    self._active.pop(trigger_id, None)
                    self._queued.pop(trigger_id, None)
                    self._last_signal.pop(trigger_id, None)
                    ready_queue.append((queued_trigger, queued_evidence))
            for queued_trigger, queued_evidence in ready_queue:
                self.dispatch(queued_trigger, {**queued_evidence, "queued": True})
            try:
                configuration = _read(self.project_path)
                triggers = [item for item in configuration["triggers"] if item.get("enabled")]
            except Exception:
                continue
            if os.name == "nt" and configuration["revision"] != self._configuration_revision:
                if self._hotkeys:
                    self._hotkeys.stop()
                hotkeys = [item for item in triggers if item["kind"] == "global_hotkey"]
                self._hotkeys = _WindowsHotkeyHost(
                    hotkeys,
                    lambda trigger: self.dispatch(trigger, {"kind": "global_hotkey", "shortcut": trigger["kind_config"]["shortcut"]}),
                )
                self._hotkeys.start()
                self._configuration_revision = configuration["revision"]
                for error in self._hotkeys.errors:
                    self._record_event({**error, "status": "failed_registration", "at_ms": int(time.time() * 1000)})
            processes: set[str] = set()
            foreground = ""
            if any(item["kind"] == "application" for item in triggers):
                try:
                    import psutil
                    processes = {str(proc.info.get("name") or "").casefold() for proc in psutil.process_iter(["name"])}
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    pid = ctypes.c_ulong()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    foreground = str(psutil.Process(pid.value).name() or "").casefold() if pid.value else ""
                except Exception:
                    pass
            for trigger in triggers:
                trigger_id, kind, config = trigger["trigger_id"], trigger["kind"], trigger["kind_config"]
                if kind == "filesystem":
                    watched = Path(str(config["path"])).expanduser()
                    signature = self._file_signature(watched)
                    previous = self._last_seen.setdefault(trigger_id, signature)
                    if signature != previous:
                        self._last_seen[trigger_id] = signature
                        self.dispatch(trigger, {"kind": "filesystem", "path": str(watched)})
                elif kind == "application":
                    name = str(config["process_name"]).casefold()
                    current = foreground == name if config["event"] == "focus" else name in processes
                    previous = bool(self._last_seen.setdefault(trigger_id, current))
                    event_matches = (config["event"] in {"start", "focus"} and current and not previous) or (config["event"] == "exit" and previous and not current)
                    self._last_seen[trigger_id] = current
                    if event_matches:
                        self.dispatch(trigger, {"kind": "application", "process_name": name, "event": config["event"]})
                elif kind == "system" and trigger_id not in fired_system:
                    fired_system.add(trigger_id)
                    self.dispatch(trigger, {"kind": "system", "event": config["event"]})


class TriggerServiceV1:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runtimes: dict[str, TriggerRuntimeV1] = {}

    def configuration(self, project_path: str) -> dict[str, Any]:
        return _read(project_path)

    def save(self, project_path: str, expected_revision: str, raw: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = _read(project_path)
            if current["revision"] != expected_revision:
                raise TriggerError("trigger.revision_conflict", "触发器配置已变化，请重新加载")
            item = _validate(raw)
            triggers = [value for value in current["triggers"] if value["trigger_id"] != item["trigger_id"]]
            if item["kind"] == "global_hotkey" and item["enabled"]:
                shortcut = str(item["kind_config"]["shortcut"]).casefold().replace(" ", "")
                if any(value.get("enabled") and value["kind"] == "global_hotkey" and str(value["kind_config"].get("shortcut") or "").casefold().replace(" ", "") == shortcut for value in triggers):
                    raise TriggerError("trigger.shortcut_conflict", "该全局快捷键已被本项目其他启动方式占用")
            triggers.append(item)
            return _write(project_path, triggers)

    def delete(self, project_path: str, expected_revision: str, trigger_id: str) -> dict[str, Any]:
        with self._lock:
            current = _read(project_path)
            if current["revision"] != expected_revision:
                raise TriggerError("trigger.revision_conflict", "触发器配置已变化，请重新加载")
            triggers = [item for item in current["triggers"] if item["trigger_id"] != trigger_id]
            if len(triggers) == len(current["triggers"]):
                raise TriggerError("trigger.not_found", "启动方式不存在")
            return _write(project_path, triggers)

    def activate(self, project_path: str, callback: Callable[[dict[str, Any]], dict[str, Any]], is_running: Callable[[str], bool] | None = None) -> TriggerRuntimeV1:
        self.deactivate(project_path)
        runtime = TriggerRuntimeV1(project_path, callback, is_running)
        self._runtimes[str(Path(project_path).resolve())] = runtime
        runtime.start()
        return runtime

    def deactivate(self, project_path: str) -> None:
        runtime = self._runtimes.pop(str(Path(project_path).resolve()), None)
        if runtime:
            runtime.stop()

    def events(self, project_path: str) -> list[dict[str, Any]]:
        runtime = self._runtimes.get(str(Path(project_path).resolve()))
        return copy.deepcopy(runtime.events if runtime else [])


trigger_service_v1 = TriggerServiceV1()

__all__ = ["TriggerError", "TriggerRuntimeV1", "TriggerServiceV1", "trigger_service_v1"]
