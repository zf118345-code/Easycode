"""Bounded, lossless frame recorder for format-6 runtime evidence.

The recorder is a host service.  It deliberately has no ProgramDocument or
ECIR entry point.  The capture thread never waits for the writer when its
bounded queue is full: the missing interval is persisted as evidence instead.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import queue
import shutil
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from core.security import atomic_write_json

from .recording_storage_v6 import (
    DROP_INDEX,
    FRAME_INDEX,
    MARKER_INDEX,
    RECORDING_FORMAT_V6,
    RECORDING_MANIFEST,
    SEGMENT_INDEX,
    TERMINAL_RECORD,
    RecordingStorageV6,
    canonical_json_bytes,
    register_active_session,
    sha256_file,
    unregister_active_session,
)

logger = logging.getLogger(__name__)


class V6RecordingError(RuntimeError):
    """The recording cannot start or continue without producing false data."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        # A committed index line must survive a normal process crash.  PNGs
        # are fsynced before their index record is appended.
        os.fsync(stream.fileno())


class V6FrameRecorder:
    """One-process recorder with a single active recording ownership domain."""

    DEFAULT_QUEUE_CAPACITY = 48
    DEFAULT_TARGET_FPS = 15.0
    DEFAULT_MAX_DURATION_MS = 30 * 60 * 1000
    DEFAULT_MAX_SESSION_BYTES = 2 * 1024 * 1024 * 1024
    DEFAULT_MIN_FREE_BYTES = 512 * 1024 * 1024
    DEFAULT_DIAGNOSTIC_PRE_FRAMES = 45
    DEFAULT_DIAGNOSTIC_POST_FRAMES = 20
    MAX_CONSECUTIVE_CAPTURE_ERRORS = 5

    STRATEGY_ALIASES = {
        "all_frames": "all_frames",
        "lossless_all_frames": "all_frames",
        "changed_frames": "changed_frames",
        "diagnostic": "diagnostic",
        "diagnostic_events": "diagnostic",
    }

    TERMINAL_REASONS = {
        "completed",
        "user_stopped",
        "user_cancelled",
        "disk_protection",
        "permission_revoked",
        "target_invalid",
        "driver_failed",
        "process_interrupted",
        "quota_reached",
        "duration_reached",
        "workspace_switched",
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._state = self._empty_state()
        self._stop_event: threading.Event | None = None
        self._capture_thread: threading.Thread | None = None
        self._writer_thread: threading.Thread | None = None
        self._write_queue: queue.Queue[dict[str, Any] | None] | None = None
        self._capture_provider: Callable[[], Image.Image] | None = None
        self._capture_release: Callable[[], None] | None = None
        self._target_snapshot_provider: Callable[[], dict[str, Any]] | None = None
        self._release_done = False
        self._writer_error: BaseException | None = None
        self._options: dict[str, Any] = {}
        self._previous_signature: np.ndarray | None = None
        self._diagnostic_ring: deque[dict[str, Any]] = deque()
        self._diagnostic_post_remaining = 0
        self._submitted_capture_sequences: set[int] = set()
        self._segment_signature: tuple[Any, ...] | None = None
        self._segment_id = ""
        self._segment_opened_at = ""
        self._pending_policy_drop: dict[str, Any] | None = None
        self._pending_backpressure_drop: dict[str, Any] | None = None
        self._subscribers: list[queue.Queue] = []
        self._last_publish = 0.0
        self._finishing = False

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "active": False,
            "status": "idle",
            "project_path": "",
            "recording_session_id": "",
            "session_id": "",
            "output_dir": "",
            "recording_format": RECORDING_FORMAT_V6,
            "strategy": "changed_frames",
            "recording_mode": "changed_frames",
            "started_at": "",
            "stopped_at": "",
            "terminal_reason": "",
            "stop_reason": "",
            "last_error": "",
            "frame_count": 0,
            "capture_count": 0,
            "segment_count": 0,
            "marker_count": 0,
            "drop_event_count": 0,
            "dropped_frame_count": 0,
            "policy_skipped_frame_count": 0,
            "disk_bytes": 0,
            "queue_depth": 0,
            "queue_capacity": 0,
            "target_fps": 0.0,
            "change_threshold": 0.006,
            "max_duration_ms": 0,
            "max_session_bytes": 0,
            "min_free_bytes": 0,
            "target_id": "",
            "target_kind": "",
            "target_title": "",
            "capture_backend": "",
            "last_frame_id": "",
            "last_capture_at": "",
            "last_write_lag_ms": 0.0,
            "owned_by_current_workspace": True,
        }

    @classmethod
    def normalize_options(cls, options: dict[str, Any] | None) -> dict[str, Any]:
        raw = options if isinstance(options, dict) else {}
        strategy = cls.STRATEGY_ALIASES.get(
            str(raw.get("strategy") or raw.get("recording_mode") or "changed_frames").strip().lower(),
            "changed_frames",
        )

        def number(name: str, default: float, low: float, high: float) -> float:
            try:
                return max(low, min(high, float(raw.get(name, default))))
            except (TypeError, ValueError):
                return default

        def integer(
            name: str, default: int, low: int, high: int, *, zero_means_default: bool = False,
        ) -> int:
            try:
                value = int(raw.get(name, default))
                if zero_means_default and value == 0:
                    value = default
                return max(low, min(high, value))
            except (TypeError, ValueError):
                return default

        return {
            "strategy": strategy,
            "target_fps": number("target_fps", cls.DEFAULT_TARGET_FPS, 0.2, 120.0),
            "queue_capacity": integer("queue_capacity", cls.DEFAULT_QUEUE_CAPACITY, 4, 512),
            "change_threshold": number("change_threshold", 0.006, 0.0001, 1.0),
            "max_duration_ms": integer(
                "max_duration_ms", cls.DEFAULT_MAX_DURATION_MS, 1_000, 7 * 24 * 60 * 60 * 1000,
                zero_means_default=True,
            ),
            "max_session_bytes": integer(
                "max_session_bytes", cls.DEFAULT_MAX_SESSION_BYTES, 1_048_576, 1_000_000_000_000,
                zero_means_default=True,
            ),
            "min_free_bytes": integer(
                "min_free_bytes", cls.DEFAULT_MIN_FREE_BYTES, 64 * 1024 * 1024, 100 * 1024**3,
                zero_means_default=True,
            ),
            "diagnostic_pre_frames": integer(
                "diagnostic_pre_frames", cls.DEFAULT_DIAGNOSTIC_PRE_FRAMES, 1, 600,
            ),
            "diagnostic_post_frames": integer(
                "diagnostic_post_frames", cls.DEFAULT_DIAGNOSTIC_POST_FRAMES, 0, 600,
            ),
        }

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._state)
            started = float(result.pop("_started_monotonic", 0.0) or 0.0)
        elapsed = max(0.0, time.monotonic() - started) if started else 0.0
        result["elapsed_ms"] = int(elapsed * 1000)
        result["average_fps"] = round(float(result["frame_count"]) / elapsed, 2) if elapsed else 0.0
        return result

    def uses_capture_provider(self, provider: Callable[[], Image.Image]) -> bool:
        with self._lock:
            return self._capture_provider is provider

    def subscribe(self) -> queue.Queue:
        subscriber: queue.Queue = queue.Queue(maxsize=32)
        with self._lock:
            self._subscribers.append(subscriber)
        subscriber.put_nowait({"event": "state", **self.get_state()})
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        with self._lock:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(subscriber)

    def _publish(self, event: str, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_publish < 0.2:
            return
        self._last_publish = now
        payload = {"event": event, **self.get_state()}
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            with contextlib.suppress(queue.Full):
                subscriber.put_nowait(payload)

    @staticmethod
    def _project_metadata(project_path: str) -> tuple[str, str]:
        path = Path(project_path) / "project.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            value = {}
        project_id = str(value.get("project_id") or "").strip()
        if not project_id:
            project_id = f"project_{hashlib.sha256(str(Path(project_path).resolve()).casefold().encode()).hexdigest()[:24]}"
        return project_id, str(value.get("name") or Path(project_path).name)

    def start(
        self,
        project_path: str,
        options: dict[str, Any] | None,
        *,
        capture_provider: Callable[[], Image.Image],
        capture_release: Callable[[], None] | None,
        target_snapshot_provider: Callable[[], dict[str, Any]],
        capture_backend: str,
        run_id: str = "",
        instance_id: str = "ide",
        storage_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """Start only after a real first frame is captured and committed."""

        with self._lifecycle_lock:
            current = self.get_state()
            normalized_project = str(Path(project_path).resolve())
            if current["active"]:
                if str(current["project_path"]).casefold() == normalized_project.casefold():
                    return current
                raise V6RecordingError("已有其他项目正在录制")
            if not Path(normalized_project).is_dir():
                raise V6RecordingError("项目路径不存在，无法开始录制")
            normalized = self.normalize_options(options)
            root = (
                Path(storage_root).resolve()
                if storage_root is not None
                else RecordingStorageV6.recordings_root(normalized_project)
            )
            root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(root).free < normalized["min_free_bytes"]:
                raise V6RecordingError("磁盘可用空间低于录制保护阈值，已阻止开始录制")
            # Resolve target identity before allocating a session directory.
            # A target that cannot be described must not leave an empty,
            # user-visible recording behind.
            target_snapshot = dict(target_snapshot_provider() or {})
            project_id, project_name = self._project_metadata(normalized_project)
            session_id = f"rec_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:10]}"
            session_dir = root / session_id
            session_dir.mkdir(parents=False, exist_ok=False)
            (session_dir / "frames").mkdir()
            register_active_session(session_dir)
            started_at = _utc_now()
            stop_event = threading.Event()
            with self._lock:
                self._state = {
                    **self._empty_state(),
                    "active": True,
                    "status": "starting",
                    "project_path": normalized_project,
                    "recording_session_id": session_id,
                    "session_id": session_id,
                    "output_dir": str(session_dir),
                    "strategy": normalized["strategy"],
                    "recording_mode": normalized["strategy"],
                    "started_at": started_at,
                    "queue_capacity": normalized["queue_capacity"],
                    "target_fps": normalized["target_fps"],
                    "change_threshold": normalized["change_threshold"],
                    "max_duration_ms": normalized["max_duration_ms"],
                    "max_session_bytes": normalized["max_session_bytes"],
                    "min_free_bytes": normalized["min_free_bytes"],
                    "target_id": str(target_snapshot.get("target_id") or ""),
                    "target_kind": str(target_snapshot.get("target_kind") or target_snapshot.get("type") or ""),
                    "target_title": str(target_snapshot.get("target_title") or target_snapshot.get("name") or "运行目标"),
                    "capture_backend": str(capture_backend or "target_driver"),
                    "_started_monotonic": time.monotonic(),
                }
                self._options = normalized
                self._stop_event = stop_event
                self._capture_provider = capture_provider
                self._capture_release = capture_release
                self._target_snapshot_provider = target_snapshot_provider
                self._release_done = False
                self._writer_error = None
                self._write_queue = queue.Queue(maxsize=normalized["queue_capacity"])
                self._previous_signature = None
                self._diagnostic_ring = deque(maxlen=normalized["diagnostic_pre_frames"])
                self._diagnostic_post_remaining = 0
                self._submitted_capture_sequences.clear()
                self._segment_signature = None
                self._segment_id = ""
                self._segment_opened_at = ""
                self._pending_policy_drop = None
                self._pending_backpressure_drop = None
                self._capture_thread = None
                self._writer_thread = None
                self._finishing = False
            manifest = {
                "recording_format": RECORDING_FORMAT_V6,
                "recording_session_id": session_id,
                "session_id": session_id,
                "project_id": project_id,
                "project_name": project_name,
                "run_id": str(run_id or ""),
                "instance_id": str(instance_id or "ide"),
                "process_id": int(__import__("os").getpid()),
                "started_at": started_at,
                "stopped_at": "",
                "status": "starting",
                "terminal_reason": "",
                "strategy": normalized["strategy"],
                "target_id": self._state["target_id"],
                "target_kind": self._state["target_kind"],
                "target_title": self._state["target_title"],
                "capture_backend": self._state["capture_backend"],
                "options": dict(normalized),
                "lossless_pixel_encoding": "png",
                "retention_policy": "explicit_user_delete_only",
                "local_only": True,
                "final": False,
            }
            atomic_write_json(str(session_dir / RECORDING_MANIFEST), manifest, clean_transient=False)
            try:
                first = self._capture_packet()
                self._ensure_segment(first)
                # Every strategy commits the first real frame so the session
                # has a trustworthy target/space anchor.
                self._write_packet(first)
                with self._lock:
                    self._state["status"] = "recording"
                writer = threading.Thread(target=self._writer_loop, daemon=True, name=f"rec-writer-{session_id[-6:]}")
                capture = threading.Thread(target=self._capture_loop, daemon=True, name=f"rec-capture-{session_id[-6:]}")
                with self._lock:
                    self._writer_thread = writer
                    self._capture_thread = capture
                writer.start()
                capture.start()
                self._write_manifest(final=False)
                self._publish("started", force=True)
                return self.get_state()
            except Exception as exc:
                self._finish("driver_failed", str(exc))
                if isinstance(exc, V6RecordingError):
                    raise
                raise V6RecordingError(str(exc)) from exc

    def _capture_packet(self) -> dict[str, Any]:
        with self._lock:
            provider = self._capture_provider
            target_provider = self._target_snapshot_provider
            capture_sequence = int(self._state["capture_count"]) + 1
            self._state["capture_count"] = capture_sequence
        if provider is None or target_provider is None:
            raise V6RecordingError("录制目标已释放")
        source = provider()
        image = source.convert("RGB") if isinstance(source, Image.Image) else Image.fromarray(np.asarray(source)).convert("RGB")
        target = dict(target_provider() or {})
        width, height = image.size
        target_id = str(target.get("target_id") or self._state.get("target_id") or "")
        target_kind = str(target.get("target_kind") or target.get("type") or self._state.get("target_kind") or "")
        orientation = str(target.get("orientation") or ("landscape" if width >= height else "portrait"))
        dpi = int(target.get("dpi") or 0)
        space_version = str(target.get("space_version") or "").strip()
        if not space_version:
            space_version = f"{target_id or target_kind}:{width}x{height}:{orientation}:dpi{dpi}"
        signature = np.asarray(image.convert("L").resize((64, 36)), dtype=np.float32)
        with self._lock:
            previous = self._previous_signature
            self._previous_signature = signature
        change_score = 1.0 if previous is None else float(np.mean(np.abs(signature - previous)) / 255.0)
        return {
            "capture_sequence": capture_sequence,
            "image": image.copy(),
            "captured_at": _utc_now(),
            "captured_monotonic": time.monotonic(),
            "timestamp_ns": time.time_ns(),
            "target_id": target_id,
            "target_kind": target_kind,
            "target_title": str(target.get("target_title") or target.get("name") or self._state.get("target_title") or ""),
            "space_version": space_version,
            "orientation": orientation,
            "dpi": dpi,
            "width": width,
            "height": height,
            "change_score": round(change_score, 8),
            "screen_region": list(target.get("screen_region") or [0, 0, width, height]),
        }

    @staticmethod
    def _segment_signature_for(packet: dict[str, Any]) -> tuple[Any, ...]:
        return (
            packet["target_id"], packet["target_kind"], packet["space_version"],
            packet["orientation"], packet["width"], packet["height"], packet["dpi"],
        )

    def _ensure_segment(self, packet: dict[str, Any]) -> None:
        signature = self._segment_signature_for(packet)
        with self._lock:
            current = self._segment_signature
        if current == signature:
            packet["recording_segment_id"] = self._segment_id
            return
        if current is not None:
            self._close_segment("target_space_changed", int(packet["capture_sequence"]) - 1)
        segment_id = f"seg_{uuid.uuid4().hex}"
        opened_at = str(packet["captured_at"])
        with self._lock:
            self._segment_signature = signature
            self._segment_id = segment_id
            self._segment_opened_at = opened_at
            self._state["segment_count"] = int(self._state["segment_count"]) + 1
        packet["recording_segment_id"] = segment_id
        _append_jsonl(Path(self._state["output_dir"]) / SEGMENT_INDEX, {
            "recording_format": RECORDING_FORMAT_V6,
            "event": "opened",
            "recording_session_id": self._state["session_id"],
            "recording_segment_id": segment_id,
            "opened_at": opened_at,
            "start_capture_sequence": int(packet["capture_sequence"]),
            "target_id": packet["target_id"],
            "target_kind": packet["target_kind"],
            "target_title": packet["target_title"],
            "space_version": packet["space_version"],
            "orientation": packet["orientation"],
            "width": int(packet["width"]),
            "height": int(packet["height"]),
            "dpi": int(packet["dpi"]),
        })

    def _close_segment(self, reason: str, end_capture_sequence: int) -> None:
        with self._lock:
            segment_id = self._segment_id
            if not segment_id:
                return
            self._segment_id = ""
            self._segment_signature = None
        _append_jsonl(Path(self._state["output_dir"]) / SEGMENT_INDEX, {
            "recording_format": RECORDING_FORMAT_V6,
            "event": "closed",
            "recording_session_id": self._state["session_id"],
            "recording_segment_id": segment_id,
            "closed_at": _utc_now(),
            "end_capture_sequence": max(0, int(end_capture_sequence)),
            "reason": str(reason),
        })

    def _write_packet(self, packet: dict[str, Any]) -> None:
        self._ensure_segment(packet)
        image: Image.Image = packet["image"]
        with self._lock:
            saved_sequence = int(self._state["frame_count"]) + 1
            session_id = str(self._state["session_id"])
            session_dir = Path(self._state["output_dir"])
        frame_id = f"frm_{uuid.uuid4().hex}"
        file_name = f"frame_{saved_sequence:09d}_{int(packet['timestamp_ns'])}.png"
        relative = f"frames/{file_name}"
        target = session_dir / "frames" / file_name
        temporary = session_dir / "frames" / f".{file_name}.{uuid.uuid4().hex}.tmp"
        image.save(temporary, format="PNG", compress_level=1)
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        temporary.replace(target)
        digest = sha256_file(target)
        record = {
            "recording_format": RECORDING_FORMAT_V6,
            "recording_session_id": session_id,
            "recording_segment_id": packet["recording_segment_id"],
            "frame_id": frame_id,
            "sequence": saved_sequence,
            "capture_sequence": int(packet["capture_sequence"]),
            "captured_at": packet["captured_at"],
            "timestamp_ns": int(packet["timestamp_ns"]),
            "file": relative,
            "pixel_encoding": "png_lossless",
            "sha256": digest,
            "bytes": target.stat().st_size,
            "width": int(packet["width"]),
            "height": int(packet["height"]),
            "orientation": packet["orientation"],
            "dpi": int(packet["dpi"]),
            "target_id": packet["target_id"],
            "target_kind": packet["target_kind"],
            "target_title": packet["target_title"],
            "space_version": packet["space_version"],
            "screen_region": list(packet["screen_region"]),
            "change_score": float(packet["change_score"]),
        }
        _append_jsonl(session_dir / FRAME_INDEX, record)
        with self._lock:
            self._submitted_capture_sequences.add(int(packet["capture_sequence"]))
            self._state["frame_count"] = saved_sequence
            self._state["disk_bytes"] = int(self._state["disk_bytes"]) + int(record["bytes"])
            self._state["last_frame_id"] = frame_id
            self._state["last_capture_at"] = str(record["captured_at"])
            self._state["last_write_lag_ms"] = round(
                max(0.0, time.monotonic() - float(packet["captured_monotonic"])) * 1000, 2,
            )
        self._publish("frame")

    def _submit(self, packet: dict[str, Any]) -> bool:
        capture_sequence = int(packet["capture_sequence"])
        with self._lock:
            if capture_sequence in self._submitted_capture_sequences:
                return True
            work_queue = self._write_queue
        if work_queue is None:
            return False
        try:
            work_queue.put_nowait(packet)
            with self._lock:
                self._submitted_capture_sequences.add(capture_sequence)
                self._state["queue_depth"] = work_queue.qsize()
            self._flush_backpressure_drop()
            return True
        except queue.Full:
            self._extend_drop("backpressure", packet)
            return False

    def _extend_drop(self, kind: str, packet: dict[str, Any]) -> None:
        attribute = "_pending_policy_drop" if kind == "policy_filtered" else "_pending_backpressure_drop"
        sequence = int(packet["capture_sequence"])
        with self._lock:
            pending = getattr(self, attribute)
            if pending and int(pending["end_capture_sequence"]) + 1 == sequence:
                pending["end_capture_sequence"] = sequence
                pending["ended_at"] = packet["captured_at"]
                pending["count"] = int(pending["count"]) + 1
            else:
                if pending:
                    self._persist_drop(pending)
                setattr(self, attribute, {
                    "recording_format": RECORDING_FORMAT_V6,
                    "drop_id": f"drop_{uuid.uuid4().hex}",
                    "recording_session_id": self._state["session_id"],
                    "recording_segment_id": packet.get("recording_segment_id") or self._segment_id,
                    "kind": kind,
                    "reason": "writer_queue_full" if kind == "backpressure" else "recording_policy",
                    "start_capture_sequence": sequence,
                    "end_capture_sequence": sequence,
                    "started_at": packet["captured_at"],
                    "ended_at": packet["captured_at"],
                    "count": 1,
                })
            if kind == "backpressure":
                self._state["dropped_frame_count"] = int(self._state["dropped_frame_count"]) + 1
            else:
                self._state["policy_skipped_frame_count"] = int(self._state["policy_skipped_frame_count"]) + 1

    def _persist_drop(self, event: dict[str, Any]) -> None:
        _append_jsonl(Path(self._state["output_dir"]) / DROP_INDEX, dict(event))
        self._state["drop_event_count"] = int(self._state["drop_event_count"]) + 1

    def _flush_policy_drop(self) -> None:
        with self._lock:
            pending, self._pending_policy_drop = self._pending_policy_drop, None
            if pending:
                self._persist_drop(pending)

    def _flush_backpressure_drop(self) -> None:
        with self._lock:
            pending, self._pending_backpressure_drop = self._pending_backpressure_drop, None
            if pending:
                self._persist_drop(pending)

    def _handle_packet(self, packet: dict[str, Any]) -> None:
        self._ensure_segment(packet)
        strategy = self._options["strategy"]
        if strategy == "all_frames":
            self._flush_policy_drop()
            self._submit(packet)
            return
        if strategy == "changed_frames":
            if float(packet["change_score"]) >= float(self._options["change_threshold"]):
                self._flush_policy_drop()
                self._submit(packet)
            else:
                self._extend_drop("policy_filtered", packet)
            return
        # Diagnostic recording keeps a true bounded pre-event ring and only
        # commits it around a marker/terminal event.
        self._diagnostic_ring.append(packet)
        if self._diagnostic_post_remaining > 0:
            self._submit(packet)
            self._diagnostic_post_remaining -= 1

    def _flush_diagnostic_ring(self, *, post_frames: int | None = None) -> None:
        for packet in list(self._diagnostic_ring):
            self._submit(packet)
        if post_frames is not None:
            self._diagnostic_post_remaining = max(self._diagnostic_post_remaining, int(post_frames))

    def _capture_loop(self) -> None:
        consecutive_errors = 0
        terminal_reason = "completed"
        terminal_error = ""
        last_disk_check = 0.0
        try:
            while True:
                stop = self._stop_event
                if stop is None or stop.is_set():
                    terminal_reason = str(self._state.get("stop_reason") or "user_stopped")
                    break
                if self._writer_error is not None:
                    raise V6RecordingError(f"录制写入失败：{self._writer_error}")
                elapsed_ms = int((time.monotonic() - float(self._state["_started_monotonic"])) * 1000)
                if elapsed_ms >= int(self._options["max_duration_ms"]):
                    terminal_reason = "duration_reached"
                    break
                if int(self._state["disk_bytes"]) >= int(self._options["max_session_bytes"]):
                    terminal_reason = "quota_reached"
                    break
                now = time.monotonic()
                if now - last_disk_check >= 1:
                    last_disk_check = now
                    if shutil.disk_usage(self._state["output_dir"]).free < int(self._options["min_free_bytes"]):
                        terminal_reason = "disk_protection"
                        break
                started = time.monotonic()
                try:
                    packet = self._capture_packet()
                    self._handle_packet(packet)
                    consecutive_errors = 0
                except Exception as exc:
                    consecutive_errors += 1
                    with self._lock:
                        self._state["last_error"] = str(exc)
                    self._publish("capture_error", force=True)
                    if consecutive_errors >= self.MAX_CONSECUTIVE_CAPTURE_ERRORS:
                        raise V6RecordingError(f"连续截图失败 {consecutive_errors} 次：{exc}") from exc
                interval = 1.0 / float(self._options["target_fps"])
                remaining = interval - (time.monotonic() - started)
                if remaining > 0 and stop.wait(remaining):
                    terminal_reason = str(self._state.get("stop_reason") or "user_stopped")
                    break
        except Exception as exc:
            terminal_reason = self._classify_failure(exc)
            terminal_error = str(exc)
            logger.exception("v6 逐帧录制异常")
        finally:
            if self._options.get("strategy") == "diagnostic":
                self._flush_diagnostic_ring(post_frames=0)
            self._flush_policy_drop()
            self._flush_backpressure_drop()
            self._drain_writer()
            self._finish(terminal_reason, terminal_error)

    @staticmethod
    def _classify_failure(exc: BaseException) -> str:
        text = str(exc).casefold()
        if any(value in text for value in ("permission", "权限", "mediaprojection")):
            return "permission_revoked"
        if any(value in text for value in ("target", "目标", "window", "窗口", "device", "设备")):
            return "target_invalid"
        return "driver_failed"

    def _writer_loop(self) -> None:
        work_queue = self._write_queue
        if work_queue is None:
            return
        packet: dict[str, Any] | None = None
        try:
            while True:
                packet = work_queue.get()
                try:
                    if packet is None:
                        return
                    self._write_packet(packet)
                finally:
                    work_queue.task_done()
                    with self._lock:
                        self._state["queue_depth"] = work_queue.qsize()
        except Exception as exc:
            lost_packets: list[dict[str, Any]] = []
            if isinstance(packet, dict):
                lost_packets.append(packet)
            while True:
                try:
                    queued = work_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    if isinstance(queued, dict):
                        lost_packets.append(queued)
                finally:
                    work_queue.task_done()
            with contextlib.suppress(Exception):
                self._persist_writer_failure(lost_packets)
            with self._lock:
                self._writer_error = exc
                self._state["last_error"] = str(exc)
            stop = self._stop_event
            if stop is not None:
                stop.set()

    def _persist_writer_failure(self, packets: list[dict[str, Any]]) -> None:
        """Account for accepted queue items that never became committed frames."""

        session_dir = Path(self._state["output_dir"])
        committed, _ = RecordingStorageV6.read_jsonl(session_dir / FRAME_INDEX)
        committed_sequences = {
            int(item.get("capture_sequence") or 0) for item in committed
        }
        sequences = sorted({
            int(item.get("capture_sequence") or 0)
            for item in packets
            if int(item.get("capture_sequence") or 0) > 0
            and int(item.get("capture_sequence") or 0) not in committed_sequences
        })
        if not sequences:
            return
        ranges: list[tuple[int, int]] = []
        start = end = sequences[0]
        for sequence in sequences[1:]:
            if sequence == end + 1:
                end = sequence
            else:
                ranges.append((start, end))
                start = end = sequence
        ranges.append((start, end))
        by_sequence = {
            int(item.get("capture_sequence") or 0): item for item in packets
        }
        for start, end in ranges:
            first, last = by_sequence[start], by_sequence[end]
            event = {
                "recording_format": RECORDING_FORMAT_V6,
                "drop_id": f"drop_{uuid.uuid4().hex}",
                "recording_session_id": self._state["session_id"],
                "recording_segment_id": str(
                    first.get("recording_segment_id") or self._segment_id or ""
                ),
                "kind": "writer_failure",
                "reason": "writer_failed_before_commit",
                "start_capture_sequence": start,
                "end_capture_sequence": end,
                "started_at": first.get("captured_at"),
                "ended_at": last.get("captured_at"),
                "count": end - start + 1,
            }
            self._persist_drop(event)
            with self._lock:
                self._state["dropped_frame_count"] = int(
                    self._state["dropped_frame_count"]
                ) + int(event["count"])

    def _drain_writer(self) -> None:
        work_queue, writer = self._write_queue, self._writer_thread
        if work_queue is None or writer is None or not writer.is_alive():
            return
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                work_queue.put(None, timeout=0.1)
                break
            except queue.Full:
                if not writer.is_alive():
                    break
        writer.join(timeout=max(0.1, deadline - time.monotonic()))
        if writer.is_alive() and self._writer_error is None:
            self._writer_error = V6RecordingError("写入线程未能在停止时限内完成")

    def mark_event(self, label: str = "手动标记", *, kind: str = "user") -> dict[str, Any]:
        clean = str(label or "手动标记").strip()[:120] or "手动标记"
        with self._lock:
            if not self._state["active"]:
                raise V6RecordingError("当前没有正在进行的录制")
            marker = {
                "recording_format": RECORDING_FORMAT_V6,
                "marker_id": f"mark_{uuid.uuid4().hex}",
                "recording_session_id": self._state["session_id"],
                "recording_segment_id": self._segment_id,
                "kind": str(kind or "user"),
                "label": clean,
                "marked_at": _utc_now(),
                "capture_sequence": int(self._state["capture_count"]),
                "nearest_frame_id": str(self._state["last_frame_id"] or ""),
            }
            _append_jsonl(Path(self._state["output_dir"]) / MARKER_INDEX, marker)
            self._state["marker_count"] = int(self._state["marker_count"]) + 1
            if self._options.get("strategy") == "diagnostic":
                self._flush_diagnostic_ring(post_frames=int(self._options["diagnostic_post_frames"]))
        self._publish("marker", force=True)
        return marker

    def request_stop(self, reason: str = "user_stopped") -> dict[str, Any]:
        normalized = {
            "user": "user_stopped",
            "stopped": "user_stopped",
            "cancelled": "user_cancelled",
        }.get(str(reason or "").strip().lower(), str(reason or "user_stopped").strip().lower())
        if normalized not in self.TERMINAL_REASONS:
            normalized = "user_stopped"
        with self._lock:
            if not self._state["active"]:
                return self.get_state()
            self._state["status"] = "stopping"
            self._state["stop_reason"] = normalized
            stop = self._stop_event
        if stop is not None:
            stop.set()
        self._publish("stopping", force=True)
        return self.get_state()

    def stop(self, reason: str = "user_stopped", timeout: float = 15) -> dict[str, Any]:
        self.request_stop(reason)
        with self._lock:
            capture = self._capture_thread
        if capture is not None and capture is not threading.current_thread():
            capture.join(timeout=max(0.1, float(timeout)))
        return self.get_state()

    def _release_capture_once(self) -> None:
        with self._lock:
            if self._release_done:
                return
            self._release_done = True
            release, self._capture_release = self._capture_release, None
            self._capture_provider = None
            self._target_snapshot_provider = None
        if release is not None:
            with contextlib.suppress(Exception):
                release()

    def _write_manifest(self, *, final: bool) -> None:
        state = self.get_state()
        session_dir = Path(state["output_dir"])
        existing = RecordingStorageV6.read_json(session_dir / RECORDING_MANIFEST, {}) or {}
        indexes = {}
        if final:
            for name in (FRAME_INDEX, SEGMENT_INDEX, MARKER_INDEX, DROP_INDEX, TERMINAL_RECORD):
                path = session_dir / name
                if path.is_file():
                    indexes[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        manifest = {
            **existing,
            "recording_format": RECORDING_FORMAT_V6,
            "recording_session_id": state["session_id"],
            "status": state["status"],
            "stopped_at": state["stopped_at"],
            "terminal_reason": state["terminal_reason"],
            "last_error": state["last_error"],
            "capture_count": state["capture_count"],
            "frame_count": state["frame_count"],
            "segment_count": state["segment_count"],
            "marker_count": state["marker_count"],
            "drop_event_count": state["drop_event_count"],
            "dropped_frame_count": state["dropped_frame_count"],
            "policy_skipped_frame_count": state["policy_skipped_frame_count"],
            "disk_bytes": state["disk_bytes"],
            "indexes": indexes,
            "content_digest": hashlib.sha256(canonical_json_bytes(indexes)).hexdigest() if final else "",
            "final": bool(final),
        }
        atomic_write_json(str(session_dir / RECORDING_MANIFEST), manifest, clean_transient=False)

    def _finish(self, reason: str, error: str) -> None:
        with self._lock:
            if self._finishing or not self._state.get("output_dir"):
                return
            self._finishing = True
            reason = reason if reason in self.TERMINAL_REASONS else "driver_failed"
            status = "completed" if reason == "completed" else ("stopped" if reason in {
                "user_stopped", "user_cancelled", "workspace_switched",
            } else "error")
            self._state["status"] = status
            self._state["terminal_reason"] = reason
            self._state["stop_reason"] = reason
            self._state["stopped_at"] = _utc_now()
            if error:
                self._state["last_error"] = error
            capture_sequence = int(self._state["capture_count"])
        with contextlib.suppress(Exception):
            self._close_segment(reason, capture_sequence)
        terminal = {
            "recording_format": RECORDING_FORMAT_V6,
            "recording_session_id": self._state["session_id"],
            "status": self._state["status"],
            "terminal_reason": reason,
            "stopped_at": self._state["stopped_at"],
            "last_error": self._state["last_error"],
            "capture_count": self._state["capture_count"],
            "frame_count": self._state["frame_count"],
        }
        with contextlib.suppress(Exception):
            atomic_write_json(
                str(Path(self._state["output_dir"]) / TERMINAL_RECORD), terminal, clean_transient=False,
            )
            self._write_manifest(final=True)
        self._release_capture_once()
        unregister_active_session(Path(self._state["output_dir"]))
        with self._lock:
            self._state["active"] = False
            self._stop_event = None
            self._capture_thread = None
            self._writer_thread = None
            self._write_queue = None
            self._finishing = False
        self._publish("stopped" if self._state["status"] != "error" else "error", force=True)


v6_frame_recorder = V6FrameRecorder()
