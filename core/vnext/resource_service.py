"""Project asset application service for vNext workspaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .mutation import FailureHook
from .workspace_context import VNextWorkspaceContext

if TYPE_CHECKING:
    from .resources import ProjectAssetService


class VNextResourceService:
    def __init__(self, context: VNextWorkspaceContext) -> None:
        self._context = context
        self.failure_hook: FailureHook | None = None

    def registry(self, workspace_id: str, generation: int, *, writable: bool = False) -> ProjectAssetService:
        from .resources import ProjectAssetService

        workspace = self._context.require(workspace_id, generation, writable=writable)
        return ProjectAssetService(workspace.project_path, failure_hook=self.failure_hook if writable else None)

    def list(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self.registry(workspace_id, generation).list()

    def import_base64(self, workspace_id: str, generation: int, **payload: Any) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).import_base64(**payload)

    def update(self, workspace_id: str, generation: int, asset_id: str, **payload: Any) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).update(asset_id, **payload)

    def replace_base64(
        self, workspace_id: str, generation: int, asset_id: str, **payload: Any,
    ) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).replace_base64(asset_id, **payload)

    def references(self, workspace_id: str, generation: int, asset_id: str) -> list[dict[str, Any]]:
        return self.registry(workspace_id, generation).references(asset_id)

    def delete(
        self,
        workspace_id: str,
        generation: int,
        asset_id: str,
        *,
        force: bool = False,
        replacement_asset_id: str = '',
    ) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).delete(
            asset_id, force=force, replacement_asset_id=replacement_asset_id,
        )

    def content_path(self, workspace_id: str, generation: int, asset_id: str) -> tuple[str, dict[str, Any]]:
        return self.registry(workspace_id, generation).content_path(asset_id)

    def create_folder(
        self, workspace_id: str, generation: int, category: str, folder: str,
    ) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).create_folder(category, folder)

    def move_folder(
        self, workspace_id: str, generation: int, source_path: str, target_parent: str, name: str,
    ) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).move_folder(source_path, target_parent, name)

    def delete_folder(
        self, workspace_id: str, generation: int, path: str, *, force: bool = False,
    ) -> dict[str, Any]:
        return self.registry(workspace_id, generation, writable=True).delete_folder(path, force=force)
