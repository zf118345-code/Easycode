"""Project-local visual asset registry.

Image files remain ordinary files under ``templates/``.  Nodes refer to a
stable ``asset://<id>`` handle so reorganising a library does not couple graph
data to a physical filename.  ``templates/assets.json`` is deliberately small
and portable; it is the single source of truth for path, purpose and capture
metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.security import assert_safe_path, atomic_write_json


class AssetService:
    SCHEMA_VERSION = 2
    REFERENCE_PREFIX = 'asset://'
    REGISTRY_NAME = 'assets.json'
    DEFAULT_DIRECTORIES = ('image', 'ocr', 'page')
    VALID_KINDS = frozenset(DEFAULT_DIRECTORIES)
    _registry_lock = threading.RLock()

    @classmethod
    def templates_dir(cls, project_path: str) -> str:
        return os.path.abspath(os.path.join(project_path, 'templates'))

    @classmethod
    def registry_path(cls, project_path: str) -> str:
        return os.path.join(cls.templates_dir(project_path), cls.REGISTRY_NAME)

    @classmethod
    def ensure_structure(cls, project_path: str) -> str:
        root = cls.templates_dir(project_path)
        os.makedirs(root, exist_ok=True)
        for name in cls.DEFAULT_DIRECTORIES:
            os.makedirs(os.path.join(root, name), exist_ok=True)
        registry_path = os.path.join(root, cls.REGISTRY_NAME)
        with cls._registry_lock:
            if not os.path.exists(registry_path):
                atomic_write_json(registry_path, cls.empty_registry())
        return root

    @classmethod
    def empty_registry(cls) -> dict[str, Any]:
        return {'schema_version': cls.SCHEMA_VERSION, 'assets': {}, 'tombstones': {}}

    @classmethod
    def load_registry(cls, project_path: str) -> dict[str, Any]:
        path = cls.registry_path(project_path)
        if not os.path.isfile(path):
            return cls.empty_registry()
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'视觉资源索引已损坏: {path}') from exc
        if not isinstance(data, dict) or data.get('schema_version') != cls.SCHEMA_VERSION:
            raise ValueError(f'视觉资源索引版本无效: {path}')
        if not isinstance(data.get('assets'), dict) or not isinstance(data.get('tombstones'), dict):
            raise ValueError(f'视觉资源索引结构无效: {path}')
        return data

    @classmethod
    def save_registry(cls, project_path: str, registry: dict[str, Any]) -> None:
        if not isinstance(registry, dict):
            raise ValueError('视觉资源索引必须是对象')
        registry['schema_version'] = cls.SCHEMA_VERSION
        if not isinstance(registry.get('assets'), dict) or not isinstance(registry.get('tombstones'), dict):
            raise ValueError('视觉资源索引缺少 assets 或 tombstones')
        atomic_write_json(cls.registry_path(project_path), registry)

    @classmethod
    def is_asset_reference(cls, value: Any) -> bool:
        return isinstance(value, str) and value.startswith(cls.REFERENCE_PREFIX)

    @classmethod
    def asset_id_from_reference(cls, reference: str) -> str:
        if not cls.is_asset_reference(reference):
            return ''
        return reference[len(cls.REFERENCE_PREFIX):].strip()

    @classmethod
    def reference(cls, asset_id: str) -> str:
        return f'{cls.REFERENCE_PREFIX}{asset_id}'

    @classmethod
    def normalize_relative_path(cls, relative_path: str, default_extension: str = '.png') -> str:
        value = str(relative_path or '').strip().replace('\\', '/').lstrip('/')
        if value.lower().startswith('templates/'):
            value = value[10:]
        if not value:
            raise ValueError('视觉资源路径不能为空')
        if not os.path.splitext(value)[1] and default_extension:
            value += default_extension
        return value

    @classmethod
    def infer_kind(cls, relative_path: str, requested_kind: str | None = None) -> str:
        requested = str(requested_kind or '').strip().lower()
        if requested in cls.VALID_KINDS:
            return requested
        first = str(relative_path or '').replace('\\', '/').split('/', 1)[0].lower()
        # 未明确分类的新资源统一进入 image；不创建 shared 杂项目录。
        return first if first in cls.VALID_KINDS else 'image'

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    @staticmethod
    def _file_metadata(path: str) -> tuple[str, int, int]:
        from PIL import Image

        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with Image.open(path) as image:
            width, height = image.size
        return digest, int(width), int(height)

    @classmethod
    def _record_for_path(cls, registry: dict[str, Any], relative_path: str) -> tuple[str, dict[str, Any] | None]:
        needle = relative_path.casefold()
        for asset_id, record in registry.get('assets', {}).items():
            if str(record.get('path') or '').replace('\\', '/').casefold() == needle:
                return asset_id, record
        return '', None

    @classmethod
    def register_files(cls, project_path: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with cls._registry_lock:
            return cls._register_files_unlocked(project_path, items)

    @classmethod
    def _register_files_unlocked(cls, project_path: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        root = cls.ensure_structure(project_path)
        registry = cls.load_registry(project_path)
        results: list[dict[str, Any]] = []
        now = cls._now()
        for item in items:
            relative_path = cls.normalize_relative_path(str(item.get('relative_path') or ''))
            full_path = assert_safe_path(root, os.path.join(root, relative_path.replace('/', os.sep)))
            if not os.path.isfile(full_path):
                raise FileNotFoundError(f'视觉资源不存在: {relative_path}')
            digest, width, height = cls._file_metadata(full_path)
            existing_id, existing = cls._record_for_path(registry, relative_path)
            asset_id = existing_id or str(item.get('asset_id') or '').strip() or f'asset_{uuid.uuid4().hex}'
            if asset_id in registry['assets'] and asset_id != existing_id:
                asset_id = f'asset_{uuid.uuid4().hex}'
            record = {
                **(existing or {}),
                'id': asset_id,
                'path': relative_path,
                'key': os.path.splitext(relative_path)[0].replace('\\', '/'),
                'kind': cls.infer_kind(relative_path, item.get('kind')),
                'display_name': str(item.get('display_name') or os.path.splitext(os.path.basename(relative_path))[0]),
                'sha256': digest,
                'width': width,
                'height': height,
                'created_at': (existing or {}).get('created_at') or now,
                'updated_at': now,
            }
            capture = item.get('capture')
            if isinstance(capture, dict) and capture:
                record['capture'] = capture
            registry['assets'][asset_id] = record
            results.append(record)
        cls.save_registry(project_path, registry)
        return results

    @classmethod
    def register_file(
        cls,
        project_path: str,
        relative_path: str,
        kind: str | None = None,
        capture: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return cls.register_files(project_path, [{
            'relative_path': relative_path,
            'kind': kind,
            'capture': capture or {},
        }])[0]

    @classmethod
    def update_capture(cls, project_path: str, reference: str, capture: dict[str, Any]) -> dict[str, Any]:
        asset_id = cls.asset_id_from_reference(reference)
        if not asset_id:
            raise ValueError('只有稳定资源引用可以更新捕获元数据')
        with cls._registry_lock:
            registry = cls.load_registry(project_path)
            record = registry.get('assets', {}).get(asset_id)
            if not isinstance(record, dict):
                raise FileNotFoundError(f'资源ID不存在: {reference}')
            record['capture'] = dict(capture or {})
            record['updated_at'] = cls._now()
            cls.save_registry(project_path, registry)
            return record

    @classmethod
    def resolve(cls, project_path: str, reference: str, require_exists: bool = True) -> dict[str, Any]:
        root = cls.templates_dir(project_path)
        raw = str(reference or '').strip()
        record = None
        asset_id = cls.asset_id_from_reference(raw)
        if asset_id:
            record = cls.load_registry(project_path).get('assets', {}).get(asset_id)
            if not isinstance(record, dict):
                raise FileNotFoundError(f'资源ID不存在: {raw}')
            relative_path = cls.normalize_relative_path(str(record.get('path') or ''))
        else:
            relative_path = cls.normalize_relative_path(raw)
            asset_id, record = cls._record_for_path(cls.load_registry(project_path), relative_path)
        full_path = assert_safe_path(root, os.path.join(root, relative_path.replace('/', os.sep)))
        if require_exists and not os.path.isfile(full_path):
            raise FileNotFoundError(f'视觉资源文件不存在: {relative_path}')
        key = os.path.splitext(relative_path)[0].replace('\\', '/')
        return {
            'asset_id': asset_id,
            'asset_ref': cls.reference(asset_id) if asset_id else key,
            'relative_path': relative_path,
            'key': key,
            'full_path': full_path,
            'record': record or {},
        }

    @classmethod
    def metadata_for_directory(cls, project_path: str, relative_dir: str) -> dict[str, dict[str, Any]]:
        prefix = str(relative_dir or '').strip('/').replace('\\', '/')
        prefix = f'{prefix}/' if prefix else ''
        result: dict[str, dict[str, Any]] = {}
        for asset_id, record in cls.load_registry(project_path).get('assets', {}).items():
            path = str(record.get('path') or '').replace('\\', '/')
            if os.path.dirname(path).replace('\\', '/').strip('/') == prefix.strip('/'):
                result[path.casefold()] = {**record, 'asset_ref': cls.reference(asset_id)}
        return result


asset_service = AssetService()
