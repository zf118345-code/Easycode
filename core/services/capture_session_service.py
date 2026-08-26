"""Frozen-workspace capture sessions and asset transactions.

The capture UI is intentionally decoupled from the IDE window.  A global hotkey can
therefore create an immutable snapshot while the IDE is in the background, and a
small CaptureHost can edit that exact frame.  This module owns the short-lived
snapshot bytes and the reversible file transactions; canvas mutations remain in
the active IDE session and are acknowledged through the event bridge.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image

from core.security import assert_safe_path
from core.services.asset_service import AssetService


logger = logging.getLogger(__name__)


SNAPSHOT_TTL_SECONDS = 30 * 60
TRANSACTION_TTL_SECONDS = 2 * 60 * 60
SESSION_TTL_SECONDS = 90
MAX_RECTS = 32
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


@dataclass
class Snapshot:
    snapshot_id: str
    project_path: str
    project_id: str
    workspace_id: str
    workspace_generation: int
    png: bytes
    width: int
    height: int
    region: list[int]
    backend: str
    session_id: str = ''
    source: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class AssetTransaction:
    transaction_id: str
    project_path: str
    project_id: str
    workspace_id: str
    workspace_generation: int
    created_files: list[str]
    overwritten: dict[str, bytes]
    registry_before: bytes | None
    created_at: float = field(default_factory=time.time)
    undone: bool = False


class CaptureSessionService:
    _lock = threading.RLock()
    _trigger_lock = threading.Lock()
    _ui_sessions: dict[str, dict[str, Any]] = {}
    _snapshots: dict[str, Snapshot] = {}
    _transactions: dict[str, AssetTransaction] = {}
    _pending_actions: dict[str, dict[str, Any]] = {}
    _native_process: subprocess.Popen | None = None
    _native_host_title: str = ''
    _native_launch_error: str = ''
    _active_snapshot_id: str | None = None

    @staticmethod
    def _replace_bytes(path: str, content: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = f'{path}.capture-restore-{uuid.uuid4().hex}.tmp'
        try:
            Path(temporary).write_bytes(content)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    @classmethod
    def _cleanup(cls) -> None:
        now = time.time()
        cls._snapshots = {
            key: item for key, item in cls._snapshots.items()
            if now - item.created_at <= SNAPSHOT_TTL_SECONDS
        }
        cls._transactions = {
            key: item for key, item in cls._transactions.items()
            if now - item.created_at <= TRANSACTION_TTL_SECONDS
        }
        cls._ui_sessions = {
            key: item for key, item in cls._ui_sessions.items()
            if now - float(item.get('last_seen_at', 0)) <= SESSION_TTL_SECONDS
        }

    @classmethod
    def register_ui_session(cls, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get('session_id') or '').strip()
        project_path = os.path.abspath(str(payload.get('project_path') or '').strip())
        if not session_id:
            raise HTTPException(status_code=400, detail='缺少 IDE 会话标识')
        if not project_path or not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='当前项目路径无效')
        now = time.time()
        record = {
            **payload,
            'session_id': session_id,
            'project_path': project_path,
            'last_seen_at': now,
            'last_focus_at': float(payload.get('last_focus_at') or now),
        }
        with cls._lock:
            cls._cleanup()
            cls._ui_sessions[session_id] = record
        return {'ok': True, 'session_id': session_id}

    @classmethod
    def unregister_ui_session(cls, session_id: str) -> dict[str, Any]:
        with cls._lock:
            cls._ui_sessions.pop(str(session_id or ''), None)
        return {'ok': True}

    @classmethod
    def active_ui_session(cls) -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            if not cls._ui_sessions:
                raise HTTPException(status_code=409, detail='没有可用的 IDE 项目会话')
            sessions = sorted(
                cls._ui_sessions.values(),
                key=lambda item: (float(item.get('last_focus_at', 0)), float(item.get('last_seen_at', 0))),
                reverse=True,
            )
            active = dict(sessions[0])
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

        try:
            bound_path = project_workspace_manager.require(
                str(active.get('workspace_id') or ''),
                int(active.get('workspace_generation') or -1),
                writable=True,
            )
        except (WorkspaceError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f'IDE 项目会话已失效: {exc}') from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(active['project_path'])):
            raise HTTPException(status_code=409, detail='IDE 捕获会话与当前项目不一致')
        state = str(active.get('execution_state') or 'idle')
        if state in {'running', 'paused'}:
            raise HTTPException(status_code=409, detail='请先停止当前任务')
        if bool(active.get('recording_active')):
            raise HTTPException(status_code=409, detail='请先停止逐帧录制')
        return active

    @classmethod
    def create_snapshot(
        cls,
        project_path: str,
        *,
        session_id: str = '',
        include_image: bool = True,
    ) -> dict[str, Any]:
        from core.services.workspace_service import WorkspaceService

        project_path = os.path.abspath(str(project_path or ''))
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

        active = project_workspace_manager.active()
        try:
            if not active:
                raise WorkspaceError('当前没有打开项目')
            bound_path = project_workspace_manager.require(
                str(active.get('workspace_id') or ''),
                int(active.get('generation') or -1),
                writable=True,
            )
        except (WorkspaceError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(project_path)):
            raise HTTPException(status_code=409, detail='截图请求不属于当前工作区')
        result = WorkspaceService.capture_frozen_snapshot(project_path)
        png = result.pop('_png')
        snapshot_id = f'snap_{uuid.uuid4().hex}'
        item = Snapshot(
            snapshot_id=snapshot_id,
            project_path=project_path,
            project_id=str(active.get('project_id') or ''),
            workspace_id=str(active['workspace_id']),
            workspace_generation=int(active['generation']),
            png=png,
            width=int(result['width']),
            height=int(result['height']),
            region=list(result.get('region') or [0, 0, result['width'], result['height']]),
            backend=str(result.get('backend') or 'unknown'),
            session_id=session_id,
        )
        with cls._lock:
            cls._cleanup()
            cls._snapshots[snapshot_id] = item
            cls._active_snapshot_id = snapshot_id
        payload = {
            'snapshot_id': snapshot_id,
            'session_id': session_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'expires_in': SNAPSHOT_TTL_SECONDS,
        }
        if include_image:
            payload['image'] = base64.b64encode(png).decode('ascii')
        return payload

    @classmethod
    def create_recording_snapshot(
        cls,
        project_path: str,
        recording_session_id: str,
        frame_index: int,
        *,
        session_id: str = '',
        include_image: bool = True,
    ) -> dict[str, Any]:
        """Register a historical frame as a normal immutable capture credential."""
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager
        from core.services.recording_replay_service import recording_replay_service

        project_path = os.path.abspath(str(project_path or ''))
        active = project_workspace_manager.active()
        try:
            if not active:
                raise WorkspaceError('当前没有打开项目')
            bound_path = project_workspace_manager.require(
                str(active.get('workspace_id') or ''), int(active.get('generation') or -1), writable=True,
            )
        except (WorkspaceError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(bound_path)) != os.path.normcase(os.path.realpath(project_path)):
            raise HTTPException(status_code=409, detail='历史帧不属于当前工作区')

        frame = recording_replay_service.resolve_frame(project_path, recording_session_id, frame_index)
        png = Path(frame.path).read_bytes()
        try:
            with Image.open(io.BytesIO(png)) as image:
                width, height = image.size
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f'录制帧无法解码: {exc}') from exc
        raw_region = frame.record.get('screen_region')
        if isinstance(raw_region, list) and len(raw_region) == 4:
            region = [int(value) for value in raw_region]
        else:
            region = [0, 0, int(width), int(height)]
        if region[2] - region[0] != width or region[3] - region[1] != height:
            region = [region[0], region[1], region[0] + int(width), region[1] + int(height)]

        snapshot_id = f'snap_{uuid.uuid4().hex}'
        source = {
            'kind': 'recording',
            'recording_session_id': recording_session_id,
            'frame_index': int(frame_index),
            'captured_at': frame.record.get('captured_at', ''),
        }
        item = Snapshot(
            snapshot_id=snapshot_id,
            project_path=project_path,
            project_id=str(active.get('project_id') or ''),
            workspace_id=str(active['workspace_id']),
            workspace_generation=int(active['generation']),
            png=png,
            width=int(width),
            height=int(height),
            region=region,
            backend='recording_replay',
            session_id=session_id,
            source=source,
        )
        with cls._lock:
            cls._cleanup()
            if cls._active_snapshot_id and cls._active_snapshot_id in cls._snapshots:
                raise HTTPException(status_code=409, detail='请先退出当前截图捕获模式')
            cls._snapshots[snapshot_id] = item
            cls._active_snapshot_id = snapshot_id
        payload = {
            'snapshot_id': snapshot_id,
            'session_id': session_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'expires_in': SNAPSHOT_TTL_SECONDS,
            'source': source,
        }
        if include_image:
            payload['image'] = base64.b64encode(png).decode('ascii')
        return payload

    @classmethod
    def get_snapshot(cls, snapshot_id: str, *, include_image: bool = True) -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            item = cls._snapshots.get(snapshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail='冻结帧已过期，请按 R 重新捕获')
        result = {
            'snapshot_id': item.snapshot_id,
            'width': item.width,
            'height': item.height,
            'region': item.region,
            'backend': item.backend,
            'coordinate_space': 'workspace_px',
            'reference_size': [item.width, item.height],
            'session_id': item.session_id,
            'project_id': item.project_id,
            # 独立 Capture WebView 没有 IDE 页面内存中的工作区身份。冻结帧是
            # 不可猜测且已绑定工作区的短期凭据，用它把相同身份交给资源管理器，
            # 后续目录/缩略图请求才能走与 IDE 完全相同的并发保护。
            'workspace_id': item.workspace_id,
            'workspace_generation': item.workspace_generation,
            'source': item.source,
        }
        if item.session_id:
            with cls._lock:
                session = dict(cls._ui_sessions.get(item.session_id) or {})
            result.update({
                'project_path': item.project_path,
                'project_name': session.get('project_name') or os.path.basename(item.project_path),
                'target_name': session.get('target_name') or '',
                'capture_context': session.get('capture_context') or {},
            })
        if include_image:
            result['image'] = base64.b64encode(item.png).decode('ascii')
        return result

    @classmethod
    def is_capture_active(cls) -> bool:
        with cls._lock:
            cls._cleanup()
            return bool(cls._active_snapshot_id and cls._active_snapshot_id in cls._snapshots)

    @classmethod
    def close_capture(cls, snapshot_id: str = '') -> dict[str, Any]:
        with cls._lock:
            if not snapshot_id or cls._active_snapshot_id == snapshot_id:
                cls._active_snapshot_id = None
        return {'ok': True}

    @classmethod
    def prewarm_native_host(cls) -> dict[str, Any]:
        """Start the resident native overlay while the IDE is idle.

        Compilation only occurs in source checkouts and only when the C# sources
        are newer than the cached executable.  No window is shown here.
        """
        from core.services.native_capture_overlay import native_capture_overlay

        native_capture_overlay.prewarm()
        with cls._lock:
            sessions = sorted(
                cls._ui_sessions.values(),
                key=lambda item: (float(item.get('last_focus_at', 0)), float(item.get('last_seen_at', 0))),
                reverse=True,
            )
            origin = str(sessions[0].get('origin') or '') if sessions else ''
        warm_result = native_capture_overlay.warm_resource_manager(origin) if origin else {
            'ok': False,
            'message': '尚未注册可用于预热的 IDE 页面',
        }
        with cls._lock:
            cls._native_process = native_capture_overlay.process
            cls._native_launch_error = native_capture_overlay.last_error
        return {
            'ok': native_capture_overlay.is_alive(),
            'resident': native_capture_overlay.is_alive(),
            'resource_manager_ready': bool(warm_result.get('ok')),
            'message': str(warm_result.get('message') or native_capture_overlay.last_error or ''),
        }

    @classmethod
    def _validate_rects(cls, rects: list[Any], snapshot: Snapshot) -> list[list[int]]:
        if not isinstance(rects, list) or not rects:
            raise HTTPException(status_code=400, detail='请先框选至少一个有效范围')
        if len(rects) > MAX_RECTS:
            raise HTTPException(status_code=400, detail=f'单个页面最多允许 {MAX_RECTS} 个特征范围')
        clean: list[list[int]] = []
        for raw in rects:
            if not isinstance(raw, (list, tuple)) or len(raw) != 4:
                raise HTTPException(status_code=400, detail='框选范围格式无效')
            try:
                x, y, width, height = [int(value) for value in raw]
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail='框选范围必须为整数') from exc
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise HTTPException(status_code=400, detail='框选范围必须位于工作面板内')
            if x + width > snapshot.width or y + height > snapshot.height:
                raise HTTPException(status_code=400, detail='框选范围超出冻结工作面板')
            clean.append([x, y, width, height])
        return clean

    @staticmethod
    def _validate_prefix(prefix: str) -> str:
        value = str(prefix or '').strip()
        if value.lower().endswith('.png'):
            value = value[:-4].rstrip()
        if not value:
            return ''
        if _INVALID_FILENAME.search(value) or value.endswith(('.', ' ')):
            raise HTTPException(status_code=400, detail='文件名包含 Windows 不允许的字符')
        if value.upper() in _RESERVED_NAMES:
            raise HTTPException(status_code=400, detail=f'“{value}”是 Windows 保留文件名')
        return value

    @staticmethod
    def _next_numbered_names(directory: str, prefix: str, count: int) -> list[str]:
        existing = {entry.name.casefold() for entry in Path(directory).glob('*.png')}
        names: list[str] = []
        number = 1
        while len(names) < count:
            suffix = f'{number:03d}' if number < 1000 else str(number)
            candidate = f'{prefix}{suffix}.png'
            if candidate.casefold() not in existing:
                names.append(candidate)
                existing.add(candidate.casefold())
            number += 1
        return names

    @staticmethod
    def _reference_hits(project_path: str, relative_path: str) -> list[dict[str, Any]]:
        template_key = relative_path.replace('\\', '/').removeprefix('templates/')
        try:
            registered = AssetService.resolve(project_path, template_key)
        except (FileNotFoundError, ValueError):
            return []
        asset_id = registered.get('asset_id')
        if not asset_id:
            return []
        needle = AssetService.reference(asset_id).casefold()
        hits: list[dict[str, Any]] = []
        for filename in ('workflow.json', 'topology.json'):
            path = os.path.join(project_path, filename)
            if not os.path.exists(path):
                continue
            try:
                text = Path(path).read_text(encoding='utf-8')
            except Exception:
                continue
            count = text.casefold().count(needle)
            if count:
                hits.append({'file': filename, 'count': count})
        return hits

    @classmethod
    def save_assets(cls, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(payload.get('snapshot_id') or '')
        with cls._lock:
            cls._cleanup()
            snapshot = cls._snapshots.get(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail='冻结帧已过期，请重新捕获')

        # The native overlay intentionally does not carry browser headers, so
        # bind its opaque snapshot back to the authoritative active workspace
        # before any project write. A snapshot from project A cannot write after
        # the IDE switches to project B.
        from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

        try:
            active_path = project_workspace_manager.require(
                snapshot.workspace_id,
                snapshot.workspace_generation,
                writable=True,
            )
        except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if os.path.normcase(os.path.realpath(active_path)) != os.path.normcase(os.path.realpath(snapshot.project_path)):
            raise HTTPException(status_code=409, detail='冻结帧属于已切换的旧项目，已拒绝保存')

        rects = cls._validate_rects(list(payload.get('rects') or []), snapshot)
        requested_category = str(payload.get('category') or 'image').strip().lower()
        if requested_category not in {'image', 'ocr', 'page'}:
            raise HTTPException(status_code=400, detail='资源分类必须为 image、ocr 或 page')

        templates_dir = os.path.join(snapshot.project_path, 'templates')
        relative_dir = str(payload.get('relative_dir') or requested_category).replace('\\', '/').strip('/')
        category = relative_dir.split('/', 1)[0].lower() if relative_dir else requested_category
        if category not in {'image', 'ocr', 'page'}:
            raise HTTPException(status_code=400, detail='资源必须保存到 image、ocr 或 page 根目录下')
        prefix = cls._validate_prefix(str(payload.get('prefix') or ''))
        collision = str(payload.get('collision') or 'ask')
        overwrite_confirmed = bool(payload.get('overwrite_confirmed'))

        target_dir = assert_safe_path(templates_dir, os.path.join(templates_dir, relative_dir))
        os.makedirs(target_dir, exist_ok=True)

        stamp = time.strftime('%Y%m%d_%H%M%S')
        if not prefix:
            prefix = f'{category}_{stamp}_feature_' if category == 'page' else f'{category}_{stamp}_'
            names = cls._next_numbered_names(target_dir, prefix, len(rects))
            if len(rects) == 1 and category != 'page':
                simple = f'{category}_{stamp}.png'
                if not os.path.exists(os.path.join(target_dir, simple)):
                    names = [simple]
        elif len(rects) > 1 or collision == 'sequence':
            names = cls._next_numbered_names(target_dir, prefix, len(rects))
        else:
            names = [f'{prefix}.png']

        paths = [assert_safe_path(templates_dir, os.path.join(target_dir, name)) for name in names]
        conflicts = []
        for path in paths:
            if os.path.exists(path):
                rel = os.path.relpath(path, snapshot.project_path).replace('\\', '/')
                conflicts.append({'path': rel, 'references': cls._reference_hits(snapshot.project_path, rel)})
        if conflicts and collision == 'ask':
            return {'ok': False, 'conflict': True, 'conflicts': conflicts, 'message': '目标文件已存在'}
        if conflicts and collision == 'cancel':
            raise HTTPException(status_code=409, detail='保存已取消，请修改文件名')
        if conflicts and collision == 'overwrite':
            referenced = [item for item in conflicts if item['references']]
            if referenced and not overwrite_confirmed:
                return {
                    'ok': False,
                    'conflict': True,
                    'requires_reference_confirmation': True,
                    'conflicts': conflicts,
                    'message': '资源已被流程引用，覆盖会改变所有引用位置',
                }
        elif conflicts:
            raise HTTPException(status_code=409, detail='目标文件已存在且未允许覆盖')

        image = Image.open(io.BytesIO(snapshot.png)).convert('RGB')
        registry_path = AssetService.registry_path(snapshot.project_path)
        registry_before = Path(registry_path).read_bytes() if os.path.exists(registry_path) else None
        asset_records: list[dict[str, Any]] = []
        created: list[str] = []
        overwritten: dict[str, bytes] = {}
        temp_paths: list[str] = []
        try:
            for path, rect in zip(paths, rects, strict=True):
                if os.path.exists(path):
                    overwritten[path] = Path(path).read_bytes()
                x, y, width, height = rect
                cropped = image.crop((x, y, x + width, y + height))
                temp_path = f'{path}.capture-{uuid.uuid4().hex}.tmp'
                cropped.save(temp_path, format='PNG')
                temp_paths.append(temp_path)
            for temp_path, path in zip(temp_paths, paths, strict=True):
                os.replace(temp_path, path)
                created.append(path)
            asset_records = AssetService.register_files(snapshot.project_path, [
                {
                    'relative_path': os.path.relpath(path, templates_dir).replace('\\', '/'),
                    'kind': category,
                    'capture': {
                        'region': rect,
                        'reference_size': [snapshot.width, snapshot.height],
                        'coordinate_space': 'workspace_px',
                        'snapshot_id': snapshot.snapshot_id,
                    },
                }
                for path, rect in zip(paths, rects, strict=True)
            ])
        except Exception as exc:
            for temp_path in temp_paths:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
            for path in created:
                try:
                    if path in overwritten:
                        cls._replace_bytes(path, overwritten[path])
                    elif os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
            if registry_before is None:
                if os.path.exists(registry_path):
                    try:
                        os.remove(registry_path)
                    except OSError:
                        pass
            else:
                cls._replace_bytes(registry_path, registry_before)
            raise HTTPException(status_code=500, detail=f'资源事务保存失败，已回滚: {exc}') from exc

        transaction_id = f'asset_tx_{uuid.uuid4().hex}'
        tx = AssetTransaction(
            transaction_id=transaction_id,
            project_path=snapshot.project_path,
            project_id=snapshot.project_id,
            workspace_id=snapshot.workspace_id,
            workspace_generation=snapshot.workspace_generation,
            created_files=created,
            overwritten=overwritten,
            registry_before=registry_before,
        )
        with cls._lock:
            cls._transactions[transaction_id] = tx
        project_workspace_manager.acknowledge(snapshot.workspace_id, snapshot.workspace_generation)
        files = [os.path.relpath(path, snapshot.project_path).replace('\\', '/') for path in paths]
        return {
            'ok': True,
            'transaction_id': transaction_id,
            'files': files,
            'template_keys': [
                os.path.splitext(os.path.relpath(path, os.path.join(snapshot.project_path, 'templates')).replace('\\', '/'))[0]
                for path in paths
            ],
            'asset_ids': [record['id'] for record in asset_records],
            'asset_refs': [AssetService.reference(record['id']) for record in asset_records],
            'rects': rects,
            'reference_size': [snapshot.width, snapshot.height],
        }

    @classmethod
    def undo_assets(cls, transaction_id: str) -> dict[str, Any]:
        with cls._lock:
            cls._cleanup()
            tx = cls._transactions.get(str(transaction_id or ''))
            if tx is None:
                raise HTTPException(status_code=404, detail='资源事务不存在或已过期')
            if tx.undone:
                return {'ok': True, 'already_undone': True}
            from core.services.project_workspace_service import WorkspaceError, project_workspace_manager

            try:
                active_path = project_workspace_manager.require(
                    tx.workspace_id,
                    tx.workspace_generation,
                    writable=True,
                )
            except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if os.path.normcase(os.path.realpath(active_path)) != os.path.normcase(os.path.realpath(tx.project_path)):
                raise HTTPException(status_code=409, detail='资源事务属于已切换的旧项目，已拒绝撤销')
            registry_path = AssetService.registry_path(tx.project_path)
            files_before = {
                path: (Path(path).read_bytes() if os.path.exists(path) else None)
                for path in tx.created_files
            }
            registry_current = Path(registry_path).read_bytes() if os.path.exists(registry_path) else None
            try:
                for path in tx.created_files:
                    if path in tx.overwritten:
                        cls._replace_bytes(path, tx.overwritten[path])
                    elif os.path.exists(path):
                        os.remove(path)
                if tx.registry_before is None:
                    if os.path.exists(registry_path):
                        os.remove(registry_path)
                else:
                    cls._replace_bytes(registry_path, tx.registry_before)
            except Exception as exc:
                # Restore the state from immediately before undo, so Ctrl+Z is
                # retryable and never leaves half of an asset batch reverted.
                for path, content in files_before.items():
                    try:
                        if content is None:
                            if os.path.exists(path):
                                os.remove(path)
                        else:
                            cls._replace_bytes(path, content)
                    except OSError:
                        pass
                try:
                    if registry_current is None:
                        if os.path.exists(registry_path):
                            os.remove(registry_path)
                    else:
                        cls._replace_bytes(registry_path, registry_current)
                except OSError:
                    pass
                raise HTTPException(status_code=500, detail=f'资源撤销失败，已恢复撤销前状态: {exc}') from exc
            tx.undone = True
            project_workspace_manager.acknowledge(tx.workspace_id, tx.workspace_generation)
            return {
                'ok': True,
                'restored': len(tx.overwritten),
                'deleted': len(tx.created_files) - len(tx.overwritten),
            }

    @classmethod
    def request_ide_action(cls, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        from core.services import capture_mode

        request_id = f'capture_req_{uuid.uuid4().hex}'
        done = threading.Event()
        pending = {'event': done, 'result': None}
        with cls._lock:
            cls._pending_actions[request_id] = pending
        capture_mode.publish_event({
            'event': 'capture-command',
            'request_id': request_id,
            **payload,
        })
        if not done.wait(max(1.0, float(timeout))):
            with cls._lock:
                cls._pending_actions.pop(request_id, None)
            operation_id = str(payload.get('operation_id') or '')
            if operation_id and payload.get('kind') not in {'undo', 'rollback_operation'}:
                # SSE preserves publish order. The IDE serializes capture commands,
                # so a late original commit is immediately compensated instead of
                # leaving a node that references assets already rolled back by Host.
                capture_mode.publish_event({
                    'event': 'capture-command',
                    'request_id': f'capture_rollback_{uuid.uuid4().hex}',
                    **payload,
                    'kind': 'rollback_operation',
                    'operation_id': operation_id,
                })
            raise HTTPException(status_code=504, detail='IDE 未响应捕获操作，请确认项目仍处于打开状态')
        with cls._lock:
            result = pending.get('result') or {'ok': False, 'message': 'IDE 返回了空结果'}
            cls._pending_actions.pop(request_id, None)
        return result

    @classmethod
    def acknowledge_ide_action(cls, request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with cls._lock:
            pending = cls._pending_actions.get(str(request_id or ''))
            if pending is None:
                raise HTTPException(status_code=404, detail='捕获操作请求不存在或已超时')
            pending['result'] = result
            pending['event'].set()
        return {'ok': True}

    @classmethod
    def trigger_recording_capture(cls, recording_session_id: str, frame_index: int) -> dict[str, Any]:
        """Open a historical frame without activating or recapturing the target window."""
        with cls._trigger_lock:
            from core.services import capture_mode
            from core.services.execution_service import ExecutionService
            from core.services.frame_recording_service import frame_recording_service

            session = cls.active_ui_session()
            if ExecutionService.has_active_execution():
                raise HTTPException(status_code=409, detail='请先停止当前任务')
            if frame_recording_service.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先停止逐帧录制')
            if capture_mode.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先退出控件捕获模式')
            snapshot = cls.create_recording_snapshot(
                session['project_path'], recording_session_id, frame_index,
                session_id=session['session_id'], include_image=False,
            )
            if not cls._launch_native_host(session, snapshot):
                with cls._lock:
                    cls._snapshots.pop(snapshot['snapshot_id'], None)
                    if cls._active_snapshot_id == snapshot['snapshot_id']:
                        cls._active_snapshot_id = None
                raise HTTPException(
                    status_code=409,
                    detail=f'桌面捕获宿主启动失败：{cls._native_launch_error or "未知错误"}',
                )
            capture_mode.publish_event({
                'event': 'screenshot-capture',
                'session_id': session['session_id'],
                'snapshot': snapshot,
                'capture_context': session.get('capture_context') or {},
                'project_name': session.get('project_name') or os.path.basename(session['project_path']),
                'target_name': f'历史帧 #{int(frame_index)}',
                'native_host': True,
                'source': snapshot.get('source'),
            })
            return {'ok': True, 'native_host': True, **snapshot}

    @classmethod
    def trigger_global_capture(cls, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Called from the RegisterHotKey worker; never blocks that window thread."""
        with cls._trigger_lock:
            return cls._trigger_global_capture_locked(options or {})

    @classmethod
    def _trigger_global_capture_locked(cls, options: dict[str, Any] | None = None) -> dict[str, Any]:
        started_at = time.perf_counter()
        session: dict[str, Any] = {}
        options = options or {}
        field_capture = options.get('field_capture')
        if field_capture is not None and not isinstance(field_capture, dict):
            raise HTTPException(status_code=400, detail='属性捕获请求格式无效')
        try:
            from core.services import capture_mode
            from core.services.execution_service import ExecutionService
            from core.services.frame_recording_service import frame_recording_service

            session = cls.active_ui_session()
            if field_capture:
                request_id = str(field_capture.get('request_id') or '').strip()
                selection_mode = str(field_capture.get('selection_mode') or '').strip()
                category = str(field_capture.get('category') or '').strip()
                if not request_id or selection_mode not in {'point', 'region', 'asset'}:
                    raise HTTPException(status_code=400, detail='属性捕获请求缺少必要参数')
                if selection_mode == 'asset' and category not in {'image', 'ocr', 'page'}:
                    raise HTTPException(status_code=400, detail='属性捕获资源分类无效')
                field_capture = {
                    'requestId': request_id,
                    'selectionMode': selection_mode,
                    'category': category,
                    'maxRects': max(1, min(MAX_RECTS, int(field_capture.get('max_rects') or 1))),
                    'title': str(field_capture.get('title') or '属性捕获'),
                }
                session = dict(session)
                session_context = dict(session.get('capture_context') or {})
                session_context['fieldCapture'] = field_capture
                session['capture_context'] = session_context
            if ExecutionService.has_active_execution():
                raise HTTPException(status_code=409, detail='请先停止当前任务')
            if frame_recording_service.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先停止逐帧录制')
            if capture_mode.get_state().get('active'):
                raise HTTPException(status_code=409, detail='请先退出控件捕获模式')
            with cls._lock:
                active_id = cls._active_snapshot_id
                active = cls._snapshots.get(active_id or '')
                from core.services.native_capture_overlay import native_capture_overlay

                native_alive = native_capture_overlay.is_alive()
            if active is not None and field_capture:
                raise HTTPException(status_code=409, detail='请先退出当前截图捕获模式')
            if active is not None:
                focused = native_alive and cls._focus_native_host()
                usable_native = bool(native_alive and focused)
                if usable_native:
                    capture_mode.publish_event({
                        'event': 'screenshot-focus',
                        'session_id': active.session_id or session['session_id'],
                        'snapshot_id': active.snapshot_id,
                        'native_host': True,
                        'focused': True,
                    })
                    return {
                        'ok': True,
                        'already_active': True,
                        'native_host': True,
                        'focused': True,
                        'snapshot_id': active.snapshot_id,
                    }
                # A dead/unfocusable native window must not strand an active
                # snapshot and trigger the old browser-centered fallback.
                with cls._lock:
                    cls._active_snapshot_id = None
                    cls._snapshots.pop(active.snapshot_id, None)
            snapshot = cls.create_snapshot(
                session['project_path'],
                session_id=session['session_id'],
                include_image=False,
            )
            captured_at = time.perf_counter()
            launched = cls._launch_native_host(session, snapshot)
            if not launched:
                with cls._lock:
                    cls._snapshots.pop(snapshot['snapshot_id'], None)
                    if cls._active_snapshot_id == snapshot['snapshot_id']:
                        cls._active_snapshot_id = None
                reason = cls._native_launch_error or '未知启动错误'
                raise HTTPException(status_code=409, detail=f'桌面捕获宿主启动失败：{reason}')
            event_snapshot = {key: value for key, value in snapshot.items() if key != 'image'}
            payload = {
                'event': 'screenshot-capture',
                'session_id': session['session_id'],
                'snapshot': event_snapshot,
                'capture_context': session.get('capture_context') or {},
                'project_name': session.get('project_name') or os.path.basename(session['project_path']),
                'target_name': session.get('target_name') or '',
                'performance': {
                    'capture_ms': round((captured_at - started_at) * 1000, 1),
                    'host_ms': round((time.perf_counter() - captured_at) * 1000, 1),
                    'total_ms': round((time.perf_counter() - started_at) * 1000, 1),
                },
            }
            payload['native_host'] = True
            capture_mode.publish_event(payload)
            performance = payload['performance']
            logger.info(
                '[CaptureOverlay] ready backend=%s capture=%.1fms host=%.1fms total=%.1fms',
                snapshot.get('backend'),
                performance['capture_ms'],
                performance['host_ms'],
                performance['total_ms'],
            )
            return {
                'ok': True,
                'native_host': True,
                'snapshot_id': snapshot['snapshot_id'],
                'performance': performance,
            }
        except HTTPException as exc:
            from core.services import capture_mode

            capture_mode.publish_event({
                'event': 'screenshot-error',
                'session_id': session.get('session_id'),
                'message': str(exc.detail),
            })
            raise
        except Exception as exc:
            from core.services import capture_mode

            capture_mode.publish_event({
                'event': 'screenshot-error',
                'session_id': session.get('session_id'),
                'message': f'截图捕获失败: {exc}',
            })
            raise

    @classmethod
    def _focus_native_host(cls) -> bool:
        from core.services.native_capture_overlay import native_capture_overlay

        return native_capture_overlay.focus()

    @classmethod
    def _launch_native_host(cls, session: dict[str, Any], snapshot: dict[str, Any]) -> bool:
        from core.services.native_capture_overlay import native_capture_overlay

        cls._native_launch_error = ''
        origin = str(session.get('origin') or '').rstrip('/')
        if not origin.startswith(('http://', 'https://')):
            cls._native_launch_error = 'IDE 页面地址无效'
            return False
        with cls._lock:
            item = cls._snapshots.get(str(snapshot.get('snapshot_id') or ''))
        if item is None:
            cls._native_launch_error = '冻结帧在显示前已经失效'
            return False
        result = native_capture_overlay.show(session, snapshot, item.png)
        with cls._lock:
            cls._native_process = native_capture_overlay.process
            cls._native_launch_error = str(result.get('message') or native_capture_overlay.last_error or '')
        return bool(result.get('ok'))


capture_session_service = CaptureSessionService
