"""Strict HTTP contracts owned by the standalone v6 Player.

Keeping these models outside the IDE-wide contract module is part of the
package boundary: importing the Player application must not load editable
ProgramDocument, workspace, compiler, or author-publishing contracts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictPlayerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DangerousOperationConfirmationRequest(StrictPlayerRequest):
    confirmation_id: str = Field(min_length=1, max_length=128)
    confirmed: Literal[True]


class PlayerRuntimeRunRequest(StrictPlayerRequest):
    profile_id: str = Field(default='', max_length=96)
    profile_revision: int | None = Field(default=None, ge=1)
    target_id: str | None = Field(default=None, max_length=256)
    player_values: dict[str, Any] = Field(default_factory=dict)
    action_control_id: str = Field(default='', max_length=256)
    dangerous_confirmations: list[DangerousOperationConfirmationRequest] = Field(
        default_factory=list,
        max_length=100,
    )
    message_instance_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$',
    )


class PlayerRecordingSettingsRequest(StrictPlayerRequest):
    enabled: bool = False
    confirm_current_revision: bool = False
    strategy: Literal['all_frames', 'changed_frames', 'diagnostic'] = 'changed_frames'
    target_fps: float = Field(default=15, ge=0.2, le=60)
    max_duration_ms: int = Field(default=1_800_000, ge=1_000, le=604_800_000)
    max_session_bytes: int = Field(default=2_147_483_648, ge=1_048_576, le=1_000_000_000_000)
    min_free_bytes: int = Field(default=536_870_912, ge=67_108_864, le=107_374_182_400)


class PlayerProfileRequest(StrictPlayerRequest):
    profile_id: str = Field(default='', max_length=96)
    name: str = Field(min_length=1, max_length=80)
    target_id: str | None = Field(default=None, max_length=256)
    values: dict[str, Any] = Field(default_factory=dict)
    expected_revision: int | None = Field(default=None, ge=1)
    recording: PlayerRecordingSettingsRequest | None = None


class PlayerControlDestinationRequest(StrictPlayerRequest):
    product_id: str = Field(min_length=1, max_length=256)
    release_id: str = Field(min_length=1, max_length=256)
    profile_id: str = Field(min_length=1, max_length=96)
    control_id: str = Field(min_length=1, max_length=256)
    action_id: Literal[
        'pick-point', 'pick-region', 'pick-color', 'capture-image', 'choose-resource',
        'capture-control', 'capture-window', 'capture-path', 'choose-file-read',
        'choose-file-save', 'choose-directory',
    ]
    profile_revision: int = Field(ge=1)
    target_id: str = Field(default='', max_length=256)


class PlayerCaptureStartRequest(StrictPlayerRequest):
    destination: PlayerControlDestinationRequest
    origin: str = Field(default='', max_length=2048)


class PlayerCaptureConfirmRequest(StrictPlayerRequest):
    capture_id: str = Field(min_length=1, max_length=256)
    destination: PlayerControlDestinationRequest
    result: dict[str, Any]


class PlayerCaptureCancelRequest(StrictPlayerRequest):
    capture_id: str = Field(min_length=1, max_length=256)
    destination: PlayerControlDestinationRequest


class PlayerImageRestoreRequest(StrictPlayerRequest):
    destination: PlayerControlDestinationRequest


class ApiFieldError(BaseModel):
    path: str
    message: str
    type: str = ''


class ApiRecovery(BaseModel):
    retryable: bool = False
    action: str = 'none'
    message: str = ''


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    fields: list[ApiFieldError] = Field(default_factory=list)
    recovery: ApiRecovery = Field(default_factory=ApiRecovery)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail


class CaptureActionRequest(StrictPlayerRequest):
    session_id: str = Field(default='', max_length=256)
    snapshot_id: str = Field(min_length=1, max_length=256)
    capture_chain_id: str = Field(default='', max_length=256)
    capture_context: dict[str, Any] = Field(default_factory=dict)
    reference_size: tuple[int, int]
    port: dict[str, Any] | None = None
    operation_id: str = Field(default='', max_length=256)
    kind: Literal['field_confirm', 'field_cancel', 'field_control_probe']
    point: tuple[int, int] | None = None
    color: dict[str, int] | None = None
    path: list[tuple[int, int]] = Field(default_factory=list, max_length=100_000)
    rects: list[tuple[int, int, int, int]] = Field(default_factory=list, max_length=32)
    field_request_id: str = Field(default='', max_length=256)
    selector: dict[str, Any] | None = None


class CaptureActionAckRequest(StrictPlayerRequest):
    request_id: str = Field(min_length=1, max_length=256)
    result: dict[str, Any] = Field(default_factory=dict)


class CaptureCloseRequest(StrictPlayerRequest):
    snapshot_id: str = Field(default='', max_length=160)


__all__ = [name for name in globals() if name.startswith(('Api', 'Capture', 'Dangerous', 'Player'))]
