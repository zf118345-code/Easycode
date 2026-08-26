"""Authoritative lifecycle manager for the single active EasyCode project.

The browser is a view of this state, never the source of truth.  Every
project-scoped request is bound to a short-lived workspace id and generation;
switching projects invalidates all delayed requests from the previous project.
"""

from __future__ import annotations

import json
import hashlib
import os
import platform
import shutil
import socket
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.project_schema import (
    PROJECT_DOCUMENTS,
    PROJECT_FILE,
    PROJECT_SCHEMA_VERSION,
    ProjectFormatError,
    load_document,
    load_project_documents,
    new_project_documents,
    new_project_id,
)
from core.security import atomic_write_json
from core.services.asset_service import AssetService


class WorkspaceError(RuntimeError):
    """A user-correctable workspace lifecycle error."""


@dataclass(frozen=True)
class WorkspaceSession:
    workspace_id: str
    generation: int
    project_id: str
    project_name: str
    project_path: str
    revision: int
    read_only: bool

    def public(self) -> dict[str, Any]:
        return asdict(self)


class ProjectWorkspaceManager:
    LOCK_RELATIVE_PATH = os.path.join('.easycode', 'workspace.lock')
    RESERVED_PATHS = frozenset((*PROJECT_DOCUMENTS, os.path.join('templates', 'assets.json')))

    def __init__(
        self,
        *,
        source_root: str | None = None,
        app_data_dir: str | None = None,
        process_id: int | None = None,
    ) -> None:
        default_root = Path(__file__).resolve().parents[2]
        self.source_root = self.canonicalize(source_root or str(default_root))
        local_app_data = os.environ.get('LOCALAPPDATA')
        default_app_data = Path(local_app_data) / 'EasyCode' if local_app_data else Path.home() / '.easycode-app'
        self.app_data_dir = self.canonicalize(app_data_dir or str(default_app_data))
        self.process_id = int(process_id or os.getpid())
        self.machine = socket.gethostname() or platform.node() or 'unknown'
        self.session_nonce = uuid.uuid4().hex
        self._mutex = threading.RLock()
        self._active: WorkspaceSession | None = None
        self._generation = 0
        self._activity_probe: Callable[[], list[str]] | None = None
        self._baseline_fingerprint: dict[str, str] = {}
        os.makedirs(self.app_data_dir, exist_ok=True)

    @staticmethod
    def canonicalize(path: str) -> str:
        raw = os.path.expandvars(os.path.expanduser(str(path or '').strip().strip('"')))
        if not raw:
            raise WorkspaceError('项目路径不能为空')
        return os.path.realpath(os.path.abspath(raw))

    @staticmethod
    def path_key(path: str) -> str:
        return os.path.normcase(os.path.normpath(ProjectWorkspaceManager.canonicalize(path)))

    @property
    def recent_path(self) -> str:
        return os.path.join(self.app_data_dir, 'recent-projects.json')

    @property
    def settings_path(self) -> str:
        return os.path.join(self.app_data_dir, 'settings.json')

    def set_activity_probe(self, probe: Callable[[], list[str]] | None) -> None:
        self._activity_probe = probe

    def blockers(self) -> list[str]:
        if self._activity_probe is None:
            return []
        try:
            return [str(item) for item in (self._activity_probe() or []) if str(item)]
        except Exception:
            return ['工作区活动状态暂时无法确认']

    def _assert_switch_allowed(self) -> None:
        blockers = self.blockers()
        if blockers:
            raise WorkspaceError(f'请先停止当前任务：{"、".join(blockers)}')

    def _assert_not_source_root(self, path: str) -> None:
        if self.path_key(path) == self.path_key(self.source_root):
            raise WorkspaceError('EasyCode 源码根目录不能作为脚本项目，请选择其子目录或其他文件夹')

    @classmethod
    def _workspace_fingerprint(cls, project_path: str) -> dict[str, str]:
        """Fingerprint user-editable project inputs, excluding generated state."""
        root = os.path.realpath(os.path.abspath(project_path))
        candidates: list[tuple[str, str]] = []
        for relative in (*PROJECT_DOCUMENTS, os.path.join('templates', 'assets.json')):
            candidates.append((relative.replace('\\', '/'), os.path.join(root, relative)))
        for directory in ('templates', 'scripts'):
            base = os.path.join(root, directory)
            if not os.path.isdir(base):
                continue
            for current, dirnames, filenames in os.walk(base):
                dirnames[:] = sorted(name for name in dirnames if not name.startswith('.'))
                for name in sorted(filenames):
                    full = os.path.join(current, name)
                    relative = os.path.relpath(full, root).replace('\\', '/')
                    if relative == 'templates/assets.json':
                        continue
                    candidates.append((relative, full))
        result: dict[str, str] = {}
        core_names = {name.replace('\\', '/') for name in (*PROJECT_DOCUMENTS, os.path.join('templates', 'assets.json'))}
        for relative, full in candidates:
            try:
                stat = os.stat(full)
                if relative in core_names:
                    digest = hashlib.sha256(Path(full).read_bytes()).hexdigest()
                    result[relative] = f'{stat.st_size}:{digest}'
                else:
                    result[relative] = f'{stat.st_size}:{stat.st_mtime_ns}'
            except FileNotFoundError:
                result[relative] = 'missing'
        return result

    @staticmethod
    def _probe_writable(path: str) -> bool:
        probe = os.path.join(path, f'.easycode-write-probe-{uuid.uuid4().hex}.tmp')
        try:
            with open(probe, 'x', encoding='utf-8') as stream:
                stream.write('ok')
            os.remove(probe)
            return True
        except OSError:
            try:
                if os.path.exists(probe):
                    os.remove(probe)
            except OSError:
                pass
            return False

    @staticmethod
    def _directory_entries(path: str) -> list[str]:
        return sorted(os.listdir(path), key=str.casefold)

    def inspect(self, project_path: str) -> dict[str, Any]:
        path = self.canonicalize(project_path)
        self._assert_not_source_root(path)
        result: dict[str, Any] = {
            'project_path': path,
            'exists': os.path.exists(path),
            'is_directory': os.path.isdir(path),
            'writable': False,
            'status': 'missing',
            'errors': [],
            'warnings': [],
            'entries': [],
            'requires_confirmation': False,
        }
        if not result['exists']:
            return result
        if not result['is_directory']:
            result['status'] = 'not_directory'
            result['errors'].append('项目路径必须是文件夹')
            return result
        result['entries'] = self._directory_entries(path)
        result['writable'] = self._probe_writable(path)
        present_reserved = [name for name in self.RESERVED_PATHS if os.path.exists(os.path.join(path, name))]
        if not present_reserved:
            result['status'] = 'empty' if not result['entries'] else 'uninitialized'
            result['requires_confirmation'] = bool(result['entries'])
            if not result['writable']:
                result['warnings'].append('目录不可写，只能预览，不能初始化或编辑')
            return result
        try:
            # Never touch a project while another live EasyCode instance owns
            # its writer lock. Recovery is safe only for this process, stale
            # locks, or currently unowned projects.
            if not self._lock_owned_by_other_live_instance(path):
                from core.services.template_library_service import TemplateLibraryService

                TemplateLibraryService.recover_pending(path)
            documents = load_project_documents(path)
            registry = AssetService.load_registry(path)
            if not os.path.isfile(AssetService.registry_path(path)):
                raise ProjectFormatError('缺少 templates/assets.json')
            missing_asset_roots = [
                name for name in AssetService.DEFAULT_DIRECTORIES
                if not os.path.isdir(os.path.join(AssetService.templates_dir(path), name))
            ]
            if missing_asset_roots:
                raise ProjectFormatError(f'缺少默认资源目录: {", ".join(missing_asset_roots)}')
            meta = documents[PROJECT_FILE]
            result.update({
                'status': 'valid',
                'valid': True,
                'schema_version': PROJECT_SCHEMA_VERSION,
                'project_id': meta['project_id'],
                'project_name': meta['project_name'],
                'revision': meta['revision'],
                'asset_count': len(registry.get('assets', {})),
            })
            if not result['writable']:
                result['status'] = 'read_only'
                result['warnings'].append('项目不可写，将以只读预览方式打开')
            return result
        except (ProjectFormatError, ValueError, OSError) as exc:
            result['status'] = 'invalid'
            result['valid'] = False
            result['errors'].append(str(exc))
            missing = [name for name in self.RESERVED_PATHS if not os.path.exists(os.path.join(path, name))]
            result['missing'] = sorted(missing)
            return result

    def initialize(self, project_path: str, project_name: str, *, confirm_nonempty: bool = False) -> dict[str, Any]:
        path = self.canonicalize(project_path)
        self._assert_not_source_root(path)
        created_root = False
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=False)
            created_root = True
        if not os.path.isdir(path):
            raise WorkspaceError('项目路径必须是文件夹')
        inspection = self.inspect(path)
        if inspection['status'] in {'valid', 'read_only'}:
            return inspection
        if inspection['status'] == 'invalid':
            raise WorkspaceError('目录包含冲突或损坏的 EasyCode 保留文件，不能初始化')
        if inspection['status'] == 'uninitialized' and not confirm_nonempty:
            raise WorkspaceError('该文件夹不是空目录，需要确认后才能初始化 EasyCode 项目')
        if not inspection['writable']:
            raise WorkspaceError('项目目录不可写，不能初始化')

        parent = os.path.dirname(path)
        staging = tempfile.mkdtemp(prefix='.easycode-init-', dir=parent)
        moved: list[str] = []
        try:
            for filename, payload in new_project_documents(project_name or os.path.basename(path)).items():
                atomic_write_json(os.path.join(staging, filename), payload)
            AssetService.ensure_structure(staging)
            load_project_documents(staging)
            AssetService.load_registry(staging)
            for name in os.listdir(staging):
                destination = os.path.join(path, name)
                if os.path.exists(destination):
                    raise WorkspaceError(f'初始化期间发现保留路径冲突: {name}')
                os.replace(os.path.join(staging, name), destination)
                moved.append(destination)
        except Exception:
            for destination in reversed(moved):
                try:
                    if os.path.isdir(destination):
                        shutil.rmtree(destination)
                    elif os.path.exists(destination):
                        os.remove(destination)
                except OSError:
                    pass
            if created_root:
                try:
                    os.rmdir(path)
                except OSError:
                    pass
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return self.inspect(path)

    def repair(self, project_path: str, *, confirmed: bool = False) -> dict[str, Any]:
        """Back up every reserved document, then rebuild only invalid pieces."""
        if not confirmed:
            raise WorkspaceError('修复项目需要明确确认')
        path = self.canonicalize(project_path)
        self._assert_not_source_root(path)
        inspection = self.inspect(path)
        if inspection['status'] != 'invalid':
            raise WorkspaceError('该目录不需要修复')
        if not inspection['writable']:
            raise WorkspaceError('项目目录不可写，不能修复')
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        recovery = os.path.join(path, '.easycode', 'recovery', f'repair-{stamp}-{uuid.uuid4().hex[:8]}')
        os.makedirs(recovery, exist_ok=False)
        for relative in self.RESERVED_PATHS:
            source = os.path.join(path, relative)
            if os.path.isfile(source):
                destination = os.path.join(recovery, relative)
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copy2(source, destination)

        defaults = new_project_documents(os.path.basename(path))
        for filename, default in defaults.items():
            target = os.path.join(path, filename)
            try:
                from core.project_schema import load_document

                load_document(path, filename)
            except (ProjectFormatError, OSError):
                atomic_write_json(target, default)
        try:
            AssetService.load_registry(path)
            if not os.path.isfile(AssetService.registry_path(path)):
                raise ValueError('missing')
        except (ValueError, OSError):
            AssetService.ensure_structure(path)
            AssetService.save_registry(path, AssetService.empty_registry())
        AssetService.ensure_structure(path)
        repaired = self.inspect(path)
        if repaired['status'] not in {'valid', 'read_only'}:
            raise WorkspaceError(f'项目修复后仍未通过校验，原文件已备份到 {recovery}')
        repaired['recovery_path'] = recovery
        return repaired

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _read_lock(self, project_path: str) -> dict[str, Any] | None:
        lock_path = os.path.join(project_path, self.LOCK_RELATIVE_PATH)
        if not os.path.isfile(lock_path):
            return None
        try:
            with open(lock_path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return {'invalid': True}

    def _acquire_lock(self, project_path: str) -> None:
        lock_path = os.path.join(project_path, self.LOCK_RELATIVE_PATH)
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        existing = self._read_lock(project_path)
        if existing:
            same_owner = (
                int(existing.get('pid') or 0) == self.process_id
                and existing.get('session_nonce') == self.session_nonce
            )
            if same_owner:
                return
            if existing.get('invalid') or not self._pid_alive(int(existing.get('pid') or 0)):
                try:
                    os.remove(lock_path)
                except OSError as exc:
                    raise WorkspaceError(f'失效项目锁无法清理: {exc}') from exc
            else:
                raise WorkspaceError(
                    f'项目已被另一个 EasyCode 实例打开（PID {existing.get("pid")}，{existing.get("machine", "未知机器")}）'
                )
        payload = {
            'pid': self.process_id,
            'machine': self.machine,
            'session_nonce': self.session_nonce,
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        try:
            with open(lock_path, 'x', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
        except FileExistsError as exc:
            raise WorkspaceError('项目刚刚被另一个 EasyCode 实例打开') from exc

    def _lock_owned_by_other_live_instance(self, project_path: str) -> bool:
        """Return True only for a valid lock whose owning process is alive."""
        existing = self._read_lock(project_path)
        if not existing or existing.get('invalid'):
            return False
        same_owner = (
            int(existing.get('pid') or 0) == self.process_id
            and existing.get('session_nonce') == self.session_nonce
        )
        return not same_owner and self._pid_alive(int(existing.get('pid') or 0))

    def _release_lock(self, project_path: str) -> None:
        lock_path = os.path.join(project_path, self.LOCK_RELATIVE_PATH)
        existing = self._read_lock(project_path)
        if not existing:
            return
        if (
            int(existing.get('pid') or 0) == self.process_id
            and existing.get('session_nonce') == self.session_nonce
        ):
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass

    def _load_recent(self) -> list[dict[str, Any]]:
        try:
            with open(self.recent_path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def recent_projects(self) -> list[dict[str, Any]]:
        records = self._load_recent()
        result = []
        for item in records:
            if not isinstance(item, dict) or not item.get('path'):
                continue
            path = self.canonicalize(item['path'])
            result.append({**item, 'path': path, 'missing': not os.path.isdir(path)})
        return result[:20]

    def _save_recent(self, session: WorkspaceSession) -> None:
        records = self._load_recent()
        current_key = self.path_key(session.project_path)
        records = [
            item for item in records
            if item.get('path')
            and self.path_key(item['path']) != current_key
            and item.get('project_id') != session.project_id
        ]
        records.insert(0, {
            'project_id': session.project_id,
            'name': session.project_name,
            'path': session.project_path,
            'last_opened_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        })
        atomic_write_json(self.recent_path, records[:20])

    def remove_recent(self, project_path: str) -> list[dict[str, Any]]:
        needle = self.path_key(project_path)
        records = [item for item in self._load_recent() if self.path_key(item.get('path', '.')) != needle]
        atomic_write_json(self.recent_path, records)
        return self.recent_projects()

    def _resolve_duplicate_identity(self, path: str, meta: dict[str, Any]) -> dict[str, Any]:
        same_id = [item for item in self._load_recent() if item.get('project_id') == meta.get('project_id')]
        for item in same_id:
            old_path = item.get('path')
            if not old_path or self.path_key(old_path) == self.path_key(path):
                continue
            if os.path.isdir(old_path):
                meta = dict(meta)
                meta['project_id'] = new_project_id()
                meta['revision'] = 0
                atomic_write_json(os.path.join(path, PROJECT_FILE), meta)
                for relative in (self.LOCK_RELATIVE_PATH, os.path.join('.easycode', 'runtime.db')):
                    candidate = os.path.join(path, relative)
                    try:
                        if os.path.isfile(candidate):
                            os.remove(candidate)
                    except OSError as exc:
                        raise WorkspaceError(f'项目副本身份初始化失败: {exc}') from exc
                break
        return meta

    def open(
        self,
        project_path: str,
        *,
        initialize: bool = False,
        confirm_nonempty: bool = False,
        project_name: str = '',
        allow_read_only: bool = True,
    ) -> dict[str, Any]:
        with self._mutex:
            path = self.canonicalize(project_path)
            if self._active and self.path_key(self._active.project_path) == self.path_key(path):
                return {'workspace': self._active.public(), 'inspection': self.inspect(path)}
            self._assert_switch_allowed()
            inspection = self.inspect(path)
            if inspection['status'] in {'missing', 'empty', 'uninitialized'}:
                if not initialize:
                    return {'workspace': None, 'inspection': inspection}
                inspection = self.initialize(
                    path,
                    project_name or os.path.basename(path),
                    confirm_nonempty=confirm_nonempty,
                )
            if inspection['status'] == 'invalid':
                raise WorkspaceError('项目文件不完整或已损坏，请先修复项目')
            read_only = inspection['status'] == 'read_only'
            locked_elsewhere = self._lock_owned_by_other_live_instance(path)
            if locked_elsewhere:
                if not allow_read_only:
                    existing = self._read_lock(path) or {}
                    raise WorkspaceError(
                        f'项目已被另一个 EasyCode 实例打开（PID {existing.get("pid")}，'
                        f'{existing.get("machine", "未知机器")}）'
                    )
                read_only = True
            if read_only and not allow_read_only:
                raise WorkspaceError('项目目录不可写')
            documents = load_project_documents(path)
            meta = documents[PROJECT_FILE]
            if not read_only:
                meta = self._resolve_duplicate_identity(path, meta)
            if not read_only:
                self._acquire_lock(path)
            previous = self._active
            self._generation += 1
            session = WorkspaceSession(
                workspace_id=f'workspace_{uuid.uuid4().hex}',
                generation=self._generation,
                project_id=str(meta['project_id']),
                project_name=str(meta['project_name']),
                project_path=path,
                revision=int(meta.get('revision', 0)),
                read_only=read_only,
            )
            self._active = session
            self._baseline_fingerprint = self._workspace_fingerprint(path)
            if previous and not previous.read_only:
                self._release_lock(previous.project_path)
            self._save_recent(session)
            return {'workspace': session.public(), 'inspection': self.inspect(path)}

    def active(self) -> dict[str, Any] | None:
        with self._mutex:
            return self._active.public() if self._active else None

    def require(self, workspace_id: str, generation: int, *, writable: bool = False) -> str:
        with self._mutex:
            session = self._active
            if session is None:
                raise WorkspaceError('当前没有打开项目')
            if workspace_id != session.workspace_id or int(generation) != session.generation:
                raise WorkspaceError('工作区已切换，此请求属于旧项目，已拒绝执行')
            if writable and session.read_only:
                raise WorkspaceError('项目以只读方式打开，不能修改或运行')
            return session.project_path

    def external_changes(self, workspace_id: str, generation: int) -> dict[str, Any]:
        path = self.require(workspace_id, generation)
        with self._mutex:
            current = self._workspace_fingerprint(path)
            baseline = dict(self._baseline_fingerprint)
        changed = sorted(
            relative for relative in set(current) | set(baseline)
            if current.get(relative) != baseline.get(relative)
        )
        identity_changed = False
        try:
            meta = load_document(path, PROJECT_FILE)
            identity_changed = str(meta.get('project_id') or '') != str(self._active.project_id if self._active else '')
        except (ProjectFormatError, OSError, ValueError):
            pass
        return {'changed': bool(changed), 'paths': changed, 'identity_changed': identity_changed}

    def acknowledge(self, workspace_id: str, generation: int) -> dict[str, Any]:
        path = self.require(workspace_id, generation)
        try:
            meta = load_document(path, PROJECT_FILE)
        except ProjectFormatError as exc:
            raise WorkspaceError(f'项目元数据已在外部损坏，请重新打开或修复项目: {exc}') from exc
        with self._mutex:
            if not self._active or str(meta['project_id']) != self._active.project_id:
                raise WorkspaceError('项目身份已在外部改变，请重新打开项目')
            name_changed = str(meta['project_name']) != self._active.project_name
            self._active = replace(
                self._active,
                project_name=str(meta['project_name']),
                revision=int(meta['revision']),
            )
            self._baseline_fingerprint = self._workspace_fingerprint(path)
            if name_changed:
                self._save_recent(self._active)
        return {'acknowledged': True, 'revision': int(meta['revision'])}

    def close(self) -> dict[str, Any]:
        with self._mutex:
            self._assert_switch_allowed()
            previous = self._active
            self._generation += 1
            self._active = None
            self._baseline_fingerprint = {}
            if previous and not previous.read_only:
                self._release_lock(previous.project_path)
            return {'closed': bool(previous), 'generation': self._generation}

    def shutdown(self) -> None:
        with self._mutex:
            previous = self._active
            self._active = None
            self._baseline_fingerprint = {}
            if previous and not previous.read_only:
                self._release_lock(previous.project_path)

    @staticmethod
    def choose_folder(title: str = '选择 EasyCode 项目文件夹') -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                return str(filedialog.askdirectory(title=title, mustexist=True) or '')
            finally:
                root.destroy()
        except Exception as exc:
            raise WorkspaceError(f'无法打开 Windows 文件夹选择器: {exc}') from exc

    @staticmethod
    def choose_file(title: str = '选择文件', extensions: list[str] | None = None) -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog

            normalized = []
            for extension in extensions or []:
                value = str(extension or '').strip().lower()
                if not value:
                    continue
                normalized.append(value if value.startswith('.') else f'.{value}')
            filetypes = []
            if normalized:
                filetypes.append(('支持的文件', ' '.join(f'*{extension}' for extension in normalized)))
            filetypes.append(('所有文件', '*.*'))

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                return str(filedialog.askopenfilename(title=title, filetypes=filetypes) or '')
            finally:
                root.destroy()
        except Exception as exc:
            raise WorkspaceError(f'无法打开 Windows 文件选择器: {exc}') from exc


project_workspace_manager = ProjectWorkspaceManager()
