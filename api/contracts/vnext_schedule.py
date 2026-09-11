"""Strict HTTP contracts for the format-6 local schedule control plane."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

StableId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$',
    ),
]


class StrictScheduleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class OnceTriggerRequest(StrictScheduleRequest):
    type: Literal['once']
    local_datetime: str = Field(min_length=19, max_length=32)


class DailyTriggerRequest(StrictScheduleRequest):
    type: Literal['daily']
    local_time: str = Field(min_length=5, max_length=15)


class IntervalTriggerRequest(StrictScheduleRequest):
    type: Literal['interval']
    anchor_local_datetime: str = Field(min_length=19, max_length=32)
    interval_seconds: int = Field(ge=1, le=31_536_000)


ScheduleTriggerRequest = Annotated[
    OnceTriggerRequest | DailyTriggerRequest | IntervalTriggerRequest,
    Field(discriminator='type'),
]


class ScheduleEntryRequest(StrictScheduleRequest):
    entry_id: StableId | None = None
    enabled: bool = True
    host_id: StableId
    instance_id: StableId
    product_id: StableId
    profile_id: StableId
    start_offset_seconds: int = Field(default=0, ge=0, le=31_536_000)
    start_deadline_seconds: int | None = Field(default=None, ge=0, le=31_536_000)


class SchedulePlanRequest(StrictScheduleRequest):
    schedule_id: StableId | None = None
    name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    timezone_id: str = Field(min_length=1, max_length=128)
    trigger: ScheduleTriggerRequest
    misfire_policy: Literal['skip', 'catch_up_once'] = 'skip'
    max_lateness_seconds: int = Field(default=0, ge=0, le=31_536_000)
    overlap_policy: Literal['skip', 'queue_once'] = 'skip'
    dispatch_mode: Literal['simultaneous', 'staggered'] = 'simultaneous'
    entries: list[ScheduleEntryRequest] = Field(min_length=1, max_length=512)


class SchedulePlanUpdateRequest(SchedulePlanRequest):
    expected_revision: int = Field(ge=1)


class ScheduleEntryResponse(BaseModel):
    entry_id: str
    order: int
    enabled: bool
    host_id: str
    instance_id: str
    product_id: str
    profile_id: str
    start_offset_seconds: int
    start_deadline_seconds: int | None
    validated_summary: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SchedulePlanResponse(BaseModel):
    schedule_id: str
    revision: int
    name: str
    enabled: bool
    timezone_id: str
    trigger: dict[str, str | int]
    misfire_policy: str
    max_lateness_seconds: int
    overlap_policy: str
    dispatch_mode: str
    entries: list[ScheduleEntryResponse]
    created_by: str
    created_at: str
    updated_at: str
    next_due_at: str | None
    last_processed_due_at: str | None
    deleted_at: str | None


class ScheduleDeleteResponse(BaseModel):
    ok: Literal[True]
    schedule_id: str
    deleted_at: str


class ScheduleOccurrenceResponse(BaseModel):
    occurrence_id: str
    schedule_id: str
    schedule_revision: int
    scheduled_at: str
    discovered_at: str
    first_due_at: str
    last_due_at: str
    collapsed_due_count: int
    trigger_source: str
    entries: list[ScheduleEntryResponse]
    status: str
    reason_code: str | None
    created_at: str
    updated_at: str


class ScheduleDispatchResponse(BaseModel):
    dispatch_id: str
    occurrence_id: str
    schedule_id: str
    schedule_revision: int
    entry_id: str
    entry_order: int
    host_id: str
    instance_id: str
    product_id: str
    profile_id: str
    not_before_at: str
    deadline_at: str | None
    status: str
    run_id: str | None
    error_id: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class ScheduleDiagnosticResponse(BaseModel):
    sequence: int
    recorded_at: str
    level: str
    category: Literal['schedule']
    event_type: str
    schedule_id: str | None
    occurrence_id: str | None
    dispatch_id: str | None
    run_id: str | None
    error_id: str | None
    details: dict[str, str | int | float | bool | None]
