"""Immutable, project-scoped build input snapshots."""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.project_schema import PROJECT_DOCUMENTS, PROJECT_FILE, load_project_documents
from core.security import atomic_write_json
from core.services.asset_service import AssetService


class BuildSnapshotService:
    @staticmethod
    def _cache_root(project_id: str) -> str:
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / '.easycode-app')
        return os.path.join(base, 'EasyCode', 'cache', project_id, 'build-snapshots')

    @staticmethod
    def _assert_plain_tree(path: str) -> None:
        for base, directories, files in os.walk(path):
            for name in [*directories, *files]:
                candidate = os.path.join(base, name)
                is_junction = bool(getattr(os.path, 'isjunction', lambda _path: False)(candidate))
                if os.path.islink(candidate) or is_junction:
                    raise ValueError(f'构建输入不允许包含符号链接或目录联接: {candidate}')

    @classmethod
    def create(cls, project_path: str) -> dict:
        documents = load_project_documents(project_path)
        AssetService.load_registry(project_path)
        meta = documents[PROJECT_FILE]
        project_id = str(meta['project_id'])
        revision = int(meta['revision'])
        root = cls._cache_root(project_id)
        os.makedirs(root, exist_ok=True)
        snapshot_id = f'r{revision}-{uuid.uuid4().hex[:10]}'
        target = os.path.join(root, snapshot_id)
        os.makedirs(target, exist_ok=False)
        try:
            for filename in PROJECT_DOCUMENTS:
                shutil.copy2(os.path.join(project_path, filename), os.path.join(target, filename))
            for directory in ('templates', 'scripts', 'capabilities'):
                source = os.path.join(project_path, directory)
                if not os.path.isdir(source):
                    continue
                cls._assert_plain_tree(source)
                shutil.copytree(source, os.path.join(target, directory))
            manifest = {
                'schema_version': 1,
                'snapshot_id': snapshot_id,
                'project_id': project_id,
                'revision': revision,
                'source_project': os.path.realpath(os.path.abspath(project_path)),
                'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            atomic_write_json(os.path.join(target, '.build-snapshot.json'), manifest)
            load_project_documents(target)
            AssetService.load_registry(target)
            return {'path': target, **manifest}
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    @staticmethod
    def remove(snapshot: dict | str) -> None:
        path = snapshot.get('path') if isinstance(snapshot, dict) else str(snapshot)
        if path and os.path.basename(path).startswith('r') and 'build-snapshots' in Path(path).parts:
            shutil.rmtree(path, ignore_errors=True)
