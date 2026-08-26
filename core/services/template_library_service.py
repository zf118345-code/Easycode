"""Transactional project template-library mutations.

The visual asset library is more than a directory of PNG files.  A mutation
may also touch the stable asset registry and both graph documents. This
service keeps those pieces in one transaction and moves
deleted material into a project-local recovery area instead of unlinking it.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.security import assert_safe_path, atomic_write_json
from core.services.asset_service import AssetService
from core.project_schema import PROJECT_FILE, TOPOLOGY_FILE, WORKFLOW_FILE, load_document, load_project_documents


class TemplateLibraryService:
    PROTECTED_ROOTS = frozenset(AssetService.DEFAULT_DIRECTORIES)
    IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg'})
    _lock = threading.RLock()
    TRASH_MAX_AGE_DAYS = 30
    TRASH_MAX_BYTES = 2 * 1024 * 1024 * 1024

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    @classmethod
    def _normalize_library_path(cls, relative_path: str, *, allow_root: bool = False) -> str:
        value = str(relative_path or '').strip().replace('\\', '/').strip('/')
        if value.lower().startswith('templates/'):
            value = value[10:].strip('/')
        if not value and allow_root:
            return ''
        if not value:
            raise ValueError('资源路径不能为空')
        if any(part in {'', '.', '..'} for part in value.split('/')):
            raise ValueError('资源路径包含非法目录段')
        return value

    @classmethod
    def _full_path(cls, project_path: str, relative_path: str) -> str:
        root = AssetService.ensure_structure(project_path)
        target = os.path.join(root, relative_path.replace('/', os.sep))
        return assert_safe_path(root, target)

    @staticmethod
    def _read_json(path: str, default: dict[str, Any]) -> dict[str, Any]:
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else copy.deepcopy(default)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return copy.deepcopy(default)

    @staticmethod
    def _read_bytes(path: str) -> bytes | None:
        try:
            return Path(path).read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def _restore_bytes(path: str, content: bytes | None) -> None:
        if content is None:
            if os.path.exists(path):
                os.remove(path)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = f'{path}.restore-{uuid.uuid4().hex}.tmp'
        Path(temp).write_bytes(content)
        os.replace(temp, path)

    @classmethod
    def _project_documents(cls, project_path: str) -> tuple[str, str]:
        load_project_documents(project_path)
        return (
            os.path.join(project_path, WORKFLOW_FILE),
            os.path.join(project_path, TOPOLOGY_FILE),
        )

    @staticmethod
    def _is_under(path: str, prefix: str) -> bool:
        path_cf = path.replace('\\', '/').strip('/').casefold()
        prefix_cf = prefix.replace('\\', '/').strip('/').casefold()
        return path_cf == prefix_cf or path_cf.startswith(f'{prefix_cf}/')

    @classmethod
    def _matching_records(
        cls,
        registry: dict[str, Any],
        source_relative: str,
        is_directory: bool,
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for asset_id, record in registry.get('assets', {}).items():
            if not isinstance(record, dict):
                continue
            path = str(record.get('path') or '').replace('\\', '/').strip('/')
            matched = cls._is_under(path, source_relative) if is_directory else path.casefold() == source_relative.casefold()
            if matched:
                result[asset_id] = record
        return result

    @classmethod
    def _matches_reference(
        cls,
        value: Any,
        source_relative: str,
        is_directory: bool,
        asset_ids: set[str],
    ) -> bool:
        raw = str(value or '').strip()
        if not raw:
            return False
        asset_id = AssetService.asset_id_from_reference(raw)
        return bool(asset_id and asset_id in asset_ids)

    @staticmethod
    def _reset_recorded_coordinates(container: dict[str, Any], prefix: str = '') -> None:
        if f'{prefix}region_type' in container:
            container[f'{prefix}region_type'] = 'fullwindow'
        for key in (f'{prefix}region_value', f'{prefix}region', f'{prefix}crop_rect'):
            if key in container:
                container[key] = [0, 0, 0, 0]
        if f'{prefix}region_reference_size' in container:
            container[f'{prefix}region_reference_size'] = [0, 0]

    @classmethod
    def _mutate_graph(
        cls,
        graph: dict[str, Any],
        canvas: str,
        source_relative: str,
        is_directory: bool,
        asset_ids: set[str],
        new_relative: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        hits: list[dict[str, Any]] = []
        changed = False

        def walk(value: Any, path: str, task: dict[str, Any], node: dict[str, Any]) -> None:
            nonlocal changed
            if isinstance(value, dict):
                for key, child in list(value.items()):
                    child_path = f'{path}.{key}' if path else key
                    if str(key).endswith('image_source') and cls._matches_reference(
                        child, source_relative, is_directory, asset_ids
                    ):
                        old_value = str(child)
                        action = 'cleared'
                        if new_relative is None:
                            value[key] = ''
                            prefix = str(key).removesuffix('image_source')
                            cls._reset_recorded_coordinates(value, prefix)
                        else:
                            action = 'stable'
                        hits.append({
                            'canvas': canvas,
                            'task_id': task.get('task_id', ''),
                            'task_name': task.get('task_name', ''),
                            'node_id': node.get('node_id', ''),
                            'node_name': node.get('node_name', ''),
                            'property_path': child_path,
                            'reference': old_value,
                            'action': action,
                        })
                        changed = changed or action == 'cleared'
                    else:
                        walk(child, child_path, task, node)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f'{path}[{index}]', task, node)

        owners: list[tuple[dict[str, Any], list[Any]]] = []
        if isinstance(graph.get('main_graph'), dict):
            owners.append(({'task_id': 'main', 'task_name': '主流程'}, graph['main_graph'].get('nodes', [])))
            for function in graph.get('functions', []):
                if not isinstance(function, dict):
                    continue
                owners.append((
                    {
                        'task_id': function.get('function_id', ''),
                        'task_name': function.get('name', ''),
                    },
                    (function.get('graph') or {}).get('nodes', []),
                ))
        elif isinstance(graph.get('nodes'), list):
            owners.append(({'task_id': 'page_map', 'task_name': '页面地图'}, graph.get('nodes', [])))
        for owner, nodes in owners:
            for node in nodes:
                if isinstance(node, dict):
                    walk(node.get('params', {}), 'params', owner, node)
        return hits, changed

    @classmethod
    def _load_state(cls, project_path: str, source_relative: str) -> dict[str, Any]:
        source_full = cls._full_path(project_path, source_relative)
        if not os.path.exists(source_full):
            raise FileNotFoundError(f'资源不存在: {source_relative}')
        is_directory = os.path.isdir(source_full)
        registry = AssetService.load_registry(project_path)
        records = cls._matching_records(registry, source_relative, is_directory)
        workflow_path, topology_path = cls._project_documents(project_path)
        workflow = cls._read_json(workflow_path, {'main_graph': {'nodes': [], 'edges': []}, 'functions': []})
        topology = cls._read_json(topology_path, {'nodes': [], 'edges': []})
        workflow_hits, _ = cls._mutate_graph(
            copy.deepcopy(workflow), 'workflow', source_relative, is_directory, set(records)
        )
        topology_hits, _ = cls._mutate_graph(
            copy.deepcopy(topology), 'topology', source_relative, is_directory, set(records)
        )
        files = []
        if is_directory:
            for base, _, names in os.walk(source_full):
                for name in names:
                    suffix = os.path.relpath(os.path.join(base, name), source_full).replace('\\', '/')
                    files.append('/'.join((source_relative, suffix)))
        else:
            files = [source_relative]
        return {
            'source_full': source_full,
            'source_relative': source_relative,
            'is_directory': is_directory,
            'registry': registry,
            'records': records,
            'workflow_path': workflow_path,
            'topology_path': topology_path,
            'workflow': workflow,
            'topology': topology,
            'files': sorted(files, key=str.casefold),
            'references': workflow_hits + topology_hits,
        }

    @classmethod
    def inspect(cls, project_path: str, relative_path: str) -> dict[str, Any]:
        source_relative = cls._normalize_library_path(relative_path)
        with cls._lock:
            state = cls._load_state(project_path, source_relative)
        unique_nodes = {
            (hit['canvas'], hit['task_id'], hit['node_id'])
            for hit in state['references']
        }
        return {
            'path': source_relative,
            'entry_type': 'directory' if state['is_directory'] else 'file',
            'protected': source_relative.casefold() in {item.casefold() for item in cls.PROTECTED_ROOTS},
            'file_count': len(state['files']),
            'asset_count': len(state['records']),
            'reference_count': len(state['references']),
            'node_count': len(unique_nodes),
            'references': state['references'],
        }

    @classmethod
    def _assert_mutable_source(cls, source_relative: str) -> None:
        if source_relative.casefold() in {item.casefold() for item in cls.PROTECTED_ROOTS}:
            raise PermissionError(f'默认资源目录不能删除、移动或重命名: {source_relative}')

    @classmethod
    def _validate_destination_parent(cls, project_path: str, parent_path: str) -> tuple[str, str]:
        parent_relative = cls._normalize_library_path(parent_path)
        top = parent_relative.split('/', 1)[0].casefold()
        if top not in {item.casefold() for item in cls.PROTECTED_ROOTS}:
            raise ValueError('目标目录必须位于 image、ocr 或 page 分类内')
        parent_full = cls._full_path(project_path, parent_relative)
        if not os.path.isdir(parent_full):
            raise FileNotFoundError(f'目标文件夹不存在: {parent_relative}')
        return parent_relative, parent_full

    @staticmethod
    def _validate_name(name: str) -> str:
        value = str(name or '').strip()
        if not value:
            raise ValueError('名称不能为空')
        if value in {'.', '..'} or re.search(r'[<>:"/\\|?*]', value) or value.endswith(('.', ' ')):
            raise ValueError('名称包含 Windows 不允许的字符')
        return value

    @classmethod
    def _write_mutated_state(cls, state: dict[str, Any]) -> None:
        AssetService.save_registry(state['project_path'], state['registry'])
        atomic_write_json(state['workflow_path'], state['workflow'])
        atomic_write_json(state['topology_path'], state['topology'])
        cls._increment_project_revision(state['project_path'])

    @staticmethod
    def _increment_project_revision(project_path: str) -> int:
        meta = load_document(project_path, PROJECT_FILE)
        meta['revision'] = int(meta.get('revision', 0)) + 1
        atomic_write_json(os.path.join(project_path, PROJECT_FILE), meta)
        return meta['revision']

    @staticmethod
    def _capture_project_snapshot(project_path: str, reason: str) -> None:
        try:
            from core.services.snapshot_service import SnapshotService

            SnapshotService.capture_current(project_path, reason)
        except Exception:
            # The project mutation is already committed and recoverable. A
            # history retention failure must not report that it was rolled back.
            pass

    @classmethod
    def _transaction_root(cls, project_path: str) -> str:
        return os.path.join(os.path.abspath(project_path), '.easycode', 'resource-transactions')

    @classmethod
    def _document_paths(cls, project_path: str) -> dict[str, str]:
        return {
            'templates/assets.json': AssetService.registry_path(project_path),
            PROJECT_FILE: os.path.join(project_path, PROJECT_FILE),
            WORKFLOW_FILE: os.path.join(project_path, WORKFLOW_FILE),
            TOPOLOGY_FILE: os.path.join(project_path, TOPOLOGY_FILE),
        }

    @classmethod
    def _backup_documents(cls, project_path: str, transaction_root: str) -> None:
        for relative, source in cls._document_paths(project_path).items():
            if not os.path.isfile(source):
                raise FileNotFoundError(f'资源事务缺少项目文档: {relative}')
            destination = os.path.join(transaction_root, 'before', relative.replace('/', os.sep))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            import shutil

            shutil.copy2(source, destination)

    @classmethod
    def _restore_documents(cls, project_path: str, transaction_root: str) -> None:
        for relative, destination in cls._document_paths(project_path).items():
            backup = os.path.join(transaction_root, 'before', relative.replace('/', os.sep))
            if not os.path.isfile(backup):
                raise FileNotFoundError(f'资源事务恢复文件缺失: {relative}')
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            import shutil

            shutil.copy2(backup, destination)

    @classmethod
    def _rollback_path_move(cls, source: str, destination: str) -> None:
        source_exists = os.path.exists(source)
        destination_exists = os.path.exists(destination)
        if source_exists and destination_exists:
            raise RuntimeError('资源事务恢复发现源位置和目标位置同时存在，已停止以避免覆盖')
        if destination_exists and not source_exists:
            os.makedirs(os.path.dirname(source), exist_ok=True)
            os.replace(destination, source)

    @classmethod
    def recover_pending(cls, project_path: str) -> dict[str, int]:
        """Recover resource operations that did not reach an acknowledged commit."""
        recovered = 0
        finalized = 0
        project_path = os.path.abspath(project_path)
        with cls._lock, AssetService._registry_lock:
            transaction_root = cls._transaction_root(project_path)
            if os.path.isdir(transaction_root):
                for name in sorted(os.listdir(transaction_root), key=str.casefold):
                    root = os.path.join(transaction_root, name)
                    manifest_path = os.path.join(root, 'manifest.json')
                    if not os.path.isfile(manifest_path):
                        continue
                    manifest = cls._read_json(manifest_path, {})
                    operation = str(manifest.get('operation') or '')
                    state = str(manifest.get('state') or '')
                    if operation not in {'move', 'restore'} or state not in {'prepared', 'committed'}:
                        raise ValueError(f'资源事务日志无效: {name}')
                    if operation == 'move':
                        source = cls._full_path(project_path, cls._normalize_library_path(manifest.get('source_path')))
                        destination = cls._full_path(
                            project_path, cls._normalize_library_path(manifest.get('destination_path'))
                        )
                        if state == 'prepared':
                            cls._rollback_path_move(source, destination)
                            cls._restore_documents(project_path, root)
                            recovered += 1
                    else:
                        trash_id = str(manifest.get('trash_id') or '')
                        trash_root = os.path.join(cls._trash_root(project_path), os.path.basename(trash_id))
                        original_path = cls._normalize_library_path(manifest.get('original_path'))
                        destination = cls._full_path(project_path, original_path)
                        payload = os.path.join(trash_root, 'templates', original_path.replace('/', os.sep))
                        if state == 'prepared':
                            cls._rollback_path_move(payload, destination)
                            cls._restore_documents(project_path, root)
                            recovered += 1
                        else:
                            import shutil

                            shutil.rmtree(trash_root, ignore_errors=True)
                            finalized += 1
                    import shutil

                    shutil.rmtree(root, ignore_errors=True)

            trash_root = cls._trash_root(project_path)
            if os.path.isdir(trash_root):
                for name in sorted(os.listdir(trash_root), key=str.casefold):
                    root = os.path.join(trash_root, name)
                    manifest_path = os.path.join(root, 'manifest.json')
                    if not os.path.isfile(manifest_path):
                        continue
                    manifest = cls._read_json(manifest_path, {})
                    state = str(manifest.get('state') or '')
                    if state == 'committed':
                        import shutil

                        shutil.rmtree(os.path.join(root, 'before'), ignore_errors=True)
                        continue
                    if state != 'prepared' or manifest.get('operation') != 'delete':
                        raise ValueError(f'资源回收日志无效: {name}')
                    original_path = cls._normalize_library_path(manifest.get('original_path'))
                    destination = cls._full_path(project_path, original_path)
                    payload = os.path.join(root, 'templates', original_path.replace('/', os.sep))
                    cls._rollback_path_move(destination, payload)
                    cls._restore_documents(project_path, root)
                    import shutil

                    shutil.rmtree(root, ignore_errors=True)
                    recovered += 1
        return {'recovered': recovered, 'finalized': finalized}

    @classmethod
    def _trash_root(cls, project_path: str) -> str:
        return os.path.join(os.path.abspath(project_path), '.easycode', 'resource-trash')

    @classmethod
    def _trash_entries(cls, project_path: str) -> list[dict[str, Any]]:
        root = cls._trash_root(project_path)
        if not os.path.isdir(root):
            return []
        entries: list[dict[str, Any]] = []
        for transaction_id in os.listdir(root):
            transaction_root = os.path.join(root, transaction_id)
            manifest_path = os.path.join(transaction_root, 'manifest.json')
            if not os.path.isdir(transaction_root) or not os.path.isfile(manifest_path):
                continue
            try:
                manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
                original_path = cls._normalize_library_path(str(manifest.get('original_path') or ''))
                deleted_at = datetime.fromisoformat(str(manifest.get('deleted_at')).replace('Z', '+00:00'))
                if deleted_at.tzinfo is None:
                    deleted_at = deleted_at.replace(tzinfo=timezone.utc)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            payload_root = os.path.join(transaction_root, 'templates', original_path.replace('/', os.sep))
            size = 0
            if os.path.isfile(payload_root):
                size = os.path.getsize(payload_root)
            elif os.path.isdir(payload_root):
                for base, _, names in os.walk(payload_root):
                    for name in names:
                        try:
                            size += os.path.getsize(os.path.join(base, name))
                        except OSError:
                            pass
            destination = cls._full_path(project_path, original_path)
            entries.append({
                **manifest,
                'transaction_id': transaction_id,
                'deleted_at': deleted_at.isoformat(timespec='seconds'),
                'size_bytes': size,
                'restorable': os.path.exists(payload_root) and not os.path.exists(destination),
                '_root': transaction_root,
                '_payload': payload_root,
                '_deleted_at': deleted_at,
            })
        return sorted(entries, key=lambda item: item['_deleted_at'], reverse=True)

    @classmethod
    def list_trash(cls, project_path: str) -> dict[str, Any]:
        with cls._lock:
            from core.services.project_workspace_service import project_workspace_manager

            active = project_workspace_manager.active()
            may_recover = not active
            if active:
                may_recover = (
                    not bool(active.get('read_only'))
                    and project_workspace_manager.path_key(active.get('project_path', ''))
                    == project_workspace_manager.path_key(project_path)
                )
            if may_recover and not project_workspace_manager._lock_owned_by_other_live_instance(project_path):
                cls.recover_pending(project_path)
            entries = cls._trash_entries(project_path)
        public = [
            {key: value for key, value in item.items() if not key.startswith('_')}
            for item in entries
        ]
        return {
            'entries': public,
            'total_bytes': sum(int(item.get('size_bytes') or 0) for item in public),
            'retention_days': cls.TRASH_MAX_AGE_DAYS,
            'max_bytes': cls.TRASH_MAX_BYTES,
        }

    @classmethod
    def _prune_trash(cls, project_path: str, preserve_id: str = '') -> None:
        entries = cls._trash_entries(project_path)
        cutoff = datetime.now(timezone.utc) - timedelta(days=cls.TRASH_MAX_AGE_DAYS)
        total = sum(int(item.get('size_bytes') or 0) for item in entries)
        # Oldest entries are removed first.  Never prune the transaction that
        # was just returned to the caller, even when a single item exceeds the cap.
        for item in reversed(entries):
            expired = item['_deleted_at'] < cutoff
            over_limit = total > cls.TRASH_MAX_BYTES
            if item['transaction_id'] == preserve_id or not (expired or over_limit):
                continue
            size = int(item.get('size_bytes') or 0)
            import shutil

            shutil.rmtree(item['_root'], ignore_errors=True)
            total = max(0, total - size)

    @classmethod
    def restore(cls, project_path: str, transaction_id: str) -> dict[str, Any]:
        safe_id = os.path.basename(str(transaction_id or ''))
        if safe_id != transaction_id or not safe_id.startswith('trash_'):
            raise ValueError('资源回收记录 ID 无效')
        with cls._lock, AssetService._registry_lock:
            cls.recover_pending(project_path)
            match = next(
                (item for item in cls._trash_entries(project_path) if item['transaction_id'] == safe_id),
                None,
            )
            if not match:
                raise FileNotFoundError(f'资源回收记录不存在: {safe_id}')
            original_path = cls._normalize_library_path(str(match.get('original_path') or ''))
            destination = cls._full_path(project_path, original_path)
            if os.path.exists(destination):
                raise FileExistsError(f'原位置已有同名资源，请先移动或重命名现有内容: {original_path}')
            payload = match['_payload']
            if not os.path.exists(payload):
                raise FileNotFoundError('回收区中的资源文件已经不存在')
            registry_path = AssetService.registry_path(project_path)
            registry_backup = cls._read_bytes(registry_path)
            registry = AssetService.load_registry(project_path)
            records = match.get('asset_records') if isinstance(match.get('asset_records'), dict) else {}
            operation_id = f'restore_{uuid.uuid4().hex}'
            operation_root = os.path.join(cls._transaction_root(project_path), operation_id)
            os.makedirs(operation_root, exist_ok=False)
            cls._backup_documents(project_path, operation_root)
            operation_manifest = {
                'schema_version': 1,
                'operation': 'restore',
                'state': 'prepared',
                'trash_id': safe_id,
                'original_path': original_path,
            }
            atomic_write_json(os.path.join(operation_root, 'manifest.json'), operation_manifest)
            moved = False
            try:
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                os.replace(payload, destination)
                moved = True
                for asset_id, record in records.items():
                    if asset_id in registry['assets']:
                        raise ValueError(f'资源 ID 已被占用，不能恢复: {asset_id}')
                    registry['assets'][asset_id] = record
                    registry.get('tombstones', {}).pop(asset_id, None)
                AssetService.save_registry(project_path, registry)
                cls._increment_project_revision(project_path)
                operation_manifest['state'] = 'committed'
                atomic_write_json(os.path.join(operation_root, 'manifest.json'), operation_manifest)
            except Exception:
                restored_documents = True
                try:
                    cls._restore_documents(project_path, operation_root)
                except Exception:
                    restored_documents = False
                    cls._restore_bytes(registry_path, registry_backup)
                if moved and os.path.exists(destination):
                    os.makedirs(os.path.dirname(payload), exist_ok=True)
                    os.replace(destination, payload)
                import shutil

                if restored_documents:
                    shutil.rmtree(operation_root, ignore_errors=True)
                raise
            import shutil

            # The resource and registry commit is complete.  A cleanup failure
            # must not roll the committed restore back or corrupt the manifest.
            shutil.rmtree(match['_root'], ignore_errors=True)
            shutil.rmtree(operation_root, ignore_errors=True)
            cls._capture_project_snapshot(project_path, 'restore_resource')
        return {
            'status': 'success',
            'operation': 'restore',
            'trash_id': safe_id,
            'path': original_path,
            'asset_count': len(records),
            'references_restored': 0,
        }

    @classmethod
    def sanitize_tombstoned_graph(
        cls,
        project_path: str,
        graph: dict[str, Any],
        canvas: str,
    ) -> list[dict[str, Any]]:
        """Prevent a stale editor window from reviving deleted references."""
        cls.recover_pending(project_path)
        registry = AssetService.load_registry(project_path)
        hits: list[dict[str, Any]] = []
        for tombstone in registry.get('tombstones', {}).values():
            if not isinstance(tombstone, dict):
                continue
            asset_id = str(tombstone.get('asset_id') or '')
            current_hits, _ = cls._mutate_graph(
                graph,
                canvas,
                '',
                False,
                {asset_id} if asset_id else set(),
            )
            hits.extend(current_hits)
        return hits

    @classmethod
    def delete(cls, project_path: str, relative_path: str) -> dict[str, Any]:
        source_relative = cls._normalize_library_path(relative_path)
        cls._assert_mutable_source(source_relative)
        with cls._lock, AssetService._registry_lock:
            cls.recover_pending(project_path)
            state = cls._load_state(project_path, source_relative)
            state['project_path'] = project_path
            asset_ids = set(state['records'])
            workflow_hits, _ = cls._mutate_graph(
                state['workflow'], 'workflow', source_relative, state['is_directory'], asset_ids
            )
            topology_hits, _ = cls._mutate_graph(
                state['topology'], 'topology', source_relative, state['is_directory'], asset_ids
            )
            for asset_id in asset_ids:
                state['registry'].get('assets', {}).pop(asset_id, None)
            tombstones = state['registry'].setdefault('tombstones', {})
            for asset_id, record in state['records'].items():
                tombstones[asset_id] = {
                    'asset_id': asset_id,
                    'path': str(record.get('path') or ''),
                    'deleted_at': cls._now(),
                }

            transaction_id = f'trash_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}'
            trash_root = os.path.join(project_path, '.easycode', 'resource-trash', transaction_id)
            trash_target = os.path.join(trash_root, 'templates', source_relative.replace('/', os.sep))
            os.makedirs(os.path.dirname(trash_target), exist_ok=True)
            cls._backup_documents(project_path, trash_root)
            manifest = {
                'schema_version': 1,
                'transaction_id': transaction_id,
                'operation': 'delete',
                'state': 'prepared',
                'deleted_at': cls._now(),
                'original_path': source_relative,
                'entry_type': 'directory' if state['is_directory'] else 'file',
                'asset_records': state['records'],
                'references': workflow_hits + topology_hits,
            }
            atomic_write_json(os.path.join(trash_root, 'manifest.json'), manifest)
            backups = {
                path: cls._read_bytes(path)
                for path in (
                    AssetService.registry_path(project_path),
                    state['workflow_path'], state['topology_path'],
                )
            }
            moved = False
            try:
                os.replace(state['source_full'], trash_target)
                moved = True
                cls._write_mutated_state(state)
                manifest['state'] = 'committed'
                atomic_write_json(os.path.join(trash_root, 'manifest.json'), manifest)
                import shutil

                shutil.rmtree(os.path.join(trash_root, 'before'), ignore_errors=True)
            except Exception:
                for path, content in backups.items():
                    try:
                        cls._restore_bytes(path, content)
                    except OSError:
                        pass
                if moved and os.path.exists(trash_target):
                    os.makedirs(os.path.dirname(state['source_full']), exist_ok=True)
                    os.replace(trash_target, state['source_full'])
                restored_documents = True
                try:
                    cls._restore_documents(project_path, trash_root)
                except Exception:
                    restored_documents = False
                import shutil

                if restored_documents:
                    shutil.rmtree(trash_root, ignore_errors=True)
                raise

            cls._prune_trash(project_path, preserve_id=transaction_id)
            cls._capture_project_snapshot(project_path, 'delete_resource')

        references = workflow_hits + topology_hits
        return {
            'status': 'success',
            'operation': 'delete',
            'path': source_relative,
            'trash_id': transaction_id,
            'file_count': len(state['files']),
            'asset_count': len(asset_ids),
            'reference_count': len(references),
            'node_count': len({(item['canvas'], item['task_id'], item['node_id']) for item in references}),
            'references': references,
        }

    @classmethod
    def move(
        cls,
        project_path: str,
        relative_path: str,
        target_parent_path: str,
        new_name: str = '',
    ) -> dict[str, Any]:
        source_relative = cls._normalize_library_path(relative_path)
        cls._assert_mutable_source(source_relative)
        with cls._lock, AssetService._registry_lock:
            cls.recover_pending(project_path)
            state = cls._load_state(project_path, source_relative)
            state['project_path'] = project_path
            parent_relative, _ = cls._validate_destination_parent(project_path, target_parent_path)
            name = cls._validate_name(new_name or os.path.basename(source_relative))
            if not state['is_directory']:
                old_extension = os.path.splitext(source_relative)[1]
                if not os.path.splitext(name)[1]:
                    name += old_extension
                if os.path.splitext(name)[1].lower() not in cls.IMAGE_EXTENSIONS:
                    raise ValueError('模板图片仅支持 PNG、JPG、JPEG')
            target_relative = '/'.join((parent_relative, name))
            target_full = cls._full_path(project_path, target_relative)
            if state['is_directory'] and cls._is_under(target_relative, source_relative):
                raise ValueError('不能把文件夹移动到自身或其子目录')
            if os.path.normcase(os.path.abspath(target_full)) == os.path.normcase(os.path.abspath(state['source_full'])):
                return {
                    'status': 'unchanged', 'operation': 'move',
                    'old_path': source_relative, 'new_path': target_relative,
                    'asset_count': len(state['records']), 'reference_count': 0, 'references': [],
                }
            if os.path.exists(target_full):
                raise FileExistsError(f'目标已存在: {target_relative}')

            asset_ids = set(state['records'])
            workflow_hits, _ = cls._mutate_graph(
                state['workflow'], 'workflow', source_relative, state['is_directory'], asset_ids, target_relative
            )
            topology_hits, _ = cls._mutate_graph(
                state['topology'], 'topology', source_relative, state['is_directory'], asset_ids, target_relative
            )
            for record in state['records'].values():
                old_path = str(record.get('path') or '').replace('\\', '/')
                suffix = old_path[len(source_relative):].lstrip('/') if state['is_directory'] else ''
                new_path = '/'.join(part for part in (target_relative, suffix) if part)
                record['path'] = new_path
                record['key'] = os.path.splitext(new_path)[0]
                record['kind'] = AssetService.infer_kind(new_path)
                if not state['is_directory']:
                    record['display_name'] = os.path.splitext(os.path.basename(new_path))[0]
                record['updated_at'] = cls._now()

            backups = {
                path: cls._read_bytes(path)
                for path in (
                    AssetService.registry_path(project_path),
                    state['workflow_path'], state['topology_path'],
                )
            }
            transaction_id = f'move_{uuid.uuid4().hex}'
            transaction_root = os.path.join(cls._transaction_root(project_path), transaction_id)
            os.makedirs(transaction_root, exist_ok=False)
            cls._backup_documents(project_path, transaction_root)
            transaction_manifest = {
                'schema_version': 1,
                'operation': 'move',
                'state': 'prepared',
                'source_path': source_relative,
                'destination_path': target_relative,
            }
            atomic_write_json(os.path.join(transaction_root, 'manifest.json'), transaction_manifest)
            moved = False
            try:
                os.makedirs(os.path.dirname(target_full), exist_ok=True)
                os.replace(state['source_full'], target_full)
                moved = True
                cls._write_mutated_state(state)
                transaction_manifest['state'] = 'committed'
                atomic_write_json(os.path.join(transaction_root, 'manifest.json'), transaction_manifest)
            except Exception:
                for path, content in backups.items():
                    try:
                        cls._restore_bytes(path, content)
                    except OSError:
                        pass
                if moved and os.path.exists(target_full):
                    os.makedirs(os.path.dirname(state['source_full']), exist_ok=True)
                    os.replace(target_full, state['source_full'])
                restored_documents = True
                try:
                    cls._restore_documents(project_path, transaction_root)
                except Exception:
                    restored_documents = False
                import shutil

                if restored_documents:
                    shutil.rmtree(transaction_root, ignore_errors=True)
                raise
            import shutil

            shutil.rmtree(transaction_root, ignore_errors=True)
            cls._capture_project_snapshot(project_path, 'move_resource')

        references = workflow_hits + topology_hits
        return {
            'status': 'success',
            'operation': 'move',
            'old_path': source_relative,
            'new_path': target_relative,
            'entry_type': 'directory' if state['is_directory'] else 'file',
            'file_count': len(state['files']),
            'asset_count': len(asset_ids),
            'reference_count': len(references),
            'references': references,
        }


template_library_service = TemplateLibraryService()
