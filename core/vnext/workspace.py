"""Strict vNext project workspace and atomic source persistence."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from typing import Any

from .extension_service import VNextExtensionService
from .adb_discovery_v6 import discover_adb_candidates
from .extensions import VNextExtensionContractRegistry
from .function_contracts_v6 import official_function_registry_v6
from .ide_service import VNextIdeService
from .mutation import ProjectMutationTransaction
from .player_service import VNextPlayerService
from .program_compiler import lower_value_node
from .program_runtime_v6 import adapt_program_ecir_for_runtime
from .program_repository import ProgramDocumentRepository
from .program_service_v6 import ProgramServiceV6
from .project_variable_service_v6 import ProjectVariableServiceV6
from .publish_service import VNextPublishService
from .recording import VNextRecordingService
from .operation_recording_v1 import OperationRecordingServiceV1
from .replay import VNextReplayService
from .resource_service import VNextResourceService
from .target_service import VNextTargetService
from .triggers_v1 import TriggerServiceV1
from .vision_preview_v6 import preview_vision
from .update_service_v6 import VNextUpdateAuthorService
from .workspace_context import VNextWorkspace, VNextWorkspaceContext, VNextWorkspaceError
from .workspace_lifecycle import VNextWorkspaceLifecycleService

PROJECT_FORMAT_VERSION = 6
PROJECT_FILE = 'project.json'
LOCK_FILE = 'easycode.lock'
REQUIRED_DIRECTORIES = (
    'program/functions',
    'extensions',
    'extension-data',
    'assets/image',
    'assets/ocr',
    'assets/page',
    'player',
    'tests',
    '.easycode/history',
    '.easycode/cache',
    '.easycode/recovery',
)


def _atomic_write_text(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.easycode-write-', suffix='.tmp', dir=directory, text=True)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(temporary)
        raise


def _atomic_write_json(path: str, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class VNextWorkspaceManager:
    def __init__(self) -> None:
        self._context = VNextWorkspaceContext()
        self._lock = self._context.lock
        self._lifecycle = VNextWorkspaceLifecycleService(
            read_json=self._read_json,
            write_json=_atomic_write_json,
            project_file=PROJECT_FILE,
            lock_file=LOCK_FILE,
            format_version=PROJECT_FORMAT_VERSION,
            required_directories=REQUIRED_DIRECTORIES,
        )
        self._resources = VNextResourceService(self._context)
        self._project_variables = ProjectVariableServiceV6(self._context)
        self._extensions = VNextExtensionService(self._context)
        self._function_registry = VNextExtensionContractRegistry(
            self._context, official_function_registry_v6,
        )
        self._programs = ProgramServiceV6(self._context, self._function_registry)
        self._ide = VNextIdeService(self, self._context)
        self._targets = VNextTargetService(self._context, self._read_json, _atomic_write_json, PROJECT_FILE)
        self._player = VNextPlayerService(self)
        self._publishing = VNextPublishService(self, PROJECT_FILE)
        self._updates = VNextUpdateAuthorService(self, PROJECT_FILE)
        self._replay = VNextReplayService()
        self._recording = VNextRecordingService()
        self._operation_recording = OperationRecordingServiceV1()
        self._triggers = TriggerServiceV1()
        for name, service in (
            ('lifecycle', self._lifecycle),
            ('resources', self._resources),
            ('project_variables', self._project_variables),
            ('programs', self._programs),
            ('extensions', self._extensions),
            ('ide', self._ide),
            ('targets', self._targets),
            ('player', self._player),
            ('publishing', self._publishing),
            ('updates', self._updates),
            ('replay', self._replay),
            ('recording', self._recording),
            ('operation_recording', self._operation_recording),
            ('triggers', self._triggers),
        ):
            self._context.register_service(name, service)

    _atomic_write_text = staticmethod(_atomic_write_text)
    _atomic_write_json = staticmethod(_atomic_write_json)

    @staticmethod
    def canonicalize(path: str) -> str:
        return VNextWorkspaceLifecycleService.canonicalize(path)

    @staticmethod
    def _read_json(path: str) -> dict[str, Any]:
        try:
            with open(path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise VNextWorkspaceError(f'无法读取项目文件：{exc}') from exc
        if not isinstance(value, dict):
            raise VNextWorkspaceError('项目文件必须是JSON对象')
        return value

    def inspect(self, raw_path: str) -> dict[str, Any]:
        return self._lifecycle.inspect(raw_path)

    def initialize(self, raw_path: str, project_name: str = '') -> dict[str, Any]:
        return self._lifecycle.initialize(raw_path, project_name)

    def recover_program_from_history(
        self,
        raw_path: str,
        function_id: str,
        history_id: str,
        expected_revision: str,
    ) -> dict[str, Any]:
        """Explicit pre-open recovery for a damaged ProgramDocument."""
        with self._lock:
            path = self.canonicalize(raw_path)
            project = self._read_json(os.path.join(path, PROJECT_FILE))
            if project.get('format_version') != PROJECT_FORMAT_VERSION:
                raise VNextWorkspaceError('只能恢复当前格式的 EasyCode 项目')
            repository = ProgramDocumentRepository(path)
            restored = repository.restore_history(
                function_id,
                history_id,
                expected_revision=expected_revision,
            )
            return {
                'function_id': function_id,
                'revision': restored.revision,
                'inspection': self.inspect(path),
            }

    def open(self, raw_path: str, *, initialize: bool = False, project_name: str = '') -> dict[str, Any]:
        with self._lock:
            path = self.canonicalize(raw_path)
            recovered_transactions = ProjectMutationTransaction.recover(path) if os.path.isdir(path) else []
            inspection = self.inspect(path)
            if inspection['status'] in {'missing', 'empty'} and initialize:
                inspection = self.initialize(path, project_name)
            if inspection['status'] != 'valid':
                return {'workspace': None, 'inspection': inspection}
            previous = self._context.active_model()
            if (
                previous is not None
                and os.path.normcase(previous.project_path) != os.path.normcase(path)
            ):
                recording_state = self._recording.status(previous.project_path)
                if recording_state.get('active') and recording_state.get('owned_by_current_workspace'):
                    self._recording.stop(previous.project_path, 'workspace_switched')
                self._triggers.deactivate(previous.project_path)
            workspace = self._context.activate(
                workspace_id=f'workspace_{uuid.uuid4().hex}',
                project_id=inspection['project_id'], project_name=inspection['project_name'], project_path=path,
                read_only=bool(inspection.get('read_only')),
            )
            if not workspace.read_only:
                from .runtime import vnext_runtime

                def start_from_trigger(trigger: dict[str, Any]) -> dict[str, Any]:
                    target_id = str(trigger.get('target_id') or '')
                    target = self.resolve_target(workspace.workspace_id, workspace.generation, target_id) if target_id else None
                    platform = str(target.get('type') or '') if target else 'no_target'
                    compiled = self.program_runtime_plan(
                        workspace.workspace_id, workspace.generation,
                        str(trigger['entry_function_id']), target_platform=platform,
                    )
                    if not compiled.get('valid') or not compiled.get('execution_plan'):
                        raise VNextWorkspaceError('触发器入口检查未通过')
                    return vnext_runtime.start(compiled['execution_plan'], target=target)

                def trigger_run_active(execution_id: str) -> bool:
                    try:
                        return str(vnext_runtime.snapshot(execution_id).get('status') or '') in {'queued', 'running', 'paused'}
                    except Exception:
                        return False

                self._triggers.activate(path, start_from_trigger, trigger_run_active)
            return {
                'workspace': workspace.to_dict(), 'inspection': inspection,
                'programs': self.list_programs(workspace.workspace_id, workspace.generation),
                'project_variables': self.project_variables(
                    workspace.workspace_id,
                    workspace.generation,
                ),
                'recovered_transactions': recovered_transactions,
                **self.target_configuration(workspace.workspace_id, workspace.generation),
            }

    def active(self) -> dict[str, Any] | None:
        return self._context.active()

    def debug_settings(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._ide.debug_settings(workspace_id, generation)

    def save_debug_settings(
        self, workspace_id: str, generation: int, breakpoints: dict[str, list[str]],
    ) -> dict[str, Any]:
        with self._lock:
            return self._ide.save_debug_settings(workspace_id, generation, breakpoints)

    def view_state(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._ide.view_state(workspace_id, generation)

    def save_view_state(
        self, workspace_id: str, generation: int, value: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            return self._ide.save_view_state(workspace_id, generation, value)

    def search_workspace(
        self, workspace_id: str, generation: int, query: str, limit: int = 200,
    ) -> dict[str, Any]:
        return self._ide.search(workspace_id, generation, query, limit=limit)

    def asset_service(self, workspace_id: str, generation: int, *, writable: bool = False):
        """Return the project-scoped registry after validating workspace freshness."""
        return self._resources.registry(workspace_id, generation, writable=writable)

    def require_path(self, workspace_id: str, generation: int, *, writable: bool = False) -> str:
        """Public identity guard for project-scoped services shared with vNext."""
        return self._require(workspace_id, generation, writable=writable).project_path

    def message_project_namespace(self, workspace_id: str, generation: int) -> str:
        """Return the stable project identity used by runtime message routing."""

        return self._require(workspace_id, generation).project_id

    @contextlib.contextmanager
    def project_transaction(self, workspace_id: str, generation: int, *, writable: bool = False):
        """Hold the project-wide gate for one consistent read or mutation."""
        with self._lock:
            yield self._require(workspace_id, generation, writable=writable)

    def list_assets(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._resources.list(workspace_id, generation)

    def import_asset(self, workspace_id: str, generation: int, **payload: Any) -> dict[str, Any]:
        with self._lock:
            capture = payload.get('capture')
            target_id = str(
                capture.get('target_id') or ''
                if isinstance(capture, dict)
                else ''
            )
            if target_id:
                self.resolve_target(workspace_id, generation, target_id)
            return self._resources.import_base64(workspace_id, generation, **payload)

    def update_asset(self, workspace_id: str, generation: int, asset_id: str, **payload: Any) -> dict[str, Any]:
        with self._lock:
            return self._resources.update(workspace_id, generation, asset_id, **payload)

    def replace_asset(self, workspace_id: str, generation: int, asset_id: str, **payload: Any) -> dict[str, Any]:
        with self._lock:
            return self._resources.replace_base64(workspace_id, generation, asset_id, **payload)

    def asset_references(self, workspace_id: str, generation: int, asset_id: str) -> list[dict[str, Any]]:
        return self._resources.references(workspace_id, generation, asset_id)

    def delete_asset(self, workspace_id: str, generation: int, asset_id: str, *, force: bool = False, replacement_asset_id: str = '') -> dict[str, Any]:
        with self._lock:
            return self._resources.delete(
                workspace_id,
                generation,
                asset_id,
                force=force,
                replacement_asset_id=replacement_asset_id,
            )

    def asset_content(self, workspace_id: str, generation: int, asset_id: str) -> tuple[str, dict[str, Any]]:
        return self._resources.content_path(workspace_id, generation, asset_id)

    def create_asset_folder(self, workspace_id: str, generation: int, category: str, folder: str) -> dict[str, Any]:
        with self._lock:
            return self._resources.create_folder(workspace_id, generation, category, folder)

    def move_asset_folder(self, workspace_id: str, generation: int, source_path: str, target_parent: str, name: str) -> dict[str, Any]:
        with self._lock:
            return self._resources.move_folder(workspace_id, generation, source_path, target_parent, name)

    def delete_asset_folder(self, workspace_id: str, generation: int, path: str, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            return self._resources.delete_folder(workspace_id, generation, path, force=force)

    def player_form(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._player.form(workspace_id, generation)

    @staticmethod
    def _normalize_player_form(value: dict[str, Any]) -> dict[str, Any]:
        return VNextPlayerService.normalize_form(value)

    def save_player_form(self, workspace_id: str, generation: int, form: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._player.save(workspace_id, generation, form)

    def player_binding_sources(self, workspace_id: str, generation: int) -> dict[str, Any]:
        """Return workspace-linked, compiler-backed Player sources only."""

        return self._player.binding_sources(workspace_id, generation)

    def player_preview_plan(
        self,
        workspace_id: str,
        generation: int,
        *,
        values: dict[str, Any] | None = None,
        action_control_id: str = '',
        target_id: str = '',
    ) -> dict[str, Any]:
        """Build the same bound plan used by a packaged schema-3 Player."""

        return self._player.preview_plan(
            workspace_id,
            generation,
            values=values,
            action_control_id=action_control_id,
            target_id=target_id,
        )

    def apply_player_values(self, workspace_id: str, generation: int, ecir: dict[str, Any], values: dict[str, Any], action_control_id: str = '') -> dict[str, Any]:
        """Apply only developer-approved bindings to a private ECIR copy."""

        return self._player.apply_values(workspace_id, generation, ecir, values, action_control_id)

    def publish_report(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._publishing.report(workspace_id, generation)

    def publish_player(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._publishing.build(workspace_id, generation)

    def player_package_readiness(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._publishing.readiness(workspace_id, generation)

    def package_player(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._publishing.package(workspace_id, generation)

    def package_android_player(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._publishing.android_package(workspace_id, generation)

    def update_configuration(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._updates.configuration(workspace_id, generation)

    def save_update_configuration(
        self, workspace_id: str, generation: int, value: dict[str, Any],
    ) -> dict[str, Any]:
        return self._updates.save_configuration(workspace_id, generation, value)

    def target_configuration(
        self,
        workspace_id: str,
        generation: int,
    ) -> dict[str, Any]:
        return self._targets.configuration(workspace_id, generation)

    def adb_candidates(
        self,
        workspace_id: str,
        generation: int,
    ) -> dict[str, Any]:
        """Return read-only authoring candidates without changing target state."""

        self._require(workspace_id, generation)
        return discover_adb_candidates()

    def target_references(
        self,
        workspace_id: str,
        generation: int,
        target_id: str,
    ) -> list[dict[str, Any]]:
        return self._targets.references(workspace_id, generation, target_id)

    def resolve_target(
        self,
        workspace_id: str,
        generation: int,
        target_id: str = '',
    ) -> dict[str, Any] | None:
        return self._targets.resolve(workspace_id, generation, target_id)

    def preview_vision(
        self,
        workspace_id: str,
        generation: int,
        *,
        target_id: str,
        **options: Any,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        target = self.resolve_target(workspace_id, generation, target_id)
        if target is None:
            raise VNextWorkspaceError('当前项目没有可测试的运行目标')
        return preview_vision(path, target, **options)

    def save_targets(
        self,
        workspace_id: str,
        generation: int,
        targets: list[dict[str, Any]],
        default_target_id: str | None,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._targets.save(
                workspace_id,
                generation,
                expected_revision=expected_revision,
                targets=targets,
                default_target_id=default_target_id,
            )

    def _require(self, workspace_id: str, generation: int, *, writable: bool = False) -> VNextWorkspace:
        return self._context.require(workspace_id, generation, writable=writable)

    def list_programs(self, workspace_id: str, generation: int) -> list[dict[str, Any]]:
        return self._programs.list_documents(workspace_id, generation)

    def project_variables(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._project_variables.load(workspace_id, generation)

    def project_variable_references(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
    ) -> list[dict[str, Any]]:
        return self._project_variables.references(
            workspace_id,
            generation,
            variable_id,
        )

    def create_project_variable(
        self,
        workspace_id: str,
        generation: int,
        **payload: Any,
    ) -> dict[str, Any]:
        with self._lock:
            return self._project_variables.create(workspace_id, generation, **payload)

    def update_project_variable(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
        **payload: Any,
    ) -> dict[str, Any]:
        with self._lock:
            return self._project_variables.update(
                workspace_id,
                generation,
                variable_id,
                **payload,
            )

    def delete_project_variable(
        self,
        workspace_id: str,
        generation: int,
        variable_id: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._project_variables.delete(
                workspace_id,
                generation,
                variable_id,
                expected_revision=expected_revision,
            )

    def load_program(self, workspace_id: str, generation: int, function_id: str) -> dict[str, Any]:
        return self._programs.load(workspace_id, generation, function_id)

    def program_history(self, workspace_id: str, generation: int, function_id: str) -> dict[str, Any]:
        return self._programs.history(workspace_id, generation, function_id)

    def restore_program_history(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
        history_id: str,
    ) -> dict[str, Any]:
        return self._programs.restore_history(
            workspace_id,
            generation,
            function_id,
            expected_revision=expected_revision,
            history_id=history_id,
        )

    def create_program(self, workspace_id: str, generation: int, display_name: str) -> dict[str, Any]:
        with self._lock:
            return self._programs.create(workspace_id, generation, display_name)

    def rename_program(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
        display_name: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.rename(
                workspace_id,
                generation,
                function_id,
                expected_revision=expected_revision,
                display_name=display_name,
            )

    def update_program_signature(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
        parameters: list[dict[str, Any]],
        return_type: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.update_signature(
                workspace_id,
                generation,
                function_id,
                expected_revision=expected_revision,
                parameters=parameters,
                return_type=return_type,
            )

    def delete_program(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.delete(
                workspace_id,
                generation,
                function_id,
                expected_revision=expected_revision,
            )

    def apply_program_command(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        command: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.apply_command(
                workspace_id,
                generation,
                function_id,
                expected_revision,
                command,
            )

    def apply_program_commands(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        commands: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.apply_commands(
                workspace_id,
                generation,
                function_id,
                expected_revision,
                commands,
            )

    def extract_program_statements(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        expected_revision: str,
        statement_ids: list[str],
        display_name: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.extract_statements(
                workspace_id,
                generation,
                function_id,
                expected_revision,
                statement_ids,
                display_name,
            )

    def program_value_catalog(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        statement_id: str,
        expected_type: str,
        scope_bindings: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return self._programs.value_catalog(
            workspace_id,
            generation,
            function_id,
            statement_id,
            expected_type,
            scope_bindings,
        )

    def undo_program(
        self, workspace_id: str, generation: int, function_id: str, expected_revision: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.undo(workspace_id, generation, function_id, expected_revision)

    def redo_program(
        self, workspace_id: str, generation: int, function_id: str, expected_revision: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.redo(workspace_id, generation, function_id, expected_revision)

    def compile_program(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        target_platform: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            return self._programs.compile(
                workspace_id,
                generation,
                function_id,
                target_platform=target_platform,
            )

    def program_runtime_plan(
        self,
        workspace_id: str,
        generation: int,
        function_id: str,
        *,
        target_platform: str | None = None,
        variable_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace = self._require(workspace_id, generation)
        compiled = self.compile_program(
            workspace_id,
            generation,
            function_id,
            target_platform=target_platform,
        )
        if not compiled.get('valid') or not compiled.get('ecir'):
            return compiled
        execution_plan = adapt_program_ecir_for_runtime(
            compiled['ecir'],
            project_path=workspace.project_path,
        )
        validated_overrides = self._project_variables.validate_overrides(
            workspace_id,
            generation,
            variable_overrides,
        )
        execution_plan['project_variable_overrides'] = {
            variable_id: lower_value_node(value)
            for variable_id, value in validated_overrides.items()
        }
        return {
            **compiled,
            'execution_plan': execution_plan,
        }

    def extension_functions(self) -> list[dict[str, Any]]:
        definitions, _errors = self._extensions.definitions()
        return definitions

    def scaffold_extension(
        self, workspace_id: str, generation: int, *, package_id: str,
        publisher_id: str, publisher_name: str, display_name: str,
        description: str = '', scope: str = 'project',
    ) -> dict[str, Any]:
        with self._lock:
            return self._extensions.scaffold(
                workspace_id,
                generation,
                package_id=package_id,
                publisher_id=publisher_id,
                publisher_name=publisher_name,
                display_name=display_name,
                description=description,
                scope=scope,
            )

    def import_extension(
        self, workspace_id: str, generation: int, *, source_path: str, scope: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._extensions.import_package(
                workspace_id, generation, source_path=source_path, scope=scope,
            )

    def extension_packages(self, workspace_id: str, generation: int) -> dict[str, Any]:
        return self._extensions.packages(workspace_id, generation)

    def extension_package(
        self, workspace_id: str, generation: int, package_id: str, scope: str | None = None,
    ) -> dict[str, Any]:
        return self._extensions.package(workspace_id, generation, package_id, scope)

    def validate_extension(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        return self._extensions.validate(workspace_id, generation, package_id, scope)

    def extension_references(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        return self._extensions.references(workspace_id, generation, package_id, scope)

    def trust_extension(
        self, workspace_id: str, generation: int, package_id: str, scope: str, mode: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._extensions.trust(workspace_id, generation, package_id, scope, mode)

    def untrust_extension(
        self, workspace_id: str, generation: int, package_id: str, scope: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._extensions.untrust(workspace_id, generation, package_id, scope)

    def enable_extension(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        with self._lock:
            return self._extensions.enable(workspace_id, generation, package_id, scope)

    def disable_extension(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        with self._lock:
            return self._extensions.disable(workspace_id, generation, package_id, scope)

    def build_extension(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        with self._lock:
            return self._extensions.build(workspace_id, generation, package_id, scope)

    def seal_android_jvm_extension(
        self,
        workspace_id: str,
        generation: int,
        package_id: str,
        scope: str,
        *,
        variant_id: str,
        module_path: str,
    ) -> dict[str, Any]:
        with self._lock:
            return self._extensions.seal_android_jvm(
                workspace_id,
                generation,
                package_id,
                scope,
                variant_id=variant_id,
                module_path=module_path,
            )

    def open_extension_folder(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        return self._extensions.open_folder(workspace_id, generation, package_id, scope)

    def test_extension_contracts(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        return self._extensions.contract_tests(workspace_id, generation, package_id, scope)

    def delete_extension_package(self, workspace_id: str, generation: int, package_id: str, scope: str) -> dict[str, Any]:
        with self._lock:
            return self._extensions.delete_package(workspace_id, generation, package_id, scope)

    def available_functions(self) -> list[dict[str, Any]]:
        # A visible catalog entry is an executable promise.  Planned official
        # contracts and source-only extension prototypes stay out of insertion.
        return [
            *official_function_registry_v6.available_catalog(),
            *self.extension_functions(),
        ]

    def replay_sessions(self, workspace_id: str, generation: int) -> list[dict[str, Any]]:
        path = self.require_path(workspace_id, generation)
        return self._replay.list_sessions(path)

    def replay_frames(
        self, workspace_id: str, generation: int, session_id: str, offset: int = 0, limit: int = 200,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.list_frames(path, session_id, offset, limit)

    def replay_session_detail(
        self, workspace_id: str, generation: int, session_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.session_detail(path, session_id)

    def replay_timeline(
        self, workspace_id: str, generation: int, session_id: str, offset: int = 0, limit: int = 500,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.timeline(path, session_id, offset, limit)

    def verify_replay_session(
        self, workspace_id: str, generation: int, session_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.verify_session(path, session_id)

    def replay_frame_bytes(
        self, workspace_id: str, generation: int, session_id: str, frame_index: int, *, thumbnail: bool = False,
    ) -> tuple[bytes, str]:
        path = self.require_path(workspace_id, generation)
        if thumbnail:
            return self._replay.frame_thumbnail_bytes(path, session_id, frame_index), 'thumbnail.jpg'
        return self._replay.frame_bytes(path, session_id, frame_index)

    def _linked_replay_ecir(
        self,
        workspace_id: str,
        generation: int,
        session_id: str,
    ) -> tuple[str, dict[str, Any]]:
        path = self.require_path(workspace_id, generation)
        project = self._read_json(os.path.join(path, PROJECT_FILE))
        entry_function_id = str(project.get('entry_function_id') or '')
        # Replay is evaluated against an immutable recorded target frame, not
        # against the workspace's currently selected live target.  Preserve
        # the recording platform so target-dependent calls remain type-safe
        # without weakening the explicit no-target check used by IDE runs.
        session = self._replay.session_detail(path, session_id)
        target_platform = str(session.get('target_kind') or '').strip()
        if target_platform not in {'windows', 'android_adb', 'android_local'}:
            raise VNextWorkspaceError(
                '录制缺少有效的目标平台，无法安全解释目标相关函数；请重新录制'
            )
        linked = self.compile_program(
            workspace_id,
            generation,
            entry_function_id,
            target_platform=target_platform,
        )
        if not linked.get('valid') or not linked.get('ecir'):
            messages = [
                str(item.get('message') or '')
                for item in (linked.get('diagnostics') or [])
                if item.get('severity') == 'error'
            ]
            detail = '；'.join(item for item in messages[:5] if item) or '项目编译失败'
            raise VNextWorkspaceError(f'无法使用当前 ProgramDocument 回放：{detail}')
        return path, {
            **linked['ecir'],
            'ecir_revision': str(linked.get('ecir_revision') or ''),
        }

    def analyze_replay_frame(
        self, workspace_id: str, generation: int, session_id: str, frame_index: int,
        *, analysis_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        path, ecir = self._linked_replay_ecir(
            workspace_id, generation, session_id,
        )
        return self._replay.analyze_frame(
            path, ecir, session_id, frame_index, analysis_ids=analysis_ids,
        )

    def analyze_replay_session(
        self, workspace_id: str, generation: int, session_id: str, **options: Any,
    ) -> dict[str, Any]:
        path, ecir = self._linked_replay_ecir(
            workspace_id, generation, session_id,
        )
        return self._replay.analyze_session(path, ecir, session_id, **options)

    def replay_analysis_catalog(
        self, workspace_id: str, generation: int,
    ) -> dict[str, Any]:
        # The recorder and replay viewer remain useful while the project is an
        # incomplete draft.  Catalog discovery therefore reports compiler
        # availability as data instead of disguising it as a workspace conflict.
        path = self.require_path(workspace_id, generation)
        project = self._read_json(os.path.join(path, PROJECT_FILE))
        entry_function_id = str(project.get('entry_function_id') or '')
        linked = self.compile_program(workspace_id, generation, entry_function_id)
        if not linked.get('valid') or not linked.get('ecir'):
            diagnostics = list(linked.get('diagnostics') or [])
            messages = [
                str(item.get('message') or '')
                for item in diagnostics
                if item.get('severity') == 'error'
            ]
            detail = '；'.join(item for item in messages[:5] if item) or '项目编译失败'
            return {
                'available': False,
                'unavailable_reason': f'当前项目尚未通过检查：{detail}',
                'diagnostics': diagnostics,
                'analyses': [],
            }
        analyses = self._replay.analysis_catalog(linked['ecir'])
        return {
            'available': bool(analyses),
            'unavailable_reason': '' if analyses else '当前入口没有可回放的图像或 OCR 语句。',
            'diagnostics': [],
            'analyses': analyses,
        }

    def compare_replay_frames(
        self,
        workspace_id: str,
        generation: int,
        session_id: str,
        left_frame_index: int,
        right_frame_index: int,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.compare_frames(path, session_id, left_frame_index, right_frame_index)

    def replay_comparison_image_bytes(
        self,
        workspace_id: str,
        generation: int,
        session_id: str,
        left_frame_index: int,
        right_frame_index: int,
    ) -> bytes:
        path = self.require_path(workspace_id, generation)
        return self._replay.comparison_image_bytes(
            path, session_id, left_frame_index, right_frame_index,
        )

    def replay_analysis_reports(
        self, workspace_id: str, generation: int, session_id: str,
    ) -> list[dict[str, Any]]:
        path = self.require_path(workspace_id, generation)
        return self._replay.analysis_reports(path, session_id)

    def replay_analysis_report(
        self, workspace_id: str, generation: int, session_id: str, analysis_run_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.analysis_report(path, session_id, analysis_run_id)

    def delete_replay_analysis_report(
        self, workspace_id: str, generation: int, session_id: str, analysis_run_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._replay.delete_analysis_report(path, session_id, analysis_run_id)

    def create_replay_export(
        self, workspace_id: str, generation: int, session_id: str, **options: Any,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._replay.create_export(path, session_id, **options)

    def replay_export_path(
        self, workspace_id: str, generation: int, session_id: str, export_id: str,
    ) -> str:
        path = self.require_path(workspace_id, generation)
        return self._replay.export_path(path, session_id, export_id)

    def delete_replay_session(
        self, workspace_id: str, generation: int, session_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        state = self._recording.status(path)
        if state.get('active') and state.get('session_id') == session_id:
            raise VNextWorkspaceError('活动录制不能删除')
        return self._replay.delete_session(path, session_id)

    def create_replay_capture(
        self,
        workspace_id: str,
        generation: int,
        session_id: str,
        frame_index: int,
        *,
        capture_session_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        from core.services.capture_session_service import CaptureSessionService

        return CaptureSessionService.create_recording_snapshot(
            path,
            session_id,
            frame_index,
            session_id=capture_session_id,
            include_image=False,
        )

    def start_recording(
        self, workspace_id: str, generation: int, target_id: str = '', options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._recording.start(
            path,
            self.resolve_target(workspace_id, generation, target_id),
            options,
        )

    def recording_status(self, workspace_id: str, generation: int) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._recording.status(path)

    def control_selector_references(
        self, workspace_id: str, generation: int, selector_id: str,
    ) -> list[dict[str, str]]:
        path = self.require_path(workspace_id, generation)
        from .control_selector_repair_v2 import control_selector_repair_service
        return control_selector_repair_service.references(path, selector_id)

    def repair_control_selector(
        self, workspace_id: str, generation: int, selector_id: str,
        replacement: dict[str, Any], expected_revisions: dict[str, str], confirmed: bool,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        from .control_selector_repair_v2 import control_selector_repair_service
        return control_selector_repair_service.repair(
            path, selector_id, replacement,
            expected_revisions=expected_revisions, confirmed=confirmed,
        )

    def stop_recording(
        self, workspace_id: str, generation: int, reason: str = 'user',
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._recording.stop(path, reason)

    def mark_recording(
        self, workspace_id: str, generation: int, label: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._recording.mark(path, label)

    def start_operation_recording(
        self, workspace_id: str, generation: int, function_id: str,
        expected_revision: str, target_id: str, location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        target = self.resolve_target(workspace_id, generation, target_id)
        session = self._operation_recording.start(
            path, function_id=function_id, expected_revision=expected_revision,
            target_id=str(target.get('target_id') or ''), target_type=str(target.get('type') or ''),
            location=location,
        )
        if target.get('type') == 'windows':
            from .control_capture_v6 import resolve_control_candidates
            from .target_runtime import WindowsTargetDriver
            from .windows_operation_recorder_v1 import WindowsOperationRecorder

            driver = WindowsTargetDriver(path, target)
            box, hwnd = tuple(driver._box), int(driver.hwnd)
            driver.close()

            def accept(event: dict[str, Any]) -> None:
                if event.get('kind') in {'click', 'double_click', 'right_click'}:
                    point = event.get('point') or [0, 0]
                    try:
                        candidates = resolve_control_candidates(
                            path, target, (int(point[0]), int(point[1])),
                            (max(1, box[2] - box[0]), max(1, box[3] - box[1])),
                            capture_region=box, expected_hwnd=hwnd,
                        )
                        if candidates:
                            event['selector'] = candidates[0]['selector']
                            event['control_name'] = candidates[0]['label']
                    except Exception:
                        pass
                self._operation_recording.append(path, session['session_id'], event)

            host = WindowsOperationRecorder(accept, box=box, hwnd=hwnd)
            host.start()
            self._operation_recording.attach_host(session['session_id'], host)
            session['capture_host'] = 'windows_low_level_hooks'
        else:
            session['capture_host'] = 'target_preview_event_bridge'
        return session

    def append_operation_recording_event(
        self, workspace_id: str, generation: int, session_id: str, event: dict[str, Any],
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._operation_recording.append(path, session_id, event)

    def stop_operation_recording(
        self, workspace_id: str, generation: int, session_id: str, reason: str = 'user',
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._operation_recording.stop(path, session_id, reason=reason)

    def commit_operation_recording(
        self, workspace_id: str, generation: int, session_id: str, review_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._operation_recording.commit(
            path, session_id, self._programs, workspace_id, generation, review_events,
        )

    def cancel_operation_recording(
        self, workspace_id: str, generation: int, session_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._operation_recording.cancel(path, session_id)

    def trigger_configuration(self, workspace_id: str, generation: int) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation)
        return self._triggers.configuration(path)

    def save_trigger(
        self, workspace_id: str, generation: int, expected_revision: str, trigger: dict[str, Any],
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        ProgramDocumentRepository(path).load(str(trigger.get('entry_function_id') or ''))
        if trigger.get('target_id'):
            if self.resolve_target(workspace_id, generation, str(trigger['target_id'])) is None:
                raise VNextWorkspaceError('触发器引用的运行目标不存在')
        return self._triggers.save(path, expected_revision, trigger)

    def delete_trigger(
        self, workspace_id: str, generation: int, expected_revision: str, trigger_id: str,
    ) -> dict[str, Any]:
        path = self.require_path(workspace_id, generation, writable=True)
        return self._triggers.delete(path, expected_revision, trigger_id)

    def trigger_events(self, workspace_id: str, generation: int) -> list[dict[str, Any]]:
        path = self.require_path(workspace_id, generation)
        return self._triggers.events(path)

    @staticmethod
    def choose_folder(title: str = '选择 EasyCode vNext 项目文件夹') -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                return str(filedialog.askdirectory(title=title, mustexist=True) or '')
            finally:
                root.destroy()
        except Exception as exc:
            raise VNextWorkspaceError(f'无法打开Windows文件夹选择器：{exc}') from exc

    @staticmethod
    def choose_file(title: str = '选择文件', extensions: tuple[str, ...] = ()) -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog
            normalized: list[str] = []
            for extension in extensions:
                value = str(extension or '').strip().casefold()
                if not value:
                    continue
                normalized.append(value if value.startswith('.') else f'.{value}')
            filetypes: list[tuple[str, str]] = []
            if normalized:
                filetypes.append(('支持的文件', ' '.join(f'*{extension}' for extension in normalized)))
            filetypes.append(('所有文件', '*.*'))
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                return str(filedialog.askopenfilename(title=title, filetypes=filetypes) or '')
            finally:
                root.destroy()
        except Exception as exc:
            raise VNextWorkspaceError(f'无法打开 Windows 文件选择器：{exc}') from exc


vnext_workspace_manager = VNextWorkspaceManager()
