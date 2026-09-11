"""Transactional vNext project asset registry.

The registry is the source of truth. Files are implementation details and may
move between the three default purpose roots without invalidating ``asset_id``.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mutation import FailureHook, ProjectMutationTransaction
from .workspace_context import VNextWorkspaceError

ASSET_CATEGORIES = ('image', 'ocr', 'page')
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
MAX_ASSET_BYTES = 25 * 1024 * 1024
_REGISTRY_CACHE_LIMIT = 32
_REGISTRY_CACHE_GUARD = threading.Lock()
_REGISTRY_CACHE: OrderedDict[str, tuple[tuple[int, int, int, int], dict[str, Any]]] = OrderedDict()
_CONTENT_HASH_CACHE_LIMIT = 2048
_CONTENT_HASH_CACHE: OrderedDict[tuple[str, tuple[int, int, int, int], str], bool] = OrderedDict()


def _file_signature(path: str) -> tuple[int, int, int, int]:
    stat = os.stat(path)
    return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino


def _registry_cache_key(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _forget_registry(path: str) -> None:
    with _REGISTRY_CACHE_GUARD:
        _REGISTRY_CACHE.pop(_registry_cache_key(path), None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _safe_segment(value: str, fallback: str = '') -> str:
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value or '').strip()).strip('. ')
    return result or fallback


def _inspect_image_bytes(content: bytes, extension: str) -> tuple[int, int]:
    expected_format = {
        '.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG',
        '.bmp': 'BMP', '.webp': 'WEBP',
    }[extension]
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            actual_format = str(image.format or '').upper()
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            width, height = int(image.width), int(image.height)
    except Exception as exc:
        raise VNextWorkspaceError('图片文件无法解码或内容已损坏') from exc
    if actual_format != expected_format:
        raise VNextWorkspaceError(
            f'图片扩展名与实际格式不一致：{extension} 不能承载 {actual_format or "未知格式"}'
        )
    if width <= 0 or height <= 0:
        raise VNextWorkspaceError('图片尺寸无效')
    return width, height


def _capture_provenance(capture: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(capture, dict):
        return None

    def coordinates(key: str, length: int) -> list[int] | None:
        raw = capture.get(key)
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)) or len(raw) != length:
            raise VNextWorkspaceError(f'捕获元数据 {key} 必须包含 {length} 个整数')
        try:
            result = [int(value) for value in raw]
        except (TypeError, ValueError) as exc:
            raise VNextWorkspaceError(f'捕获元数据 {key} 必须包含 {length} 个整数') from exc
        if key in {'work_area', 'selection_rect'} and (result[2] <= 0 or result[3] <= 0):
            raise VNextWorkspaceError(f'捕获元数据 {key} 的宽高必须大于 0')
        if key == 'reference_size' and (result[0] <= 0 or result[1] <= 0):
            raise VNextWorkspaceError('捕获参考尺寸必须大于 0')
        return result

    return {
        'platform': str(capture.get('platform') or ''),
        'target_id': str(capture.get('target_id') or ''),
        'work_area': coordinates('work_area', 4),
        'captured_at': str(capture.get('captured_at') or _now()),
        'host': str(capture.get('host') or ''),
        'selection_rect': coordinates('selection_rect', 4),
        'reference_size': coordinates('reference_size', 2),
        'coordinate_space': str(capture.get('coordinate_space') or 'workspace_px'),
    }


class ProjectAssetService:
    def __init__(self, project_path: str, *, failure_hook: FailureHook | None = None):
        self.project_path = os.path.realpath(project_path)
        self.assets_root = os.path.join(self.project_path, 'assets')
        self.registry_path = os.path.join(self.assets_root, 'registry.json')
        self.failure_hook = failure_hook

    def _read(self, *, mutable: bool = True) -> dict[str, Any]:
        try:
            signature = _file_signature(self.registry_path)
        except OSError as exc:
            raise VNextWorkspaceError(f'无法读取资源注册表：{exc}') from exc
        key = _registry_cache_key(self.registry_path)
        with _REGISTRY_CACHE_GUARD:
            cached = _REGISTRY_CACHE.get(key)
            value = cached[1] if cached is not None and cached[0] == signature else None
            if value is not None:
                _REGISTRY_CACHE.move_to_end(key)
        if value is None:
            try:
                with open(self.registry_path, encoding='utf-8-sig') as stream:
                    value = json.load(stream)
            except (OSError, json.JSONDecodeError) as exc:
                raise VNextWorkspaceError(f'无法读取资源注册表：{exc}') from exc
            if not isinstance(value, dict) or not isinstance(value.get('assets'), dict):
                raise VNextWorkspaceError('资源注册表格式无效')
            folders = value.get('folders') if isinstance(value.get('folders'), dict) else {}
            value['folders'] = {
                category: [self._folder(item) for item in folders.get(category) or [] if self._folder(item)]
                for category in ASSET_CATEGORIES
            }
            with _REGISTRY_CACHE_GUARD:
                _REGISTRY_CACHE[key] = (signature, value)
                _REGISTRY_CACHE.move_to_end(key)
                while len(_REGISTRY_CACHE) > _REGISTRY_CACHE_LIMIT:
                    _REGISTRY_CACHE.popitem(last=False)
        # Mutations work on an isolated candidate until the project transaction
        # commits. Read-only hot paths may safely share the parsed snapshot.
        return copy.deepcopy(value) if mutable else value

    @staticmethod
    def _registry_content(registry: dict[str, Any]) -> bytes:
        return (json.dumps(registry, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    def _commit(self, registry: dict[str, Any], replacements: dict[str, bytes | str | None]) -> str:
        next_replacements = dict(replacements)
        next_replacements['assets/registry.json'] = self._registry_content(registry)
        transaction_id = ProjectMutationTransaction.apply(
            self.project_path, next_replacements, failure_hook=self.failure_hook,
        )
        _forget_registry(self.registry_path)
        return transaction_id

    def _relative(self, absolute: str) -> str:
        candidate = os.path.realpath(absolute)
        if os.path.commonpath([self.project_path, candidate]) != self.project_path:
            raise VNextWorkspaceError('资源路径超出项目目录')
        return Path(candidate).relative_to(self.project_path).as_posix()

    @staticmethod
    def _remove_empty_directories(root: str, stop: str) -> None:
        current = os.path.realpath(root)
        boundary = os.path.realpath(stop)
        while current != boundary and os.path.commonpath([boundary, current]) == boundary:
            with contextlib.suppress(OSError):
                os.rmdir(current)
            current = os.path.dirname(current)

    @staticmethod
    def _category(value: str) -> str:
        category = str(value or '').strip().lower()
        if category not in ASSET_CATEGORIES:
            raise VNextWorkspaceError('资源分类必须是 image、ocr 或 page')
        return category

    @staticmethod
    def _folder(value: str) -> str:
        parts = [part for part in str(value or '').replace('\\', '/').split('/') if part]
        if any(part in {'.', '..'} for part in parts):
            raise VNextWorkspaceError('资源目录不能包含相对路径')
        return '/'.join(_safe_segment(part) for part in parts)

    def _absolute(self, relative: str) -> str:
        candidate = os.path.realpath(os.path.join(self.project_path, *str(relative).replace('\\', '/').split('/')))
        if os.path.commonpath([self.project_path, candidate]) != self.project_path:
            raise VNextWorkspaceError('资源路径超出项目目录')
        return candidate

    def list(self) -> dict[str, Any]:
        registry = self._read(mutable=False)
        assets = [dict(value) for value in registry['assets'].values() if isinstance(value, dict)]
        assets.sort(key=lambda item: (ASSET_CATEGORIES.index(item.get('category', 'image')), str(item.get('folder') or '').casefold(), str(item.get('display_name') or '').casefold()))
        folders: dict[str, set[str]] = {
            category: set(registry.get('folders', {}).get(category) or [])
            for category in ASSET_CATEGORIES
        }
        for item in assets:
            category = item.get('category')
            if category in folders and item.get('folder'):
                current = ''
                for part in str(item['folder']).split('/'):
                    current = f'{current}/{part}'.strip('/')
                    folders[category].add(current)
        return {
            'categories': [
                {'id': category, 'label': {'image': '图像', 'ocr': 'OCR', 'page': '页面'}[category], 'folders': sorted(folders[category], key=str.casefold)}
                for category in ASSET_CATEGORIES
            ],
            'assets': assets,
        }

    def import_base64(
        self, *, category: str, file_name: str, display_name: str, content_base64: str,
        folder: str = '', source: str = 'import', capture: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        category = self._category(category)
        folder = self._folder(folder)
        extension = os.path.splitext(str(file_name or ''))[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise VNextWorkspaceError('仅支持 PNG、JPG、JPEG、BMP、WEBP 图片')
        try:
            content = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise VNextWorkspaceError('图片内容不是有效 Base64') from exc
        if not content or len(content) > MAX_ASSET_BYTES:
            raise VNextWorkspaceError('图片为空或超过 25MB 限制')
        digest = hashlib.sha256(content).hexdigest()
        registry = self._read()
        duplicate = next((dict(item) for item in registry['assets'].values() if isinstance(item, dict) and item.get('sha256') == digest), None)
        asset_id = f'asset_{uuid.uuid4().hex}'
        shown_name = _safe_segment(display_name or os.path.splitext(os.path.basename(file_name))[0], '未命名资源')
        relative_dir = f'assets/{category}' + (f'/{folder}' if folder else '')
        relative_path = f'{relative_dir}/{asset_id}{extension}'
        width, height = _inspect_image_bytes(content, extension)
        capture_provenance = _capture_provenance(capture)
        item = {
            'asset_id': asset_id,
            'display_name': shown_name,
            'category': category,
            'folder': folder,
            'path': relative_path,
            'extension': extension,
            'mime_type': {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.bmp': 'image/bmp', '.webp': 'image/webp'}[extension],
            'size_bytes': len(content),
            'width': width,
            'height': height,
            'sha256': digest,
            'source': str(source or 'import'),
            'created_at': _now(),
            'updated_at': _now(),
            'aliases': [],
            # Diagnostic provenance only. Runtime search regions always belong to
            # individual function calls and are never inherited from this field.
            'capture': capture_provenance,
        }
        registry['assets'][asset_id] = item
        if folder:
            registry.setdefault('folders', {}).setdefault(category, [])
            registry['folders'][category] = sorted(set([*registry['folders'][category], folder]), key=str.casefold)
        transaction_id = self._commit(registry, {relative_path: content})
        return {'asset': item, 'duplicate_of': duplicate, 'transaction_id': transaction_id}

    def content_path(self, asset_id: str) -> tuple[str, dict[str, Any]]:
        registry = self._read(mutable=False)
        item = registry['assets'].get(asset_id)
        if not isinstance(item, dict):
            raise VNextWorkspaceError('资源不存在')
        path = self._absolute(str(item.get('path') or ''))
        if not os.path.isfile(path):
            raise VNextWorkspaceError('资源文件已丢失')
        expected_hash = str(item.get('sha256') or '')
        if expected_hash:
            signature = _file_signature(path)
            cache_key = (_registry_cache_key(path), signature, expected_hash)
            with _REGISTRY_CACHE_GUARD:
                verified = _CONTENT_HASH_CACHE.get(cache_key, False)
            if not verified:
                actual_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    raise VNextWorkspaceError('资源文件已被外部修改，哈希与注册表不一致')
                with _REGISTRY_CACHE_GUARD:
                    _CONTENT_HASH_CACHE[cache_key] = True
                    _CONTENT_HASH_CACHE.move_to_end(cache_key)
                    while len(_CONTENT_HASH_CACHE) > _CONTENT_HASH_CACHE_LIMIT:
                        _CONTENT_HASH_CACHE.popitem(last=False)
        return path, dict(item)

    def update(self, asset_id: str, *, display_name: str | None = None, category: str | None = None, folder: str | None = None) -> dict[str, Any]:
        registry = self._read()
        item = registry['assets'].get(asset_id)
        if not isinstance(item, dict):
            raise VNextWorkspaceError('资源不存在')
        old_name = str(item.get('display_name') or '')
        if display_name is not None:
            item['display_name'] = _safe_segment(display_name, old_name or '未命名资源')
            if old_name and old_name != item['display_name']:
                aliases = [str(value) for value in item.get('aliases') or [] if str(value)]
                item['aliases'] = list(dict.fromkeys([*aliases, old_name]))[-20:]
        next_category = self._category(category if category is not None else str(item.get('category') or ''))
        next_folder = self._folder(folder if folder is not None else str(item.get('folder') or ''))
        replacements: dict[str, bytes | str | None] = {}
        if next_category != item.get('category') or next_folder != item.get('folder'):
            source = self._absolute(str(item.get('path') or ''))
            if not os.path.isfile(source):
                raise VNextWorkspaceError('资源文件已丢失')
            extension = str(item.get('extension') or os.path.splitext(source)[1])
            relative_dir = f'assets/{next_category}' + (f'/{next_folder}' if next_folder else '')
            relative_path = f'{relative_dir}/{asset_id}{extension}'
            old_relative = str(item.get('path') or '')
            replacements[relative_path] = Path(source).read_bytes()
            if old_relative != relative_path:
                replacements[old_relative] = None
            item['category'] = next_category
            item['folder'] = next_folder
            item['path'] = relative_path
            if next_folder:
                registry.setdefault('folders', {}).setdefault(next_category, [])
                registry['folders'][next_category] = sorted(set([*registry['folders'][next_category], next_folder]), key=str.casefold)
        item['updated_at'] = _now()
        transaction_id = self._commit(registry, replacements)
        return {'asset': dict(item), 'transaction_id': transaction_id}

    def create_folder(self, category: str, folder: str) -> dict[str, Any]:
        category = self._category(category)
        folder = self._folder(folder)
        if not folder:
            raise VNextWorkspaceError('默认资源分类已经存在')
        registry = self._read()
        values = set(registry.setdefault('folders', {}).setdefault(category, []))
        if folder in values:
            raise VNextWorkspaceError('资源文件夹已存在')
        current = ''
        for part in folder.split('/'):
            current = f'{current}/{part}'.strip('/')
            values.add(current)
        registry['folders'][category] = sorted(values, key=str.casefold)
        transaction_id = self._commit(registry, {})
        return {
            'created': True, 'path': f'{category}/{folder}', 'operation': 'create_folder',
            'transaction_id': transaction_id,
        }

    @staticmethod
    def _split_managed_path(value: str) -> tuple[str, str]:
        parts = [part for part in str(value or '').replace('\\', '/').split('/') if part]
        if not parts or parts[0] not in ASSET_CATEGORIES:
            raise VNextWorkspaceError('资源路径必须位于 image、ocr 或 page')
        return parts[0], '/'.join(parts[1:])

    def move_folder(self, source_path: str, target_parent: str, name: str) -> dict[str, Any]:
        source_category, source_folder = self._split_managed_path(source_path)
        target_category, target_folder = self._split_managed_path(target_parent)
        if not source_folder:
            raise VNextWorkspaceError('默认资源分类不能移动或重命名')
        next_name = _safe_segment(name)
        if not next_name:
            raise VNextWorkspaceError('资源文件夹名称不能为空')
        destination_folder = self._folder('/'.join(item for item in (target_folder, next_name) if item))
        if source_category == target_category and source_folder == destination_folder:
            return {'status': 'unchanged', 'operation': 'move_folder', 'new_path': source_path}
        registry = self._read()
        known = set(registry.get('folders', {}).get(target_category) or [])
        if destination_folder in known:
            raise VNextWorkspaceError('目标资源文件夹已存在')
        source_absolute = self._absolute(f'assets/{source_category}/{source_folder}')
        destination_absolute = self._absolute(f'assets/{target_category}/{destination_folder}')
        if os.path.exists(destination_absolute):
            raise VNextWorkspaceError('目标资源文件夹已存在')
        replacements: dict[str, bytes | str | None] = {}
        if os.path.isdir(source_absolute):
            for source_file in sorted(Path(source_absolute).rglob('*')):
                if not source_file.is_file():
                    continue
                suffix = source_file.relative_to(source_absolute)
                destination_file = Path(destination_absolute) / suffix
                if destination_file.exists():
                    raise VNextWorkspaceError(f'目标资源路径已存在：{destination_file.name}')
                replacements[self._relative(str(destination_file))] = source_file.read_bytes()
                replacements[self._relative(str(source_file))] = None
        for item in registry['assets'].values():
            if not isinstance(item, dict) or item.get('category') != source_category:
                continue
            old_folder = str(item.get('folder') or '')
            if old_folder != source_folder and not old_folder.startswith(source_folder + '/'):
                continue
            suffix = old_folder[len(source_folder):].lstrip('/')
            new_folder = '/'.join(part for part in (destination_folder, suffix) if part)
            item['category'] = target_category
            item['folder'] = new_folder
            item['path'] = f'assets/{target_category}/{new_folder}/{item["asset_id"]}{item["extension"]}'
            item['updated_at'] = _now()
        source_values = set(registry.get('folders', {}).get(source_category) or [])
        moved_values = [item for item in source_values if item == source_folder or item.startswith(source_folder + '/')]
        registry['folders'][source_category] = sorted(source_values - set(moved_values), key=str.casefold)
        target_values = set(registry.get('folders', {}).get(target_category) or [])
        for old in moved_values or [source_folder]:
            suffix = old[len(source_folder):].lstrip('/')
            target_values.add('/'.join(part for part in (destination_folder, suffix) if part))
        registry['folders'][target_category] = sorted(target_values, key=str.casefold)
        transaction_id = self._commit(registry, replacements)
        self._remove_empty_directories(source_absolute, self.assets_root)
        return {
            'status': 'moved', 'operation': 'move_folder', 'old_path': source_path,
            'new_path': f'{target_category}/{destination_folder}', 'transaction_id': transaction_id,
        }

    def delete_folder(self, path: str, *, force: bool = False) -> dict[str, Any]:
        category, folder = self._split_managed_path(path)
        if not folder:
            raise VNextWorkspaceError('image、ocr、page 默认资源分类不能删除')
        registry = self._read()
        assets = [
            dict(item) for item in registry['assets'].values() if isinstance(item, dict)
            and item.get('category') == category
            and (str(item.get('folder') or '') == folder or str(item.get('folder') or '').startswith(folder + '/'))
        ]
        references = [reference for item in assets for reference in self.references(str(item.get('asset_id') or ''))]
        if references:
            return {
                'deleted': False,
                'blocked': True,
                'reason': 'asset_in_use',
                'asset_count': len(assets),
                'references': references,
                'path': path,
            }
        if assets and not force:
            return {
                'deleted': False, 'requires_confirmation': True, 'asset_count': len(assets),
                'references': references, 'path': path,
            }
        replacements: dict[str, bytes | str | None] = {}
        for item in assets:
            relative_asset = str(item.get('path') or '')
            if relative_asset:
                replacements[relative_asset] = None
            registry['assets'].pop(str(item.get('asset_id') or ''), None)
        values = set(registry.get('folders', {}).get(category) or [])
        registry['folders'][category] = sorted({item for item in values if item != folder and not item.startswith(folder + '/')}, key=str.casefold)
        absolute = self._absolute(f'assets/{category}/{folder}')
        transaction_id = self._commit(registry, replacements)
        self._remove_empty_directories(absolute, self.assets_root)
        return {
            'deleted': True, 'operation': 'delete_folder', 'asset_count': len(assets),
            'references_updated': len(references), 'transaction_id': transaction_id,
        }

    def replace_base64(
        self, asset_id: str, *, file_name: str, content_base64: str,
        source: str = 'replace', capture: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        registry = self._read()
        item = registry['assets'].get(asset_id)
        if not isinstance(item, dict):
            raise VNextWorkspaceError('资源不存在')
        extension = os.path.splitext(file_name)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise VNextWorkspaceError('替换文件类型不受支持')
        try:
            content = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise VNextWorkspaceError('图片内容不是有效 Base64') from exc
        if not content or len(content) > MAX_ASSET_BYTES:
            raise VNextWorkspaceError('图片为空或超过 25MB 限制')
        previous_path = self._absolute(str(item.get('path') or ''))
        relative_dir = os.path.dirname(str(item.get('path') or '')).replace('\\', '/')
        next_relative = f'{relative_dir}/{asset_id}{extension}'
        previous_relative = str(item.get('path') or '')
        width, height = _inspect_image_bytes(content, extension)
        capture_provenance = _capture_provenance(capture)
        item.update({
            'path': next_relative, 'extension': extension, 'size_bytes': len(content),
            'mime_type': {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.bmp': 'image/bmp', '.webp': 'image/webp'}[extension],
            'width': width, 'height': height, 'sha256': hashlib.sha256(content).hexdigest(),
            'updated_at': _now(),
            'source': str(source or 'replace'), 'capture': capture_provenance,
        })
        replacements: dict[str, bytes | str | None] = {next_relative: content}
        if previous_relative != next_relative:
            replacements[previous_relative] = None
        transaction_id = self._commit(registry, replacements)
        if previous_relative != next_relative:
            self._remove_empty_directories(os.path.dirname(previous_path), self.assets_root)
        return {'asset': dict(item), 'transaction_id': transaction_id}

    def references(self, asset_id: str) -> list[dict[str, Any]]:
        registry = self._read(mutable=False)
        item = registry['assets'].get(asset_id)
        if not isinstance(item, dict):
            raise VNextWorkspaceError('资源不存在')
        result: list[dict[str, Any]] = []
        program_root = Path(self.project_path) / 'program' / 'functions'
        for path in sorted(program_root.glob('*.json'), key=lambda value: value.name.casefold()):
            try:
                document = json.loads(path.read_text(encoding='utf-8-sig'))
                from .program_types import ProgramDocument

                # Asset deletion is deliberately fail-closed.  A corrupt
                # ProgramDocument cannot be treated as "no references".
                ProgramDocument.model_validate(document)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise VNextWorkspaceError(
                    f'无法检查资源引用，ProgramDocument 损坏：{path.name}: {exc}'
                ) from exc
            function = document['function']
            document_id = str(document.get('document_id') or '')
            function_id = str(function.get('function_id') or '')

            def visit_value_tree(
                value: Any,
                value_path: str,
                *,
                statement_id: str = '',
                parameter_id: str = '',
                statement_label: str = '',
                source_path: Path = path,
                current_document_id: str = document_id,
                current_function_id: str = function_id,
            ) -> None:
                if isinstance(value, list):
                    for index, child in enumerate(value):
                        visit_value_tree(
                            child,
                            f'{value_path}[{index}]',
                            statement_id=statement_id,
                            parameter_id=parameter_id,
                            statement_label=statement_label,
                        )
                    return
                if not isinstance(value, dict):
                    return

                next_statement_id = str(value.get('statement_id') or statement_id)
                next_statement_label = statement_label
                if value.get('statement_id'):
                    next_statement_label = str(
                        value.get('function_id') or value.get('kind') or 'statement'
                    )
                if value.get('kind') == 'asset_ref' and str(value.get('asset_id') or '') == asset_id:
                    result.append({
                        'kind': 'program_parameter',
                        'path': source_path.relative_to(self.project_path).as_posix(),
                        'document_id': current_document_id,
                        'function_id': current_function_id,
                        'statement_id': next_statement_id,
                        'parameter_id': parameter_id,
                        'value_id': str(value.get('value_id') or ''),
                        'field_path': value_path,
                        'preview': (
                            f'{next_statement_label or current_function_id} · {parameter_id}'
                            if parameter_id else next_statement_label or current_function_id
                        ),
                    })

                for key, child in value.items():
                    if key in {'arguments', 'handler_arguments'} and isinstance(child, dict):
                        for child_parameter_id, argument in child.items():
                            visit_value_tree(
                                argument,
                                f'{value_path}.{key}.{child_parameter_id}',
                                statement_id=next_statement_id,
                                parameter_id=str(child_parameter_id),
                                statement_label=next_statement_label,
                            )
                        continue
                    visit_value_tree(
                        child,
                        f'{value_path}.{key}',
                        statement_id=next_statement_id,
                        parameter_id=parameter_id,
                        statement_label=next_statement_label,
                    )

            for index, parameter in enumerate(function.get('parameters') or []):
                default_value = parameter.get('default_value')
                if default_value is not None:
                    visit_value_tree(
                        default_value,
                        f'function.parameters[{index}].default_value',
                        parameter_id=str(parameter.get('parameter_id') or ''),
                        statement_label=function_id,
                    )

            for index, statement in enumerate(function['statements']):
                visit_value_tree(statement, f'function.statements[{index}]')
        player_form_path = Path(self.project_path) / 'player' / 'form.json'
        if player_form_path.is_file():
            try:
                player_form = json.loads(player_form_path.read_text(encoding='utf-8-sig'))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise VNextWorkspaceError(
                    f'无法检查资源引用，Player 表单损坏：{exc}'
                ) from exc
            if str(player_form.get('icon_asset_id') or '') == asset_id:
                result.append({
                    'kind': 'player_branding',
                    'path': 'player/form.json',
                    'field_path': 'icon_asset_id',
                    'preview': 'Player 应用图标',
                })
        result.sort(key=lambda value: (
            str(value.get('path') or ''),
            str(value.get('statement_id') or ''),
            str(value.get('parameter_id') or ''),
            str(value.get('field_path') or ''),
        ))
        return result

    def delete(self, asset_id: str, *, force: bool = False, replacement_asset_id: str = '') -> dict[str, Any]:
        registry = self._read()
        item = registry['assets'].get(asset_id)
        if not isinstance(item, dict):
            raise VNextWorkspaceError('资源不存在')
        references = self.references(asset_id)
        if references:
            return {
                'deleted': False,
                'blocked': True,
                'reason': 'asset_in_use',
                'references': references,
                'message': '资源仍被 ProgramDocument 引用，请先替换或清除对应参数',
            }
        replacement = registry['assets'].get(replacement_asset_id) if replacement_asset_id else None
        if replacement_asset_id and not isinstance(replacement, dict):
            raise VNextWorkspaceError('替代资源不存在')
        replacements: dict[str, bytes | str | None] = {}
        path = self._absolute(str(item.get('path') or ''))
        relative_asset = str(item.get('path') or '')
        if relative_asset:
            replacements[relative_asset] = None
        del registry['assets'][asset_id]
        transaction_id = self._commit(registry, replacements)
        self._remove_empty_directories(os.path.dirname(path), self.assets_root)
        return {
            'deleted': True, 'references_updated': len(references),
            'replacement_asset_id': replacement_asset_id or None,
            'transaction_id': transaction_id,
        }
