"""Reviewed operation recording sessions that commit one ProgramDocument edit."""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .program_types import new_stable_id


class OperationRecordingError(RuntimeError):
    def __init__(self, error_id: str, message: str) -> None:
        super().__init__(message)
        self.error_id = error_id


SUPPORTED_EVENTS = {
    "click", "double_click", "right_click", "text_input", "key", "shortcut",
    "scroll", "drag", "application_start", "window_activate", "wait",
}


def _value(kind: str, **payload: Any) -> dict[str, Any]:
    return {"value_id": new_stable_id("value"), "kind": kind, **payload}


def _selector_value(selector: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}
    prefix = "control_selector.field."
    for name, value in selector.items():
        if not name.startswith(prefix):
            continue
        if isinstance(value, str):
            fields[name] = _value("string", value=value)
        elif isinstance(value, int) and not isinstance(value, bool):
            fields[name] = _value("int64", value=value)
        elif name.endswith("rect") and isinstance(value, dict):
            fields[name] = _value(
                "rect", x=value.get("x", 0), y=value.get("y", 0),
                width=max(0, value.get("width", 0)), height=max(0, value.get("height", 0)),
            )
        elif name.endswith("path") and isinstance(value, list) and all(isinstance(item, int) for item in value):
            fields[name] = {
                "value_id": new_stable_id("value"), "kind": "list", "item_type": "int64",
                "items": [_value("int64", value=item) for item in value],
            }
        elif isinstance(value, (dict, list)):
            fields[name] = _value("json", payload=value)
    return {
        "value_id": new_stable_id("value"), "kind": "record",
        "record_type": "control_selector", "fields": fields,
    }


def _location(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent_statement_id": raw.get("parent_statement_id"),
        "block": str(raw.get("block") or "root"),
        "clause_id": raw.get("clause_id"),
        "before_statement_id": raw.get("before_statement_id"),
    }


