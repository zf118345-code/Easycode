"""Strict HTTP contracts for legacy project-workspace operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectWorkspacePathRequest(StrictWorkspaceRequest):
    path: str = Field(min_length=1, max_length=32767)


class ProjectWorkspaceOpenRequest(ProjectWorkspacePathRequest):
    initialize: bool = False
    confirm_nonempty: bool = False
    project_name: str = Field(default='', max_length=256)
    allow_read_only: bool = True


class ProjectWorkspaceRepairRequest(ProjectWorkspacePathRequest):
    confirmed: bool = False


class FolderDialogRequest(StrictWorkspaceRequest):
    title: str = Field(default='选择 EasyCode 项目文件夹', max_length=256)


class FileDialogRequest(StrictWorkspaceRequest):
    title: str = Field(default='选择文件', max_length=256)
    extensions: list[str] = Field(default_factory=list, max_length=64)
