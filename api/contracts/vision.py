"""Strict HTTP contracts for visual-resource mutations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictVisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class VisionProjectRequest(StrictVisionRequest):
    project_path: str = Field(min_length=1, max_length=32767)


class TemplateFolderCreateRequest(VisionProjectRequest):
    parent_path: str = Field(default='', max_length=32767)
    folder_name: str = Field(min_length=1, max_length=255)


class TemplateRegisterRequest(VisionProjectRequest):
    relative_path: str = Field(min_length=1, max_length=32767)
    kind: Literal['', 'image', 'ocr', 'page'] = ''


class RegionSaveRequest(VisionProjectRequest):
    template_name: str | None = Field(default=None, max_length=32767)
    relative_path: str | None = Field(default=None, max_length=32767)
    crop_rect: list[int] | dict[str, Any] | None = None
    region: list[int] | dict[str, Any] | None = None
    reference_size: list[int] | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode='after')
    def validate_target_and_region(self):
        if not (self.template_name or self.relative_path):
            raise ValueError('template_name 或 relative_path 至少填写一个')
        if self.crop_rect is None and self.region is None:
            raise ValueError('crop_rect 或 region 至少填写一个')
        return self

