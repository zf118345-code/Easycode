"""Strict HTTP contracts for the per-user Player Hub catalog."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .vnext_schedule import ScheduleEntryRequest, StableId


class StrictHubRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallationRegisterRequest(StrictHubRequest):
    distribution_root: str = Field(min_length=1, max_length=2048)
    instance_name: str = Field(default="实例 1", min_length=1, max_length=120)
    instance_id: StableId | None = None


class InstanceCreateRequest(StrictHubRequest):
    installation_id: StableId
    name: str = Field(min_length=1, max_length=120)
    instance_id: StableId | None = None


class InstanceReleaseRequest(StrictHubRequest):
    installation_id: StableId
    expected_revision: int = Field(ge=1)


class BatchRequest(StrictHubRequest):
    batch_id: StableId | None = None
    name: str = Field(min_length=1, max_length=160)
    dispatch_mode: Literal["simultaneous", "staggered"] = "simultaneous"
    entries: list[ScheduleEntryRequest] = Field(min_length=1, max_length=512)


class BatchUpdateRequest(BatchRequest):
    expected_revision: int = Field(ge=1)


class HubActionResponse(BaseModel):
    ok: Literal[True]
    state: str | None = None
    task_name: str | None = None
    batch_id: str | None = None


class HubStatusResponse(BaseModel):
    available: bool
    ready: bool
    host_id: str
    owner_scope: str
    checked_at: str
    installations: list[dict[str, Any]]
    active_run_count: int
    interactive_session: dict[str, Any]
    wake_agent: dict[str, Any]
    remote_dispatch: dict[str, Any]
    android_system_scheduler: dict[str, Any]
    registry_error: dict[str, Any] | None = None


class HubTickResponse(BaseModel):
    checked_at: str
    occurrences: list[dict[str, Any]]
    dispatches: list[dict[str, Any]]


class LanPermissionsRequest(StrictHubRequest):
    messages: bool = False
    status: bool = False
    remote_start: bool = False
    allowed_products: list[StableId] = Field(default_factory=list, max_length=512)
    allowed_instances: list[StableId] = Field(default_factory=list, max_length=512)


class LanPairingSessionRequest(StrictHubRequest):
    ttl_ms: int = Field(default=300_000, ge=1_000, le=900_000)


class LanDiscoveryRequest(StrictHubRequest):
    timeout_seconds: float = Field(default=1.0, ge=0.1, le=5.0)
    port: int | None = Field(default=None, ge=1, le=65535)


class LanPairBeginRequest(StrictHubRequest):
    address: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    code: str | None = Field(default=None, min_length=4, max_length=32)
    session_id: StableId | None = None
    qr_payload: str | None = Field(default=None, min_length=1, max_length=16_384)
    permissions: LanPermissionsRequest = Field(default_factory=LanPermissionsRequest)


class LanPairCompleteRequest(StrictHubRequest):
    pairing: dict[str, Any]
    expected_fingerprint: str = Field(default="", max_length=160)


class LanPairConfirmRequest(StrictHubRequest):
    permissions: LanPermissionsRequest = Field(default_factory=LanPermissionsRequest)
