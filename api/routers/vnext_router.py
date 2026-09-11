from __future__ import annotations

import json
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from api.contracts.vnext import (
    VNEXT_CONTRACT_VERSION,
    ApiErrorResponse,
    AssetOverrideRequest,
    CaptureControlRequest,
    ControlSelectorRepairRequest,
    ResolveControlRequest,
    ResolveWindowCaptureRequest,
    ChooseFileRequest,
    ChooseFolderRequest,
    CreateAssetFolderRequest,
    ExtensionScopeRequest,
    DebugSettingsRequest,
    ImportAssetRequest,
    ImportExtensionRequest,
    IdeSettingsRequest,
    MessageInstanceRegisterRequest,
    MessageInstanceRenameRequest,
    MetaResponse,
    MoveAssetFolderRequest,
    OperationRecordingCommitRequest,
    OperationRecordingEventRequest,
    OperationRecordingStartRequest,
    OperationRecordingStopRequest,
    PlayerFormRequest,
    PlayerCaptureCancelRequest,
    PlayerCaptureConfirmRequest,
    PlayerCaptureStartRequest,
    PlayerImageRestoreRequest,
    PlayerProfileRequest,
    PlayerRuntimeRunRequest,
    ProgramCommandRequest,
    ProgramCommandBatchRequest,
    ProgramCompileRequest,
    ProgramCreateRequest,
    ProgramExtractStatementsRequest,
    ProgramHistoryRestoreRequest,
    ProgramRenameRequest,
    ProgramRevisionRequest,
    ProgramSignatureUpdateRequest,
    ProgramRunRequest,
    ProgramValueCatalogRequest,
    ProjectVariableCreateRequest,
    ProjectVariableRevisionRequest,
    ProjectVariableUpdateRequest,
    RecordingMarkRequest,
    RecordingStartRequest,
    RecordingStopRequest,
    ReplaceAssetRequest,
    ReplayAnalyzeRequest,
    ReplayAnalyzeSessionRequest,
    ReplayCaptureRequest,
    ReplayCompareRequest,
    ReplayExportRequest,
    ScaffoldExtensionRequest,
    SealAndroidJvmExtensionRequest,
    TargetConfigurationRequest,
    TestWindowsTargetRequest,
    TriggerDeleteRequest,
    TriggerSaveRequest,
    UpdateAssetRequest,
    TrustExtensionRequest,
    WorkspaceOpenRequest,
    WorkspacePathRequest,
    WorkspaceProgramRecoveryRequest,
    ViewStateRequest,
    VisionPreviewRequest,
)
from api.errors import failure_detail as api_failure_detail
from api.idempotency import execute_idempotent
from core.vnext import (
    RuntimeFailure,
    VNextWorkspaceError,
    vnext_runtime,
    vnext_workspace_manager,
)
from core.vnext.ide_settings_v6 import IdeSettingsError, ide_settings_store
from core.vnext.message_runtime_v6 import (
    MessageRuntimeError,
    MessageRuntimeV6,
    program_uses_messages,
)
from core.vnext.player_bindings import player_binding_contract
from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager
from core.vnext.program_repository import (
    ProgramConflictError,
    ProgramDocumentCorruptError,
    ProgramDocumentNotFoundError,
    ProgramDocumentValidationError,
)
from core.vnext.program_runtime_v6 import assert_available_runtime_contracts_are_bound
from core.vnext.program_service_v6 import (
    ProgramCommandRequestError,
    ProgramEntryPointDeletionError,
    ProgramReferencedError,
)
from core.vnext.project_variable_service_v6 import (
    ProjectVariableNotFoundError,
    ProjectVariableReferencedError,
    ProjectVariableRequestError,
)
from core.vnext.project_variables_v6 import ProjectVariableRegistryCorruptError
from core.vnext.target_service import (
    TargetConfigurationCorruptError,
    TargetConflictError,
    TargetNotFoundError,
    TargetReferencedError,
    TargetRequestError,
    TargetServiceError,
)