class OperationRecordingServiceV1:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._hosts: dict[str, Any] = {}

    def attach_host(self, session_id: str, host: Any) -> None:
        with self._lock:
            self._hosts[session_id] = host

    def _stop_host(self, session_id: str) -> None:
        host = self._hosts.pop(session_id, None)
        if host is not None:
            threading.Thread(target=host.stop, daemon=True, name="operation-recorder-stop").start()

    @staticmethod
    def _directory(project_path: str) -> Path:
        return Path(project_path).resolve() / ".easycode" / "recovery" / "operation-recording"

    def _save(self, project_path: str, session: dict[str, Any]) -> None:
        directory = self._directory(project_path)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{session['session_id']}.json"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def start(
        self, project_path: str, *, function_id: str, expected_revision: str,
        target_id: str, target_type: str, location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if any(item["status"] in {"preparing", "active", "stopping"} for item in self._sessions.values()):
                raise OperationRecordingError("operation_recording.already_active", "已有操作录制正在进行")
            now = int(time.time() * 1000)
            session = {
                "schema_version": 1,
                "session_id": f"operation_recording_{uuid.uuid4().hex}",
                "status": "active",
                "function_id": function_id,
                "expected_revision": expected_revision,
                "target_id": target_id,
                "target_type": target_type,
                "location": _location(location or {}),
                "created_at_ms": now,
                "updated_at_ms": now,
                "events": [],
                "unrecorded_intervals": [],
                "last_error": "",
            }
            self._sessions[session["session_id"]] = session
            self._save(project_path, session)
            return copy.deepcopy(session)

    def append(self, project_path: str, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session["status"] != "active":
                raise OperationRecordingError("operation_recording.not_active", "操作录制会话当前不可写入")
            kind = str(event.get("kind") or "")
            if kind not in SUPPORTED_EVENTS:
                session["unrecorded_intervals"].append({"reason": f"unsupported:{kind or 'empty'}", "at_ms": int(time.time() * 1000)})
                self._save(project_path, session)
                raise OperationRecordingError("operation_recording.event_unsupported", "该输入无法可靠转换为结构化语句")
            occurred = int(event.get("occurred_at_ms") or time.time() * 1000)
            previous = session["events"][-1]["occurred_at_ms"] if session["events"] else session["created_at_ms"]
            item = {
                **copy.deepcopy(event), "event_id": f"recorded_event_{uuid.uuid4().hex}",
                "kind": kind, "occurred_at_ms": occurred, "delay_ms": max(0, occurred - previous),
            }
            session["events"].append(item)
            session["updated_at_ms"] = int(time.time() * 1000)
            self._save(project_path, session)
            return copy.deepcopy(item)

    def stop(self, project_path: str, session_id: str, *, reason: str = "user") -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise OperationRecordingError("operation_recording.not_found", "操作录制草稿不存在")
            if session["status"] == "active":
                self._stop_host(session_id)
                session["status"] = "review"
                session["stop_reason"] = reason
                session["updated_at_ms"] = int(time.time() * 1000)
                self._save(project_path, session)
            return self.review(project_path, session_id)

    def review(self, project_path: str, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                path = self._directory(project_path) / f"{session_id}.json"
                if not path.is_file():
                    raise OperationRecordingError("operation_recording.not_found", "操作录制草稿不存在")
                session = json.loads(path.read_text(encoding="utf-8"))
                self._sessions[session_id] = session
            events: list[dict[str, Any]] = []
            for source in session["events"]:
                item = copy.deepcopy(source)
                item["enabled"] = True
                item["needs_attention"] = False
                item["suggestions"] = []
                if item["kind"] in {"click", "double_click", "right_click"} and not item.get("selector"):
                    item["suggestions"] = ["可替换为等待图片并点击", "可在动作前增加等待文字"]
                if item["kind"] == "text_input" and events and events[-1]["kind"] == "text_input" and item["delay_ms"] <= 600:
                    events[-1]["text"] = str(events[-1].get("text") or "") + str(item.get("text") or "")
                    continue
                events.append(item)
            return {**copy.deepcopy(session), "review_events": events}

    @staticmethod
    def commands(review_events: list[dict[str, Any]], location: dict[str, Any]) -> list[dict[str, Any]]:
        commands: list[dict[str, Any]] = []
        for event in review_events:
            if not event.get("enabled", True):
                continue
            delay = int(event.get("delay_ms") or 0)
            if delay >= 400:
                commands.append({"kind": "insert_call", "function_id": "official.wait.duration", "arguments": {"official.wait.duration.parameter.duration": _value("duration", milliseconds=delay)}, "location": location})
            kind = event["kind"]
            if kind in {"click", "double_click", "right_click"}:
                if isinstance(event.get("selector"), dict):
                    commands.append({"kind": "insert_call", "function_id": "official.control.click_selector", "arguments": {"official.control.click_selector.parameter.selector": _selector_value(event["selector"])}, "location": location})
                else:
                    point = event.get("point") or [0, 0]
                    commands.append({"kind": "insert_call", "function_id": "official.input.click", "arguments": {
                        "official.input.click.parameter.position": _value("point", x=point[0], y=point[1]),
                        "official.input.click.parameter.button": _value("string", value="secondary" if kind == "right_click" else "primary"),
                        "official.input.click.parameter.count": _value("int64", value=2 if kind == "double_click" else 1),
                    }, "location": location})
            elif kind == "text_input":
                commands.append({"kind": "insert_call", "function_id": "official.input.type_text", "arguments": {"official.input.type_text.parameter.content": _value("string", value=str(event.get("text") or ""))}, "location": location})
            elif kind in {"key", "shortcut"}:
                keys = [part.strip() for part in str(event.get("key") or "").replace("+", ",").split(",") if part.strip()]
                key_value = {
                    "value_id": new_stable_id("value"), "kind": "record", "record_type": "key_chord",
                    "fields": {"key_chord.field.keys": {
                        "value_id": new_stable_id("value"), "kind": "list", "item_type": "string",
                        "items": [_value("string", value=item) for item in keys],
                    }},
                }
                commands.append({"kind": "insert_call", "function_id": "official.input.key", "arguments": {"official.input.key.parameter.key": key_value}, "location": location})
            elif kind == "scroll":
                delta = float(event.get("delta") or 0)
                commands.append({"kind": "insert_call", "function_id": "official.input.scroll", "arguments": {"official.input.scroll.parameter.direction": _value("string", value="up" if delta > 0 else "down"), "official.input.scroll.parameter.distance": _value("float64", value=abs(delta) or 0.6)}, "location": location})
            elif kind == "drag":
                points = event.get("points") or []
                commands.append({"kind": "insert_call", "function_id": "official.input.drag", "arguments": {"official.input.drag.parameter.path": _value("path", points=[{"x": item[0], "y": item[1]} for item in points])}, "location": location})
            elif kind == "wait":
                commands.append({"kind": "insert_call", "function_id": "official.wait.duration", "arguments": {"official.wait.duration.parameter.duration": _value("duration", milliseconds=max(0, int(event.get("duration_ms") or 0)))}, "location": location})
            elif kind == "application_start" and isinstance(event.get("application"), dict):
                commands.append({"kind": "insert_call", "function_id": "official.application.start", "arguments": {"official.application.start.parameter.application": event["application"]}, "location": location})
            elif kind == "window_activate" and isinstance(event.get("window"), dict):
                commands.append({"kind": "insert_call", "function_id": "official.window.activate", "arguments": {"official.window.activate.parameter.window": event["window"]}, "location": location})
            else:
                event["needs_attention"] = True
        return commands

    def commit(self, project_path: str, session_id: str, program_service: Any, workspace_id: str, generation: int, review_events: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session["status"] != "review":
                raise OperationRecordingError("operation_recording.not_reviewable", "操作录制尚未进入审阅状态")
            commands = self.commands(review_events, session["location"])
            if not commands:
                raise OperationRecordingError("operation_recording.empty", "没有可插入的录制动作")
            session["status"] = "committing"
            self._save(project_path, session)
            try:
                result = program_service.apply_commands(
                    workspace_id, generation, session["function_id"], session["expected_revision"], commands,
                )
            except Exception as exc:
                session["status"] = "review"
                session["last_error"] = str(exc)
                self._save(project_path, session)
                raise
            session["status"] = "complete"
            session["updated_at_ms"] = int(time.time() * 1000)
            self._save(project_path, session)
            return {"session": copy.deepcopy(session), "program": result, "inserted_command_count": len(commands)}

    def cancel(self, project_path: str, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise OperationRecordingError("operation_recording.not_found", "操作录制草稿不存在")
            session["status"] = "cancelled"
            self._stop_host(session_id)
            session["updated_at_ms"] = int(time.time() * 1000)
            self._save(project_path, session)
            return copy.deepcopy(session)


operation_recording_service_v1 = OperationRecordingServiceV1()

__all__ = ["OperationRecordingError", "OperationRecordingServiceV1", "operation_recording_service_v1"]
