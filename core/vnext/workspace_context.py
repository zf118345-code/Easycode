"""Workspace identity, generation and lock ownership for vNext services."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any


class VNextWorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VNextWorkspace:
    workspace_id: str
    generation: int
    project_id: str
    project_name: str
    project_path: str
    read_only: bool

    def to_dict(self) -> dict:
        return asdict(self)


class VNextWorkspaceContext:
    """The only owner of the active project identity and generation."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._active: VNextWorkspace | None = None
        self._generation = 0
        self._services: dict[str, Any] = {}

    def register_service(self, name: str, service: Any) -> None:
        """Register one workspace-scoped application service."""

        key = str(name or '').strip()
        if not key:
            raise ValueError('service name is required')
        with self.lock:
            if key in self._services and self._services[key] is not service:
                raise ValueError(f'workspace service already registered: {key}')
            self._services[key] = service

    def service(self, name: str) -> Any:
        with self.lock:
            try:
                return self._services[name]
            except KeyError as exc:
                raise KeyError(f'workspace service is not registered: {name}') from exc

    def service_names(self) -> tuple[str, ...]:
        with self.lock:
            return tuple(self._services)

    def active_model(self) -> VNextWorkspace | None:
        return self._active

    def active(self) -> dict | None:
        with self.lock:
            return self._active.to_dict() if self._active else None

    def activate(
        self,
        *,
        workspace_id: str,
        project_id: str,
        project_name: str,
        project_path: str,
        read_only: bool,
    ) -> VNextWorkspace:
        with self.lock:
            self._generation += 1
            self._active = VNextWorkspace(
                workspace_id=workspace_id,
                generation=self._generation,
                project_id=project_id,
                project_name=project_name,
                project_path=project_path,
                read_only=read_only,
            )
            return self._active

    def require(self, workspace_id: str, generation: int, *, writable: bool = False) -> VNextWorkspace:
        with self.lock:
            workspace = self._active
            if workspace is None:
                raise VNextWorkspaceError('当前没有打开vNext项目')
            if workspace.workspace_id != workspace_id or workspace.generation != int(generation):
                raise VNextWorkspaceError('工作区已切换，此请求已失效')
            if writable and workspace.read_only:
                raise VNextWorkspaceError('项目以只读方式打开')
            return workspace
