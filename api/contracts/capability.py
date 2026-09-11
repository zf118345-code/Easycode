"""Strict HTTP contracts for capability package management."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityPackageCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    scope: Literal['project', 'shared'] = 'project'
    package_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$')
    function_name: str = Field(default='run', min_length=1, max_length=128, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    display_name: str = Field(default='', max_length=128)
    description: str = Field(default='', max_length=2000)

