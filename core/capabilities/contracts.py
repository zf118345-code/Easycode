from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    version: str
    entry: Callable[..., Any]
    name: str = ''
    description: str = ''
    inputs: tuple[dict[str, Any], ...] = ()
    outputs: tuple[dict[str, Any], ...] = ()
    permissions: frozenset[str] = field(default_factory=frozenset)
    timeout_ms: int = 30000
    idempotent: bool = False
    package_id: str = 'builtin'
    source: str = 'builtin'

    def public(self) -> dict[str, Any]:
        return {
            'id': self.capability_id,
            'name': self.name or self.capability_id,
            'version': self.version,
            'description': self.description,
            'inputs': [dict(item) for item in self.inputs],
            'outputs': [dict(item) for item in self.outputs],
            'permissions': sorted(self.permissions),
            'timeout_ms': self.timeout_ms,
            'idempotent': self.idempotent,
            'package_id': self.package_id,
            'source': self.source,
        }


class CapabilityContext:
    """Narrow, permission-checked facade passed to developer capabilities."""

    def __init__(
        self,
        executor,
        spec: CapabilitySpec,
        cancellation: threading.Event,
        *,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._executor = executor
        self.spec = spec
        self._cancellation = cancellation
        self._progress = progress

    @property
    def project_path(self) -> str:
        return str(getattr(self._executor, 'project_dir', '') or '')

    @property
    def cancelled(self) -> bool:
        return self._cancellation.is_set() or bool(getattr(self._executor, 'is_stopped', False))

    def require(self, permission: str) -> None:
        if permission not in self.spec.permissions:
            raise PermissionError(f'能力 {self.spec.capability_id} 未声明权限: {permission}')

    def log(self, message: str, level: str = 'info') -> None:
        self._executor.log(f'[能力 {self.spec.capability_id}] {message}', level)

    def report_progress(self, current: int, total: int | None = None, message: str = '') -> None:
        payload = {'current': int(current), 'total': int(total) if total is not None else None, 'message': str(message or '')}
        if self._progress:
            self._progress(payload)
        if message:
            self.log(message)

    def get_variable(self, name: str, default=None):
        return getattr(self._executor, 'variables', {}).get(str(name), default)

    def set_variable(self, name: str, value: Any) -> None:
        self.require('variables.write')
        getattr(self._executor, 'variables', {})[str(name)] = value

    def platform_store(self, permission: str):
        self.require(permission)
        store = getattr(self._executor, '_platform_store', None)
        if store is None:
            raise RuntimeError('当前执行环境未初始化平台运行时')
        return store

    def send_remote_message(
        self,
        endpoint: str,
        token: str,
        channel: str,
        payload: Any,
        *,
        sender: str = '',
        ttl_seconds: int = 86400,
    ) -> dict[str, Any]:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        store = getattr(self._executor, '_platform_store', None)
        if store is None:
            raise RuntimeError('当前执行环境未初始化平台运行时')
        return platform_runtime_service.send_remote_message(
            store, endpoint, token, channel, payload,
            sender=sender, ttl_seconds=ttl_seconds,
        )

    def claim_remote_messages(
        self, endpoint: str, token: str, channel: str, consumer: str,
        *, limit: int = 20, lease_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        return platform_runtime_service.claim_remote_messages(
            endpoint, token, channel, consumer, limit=limit, lease_seconds=lease_seconds,
        )

    def ack_remote_message(self, endpoint: str, token: str, message_id: str, consumer: str) -> bool:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        return platform_runtime_service.ack_remote_message(endpoint, token, message_id, consumer)

    def acquire_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, *, ttl_seconds: int = 30,
    ) -> dict[str, Any] | None:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        return platform_runtime_service.acquire_remote_lease(
            endpoint, token, resource_key, owner, ttl_seconds=ttl_seconds,
        )

    def renew_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, lease_token: str,
        *, ttl_seconds: int = 30,
    ) -> bool:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        return platform_runtime_service.renew_remote_lease(
            endpoint, token, resource_key, owner, lease_token, ttl_seconds=ttl_seconds,
        )

    def release_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, lease_token: str,
    ) -> bool:
        self.require('network.coordinator')
        from core.services.platform_runtime_service import platform_runtime_service

        return platform_runtime_service.release_remote_lease(
            endpoint, token, resource_key, owner, lease_token,
        )

    def ocr_region(
        self,
        region: list[int],
        *,
        reference_size: list[int] | None = None,
        gray_scale: bool = False,
        gray_threshold: int = 128,
    ) -> str:
        self.require('screen.read')
        import cv2
        import numpy as np

        from core.vision.ocr_engine import ocr_engine_recognize
        from core.services.runtime_target import capture_workspace_region

        # Runtime capabilities must use the already bound execution target,
        # including its warm Android stream.  The property-panel preview API
        # also renders a PNG preview and resolves project context, which is
        # useful in the IDE but needlessly expensive and incorrect in Player.
        image, _ = capture_workspace_region(
            self._executor,
            list(region or [0, 0, 0, 0]),
            list(reference_size or [0, 0]),
        )
        frame_bgr = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2BGR)
        if gray_scale:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            _, thresholded = cv2.threshold(gray, int(gray_threshold), 255, cv2.THRESH_BINARY)
            frame_bgr = cv2.cvtColor(thresholded, cv2.COLOR_GRAY2BGR)
        return str(ocr_engine_recognize(frame_bgr) or '').strip()

    def swipe(
        self,
        start: list[int],
        end: list[int],
        *,
        reference_size: list[int] | None = None,
        duration_ms: int = 300,
        hold_after_ms: int = 0,
    ) -> dict[str, Any]:
        self.require('input.gesture')
        from core.services.input_dispatcher import drag_workspace

        return drag_workspace(
            self._executor,
            start[0], start[1], end[0], end[1],
            reference_size=reference_size,
            duration_ms=duration_ms,
            hold_after_ms=hold_after_ms,
            requested_mode='background',
            stop_check=lambda: self.cancelled,
        )
