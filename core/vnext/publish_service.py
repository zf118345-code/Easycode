"""Player publish and distribution application service."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .workspace_context import VNextWorkspaceError

if TYPE_CHECKING:
    from .workspace import VNextWorkspaceManager


class VNextPublishService:
    def __init__(self, owner: VNextWorkspaceManager, project_file: str) -> None:
        self._owner = owner
        self._project_file = project_file

    def report(self, workspace_id: str, generation: int) -> dict[str, Any]:
        with self._owner._lock:
            return self._report_locked(workspace_id, generation)

    def _report_locked(self, workspace_id: str, generation: int) -> dict[str, Any]:
        from .extensions import VNextExtensionRegistry
        from .publish import VNextPublisher

        owner = self._owner
        workspace = owner._require(workspace_id, generation)
        project = owner._read_json(os.path.join(workspace.project_path, self._project_file))
        entry_function_id = str(project.get('entry_function_id') or '')
        linked = owner.compile_program(workspace_id, generation, entry_function_id)
        extensions = VNextExtensionRegistry.publish_closure(workspace.project_path)
        return VNextPublisher(workspace.project_path).report(
            linked, owner.player_form(workspace_id, generation), extensions['errors'], extensions,
        )

    def build(self, workspace_id: str, generation: int) -> dict[str, Any]:
        with self._owner._lock:
            return self._build_locked(workspace_id, generation)

    def _build_locked(self, workspace_id: str, generation: int) -> dict[str, Any]:
        from .extensions import VNextExtensionRegistry
        from .publish import VNextPublisher

        owner = self._owner
        workspace = owner._require(workspace_id, generation, writable=True)
        project = owner._read_json(os.path.join(workspace.project_path, self._project_file))
        entry_function_id = str(project.get('entry_function_id') or '')
        linked = owner.compile_program(workspace_id, generation, entry_function_id)
        form = owner.player_form(workspace_id, generation)
        extensions = VNextExtensionRegistry.publish_closure(workspace.project_path)
        publisher = VNextPublisher(workspace.project_path)
        report = publisher.report(linked, form, extensions['errors'], extensions)
        target_configuration = owner.target_configuration(workspace_id, generation)
        project['targets_schema_version'] = target_configuration['schema_version']
        project['targets'] = target_configuration['targets']
        project['default_target_id'] = target_configuration['default_target_id']
        project['target_configuration_revision'] = target_configuration['revision']
        return publisher.build(linked, form, project, report, extension_packages=extensions)

    def readiness(self, workspace_id: str, generation: int) -> dict[str, Any]:
        from .distribution import (
            DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME,
            VNextDistributionAssembler,
        )

        self._owner._require(workspace_id, generation)
        root = Path(__file__).resolve().parents[2]
        return VNextDistributionAssembler(
            root / 'dist' / DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME,
            root / 'release' / 'player-web',
            require_current_runtime=True,
        ).readiness()

    def package(self, workspace_id: str, generation: int) -> dict[str, Any]:
        with self._owner._lock:
            return self._package_locked(workspace_id, generation)

    def _package_locked(self, workspace_id: str, generation: int) -> dict[str, Any]:
        from .distribution import (
            DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME,
            DistributionError,
            VNextDistributionAssembler,
        )

        owner = self._owner
        workspace = owner._require(workspace_id, generation, writable=True)
        published = self.build(workspace_id, generation)
        root = Path(__file__).resolve().parents[2]
        assembler = VNextDistributionAssembler(
            root / 'dist' / DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME,
            root / 'release' / 'player-web',
            require_current_runtime=True,
        )
        try:
            packaged = assembler.assemble(published['path'], str(Path(workspace.project_path) / 'dist'))
        except DistributionError as exc:
            raise VNextWorkspaceError(str(exc)) from exc
        except PermissionError as exc:
            raise VNextWorkspaceError(
                '无法替换旧 Player：Player_Bundle 正被正在运行的 EasyCode Player 占用。'
                '请通过 Player 右上角关闭窗口，确认任务已安全停止后重试。'
            ) from exc
        except OSError as exc:
            if getattr(exc, 'winerror', None) in {5, 32}:
                raise VNextWorkspaceError(
                    '无法替换旧 Player：Player_Bundle 仍被进程占用。'
                    '请完整关闭 Player 后重新生成。'
                ) from exc
            raise
        return {
            'published_bundle': published,
            **packaged,
            'release_id': published.get('release_id'),
            'signature': published.get('signature'),
        }

    def android_package(self, workspace_id: str, generation: int) -> dict[str, Any]:
        """Build a verified Android debug candidate from the current workspace.

        The IDE owns trust-root derivation so the renderer never handles author
        keys or stitches together arbitrary local paths.
        """

        from .android_delivery_v6 import AndroidDeliveryError, android_delivery_service_v6
        from .bundle_signing_v6 import BundleSignatureError, trust_root_document

        with self._owner._lock:
            owner = self._owner
            workspace = owner._require(workspace_id, generation, writable=True)
            published = self._build_locked(workspace_id, generation)
            report = published.get('report') or {}
            if report.get('android_build_declared') is not True:
                raise VNextWorkspaceError('当前项目没有声明 Android 本机交付目标')
            project = owner._read_json(os.path.join(workspace.project_path, self._project_file))
            try:
                trust_root = trust_root_document(
                    published.get('signature') or {},
                    str(project.get('project_id') or ''),
                )
            except BundleSignatureError as exc:
                raise VNextWorkspaceError(str(exc)) from exc
            output_root = Path(workspace.project_path) / 'dist' / 'android'
            output_root.mkdir(parents=True, exist_ok=True)
            trust_root_path = output_root / 'trust-root.json'
            temporary = output_root / '.trust-root.json.tmp'
            temporary.write_text(
                json.dumps(trust_root, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            os.replace(temporary, trust_root_path)
            try:
                built = android_delivery_service_v6.build(
                    published['path'],
                    trust_root_path,
                    variant='productionDebug',
                    output_path=output_root / 'EasyCodePlayer-android-debug.apk',
                )
            except AndroidDeliveryError as exc:
                raise VNextWorkspaceError(f'{exc.code}: {exc}') from exc
            return {
                **built,
                'published_bundle': published,
                'release_id': published.get('release_id'),
                'signature': published.get('signature'),
            }
