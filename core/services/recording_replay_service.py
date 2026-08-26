"""Read-only frame-recording timeline and offline visual regression services."""

from __future__ import annotations

import json
import io
import hashlib
import os
import time
import statistics
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from PIL import Image

import core.conditions  # noqa: F401 - register condition handlers
from core.models import Node
from core.node_executors.base.page_state import PageStateNodeExecutor
from core.security import assert_safe_path
from core.services.blueprint_service import BlueprintService


@dataclass(frozen=True)
class RecordedFrame:
    session_id: str
    session_dir: str
    record: dict[str, Any]
    path: str


class _OfflineContext:
    def __init__(self, project_path: str, image: Image.Image, *, diagnostics: bool = False):
        self.project_dir = project_path
        self._step_screen = image.convert('RGB')
        self.window_rect = (0, 0, self._step_screen.width, self._step_screen.height)
        self.window_hwnd = None
        self.is_emulator = False
        self.variables: dict[str, Any] = {}
        self.last_match_score = 0.0
        self.last_ocr_text = ''
        self.logs: list[dict[str, str]] = []
        self._diagnostics = bool(diagnostics)

    def log(self, message, level='info', **_kwargs):
        self.logs.append({'level': str(level or 'info'), 'message': str(message)})

    def get_setting(self, name, default=None):
        if name == 'diagnostic_full_page_evaluation':
            return self._diagnostics
        return default


