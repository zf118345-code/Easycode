"""Versioned, local-only storage for format-6 recording sessions.

The storage is deliberately outside the editable project.  A recording is
runtime evidence, not project source, a publish input, or an update payload.
This module also remains the single path validator used by Recorder, Replay
and historical Capture so a crafted session id can never escape its data root.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException
from PIL import Image, ImageChops, ImageStat

from core.security import atomic_write_json


RECORDING_FORMAT_V6 = 3
RECORDING_MANIFEST = "session.json"
FRAME_INDEX = "frames.jsonl"
SEGMENT_INDEX = "segments.jsonl"
MARKER_INDEX = "markers.jsonl"
DROP_INDEX = "drops.jsonl"
TERMINAL_RECORD = "terminal.json"
ANALYSIS_DIRECTORY = "analyses"
ANALYSIS_INPUT_DIRECTORY = "analysis-inputs"
EXPORT_DIRECTORY = "exports"

_SESSION_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)
_ACTIVE_SESSION_PATHS: set[str] = set()
_ACTIVE_SESSION_LOCK = threading.Lock()
_RECOVERY_LOCK = threading.Lock()


def register_active_session(path: Path) -> None:
    with _ACTIVE_SESSION_LOCK:
        _ACTIVE_SESSION_PATHS.add(os.path.normcase(str(path.resolve())))


def unregister_active_session(path: Path) -> None:
    with _ACTIVE_SESSION_LOCK:
        _ACTIVE_SESSION_PATHS.discard(os.path.normcase(str(path.resolve())))


def _session_is_active(path: Path, manifest: dict[str, Any]) -> bool:
    normalized = os.path.normcase(str(path.resolve()))
    with _ACTIVE_SESSION_LOCK:
        if normalized in _ACTIVE_SESSION_PATHS:
            return True
    pid = int(manifest.get("process_id") or 0)
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        import psutil

        return bool(psutil.pid_exists(pid))
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _safe_component(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value or any(character not in _SESSION_ID_CHARS for character in value):
        raise HTTPException(status_code=400, detail=f"{label}无效")
    return value


def _safe_child(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="录制数据路径越界")
    return candidate


def _project_identity(project_path: str) -> tuple[str, str]:
    project = Path(project_path).resolve()
    try:
        value = json.loads((project / "project.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        value = {}
    project_id = str(value.get("project_id") or "").strip()
    if not project_id:
        # Read-only fallback for damaged/test projects.  It is deterministic
        # and does not expose the absolute path as a directory name.
        project_id = f"project_{sha256_bytes(str(project).casefold().encode('utf-8'))[:24]}"
    safe_id = "".join(character if character in _SESSION_ID_CHARS else "_" for character in project_id)
    return safe_id[:160], str(value.get("name") or project.name)


def recording_data_root(project_path: str) -> Path:
    """Return the isolated IDE recording root for one project identity."""

    configured = str(os.environ.get("EASYCODE_RECORDING_DATA_ROOT") or "").strip()
    if configured:
        base = Path(configured)
    else:
        local = str(os.environ.get("LOCALAPPDATA") or "").strip()
        base = Path(local) if local else Path(tempfile.gettempdir())
        base = base / "EasyCode" / "RecordingData" / "IDE"
    project_id, _ = _project_identity(project_path)
    root = base.resolve() / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class RecordedFrameV6:
    session_id: str
    session_dir: Path
    record: dict[str, Any]
    path: Path


class RecordingStorageV6:
    """Read, validate, export and remove immutable recording evidence."""

    MAX_PAGE_SIZE = 500
    MAX_EXPORT_BYTES = 50 * 1024 * 1024 * 1024

    @classmethod
    def recordings_root(cls, project_path: str) -> Path:
        return recording_data_root(project_path)

    @classmethod
    def legacy_root(cls, project_path: str) -> Path:
        return Path(project_path).resolve() / "recordings"

    @classmethod
    def candidate_roots(cls, project_path: str) -> list[Path]:
        roots = [cls.recordings_root(project_path)]
        legacy = cls.legacy_root(project_path)
        if legacy.is_dir() and legacy.resolve() != roots[0].resolve():
            # Read-only bridge for already-created diagnostics. New v6
            # sessions never write here.
            roots.append(legacy)
        return roots

    @classmethod
    def session_dir(cls, project_path: str, session_id: str) -> Path:
        safe_id = _safe_component(session_id, "录制会话标识")
        for root in cls.candidate_roots(project_path):
            candidate = _safe_child(root, safe_id)
            if candidate.is_dir():
                return candidate
        raise HTTPException(status_code=404, detail="录制会话不存在")

    @staticmethod
    def read_json(path: Path, fallback: Any = None) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        records: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, raw in enumerate(stream, 1):
                    if not raw.strip():
                        continue
                    try:
                        value = json.loads(raw)
                    except json.JSONDecodeError:
                        issues.append({
                            "code": "recording.index_truncated",
                            "file": path.name,
                            "line": line_number,
                            "message": "索引包含截断或无效 JSON 行",
                        })
                        continue
                    if not isinstance(value, dict):
                        issues.append({
                            "code": "recording.index_record_invalid",
                            "file": path.name,
                            "line": line_number,
                            "message": "索引记录不是对象",
                        })
                        continue
                    records.append({**value, "_line": line_number})
        except FileNotFoundError:
            pass
        return records, issues

    @classmethod
    def _recover_interrupted_session(cls, session_dir: Path) -> dict[str, Any]:
        """Materialize one truthful terminal for a dead format-3 writer.

        Recovery never resumes capture and never edits a committed frame or
        JSONL index.  It only seals the indexes that survived the process and
        records that the previous process ended without its normal terminal.
        A truncated index therefore remains detectable by ``verify_session``.
        """

        with _RECOVERY_LOCK:
            manifest = cls.read_json(session_dir / RECORDING_MANIFEST, {}) or {}
            if (
                not manifest
                or bool(manifest.get("final"))
                or int(manifest.get("recording_format") or 0) != RECORDING_FORMAT_V6
                or _session_is_active(session_dir, manifest)
            ):
                return manifest
            frames, _ = cls.read_jsonl(session_dir / FRAME_INDEX)
            segments, _ = cls.read_jsonl(session_dir / SEGMENT_INDEX)
            markers, _ = cls.read_jsonl(session_dir / MARKER_INDEX)
            drops, _ = cls.read_jsonl(session_dir / DROP_INDEX)
            recovered_at = _utc_now()
            terminal = {
                "recording_format": RECORDING_FORMAT_V6,
                "recording_session_id": str(
                    manifest.get("recording_session_id") or session_dir.name
                ),
                "status": "error",
                "terminal_reason": "process_interrupted",
                "stopped_at": recovered_at,
                "recovered_at": recovered_at,
                "last_error": "上次录制进程未写入正常终态；未自动恢复录制",
                "capture_count": max(
                    (int(item.get("capture_sequence") or 0) for item in frames),
                    default=int(manifest.get("capture_count") or 0),
                ),
                "frame_count": len(frames),
            }
            atomic_write_json(
                str(session_dir / TERMINAL_RECORD), terminal, clean_transient=False,
            )
            indexes: dict[str, dict[str, Any]] = {}
            for name in (FRAME_INDEX, SEGMENT_INDEX, MARKER_INDEX, DROP_INDEX, TERMINAL_RECORD):
                path = session_dir / name
                if path.is_file():
                    indexes[name] = {
                        "sha256": sha256_file(path),
                        "bytes": path.stat().st_size,
                    }
            recovered = {
                **manifest,
                "status": "error",
                "terminal_reason": "process_interrupted",
                "stopped_at": recovered_at,
                "last_error": terminal["last_error"],
                "capture_count": terminal["capture_count"],
                "frame_count": len(frames),
                "segment_count": len(
                    [item for item in segments if item.get("event") in {None, "opened"}]
                ),
                "marker_count": len(markers),
                "drop_event_count": len(drops),
                "indexes": indexes,
                "content_digest": sha256_bytes(canonical_json_bytes(indexes)),
                "recovered": True,
                "recovered_at": recovered_at,
                "final": True,
            }
            atomic_write_json(
                str(session_dir / RECORDING_MANIFEST), recovered, clean_transient=False,
            )
            return recovered

    @classmethod
    def _manifest_view(cls, session_dir: Path) -> dict[str, Any]:
        manifest = cls.read_json(session_dir / RECORDING_MANIFEST, {}) or {}
        if not bool(manifest.get("final")) and manifest:
            manifest = cls._recover_interrupted_session(session_dir)
        return manifest

    @classmethod
    def _session_summary(cls, session_dir: Path) -> dict[str, Any]:
        manifest = cls._manifest_view(session_dir)
        frames, frame_issues = cls.read_jsonl(session_dir / FRAME_INDEX)
        drops, drop_issues = cls.read_jsonl(session_dir / DROP_INDEX)
        markers, marker_issues = cls.read_jsonl(session_dir / MARKER_INDEX)
        segments, segment_issues = cls.read_jsonl(session_dir / SEGMENT_INDEX)
        issues = [*frame_issues, *drop_issues, *marker_issues, *segment_issues]
        total_bytes = sum(int(item.get("bytes") or 0) for item in frames)
        return {
            "recording_format": int(manifest.get("recording_format") or manifest.get("schema_version") or 0),
            "recording_session_id": str(
                manifest.get("recording_session_id") or manifest.get("session_id") or session_dir.name
            ),
            "session_id": session_dir.name,
            "project_id": str(manifest.get("project_id") or ""),
            "project_name": str(manifest.get("project_name") or ""),
            "run_id": str(manifest.get("run_id") or ""),
            "instance_id": str(manifest.get("instance_id") or ""),
            "started_at": str(manifest.get("started_at") or ""),
            "stopped_at": str(manifest.get("stopped_at") or ""),
            "status": str(manifest.get("status") or "unknown"),
            "terminal_reason": str(manifest.get("terminal_reason") or manifest.get("stop_reason") or ""),
            "strategy": str(manifest.get("strategy") or manifest.get("recording_mode") or "unknown"),
            "target_id": str(manifest.get("target_id") or ""),
            "target_kind": str(manifest.get("target_kind") or ""),
            "target_title": str(manifest.get("target_title") or ""),
            "capture_backend": str(manifest.get("capture_backend") or ""),
            "frame_count": len(frames),
            "capture_count": int(manifest.get("capture_count") or len(frames)),
            "segment_count": len([item for item in segments if item.get("event") == "opened"]),
            "drop_event_count": len(drops),
            "dropped_frame_count": sum(
                max(0, int(item.get("end_capture_sequence") or 0) - int(item.get("start_capture_sequence") or 0) + 1)
                for item in drops
                if item.get("kind") in {"backpressure", "writer_failure"}
            ),
            "policy_skipped_frame_count": sum(
                max(0, int(item.get("end_capture_sequence") or 0) - int(item.get("start_capture_sequence") or 0) + 1)
                for item in drops
                if item.get("kind") == "policy_filtered"
            ),
            "marker_count": len(markers),
            "total_bytes": total_bytes,
            "locked": bool(manifest.get("locked")),
            "final": bool(manifest.get("final")),
            "recovered": bool(manifest.get("recovered")),
            "integrity": "incomplete" if issues or not manifest.get("final") else "unchecked",
            "issue_count": len(issues) + (0 if manifest.get("final") else 1),
        }

    @classmethod
    def list_sessions(cls, project_path: str) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root in cls.candidate_roots(project_path):
            if not root.is_dir():
                continue
            for entry in root.iterdir():
                if not entry.is_dir() or entry.name in {
                    ANALYSIS_INPUT_DIRECTORY,
                    ANALYSIS_DIRECTORY,
                    EXPORT_DIRECTORY,
                    "blobs",
                }:
                    continue
                if entry.name in seen:
                    continue
                seen.add(entry.name)
                sessions.append(cls._session_summary(entry))
        return sorted(
            sessions,
            key=lambda item: (item.get("started_at") or "", item["session_id"]),
            reverse=True,
        )

    @classmethod
    def session_detail(cls, project_path: str, session_id: str) -> dict[str, Any]:
        session_dir = cls.session_dir(project_path, session_id)
        summary = cls._session_summary(session_dir)
        segments, segment_issues = cls.read_jsonl(session_dir / SEGMENT_INDEX)
        markers, marker_issues = cls.read_jsonl(session_dir / MARKER_INDEX)
        drops, drop_issues = cls.read_jsonl(session_dir / DROP_INDEX)
        terminal = cls.read_json(session_dir / TERMINAL_RECORD, None)
        return {
            **summary,
            "segments": [{k: v for k, v in item.items() if not k.startswith("_")} for item in segments],
            "markers": [{k: v for k, v in item.items() if not k.startswith("_")} for item in markers],
            "drops": [{k: v for k, v in item.items() if not k.startswith("_")} for item in drops],
            "terminal": terminal,
            "issues": [*segment_issues, *marker_issues, *drop_issues],
        }

    @classmethod
    def list_frames(
        cls,
        project_path: str,
        session_id: str,
        offset: int = 0,
        limit: int = 200,
    ) -> dict[str, Any]:
        session_dir = cls.session_dir(project_path, session_id)
        records, issues = cls.read_jsonl(session_dir / FRAME_INDEX)
        offset = max(0, int(offset or 0))
        limit = max(1, min(cls.MAX_PAGE_SIZE, int(limit or 200)))
        items = [
            {key: value for key, value in record.items() if not key.startswith("_")}
            for record in records[offset : offset + limit]
        ]
        return {
            "session_id": session_id,
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "frames": items,
            "issues": issues,
        }

    @classmethod
    def timeline(
        cls,
        project_path: str,
        session_id: str,
        offset: int = 0,
        limit: int = 500,
    ) -> dict[str, Any]:
        session_dir = cls.session_dir(project_path, session_id)
        frames, frame_issues = cls.read_jsonl(session_dir / FRAME_INDEX)
        markers, marker_issues = cls.read_jsonl(session_dir / MARKER_INDEX)
        drops, drop_issues = cls.read_jsonl(session_dir / DROP_INDEX)
        items: list[dict[str, Any]] = []
        for frame in frames:
            items.append({
                "kind": "frame",
                "sort_sequence": int(frame.get("capture_sequence") or frame.get("capture_index") or frame.get("index") or 0),
                **{key: value for key, value in frame.items() if not key.startswith("_")},
            })
        for marker in markers:
            items.append({
                "kind": "marker",
                "sort_sequence": int(marker.get("capture_sequence") or 0),
                **{key: value for key, value in marker.items() if not key.startswith("_")},
            })
        for drop in drops:
            items.append({
                "kind": "drop",
                "sort_sequence": int(drop.get("start_capture_sequence") or 0),
                **{key: value for key, value in drop.items() if not key.startswith("_")},
            })
        items.sort(key=lambda item: (item["sort_sequence"], {"marker": 0, "frame": 1, "drop": 2}.get(item["kind"], 9)))
        offset = max(0, int(offset or 0))
        limit = max(1, min(2_000, int(limit or 500)))
        return {
            "session_id": session_id,
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "items": items[offset : offset + limit],
            "issues": [*frame_issues, *marker_issues, *drop_issues],
        }

    @classmethod
    def resolve_frame(
        cls,
        project_path: str,
        session_id: str,
        frame_index: int | None = None,
        *,
        frame_id: str = "",
    ) -> RecordedFrameV6:
        session_dir = cls.session_dir(project_path, session_id)
        records, _ = cls.read_jsonl(session_dir / FRAME_INDEX)
        wanted_index = int(frame_index or 0)
        wanted_id = str(frame_id or "")
        record = next(
            (
                item
                for item in records
                if (wanted_id and str(item.get("frame_id") or "") == wanted_id)
                or (
                    wanted_index
                    and int(item.get("sequence") or item.get("frame_sequence") or item.get("index") or 0)
                    == wanted_index
                )
            ),
            None,
        )
        if record is None:
            label = wanted_id or str(wanted_index)
            raise HTTPException(status_code=404, detail=f"录制帧不存在：{label}")
        relative = str(record.get("file") or "").replace("\\", "/").strip()
        parts = tuple(part for part in relative.split("/") if part)
        if not parts or relative.startswith("/") or any(part in {".", ".."} for part in parts):
            raise HTTPException(status_code=422, detail="录制帧路径无效")
        path = _safe_child(session_dir, *parts)
        if not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=404, detail=f"录制帧文件缺失：{relative}")
        return RecordedFrameV6(session_id=session_id, session_dir=session_dir, record=record, path=path)

    @classmethod
    def frame_bytes(
        cls, project_path: str, session_id: str, frame_index: int
    ) -> tuple[bytes, str]:
        frame = cls.resolve_frame(project_path, session_id, frame_index)
        cls.require_frame_integrity(frame)
        return frame.path.read_bytes(), str(frame.path)

    @classmethod
    def frame_thumbnail_bytes(
        cls, project_path: str, session_id: str, frame_index: int
    ) -> bytes:
        frame = cls.resolve_frame(project_path, session_id, frame_index)
        cls.require_frame_integrity(frame)
        with Image.open(frame.path) as source:
            image = source.convert("RGB")
            image.thumbnail((240, 150), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=78, optimize=True)
            return buffer.getvalue()

    @staticmethod
    def checksum_error(frame: RecordedFrameV6) -> str | None:
        expected = str(frame.record.get("sha256") or "").strip().lower()
        if not expected:
            return "录制帧缺少内容哈希"
        try:
            actual = sha256_file(frame.path)
        except OSError as exc:
            return f"帧读取失败：{exc}"
        return None if actual == expected else f"帧校验失败：期望 {expected[:12]}，实际 {actual[:12]}"

    @classmethod
    def require_frame_integrity(cls, frame: RecordedFrameV6) -> None:
        error = cls.checksum_error(frame)
        if error:
            raise HTTPException(status_code=422, detail=error)

    @classmethod
    def verify_session(cls, project_path: str, session_id: str) -> dict[str, Any]:
        session_dir = cls.session_dir(project_path, session_id)
        manifest = cls._manifest_view(session_dir)
        frames, issues = cls.read_jsonl(session_dir / FRAME_INDEX)
        segments, segment_issues = cls.read_jsonl(session_dir / SEGMENT_INDEX)
        issues.extend(segment_issues)
        recording_format = int(
            manifest.get("recording_format") or manifest.get("schema_version") or 0
        )
        if recording_format not in {2, RECORDING_FORMAT_V6}:
            issues.append({
                "code": "recording.format_unsupported",
                "recording_format": recording_format,
            })
        if recording_format == RECORDING_FORMAT_V6 and manifest.get("final"):
            indexes = manifest.get("indexes") if isinstance(manifest.get("indexes"), dict) else {}
            for name in (FRAME_INDEX, SEGMENT_INDEX, TERMINAL_RECORD):
                expected = indexes.get(name) if isinstance(indexes, dict) else None
                path = session_dir / name
                if not isinstance(expected, dict) or not path.is_file():
                    issues.append({"code": "recording.index_manifest_missing", "file": name})
                    continue
                actual_hash = sha256_file(path)
                actual_bytes = path.stat().st_size
                if str(expected.get("sha256") or "") != actual_hash or int(
                    expected.get("bytes") or -1
                ) != actual_bytes:
                    issues.append({"code": "recording.index_integrity_failed", "file": name})
            expected_digest = str(manifest.get("content_digest") or "")
            actual_digest = sha256_bytes(canonical_json_bytes(indexes))
            if not expected_digest or expected_digest != actual_digest:
                issues.append({"code": "recording.content_digest_invalid"})
            terminal = cls.read_json(session_dir / TERMINAL_RECORD, None)
            if not isinstance(terminal, dict):
                issues.append({"code": "recording.terminal_missing"})
            elif str(terminal.get("terminal_reason") or "") != str(
                manifest.get("terminal_reason") or ""
            ):
                issues.append({"code": "recording.terminal_manifest_mismatch"})
        seen_frame_ids: set[str] = set()
        seen_sequences: set[int] = set()
        known_segments = {
            str(item.get("recording_segment_id") or item.get("segment_id") or "")
            for item in segments
            if item.get("event") in {None, "opened"}
        }
        previous_capture_sequence = 0
        verified_count = 0
        for record in frames:
            frame_id = str(record.get("frame_id") or "")
            sequence = int(record.get("sequence") or record.get("frame_sequence") or record.get("index") or 0)
            capture_sequence = int(record.get("capture_sequence") or record.get("capture_index") or sequence)
            if not frame_id:
                issues.append({"code": "recording.frame_id_missing", "frame_sequence": sequence})
            elif frame_id in seen_frame_ids:
                issues.append({"code": "recording.frame_id_duplicate", "frame_id": frame_id})
            seen_frame_ids.add(frame_id)
            if sequence <= 0 or sequence in seen_sequences:
                issues.append({"code": "recording.frame_sequence_invalid", "frame_sequence": sequence})
            seen_sequences.add(sequence)
            if capture_sequence <= previous_capture_sequence:
                issues.append({
                    "code": "recording.capture_sequence_not_monotonic",
                    "capture_sequence": capture_sequence,
                })
            previous_capture_sequence = max(previous_capture_sequence, capture_sequence)
            segment_id = str(record.get("recording_segment_id") or record.get("segment_id") or "")
            if known_segments and segment_id not in known_segments:
                issues.append({"code": "recording.segment_missing", "segment_id": segment_id})
            try:
                resolved = cls.resolve_frame(
                    project_path,
                    session_id,
                    sequence,
                    frame_id=frame_id,
                )
                error = cls.checksum_error(resolved)
            except HTTPException as exc:
                error = str(exc.detail)
            if error:
                issues.append({
                    "code": "recording.frame_integrity_failed",
                    "frame_id": frame_id,
                    "message": error,
                })
            else:
                verified_count += 1
        expected_count = int(manifest.get("frame_count") or len(frames))
        if expected_count != len(frames):
            issues.append({
                "code": "recording.frame_count_mismatch",
                "expected": expected_count,
                "actual": len(frames),
            })
        if recording_format == RECORDING_FORMAT_V6 and sorted(seen_sequences) != list(
            range(1, len(frames) + 1)
        ):
            issues.append({"code": "recording.frame_sequence_not_contiguous"})
        if not manifest.get("final"):
            issues.append({
                "code": "recording.process_interrupted",
                "message": "录制进程未写入完整终态；已提交帧仍可浏览",
            })
        return {
            "session_id": session_id,
            "ok": not issues,
            "integrity": "verified" if not issues else "incomplete",
            "verified_frame_count": verified_count,
            "frame_count": len(frames),
            "issues": issues,
        }

    @classmethod
    def compare_frames(
        cls,
        project_path: str,
        session_id: str,
        left_frame_index: int,
        right_frame_index: int,
    ) -> dict[str, Any]:
        left = cls.resolve_frame(project_path, session_id, left_frame_index)
        right = cls.resolve_frame(project_path, session_id, right_frame_index)
        cls.require_frame_integrity(left)
        cls.require_frame_integrity(right)
        if str(left.record.get("recording_segment_id") or "") != str(
            right.record.get("recording_segment_id") or ""
        ):
            raise HTTPException(status_code=422, detail="不同目标片段不能直接比较空间差异")
        with Image.open(left.path) as left_source, Image.open(right.path) as right_source:
            left_image = left_source.convert("RGB")
            right_image = right_source.convert("RGB")
            if left_image.size != right_image.size:
                raise HTTPException(status_code=422, detail="两帧尺寸不同，不能直接比较")
            difference = ImageChops.difference(left_image, right_image)
            extrema = difference.getbbox()
            histogram = difference.convert("L").histogram()
            changed_pixels = sum(histogram[1:])
            total_pixels = max(1, left_image.width * left_image.height)
            mean = float(ImageStat.Stat(difference).mean[0] + ImageStat.Stat(difference).mean[1] + ImageStat.Stat(difference).mean[2]) / 3.0
            return {
                "session_id": session_id,
                "left_frame_index": left_frame_index,
                "right_frame_index": right_frame_index,
                "width": left_image.width,
                "height": left_image.height,
                "identical": extrema is None,
                "difference_box": list(extrema) if extrema else None,
                "changed_pixel_ratio": round(changed_pixels / total_pixels, 6),
                "mean_channel_difference": round(mean, 4),
            }

    @classmethod
    def comparison_image_bytes(
        cls,
        project_path: str,
        session_id: str,
        left_frame_index: int,
        right_frame_index: int,
    ) -> bytes:
        left = cls.resolve_frame(project_path, session_id, left_frame_index)
        right = cls.resolve_frame(project_path, session_id, right_frame_index)
        cls.require_frame_integrity(left)
        cls.require_frame_integrity(right)
        if str(left.record.get("recording_segment_id") or "") != str(
            right.record.get("recording_segment_id") or ""
        ):
            raise HTTPException(status_code=422, detail="不同目标片段不能生成像素差异图")
        with Image.open(left.path) as left_source, Image.open(right.path) as right_source:
            left_image = left_source.convert("RGB")
            right_image = right_source.convert("RGB")
            if left_image.size != right_image.size:
                raise HTTPException(status_code=422, detail="两帧尺寸不同，不能生成差异图")
            difference = ImageChops.difference(left_image, right_image)
            # Preserve exact diff pixels; viewers can inspect rather than trust
            # an opaque score only.
            buffer = io.BytesIO()
            difference.save(buffer, format="PNG", compress_level=3)
            return buffer.getvalue()

    @classmethod
    def list_analysis_reports(cls, project_path: str, session_id: str) -> list[dict[str, Any]]:
        session_dir = cls.session_dir(project_path, session_id)
        root = session_dir / ANALYSIS_DIRECTORY
        if not root.is_dir():
            return []
        reports = []
        for path in root.glob("analysis_*.json"):
            value = cls.read_json(path, None)
            if isinstance(value, dict):
                reports.append(value)
        return sorted(reports, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    @classmethod
    def analysis_report(cls, project_path: str, session_id: str, analysis_run_id: str) -> dict[str, Any]:
        safe_id = _safe_component(analysis_run_id, "分析记录标识")
        session_dir = cls.session_dir(project_path, session_id)
        path = _safe_child(session_dir / ANALYSIS_DIRECTORY, f"{safe_id}.json")
        value = cls.read_json(path, None)
        if not isinstance(value, dict):
            raise HTTPException(status_code=404, detail="分析报告不存在")
        return value

    @classmethod
    def delete_analysis_report(
        cls, project_path: str, session_id: str, analysis_run_id: str
    ) -> dict[str, Any]:
        safe_id = _safe_component(analysis_run_id, "分析记录标识")
        session_dir = cls.session_dir(project_path, session_id)
        path = _safe_child(session_dir / ANALYSIS_DIRECTORY, f"{safe_id}.json")
        value = cls.read_json(path, None)
        if not isinstance(value, dict):
            raise HTTPException(status_code=404, detail="分析报告不存在")
        size = path.stat().st_size
        path.unlink()
        return {
            "deleted": True,
            "analysis_run_id": safe_id,
            "released_bytes": size,
            "analysis_input_bundle_retained": str(value.get("analysis_input_bundle_id") or ""),
        }

    @classmethod
    def create_export(
        cls,
        project_path: str,
        session_id: str,
        *,
        mode: str,
        analysis_run_ids: Iterable[str] = (),
        include_categories: Iterable[str] = (),
        frame_indices: Iterable[int] = (),
    ) -> dict[str, Any]:
        mode = str(mode or "default").strip().lower()
        if mode not in {"default", "reproducible"}:
            raise HTTPException(status_code=422, detail="导出模式必须为 default 或 reproducible")
        include = frozenset(str(item) for item in include_categories)
        allowed_categories = frozenset({"program", "ecir", "resources", "ocr", "parameters", "implementation"})
        if include - allowed_categories:
            raise HTTPException(status_code=422, detail="高级导出包含未知隐私类别")
        if mode == "default" and include:
            raise HTTPException(status_code=422, detail="默认导出不能包含分析输入快照")
        if mode == "reproducible" and not include:
            raise HTTPException(status_code=422, detail="可重现导出必须逐类确认要包含的输入")

        session_dir = cls.session_dir(project_path, session_id)
        summary = cls._session_summary(session_dir)
        if summary.get("status") in {"recording", "starting", "stopping"}:
            raise HTTPException(status_code=409, detail="活动录制不能导出")
        reports = []
        requested_ids = [str(item) for item in analysis_run_ids]
        if requested_ids:
            reports = [cls.analysis_report(project_path, session_id, item) for item in requested_ids]
        else:
            reports = cls.list_analysis_reports(project_path, session_id)
        requested_frames = sorted({int(item) for item in frame_indices if int(item) > 0})
        all_frames, frame_index_issues = cls.read_jsonl(session_dir / FRAME_INDEX)
        if frame_index_issues:
            raise HTTPException(status_code=422, detail="录制帧索引不完整，不能导出")
        available_frames = {
            int(item.get("sequence") or item.get("frame_sequence") or item.get("index") or 0): item
            for item in all_frames
        }
        unknown_frames = [item for item in requested_frames if item not in available_frames]
        if unknown_frames:
            raise HTTPException(status_code=422, detail=f"导出帧不存在：{unknown_frames[:5]}")
        selected_frames = (
            [available_frames[item] for item in requested_frames]
            if requested_frames else all_frames
        )

        export_root = session_dir / EXPORT_DIRECTORY
        export_root.mkdir(parents=True, exist_ok=True)
        seed = canonical_json_bytes({
            "session_id": session_id,
            "mode": mode,
            "reports": [item.get("analysis_run_id") for item in reports],
            "include": sorted(include),
            "frames": requested_frames or "all",
        })
        export_id = f"export_{sha256_bytes(seed)[:24]}"
        destination = _safe_child(export_root, f"{export_id}.zip")
        if destination.is_file():
            return {
                "export_id": export_id,
                "mode": mode,
                "path": str(destination),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "privacy": {
                    "mode": mode,
                    "session_id": session_id,
                    "immutable_existing_export": True,
                },
            }
        descriptor, temporary_name = tempfile.mkstemp(prefix=".export-", suffix=".zip", dir=export_root)
        os.close(descriptor)
        temporary = Path(temporary_name)
        entries: list[dict[str, Any]] = []
        privacy = {
            "schema_version": 1,
            "mode": mode,
            "session_id": session_id,
            "contains_recorded_pixels": True,
            "contains_project_program": "program" in include,
            "contains_ecir": "ecir" in include,
            "contains_resources": "resources" in include,
            "contains_ocr_dependencies": "ocr" in include,
            "contains_parameters": "parameters" in include,
            "contains_replay_implementation": "implementation" in include,
            "automatic_upload": False,
            "session_started_at": summary.get("started_at"),
            "session_stopped_at": summary.get("stopped_at"),
            "target_id": summary.get("target_id"),
            "target_kind": summary.get("target_kind"),
            "target_title": summary.get("target_title"),
            "recorded_frame_count": summary.get("frame_count"),
            "recorded_pixel_bytes": summary.get("total_bytes"),
            "exported_frame_count": len(selected_frames),
            "exported_frame_indices": requested_frames or "all",
            "exported_pixel_bytes": sum(int(item.get("bytes") or 0) for item in selected_frames),
            "warnings": ["录制画面可能包含账号、聊天或其他敏感内容"],
        }

        def write_path(archive: zipfile.ZipFile, arcname: str, path: Path) -> None:
            if path.is_symlink() or not path.is_file():
                return
            size = path.stat().st_size
            if size > cls.MAX_EXPORT_BYTES:
                raise HTTPException(status_code=413, detail="导出文件超过安全上限")
            archive.write(path, arcname)
            entries.append({"path": arcname, "size": size, "sha256": sha256_file(path)})

        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
                for name in (RECORDING_MANIFEST, FRAME_INDEX, SEGMENT_INDEX, MARKER_INDEX, DROP_INDEX, TERMINAL_RECORD):
                    path = session_dir / name
                    if path.is_file():
                        write_path(archive, f"recording/{name}", path)
                for frame in selected_frames:
                    relative_frame = str(frame.get("file") or "").replace("\\", "/").strip("/")
                    path = _safe_child(session_dir, *relative_frame.split("/"))
                    write_path(archive, f"recording/frames/{path.name}", path)
                for report in reports:
                    run_id = _safe_component(str(report.get("analysis_run_id") or ""), "分析记录标识")
                    path = session_dir / ANALYSIS_DIRECTORY / f"{run_id}.json"
                    write_path(archive, f"reports/{path.name}", path)
                    if mode != "reproducible":
                        continue
                    bundle_id = _safe_component(str(report.get("analysis_input_bundle_id") or ""), "分析输入包标识")
                    bundle_root = recording_data_root(project_path) / ANALYSIS_INPUT_DIRECTORY / bundle_id
                    manifest = cls.read_json(bundle_root / "manifest.json", {}) or {}
                    for component in manifest.get("components") or []:
                        category = str(component.get("category") or "")
                        if category not in include:
                            continue
                        relative = str(component.get("path") or "")
                        source = _safe_child(bundle_root, *relative.split("/"))
                        write_path(archive, f"analysis-inputs/{bundle_id}/{relative}", source)
                    manifest_bytes = canonical_json_bytes({
                        **manifest,
                        "exported_categories": sorted(include),
                        "reproducible": (
                            set(manifest.get("required_categories") or ()) - {"frames"}
                        ).issubset(include),
                    })
                    archive.writestr(f"analysis-inputs/{bundle_id}/manifest.json", manifest_bytes)
                    entries.append({
                        "path": f"analysis-inputs/{bundle_id}/manifest.json",
                        "size": len(manifest_bytes),
                        "sha256": sha256_bytes(manifest_bytes),
                    })
                privacy_bytes = canonical_json_bytes(privacy)
                archive.writestr("privacy-manifest.json", privacy_bytes)
                entries.append({"path": "privacy-manifest.json", "size": len(privacy_bytes), "sha256": sha256_bytes(privacy_bytes)})
                content_manifest = canonical_json_bytes({"schema_version": 1, "entries": sorted(entries, key=lambda item: item["path"])})
                archive.writestr("content-manifest.json", content_manifest)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "export_id": export_id,
            "mode": mode,
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "privacy": privacy,
        }

    @classmethod
    def export_path(
        cls, project_path: str, session_id: str, export_id: str
    ) -> Path:
        safe_id = _safe_component(export_id, "导出标识")
        session_dir = cls.session_dir(project_path, session_id)
        path = _safe_child(session_dir / EXPORT_DIRECTORY, f"{safe_id}.zip")
        if not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=404, detail="录制导出不存在")
        return path

    @classmethod
    def delete_session(cls, project_path: str, session_id: str) -> dict[str, Any]:
        session_dir = cls.session_dir(project_path, session_id)
        summary = cls._session_summary(session_dir)
        if summary.get("status") in {"recording", "starting", "stopping"}:
            raise HTTPException(status_code=409, detail="活动录制不能删除")
        if summary.get("locked"):
            raise HTTPException(status_code=409, detail="录制已被用户锁定，请先解锁")
        reports = cls.list_analysis_reports(project_path, session_id)
        if reports:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "recording.analysis_references_exist",
                    "message": "录制仍被分析报告引用",
                    "analysis_run_ids": [item.get("analysis_run_id") for item in reports],
                },
            )
        released = sum(path.stat().st_size for path in session_dir.rglob("*") if path.is_file() and not path.is_symlink())
        shutil.rmtree(session_dir)
        return {"deleted": True, "session_id": session_id, "released_bytes": released}


__all__ = [
    "ANALYSIS_DIRECTORY",
    "ANALYSIS_INPUT_DIRECTORY",
    "DROP_INDEX",
    "FRAME_INDEX",
    "MARKER_INDEX",
    "RECORDING_FORMAT_V6",
    "RECORDING_MANIFEST",
    "SEGMENT_INDEX",
    "TERMINAL_RECORD",
    "RecordedFrameV6",
    "RecordingStorageV6",
    "canonical_json_bytes",
    "recording_data_root",
    "sha256_bytes",
    "sha256_file",
]
