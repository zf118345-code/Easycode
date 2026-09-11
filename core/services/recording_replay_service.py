"""Read-only frame-recording storage and timeline access.

Format-6 offline analysis lives in :mod:`core.vnext.replay`, where it is
linked to the reachable ProgramDocument bundle. This storage service must
not revive the retired page-topology evaluator.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _storage():
    # Keep this legacy compatibility facade importable without initializing
    # the complete format-6 IDE package.  Historical Capture calls it only
    # after a workspace has already been established.
    from core.vnext.recording_storage_v6 import RecordingStorageV6

    return RecordingStorageV6


@dataclass(frozen=True)
class RecordedFrame:
    session_id: str
    session_dir: str
    record: dict[str, Any]
    path: str


class RecordingReplayService:
    MAX_PAGE_SIZE = 500

    @staticmethod
    def _recordings_root(project_path: str) -> str:
        return str(_storage().recordings_root(project_path))

    @classmethod
    def _session_dir(cls, project_path: str, session_id: str) -> str:
        return str(_storage().session_dir(project_path, session_id))

    @staticmethod
    def _read_json(path: str, fallback=None):
        try:
            with open(path, encoding='utf-8') as stream:
                return json.load(stream)
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _read_frames(session_dir: str) -> list[dict[str, Any]]:
        records, _ = _storage().read_jsonl(Path(session_dir) / 'frames.jsonl')
        for index, record in enumerate(records, 1):
            record.setdefault('index', int(record.get('sequence') or index))
        return records

    @classmethod
    def list_sessions(cls, project_path: str) -> list[dict[str, Any]]:
        return _storage().list_sessions(project_path)

    @classmethod
    def list_frames(cls, project_path: str, session_id: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
        return _storage().list_frames(project_path, session_id, offset, limit)

    @classmethod
    def resolve_frame(cls, project_path: str, session_id: str, frame_index: int) -> RecordedFrame:
        frame = _storage().resolve_frame(project_path, session_id, frame_index)
        record = dict(frame.record)
        record.setdefault('index', int(record.get('sequence') or frame_index))
        return RecordedFrame(
            session_id=session_id,
            session_dir=str(frame.session_dir),
            record=record,
            path=str(frame.path),
        )

    @classmethod
    def frame_bytes(cls, project_path: str, session_id: str, frame_index: int) -> tuple[bytes, str]:
        return _storage().frame_bytes(project_path, session_id, frame_index)

    @classmethod
    def frame_thumbnail_bytes(cls, project_path: str, session_id: str, frame_index: int) -> bytes:
        return _storage().frame_thumbnail_bytes(project_path, session_id, frame_index)

    @staticmethod
    def _checksum_error(path: str, record: dict[str, Any]) -> str | None:
        expected = str(record.get('sha256') or '').strip().lower()
        if not expected:
            return None
        digest = hashlib.sha256()
        try:
            with open(path, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
        except OSError as exc:
            return f'帧读取失败: {exc}'
        actual = digest.hexdigest().lower()
        return None if actual == expected else f'帧校验失败: 期望 {expected[:12]}，实际 {actual[:12]}'

recording_replay_service = RecordingReplayService()
