"""Typed requests for the native Windows Player multi-instance console."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlayerConsoleInstanceCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    installation_id: str = Field(min_length=1, max_length=128)
    name: str = Field(default='', max_length=120)


class PlayerConsoleInstanceDeleteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    expected_revision: int = Field(ge=1)


class PlayerConsolePrepareCloseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stop_active: bool = False


__all__ = [
    'PlayerConsoleInstanceCreateRequest',
    'PlayerConsoleInstanceDeleteRequest',
    'PlayerConsolePrepareCloseRequest',
]
