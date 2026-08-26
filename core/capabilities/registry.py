from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from .contracts import CapabilitySpec


class CapabilityRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._specs: dict[tuple[str, str], CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec, *, replace: bool = False) -> CapabilitySpec:
        key = (spec.capability_id, spec.version)
        with self._lock:
            if key in self._specs and not replace:
                existing = self._specs[key]
                if existing.entry is spec.entry:
                    return existing
                raise ValueError(f'能力已注册: {spec.capability_id}@{spec.version}')
            self._specs[key] = spec
        return spec

    def unregister_source(self, source: str) -> None:
        with self._lock:
            self._specs = {key: spec for key, spec in self._specs.items() if spec.source != source}

    def unregister_source_prefix(self, prefix: str) -> None:
        with self._lock:
            self._specs = {key: spec for key, spec in self._specs.items() if not spec.source.startswith(prefix)}

    def resolve(self, capability_id: str, version: str | None = None) -> CapabilitySpec | None:
        clean_id = str(capability_id or '').strip()
        clean_version = str(version or '').strip()
        with self._lock:
            if clean_version:
                return self._specs.get((clean_id, clean_version))
            matches = [spec for (item_id, _), spec in self._specs.items() if item_id == clean_id]
        if not matches:
            return None
        # Numeric semantic-version components sort naturally; non-numeric
        # suffixes remain deterministic without pulling another dependency.
        def version_key(spec: CapabilitySpec):
            parts = []
            for part in spec.version.replace('-', '.').split('.'):
                parts.append((0, int(part)) if part.isdigit() else (1, part))
            return tuple(parts)

        return sorted(matches, key=version_key)[-1]

    def list(self) -> list[CapabilitySpec]:
        with self._lock:
            return sorted(self._specs.values(), key=lambda item: (item.capability_id, item.version))


capability_registry = CapabilityRegistry()


def register_capability(
    capability_id: str,
    *,
    version: str = '1.0.0',
    name: str = '',
    description: str = '',
    inputs: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    outputs: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    permissions: list[str] | tuple[str, ...] | set[str] = (),
    timeout_ms: int = 30000,
    idempotent: bool = False,
    package_id: str = 'builtin',
):
    def decorator(function: Callable[..., Any]):
        spec = CapabilitySpec(
            capability_id=str(capability_id),
            version=str(version),
            entry=function,
            name=str(name or capability_id),
            description=str(description or ''),
            inputs=tuple(dict(item) for item in inputs),
            outputs=tuple(dict(item) for item in outputs),
            permissions=frozenset(str(item) for item in permissions),
            timeout_ms=max(1, int(timeout_ms or 30000)),
            idempotent=bool(idempotent),
            package_id=str(package_id or 'builtin'),
            source='builtin',
        )
        capability_registry.register(spec)
        function.__easycode_capability__ = spec
        return function

    return decorator
