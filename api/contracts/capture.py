"""Strict HTTP contracts for the native frozen-capture bridge."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictCaptureRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CaptureSessionRegisterRequest(StrictCaptureRequest):
    session_id: str = Field(min_length=1, max_length=256)
    project_path: str = Field(min_length=1, max_length=32767)
    workspace_kind: Literal['legacy', 'vnext', 'player'] = 'legacy'
    workspace_id: str = Field(min_length=1, max_length=256)
    workspace_generation: int = Field(ge=0)
    project_id: str = Field(default='', max_length=256)
    project_name: str = Field(default='', max_length=512)
    target_name: str = Field(default='', max_length=1024)
    canvas_mode: str = Field(default='', max_length=64)
    capture_context: dict[str, Any] = Field(default_factory=dict)
    execution_state: str = Field(default='idle', max_length=64)
    recording_active: bool = False
    origin: str = Field(default='', max_length=2048)
    last_focus_at: float | None = None


class CaptureSessionRequest(StrictCaptureRequest):
    session_id: str = Field(default='', max_length=256)


class FieldCaptureRequest(StrictCaptureRequest):
    request_id: str = Field(min_length=1, max_length=256)
    selection_mode: Literal['point', 'region', 'asset', 'color', 'path', 'control']
    category: Literal['image', 'ocr', 'page'] = 'image'
    destination: Literal['parameter', 'resource'] = 'parameter'
    max_rects: int = Field(default=1, ge=1, le=32)
    title: str = Field(default='属性捕获', max_length=160)


class CaptureTriggerRequest(CaptureSessionRequest):
    field_capture: FieldCaptureRequest | None = None


class CaptureReplayRequest(CaptureSessionRequest):
    recording_session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    frame_index: int = Field(ge=1)


class CaptureSnapshotRequest(CaptureSessionRequest):
    project_path: str = Field(default='', max_length=32767)


class CaptureCloseRequest(StrictCaptureRequest):
    snapshot_id: str = Field(default='', max_length=256)


class CaptureAssetSaveRequest(StrictCaptureRequest):
    snapshot_id: str = Field(min_length=1, max_length=256)
    category: Literal['image', 'ocr', 'page'] = 'image'
    relative_dir: str = Field(default='', max_length=2048)
    prefix: str = Field(default='', max_length=512)
    rects: list[tuple[int, int, int, int]] = Field(min_length=1, max_length=32)
    collision: Literal['ask', 'cancel', 'overwrite', 'sequence'] = 'ask'
    overwrite_confirmed: bool = False


class CaptureAssetUndoRequest(StrictCaptureRequest):
    transaction_id: str = Field(min_length=1, max_length=256)


class CaptureActionRequest(StrictCaptureRequest):
    session_id: str = Field(default='', max_length=256)
    snapshot_id: str = Field(min_length=1, max_length=256)
    capture_chain_id: str = Field(default='', max_length=256)
    capture_context: dict[str, Any] = Field(default_factory=dict)
    reference_size: tuple[int, int]
    port: dict[str, Any] | None = None
    operation_id: str = Field(default='', max_length=256)
    kind: Literal[
        'click', 'image', 'ocr', 'page', 'record', 'field_confirm',
        'field_cancel', 'field_control_probe', 'undo', 'rollback_operation',
    ]
    point: tuple[int, int] | None = None
    color: dict[str, int] | None = None
    path: list[tuple[int, int]] = Field(default_factory=list, max_length=100_000)
    rects: list[tuple[int, int, int, int]] = Field(default_factory=list, max_length=32)
    template_keys: list[str] = Field(default_factory=list, max_length=32)
    asset_refs: list[str] = Field(default_factory=list, max_length=32)
    captured_assets: list[dict[str, Any]] = Field(default_factory=list, max_length=32)
    asset_transaction: str = Field(default='', max_length=256)
    field_request_id: str = Field(default='', max_length=256)
    selector: dict[str, Any] | None = None


class CaptureActionAcknowledgeRequest(StrictCaptureRequest):
    request_id: str = Field(min_length=1, max_length=256)
    result: dict[str, Any] = Field(default_factory=dict)
