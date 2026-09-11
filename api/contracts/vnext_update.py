"""Strict HTTP requests for the v6 signed-update vertical slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdatePreferencesRequest(StrictUpdateRequest):
    automatic_check: bool
    automatic_download: bool
    automatic_apply: bool


class AuthorUpdateDomainRequest(StrictUpdateRequest):
    enabled: bool
    product_id: str = Field(default="", max_length=256)
    provider: Literal["easycode_hosted", "self_hosted"] = "self_hosted"
    feed_base_url: str = Field(default="", max_length=2048)
    channel: Literal["test", "stable"] = "stable"
    required_policy_capability: bool = False
    initial_preferences: UpdatePreferencesRequest
    pinned_root: dict[str, Any] | None = None


class AuthorUpdateDomainsRequest(StrictUpdateRequest):
    player_application: AuthorUpdateDomainRequest
    project_content: AuthorUpdateDomainRequest


class AuthorUpdateConfigurationRequest(StrictUpdateRequest):
    schema_version: Literal[1]
    domains: AuthorUpdateDomainsRequest


class InitializeUpdateRepositoryRequest(StrictUpdateRequest):
    domain: Literal["player_application", "project_content"]
    repository_root: str = Field(min_length=1, max_length=32767)


class PublishContentUpdateRequest(StrictUpdateRequest):
    repository_root: str = Field(min_length=1, max_length=32767)
    platform: Literal["windows", "android"]
    architecture: str = Field(min_length=1, max_length=80)
    display_version: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=4000)


class PublishApplicationUpdateRequest(PublishContentUpdateRequest):
    artifact_path: str = Field(min_length=1, max_length=32767)
    runtime_min: str = Field(default="0.0.0", max_length=40)
    runtime_max: str = Field(default="9999.0.0", max_length=40)
    ecir_min: str = Field(default="0.0.0", max_length=40)
    ecir_max: str = Field(default="9999.0.0", max_length=40)
    application_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    permissions_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    abi: list[str] = Field(default_factory=list, max_length=20)
    android_version_code: int | None = Field(default=None, ge=1)
    android_certificate_sha256: str = Field(default="", max_length=64)


class UpdateRolloutRequest(StrictUpdateRequest):
    domain: Literal["player_application", "project_content"]
    repository_root: str = Field(min_length=1, max_length=32767)
    release_id: str = Field(min_length=1, max_length=256)
    channel: Literal["test", "stable"]
    percent_bps: int = Field(default=0, ge=0, le=10_000)
    whitelist_codes: list[str] = Field(default_factory=list, max_length=10_000)
    whitelist_hashes: list[str] = Field(default_factory=list, max_length=10_000)
    paused: bool = False
    rollout_id: str = Field(default="", max_length=256)


class RequiredUpdatePolicyRequest(StrictUpdateRequest):
    domain: Literal["player_application", "project_content"]
    repository_root: str = Field(min_length=1, max_length=32767)
    release_id: str = Field(min_length=1, max_length=256)
    effective_at: datetime
    grace_deadline: datetime
    reason: str = Field(min_length=1, max_length=500)
    platform_targets: list[str] = Field(min_length=1, max_length=100)


class RevokeUpdatePolicyRequest(StrictUpdateRequest):
    domain: Literal["player_application", "project_content"]
    repository_root: str = Field(min_length=1, max_length=32767)


class PlayerUpdateDomainRequest(StrictUpdateRequest):
    domain: Literal["player_application", "project_content"]


class PlayerUpdateCheckRequest(PlayerUpdateDomainRequest):
    policy_only: bool = False


class PlayerUpdatePreferencesRequest(PlayerUpdateDomainRequest):
    preferences: UpdatePreferencesRequest


class PlayerUpdateSafePointRequest(StrictUpdateRequest):
    running_or_paused: bool
    uncommitted_draft: bool = False


__all__ = [name for name in globals() if name.endswith("Request")]
