"""Strict HTTP contracts for schedules, messages and distributed leases."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictPlatformRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ScheduleSaveRequest(StrictPlatformRequest):
    id: str | None = Field(default=None, max_length=160)
    name: str = Field(default='未命名计划', min_length=1, max_length=160)
    schedule_type: Literal['daily', 'interval', 'once'] = 'daily'
    schedule_value: str = Field(default='00:00', min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class MessagePublishRequest(StrictPlatformRequest):
    id: str | None = Field(default=None, max_length=160)
    channel: str = Field(default='default', min_length=1, max_length=160)
    payload: Any = None
    sender: str = Field(default='', max_length=160)
    ttl_seconds: int = Field(default=86400, ge=1, le=31_536_000)


class MessageClaimRequest(StrictPlatformRequest):
    channel: str = Field(default='default', min_length=1, max_length=160)
    consumer: str = Field(default='default', min_length=1, max_length=160)
    limit: int = Field(default=20, ge=1, le=1000)
    lease_seconds: int = Field(default=30, ge=1, le=86400)


class MessageAckRequest(StrictPlatformRequest):
    consumer: str = Field(default='default', min_length=1, max_length=160)


class LeaseAcquireRequest(StrictPlatformRequest):
    resource_key: str = Field(min_length=1, max_length=512)
    owner: str = Field(min_length=1, max_length=160)
    ttl_seconds: int = Field(default=30, ge=1, le=86400)


class LeaseMutationRequest(StrictPlatformRequest):
    resource_key: str = Field(min_length=1, max_length=512)
    owner: str = Field(min_length=1, max_length=160)
    token: str = Field(min_length=1, max_length=512)
    ttl_seconds: int = Field(default=30, ge=1, le=86400)


class RemoteConnection(StrictPlatformRequest):
    endpoint: str = Field(min_length=1, max_length=2048)
    token: str = Field(default='', max_length=2048)


class RemoteMessagePublishRequest(RemoteConnection):
    channel: str = Field(default='default', min_length=1, max_length=160)
    payload: Any = None
    sender: str = Field(default='', max_length=160)
    ttl_seconds: int = Field(default=86400, ge=1, le=31_536_000)


class RemoteMessageClaimRequest(RemoteConnection):
    channel: str = Field(default='default', min_length=1, max_length=160)
    consumer: str = Field(default='default', min_length=1, max_length=160)
    limit: int = Field(default=20, ge=1, le=1000)
    lease_seconds: int = Field(default=30, ge=1, le=86400)


class RemoteMessageAckRequest(RemoteConnection):
    consumer: str = Field(default='default', min_length=1, max_length=160)


class RemoteLeaseAcquireRequest(RemoteConnection):
    resource_key: str = Field(min_length=1, max_length=512)
    owner: str = Field(min_length=1, max_length=160)
    ttl_seconds: int = Field(default=30, ge=1, le=86400)


class RemoteLeaseMutationRequest(RemoteConnection):
    resource_key: str = Field(min_length=1, max_length=512)
    owner: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=1, max_length=512)
    ttl_seconds: int = Field(default=30, ge=1, le=86400)

