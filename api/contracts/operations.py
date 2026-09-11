"""Strict request contracts for legacy operational endpoints.

These endpoints remain available to the current IDE and Player, but their HTTP
boundary must reject misspelled or unsupported top-level fields instead of
silently changing build, execution, or recording behaviour.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictOperationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectPathRequest(StrictOperationRequest):
    project_path: str = Field(min_length=1, max_length=32767)


class ExporterSchemaRequest(ProjectPathRequest):
    schema_data: dict[str, Any] | None = None


class ExporterBuildRequest(ProjectPathRequest):
    form_schema: dict[str, Any] | None = None
    acknowledge_warnings: bool = False


class ExporterPreflightRequest(ProjectPathRequest):
    form_schema: dict[str, Any] | None = None
    entry_task_id: str | None = Field(default=None, max_length=256)
    entry_node_id: str | None = Field(default=None, max_length=256)
    scope: Literal['publish', 'debug'] = 'publish'


class PlayerConfigRequest(StrictOperationRequest):
    user_config: dict[str, Any] = Field(default_factory=dict)
    instance_id: str = Field(default='instance-1', min_length=1, max_length=128)


class PlayerRunRequest(StrictOperationRequest):
    instance_id: str = Field(default='instance-1', min_length=1, max_length=128)
    resume: bool = False


class PlayerInstanceRequest(StrictOperationRequest):
    instance_id: str = Field(default='instance-1', min_length=1, max_length=128)


class PlayerProfileRequest(StrictOperationRequest):
    name: str = Field(min_length=1, max_length=80)
    user_config: dict[str, Any] = Field(default_factory=dict)


class PlayerProfileApplyRequest(StrictOperationRequest):
    instance_id: str = Field(default='instance-1', min_length=1, max_length=128)


class FrameRecordingOptions(StrictOperationRequest):
    target_fps: float = Field(default=0, ge=0, le=240)
    queue_capacity: int = Field(default=96, ge=8, le=512)
    recording_mode: Literal['lossless_all_frames', 'changed_frames', 'diagnostic_events'] = 'lossless_all_frames'
    change_threshold: float = Field(default=0.006, ge=0.0001, le=1)
    max_session_bytes: int = Field(default=0, ge=0, le=1_000_000_000_000)


class FrameRecordingStartRequest(ProjectPathRequest):
    options: FrameRecordingOptions | None = None


class FrameRecordingStopRequest(StrictOperationRequest):
    reason: str = Field(default='api', max_length=120)


class FrameRecordingMarkRequest(StrictOperationRequest):
    label: str = Field(default='手动标记', max_length=120)


class AdbResolveRequest(StrictOperationRequest):
    window_title: str = Field(default='', max_length=1024)
    window_hwnd: int = Field(default=0, ge=0)
    process_id: int = Field(default=0, ge=0)


class ProjectSettingsRequest(ProjectPathRequest):
    settings: dict[str, Any] = Field(default_factory=dict)


class ExecutionRunRequest(ProjectPathRequest):
    task_id: str = Field(min_length=1, max_length=256)
    start_node_id: str | None = Field(default=None, max_length=256)
    blueprint_data: dict[str, Any] | None = None


class ExecutionStepRequest(StrictOperationRequest):
    step: Literal['over', 'into', 'out', 'next'] = 'over'


class ExecutionBreakpointsRequest(StrictOperationRequest):
    breakpoints: list[str] = Field(default_factory=list, max_length=10_000)


class ExecutionBreakpointRequest(StrictOperationRequest):
    node_id: str = Field(min_length=1, max_length=256)
