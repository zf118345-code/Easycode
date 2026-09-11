"""Workspace-identity guarded application service for v6 extensions."""

from __future__ import annotations

from typing import Any

from .extensions import VNextExtensionRegistry
from .workspace_context import VNextWorkspaceContext


class VNextExtensionService:
    def __init__(self, context: VNextWorkspaceContext) -> None:
        self._context = context
    def definitions(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        workspace = self._context.active_model()
        if workspace is None:
            return [], []
        return VNextExtensionRegistry.definitions(workspace.project_path)

    def scaffold(
        self,
        workspace_id: str,
        generation: int,
        *,
        package_id: str,
        publisher_id: str,
        publisher_name: str,
        display_name: str,
        description: str = '',
        scope: str = 'project',
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.scaffold(
            workspace.project_path,
            package_id=package_id,
            publisher_id=publisher_id,
            publisher_name=publisher_name,
            display_name=display_name,
            description=description,
            scope=scope,
        )

    def import_package(
        self, workspace_id: str, generation: int, *, source_path: str, scope: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.import_package(
            workspace.project_path, source_path=source_path, scope=scope,
        )

    def packages(self, workspace_id: str, generation: int) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        return VNextExtensionRegistry.packages(workspace.project_path)

    def package(
        self, workspace_id: str, generation: int, package_id: str, scope: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        return VNextExtensionRegistry.package(workspace.project_path, package_id, scope)

    def validate(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        return VNextExtensionRegistry.validate(workspace.project_path, package_id, scope)

    def references(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        references = VNextExtensionRegistry.references(workspace.project_path, package_id, scope)
        return {'package_id': package_id, 'scope': scope, 'references': references}

    def trust(
        self, workspace_id: str, generation: int, package_id: str, scope: str, mode: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.trust(
            workspace.project_path, package_id, scope, mode=mode,
        )

    def untrust(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.untrust(workspace.project_path, package_id, scope)

    def enable(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.enable(workspace.project_path, package_id, scope)

    def disable(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.disable(workspace.project_path, package_id, scope)

    def build(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.build_sealed(workspace.project_path, package_id, scope)

    def seal_android_jvm(
        self,
        workspace_id: str,
        generation: int,
        package_id: str,
        scope: str,
        *,
        variant_id: str,
        module_path: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.seal_android_jvm(
            workspace.project_path,
            package_id,
            scope,
            variant_id=variant_id,
            module_path=module_path,
        )

    def open_folder(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        return VNextExtensionRegistry.open_folder(workspace.project_path, package_id, scope)

    def contract_tests(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        return VNextExtensionRegistry.contract_tests(workspace.project_path, package_id, scope)

    def delete_package(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        return VNextExtensionRegistry.delete_package(workspace.project_path, package_id, scope)
