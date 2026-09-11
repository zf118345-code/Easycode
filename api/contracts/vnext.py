"""Versioned request and response contracts for the EasyCode vNext API.

The language/compiler accepts flexible semantic values, but the HTTP boundary
must stay strict.  These models intentionally reject unknown top-level fields
so a misspelled client property cannot silently change execution behaviour.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.vnext.program_types import (
    AssignmentTarget,
    CatchClause,
    LoopBinding,
    MessageEventSource,
    ResultBinding,
    StableId,
    Statement,
    ValueNode,
)
from core.vnext.target_service import TargetDefinition, WindowsTargetDefinition

VNEXT_CONTRACT_VERSION = 1


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class IdeSettingsRequest(StrictRequest):
    shortcuts: dict[str, str] = Field(default_factory=dict, max_length=100)


class MetaResponse(BaseModel):
    product: str
    api_contract_version: int
    project_format_version: int
    language_version: int
    ecir_version: int
    platforms: list[str]


class CaptureControlRequest(StrictRequest):
    action: Literal['start', 'stop']


class VisionPreviewRequest(StrictRequest):
    target_id: str = Field(default='', max_length=256)
    function_id: Literal[
        'official.image.find', 'official.image.find_all', 'official.image.wait_visible',
        'official.image.wait_hidden', 'official.image.click_once', 'official.image.click_until_hidden',
        'official.image.click_position_until_visible', 'official.image.click_position_until_hidden',
        'official.text.recognize', 'official.text.match', 'official.text.wait_visible',
    ]
    region: list[int] | None = Field(default=None, min_length=4, max_length=4)
    image_asset_id: str = Field(default='', max_length=256)
    similarity: float = Field(default=0.85, ge=0, le=1)
    language: str = Field(default='auto', max_length=32)
    preprocess: dict[str, Any] = Field(default_factory=dict, max_length=16)
    expected_text: str = Field(default='', max_length=10000)
    match_mode: str = Field(default='contains', max_length=32)


class ResolveControlRequest(StrictRequest):
    target_id: StableId
    point: tuple[int, int]
    reference_size: tuple[int, int]


class ResolveWindowCaptureRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=256)
    snapshot_id: str = Field(min_length=1, max_length=256)
    point: tuple[int, int]
    reference_size: tuple[int, int]


class TestWindowsTargetRequest(StrictRequest):
    target: WindowsTargetDefinition


class ChooseFolderRequest(StrictRequest):
    title: str = Field(default='选择 EasyCode vNext 项目文件夹', max_length=120)


class ChooseFileRequest(StrictRequest):
    title: str = Field(default='选择文件', max_length=120)
    extensions: tuple[str, ...] = Field(default=(), max_length=32)


class WorkspacePathRequest(StrictRequest):
    path: str = Field(min_length=1, max_length=32767)


class WorkspaceOpenRequest(WorkspacePathRequest):
    initialize: bool = False
    project_name: str = Field(default='', max_length=160)


class WorkspaceProgramRecoveryRequest(WorkspacePathRequest):
    function_id: StableId
    history_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.-]+$')
    expected_revision: str = Field(min_length=1, max_length=100)


class DangerousOperationConfirmationRequest(StrictRequest):
    confirmation_id: str = Field(min_length=1, max_length=128)
    confirmed: Literal[True]


class PlayerRuntimeRunRequest(StrictRequest):
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


class PlayerRecordingSettingsRequest(StrictRequest):
    enabled: bool = False
    confirm_current_revision: bool = False
    strategy: Literal['all_frames', 'changed_frames', 'diagnostic'] = 'changed_frames'
    target_fps: float = Field(default=15, ge=0.2, le=60)
    max_duration_ms: int = Field(default=1_800_000, ge=1_000, le=604_800_000)
    max_session_bytes: int = Field(default=2_147_483_648, ge=1_048_576, le=1_000_000_000_000)
    min_free_bytes: int = Field(default=536_870_912, ge=67_108_864, le=107_374_182_400)


class PlayerProfileRequest(StrictRequest):
    profile_id: str = Field(default='', max_length=96)
    name: str = Field(min_length=1, max_length=80)
    target_id: str | None = Field(default=None, max_length=256)
    values: dict[str, Any] = Field(default_factory=dict)
    expected_revision: int | None = Field(default=None, ge=1)
    recording: PlayerRecordingSettingsRequest | None = None


class PlayerControlDestinationRequest(StrictRequest):
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


class PlayerCaptureStartRequest(StrictRequest):
    destination: PlayerControlDestinationRequest
    origin: str = Field(default='', max_length=2048)


class PlayerCaptureConfirmRequest(StrictRequest):
    capture_id: str = Field(min_length=1, max_length=256)
    destination: PlayerControlDestinationRequest
    result: dict[str, Any]


class PlayerCaptureCancelRequest(StrictRequest):
    capture_id: str = Field(min_length=1, max_length=256)
    destination: PlayerControlDestinationRequest


class PlayerImageRestoreRequest(StrictRequest):
    destination: PlayerControlDestinationRequest


class ReplayAnalyzeRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    frame_index: int = Field(ge=1)
    analysis_ids: tuple[str, ...] = Field(default=(), max_length=1_000)


class ReplayAnalyzeSessionRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    changes_only: bool = False
    change_threshold: float = Field(default=0.006, ge=0, le=1)
    step: int = Field(default=1, ge=1, le=10_000)
    max_frames: int = Field(default=1_000, ge=1, le=10_000)
    analysis_ids: tuple[str, ...] = Field(default=(), max_length=1_000)


class ReplayCompareRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    left_frame_index: int = Field(ge=1)
    right_frame_index: int = Field(ge=1)


class ReplayExportRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    mode: Literal['default', 'reproducible'] = 'default'
    analysis_run_ids: tuple[str, ...] = Field(default=(), max_length=1_000)
    include_categories: tuple[
        Literal['program', 'ecir', 'resources', 'ocr', 'parameters', 'implementation'], ...
    ] = Field(default=(), max_length=6)
    frame_indices: tuple[Annotated[int, Field(ge=1)], ...] = Field(default=(), max_length=10_000)


class ReplayCaptureRequest(StrictRequest):
    session_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_-]+$')
    frame_index: int = Field(ge=1)
    capture_session_id: str = Field(min_length=1, max_length=256)


class RecordingStartRequest(StrictRequest):
    target_id: str = Field(default='', max_length=256)
    target_fps: float = Field(default=15, ge=0.2, le=120)
    queue_capacity: int = Field(default=48, ge=4, le=512)
    recording_mode: Literal[
        'all_frames', 'changed_frames', 'diagnostic',
        'lossless_all_frames', 'diagnostic_events',
    ] = 'changed_frames'
    change_threshold: float = Field(default=0.006, ge=0.0001, le=1)
    max_duration_ms: int = Field(default=1_800_000, ge=1_000, le=604_800_000)
    max_session_bytes: int = Field(default=2_147_483_648, ge=1_048_576, le=1_000_000_000_000)
    min_free_bytes: int = Field(default=536_870_912, ge=67_108_864, le=107_374_182_400)
    diagnostic_pre_frames: int = Field(default=45, ge=1, le=600)
    diagnostic_post_frames: int = Field(default=20, ge=0, le=600)


class RecordingStopRequest(StrictRequest):
    reason: Literal['user', 'user_stopped', 'user_cancelled'] = 'user'


class RecordingMarkRequest(StrictRequest):
    label: str = Field(default='手动标记', max_length=120)


class OperationRecordingStartRequest(StrictRequest):
    function_id: StableId
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    target_id: StableId
    location: dict[str, Any] = Field(default_factory=dict)


class OperationRecordingEventRequest(StrictRequest):
    event: dict[str, Any]


class OperationRecordingStopRequest(StrictRequest):
    reason: str = Field(default='user', min_length=1, max_length=80)


class OperationRecordingCommitRequest(StrictRequest):
    review_events: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class TriggerSaveRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    trigger: dict[str, Any]


class TriggerDeleteRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')


class AssetOverrideRequest(StrictRequest):
    control_id: str = Field(min_length=1, max_length=256)
    file_name: str = Field(min_length=1, max_length=512)
    content_base64: str = Field(min_length=1, max_length=100_000_000)


class ScaffoldExtensionRequest(StrictRequest):
    package_id: str = Field(min_length=3, max_length=200)
    publisher_id: str = Field(min_length=3, max_length=160)
    publisher_name: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=4000)
    scope: Literal['project', 'user'] = 'project'


class ImportExtensionRequest(StrictRequest):
    source_path: str = Field(min_length=1, max_length=4096)
    scope: Literal['project', 'user'] = 'project'


class ExtensionScopeRequest(StrictRequest):
    scope: Literal['official', 'user', 'project']


class SealAndroidJvmExtensionRequest(StrictRequest):
    scope: Literal['user', 'project']
    variant_id: str = Field(min_length=3, max_length=200, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
    module_path: str = Field(min_length=1, max_length=4096)


class TrustExtensionRequest(StrictRequest):
    scope: Literal['user', 'project']
    mode: Literal['explicit', 'local_development'] = 'explicit'


class ImportAssetRequest(StrictRequest):
    category: Literal['image', 'ocr', 'page'] = 'image'
    folder: str = Field(default='', max_length=1024)
    file_name: str = Field(min_length=1, max_length=512)
    display_name: str = Field(default='', max_length=512)
    content_base64: str = Field(min_length=1, max_length=100_000_000)
    source: str = Field(default='import', max_length=128)
    capture: dict[str, Any] | None = None


class CreateAssetFolderRequest(StrictRequest):
    category: Literal['image', 'ocr', 'page']
    folder: str = Field(min_length=1, max_length=1024)


class MoveAssetFolderRequest(StrictRequest):
    source_path: str = Field(min_length=1, max_length=1024)
    target_parent: str = Field(default='', max_length=1024)
    name: str = Field(min_length=1, max_length=512)


class UpdateAssetRequest(StrictRequest):
    display_name: str | None = Field(default=None, max_length=512)
    category: Literal['image', 'ocr', 'page'] | None = None
    folder: str | None = Field(default=None, max_length=1024)


class ReplaceAssetRequest(StrictRequest):
    file_name: str = Field(min_length=1, max_length=512)
    content_base64: str = Field(min_length=1, max_length=100_000_000)


class PlayerFormFeaturesRequest(StrictRequest):
    recording: bool = False


class PlayerFormRequest(StrictRequest):
    schema_version: Literal[3] = 3
    title: str = Field(default='脚本运行器', max_length=256)
    icon_asset_id: str = Field(default='', max_length=160)
    features: PlayerFormFeaturesRequest = Field(default_factory=PlayerFormFeaturesRequest)
    pages: list[dict[str, Any]] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)


class DebugSettingsRequest(StrictRequest):
    breakpoints: dict[str, list[str]] = Field(default_factory=dict)


class ViewStateRequest(StrictRequest):
    active_view: Literal['program', 'resources', 'variables', 'targets', 'replay', 'extensions', 'schedules', 'player'] = 'program'
    active_function_id: str = Field(default='', max_length=160)
    collapsed_statement_ids: dict[str, list[str]] = Field(default_factory=dict)
    scroll_offsets: dict[str, int] = Field(default_factory=dict)
    panel_sizes: dict[str, int] = Field(default_factory=dict)


class TargetConfigurationRequest(StrictRequest):
    expected_revision: str = Field(
        min_length=1,
        max_length=96,
        pattern=r'^sha256:[0-9a-f]{64}$',
    )
    targets: list[TargetDefinition] = Field(default_factory=list)
    default_target_id: StableId | None = None


# Project format 6 ProgramDocument commands.  Values are validated by the
# versioned ProgramDocument schema in the Program Service; the HTTP envelope is
# still discriminated and strict so misspelled command fields cannot be ignored.
class ProgramCreateRequest(StrictRequest):
    display_name: str = Field(min_length=1, max_length=160)


class ProgramRenameRequest(StrictRequest):
    expected_revision: str = Field(
        min_length=1,
        max_length=96,
        pattern=r'^sha256:[0-9a-f]{64}$',
    )
    display_name: str = Field(min_length=1, max_length=160)


class ProgramLocationRequest(StrictRequest):
    parent_statement_id: str | None = Field(default=None, max_length=160)
    block: Literal[
        'root', 'then', 'otherwise', 'additional_branch', 'body', 'catch', 'finally'
    ] = 'root'
    clause_id: str | None = Field(default=None, max_length=160)
    before_statement_id: str | None = Field(default=None, max_length=160)


class ProgramInsertCallCommand(StrictRequest):
    kind: Literal['insert_call']
    function_id: str = Field(min_length=1, max_length=160)
    arguments: dict[str, ValueNode] = Field(default_factory=dict)
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertAssignmentCommand(StrictRequest):
    kind: Literal['insert_assignment']
    target: AssignmentTarget
    value: ValueNode
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertIfCommand(StrictRequest):
    kind: Literal['insert_if']
    condition: ValueNode
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertIfFromCallResultCommand(StrictRequest):
    kind: Literal['insert_if_from_call_result']
    statement_id: str = Field(min_length=1, max_length=160)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)


class ProgramInsertLoopCommand(StrictRequest):
    kind: Literal['insert_loop']
    mode: Literal['repeat', 'while', 'for_each', 'for_each_map']
    source: ValueNode
    item_binding: LoopBinding | None = None
    index_binding: LoopBinding | None = None
    key_binding: LoopBinding | None = None
    value_binding: LoopBinding | None = None
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertBreakCommand(StrictRequest):
    kind: Literal['insert_break']
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertContinueCommand(StrictRequest):
    kind: Literal['insert_continue']
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertReturnCommand(StrictRequest):
    kind: Literal['insert_return']
    value: ValueNode | None = None
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertFailCommand(StrictRequest):
    kind: Literal['insert_fail']
    error_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$')
    message: ValueNode
    details: ValueNode | None = None
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramRetryPolicyInput(StrictRequest):
    """Editable retry settings; author review evidence is never client input."""

    max_retries: ValueNode
    interval: ValueNode
    transient_only: Literal[True] = True


class ProgramInsertTryCommand(StrictRequest):
    kind: Literal['insert_try']
    retry_policy: ProgramRetryPolicyInput | None = None
    catches: tuple[CatchClause, ...] = ()
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertTargetScopeCommand(StrictRequest):
    kind: Literal['insert_target_scope']
    target: ValueNode
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramInsertListenCommand(StrictRequest):
    kind: Literal['insert_listen']
    event_source: MessageEventSource
    receive_binding: LoopBinding
    handler_function_id: str = Field(min_length=1, max_length=160)
    condition: ValueNode | None = None
    handler_arguments: dict[str, ValueNode] = Field(default_factory=dict)
    location: ProgramLocationRequest = Field(default_factory=ProgramLocationRequest)


class ProgramAddIfBranchCommand(StrictRequest):
    kind: Literal['add_if_branch']
    statement_id: str = Field(min_length=1, max_length=160)
    condition: ValueNode


class ProgramRemoveIfBranchCommand(StrictRequest):
    kind: Literal['remove_if_branch']
    statement_id: str = Field(min_length=1, max_length=160)
    branch_id: str = Field(min_length=1, max_length=160)


class ProgramAddCatchClauseCommand(StrictRequest):
    kind: Literal['add_catch_clause']
    statement_id: str = Field(min_length=1, max_length=160)
    error_ids: tuple[str, ...] = ()
    error_binding: LoopBinding | None = None


class ProgramUpdateArgumentCommand(StrictRequest):
    kind: Literal['update_argument']
    statement_id: str = Field(min_length=1, max_length=160)
    parameter_id: str = Field(min_length=1, max_length=160)
    value: ValueNode


class ProgramRepairMissingArgumentsCommand(StrictRequest):
    kind: Literal['repair_missing_arguments']
    statement_id: str = Field(min_length=1, max_length=160)


class ProgramUpdateAssignmentValueCommand(StrictRequest):
    kind: Literal['update_assignment_value']
    statement_id: str = Field(min_length=1, max_length=160)
    value: ValueNode


class ProgramUpdateAssignmentTargetCommand(StrictRequest):
    kind: Literal['update_assignment_target']
    statement_id: str = Field(min_length=1, max_length=160)
    target: AssignmentTarget
    value: ValueNode | None = None


class ProgramUpdateIfConditionCommand(StrictRequest):
    kind: Literal['update_if_condition']
    statement_id: str = Field(min_length=1, max_length=160)
    branch_id: str | None = Field(default=None, max_length=160)
    condition: ValueNode


class ProgramUpdateLoopCommand(StrictRequest):
    kind: Literal['update_loop']
    statement_id: str = Field(min_length=1, max_length=160)
    mode: Literal['repeat', 'while', 'for_each', 'for_each_map']
    source: ValueNode
    item_binding: LoopBinding | None = None
    index_binding: LoopBinding | None = None
    key_binding: LoopBinding | None = None
    value_binding: LoopBinding | None = None


class ProgramUpdateReturnValueCommand(StrictRequest):
    kind: Literal['update_return_value']
    statement_id: str = Field(min_length=1, max_length=160)
    value: ValueNode | None


class ProgramUpdateFailCommand(StrictRequest):
    kind: Literal['update_fail']
    statement_id: str = Field(min_length=1, max_length=160)
    error_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$')
    message: ValueNode
    details: ValueNode | None = None


class ProgramUpdateTryRetryPolicyCommand(StrictRequest):
    kind: Literal['update_try_retry_policy']
    statement_id: str = Field(min_length=1, max_length=160)
    retry_policy: ProgramRetryPolicyInput | None


class ProgramReviewRetryRiskCommand(StrictRequest):
    kind: Literal['review_retry_risk']
    statement_id: str = Field(min_length=1, max_length=160)


class ProgramUpdateCatchClauseCommand(StrictRequest):
    kind: Literal['update_catch_clause']
    statement_id: str = Field(min_length=1, max_length=160)
    catch_id: str = Field(min_length=1, max_length=160)
    error_ids: tuple[str, ...] = ()
    error_binding: LoopBinding | None = None


class ProgramUpdateTargetScopeCommand(StrictRequest):
    kind: Literal['update_target_scope']
    statement_id: str = Field(min_length=1, max_length=160)
    target: ValueNode


class ProgramUpdateListenCommand(StrictRequest):
    kind: Literal['update_listen']
    statement_id: str = Field(min_length=1, max_length=160)
    event_source: MessageEventSource
    receive_binding: LoopBinding
    handler_function_id: str = Field(min_length=1, max_length=160)
    condition: ValueNode | None = None
    handler_arguments: dict[str, ValueNode] = Field(default_factory=dict)


class ProgramSetResultBindingCommand(StrictRequest):
    kind: Literal['set_result_binding']
    statement_id: str = Field(min_length=1, max_length=160)
    binding: ResultBinding | None = None


class ProgramSetStepLabelCommand(StrictRequest):
    kind: Literal['set_step_label']
    statement_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=500)


class ProgramMoveStatementCommand(StrictRequest):
    kind: Literal['move_statement']
    statement_id: str = Field(min_length=1, max_length=160)
    location: ProgramLocationRequest


class ProgramMoveStatementsCommand(StrictRequest):
    kind: Literal['move_statements']
    statement_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    location: ProgramLocationRequest


class ProgramCopyStatementCommand(StrictRequest):
    kind: Literal['copy_statement']
    statement_id: str = Field(min_length=1, max_length=160)
    location: ProgramLocationRequest


class ProgramPasteStatementsCommand(StrictRequest):
    kind: Literal['paste_statements']
    statements: tuple[Statement, ...] = Field(min_length=1, max_length=500)
    location: ProgramLocationRequest


class ProgramDeleteStatementCommand(StrictRequest):
    kind: Literal['delete_statement']
    statement_id: str = Field(min_length=1, max_length=160)


class ProgramDeleteStatementsCommand(StrictRequest):
    kind: Literal['delete_statements']
    statement_ids: tuple[str, ...] = Field(min_length=1, max_length=500)


ProgramCommandRequestValue = Annotated[
    ProgramInsertCallCommand
    | ProgramInsertAssignmentCommand
    | ProgramInsertIfCommand
    | ProgramInsertIfFromCallResultCommand
    | ProgramInsertLoopCommand
    | ProgramInsertBreakCommand
    | ProgramInsertContinueCommand
    | ProgramInsertReturnCommand
    | ProgramInsertFailCommand
    | ProgramInsertTryCommand
    | ProgramInsertTargetScopeCommand
    | ProgramInsertListenCommand
    | ProgramAddIfBranchCommand
    | ProgramRemoveIfBranchCommand
    | ProgramAddCatchClauseCommand
    | ProgramRepairMissingArgumentsCommand
    | ProgramUpdateArgumentCommand
    | ProgramUpdateAssignmentValueCommand
    | ProgramUpdateAssignmentTargetCommand
    | ProgramUpdateIfConditionCommand
    | ProgramUpdateLoopCommand
    | ProgramUpdateReturnValueCommand
    | ProgramUpdateFailCommand
    | ProgramUpdateTryRetryPolicyCommand
    | ProgramReviewRetryRiskCommand
    | ProgramUpdateCatchClauseCommand
    | ProgramUpdateTargetScopeCommand
    | ProgramUpdateListenCommand
    | ProgramSetResultBindingCommand
    | ProgramSetStepLabelCommand
    | ProgramMoveStatementCommand
    | ProgramMoveStatementsCommand
    | ProgramCopyStatementCommand
    | ProgramPasteStatementsCommand
    | ProgramDeleteStatementCommand
    | ProgramDeleteStatementsCommand,
    Field(discriminator='kind'),
]


class ProgramCommandRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    command: ProgramCommandRequestValue


class ProgramCommandBatchRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    commands: tuple[ProgramCommandRequestValue, ...] = Field(min_length=1, max_length=2000)


class ProgramCompileRequest(StrictRequest):
    target_platform: Literal[
        'windows', 'android_adb', 'android_local', 'no_target'
    ] | None = None


class ProgramRevisionRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')


class ControlSelectorRepairRequest(StrictRequest):
    selector_id: StableId
    replacement: ValueNode
    expected_revisions: dict[StableId, str] = Field(default_factory=dict)
    confirmed: bool = False


class ProgramHistoryRestoreRequest(ProgramRevisionRequest):
    history_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.-]+$')


class ProgramExtractStatementsRequest(ProgramRevisionRequest):
    statement_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=160)


class ProgramValueCatalogScopeBinding(StrictRequest):
    symbol_id: str = Field(min_length=1, max_length=160, pattern=r'^[A-Za-z][A-Za-z0-9_.-]*$')
    display_name: str = Field(min_length=1, max_length=160)
    value_type: str = Field(min_length=1, max_length=240)


class ProgramValueCatalogRequest(StrictRequest):
    statement_id: str = Field(min_length=1, max_length=160)
    expected_type: str = Field(min_length=1, max_length=256)
    scope_bindings: list[ProgramValueCatalogScopeBinding] = Field(default_factory=list, max_length=32)


class ProgramRunRequest(ProgramCompileRequest):
    target_id: str | None = Field(default=None, max_length=256)
    debug: dict[str, Any] = Field(default_factory=dict)
    variable_overrides: dict[str, ValueNode] = Field(default_factory=dict)
    message_instance_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$',
    )


class MessageInstanceRegisterRequest(StrictRequest):
    display_name: str = Field(min_length=1, max_length=160)
    instance_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$',
    )
    endpoint_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$',
    )
    endpoint_kind: Literal['ide_debug', 'player'] = 'ide_debug'


class MessageInstanceRenameRequest(StrictRequest):
    display_name: str = Field(min_length=1, max_length=160)


class ProjectVariableCreateRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    display_name: str = Field(min_length=1, max_length=160)
    value_type: str = Field(min_length=1, max_length=240)
    default_value: ValueNode
    description: str = Field(default='', max_length=4000)
    constraints: dict[str, Any] = Field(default_factory=dict)


class ProjectVariableUpdateRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    value_type: str | None = Field(default=None, min_length=1, max_length=240)
    default_value: ValueNode | None = None
    description: str | None = Field(default=None, max_length=4000)
    constraints: dict[str, Any] | None = None


class ProjectVariableRevisionRequest(StrictRequest):
    expected_revision: str = Field(min_length=1, max_length=96, pattern=r'^sha256:[0-9a-f]{64}$')


class ApiFieldError(BaseModel):
    path: str
    message: str
    kind: str = ''


class ApiRecovery(BaseModel):
    retryable: bool = False
    action: Literal['none', 'retry', 'reload_workspace', 'fix_request', 'contact_support'] = 'none'
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