class RecordingReplayService:
    MAX_PAGE_SIZE = 500

    @staticmethod
    def _recordings_root(project_path: str) -> str:
        project_path = os.path.abspath(str(project_path or ''))
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')
        root = assert_safe_path(project_path, os.path.join(project_path, 'recordings'))
        os.makedirs(root, exist_ok=True)
        return root

    @classmethod
    def _session_dir(cls, project_path: str, session_id: str) -> str:
        value = str(session_id or '').strip()
        allowed = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
        if not value or any(char not in allowed for char in value):
            raise HTTPException(status_code=400, detail='录制会话标识无效')
        root = cls._recordings_root(project_path)
        path = assert_safe_path(root, os.path.join(root, value))
        if not os.path.isdir(path):
            raise HTTPException(status_code=404, detail='录制会话不存在')
        return path

    @staticmethod
    def _read_json(path: str, fallback=None):
        try:
            with open(path, 'r', encoding='utf-8') as stream:
                return json.load(stream)
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _read_frames(session_dir: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            with open(os.path.join(session_dir, 'frames.jsonl'), 'r', encoding='utf-8') as stream:
                for line_number, raw in enumerate(stream, 1):
                    if not raw.strip():
                        continue
                    try:
                        record = json.loads(raw)
                    except json.JSONDecodeError:
                        # A crash can leave one partial trailing line. Valid
                        # frames before it must remain available.
                        continue
                    if not isinstance(record, dict) or not record.get('file'):
                        continue
                    record.setdefault('index', len(records) + 1)
                    record['_line'] = line_number
                    records.append(record)
        except FileNotFoundError:
            pass
        return records

    @classmethod
    def list_sessions(cls, project_path: str) -> list[dict[str, Any]]:
        root = cls._recordings_root(project_path)
        sessions = []
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            manifest = cls._read_json(os.path.join(entry.path, 'session.json'), {}) or {}
            records = cls._read_frames(entry.path)
            sessions.append({
                'session_id': entry.name,
                'started_at': manifest.get('started_at', ''),
                'stopped_at': manifest.get('stopped_at', ''),
                'status': manifest.get('status', 'unknown'),
                'stop_reason': manifest.get('stop_reason', ''),
                'target_title': manifest.get('target_title', ''),
                'capture_backend': manifest.get('capture_backend', ''),
                'frame_count': len(records),
                'total_bytes': sum(int(item.get('bytes') or 0) for item in records),
                'workspace_size': manifest.get('workspace_size') or (
                    [records[0].get('width'), records[0].get('height')] if records else []
                ),
            })
        return sorted(sessions, key=lambda item: item.get('started_at') or item['session_id'], reverse=True)

    @classmethod
    def list_frames(cls, project_path: str, session_id: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
        session_dir = cls._session_dir(project_path, session_id)
        records = cls._read_frames(session_dir)
        offset = max(0, int(offset or 0))
        limit = max(1, min(cls.MAX_PAGE_SIZE, int(limit or 200)))
        items = [{key: value for key, value in record.items() if not key.startswith('_')}
                 for record in records[offset:offset + limit]]
        return {'session_id': session_id, 'total': len(records), 'offset': offset, 'limit': limit, 'frames': items}

    @classmethod
    def resolve_frame(cls, project_path: str, session_id: str, frame_index: int) -> RecordedFrame:
        session_dir = cls._session_dir(project_path, session_id)
        wanted = int(frame_index or 0)
        record = next((item for item in cls._read_frames(session_dir) if int(item.get('index') or 0) == wanted), None)
        if record is None:
            raise HTTPException(status_code=404, detail=f'录制帧不存在: {wanted}')
        path = assert_safe_path(session_dir, os.path.join(session_dir, os.path.basename(str(record['file']))))
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail=f'录制帧文件缺失: {record["file"]}')
        return RecordedFrame(session_id=session_id, session_dir=session_dir, record=record, path=path)

    @classmethod
    def frame_bytes(cls, project_path: str, session_id: str, frame_index: int) -> tuple[bytes, str]:
        frame = cls.resolve_frame(project_path, session_id, frame_index)
        with open(frame.path, 'rb') as stream:
            return stream.read(), frame.path

    @classmethod
    def frame_thumbnail_bytes(cls, project_path: str, session_id: str, frame_index: int) -> bytes:
        frame = cls.resolve_frame(project_path, session_id, frame_index)
        with Image.open(frame.path) as source:
            image = source.convert('RGB')
            image.thumbnail((180, 110), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=72, optimize=True)
            return buffer.getvalue()

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

    @classmethod
    def _page_nodes(cls, project_path: str) -> list[tuple[dict[str, Any], Node]]:
        topology = BlueprintService.load_topology(project_path)
        nodes = []
        owner = {'task_id': 'page_map', 'task_name': '页面地图'}
        for raw_node in topology.get('nodes', []) or []:
            if not isinstance(raw_node, dict) or raw_node.get('node_type') != 'page_state':
                continue
            node = Node(
                node_id=str(raw_node.get('node_id') or ''),
                node_name=str(raw_node.get('node_name') or '页面节点'),
                node_type='page_state',
                params=dict(raw_node.get('params') or {}),
            )
            nodes.append((owner, node))
        return nodes

    @classmethod
    def _analyze_image(cls, project_path: str, image: Image.Image, page_nodes, *, diagnostics: bool = False):
        pages = []
        for task, node in page_nodes:
            context = _OfflineContext(project_path, image, diagnostics=diagnostics)
            page_started = time.perf_counter()
            result = PageStateNodeExecutor().execute(node, context)
            pages.append({
                'task_id': task.get('task_id'),
                'task_name': task.get('task_name'),
                'node_id': node.node_id,
                'node_name': node.node_name,
                'page_id': node.params.get('page_id', ''),
                'matched': bool(result.get('success')),
                'elapsed_ms': round((time.perf_counter() - page_started) * 1000, 2),
                'last_match_score': round(float(context.last_match_score or 0.0), 4),
                'last_ocr_text': context.last_ocr_text,
                'logs': context.logs,
            })
        pages.sort(key=lambda item: (not item['matched'], -item['last_match_score'], item['elapsed_ms']))
        return pages

    @classmethod
    def analyze_frame(cls, project_path: str, session_id: str, frame_index: int, *, diagnostics: bool = False) -> dict[str, Any]:
        frame = cls.resolve_frame(project_path, session_id, frame_index)
        checksum_error = cls._checksum_error(frame.path, frame.record)
        if checksum_error:
            raise HTTPException(status_code=422, detail=checksum_error)
        started = time.perf_counter()
        with Image.open(frame.path) as source:
            image = source.convert('RGB')
        pages = cls._analyze_image(project_path, image, cls._page_nodes(project_path), diagnostics=diagnostics)
        return {
            'session_id': session_id,
            'frame_index': int(frame_index),
            'width': image.width,
            'height': image.height,
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
            'matched_pages': [item for item in pages if item['matched']],
            'pages': pages,
        }

    @classmethod
    def analyze_session(
        cls,
        project_path: str,
        session_id: str,
        *,
        diagnostics: bool = False,
        changes_only: bool = False,
        change_threshold: float = 0.006,
        step: int = 1,
        max_frames: int = 10000,
    ) -> dict[str, Any]:
        session_dir = cls._session_dir(project_path, session_id)
        records = cls._read_frames(session_dir)
        step = max(1, int(step or 1))
        max_frames = max(1, min(10000, int(max_frames or 10000)))
        selected = []
        for record in records[::step]:
            if changes_only and float(record.get('change_score') or 0.0) < float(change_threshold or 0.006):
                continue
            selected.append(record)
            if len(selected) >= max_frames:
                break
        page_nodes = cls._page_nodes(project_path)
        started = time.perf_counter()
        frames = []
        coverage: dict[str, dict[str, Any]] = {
            node.node_id: {'node_id': node.node_id, 'node_name': node.node_name, 'matched_frames': 0, 'first_frame': None}
            for _, node in page_nodes
        }
        elapsed_values = []
        for record in selected:
            path = assert_safe_path(session_dir, os.path.join(session_dir, os.path.basename(str(record['file']))))
            if not os.path.isfile(path):
                frames.append({'frame_index': int(record.get('index') or 0), 'error': '帧文件缺失', 'matched_pages': []})
                continue
            checksum_error = cls._checksum_error(path, record)
            if checksum_error:
                frames.append({
                    'frame_index': int(record.get('index') or 0),
                    'error': checksum_error,
                    'matched_pages': [],
                })
                continue
            frame_started = time.perf_counter()
            try:
                with Image.open(path) as source:
                    image = source.convert('RGB')
            except Exception as exc:
                frames.append({
                    'frame_index': int(record.get('index') or 0),
                    'error': f'帧图片损坏: {exc}',
                    'matched_pages': [],
                })
                continue
            pages = cls._analyze_image(project_path, image, page_nodes, diagnostics=diagnostics)
            elapsed_ms = round((time.perf_counter() - frame_started) * 1000, 2)
            elapsed_values.append(elapsed_ms)
            matched = [page for page in pages if page['matched']]
            index = int(record.get('index') or 0)
            for page in matched:
                item = coverage.get(page['node_id'])
                if item is not None:
                    item['matched_frames'] += 1
                    if item['first_frame'] is None:
                        item['first_frame'] = index
            frames.append({
                'frame_index': index,
                'captured_at': record.get('captured_at'),
                'change_score': float(record.get('change_score') or 0.0),
                'elapsed_ms': elapsed_ms,
                'matched_pages': [{'node_id': page['node_id'], 'node_name': page['node_name']} for page in matched],
            })
        sorted_elapsed = sorted(elapsed_values)
        p95 = sorted_elapsed[min(len(sorted_elapsed) - 1, int(len(sorted_elapsed) * 0.95))] if sorted_elapsed else 0.0
        return {
            'session_id': session_id,
            'source_frame_count': len(records),
            'analyzed_frame_count': len(frames),
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
            'frame_analysis_p95_ms': round(float(p95), 2),
            'average_frame_analysis_ms': round(statistics.fmean(elapsed_values), 2) if elapsed_values else 0.0,
            'unmatched_frame_count': sum(1 for frame in frames if not frame.get('matched_pages')),
            'error_frame_count': sum(1 for frame in frames if frame.get('error')),
            'coverage': list(coverage.values()),
            'frames': frames,
        }


recording_replay_service = RecordingReplayService()
