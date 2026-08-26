from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from core.services.capability_service import CapabilityService


class CapabilityPackagingError(RuntimeError):
    pass


class CapabilityPackagingService:
    """Resolve the executable code required by a blueprint for Player export."""

    _SAFE_PART = re.compile(r'[^A-Za-z0-9_.-]+')

    @staticmethod
    def _nodes(blueprint: dict[str, Any]) -> Iterable[dict[str, Any]]:
        """Yield executable/resource-bearing nodes from a v3 merged blueprint.

        The exporter can pass either the complete project or a reference-trimmed
        blueprint.  Keeping traversal here schema-aware prevents a packaged
        Player from silently omitting capabilities used by functions or the
        page map.
        """
        graphs: list[dict[str, Any]] = []
        main_graph = blueprint.get('main_graph')
        if isinstance(main_graph, dict):
            graphs.append(main_graph)
        for function in blueprint.get('functions') or []:
            if isinstance(function, dict) and isinstance(function.get('graph'), dict):
                graphs.append(function['graph'])
        page_map = blueprint.get('page_map')
        if isinstance(page_map, dict):
            graphs.append(page_map)
        for graph in graphs:
            for node in graph.get('nodes') or []:
                if isinstance(node, dict):
                    yield node

    @classmethod
    def references(cls, blueprint: dict[str, Any]) -> set[str]:
        capabilities = set()
        for node in cls._nodes(blueprint):
            if node.get('node_type') != 'script_call':
                continue
            params = node.get('params') or {}
            capability_id = str(params.get('capability_id') or '').strip()
            if capability_id:
                capabilities.add(capability_id)
        return capabilities

    @classmethod
    def _manifests(cls, project_path: str) -> list[tuple[Path, dict[str, Any]]]:
        roots = []
        project_root = Path(project_path).resolve() / 'capabilities'
        if project_root.is_dir():
            roots.extend(path for path in project_root.iterdir() if path.is_dir())
        shared_root = CapabilityService._shared_root()
        if shared_root.is_dir():
            roots.extend(path for path in shared_root.iterdir() if path.is_dir())
        result = []
        for root in roots:
            manifest_path = root / 'capability.json'
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            except Exception as exc:
                raise CapabilityPackagingError(f'能力清单无法读取 {manifest_path}: {exc}') from exc
            if isinstance(data, dict):
                result.append((root, data))
        return result

    @classmethod
    def collect_files(cls, project_path: str, blueprint: dict[str, Any]) -> dict[str, Path]:
        capability_ids = cls.references(blueprint)
        manifests = cls._manifests(project_path)
        by_capability: dict[str, tuple[Path, dict[str, Any]]] = {}
        by_package: dict[str, tuple[Path, dict[str, Any]]] = {}
        for root, manifest in manifests:
            package_id = str(manifest.get('package_id') or root.name).strip()
            by_package[package_id] = (root, manifest)
            for function in manifest.get('functions') or []:
                if isinstance(function, dict) and function.get('id'):
                    by_capability[str(function['id'])] = (root, manifest)

        selected: dict[str, tuple[Path, dict[str, Any]]] = {}
        missing = []
        for capability_id in capability_ids:
            # Built-ins ship with the engine and need no package payload.
            spec = CapabilityService.resolve(project_path, capability_id)
            if spec is not None and spec.source == 'builtin':
                continue
            package = by_capability.get(capability_id)
            if package is None:
                missing.append(capability_id)
                continue
            package_id = str(package[1].get('package_id') or package[0].name)
            selected[package_id] = package

        if missing:
            raise CapabilityPackagingError(f'以下能力未安装，无法打包: {", ".join(sorted(missing))}')

        # Manifest-level package dependencies make reusable capability libraries
        # composable without leaking project-specific logic into the node graph.
        pending = list(selected.values())
        while pending:
            _, manifest = pending.pop()
            for dependency in manifest.get('dependencies') or []:
                dependency_id = str(dependency.get('package_id') if isinstance(dependency, dict) else dependency).strip()
                if not dependency_id or dependency_id in selected:
                    continue
                package = by_package.get(dependency_id)
                if package is None:
                    raise CapabilityPackagingError(f'能力依赖未安装: {dependency_id}')
                selected[dependency_id] = package
                pending.append(package)

        result: dict[str, Path] = {}
        for package_id, (root, _) in selected.items():
            folder = cls._SAFE_PART.sub('_', package_id).strip('._') or root.name
            for path in root.rglob('*'):
                if not path.is_file() or path.suffix.lower() not in {'.py', '.json'}:
                    continue
                relative = path.relative_to(root).as_posix()
                if '__pycache__' in path.parts or any(part.startswith('.') for part in Path(relative).parts):
                    continue
                result[f'capabilities/{folder}/{relative}'] = path

        return result