def create_vnext_router() -> APIRouter:
    error_responses = {
        status: {'model': ApiErrorResponse, 'description': description}
        for status, description in (
            (400, '请求无效'), (404, '资源不存在'), (409, '状态冲突'),
            (410, '已退役接口'),
            (422, '字段校验失败'), (500, '内部错误'),
        )
    }
    router = APIRouter(prefix='/api/vnext', tags=['EasyCode vNext'], responses=error_responses)

    def failure_detail(code: str, message: str, *, action: str = 'retry', diagnostics=None):
        return api_failure_detail(
            code,
            message,
            action=action,
            recovery_message='请重新打开项目后重试' if action == 'reload_workspace' else '',
            diagnostics=diagnostics,
        )

    def translate(exc: VNextWorkspaceError):
        message = str(exc)
        action = 'reload_workspace' if any(word in message for word in ('工作区', '项目已切换', '身份')) else 'retry'
        raise HTTPException(
            status_code=409,
            detail=failure_detail('workspace_conflict', message, action=action),
        ) from exc

    def translate_program(exc: Exception):
        if isinstance(exc, ProgramConflictError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'program_revision_conflict',
                    'ProgramDocument 已被其他操作修改，当前命令未执行',
                    action='reload_workspace',
                    diagnostics=[{
                        'function_id': exc.function_id,
                        'expected_revision': exc.expected_revision,
                        'actual_revision': exc.actual_revision,
                    }],
                ),
            ) from exc
        if isinstance(exc, ProgramDocumentNotFoundError):
            raise HTTPException(
                status_code=404,
                detail=failure_detail(
                    'program_not_found', str(exc), action='reload_workspace',
                ),
            ) from exc
        if isinstance(exc, ProgramEntryPointDeletionError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'program_entry_delete_forbidden',
                    str(exc),
                    action='fix_request',
                    diagnostics=[{'function_id': exc.function_id, 'kind': 'entry_function'}],
                ),
            ) from exc
        if isinstance(exc, ProgramReferencedError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'program_referenced',
                    str(exc),
                    action='fix_request',
                    diagnostics=exc.references,
                ),
            ) from exc
        if isinstance(exc, (ProgramCommandRequestError, ProgramDocumentValidationError)):
            raise HTTPException(
                status_code=422,
                detail=failure_detail('program_command_invalid', str(exc), action='fix_request'),
            ) from exc
        if isinstance(exc, ProgramDocumentCorruptError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail('program_document_corrupt', str(exc), action='reload_workspace'),
            ) from exc
        if isinstance(exc, RuntimeFailure):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'program_runtime_unsupported',
                    str(exc),
                    action='fix_request',
                ),
            ) from exc
        if isinstance(exc, VNextWorkspaceError):
            translate(exc)
        raise exc

    def translate_message(exc: MessageRuntimeError):
        raise HTTPException(
            status_code=(
                404
                if exc.error_id in {'message.instance_unknown', 'message.batch_unknown'}
                else 409
            ),
            detail=failure_detail(
                exc.error_id,
                str(exc),
                action='retry' if exc.transient else 'fix_request',
            ),
        ) from exc

    def message_service_and_project(
        workspace_id: str,
        generation: int,
    ) -> tuple[MessageRuntimeV6, str]:
        project_namespace = vnext_workspace_manager.message_project_namespace(
            workspace_id,
            generation,
        )
        return MessageRuntimeV6(), project_namespace

    def translate_project_variable(exc: Exception):
        if isinstance(exc, ProgramConflictError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'project_variable_revision_conflict',
                    '项目变量已被其他操作修改，当前请求未执行',
                    action='reload_workspace',
                    diagnostics=[{
                        'expected_revision': exc.expected_revision,
                        'actual_revision': exc.actual_revision,
                    }],
                ),
            ) from exc
        if isinstance(exc, ProjectVariableNotFoundError):
            raise HTTPException(
                status_code=404,
                detail=failure_detail(
                    'project_variable_not_found',
                    f'项目变量不存在：{exc}',
                    action='reload_workspace',
                ),
            ) from exc
        if isinstance(exc, ProjectVariableReferencedError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'project_variable_referenced',
                    str(exc),
                    action='fix_request',
                    diagnostics=exc.references,
                ),
            ) from exc
        if isinstance(exc, ProjectVariableRequestError):
            raise HTTPException(
                status_code=422,
                detail=failure_detail(
                    'project_variable_invalid', str(exc), action='fix_request',
                ),
            ) from exc
        if isinstance(exc, ProjectVariableRegistryCorruptError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'project_variable_registry_corrupt',
                    str(exc),
                    action='reload_workspace',
                ),
            ) from exc
        if isinstance(exc, VNextWorkspaceError):
            translate(exc)
        raise exc

    def translate_target(exc: Exception):
        if isinstance(exc, TargetNotFoundError):
            raise HTTPException(
                status_code=404,
                detail=failure_detail(
                    'target_not_found',
                    f'运行目标不存在：{exc}',
                    action='reload_workspace',
                ),
            ) from exc
        if isinstance(exc, TargetConflictError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'target_revision_conflict',
                    str(exc),
                    action='reload_workspace',
                    diagnostics=[{
                        'expected_revision': exc.expected_revision,
                        'actual_revision': exc.actual_revision,
                    }],
                ),
            ) from exc
        if isinstance(exc, TargetReferencedError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'target_referenced',
                    str(exc),
                    action='fix_request',
                    diagnostics=exc.references,
                ),
            ) from exc
        if isinstance(exc, TargetRequestError):
            raise HTTPException(
                status_code=422,
                detail=failure_detail(
                    'target_configuration_invalid',
                    str(exc),
                    action='fix_request',
                ),
            ) from exc
        if isinstance(exc, TargetConfigurationCorruptError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(
                    'target_configuration_corrupt',
                    str(exc),
                    action='reload_workspace',
                ),
            ) from exc
        if isinstance(exc, VNextWorkspaceError):
            translate(exc)
        raise exc

    @router.get('/meta', response_model=MetaResponse)
    async def meta():
        return {
            'product': 'EasyCode', 'api_contract_version': VNEXT_CONTRACT_VERSION,
            'project_format_version': 6,
            'language_version': 1, 'ecir_version': 1,
            'platforms': ['windows', 'android_adb', 'android_local'],
        }

    @router.get('/functions')
    async def functions():
        return {'functions': vnext_workspace_manager.available_functions()}

    @router.get('/project-variables')
    async def project_variables(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.project_variables,
                x_workspace_id,
                x_workspace_generation,
            )
        except Exception as exc:
            translate_project_variable(exc)

    @router.post('/project-variables')
    async def create_project_variable(
        payload: ProjectVariableCreateRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            values = payload.model_dump(mode='json')
            expected_revision = values.pop('expected_revision')
            return await run_in_threadpool(
                vnext_workspace_manager.create_project_variable,
                x_workspace_id,
                x_workspace_generation,
                expected_revision=expected_revision,
                **values,
            )
        except Exception as exc:
            translate_project_variable(exc)

    @router.patch('/project-variables/{variable_id}')
    async def update_project_variable(
        variable_id: str,
        payload: ProjectVariableUpdateRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            values = payload.model_dump(mode='json', exclude_unset=True)
            expected_revision = values.pop('expected_revision')
            return await run_in_threadpool(
                vnext_workspace_manager.update_project_variable,
                x_workspace_id,
                x_workspace_generation,
                variable_id,
                expected_revision=expected_revision,
                changes=values,
            )
        except Exception as exc:
            translate_project_variable(exc)

    @router.delete('/project-variables/{variable_id}')
    async def delete_project_variable(
        variable_id: str,
        payload: ProjectVariableRevisionRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_project_variable,
                x_workspace_id,
                x_workspace_generation,
                variable_id,
                expected_revision=payload.expected_revision,
            )
        except Exception as exc:
            translate_project_variable(exc)

    @router.get('/project-variables/{variable_id}/references')
    async def project_variable_references(
        variable_id: str,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return {'references': await run_in_threadpool(
                vnext_workspace_manager.project_variable_references,
                x_workspace_id,
                x_workspace_generation,
                variable_id,
            )}
        except Exception as exc:
            translate_project_variable(exc)

    @router.get('/programs')
    async def list_programs(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return {'programs': await run_in_threadpool(
                vnext_workspace_manager.list_programs,
                x_workspace_id,
                x_workspace_generation,
            )}
        except Exception as exc:
            translate_program(exc)

    @router.get('/control-selectors/{selector_id}/references')
    async def control_selector_references(
        selector_id: str,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return {'references': await run_in_threadpool(
                vnext_workspace_manager.control_selector_references,
                x_workspace_id, x_workspace_generation, selector_id,
            )}
        except Exception as exc:
            translate_program(exc)

    @router.post('/control-selectors/repair')
    async def repair_control_selector(
        payload: ControlSelectorRepairRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.repair_control_selector,
                x_workspace_id, x_workspace_generation, payload.selector_id,
                payload.replacement.model_dump(mode='json'), payload.expected_revisions,
                payload.confirmed,
            )
        except Exception as exc:
            from core.vnext.control_selector_repair_v2 import ControlSelectorRepairError
            if isinstance(exc, ControlSelectorRepairError):
                raise HTTPException(
                    status_code=409,
                    detail=failure_detail(exc.error_id, str(exc), action='fix_request'),
                ) from exc
            translate_program(exc)

    @router.post('/programs')
    async def create_program(
        payload: ProgramCreateRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.create_program,
                x_workspace_id,
                x_workspace_generation,
                payload.display_name,
            )
        except Exception as exc:
            translate_program(exc)

    @router.get('/programs/{function_id}')
    async def get_program(
        function_id: str,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.load_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
            )
        except Exception as exc:
            translate_program(exc)

    @router.get('/programs/{function_id}/history')
    async def get_program_history(
        function_id: str,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.program_history,
                x_workspace_id,
                x_workspace_generation,
                function_id,
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/history/restore')
    async def restore_program_history(
        function_id: str,
        payload: ProgramHistoryRestoreRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.restore_program_history,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                expected_revision=payload.expected_revision,
                history_id=payload.history_id,
            )
        except Exception as exc:
            translate_program(exc)

    @router.patch('/programs/{function_id}')
    async def rename_program(
        function_id: str,
        payload: ProgramRenameRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.rename_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                expected_revision=payload.expected_revision,
                display_name=payload.display_name,
            )
        except Exception as exc:
            translate_program(exc)

    @router.put('/programs/{function_id}/signature')
    async def update_program_signature(
        function_id: str,
        payload: ProgramSignatureUpdateRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.update_program_signature,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                expected_revision=payload.expected_revision,
                parameters=[item.model_dump(mode='json') for item in payload.parameters],
                return_type=payload.return_type,
            )
        except Exception as exc:
            translate_program(exc)

    @router.delete('/programs/{function_id}')
    async def delete_program(
        function_id: str,
        payload: ProgramRevisionRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                expected_revision=payload.expected_revision,
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/commands')
    async def apply_program_command(
        function_id: str,
        payload: ProgramCommandRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.apply_program_command,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.expected_revision,
                payload.command.model_dump(mode='json'),
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/commands/batch')
    async def apply_program_commands(
        function_id: str,
        payload: ProgramCommandBatchRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.apply_program_commands,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.expected_revision,
                [command.model_dump(mode='json') for command in payload.commands],
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/extract')
    async def extract_program_statements(
        function_id: str,
        payload: ProgramExtractStatementsRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.extract_program_statements,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.expected_revision,
                list(payload.statement_ids),
                payload.display_name,
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/value-catalog')
    async def program_value_catalog(
        function_id: str,
        payload: ProgramValueCatalogRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.program_value_catalog,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.statement_id,
                payload.expected_type,
                [item.model_dump(mode='json') for item in payload.scope_bindings],
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/undo')
    async def undo_program(
        function_id: str,
        payload: ProgramRevisionRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.undo_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.expected_revision,
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/redo')
    async def redo_program(
        function_id: str,
        payload: ProgramRevisionRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.redo_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                payload.expected_revision,
            )
        except Exception as exc:
            translate_program(exc)

    @router.get('/message-instances')
    async def list_message_instances(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            service, project_namespace = await run_in_threadpool(
                message_service_and_project,
                x_workspace_id,
                x_workspace_generation,
            )
            instances = await run_in_threadpool(service.list_instances, project_namespace)
            return {
                'host_id': service.host_id(),
                'project_namespace': project_namespace,
                'instances': instances,
            }
        except MessageRuntimeError as exc:
            translate_message(exc)
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/message-instances')
    async def register_message_instance(
        payload: MessageInstanceRegisterRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            service, project_namespace = await run_in_threadpool(
                message_service_and_project,
                x_workspace_id,
                x_workspace_generation,
            )
            return await run_in_threadpool(
                service.register_instance,
                project_namespace,
                payload.display_name,
                instance_id=str(payload.instance_id or ''),
                endpoint_key=payload.endpoint_key,
                endpoint_kind=payload.endpoint_kind,
            )
        except MessageRuntimeError as exc:
            translate_message(exc)
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.patch('/message-instances/{instance_id}')
    async def rename_message_instance(
        instance_id: str,
        payload: MessageInstanceRenameRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            service, project_namespace = await run_in_threadpool(
                message_service_and_project,
                x_workspace_id,
                x_workspace_generation,
            )
            return await run_in_threadpool(
                service.rename_instance,
                project_namespace,
                instance_id,
                payload.display_name,
            )
        except MessageRuntimeError as exc:
            translate_message(exc)
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/programs/{function_id}/compile')
    async def compile_program(
        function_id: str,
        payload: ProgramCompileRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.compile_program,
                x_workspace_id,
                x_workspace_generation,
                function_id,
                target_platform=payload.target_platform,
            )
        except Exception as exc:
            translate_program(exc)

    @router.post('/programs/{function_id}/run')
    async def run_program(
        function_id: str,
        payload: ProgramRunRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            try:
                assert_available_runtime_contracts_are_bound()
                # ``no_target`` is an explicit execution choice, not a
                # request to fall back to the project's default target.  A
                # pure calculation/log/file task must remain independent of
                # minimized, disconnected, or busy UI targets.
                target = None if payload.target_platform == 'no_target' else (
                    vnext_workspace_manager.resolve_target(
                        x_workspace_id,
                        x_workspace_generation,
                        str(payload.target_id or ''),
                    )
                )
                platform = payload.target_platform or (str(target.get('type')) if target else 'no_target')
                compiled = await run_in_threadpool(
                    vnext_workspace_manager.program_runtime_plan,
                    x_workspace_id,
                    x_workspace_generation,
                    function_id,
                    target_platform=platform,
                    variable_overrides=payload.model_dump(
                        mode='json',
                    )['variable_overrides'],
                )
            except Exception as exc:
                if isinstance(exc, TargetServiceError):
                    translate_target(exc)
                if isinstance(exc, (
                    ProjectVariableRequestError,
                    ProjectVariableRegistryCorruptError,
                )):
                    translate_project_variable(exc)
                translate_program(exc)
            if not compiled.get('valid') or not compiled.get('execution_plan'):
                raise HTTPException(
                    status_code=409,
                    detail=failure_detail(
                        'program_compile_failed',
                        '程序检查未通过',
                        action='fix_request',
                        diagnostics=compiled.get('diagnostics') or [],
                    ),
                )
            try:
                message_context = None
                if program_uses_messages(compiled['execution_plan']):
                    message_service, project_namespace = message_service_and_project(
                        x_workspace_id,
                        x_workspace_generation,
                    )
                    message_context = message_service.instance_context(
                        project_namespace,
                        instance_id=str(payload.message_instance_id or ''),
                        default_display_name='IDE调试-1',
                        endpoint_key='ide-debug-1',
                    )
                return vnext_runtime.start(
                    compiled['execution_plan'],
                    debug=payload.debug,
                    target=target,
                    message_context=message_context,
                )
            except MessageRuntimeError as exc:
                translate_message(exc)
            except RuntimeFailure as exc:
                translate_program(exc)

        return await execute_idempotent(
            idempotency_key,
            'vnext.program.run',
            {
                'workspace_id': x_workspace_id,
                'workspace_generation': x_workspace_generation,
                'function_id': function_id,
                'payload': payload.model_dump(mode='json'),
            },
            operation,
        )

    @router.get('/player/binding-contract')
    async def get_player_binding_contract():
        return player_binding_contract()

    @router.get('/player/binding-sources')
    async def player_binding_sources(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.player_binding_sources,
                x_workspace_id,
                x_workspace_generation,
            )
        except Exception as exc:
            if isinstance(exc, TargetServiceError):
                translate_target(exc)
            if isinstance(exc, VNextWorkspaceError):
                translate(exc)
            translate_program(exc)

    @router.post('/player/preview-run')
    async def player_preview_run(
        payload: PlayerRuntimeRunRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            if payload.profile_id:
                raise HTTPException(
                    status_code=422,
                    detail=failure_detail(
                        'player_preview_profile_unsupported',
                        'IDE 预览直接使用当前表单值，不读取独立 Player 运行方案',
                        action='fix_request',
                    ),
                )
            try:
                assert_available_runtime_contracts_are_bound()
                prepared = await run_in_threadpool(
                    vnext_workspace_manager.player_preview_plan,
                    x_workspace_id,
                    x_workspace_generation,
                    values=payload.player_values,
                    action_control_id=payload.action_control_id,
                    target_id=str(payload.target_id or ''),
                )
            except Exception as exc:
                if isinstance(exc, TargetServiceError):
                    translate_target(exc)
                if isinstance(exc, VNextWorkspaceError):
                    translate(exc)
                translate_program(exc)
            if not prepared.get('valid') or not prepared.get('execution_plan'):
                raise HTTPException(
                    status_code=409,
                    detail=failure_detail(
                        'player_preview_compile_failed',
                        'Player 预览检查未通过',
                        action='fix_request',
                        diagnostics=prepared.get('diagnostics') or [],
                    ),
                )
            try:
                message_context = None
                if program_uses_messages(prepared['execution_plan']):
                    message_service, project_namespace = message_service_and_project(
                        x_workspace_id,
                        x_workspace_generation,
                    )
                    message_context = message_service.instance_context(
                        project_namespace,
                        instance_id=str(payload.message_instance_id or ''),
                        default_display_name='IDE Player 预览-1',
                        endpoint_key='ide-player-preview-1',
                    )
                return vnext_runtime.start(
                    prepared['execution_plan'],
                    # Runtime debug state is a structured options object, not
                    # a boolean feature flag.  An empty object enables the
                    # normal observable session without inventing breakpoints.
                    debug={},
                    target=prepared.get('target'),
                    message_context=message_context,
                )
            except MessageRuntimeError as exc:
                translate_message(exc)
            except RuntimeFailure as exc:
                translate_program(exc)

        return await execute_idempotent(
            idempotency_key,
            'vnext.player.preview-run',
            {
                'workspace_id': x_workspace_id,
                'workspace_generation': x_workspace_generation,
                'payload': payload.model_dump(mode='json'),
            },
            operation,
        )

    @router.post('/capture/control')
    async def control_capture_mode(
        payload: CaptureControlRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=0, alias='X-Workspace-Generation'),
    ):
        """Start the one-shot Windows UIA host for a validated vNext workspace.

        The legacy endpoint intentionally validates the legacy workspace.  vNext
        uses this explicit bridge so the global UIA host never starts for a stale
        browser tab or an unvalidated project identity.
        """
        try:
            vnext_workspace_manager.require_path(x_workspace_id, x_workspace_generation, writable=True)
            from core.services import capture_mode

            action = payload.action
            if action == 'start':
                result = await run_in_threadpool(capture_mode.start_mode, 'vnext')
                if not result.get('ok'):
                    raise HTTPException(status_code=409, detail=result.get('message') or '控件捕获启动失败')
                return {**result, **capture_mode.get_state()}
            if action == 'stop':
                await run_in_threadpool(capture_mode.stop_mode)
                return {'ok': True, **capture_mode.get_state()}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/capture/control/resolve')
    async def resolve_control_capture(
        payload: ResolveControlRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=0, alias='X-Workspace-Generation'),
    ):
        try:
            configuration = vnext_workspace_manager.target_configuration(
                x_workspace_id, x_workspace_generation,
            )
            target = next(
                (item for item in configuration.get('targets') or [] if item.get('target_id') == payload.target_id),
                None,
            )
            if not isinstance(target, dict):
                raise HTTPException(status_code=404, detail='控件捕获目标不存在')
            from core.vnext.control_capture_v6 import ControlCaptureError, resolve_control_candidates
            try:
                candidates = await run_in_threadpool(
                    resolve_control_candidates,
                    vnext_workspace_manager.require_path(
                        x_workspace_id, x_workspace_generation, writable=False,
                    ),
                    target,
                    payload.point,
                    payload.reference_size,
                )
            except ControlCaptureError as exc:
                raise HTTPException(status_code=409, detail={
                    'error_id': exc.error_id, 'message': str(exc), 'transient': exc.transient,
                }) from exc
            return {'candidates': candidates}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/player/runtime/bootstrap')
    async def player_runtime_bootstrap():
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            if not vnext_player_bundle_manager.available():
                return {'available': False}
            return await run_in_threadpool(vnext_player_bundle_manager.bootstrap)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/run')
    async def player_runtime_run(
        payload: Annotated[PlayerRuntimeRunRequest | None, Body()] = None,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        options = payload or PlayerRuntimeRunRequest()

        async def operation():
            try:
                if not vnext_player_bundle_manager.available():
                    vnext_player_bundle_manager.ensure_from_environment()
                return await run_in_threadpool(vnext_player_bundle_manager.start, options.model_dump())
            except PlayerBundleError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        return await execute_idempotent(
            idempotency_key,
            'vnext.player-runtime.run',
            options.model_dump(),
            operation,
        )

    @router.post('/player/runtime/dangerous-operations')
    async def player_runtime_dangerous_operations(
        payload: Annotated[PlayerRuntimeRunRequest | None, Body()] = None,
    ):
        """Resolve server-owned per-run confirmations before execution starts."""

        options = payload or PlayerRuntimeRunRequest()
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            request_payload = options.model_dump(mode='json')
            request_payload['dangerous_confirmations'] = []
            return await run_in_threadpool(
                vnext_player_bundle_manager.dangerous_operation_requirements,
                request_payload,
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/player/runtime/preflight')
    async def player_runtime_preflight(
        target_id: str = '',
        profile_id: str = '',
        profile_revision: int | None = None,
    ):
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(
                vnext_player_bundle_manager.preflight,
                target_id,
                profile_id,
                profile_revision,
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/player/runtime/profiles')
    async def player_runtime_profiles():
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(vnext_player_bundle_manager.profiles)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put('/player/runtime/profiles')
    async def save_player_runtime_profile(payload: PlayerProfileRequest):
        try:
            arguments = (
                payload.profile_id, payload.name, payload.target_id, payload.values,
                payload.expected_revision,
            )
            if payload.recording is None:
                # Keep the original five-argument manager seam intact for
                # embedded hosts and compatibility tests that do not opt in.
                return await run_in_threadpool(
                    vnext_player_bundle_manager.save_profile, *arguments,
                )
            return await run_in_threadpool(
                vnext_player_bundle_manager.save_profile,
                *arguments,
                payload.recording.model_dump(mode='json'),
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/player/runtime/recording')
    async def player_runtime_recording_status():
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(vnext_player_bundle_manager.recording_status)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/recording/stop')
    async def player_runtime_recording_stop():
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(vnext_player_bundle_manager.stop_recording)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.delete('/player/runtime/profiles/{profile_id}')
    async def delete_player_runtime_profile(profile_id: str):
        try:
            return await run_in_threadpool(vnext_player_bundle_manager.delete_profile, profile_id)
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/player/runtime/assets/{asset_id}/content')
    async def player_runtime_asset_content(asset_id: str):
        try:
            path, item = await run_in_threadpool(vnext_player_bundle_manager.asset_content, asset_id)
            return FileResponse(path, media_type=str(item.get('mime_type') or 'application/octet-stream'))
        except PlayerBundleError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get('/player/runtime/actions')
    async def player_runtime_actions(
        profile_id: str = '',
        profile_revision: int | None = None,
        target_id: str = '',
    ):
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(
                vnext_player_bundle_manager.terminal_action_availability,
                profile_id, profile_revision, target_id,
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/capture/start')
    async def player_runtime_capture_start(payload: PlayerCaptureStartRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.start_control_capture,
                payload.destination.model_dump(),
                origin=payload.origin,
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/capture/confirm')
    async def player_runtime_capture_confirm(payload: PlayerCaptureConfirmRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.confirm_control_capture,
                payload.capture_id, payload.destination.model_dump(), payload.result,
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/capture/cancel')
    async def player_runtime_capture_cancel(payload: PlayerCaptureCancelRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.cancel_control_capture,
                payload.capture_id, payload.destination.model_dump(),
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/images/restore')
    async def player_runtime_image_restore(payload: PlayerImageRestoreRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.restore_profile_image,
                payload.destination.model_dump(),
            )
        except PlayerBundleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/player/runtime/assets/override')
    async def player_runtime_asset_override(payload: AssetOverrideRequest):
        raise HTTPException(
            status_code=410,
            detail='全局 Player 图片覆盖已退役；请使用已发布字段动作和 revision 化配置方案',
        )

    @router.delete('/player/runtime/assets/override/{control_id}')
    async def player_runtime_asset_restore(control_id: str):
        raise HTTPException(
            status_code=410,
            detail='全局 Player 图片覆盖已退役；请恢复当前配置方案的私有图片覆盖',
        )

    def translate_extension(exc: Exception):
        if isinstance(exc, VNextWorkspaceError):
            translate(exc)
        raise HTTPException(
            status_code=409,
            detail=failure_detail(
                'extension_operation_failed', str(exc), action='fix_request',
            ),
        ) from exc

    @router.post('/extensions/scaffold')
    async def scaffold_extension(
        payload: ScaffoldExtensionRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.scaffold_extension,
                x_workspace_id,
                x_workspace_generation,
                package_id=payload.package_id,
                publisher_id=payload.publisher_id,
                publisher_name=payload.publisher_name,
                display_name=payload.display_name,
                description=payload.description,
                scope=payload.scope,
            )
        except (VNextWorkspaceError, RuntimeFailure, ValueError) as exc:
            translate_extension(exc)

    @router.post('/extensions/import')
    async def import_extension(
        payload: ImportExtensionRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.import_extension,
                x_workspace_id,
                x_workspace_generation,
                source_path=payload.source_path,
                scope=payload.scope,
            )
        except (VNextWorkspaceError, RuntimeFailure, ValueError) as exc:
            translate_extension(exc)

    @router.get('/extensions')
    async def list_extensions(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.extension_packages, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/extensions/{package_id}')
    async def get_extension(
        package_id: str, scope: str | None = None,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.extension_package,
                x_workspace_id, x_workspace_generation, package_id, scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.post('/extensions/{package_id}/validate')
    async def validate_extension(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.validate_extension,
                x_workspace_id, x_workspace_generation, package_id, payload.scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.post('/extensions/{package_id}/references')
    async def extension_references(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.extension_references,
                x_workspace_id, x_workspace_generation, package_id, payload.scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.post('/extensions/{package_id}/trust')
    async def trust_extension(
        package_id: str, payload: TrustExtensionRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.trust_extension,
                x_workspace_id, x_workspace_generation, package_id,
                payload.scope, payload.mode,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.delete('/extensions/{package_id}/trust')
    async def untrust_extension(
        package_id: str, scope: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.untrust_extension,
                x_workspace_id, x_workspace_generation, package_id, scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    async def extension_scope_operation(
        operation: Callable[..., Any], package_id: str, payload: ExtensionScopeRequest,
        workspace_id: str, generation: int,
    ):
        try:
            return await run_in_threadpool(
                operation, workspace_id, generation, package_id, payload.scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.post('/extensions/{package_id}/enable')
    async def enable_extension(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        return await extension_scope_operation(
            vnext_workspace_manager.enable_extension, package_id, payload,
            x_workspace_id, x_workspace_generation,
        )

    @router.post('/extensions/{package_id}/disable')
    async def disable_extension(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        return await extension_scope_operation(
            vnext_workspace_manager.disable_extension, package_id, payload,
            x_workspace_id, x_workspace_generation,
        )

    @router.post('/extensions/{package_id}/build')
    async def build_extension(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        return await extension_scope_operation(
            vnext_workspace_manager.build_extension, package_id, payload,
            x_workspace_id, x_workspace_generation,
        )

    @router.post('/extensions/{package_id}/seal-android-jvm')
    async def seal_android_jvm_extension(
        package_id: str, payload: SealAndroidJvmExtensionRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.seal_android_jvm_extension,
                x_workspace_id,
                x_workspace_generation,
                package_id,
                payload.scope,
                variant_id=payload.variant_id,
                module_path=payload.module_path,
            )
        except (VNextWorkspaceError, RuntimeFailure, ValueError) as exc:
            translate_extension(exc)

    @router.post('/extensions/{package_id}/open')
    async def open_extension_folder(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        return await extension_scope_operation(
            vnext_workspace_manager.open_extension_folder, package_id, payload,
            x_workspace_id, x_workspace_generation,
        )

    @router.post('/extensions/{package_id}/contract-tests')
    async def test_extension_contracts(
        package_id: str, payload: ExtensionScopeRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        return await extension_scope_operation(
            vnext_workspace_manager.test_extension_contracts, package_id, payload,
            x_workspace_id, x_workspace_generation,
        )

    @router.post('/extensions')
    async def create_extension_retired():
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'extension_source_editor_retired',
                '内置扩展源码编辑已退役；请使用 /extensions/scaffold 创建外部 IDE 骨架',
                action='fix_request',
            ),
        )

    @router.put('/extensions/{package_id}')
    async def update_extension_retired(package_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'extension_source_editor_retired',
                f'扩展 {package_id} 的清单与契约必须在外部 IDE 修改后重新校验',
                action='fix_request',
            ),
        )

    @router.post('/extensions/{package_id}/functions')
    async def add_extension_function_retired(package_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'extension_source_editor_retired',
                f'扩展 {package_id} 的函数契约只能来自 manifest/function contract JSON',
                action='fix_request',
            ),
        )

    @router.get('/extensions/{package_id}/source')
    @router.put('/extensions/{package_id}/source')
    async def extension_source_retired(package_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'extension_source_editor_retired',
                f'扩展 {package_id} 不再提供内置源码 GET/PUT；请打开外部 IDE 文件夹',
                action='fix_request',
            ),
        )

    @router.post('/analyze')
    async def analyze_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'source_api_retired',
                '格式 6 不再接受可编辑源码；请使用 ProgramDocument 结构命令',
                action='fix_request',
            ),
        )

    @router.post('/compile')
    async def compile_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '请使用 /programs/{function_id}/compile', action='fix_request'),
        )

    @router.post('/edit/call-argument')
    async def edit_retired_source_argument():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '请使用 ProgramDocument update_argument 命令', action='fix_request'),
        )

    @router.post('/run')
    async def run_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '请使用 /programs/{function_id}/run', action='fix_request'),
        )

    @router.post('/run-project')
    async def run_retired_project_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'source_api_retired',
                '格式 6 项目入口由 function_id 标识；请使用 /programs/{function_id}/run',
                action='fix_request',
            ),
        )

    @router.delete('/extensions/{package_id}/functions/{capability_id:path}')
    async def delete_extension_function_retired(package_id: str, capability_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'extension_source_editor_retired',
                f'不能在 EasyCode 内删除 {package_id} 的函数契约 {capability_id}；请在外部 IDE 修改清单',
                action='fix_request',
            ),
        )

    @router.delete('/extensions/{package_id}')
    async def delete_extension_package(
        package_id: str, scope: str,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_extension_package,
                x_workspace_id, x_workspace_generation, package_id, scope,
            )
        except (VNextWorkspaceError, RuntimeFailure) as exc:
            translate_extension(exc)

    @router.get('/runs/active')
    async def active_runs(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            project_path = await run_in_threadpool(
                vnext_workspace_manager.require_path,
                x_workspace_id,
                x_workspace_generation,
            )
            runs = await run_in_threadpool(vnext_runtime.active_snapshots, project_path)
            return {'runs': runs}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/runs/{execution_id}')
    async def run_status(execution_id: str, after_sequence: int | None = None):
        try:
            return vnext_runtime.snapshot(execution_id, after_sequence)
        except RuntimeFailure as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get('/runs/{execution_id}/events')
    async def run_events(execution_id: str, after_sequence: int = 0):
        async def stream():
            cursor = max(0, after_sequence)
            while True:
                try:
                    snapshot = await run_in_threadpool(vnext_runtime.wait_snapshot, execution_id, cursor, 15.0)
                except RuntimeFailure as exc:
                    payload = json.dumps({'message': str(exc)}, ensure_ascii=False)
                    yield f'event: error\ndata: {payload}\n\n'
                    return
                events = snapshot.get('events') or []
                if not events:
                    yield ': keepalive\n\n'
                for event in events:
                    cursor = max(cursor, int(event.get('sequence') or 0))
                    payload = json.dumps(event, ensure_ascii=False, separators=(',', ':'))
                    yield f'id: {cursor}\nevent: runtime\ndata: {payload}\n\n'
                if snapshot.get('status') in {'completed', 'failed', 'cancelled'} and snapshot.get('finished_at'):
                    terminal = {key: value for key, value in snapshot.items() if key != 'events'}
                    yield f'event: end\ndata: {json.dumps(terminal, ensure_ascii=False, separators=(",", ":"))}\n\n'
                    return

        return StreamingResponse(
            stream(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    @router.delete('/runs/{execution_id}')
    async def cancel_run(execution_id: str):
        try:
            return vnext_runtime.cancel(execution_id)
        except RuntimeFailure as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post('/runs/{execution_id}/pause')
    async def pause_run(execution_id: str):
        try:
            return vnext_runtime.pause(execution_id)
        except RuntimeFailure as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/runs/{execution_id}/resume')
    async def resume_run(execution_id: str):
        try:
            return vnext_runtime.resume(execution_id)
        except RuntimeFailure as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/runs/{execution_id}/step')
    async def step_run(execution_id: str):
        try:
            return vnext_runtime.step(execution_id)
        except RuntimeFailure as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get('/runs/{execution_id}/diagnostics')
    async def download_diagnostics(execution_id: str):
        try:
            path = vnext_runtime.diagnostic_path(execution_id)
            return FileResponse(path, media_type='application/zip', filename=f'{execution_id}-diagnostic.zip')
        except RuntimeFailure as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get('/runs/{execution_id}/failure-frame')
    async def download_failure_frame(execution_id: str):
        try:
            path = vnext_runtime.failure_frame_path(execution_id)
            return FileResponse(path, media_type='image/png', filename=f'{execution_id}-failure.png')
        except RuntimeFailure as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get('/replay/sessions')
    async def replay_sessions(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            sessions = await run_in_threadpool(
                vnext_workspace_manager.replay_sessions, x_workspace_id, x_workspace_generation,
            )
            return {'sessions': sessions}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/analysis-catalog')
    async def replay_analysis_catalog(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            result = await run_in_threadpool(
                vnext_workspace_manager.replay_analysis_catalog,
                x_workspace_id, x_workspace_generation,
            )
            return result
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/recording/status')
    async def recording_status(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.recording_status, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/recording/start')
    async def start_recording(
        payload: RecordingStartRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            options = payload.model_dump(exclude={'target_id'})
            return await run_in_threadpool(
                vnext_workspace_manager.start_recording,
                x_workspace_id, x_workspace_generation, payload.target_id, options,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/recording/stop')
    async def stop_recording(
        payload: RecordingStopRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.stop_recording,
                x_workspace_id, x_workspace_generation, payload.reason,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/recording/mark')
    async def mark_recording(
        payload: RecordingMarkRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.mark_recording,
                x_workspace_id, x_workspace_generation, payload.label,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    def translate_operation_recording(exc: Exception):
        from core.vnext.operation_recording_v1 import OperationRecordingError
        if isinstance(exc, OperationRecordingError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(exc.error_id, str(exc), action='fix_request'),
            ) from exc
        translate_program(exc)

    @router.post('/operation-recording/start')
    async def start_operation_recording(
        payload: OperationRecordingStartRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.start_operation_recording,
                x_workspace_id, x_workspace_generation, payload.function_id,
                payload.expected_revision, payload.target_id, payload.location,
            )
        except Exception as exc:
            translate_operation_recording(exc)

    @router.post('/operation-recording/{session_id}/events')
    async def append_operation_recording_event(
        session_id: str, payload: OperationRecordingEventRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.append_operation_recording_event,
                x_workspace_id, x_workspace_generation, session_id, payload.event,
            )
        except Exception as exc:
            translate_operation_recording(exc)

    @router.post('/operation-recording/{session_id}/stop')
    async def stop_operation_recording(
        session_id: str, payload: OperationRecordingStopRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.stop_operation_recording,
                x_workspace_id, x_workspace_generation, session_id, payload.reason,
            )
        except Exception as exc:
            translate_operation_recording(exc)

    @router.post('/operation-recording/{session_id}/commit')
    async def commit_operation_recording(
        session_id: str, payload: OperationRecordingCommitRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.commit_operation_recording,
                x_workspace_id, x_workspace_generation, session_id, payload.review_events,
            )
        except Exception as exc:
            translate_operation_recording(exc)

    @router.delete('/operation-recording/{session_id}')
    async def cancel_operation_recording(
        session_id: str,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.cancel_operation_recording,
                x_workspace_id, x_workspace_generation, session_id,
            )
        except Exception as exc:
            translate_operation_recording(exc)

    def translate_trigger(exc: Exception):
        from core.vnext.triggers_v1 import TriggerError
        if isinstance(exc, TriggerError):
            raise HTTPException(
                status_code=409,
                detail=failure_detail(exc.error_id, str(exc), action='fix_request'),
            ) from exc
        translate_program(exc)

    @router.get('/triggers')
    async def trigger_configuration(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.trigger_configuration,
                x_workspace_id, x_workspace_generation,
            )
        except Exception as exc:
            translate_trigger(exc)

    @router.put('/triggers')
    async def save_trigger(
        payload: TriggerSaveRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.save_trigger,
                x_workspace_id, x_workspace_generation, payload.expected_revision, payload.trigger,
            )
        except Exception as exc:
            translate_trigger(exc)

    @router.delete('/triggers/{trigger_id}')
    async def delete_trigger(
        trigger_id: str, payload: TriggerDeleteRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_trigger,
                x_workspace_id, x_workspace_generation, payload.expected_revision, trigger_id,
            )
        except Exception as exc:
            translate_trigger(exc)

    @router.get('/triggers/events')
    async def trigger_events(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return {'events': await run_in_threadpool(
                vnext_workspace_manager.trigger_events,
                x_workspace_id, x_workspace_generation,
            )}
        except Exception as exc:
            translate_trigger(exc)

    @router.get('/replay/sessions/{session_id}/frames')
    async def replay_frames(
        session_id: str, offset: int = 0, limit: int = 200,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.replay_frames,
                x_workspace_id, x_workspace_generation, session_id, offset, limit,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}')
    async def replay_session_detail(
        session_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.replay_session_detail,
                x_workspace_id, x_workspace_generation, session_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/timeline')
    async def replay_timeline(
        session_id: str, offset: int = 0, limit: int = 500,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.replay_timeline,
                x_workspace_id, x_workspace_generation, session_id, offset, limit,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/sessions/{session_id}/verify')
    async def replay_verify(
        session_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.verify_replay_session,
                x_workspace_id, x_workspace_generation, session_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/frames/{frame_index}/image')
    async def replay_frame_image(
        session_id: str, frame_index: int, thumbnail: bool = False,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            content, path = await run_in_threadpool(
                vnext_workspace_manager.replay_frame_bytes,
                x_workspace_id, x_workspace_generation, session_id, frame_index,
                thumbnail=thumbnail,
            )
            media_type = 'image/jpeg' if thumbnail else 'image/png'
            filename = str(path).replace('\\', '/').rsplit('/', 1)[-1]
            return StreamingResponse(iter([content]), media_type=media_type, headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Cache-Control': 'private, max-age=60',
            })
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/analyze-frame')
    async def replay_analyze_frame(
        payload: ReplayAnalyzeRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.analyze_replay_frame,
                x_workspace_id, x_workspace_generation, payload.session_id, payload.frame_index,
                analysis_ids=list(payload.analysis_ids) or None,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/analyze-session')
    async def replay_analyze_session(
        payload: ReplayAnalyzeSessionRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.analyze_replay_session,
                x_workspace_id, x_workspace_generation, payload.session_id,
                changes_only=payload.changes_only,
                change_threshold=payload.change_threshold,
                step=payload.step,
                max_frames=payload.max_frames,
                analysis_ids=list(payload.analysis_ids) or None,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/compare')
    async def replay_compare(
        payload: ReplayCompareRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.compare_replay_frames,
                x_workspace_id, x_workspace_generation, payload.session_id,
                payload.left_frame_index, payload.right_frame_index,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/comparison.png')
    async def replay_comparison_image(
        session_id: str, left_frame_index: int, right_frame_index: int,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            content = await run_in_threadpool(
                vnext_workspace_manager.replay_comparison_image_bytes,
                x_workspace_id, x_workspace_generation, session_id,
                left_frame_index, right_frame_index,
            )
            return StreamingResponse(iter([content]), media_type='image/png', headers={
                'Content-Disposition': 'inline; filename="frame-difference.png"',
                'Cache-Control': 'private, max-age=60',
            })
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/analyses')
    async def replay_analysis_reports(
        session_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            reports = await run_in_threadpool(
                vnext_workspace_manager.replay_analysis_reports,
                x_workspace_id, x_workspace_generation, session_id,
            )
            return {'reports': reports}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/analyses/{analysis_run_id}')
    async def replay_analysis_report(
        session_id: str, analysis_run_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.replay_analysis_report,
                x_workspace_id, x_workspace_generation, session_id, analysis_run_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.delete('/replay/sessions/{session_id}/analyses/{analysis_run_id}')
    async def delete_replay_analysis_report(
        session_id: str, analysis_run_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_replay_analysis_report,
                x_workspace_id, x_workspace_generation, session_id, analysis_run_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/export')
    async def create_replay_export(
        payload: ReplayExportRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.create_replay_export,
                x_workspace_id, x_workspace_generation, payload.session_id,
                mode=payload.mode,
                analysis_run_ids=payload.analysis_run_ids,
                include_categories=payload.include_categories,
                frame_indices=payload.frame_indices,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/replay/sessions/{session_id}/exports/{export_id}')
    async def download_replay_export(
        session_id: str, export_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            path = await run_in_threadpool(
                vnext_workspace_manager.replay_export_path,
                x_workspace_id, x_workspace_generation, session_id, export_id,
            )
            return FileResponse(path, media_type='application/zip', filename=f'{export_id}.zip')
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/replay/capture')
    async def create_replay_capture(
        payload: ReplayCaptureRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.create_replay_capture,
                x_workspace_id, x_workspace_generation, payload.session_id, payload.frame_index,
                capture_session_id=payload.capture_session_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.delete('/replay/sessions/{session_id}')
    async def delete_replay_session(
        session_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_replay_session,
                x_workspace_id, x_workspace_generation, session_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/workspaces/inspect')
    async def inspect(payload: WorkspacePathRequest):
        try:
            return await run_in_threadpool(vnext_workspace_manager.inspect, payload.path)
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/workspaces/open')
    async def open_workspace(payload: WorkspaceOpenRequest):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.open, payload.path,
                initialize=payload.initialize, project_name=payload.project_name,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/workspaces/recover-program')
    async def recover_workspace_program(payload: WorkspaceProgramRecoveryRequest):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.recover_program_from_history,
                payload.path,
                payload.function_id,
                payload.history_id,
                payload.expected_revision,
            )
        except Exception as exc:
            translate_program(exc)

    @router.get('/workspaces/active')
    async def active():
        workspace = vnext_workspace_manager.active()
        programs = []
        project_variables = None
        target_configuration = {
            'schema_version': 1,
            'targets': [],
            'default_target_id': None,
            'revision': None,
        }
        if workspace:
            programs = await run_in_threadpool(
                vnext_workspace_manager.list_programs,
                workspace['workspace_id'],
                workspace['generation'],
            )
            project_variables = await run_in_threadpool(
                vnext_workspace_manager.project_variables,
                workspace['workspace_id'],
                workspace['generation'],
            )
            try:
                target_configuration = await run_in_threadpool(
                    vnext_workspace_manager.target_configuration,
                    workspace['workspace_id'],
                    workspace['generation'],
                )
            except Exception as exc:
                translate_target(exc)
        return {
            'workspace': workspace,
            'programs': programs,
            'project_variables': project_variables,
            **target_configuration,
        }

    @router.get('/targets')
    async def targets(
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.target_configuration,
                x_workspace_id,
                x_workspace_generation,
            )
        except Exception as exc:
            translate_target(exc)

    @router.post('/targets/windows/capture/resolve')
    async def resolve_window_capture(
        payload: ResolveWindowCaptureRequest,
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        from core.services.capture_session_service import CaptureSessionService

        return await run_in_threadpool(
            CaptureSessionService.resolve_window_capture,
            payload.model_dump(mode='json'),
            workspace_id=x_workspace_id,
            workspace_generation=x_workspace_generation,
        )

    @router.post('/targets/windows/test')
    async def test_windows_target(payload: TestWindowsTargetRequest):
        from core.vnext.window_binding_v2 import (
            WindowBindingResolutionError,
            flash_window,
            resolve_target_window,
        )

        try:
            candidate, method = await run_in_threadpool(
                resolve_target_window,
                payload.target.model_dump(mode='json', exclude_none=True),
            )
        except WindowBindingResolutionError as exc:
            raise HTTPException(
                status_code=409,
                detail=failure_detail(exc.error_id, str(exc), action='fix_request'),
            ) from exc
        await run_in_threadpool(flash_window, int(candidate['hwnd']))
        return {
            'ok': True,
            'title': str(candidate.get('title') or ''),
            'application': str(candidate.get('executable_name') or ''),
            'window_rect': list(candidate.get('rect') or []),
            'binding_method': method,
            'message': '已找到并高亮目标窗口',
        }

    @router.post('/vision/preview')
    async def preview_vision(
        payload: VisionPreviewRequest,
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        try:
            values = payload.model_dump(mode='json')
            target_id = str(values.pop('target_id') or '')
            return await run_in_threadpool(
                vnext_workspace_manager.preview_vision,
                x_workspace_id,
                x_workspace_generation,
                target_id=target_id,
                **values,
            )
        except TargetServiceError as exc:
            translate_target(exc)
        except RuntimeFailure as exc:
            raise HTTPException(
                status_code=409,
                detail=failure_detail(exc.error_id, str(exc), action='fix_request'),
            ) from exc
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/targets/adb-candidates')
    async def adb_candidates(
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.adb_candidates,
                x_workspace_id,
                x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.put('/targets')
    async def save_targets(
        payload: TargetConfigurationRequest,
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.save_targets, x_workspace_id, x_workspace_generation,
                [item.model_dump(mode='json') for item in payload.targets],
                payload.default_target_id,
                expected_revision=payload.expected_revision,
            )
        except Exception as exc:
            translate_target(exc)

    @router.get('/targets/{target_id}/references')
    async def target_references(
        target_id: str,
        x_workspace_id: Annotated[str, Header(alias='X-Workspace-ID')],
        x_workspace_generation: Annotated[int, Header(alias='X-Workspace-Generation')],
    ):
        try:
            references = await run_in_threadpool(
                vnext_workspace_manager.target_references,
                x_workspace_id,
                x_workspace_generation,
                target_id,
            )
            return {'target_id': target_id, 'references': references}
        except Exception as exc:
            translate_target(exc)

    @router.get('/assets')
    async def assets(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.list_assets, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/assets')
    async def import_asset(
        payload: ImportAssetRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.import_asset, x_workspace_id, x_workspace_generation,
                category=payload.category,
                folder=payload.folder,
                file_name=payload.file_name,
                display_name=payload.display_name,
                content_base64=payload.content_base64,
                source=payload.source,
                capture=payload.capture,
            )
        except Exception as exc:
            if isinstance(exc, TargetServiceError):
                translate_target(exc)
            if isinstance(exc, VNextWorkspaceError):
                translate(exc)
            raise

    @router.post('/asset-folders')
    async def create_asset_folder(
        payload: CreateAssetFolderRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.create_asset_folder,
                x_workspace_id, x_workspace_generation,
                payload.category, payload.folder,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/asset-folders/move')
    async def move_asset_folder(
        payload: MoveAssetFolderRequest,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.move_asset_folder,
                x_workspace_id, x_workspace_generation,
                payload.source_path, payload.target_parent,
                payload.name,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.delete('/asset-folders/{folder_path:path}')
    async def delete_asset_folder(
        folder_path: str, force: bool = False,
        x_workspace_id: str = Header(default=''), x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_asset_folder,
                x_workspace_id, x_workspace_generation, folder_path, force=force,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.patch('/assets/{asset_id}')
    async def update_asset(
        asset_id: str,
        payload: UpdateAssetRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            values = payload.model_dump(exclude_none=True)
            return await run_in_threadpool(
                vnext_workspace_manager.update_asset, x_workspace_id, x_workspace_generation, asset_id, **values,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.put('/assets/{asset_id}/content')
    async def replace_asset(
        asset_id: str,
        payload: ReplaceAssetRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.replace_asset, x_workspace_id, x_workspace_generation, asset_id,
                file_name=payload.file_name,
                content_base64=payload.content_base64,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/assets/{asset_id}/references')
    async def asset_references(
        asset_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            references = await run_in_threadpool(
                vnext_workspace_manager.asset_references, x_workspace_id, x_workspace_generation, asset_id,
            )
            return {'references': references}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.delete('/assets/{asset_id}')
    async def delete_asset(
        asset_id: str,
        force: bool = False,
        replacement_asset_id: str = '',
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.delete_asset, x_workspace_id, x_workspace_generation, asset_id,
                force=force, replacement_asset_id=replacement_asset_id,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/assets/{asset_id}/content')
    async def asset_content(
        asset_id: str,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            path, item = await run_in_threadpool(
                vnext_workspace_manager.asset_content, x_workspace_id, x_workspace_generation, asset_id,
            )
            return FileResponse(path, media_type=str(item.get('mime_type') or 'application/octet-stream'))
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/player/form')
    async def player_form(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.player_form, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.put('/player/form')
    async def save_player_form(
        payload: PlayerFormRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            try:
                return await run_in_threadpool(
                    vnext_workspace_manager.save_player_form,
                    x_workspace_id, x_workspace_generation, payload.model_dump(),
                )
            except Exception as exc:
                if isinstance(exc, TargetServiceError):
                    translate_target(exc)
                if isinstance(exc, VNextWorkspaceError):
                    translate(exc)
                raise

        return await execute_idempotent(
            idempotency_key,
            'vnext.player-form.save',
            {
                'workspace_id': x_workspace_id,
                'workspace_generation': x_workspace_generation,
                'payload': payload.model_dump(),
            },
            operation,
        )

    @router.get('/player/publish-report')
    async def player_publish_report(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.publish_report, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/player/publish')
    async def publish_player(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            try:
                return await run_in_threadpool(
                    vnext_workspace_manager.publish_player, x_workspace_id, x_workspace_generation,
                )
            except (VNextWorkspaceError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        return await execute_idempotent(
            idempotency_key,
            'vnext.player.publish',
            {'workspace_id': x_workspace_id, 'workspace_generation': x_workspace_generation},
            operation,
        )

    @router.get('/player/package-readiness')
    async def player_package_readiness(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.player_package_readiness, x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/player/package')
    async def package_player(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        async def operation():
            try:
                return await run_in_threadpool(
                    vnext_workspace_manager.package_player, x_workspace_id, x_workspace_generation,
                )
            except (VNextWorkspaceError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        return await execute_idempotent(
            idempotency_key,
            'vnext.player.package',
            {'workspace_id': x_workspace_id, 'workspace_generation': x_workspace_generation},
            operation,
        )

    @router.post('/player/android-package')
    async def package_android_player(
        request: Request,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        host = request.client.host if request.client else ''
        if host not in {'127.0.0.1', '::1', 'localhost', 'testclient'}:
            raise HTTPException(
                status_code=403,
                detail=failure_detail(
                    'android_bridge_local_only',
                    'APK 构建只允许 IDE 本机调用',
                    action='use_local_ide',
                ),
            )
        async def operation():
            try:
                return await run_in_threadpool(
                    vnext_workspace_manager.package_android_player,
                    x_workspace_id,
                    x_workspace_generation,
                )
            except (VNextWorkspaceError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        return await execute_idempotent(
            idempotency_key,
            'vnext.player.android-package',
            {'workspace_id': x_workspace_id, 'workspace_generation': x_workspace_generation},
            operation,
            timeout=3600,
        )

    @router.post('/workspaces/choose-folder')
    async def choose_folder(payload: Annotated[ChooseFolderRequest | None, Body()] = None):
        try:
            title = payload.title if payload else '选择 EasyCode vNext 项目文件夹'
            return {'path': await run_in_threadpool(vnext_workspace_manager.choose_folder, title)}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.post('/workspaces/choose-file')
    async def choose_file(payload: Annotated[ChooseFileRequest | None, Body()] = None):
        try:
            request = payload or ChooseFileRequest()
            return {'path': await run_in_threadpool(
                vnext_workspace_manager.choose_file, request.title, request.extensions,
            )}
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/sources')
    async def read_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '格式 6 不存在可编辑源码文件', action='fix_request'),
        )

    @router.put('/sources')
    async def save_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '请使用 ProgramDocument 结构命令', action='fix_request'),
        )
    @router.post('/sources/create')
    async def create_retired_source():
        raise HTTPException(
            status_code=410,
            detail=failure_detail('source_api_retired', '请使用 POST /programs', action='fix_request'),
        )
    @router.get('/debug-settings')
    async def debug_settings(
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.debug_settings,
                x_workspace_id, x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/ide-settings')
    async def ide_settings():
        return await run_in_threadpool(ide_settings_store.load)

    @router.put('/ide-settings')
    async def save_ide_settings(payload: IdeSettingsRequest):
        try:
            return await run_in_threadpool(ide_settings_store.save, payload.shortcuts)
        except IdeSettingsError as exc:
            raise HTTPException(
                status_code=422,
                detail=failure_detail('ide_settings.invalid_shortcut', str(exc), action='fix_request'),
            ) from exc

    @router.put('/debug-settings')
    async def save_debug_settings(
        payload: DebugSettingsRequest,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.save_debug_settings,
                x_workspace_id, x_workspace_generation, payload.breakpoints,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/view-state')
    async def get_view_state(
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.view_state,
                x_workspace_id,
                x_workspace_generation,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.put('/view-state')
    async def save_view_state(
        payload: ViewStateRequest,
        x_workspace_id: str = Header(default='', alias='X-Workspace-ID'),
        x_workspace_generation: int = Header(default=-1, alias='X-Workspace-Generation'),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.save_view_state,
                x_workspace_id,
                x_workspace_generation,
                payload.model_dump(mode='json'),
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/search')
    async def search_workspace(
        query: str = '',
        limit: int = 200,
        x_workspace_id: str = Header(default=''),
        x_workspace_generation: int = Header(default=-1),
    ):
        try:
            return await run_in_threadpool(
                vnext_workspace_manager.search_workspace,
                x_workspace_id, x_workspace_generation, query, limit,
            )
        except VNextWorkspaceError as exc:
            translate(exc)

    @router.get('/functions/{function_id}/references')
    async def retired_function_references(function_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'source_api_retired',
                f'旧源码函数 {function_id} 已退役；项目函数引用由 /programs/{{function_id}} 管理',
                action='fix_request',
            ),
        )

    @router.patch('/functions/{function_id}')
    async def rename_retired_function(function_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'source_api_retired',
                f'旧源码函数 {function_id} 已退役；请使用 PATCH /programs/{{function_id}}',
                action='fix_request',
            ),
        )

    @router.delete('/functions/{function_id}')
    async def delete_retired_function(function_id: str):
        raise HTTPException(
            status_code=410,
            detail=failure_detail(
                'source_api_retired',
                f'旧源码函数 {function_id} 已退役；请使用 DELETE /programs/{{function_id}}',
                action='fix_request',
            ),
        )

    return router
