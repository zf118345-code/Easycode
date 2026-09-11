"""Secure, source-free vNext Player bundle loading and execution."""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from .bundle_signing_v6 import (
    BUNDLE_FORMAT_V6,
    BundleSignatureError,
    verify_signed_archive,
)
from .extension_schema_v6 import (
    ExtensionSchemaError,
    PublishedExtensionV1,
    load_easycode_lock,
    validate_published_extension,
)
from .message_runtime_v6 import MessageRuntimeError, MessageRuntimeV6, program_uses_messages
from .function_contracts_v6 import official_function_registry_v6
from .player_bindings import (
    PlayerBindingError,
    PLAYER_TERMINAL_ACTION_SPECS,
    apply_player_bindings,
    canonicalize_player_fixed_options,
    merge_target_overrides,
    player_terminal_action_closure,
    validate_player_form_bindings,
    validate_player_target_scope,
)
from .player_service import VNextPlayerService
from .resources import ProjectAssetService
from .recorder_v6 import V6FrameRecorder
from .recording import VNextRecordingService
from .recording_storage_v6 import RecordingStorageV6
from .program_serialization import canonical_json_bytes, content_revision
from .runtime import RuntimeFailure, vnext_runtime
from .target_service import TargetConfiguration, target_configuration_revision
from .update_client_v6 import (
    CommandPlatformInstaller,
    UpdateClient,
    UpdateClientConfig,
    UpdateClientError,
    UpdatePreferencesStore,
    native_platform,
)
from .update_service_v6 import (
    UpdateConfigurationError,
    validate_bundled_update_configuration,
)
from .workspace_context import VNextWorkspaceError


class PlayerBundleError(RuntimeError):
    pass


PLAYER_PROFILE_SCHEMA_VERSION = 3
PLAYER_FILE_ACTIONS = frozenset({'choose-file-read', 'choose-file-save', 'choose-directory'})


@dataclass(frozen=True, slots=True)
class PlayerControlDestination:
    """Immutable authority carried through both capture validation points."""

    product_id: str
    release_id: str
    profile_id: str
    control_id: str
    action_id: str
    profile_revision: int
    target_id: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> 'PlayerControlDestination':
        expected = {
            'product_id', 'release_id', 'profile_id', 'control_id',
            'action_id', 'profile_revision', 'target_id',
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise PlayerBundleError('PlayerControlDestination 字段不完整或包含未知字段')
        revision = value.get('profile_revision')
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise PlayerBundleError('PlayerControlDestination profile_revision 无效')
        strings = {key: str(value.get(key) or '').strip() for key in expected - {'profile_revision'}}
        required_strings = {key: item for key, item in strings.items() if key != 'target_id'}
        if any(not item for item in required_strings.values()):
            raise PlayerBundleError('PlayerControlDestination 稳定标识不能为空')
        return cls(profile_revision=revision, **strings)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_player_values(
    ecir: dict[str, Any], form: dict[str, Any], values: dict[str, Any] | None = None,
    action_control_id: str = '', *, selected_target_id: str | None = None,
) -> dict[str, Any]:
    """Apply only explicitly published values to a detached ECIR copy."""

    return apply_player_bindings(
        ecir,
        form,
        values,
        action_control_id,
        selected_target_id=selected_target_id,
        error=PlayerBundleError,
    )


class VNextPlayerBundleManager:
    """Own one verified extracted bundle for the lifetime of the Player process."""

    MAX_FILES = 20_000
    MAX_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024
    CONTROL_CAPTURE_TTL_SECONDS = 30 * 60

    def __init__(
        self,
        *,
        expected_public_key: str | bytes | Path | dict[str, Any] | None = None,
        require_trusted_key: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._expected_public_key = expected_public_key
        self._require_trusted_key = require_trusted_key
        self._bundle_path = ''
        self._runtime_root = ''
        self._manifest: dict[str, Any] = {}
        self._signature: dict[str, Any] = {}
        self._ecir: dict[str, Any] = {}
        self._form: dict[str, Any] = {}
        self._base_form: dict[str, Any] = {}
        self._project: dict[str, Any] = {}
        self._publish_report: dict[str, Any] = {}
        self._extension_lock: dict[str, Any] = {}
        self._extensions: dict[str, dict[str, Any]] = {}
        self._override_assets: dict[str, str] = {}
        self._profile_override_assets: dict[tuple[str, str], str] = {}
        self._active_capture: dict[str, Any] | None = None
        self._execution_ids: set[str] = set()
        # Player recording is process-local and must not share ownership with
        # an IDE recorder in tests or embedded development hosts.
        self._recording = VNextRecordingService(V6FrameRecorder())
        self._recording_monitors: dict[str, threading.Thread] = {}
        self._update_config: dict[str, Any] = {}
        self._update_clients: dict[str, UpdateClient] = {}
        self._update_preferences: dict[str, UpdatePreferencesStore] = {}
        self._update_monitors: dict[str, threading.Thread] = {}
        self._update_scheduler_stop = threading.Event()
        self._update_scheduler_thread: threading.Thread | None = None

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
        except Exception as exc:
            raise PlayerBundleError(f'Player 包文件无法读取：{path.name}（{exc}）') from exc
        if not isinstance(value, dict):
            raise PlayerBundleError(f'Player 包文件必须是 JSON 对象：{path.name}')
        return value

    @classmethod
    def _validate_members(cls, archive: zipfile.ZipFile) -> None:
        members = archive.infolist()
        if len(members) > cls.MAX_FILES:
            raise PlayerBundleError('Player 包文件数量超过安全上限')
        if sum(max(0, item.file_size) for item in members) > cls.MAX_UNCOMPRESSED_BYTES:
            raise PlayerBundleError('Player 包解压后体积超过安全上限')
        for item in members:
            name = item.filename.replace('\\', '/')
            path = PurePosixPath(name)
            if not name or path.is_absolute() or '..' in path.parts or ':' in path.parts[0]:
                raise PlayerBundleError(f'Player 包包含不安全路径：{item.filename}')
            # Unix symlinks inside ZIPs must not escape the verified extraction tree.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise PlayerBundleError(f'Player 包不允许符号链接：{item.filename}')

    def load(
        self,
        bundle_path: str,
        expected_public_key: str | bytes | Path | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            path = Path(bundle_path).expanduser().resolve()
            if not path.is_file():
                raise PlayerBundleError(f'Player 包不存在：{path}')
            if self._bundle_path == str(path) and self._runtime_root:
                return self.bootstrap()
            temporary = Path(tempfile.mkdtemp(prefix='EasyCodePlayer-'))
            try:
                with zipfile.ZipFile(path, 'r') as archive:
                    self._validate_members(archive)
                    configured_trust = (
                        expected_public_key
                        if expected_public_key is not None
                        else self._expected_public_key
                    )
                    if configured_trust is None:
                        configured_trust = (
                            str(os.environ.get('EASYCODE_PLAYER_TRUST_ROOT') or '').strip()
                            or str(os.environ.get('EASYCODE_PLAYER_TRUST_PUBLIC_KEY') or '').strip()
                            or None
                        )
                    require_trust = self._require_trusted_key or str(
                        os.environ.get('EASYCODE_PLAYER_REQUIRE_TRUST_ROOT') or ''
                    ).strip().lower() in {'1', 'true', 'yes', 'on'}
                    if require_trust and configured_trust is None:
                        raise PlayerBundleError('Player 缺少固定的发布者信任根')
                    try:
                        signature = verify_signed_archive(archive, configured_trust)
                    except BundleSignatureError as exc:
                        raise PlayerBundleError(str(exc)) from exc
                    archive.extractall(temporary)
                for required in (
                    'manifest.json', 'runtime/ecir.json', 'runtime/project.json',
                    'runtime/easycode.lock', 'player/form.json', 'publish-report.json',
                ):
                    if not (temporary / required).is_file():
                        raise PlayerBundleError(f'Player 包缺少必要文件：{required}')
                manifest = self._read_json(temporary / 'manifest.json')
                if int(manifest.get('bundle_format') or 0) != BUNDLE_FORMAT_V6:
                    raise PlayerBundleError('不支持此 Player 包版本')
                if not str(manifest.get('release_id') or ''):
                    raise PlayerBundleError('Player 包缺少不可变 release_id')
                if str(manifest.get('signing_key_id') or '') != signature['key_id']:
                    raise PlayerBundleError('Player 包清单与发布签名身份不一致')
                if manifest.get('source_included') is not False:
                    raise PlayerBundleError('Player 包未通过源码隔离检查')
                if any(item.suffix.lower() == '.easy' for item in temporary.rglob('*') if item.is_file()):
                    raise PlayerBundleError('Player 包意外包含 .easy 源码')
                try:
                    extension_lock_model = load_easycode_lock(temporary / 'runtime' / 'easycode.lock')
                except ExtensionSchemaError as exc:
                    raise PlayerBundleError(str(exc)) from exc
                extension_lock = extension_lock_model.model_dump(mode='json')
                lock_bytes = (temporary / 'runtime' / 'easycode.lock').read_bytes()
                if str(manifest.get('easycode_lock_sha256') or '') != hashlib.sha256(lock_bytes).hexdigest():
                    raise PlayerBundleError('Player 包 easycode.lock 与发布清单不一致')
                if int(manifest.get('extension_package_count') or 0) != len(extension_lock_model.extensions):
                    raise PlayerBundleError('Player 包扩展数量与发布清单不一致')
                extension_root = temporary / 'runtime' / 'extensions'
                actual_extension_files = {
                    item.relative_to(temporary).as_posix()
                    for item in extension_root.rglob('*')
                    if item.is_file()
                } if extension_root.is_dir() else set()
                expected_extension_files: set[str] = set()
                extensions: dict[str, dict[str, Any]] = {}
                locked_by_id = {item.package_id: item for item in extension_lock_model.extensions}
                for record in extension_lock_model.extensions:
                    descriptor_relative = f'runtime/extensions/{record.package_id}/extension.json'
                    descriptor_path = temporary.joinpath(*PurePosixPath(descriptor_relative).parts)
                    if not descriptor_path.is_file():
                        raise PlayerBundleError(f'Player 包缺少扩展运行描述：{record.package_id}')
                    try:
                        descriptor = PublishedExtensionV1.model_validate(self._read_json(descriptor_path))
                        validated = validate_published_extension(temporary, descriptor, record)
                    except (ExtensionSchemaError, ValueError) as exc:
                        raise PlayerBundleError(f'Player 扩展校验失败：{record.package_id}（{exc}）') from exc
                    expected_extension_files.add(descriptor_relative)
                    for variant in descriptor.variants:
                        expected_extension_files.add(variant.artifact_path)
                        expected_extension_files.add(variant.artifact_signature_path)
                    extensions[record.package_id] = {
                        'descriptor': descriptor.model_dump(mode='json'),
                        'validated': validated,
                    }
                    for dependency in record.dependencies:
                        installed = locked_by_id.get(dependency.package_id)
                        if (
                            installed is None
                            or installed.version != dependency.version
                            or installed.content_sha256 != dependency.content_sha256
                        ):
                            raise PlayerBundleError(
                                f'Player 扩展精确依赖不完整：{record.package_id} -> {dependency.package_id}'
                            )
                if actual_extension_files != expected_extension_files:
                    unexpected = sorted(actual_extension_files - expected_extension_files)
                    missing = sorted(expected_extension_files - actual_extension_files)
                    raise PlayerBundleError(
                        f'Player 扩展文件闭包不完整：unexpected={unexpected[:1]}, missing={missing[:1]}'
                    )
                ecir = self._read_json(temporary / 'runtime' / 'ecir.json')
                project = self._read_json(temporary / 'runtime' / 'project.json')
                form = self._read_json(temporary / 'player' / 'form.json')
                publish_report = self._read_json(temporary / 'publish-report.json')
                update_config: dict[str, Any] = {}
                update_path = temporary / 'update' / 'config.json'
                if update_path.is_file():
                    try:
                        update_config = validate_bundled_update_configuration(
                            self._read_json(update_path)
                        )
                    except UpdateConfigurationError as exc:
                        raise PlayerBundleError(str(exc)) from exc
                report_extension_ids = {
                    str(item.get('package_id') or '')
                    for item in publish_report.get('extensions') or []
                    if isinstance(item, dict)
                }
                if report_extension_ids != set(extensions):
                    raise PlayerBundleError('Player 发布报告与扩展锁定闭包不一致')
                expected_extension_permissions = sorted({
                    str(permission)
                    for item in extensions.values()
                    for permission in item['descriptor'].get('permissions') or []
                })
                if publish_report.get('extension_permissions') != expected_extension_permissions:
                    raise PlayerBundleError('Player 发布报告与扩展权限闭包不一致')
                if not ecir.get('entry_function_id') or not isinstance(ecir.get('functions'), list):
                    raise PlayerBundleError('Player 包运行指令不完整')
                if 'targets_schema_version' not in project:
                    raise PlayerBundleError('Player 包缺少目标配置版本')
                if not str(project.get('target_configuration_revision') or ''):
                    raise PlayerBundleError('Player 包缺少目标配置校验 revision')
                try:
                    target_configuration = TargetConfiguration.model_validate({
                        'schema_version': project.get('targets_schema_version', 1),
                        'targets': project.get('targets', []),
                        'default_target_id': project.get('default_target_id'),
                    })
                except Exception as exc:
                    raise PlayerBundleError(f'Player 包目标配置无效：{exc}') from exc
                actual_target_revision = target_configuration_revision(target_configuration)
                expected_target_revision = str(
                    project.get('target_configuration_revision') or ''
                )
                if expected_target_revision != actual_target_revision:
                    raise PlayerBundleError('Player 包目标配置校验失败')
                project['targets_schema_version'] = target_configuration.schema_version
                project['targets'] = [
                    item.model_dump(mode='json', exclude_none=True)
                    for item in target_configuration.targets
                ]
                project['default_target_id'] = target_configuration.default_target_id
                project['target_configuration_revision'] = actual_target_revision
                try:
                    form = VNextPlayerService.normalize_form(form)
                    validation_ecir = copy.deepcopy(ecir)
                    validation_ecir['targets'] = copy.deepcopy(project['targets'])
                    validate_player_form_bindings(
                        validation_ecir,
                        form,
                        targets=project['targets'],
                    )
                    terminal_closure = player_terminal_action_closure(form)
                    if publish_report.get('valid') is not True:
                        raise PlayerBundleError('Player 包发布报告未通过')
                    published_terminal_actions = publish_report.get('player_terminal_actions', [])
                    if not isinstance(published_terminal_actions, list) or published_terminal_actions != terminal_closure:
                        raise PlayerBundleError('Player 包终端动作发布闭包与表单不一致')
                    expected_capabilities = sorted({
                        str(item['capability']) for item in terminal_closure
                    })
                    published_terminal_capabilities = publish_report.get('player_terminal_capabilities', [])
                    if (
                        not isinstance(published_terminal_capabilities, list)
                        or published_terminal_capabilities != expected_capabilities
                    ):
                        raise PlayerBundleError('Player 包终端动作能力闭包不一致')
                except (PlayerBindingError, VNextWorkspaceError) as exc:
                    raise PlayerBundleError(f'Player 表单契约无效：{exc}') from exc
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
            previous = self._runtime_root
            self._bundle_path = str(path)
            self._runtime_root = str(temporary)
            self._manifest = manifest
            self._signature = signature
            self._ecir, self._base_form, self._form, self._project = ecir, copy.deepcopy(form), form, project
            self._publish_report = publish_report
            self._extension_lock = extension_lock
            self._extensions = extensions
            self._ecir['project_path'] = self._runtime_root
            self._override_assets = {}
            self._profile_override_assets = {}
            self._active_capture = None
            self._execution_ids = set()
            self._update_config = update_config
            self._configure_updates()
            if previous:
                shutil.rmtree(previous, ignore_errors=True)
            return self.bootstrap()

    def ensure_from_environment(self) -> bool:
        path = str(os.environ.get('EASYCODE_PLAYER_BUNDLE') or '').strip()
        if not path:
            return False
        self.load(path)
        return True

    def available(self) -> bool:
        return bool(self._runtime_root)

    def _require(self) -> None:
        if not self.available():
            raise PlayerBundleError('当前进程没有加载 Player 包')

    def _override_root(self) -> Path:
        root = self._data_root() / 'overrides'
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _data_root(self) -> Path:
        project_id = str(self._manifest.get('project_id') or 'unknown')
        safe_id = ''.join(char for char in project_id if char.isalnum() or char in {'-', '_'}) or 'unknown'
        configured = str(os.environ.get('EASYCODE_PLAYER_DATA_DIR') or '').strip()
        base = Path(configured) if configured else Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'EasyCode' / 'PlayerData'
        root = base / safe_id
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Restricted test/service accounts may not own LOCALAPPDATA. The
            # runtime remains usable and isolated, while desktop builds keep the
            # durable per-user path above.
            root = Path(tempfile.gettempdir()) / 'EasyCode' / 'PlayerData' / safe_id
            root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _update_storage_roots() -> tuple[Path, Path]:
        configured = str(os.environ.get('EASYCODE_UPDATE_DATA_DIR') or '').strip()
        base = (
            Path(configured)
            if configured
            else Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
            / 'EasyCode'
            / 'UpdateState'
        )
        cache_configured = str(os.environ.get('EASYCODE_UPDATE_CACHE_DIR') or '').strip()
        cache = Path(cache_configured) if cache_configured else base.parent / 'UpdateCache'
        return base, cache

    def _update_bundle_health(self, path: Path) -> bool:
        try:
            with zipfile.ZipFile(path, 'r') as archive:
                self._validate_members(archive)
                verify_signed_archive(archive, str(self._signature.get('public_key') or ''))
                names = {item.filename.replace('\\', '/') for item in archive.infolist()}
                return {
                    'manifest.json', 'runtime/ecir.json', 'runtime/project.json',
                    'runtime/easycode.lock', 'player/form.json', 'publish-report.json',
                }.issubset(names)
        except Exception:
            return False

    def _configure_updates(self) -> None:
        for client in self._update_clients.values():
            with contextlib.suppress(Exception):
                client.close()
        self._update_clients = {}
        self._update_preferences = {}
        domains = self._update_config.get('domains') if isinstance(self._update_config, dict) else None
        if not isinstance(domains, dict) or not domains:
            return
        durable_root, cache_root = self._update_storage_roots()
        host_platform, architecture = native_platform()
        for domain, raw in domains.items():
            product_id = str(raw['product_id'])
            preferences = UpdatePreferencesStore(durable_root, product_id)
            values = preferences.get(raw['initial_preferences'])
            if domain == 'project_content':
                current_release_id = str(self._manifest.get('release_id') or '')
                current_sequence = int(os.environ.get('EASYCODE_PLAYER_CONTENT_RELEASE_SEQUENCE') or 0)
            else:
                current_release_id = str(
                    os.environ.get('EASYCODE_PLAYER_APP_RELEASE_ID') or 'player-application-installed'
                )
                current_sequence = int(os.environ.get('EASYCODE_PLAYER_APP_RELEASE_SEQUENCE') or 0)
            config = UpdateClientConfig(
                enabled=True,
                product_id=product_id,
                domain=str(domain),
                platform=host_platform,
                architecture=architecture,
                current_release_id=current_release_id,
                current_release_sequence=current_sequence,
                channel=str(raw['channel']),
                automatic_checks=values['automatic_check'],
                required_policy_capability=bool(raw['required_policy_capability']),
                feed_base_url=str(raw['feed_base_url']),
                pinned_root=copy.deepcopy(raw['pinned_root']),
            )
            installer = None
            if domain == 'player_application' and host_platform == 'windows':
                helper_raw = str(os.environ.get('EASYCODE_WINDOWS_UPDATE_HELPER') or '').strip()
                if getattr(sys, 'frozen', False):
                    install_root = Path(sys.executable).resolve().parent
                    helper = install_root / 'EasycodeUpdateHelper.exe'
                    restart_command = [Path(sys.executable).name, *sys.argv[1:]]
                else:
                    install_raw = str(os.environ.get('EASYCODE_WINDOWS_INSTALL_ROOT') or '').strip()
                    restart_raw = str(os.environ.get('EASYCODE_WINDOWS_RESTART_COMMAND') or '').strip()
                    install_root = Path(install_raw).resolve() if install_raw else None
                    helper = Path(helper_raw).resolve() if helper_raw else Path()
                    try:
                        restart_command = json.loads(restart_raw) if restart_raw else []
                    except json.JSONDecodeError as exc:
                        raise PlayerBundleError('Windows 更新重启命令不是有效 JSON') from exc
                if helper.is_file() and install_root is not None and isinstance(restart_command, list):
                    installer = CommandPlatformInstaller(
                        [str(helper)],
                        durable_root / 'handoffs',
                        install_root=install_root,
                        restart_command=[str(item) for item in restart_command],
                    )
            try:
                client = UpdateClient(
                    config,
                    durable_root=durable_root,
                    cache_root=cache_root,
                    installer=installer,
                    health_check=self._update_bundle_health if domain == 'project_content' else None,
                )
                client.mark_runtime_state(running_or_paused=self._runtime_busy())
            except (UpdateClientError, OSError, ValueError) as exc:
                raise PlayerBundleError(f'Player 更新服务初始化失败：{exc}') from exc
            self._update_clients[str(domain)] = client
            self._update_preferences[str(domain)] = preferences
        if self._update_scheduler_thread is None or not self._update_scheduler_thread.is_alive():
            self._update_scheduler_stop.clear()
            self._update_scheduler_thread = threading.Thread(
                target=self._update_scheduler_loop,
                daemon=True,
                name='player-update-scheduler',
            )
            self._update_scheduler_thread.start()

    def _update_scheduler_loop(self) -> None:
        while not self._update_scheduler_stop.wait(30.0):
            with self._lock:
                clients = list(self._update_clients.items())
            for domain, client in clients:
                try:
                    preferences = self._update_preferences[domain].get(
                        self._update_config['domains'][domain]['initial_preferences']
                    )
                    for result in client.run_due_checks():
                        if result.available and preferences['automatic_download']:
                            client.download()
                            if preferences['automatic_apply']:
                                client.apply()
                except Exception:
                    # The client's local structured state is the visible
                    # diagnostic; maintenance failure never terminates Player.
                    continue

    def update_status(self) -> dict[str, Any]:
        with self._lock:
            self._require()
            if not self._update_clients:
                return {'enabled': False, 'domains': {}}
            domains: dict[str, Any] = {}
            for domain, client in self._update_clients.items():
                preferences = self._update_preferences[domain].get(
                    self._update_config['domains'][domain]['initial_preferences']
                )
                domains[domain] = {**client.status(), 'preferences': preferences}
            return {
                'enabled': True,
                'domains': domains,
                'telemetry': False,
                'task_execution_requires_network': False,
            }

    def save_update_preferences(self, domain: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            store = self._update_preferences.get(str(domain))
            if client is None or store is None:
                raise PlayerBundleError('该更新产品域未启用')
            try:
                preferences = store.save(values)
                client.set_automatic_checks(preferences['automatic_check'])
            except UpdateClientError as exc:
                raise PlayerBundleError(str(exc)) from exc
            return {'saved': True, 'domain': domain, 'preferences': preferences}

    def check_update(self, domain: str, *, policy_only: bool = False) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            if client is None:
                raise PlayerBundleError('该更新产品域未启用')
        return asdict(client.check(manual=not policy_only, policy_only=policy_only))

    def download_update(self, domain: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            if client is None:
                raise PlayerBundleError('该更新产品域未启用')
        try:
            path = client.download()
        except UpdateClientError as exc:
            raise PlayerBundleError(str(exc)) from exc
        return {'downloaded': True, 'domain': domain, 'path': str(path), 'status': client.status()}

    def apply_update(self, domain: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            if client is None:
                raise PlayerBundleError('该更新产品域未启用')
        try:
            result = client.apply()
            active_bundle = str(result.get('active_bundle_path') or '')
            if active_bundle and result.get('state') == 'complete':
                self.load(active_bundle, str(self._signature.get('public_key') or ''))
                result = self.update_status()['domains'][domain]
        except UpdateClientError as exc:
            raise PlayerBundleError(str(exc)) from exc
        return {'domain': domain, 'status': result}

    def reset_update_group(self, domain: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            if client is None:
                raise PlayerBundleError('该更新产品域未启用')
            try:
                code = client.reset_group_code()
            except UpdateClientError as exc:
                raise PlayerBundleError(str(exc)) from exc
            return {'reset': True, 'domain': domain, 'group_code': code}

    def update_group_code(self, domain: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            client = self._update_clients.get(str(domain))
            if client is None or client.identity is None:
                raise PlayerBundleError('该更新产品域未启用')
            return {'domain': domain, 'group_code': client.identity.get()}

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, path)

    def _override_manifest_path(self) -> Path:
        return self._override_root() / 'manifest.json'

    def _read_override_manifest(self) -> dict[str, Any]:
        path = self._override_manifest_path()
        if not path.is_file():
            return {'schema_version': 1, 'controls': {}}
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
        except Exception:
            return {'schema_version': 1, 'controls': {}}
        return value if isinstance(value, dict) and isinstance(value.get('controls'), dict) else {'schema_version': 1, 'controls': {}}

    def _write_override_manifest(self, value: dict[str, Any]) -> None:
        self._write_json_atomic(self._override_manifest_path(), value)

    def _profiles_path(self) -> Path:
        return self._data_root() / 'profiles.json'

    def _recording_feature_enabled(self) -> bool:
        features = self._form.get('features') if isinstance(self._form, dict) else {}
        return bool(features.get('recording')) if isinstance(features, dict) else False

    def _require_recording_feature(self) -> None:
        if not self._recording_feature_enabled():
            raise PlayerBundleError('当前 Player 未发布运行录制能力')

    @staticmethod
    def _normalize_recording_settings(
        value: Any,
        *,
        profile_revision: int,
        confirmed: bool | None = None,
    ) -> dict[str, Any]:
        raw = value if isinstance(value, dict) else {}
        allowed = {
            'enabled', 'strategy', 'target_fps', 'max_duration_ms',
            'max_session_bytes', 'min_free_bytes',
            'confirmed_profile_revision', 'confirm_current_revision',
        }
        unknown = set(raw) - allowed
        if unknown:
            raise PlayerBundleError(f'录制设置包含未知字段：{sorted(unknown)[0]}')
        strategy = str(raw.get('strategy') or 'changed_frames')
        if strategy not in {'all_frames', 'changed_frames', 'diagnostic'}:
            raise PlayerBundleError('录制策略无效')
        enabled = bool(raw.get('enabled'))
        explicit_confirmation = (
            bool(raw.get('confirm_current_revision'))
            if confirmed is None else bool(confirmed)
        )
        if enabled and confirmed is not None and not explicit_confirmation:
            raise PlayerBundleError('启用录制前必须明确确认到本次配置方案 revision')

        def number(name: str, default: float, low: float, high: float) -> float:
            candidate = raw.get(name, default)
            if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
                raise PlayerBundleError(f'录制设置 {name} 无效')
            rendered = float(candidate)
            if not low <= rendered <= high:
                raise PlayerBundleError(f'录制设置 {name} 超出范围')
            return rendered

        def integer(name: str, default: int, low: int, high: int) -> int:
            candidate = raw.get(name, default)
            if isinstance(candidate, bool) or not isinstance(candidate, int) or not low <= candidate <= high:
                raise PlayerBundleError(f'录制设置 {name} 无效')
            return candidate

        persisted_confirmation = raw.get('confirmed_profile_revision')
        if persisted_confirmation is not None and (
            isinstance(persisted_confirmation, bool)
            or not isinstance(persisted_confirmation, int)
            or persisted_confirmation < 1
        ):
            raise PlayerBundleError('录制确认 revision 无效')
        confirmed_revision = (
            profile_revision
            if enabled and explicit_confirmation
            else int(persisted_confirmation or 0) or None
        )
        return {
            'enabled': enabled,
            'strategy': strategy,
            'target_fps': number('target_fps', 15, 0.2, 60),
            'max_duration_ms': integer('max_duration_ms', 1_800_000, 1_000, 604_800_000),
            'max_session_bytes': integer('max_session_bytes', 2_147_483_648, 1_048_576, 1_000_000_000_000),
            'min_free_bytes': integer('min_free_bytes', 536_870_912, 67_108_864, 107_374_182_400),
            'confirmed_profile_revision': confirmed_revision,
        }

    def _read_profiles(self) -> dict[str, Any]:
        path = self._profiles_path()
        if not path.is_file():
            return {'schema_version': PLAYER_PROFILE_SCHEMA_VERSION, 'profiles': {}}
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PlayerBundleError(f'配置方案文档损坏：{exc}') from exc
        if not isinstance(value, dict) or set(value) - {'schema_version', 'profiles'}:
            raise PlayerBundleError('配置方案文档结构无效')
        schema_version = value.get('schema_version', 1)
        if schema_version not in {1, 2, PLAYER_PROFILE_SCHEMA_VERSION}:
            raise PlayerBundleError(f'不支持的配置方案文档版本：{schema_version}')
        raw_profiles = value.get('profiles')
        if not isinstance(raw_profiles, dict):
            raise PlayerBundleError('配置方案文档 profiles 必须是对象')
        normalized: dict[str, dict[str, Any]] = {}
        migrated = schema_version != PLAYER_PROFILE_SCHEMA_VERSION
        allowed = {
            'profile_id', 'name', 'target_id', 'values', 'revision',
            'image_overrides', 'recording', 'created_at', 'updated_at',
        }
        for profile_id, raw in raw_profiles.items():
            if not isinstance(raw, dict) or set(raw) - allowed:
                raise PlayerBundleError(f'配置方案 {profile_id} 结构无效')
            clean_id = str(profile_id or '').strip()
            if clean_id != str(raw.get('profile_id') or '') or not clean_id.startswith('profile_'):
                raise PlayerBundleError(f'配置方案 {profile_id} 的稳定 ID 无效')
            name = str(raw.get('name') or '').strip()
            if not name or len(name) > 80:
                raise PlayerBundleError(f'配置方案 {profile_id} 的名称无效')
            values = raw.get('values')
            overrides = raw.get('image_overrides', {})
            if not isinstance(values, dict) or not isinstance(overrides, dict):
                raise PlayerBundleError(f'配置方案 {profile_id} 的值结构无效')
            for control_id, record in overrides.items():
                if (
                    not str(control_id).strip()
                    or not isinstance(record, dict)
                    or set(record) != {'file', 'file_name', 'sha256'}
                ):
                    raise PlayerBundleError(f'配置方案 {profile_id} 的图片覆盖结构无效')
                file_value = str(record.get('file') or '')
                digest = str(record.get('sha256') or '')
                if (
                    Path(file_value).name != file_value
                    or not file_value.lower().endswith('.png')
                    or len(digest) != 64
                    or any(char not in '0123456789abcdef' for char in digest)
                ):
                    raise PlayerBundleError(f'配置方案 {profile_id} 的图片覆盖凭据无效')
            revision = raw.get('revision', 1)
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
                raise PlayerBundleError(f'配置方案 {profile_id} 的 revision 无效')
            target_id = raw.get('target_id')
            if target_id is not None and not isinstance(target_id, str):
                raise PlayerBundleError(f'配置方案 {profile_id} 的 target_id 无效')
            created_at = str(raw.get('created_at') or '').strip()
            updated_at = str(raw.get('updated_at') or '').strip()
            if not created_at or not updated_at:
                raise PlayerBundleError(f'配置方案 {profile_id} 的时间戳无效')
            normalized[clean_id] = {
                'profile_id': clean_id,
                'name': name,
                'target_id': target_id,
                'values': copy.deepcopy(values),
                'revision': revision,
                'image_overrides': copy.deepcopy(overrides),
                'recording': self._normalize_recording_settings(
                    raw.get('recording'), profile_revision=revision,
                ),
                'created_at': created_at,
                'updated_at': updated_at,
            }
            migrated = migrated or 'revision' not in raw or 'image_overrides' not in raw or 'recording' not in raw
        document = {'schema_version': PLAYER_PROFILE_SCHEMA_VERSION, 'profiles': normalized}
        if migrated:
            self._write_json_atomic(path, document)
        return document

    def profiles(self) -> dict[str, Any]:
        with self._lock:
            self._require()
            values = [
                self._materialize_profile(dict(item))
                for item in self._read_profiles()['profiles'].values()
                if isinstance(item, dict)
            ]
            values.sort(key=lambda item: (str(item.get('name') or '').casefold(), str(item.get('profile_id') or '')))
            return {'profiles': values}

    def _raw_profile(self, profile_id: str, expected_revision: int | None = None) -> dict[str, Any] | None:
        clean_id = str(profile_id or '').strip()
        if not clean_id:
            return None
        value = self._read_profiles()['profiles'].get(clean_id)
        if not isinstance(value, dict):
            raise PlayerBundleError(f'配置方案不存在：{clean_id}')
        if expected_revision is not None and int(value.get('revision') or 0) != expected_revision:
            raise PlayerBundleError('配置方案 revision 已过期，请重新载入')
        return copy.deepcopy(value)

    def _profile_override_path(self, profile_id: str, record: dict[str, Any]) -> Path:
        root = (self._data_root() / 'profiles' / profile_id / 'images').resolve()
        relative = str(record.get('file') or '')
        path = (root / relative).resolve()
        if root not in path.parents or not relative or not path.is_file():
            raise PlayerBundleError(f'配置方案 {profile_id} 的私有图片不存在')
        return path

    def _materialize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(profile)
        profile_id = str(result.get('profile_id') or '')
        values = dict(result.get('values') or {})
        for control_id, record in (result.get('image_overrides') or {}).items():
            if not isinstance(record, dict):
                raise PlayerBundleError(f'配置方案 {profile_id} 的图片覆盖结构无效')
            path = self._profile_override_path(profile_id, record)
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != str(record.get('sha256') or ''):
                raise PlayerBundleError(f'配置方案 {profile_id} 的私有图片校验失败')
            key = (profile_id, str(control_id))
            asset_id = self._profile_override_assets.get(key, '')
            if not asset_id:
                imported = ProjectAssetService(self._runtime_root).import_base64(
                    category='image',
                    folder=f'_player_profiles/{profile_id}',
                    file_name=str(record.get('file_name') or path.name),
                    display_name=f'{result.get("name") or profile_id} · {control_id}',
                    content_base64=base64.b64encode(content).decode('ascii'),
                    source='player_profile_override',
                    capture=None,
                )
                asset_id = str((imported.get('asset') or {}).get('asset_id') or '')
                if not asset_id:
                    raise PlayerBundleError(f'配置方案 {profile_id} 的私有图片无法载入')
                self._profile_override_assets[key] = asset_id
            values[str(control_id)] = {'asset_id': asset_id, 'asset_kind': 'image'}
        result['values'] = canonicalize_player_fixed_options(self._form, values)
        return result

    def _profile(self, profile_id: str, expected_revision: int | None = None) -> dict[str, Any] | None:
        raw = self._raw_profile(profile_id, expected_revision)
        return self._materialize_profile(raw) if raw is not None else None

    def save_profile(
        self, profile_id: str, name: str, target_id: str | None, values: dict[str, Any],
        expected_revision: int | None = None,
        recording: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._require()
            clean_name = str(name or '').strip()
            if not clean_name or len(clean_name) > 80:
                raise PlayerBundleError('配置方案名称必须为 1-80 个字符')
            clean_id = str(profile_id or '').strip() or f'profile_{uuid.uuid4().hex}'
            if not clean_id.startswith('profile_') or len(clean_id) > 96:
                raise PlayerBundleError('配置方案ID格式无效')
            selected_target = self._target(str(target_id or ''))
            controls = {
                str(control.get('control_id') or ''): control
                for page in self._form.get('pages') or []
                for control in page.get('controls') or []
                if isinstance(control, dict) and control.get('control_id')
            }
            unknown = sorted(set(values) - set(controls))
            if unknown:
                raise PlayerBundleError(f'配置方案包含未发布控件：{unknown[0]}')
            button_values = sorted(
                control_id for control_id in values
                if controls[control_id].get('type') == 'button'
            )
            if button_values:
                raise PlayerBundleError(f'配置方案不能保存函数按钮值：{button_values[0]}')
            selected_target_id = str((selected_target or {}).get('target_id') or '')
            validate_player_target_scope(
                self._form,
                values,
                selected_target_id,
                error=PlayerBundleError,
            )
            safe_values = {
                control_id: copy.deepcopy(value)
                for control_id, value in values.items()
            }
            # A packaged ECIR contains only the executable target closure, but
            # a developer may publish a setting for another registered target.
            # Validate profiles against the signed full target registry bundled
            # in runtime/project.json, exactly as save and publish do.
            profile_ecir = copy.deepcopy(self._ecir)
            profile_ecir['targets'] = copy.deepcopy(self._project.get('targets') or [])
            safe_values = canonicalize_player_fixed_options(self._form, safe_values)
            apply_player_values(
                profile_ecir,
                self._form,
                safe_values,
                selected_target_id=selected_target_id,
            )
            try:
                encoded = json.dumps(safe_values, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise PlayerBundleError('配置方案包含无法保存的值') from exc
            if len(encoded.encode('utf-8')) > 1024 * 1024:
                raise PlayerBundleError('配置方案超过 1MB 限制')
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            document = self._read_profiles()
            previous = document['profiles'].get(clean_id)
            if isinstance(previous, dict):
                if expected_revision is None:
                    raise PlayerBundleError('更新配置方案必须提供 expected_revision')
                if int(previous.get('revision') or 0) != expected_revision:
                    raise PlayerBundleError('配置方案 revision 已过期，请重新载入')
                revision = expected_revision + 1
            else:
                if expected_revision is not None:
                    raise PlayerBundleError('新建配置方案不能提供 expected_revision')
                revision = 1
            previous_recording = (
                previous.get('recording')
                if isinstance(previous, dict) and isinstance(previous.get('recording'), dict)
                else None
            )
            recording_feature_enabled = self._recording_feature_enabled()
            if recording is not None and bool(recording.get('enabled')) and not recording_feature_enabled:
                raise PlayerBundleError('当前 Player 未发布运行录制能力')
            if not recording_feature_enabled:
                normalized_recording = self._normalize_recording_settings(
                    {'enabled': False},
                    profile_revision=revision,
                )
            elif recording is not None:
                normalized_recording = self._normalize_recording_settings(
                    recording,
                    profile_revision=revision,
                    confirmed=bool(recording.get('confirm_current_revision')),
                )
            else:
                # Any profile mutation creates a new revision.  Existing
                # recording consent remains visible but becomes stale until
                # the terminal user explicitly confirms the new revision.
                normalized_recording = self._normalize_recording_settings(
                    previous_recording,
                    profile_revision=revision,
                )
            if normalized_recording['enabled'] and selected_target is None:
                raise PlayerBundleError('无操作目标不能启用逐帧录制')
            stored_values = copy.deepcopy(safe_values)
            if isinstance(previous, dict):
                for overridden_control_id in (previous.get('image_overrides') or {}):
                    stored_values.pop(str(overridden_control_id), None)
            profile = {
                'profile_id': clean_id, 'name': clean_name, 'target_id': target_id or None,
                'values': stored_values,
                'revision': revision,
                'image_overrides': copy.deepcopy(
                    previous.get('image_overrides') or {}
                    if isinstance(previous, dict) else {}
                ),
                'recording': normalized_recording,
                'created_at': str(previous.get('created_at') or now) if isinstance(previous, dict) else now,
                'updated_at': now,
            }
            document['profiles'][clean_id] = profile
            self._write_json_atomic(self._profiles_path(), document)
            return {'saved': True, 'profile': profile}

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            document = self._read_profiles()
            if document['profiles'].pop(str(profile_id or ''), None) is None:
                raise PlayerBundleError('配置方案不存在')
            self._write_json_atomic(self._profiles_path(), document)
            return {'deleted': True, 'profile_id': profile_id}

    @staticmethod
    def _frame_size(frame: Any) -> list[int]:
        shape = getattr(frame, 'shape', None)
        if shape is not None and len(shape) >= 2:
            return [int(shape[1]), int(shape[0])]
        image_size = getattr(frame, 'size', None)
        if isinstance(image_size, (tuple, list)) and len(image_size) >= 2:
            return [int(image_size[0]), int(image_size[1])]
        return []

    def preflight(
        self,
        target_id: str = '',
        profile_id: str = '',
        profile_revision: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._require()
            target = self._target(target_id)
            if profile_id:
                if profile_revision is None:
                    raise PlayerBundleError('环境检查已保存方案必须提供 profile_revision')
                profile = self._raw_profile(profile_id, profile_revision)
                if profile is None or str(profile.get('target_id') or '') != str(target_id or ''):
                    raise PlayerBundleError('环境检查目标与已保存方案不一致')
                if target is not None:
                    target = self._effective_profile_target(profile, target)
            checks: list[dict[str, Any]] = [{
                'id': 'bundle', 'status': 'pass', 'message': 'Player 包结构与源码隔离检查通过',
            }]
            try:
                self._assert_execution_platform(target)
            except PlayerBundleError as exc:
                checks.append({'id': 'target', 'status': 'fail', 'message': str(exc)})
                return {
                    'ready': False,
                    'target_id': str((target or {}).get('target_id') or '') or None,
                    'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'profile_id': profile_id or None,
                    'checks': checks,
                }
            if target is None:
                checks.append({'id': 'target', 'status': 'warning', 'message': '未选择操作目标；仅可运行不依赖屏幕的逻辑'})
                return {'ready': True, 'target_id': None, 'profile_id': profile_id or None, 'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'checks': checks}
            driver = None
            started = time.perf_counter()
            try:
                from .target_runtime import create_target_driver
                driver = create_target_driver(self._runtime_root, target)
                checks.append({'id': 'target', 'status': 'pass', 'message': f'目标“{target.get("name") or target.get("target_id")}”绑定成功'})
                frame = driver.capture_frame() if driver is not None else None
                size = self._frame_size(frame)
                checks.append({'id': 'capture', 'status': 'pass', 'message': f'画面获取成功{f"：{size[0]}×{size[1]}" if size else ""}', 'size': size})
                ready = True
            except Exception as exc:
                checks.append({'id': 'target', 'status': 'fail', 'message': str(exc)})
                ready = False
            finally:
                if driver is not None:
                    with contextlib.suppress(Exception):
                        driver.close()
            return {
                'ready': ready, 'target_id': str(target.get('target_id') or ''),
                'profile_id': profile_id or None,
                'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'duration_ms': round((time.perf_counter() - started) * 1000, 1), 'checks': checks,
            }

    @staticmethod
    def _control(form: dict[str, Any], control_id: str) -> dict[str, Any] | None:
        return next((control for page in form.get('pages') or [] for control in page.get('controls') or [] if str(control.get('control_id') or '') == control_id), None)

    def _install_override(self, control_id: str, file_name: str, content_base64: str) -> dict[str, Any]:
        service = ProjectAssetService(self._runtime_root)
        previous = self._override_assets.get(control_id)
        if previous:
            with contextlib.suppress(Exception):
                service.delete(previous, force=True)
        result = service.import_base64(
            category='image', folder='_player_overrides', file_name=file_name,
            display_name=f'Player 覆盖 · {control_id}', content_base64=content_base64,
            source='player_override', capture=None,
        )
        asset = dict(result['asset'])
        self._override_assets[control_id] = str(asset['asset_id'])
        control = self._control(self._form, control_id)
        if control is not None:
            control['default'] = asset['asset_id']
            control['override'] = {'active': True, 'asset_id': asset['asset_id'], 'file_name': file_name}
        return asset

    def _apply_persisted_overrides(self) -> None:
        manifest = self._read_override_manifest()
        root = self._override_root()
        for control_id, record in list((manifest.get('controls') or {}).items()):
            if not isinstance(record, dict):
                continue
            relative = str(record.get('file') or '')
            path = (root / relative).resolve()
            if root.resolve() not in path.parents or not path.is_file():
                continue
            control = self._control(self._form, str(control_id))
            if not control or control.get('type') != 'resource':
                continue
            try:
                self._install_override(str(control_id), str(record.get('file_name') or path.name), base64.b64encode(path.read_bytes()).decode('ascii'))
            except Exception:
                continue

    def create_resource_override(self, control_id: str, file_name: str, content_base64: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            control_id = str(control_id or '').strip()
            control = self._control(self._base_form, control_id)
            if not control or control.get('type') != 'resource':
                raise PlayerBundleError('该 Player 控件不是可替换的图片资源')
            # Validate content and extension through the same registry service used
            # by packaged assets before persisting anything outside the bundle.
            asset = self._install_override(control_id, file_name, content_base64)
            try:
                content = base64.b64decode(content_base64, validate=True)
            except Exception as exc:
                raise PlayerBundleError('覆盖图片内容无效') from exc
            extension = str(asset.get('extension') or '.png')
            root = self._override_root()
            stored_name = f'{control_id}{extension}'
            destination = (root / stored_name).resolve()
            if root.resolve() not in destination.parents:
                raise PlayerBundleError('覆盖资源路径无效')
            temporary = destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.tmp')
            temporary.write_bytes(content)
            os.replace(temporary, destination)
            manifest = self._read_override_manifest()
            manifest.setdefault('controls', {})[control_id] = {'file': stored_name, 'file_name': file_name}
            self._write_override_manifest(manifest)
            return {'ok': True, 'control_id': control_id, 'asset': asset, 'default': asset['asset_id']}

    def restore_resource_default(self, control_id: str) -> dict[str, Any]:
        with self._lock:
            self._require()
            control_id = str(control_id or '').strip()
            base_control = self._control(self._base_form, control_id)
            control = self._control(self._form, control_id)
            if not base_control or not control or base_control.get('type') != 'resource':
                raise PlayerBundleError('该 Player 控件不是可恢复的图片资源')
            service = ProjectAssetService(self._runtime_root)
            asset_id = self._override_assets.pop(control_id, '')
            if asset_id:
                with contextlib.suppress(Exception):
                    service.delete(asset_id, force=True)
            manifest = self._read_override_manifest()
            record = (manifest.get('controls') or {}).pop(control_id, None)
            if isinstance(record, dict):
                path = (self._override_root() / str(record.get('file') or '')).resolve()
                if self._override_root().resolve() in path.parents:
                    path.unlink(missing_ok=True)
            self._write_override_manifest(manifest)
            control['default'] = copy.deepcopy(base_control.get('default'))
            control.pop('override', None)
            return {'ok': True, 'control_id': control_id, 'default': control.get('default')}

    def bootstrap(self) -> dict[str, Any]:
        self._require()
        for profile in self._read_profiles()['profiles'].values():
            self._materialize_profile(dict(profile))
        assets = ProjectAssetService(self._runtime_root).list()
        result = {
            'available': True,
            'bundle': {
                'project_id': self._manifest.get('project_id'),
                'release_id': self._manifest.get('release_id'),
                'name': self._manifest.get('name') or self._project.get('name') or 'EasyCode Player',
                'created_at': self._manifest.get('created_at'),
                'signature': copy.deepcopy(self._signature),
            },
            'form': copy.deepcopy(self._form),
            'targets': copy.deepcopy(self._project.get('targets') or []),
            'default_target_id': self._project.get('default_target_id'),
            'assets': assets,
            'extensions': [
                {
                    'package_id': package_id,
                    'version': record['descriptor'].get('version'),
                    'variants': copy.deepcopy(record['descriptor'].get('variants') or []),
                }
                for package_id, record in sorted(self._extensions.items())
            ],
        }
        if self._update_clients:
            result['updates'] = self.update_status()
        return result

    def mark_update_safe_point(
        self, *, running_or_paused: bool, uncommitted_draft: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            self._require()
            for client in self._update_clients.values():
                client.mark_runtime_state(
                    running_or_paused=running_or_paused,
                    uncommitted_draft=uncommitted_draft,
                )
            return self.update_status() if self._update_clients else {'enabled': False, 'domains': {}}

    def _monitor_update_execution(self, execution_id: str) -> None:
        try:
            while True:
                try:
                    status = str(vnext_runtime.snapshot(execution_id).get('status') or '')
                except RuntimeFailure:
                    status = 'finished'
                if status not in {'queued', 'running', 'paused'}:
                    break
                time.sleep(0.25)
            with self._lock:
                busy = self._runtime_busy()
                for client in self._update_clients.values():
                    client.mark_runtime_state(running_or_paused=busy)
        finally:
            with self._lock:
                self._update_monitors.pop(execution_id, None)

    def asset_content(self, asset_id: str) -> tuple[str, dict[str, Any]]:
        self._require()
        try:
            return ProjectAssetService(self._runtime_root).content_path(asset_id)
        except Exception as exc:
            raise PlayerBundleError(str(exc)) from exc

    def _target(self, target_id: str = '') -> dict[str, Any] | None:
        targets = self._project.get('targets') if isinstance(self._project.get('targets'), list) else []
        chosen = str(target_id or self._project.get('default_target_id') or '')
        if not chosen:
            return None
        target = next((item for item in targets if str(item.get('target_id') or '') == chosen), None)
        if target is None:
            raise PlayerBundleError(f'运行目标不存在：{chosen}')
        return copy.deepcopy(target)

    def _assert_execution_platform(self, target: dict[str, Any] | None) -> str:
        platform = str((target or {}).get('type') or 'no_target')
        supported = {str(item) for item in self._ecir.get('supported_platforms') or []}
        if platform not in supported:
            if platform == 'no_target':
                raise PlayerBundleError('当前程序需要操作目标，无操作目标方案不能运行')
            raise PlayerBundleError(f'当前程序未通过目标平台检查：{platform}')
        return platform

    def _runtime_busy(self) -> bool:
        active = False
        retained: set[str] = set()
        for execution_id in self._execution_ids:
            try:
                status = str(vnext_runtime.snapshot(execution_id).get('status') or '')
            except RuntimeFailure:
                continue
            if status in {'queued', 'running', 'paused'}:
                active = True
                retained.add(execution_id)
        self._execution_ids = retained
        return active

    @staticmethod
    def _host_action_reason(action_id: str, platform: str) -> str:
        if os.name != 'nt':
            return '当前独立 Player 宿主不是已验证的 Windows Capture Host'
        if platform == 'android_local':
            return 'Android 本机字段动作只能在独立 APK Player 中使用'
        if platform not in set(PLAYER_TERMINAL_ACTION_SPECS[action_id]['platforms']):
            return '当前目标平台没有真实终端采集桥'
        return ''

    def _validate_destination(
        self,
        destination: PlayerControlDestination,
        *,
        require_idle: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
        self._require()
        if destination.product_id != str(self._manifest.get('project_id') or ''):
            raise PlayerBundleError('PlayerControlDestination product_id 与当前产品不一致')
        if destination.release_id != str(self._manifest.get('release_id') or ''):
            raise PlayerBundleError('PlayerControlDestination release_id 已过期')
        profile = self._raw_profile(destination.profile_id, destination.profile_revision)
        if profile is None:
            raise PlayerBundleError('终端字段动作必须绑定已保存配置方案')
        if str(profile.get('target_id') or '') != destination.target_id:
            raise PlayerBundleError('PlayerControlDestination target_id 与已保存方案不一致')
        target = self._target(destination.target_id) if destination.target_id else None
        if target is None:
            if destination.action_id not in PLAYER_FILE_ACTIONS:
                raise PlayerBundleError('该终端字段动作必须绑定真实运行目标')
            target = {'target_id': '', 'name': '当前电脑', 'type': 'windows'}
        platform = str(target.get('type') or '')
        control = self._control(self._form, destination.control_id)
        if not control or control.get('type') == 'button':
            raise PlayerBundleError('PlayerControlDestination control_id 未发布或不是字段')
        configured = next((
            item for item in control.get('terminal_actions') or []
            if str(item.get('action_id') or '') == destination.action_id
            and platform in {str(value) for value in item.get('platforms') or []}
        ), None)
        if configured is None:
            raise PlayerBundleError('当前字段未向此平台发布该终端动作')
        closure = next((
            item for item in self._publish_report.get('player_terminal_actions') or []
            if str(item.get('control_id') or '') == destination.control_id
            and str(item.get('action_id') or '') == destination.action_id
            and platform in {str(value) for value in item.get('platforms') or []}
        ), None)
        spec = PLAYER_TERMINAL_ACTION_SPECS.get(destination.action_id)
        if spec is None or closure is None or str(closure.get('capability') or '') != str(spec['capability']):
            raise PlayerBundleError('终端动作不在当前签名发布权限闭包中')
        reason = self._host_action_reason(destination.action_id, platform)
        if reason:
            raise PlayerBundleError(reason)
        if require_idle and self._runtime_busy():
            raise PlayerBundleError('运行、暂停或排队期间不能采集 Player 字段')
        effective_target = self._effective_profile_target(profile, target)
        return profile, control, effective_target, platform

    def _effective_profile_target(
        self,
        profile: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply one saved profile's signed setting slots to its capture target."""

        candidate = self._materialize_profile(copy.deepcopy(profile))
        target_id = str(target.get('target_id') or '')
        runtime_ecir = copy.deepcopy(self._ecir)
        runtime_ecir['targets'] = copy.deepcopy(self._project.get('targets') or [])
        applied = apply_player_values(
            runtime_ecir,
            self._form,
            copy.deepcopy(dict(candidate.get('values') or {})),
            selected_target_id=target_id,
        )
        overrides = copy.deepcopy(dict(applied.get('target_overrides') or {}))
        if not target_id or not overrides.get(target_id):
            return copy.deepcopy(target)
        return merge_target_overrides(
            target,
            overrides,
        ) or copy.deepcopy(target)

    def terminal_action_availability(
        self,
        profile_id: str,
        profile_revision: int | None,
        target_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._require()
            self._expire_stale_control_capture()
            blocked_reason = ''
            profile: dict[str, Any] | None = None
            target: dict[str, Any] | None = None
            if not profile_id or profile_revision is None:
                blocked_reason = '请先保存并选择一个配置方案'
            else:
                try:
                    profile = self._raw_profile(profile_id, profile_revision)
                except PlayerBundleError as exc:
                    blocked_reason = str(exc)
            # Resolve the selected target independently from profile validity.
            # Its platform is still authoritative for deciding which signed
            # field actions belong beside a Control.  A missing/stale profile
            # must disable those actions with a recovery reason, not make them
            # disappear from the form.
            if target_id:
                try:
                    target = self._target(target_id)
                except PlayerBundleError as exc:
                    blocked_reason = str(exc)
            if profile is not None:
                if str(profile.get('target_id') or '') != str(target_id or ''):
                    blocked_reason = '请先把当前目标保存到配置方案'
            if self._runtime_busy():
                blocked_reason = '运行、暂停或排队期间不能采集 Player 字段'
            if self._active_capture is not None:
                blocked_reason = '已有一个终端字段采集会话正在进行'
            # File and directory selection is a Windows host action even when
            # this profile intentionally runs without an operation target.
            platform = str((target or {}).get('type') or ('windows' if not target_id else ''))
            signed = {
                (str(item.get('control_id') or ''), str(item.get('action_id') or '')): item
                for item in self._publish_report.get('player_terminal_actions') or []
                if platform in {str(value) for value in item.get('platforms') or []}
            }
            actions: list[dict[str, Any]] = []
            if platform:
                for page in self._form.get('pages') or []:
                    for control in page.get('controls') or []:
                        control_id = str(control.get('control_id') or '')
                        for permission in control.get('terminal_actions') or []:
                            action_id = str(permission.get('action_id') or '')
                            if not target_id and action_id not in PLAYER_FILE_ACTIONS:
                                continue
                            if platform not in {str(item) for item in permission.get('platforms') or []}:
                                continue
                            if (control_id, action_id) not in signed:
                                continue
                            reason = blocked_reason or self._host_action_reason(action_id, platform)
                            actions.append({
                                'control_id': control_id,
                                'action_id': action_id,
                                'platform': platform,
                                'capability': PLAYER_TERMINAL_ACTION_SPECS[action_id]['capability'],
                                'enabled': not reason,
                                'disabled_reason': reason,
                                'destination': {
                                    'product_id': str(self._manifest.get('project_id') or ''),
                                    'release_id': str(self._manifest.get('release_id') or ''),
                                    'profile_id': str(profile_id or ''),
                                    'control_id': control_id,
                                    'action_id': action_id,
                                    'profile_revision': int(profile_revision or 0),
                                    'target_id': str(target_id or ''),
                                },
                            })
            return {
                'platform': platform or None,
                'profile_id': profile_id or None,
                'profile_revision': profile_revision,
                'blocked_reason': blocked_reason,
                'actions': actions,
            }

    def start_control_capture(
        self,
        destination_value: dict[str, Any],
        *,
        origin: str = '',
    ) -> dict[str, Any]:
        with self._lock:
            self._expire_stale_control_capture()
            if self._active_capture is not None:
                raise PlayerBundleError('一个 Player 进程只允许一个活动字段采集会话')
            destination = PlayerControlDestination.from_mapping(destination_value)
            _profile, control, target, platform = self._validate_destination(destination)
            capture_id = f'player_capture_{uuid.uuid4().hex}'
            session_id = f'player_session_{uuid.uuid4().hex}'
            state = {
                'capture_id': capture_id,
                'session_id': session_id,
                'destination': destination.as_dict(),
                'started_at': time.time(),
            }
            self._active_capture = state
        try:
            action_id = destination.action_id
            if action_id in PLAYER_FILE_ACTIONS:
                from core.services.player_native_dialogs import (
                    PlayerNativeDialogError,
                    player_native_dialog_service,
                )

                try:
                    candidate = player_native_dialog_service.choose(
                        action_id,
                        label=str(control.get('label') or '选择内容'),
                        value_type=str(control.get('source_type') or ''),
                        constraints=dict(control.get('constraints') or {}),
                    )
                except PlayerNativeDialogError as exc:
                    raise PlayerBundleError(str(exc)) from exc
                if candidate is None:
                    with self._lock:
                        if self._active_capture and self._active_capture.get('capture_id') == capture_id:
                            self._active_capture = None
                    return {
                        'ok': True, 'cancelled': True, 'capture_id': capture_id,
                        'state': 'cancelled', 'destination': destination.as_dict(),
                    }
                candidate_id = f'player_candidate_{uuid.uuid4().hex}'
                with self._lock:
                    if self._active_capture and self._active_capture.get('capture_id') == capture_id:
                        self._active_capture['candidate_id'] = candidate_id
                        self._active_capture['candidate'] = copy.deepcopy(candidate)
                return {
                    'ok': True, 'capture_id': capture_id, 'state': 'awaiting_confirmation',
                    'destination': destination.as_dict(),
                    'candidate': {
                        'candidate_id': candidate_id,
                        'kind': candidate['kind'],
                        'display_name': candidate['display_name'],
                        'access': copy.deepcopy(candidate['access']),
                    },
                }
            if action_id == 'choose-resource':
                return {
                    'ok': True, 'capture_id': capture_id,
                    'state': 'awaiting_file', 'destination': destination.as_dict(),
                }
            from core.services.player_capture_session import player_capture_session_service

            player_capture_session_service.register_ui_session({
                'session_id': session_id,
                'project_path': self._runtime_root,
                'workspace_kind': 'player',
                'workspace_id': f'player:{destination.product_id}:{destination.release_id}',
                'workspace_generation': destination.profile_revision,
                'project_id': destination.product_id,
                'project_name': str(self._manifest.get('name') or 'EasyCode Player'),
                'target_name': str(target.get('name') or destination.target_id),
                'capture_context': {
                    'player_destination': destination.as_dict(),
                    'capture_id': capture_id,
                    'control_type': control.get('type'),
                    'target_id': destination.target_id,
                },
                'execution_state': 'idle',
                'recording_active': False,
                'origin': str(origin or ''),
            })
            modes = {
                'pick-point': 'point',
                'pick-region': 'region',
                'pick-color': 'color',
                # Image capture deliberately uses the typed region result. The
                # Player commits the crop privately instead of opening the IDE
                # resource browser used by the legacy ``asset`` mode.
                'capture-image': 'region',
                'capture-path': 'path',
                'capture-control': 'control',
                'capture-window': 'point',
            }
            launched = player_capture_session_service.trigger_global_capture({
                'session_id': session_id,
                'field_capture': {
                    'request_id': capture_id,
                    'selection_mode': modes[action_id],
                    'category': 'image',
                    'max_rects': 1,
                    'title': str(control.get('label') or '采集字段'),
                },
            })
            with self._lock:
                if self._active_capture and self._active_capture.get('capture_id') == capture_id:
                    self._active_capture['snapshot_id'] = str(launched.get('snapshot_id') or '')
                    self._active_capture['reference_size'] = copy.deepcopy(launched.get('reference_size') or [])
            return {
                'ok': True, 'capture_id': capture_id,
                'state': 'capturing', 'destination': destination.as_dict(),
                'host': str(launched.get('backend') or 'native-capture'),
                'snapshot_id': launched.get('snapshot_id'),
            }
        except Exception:
            with self._lock:
                if self._active_capture and self._active_capture.get('capture_id') == capture_id:
                    self._active_capture = None
            with contextlib.suppress(Exception):
                from core.services.player_capture_session import player_capture_session_service
                player_capture_session_service.unregister_ui_session(session_id)
            raise

    def resolve_control_capture_candidates(
        self,
        capture_id: str,
        point: Any,
        reference_size: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise PlayerBundleError('控件捕获点无效')
        if not isinstance(reference_size, (list, tuple)) or len(reference_size) != 2:
            raise PlayerBundleError('控件捕获坐标空间无效')
        with self._lock:
            state = copy.deepcopy(self._active_capture or {})
            if not state or str(state.get('capture_id') or '') != str(capture_id or ''):
                raise PlayerBundleError('Player 控件捕获会话不存在或已结束')
            destination = PlayerControlDestination.from_mapping(state.get('destination') or {})
            _profile, _control, target, platform = self._validate_destination(destination)
        if platform == 'android_adb' and state.get('semantic_snapshot'):
            from .android_control_v6 import control_candidates_at
            return control_candidates_at(
                state['semantic_snapshot'], int(point[0]), int(point[1]),
                destination.target_id, 'android_uiautomator', source_size=reference_size,
            )
        from .control_capture_v6 import ControlCaptureError, resolve_control_candidates
        try:
            return resolve_control_candidates(
                self._runtime_root, target,
                (int(point[0]), int(point[1])),
                (int(reference_size[0]), int(reference_size[1])),
            )
        except ControlCaptureError as exc:
            raise PlayerBundleError(str(exc)) from exc

    def validate_player_capture_session(self, session: dict[str, Any]) -> str:
        with self._lock:
            if str(session.get('workspace_kind') or '') != 'player':
                raise PlayerBundleError('不是 Player Capture 会话')
            active = self._active_capture
            context = session.get('capture_context') or {}
            if not active or str(context.get('capture_id') or '') != str(active.get('capture_id') or ''):
                raise PlayerBundleError('Player Capture 会话已失效')
            destination = PlayerControlDestination.from_mapping(
                dict(context.get('player_destination') or {})
            )
            if destination.as_dict() != active.get('destination'):
                raise PlayerBundleError('Player Capture 目标在启动后发生变化')
            self._validate_destination(destination)
            expected_workspace = f'player:{destination.product_id}:{destination.release_id}'
            if str(session.get('workspace_id') or '') != expected_workspace:
                raise PlayerBundleError('Player Capture 宿主身份不一致')
            if int(session.get('workspace_generation') or 0) != destination.profile_revision:
                raise PlayerBundleError('Player Capture profile revision 已过期')
            bound = os.path.realpath(self._runtime_root)
            if os.path.normcase(os.path.realpath(str(session.get('project_path') or ''))) != os.path.normcase(bound):
                raise PlayerBundleError('Player Capture 运行目录不一致')
            return bound

    def player_capture_target(self, session: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        with self._lock:
            bound = self.validate_player_capture_session(session)
            destination = PlayerControlDestination.from_mapping(
                dict((session.get('capture_context') or {}).get('player_destination') or {})
            )
            _profile, _control, target, _platform = self._validate_destination(destination)
            if destination.action_id == 'capture-window':
                return bound, {
                    'target_id': destination.target_id,
                    'name': '选择目标窗口',
                    'type': 'windows',
                    'window_title': '',
                    'window_match': 'contains',
                    'work_area': {'mode': 'desktop'},
                    'allow_physical_fallback': True,
                }
            return bound, target

    def _validate_profile_candidate(
        self,
        profile: dict[str, Any],
        control_id: str,
        value: Any,
    ) -> None:
        candidate = self._materialize_profile(profile)
        values = copy.deepcopy(dict(candidate.get('values') or {}))
        values[control_id] = copy.deepcopy(value)
        target_id = str(candidate.get('target_id') or '')
        runtime_ecir = copy.deepcopy(self._ecir)
        runtime_ecir['targets'] = copy.deepcopy(self._project.get('targets') or [])
        validate_player_target_scope(
            self._form, values, target_id, error=PlayerBundleError,
        )
        apply_player_values(
            runtime_ecir,
            self._form,
            values,
            selected_target_id=target_id,
        )

    def _commit_profile_value(
        self,
        destination: PlayerControlDestination,
        value: Any,
    ) -> dict[str, Any]:
        document = self._read_profiles()
        profile = document['profiles'].get(destination.profile_id)
        if not isinstance(profile, dict) or int(profile.get('revision') or 0) != destination.profile_revision:
            raise PlayerBundleError('确认时配置方案 revision 已过期')
        self._validate_profile_candidate(profile, destination.control_id, value)
        updated = copy.deepcopy(profile)
        updated.setdefault('values', {})[destination.control_id] = copy.deepcopy(value)
        updated['revision'] = destination.profile_revision + 1
        updated['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        document['profiles'][destination.profile_id] = updated
        self._write_json_atomic(self._profiles_path(), document)
        return self._materialize_profile(updated)

    @staticmethod
    def _canonical_image(content: bytes) -> bytes:
        if not content or len(content) > 32 * 1024 * 1024:
            raise PlayerBundleError('终端图片为空或超过 32MB 限制')
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                converted = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                buffer = io.BytesIO()
                converted.save(buffer, format='PNG', optimize=False)
                return buffer.getvalue()
        except Exception as exc:
            raise PlayerBundleError(f'终端图片无法解码：{exc}') from exc

    def _commit_profile_image(
        self,
        destination: PlayerControlDestination,
        content: bytes,
        file_name: str,
    ) -> dict[str, Any]:
        png = self._canonical_image(content)
        document = self._read_profiles()
        profile = document['profiles'].get(destination.profile_id)
        if not isinstance(profile, dict) or int(profile.get('revision') or 0) != destination.profile_revision:
            raise PlayerBundleError('确认图片时配置方案 revision 已过期')
        digest = hashlib.sha256(png).hexdigest()
        root = (self._data_root() / 'profiles' / destination.profile_id / 'images').resolve()
        root.mkdir(parents=True, exist_ok=True)
        destination_path = (root / f'{digest}.png').resolve()
        if root not in destination_path.parents:
            raise PlayerBundleError('配置方案私有图片路径无效')
        created_file = not destination_path.exists()
        if created_file:
            temporary = destination_path.with_name(f'.{destination_path.name}.{uuid.uuid4().hex}.tmp')
            try:
                temporary.write_bytes(png)
                os.replace(temporary, destination_path)
            finally:
                temporary.unlink(missing_ok=True)
        imported_asset_id = ''
        try:
            imported = ProjectAssetService(self._runtime_root).import_base64(
                category='image',
                folder=f'_player_profiles/{destination.profile_id}',
                file_name=str(file_name or destination_path.name),
                display_name=f'{profile.get("name") or destination.profile_id} · {destination.control_id}',
                content_base64=base64.b64encode(png).decode('ascii'),
                source='player_profile_override',
                capture=None,
            )
            imported_asset_id = str((imported.get('asset') or {}).get('asset_id') or '')
            if not imported_asset_id:
                raise PlayerBundleError('终端图片无法进入 Player 私有资源覆盖')
            value = {'asset_id': imported_asset_id, 'asset_kind': 'image'}
            candidate = copy.deepcopy(profile)
            candidate.setdefault('image_overrides', {})[destination.control_id] = {
                'file': destination_path.name,
                'file_name': str(file_name or destination_path.name),
                'sha256': digest,
            }
            candidate.setdefault('values', {}).pop(destination.control_id, None)
            # Prevent materialisation of the old record while validating the
            # candidate; the new runtime asset is already strongly typed.
            candidate_without_new = copy.deepcopy(candidate)
            candidate_without_new.setdefault('image_overrides', {}).pop(destination.control_id, None)
            self._validate_profile_candidate(candidate_without_new, destination.control_id, value)
            candidate['revision'] = destination.profile_revision + 1
            candidate['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            old_record = copy.deepcopy((profile.get('image_overrides') or {}).get(destination.control_id))
            old_asset_id = self._profile_override_assets.get(
                (destination.profile_id, destination.control_id), ''
            )
            document['profiles'][destination.profile_id] = candidate
            self._write_json_atomic(self._profiles_path(), document)
            self._profile_override_assets[(destination.profile_id, destination.control_id)] = imported_asset_id
            if old_asset_id and old_asset_id != imported_asset_id:
                with contextlib.suppress(Exception):
                    ProjectAssetService(self._runtime_root).delete(old_asset_id, force=True)
            if isinstance(old_record, dict) and str(old_record.get('file') or '') != destination_path.name:
                with contextlib.suppress(Exception):
                    self._profile_override_path(destination.profile_id, old_record).unlink(missing_ok=True)
            return self._materialize_profile(candidate)
        except Exception:
            if imported_asset_id:
                with contextlib.suppress(Exception):
                    ProjectAssetService(self._runtime_root).delete(imported_asset_id, force=True)
            if created_file:
                destination_path.unlink(missing_ok=True)
            raise

    def _release_control_capture(self, state: dict[str, Any]) -> None:
        destination = state.get('destination') or {}
        if str(destination.get('action_id') or '') == 'capture-control':
            with contextlib.suppress(Exception):
                from core.services import capture_mode
                capture_mode.stop_mode()
        with contextlib.suppress(Exception):
            from core.services.player_capture_session import player_capture_session_service
            player_capture_session_service.close_capture(str(state.get('snapshot_id') or ''))
            player_capture_session_service.unregister_ui_session(str(state.get('session_id') or ''))

    def _expire_stale_control_capture(self, *, now: float | None = None) -> bool:
        """Release an abandoned field capture without touching profile values.

        Browser tabs can be closed after a native host returns a candidate, and
        Android/Windows capture hosts can be interrupted independently of the
        Player UI. A process-local session must therefore fail closed and age
        out instead of permanently disabling every capture button.
        """

        state = copy.deepcopy(self._active_capture or {})
        if not state:
            return False
        started_at = state.get('started_at')
        if isinstance(started_at, bool) or not isinstance(started_at, (int, float)):
            return False
        if float(now if now is not None else time.time()) - float(started_at) <= self.CONTROL_CAPTURE_TTL_SECONDS:
            return False
        self._active_capture = None
        self._release_control_capture(state)
        return True

    def confirm_control_capture(
        self,
        capture_id: str,
        destination_value: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        state: dict[str, Any]
        with self._lock:
            destination = PlayerControlDestination.from_mapping(destination_value)
            state = copy.deepcopy(self._active_capture or {})
            if not state or str(state.get('capture_id') or '') != str(capture_id or ''):
                raise PlayerBundleError('Player 字段采集会话不存在或已结束')
            if state.get('destination') != destination.as_dict():
                raise PlayerBundleError('确认目标与启动时的 PlayerControlDestination 不一致')
            try:
                # Second authority check: release, profile revision, target,
                # field, platform, signed permission, host and runtime state
                # may all have changed while the native host was open.
                _profile, _control, target, platform = self._validate_destination(destination)
                action_id = destination.action_id
                kind = str(result.get('kind') or '')
                if action_id in PLAYER_FILE_ACTIONS:
                    if kind != 'native-reference':
                        raise PlayerBundleError('系统选择结果类型无效')
                    candidate = state.get('candidate')
                    if (
                        not isinstance(candidate, dict)
                        or str(result.get('candidate_id') or '') != str(state.get('candidate_id') or '')
                        or not isinstance(candidate.get('reference'), dict)
                    ):
                        raise PlayerBundleError('系统选择候选已失效，请重新选择')
                    profile = self._commit_profile_value(
                        destination, copy.deepcopy(candidate['reference']),
                    )
                elif action_id == 'choose-resource':
                    if kind != 'file':
                        raise PlayerBundleError('图片选择确认结果类型无效')
                    try:
                        content = base64.b64decode(str(result.get('content_base64') or ''), validate=True)
                    except Exception as exc:
                        raise PlayerBundleError('图片选择结果内容无效') from exc
                    profile = self._commit_profile_image(
                        destination, content, str(result.get('file_name') or 'image.png'),
                    )
                elif action_id == 'capture-control':
                    if kind != 'field_confirm' or not isinstance(result.get('selector'), dict):
                        raise PlayerBundleError('控件捕获结果无效')
                    snapshot_id = str(result.get('snapshot_id') or '')
                    if snapshot_id != str(state.get('snapshot_id') or ''):
                        raise PlayerBundleError('确认结果属于另一张冻结帧')
                    selector = copy.deepcopy(result['selector'])
                    provider = str(selector.get('control_selector.field.provider') or '')
                    expected_provider = 'windows_uia' if platform == 'windows' else 'android_uiautomator'
                    if provider != expected_provider:
                        raise PlayerBundleError('控件选择器不属于当前平台适配器')
                    if str(selector.get('control_selector.field.target_id') or '') != destination.target_id:
                        raise PlayerBundleError('控件选择器不属于当前 Player 目标')
                    profile = self._commit_profile_value(destination, selector)
                elif action_id == 'capture-window':
                    if kind != 'field_confirm':
                        raise PlayerBundleError('窗口捕获结果无效')
                    snapshot_id = str(result.get('snapshot_id') or '')
                    if snapshot_id != str(state.get('snapshot_id') or ''):
                        raise PlayerBundleError('确认结果属于另一张冻结帧')
                    point = result.get('point')
                    reference_size = result.get('reference_size')
                    from core.services.player_capture_session import player_capture_session_service

                    binding = player_capture_session_service.resolve_window_capture(
                        snapshot_id,
                        str(state.get('session_id') or ''),
                        point,
                        reference_size,
                    )
                    profile = self._commit_profile_value(destination, binding)
                else:
                    if kind != 'field_confirm':
                        raise PlayerBundleError('原生 Capture Host 确认结果类型无效')
                    snapshot_id = str(result.get('snapshot_id') or '')
                    if snapshot_id != str(state.get('snapshot_id') or ''):
                        raise PlayerBundleError('确认结果属于另一张冻结帧')
                    from core.services.player_capture_session import player_capture_session_service

                    if action_id == 'pick-point':
                        point = result.get('point')
                        if not isinstance(point, (list, tuple)) or len(point) != 2:
                            raise PlayerBundleError('点捕获结果无效')
                        player_capture_session_service.validate_player_snapshot(
                            snapshot_id, str(state.get('session_id') or ''),
                        )
                        profile = self._commit_profile_value(
                            destination, {'x': int(point[0]), 'y': int(point[1])},
                        )
                    elif action_id == 'pick-color':
                        raw_color = result.get('color')
                        channels = ('red', 'green', 'blue', 'alpha')
                        if not isinstance(raw_color, dict) or any(
                            isinstance(raw_color.get(channel), bool)
                            or not isinstance(raw_color.get(channel), int)
                            or not 0 <= raw_color[channel] <= 255
                            for channel in channels
                        ):
                            raise PlayerBundleError('颜色捕获结果无效')
                        player_capture_session_service.validate_player_snapshot(
                            snapshot_id, str(state.get('session_id') or ''),
                        )
                        profile = self._commit_profile_value(destination, {
                            f'color.field.{channel}': int(raw_color[channel])
                            for channel in channels
                        })
                    elif action_id in {'pick-region', 'capture-image'}:
                        rects = result.get('rects')
                        if not isinstance(rects, list) or len(rects) != 1:
                            raise PlayerBundleError('区域捕获结果必须且只能包含一个矩形')
                        rect = rects[0]
                        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                            raise PlayerBundleError('区域捕获结果无效')
                        clean_rect = [int(item) for item in rect]
                        if action_id == 'pick-region':
                            player_capture_session_service.validate_player_snapshot(
                                snapshot_id, str(state.get('session_id') or ''), clean_rect,
                            )
                            profile = self._commit_profile_value(destination, {
                                'x': clean_rect[0], 'y': clean_rect[1],
                                'width': clean_rect[2], 'height': clean_rect[3],
                            })
                        else:
                            content = player_capture_session_service.player_snapshot_crop(
                                snapshot_id, str(state.get('session_id') or ''), clean_rect,
                            )
                            profile = self._commit_profile_image(
                                destination, content, f'{destination.control_id}.png',
                            )
                    elif action_id == 'capture-path':
                        raw_path = result.get('path')
                        if not isinstance(raw_path, list) or not raw_path or len(raw_path) > 100_000:
                            raise PlayerBundleError('手势路径捕获结果无效')
                        points = [
                            {'x': int(item[0]), 'y': int(item[1])}
                            for item in raw_path
                            if isinstance(item, (list, tuple)) and len(item) == 2
                        ]
                        if len(points) != len(raw_path):
                            raise PlayerBundleError('手势路径包含无效坐标')
                        player_capture_session_service.validate_player_snapshot(
                            snapshot_id, str(state.get('session_id') or ''),
                        )
                        profile = self._commit_profile_value(destination, points)
                    else:
                        raise PlayerBundleError('终端字段动作没有确认适配器')
                return {
                    'ok': True,
                    'capture_id': capture_id,
                    'profile': profile,
                    'value': copy.deepcopy((profile.get('values') or {}).get(destination.control_id)),
                }
            finally:
                self._active_capture = None
                self._release_control_capture(state)

    def cancel_control_capture(
        self,
        capture_id: str,
        destination_value: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            destination = PlayerControlDestination.from_mapping(destination_value)
            state = copy.deepcopy(self._active_capture or {})
            if not state or str(state.get('capture_id') or '') != str(capture_id or ''):
                raise PlayerBundleError('Player 字段采集会话不存在或已结束')
            if state.get('destination') != destination.as_dict():
                raise PlayerBundleError('取消目标与启动时的 PlayerControlDestination 不一致')
            # Cancellation never writes profile state, even if the stored
            # revision has moved while the host was open.
            self._active_capture = None
            self._release_control_capture(state)
            return {'ok': True, 'cancelled': True, 'capture_id': capture_id}

    def restore_profile_image(
        self,
        destination_value: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            destination = PlayerControlDestination.from_mapping(destination_value)
            profile, control, _target, _platform = self._validate_destination(destination)
            if control.get('type') != 'resource' or destination.action_id not in {'choose-resource', 'capture-image'}:
                raise PlayerBundleError('该 Player 字段没有可恢复的图片覆盖')
            document = self._read_profiles()
            raw = document['profiles'].get(destination.profile_id)
            record = (raw.get('image_overrides') or {}).pop(destination.control_id, None) if isinstance(raw, dict) else None
            if not isinstance(record, dict):
                raise PlayerBundleError('当前配置方案没有该字段的私有图片覆盖')
            raw.setdefault('values', {}).pop(destination.control_id, None)
            raw['revision'] = destination.profile_revision + 1
            raw['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            document['profiles'][destination.profile_id] = raw
            self._write_json_atomic(self._profiles_path(), document)
            old_asset_id = self._profile_override_assets.pop(
                (destination.profile_id, destination.control_id), ''
            )
            if old_asset_id:
                with contextlib.suppress(Exception):
                    ProjectAssetService(self._runtime_root).delete(old_asset_id, force=True)
            with contextlib.suppress(Exception):
                self._profile_override_path(destination.profile_id, record).unlink(missing_ok=True)
            materialized = self._materialize_profile(raw)
            default = copy.deepcopy(control.get('default')) if 'default' in control else None
            return {
                'ok': True, 'profile': materialized,
                'value': copy.deepcopy((materialized.get('values') or {}).get(destination.control_id, default)),
            }

    @staticmethod
    def _instruction_records(ecir: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Collect reachable instructions without trusting a browser-supplied list."""

        functions = {
            str(item.get('function_id') or ''): item
            for item in (ecir.get('functions') or [])
            if isinstance(item, dict) and str(item.get('function_id') or '')
        }
        records: dict[str, dict[str, Any]] = {}
        visited_functions: set[str] = set()

        def visit_value(value: Any, owner_function_id: str) -> None:
            if isinstance(value, dict):
                instruction_id = str(value.get('instruction_id') or '')
                opcode = str(value.get('opcode') or '')
                if instruction_id and opcode:
                    if instruction_id in records:
                        raise PlayerBundleError(
                            f'Player 运行产物包含重复语句 ID：{instruction_id}'
                        )
                    records[instruction_id] = {
                        'owner_function_id': owner_function_id,
                        'instruction': value,
                    }
                    callee = str(value.get('callee_function_id') or '')
                    if not callee and opcode == 'control.listen':
                        callee = str(
                            (value.get('arguments') or {}).get('handler_function_id') or ''
                        )
                    if callee and opcode != 'call.extension':
                        visit_function(callee)
                for child in value.values():
                    visit_value(child, owner_function_id)
            elif isinstance(value, list):
                for child in value:
                    visit_value(child, owner_function_id)

        def visit_function(function_id: str) -> None:
            if not function_id or function_id in visited_functions:
                return
            definition = functions.get(function_id)
            if definition is None:
                raise PlayerBundleError(f'Player 运行闭包缺少项目函数：{function_id}')
            visited_functions.add(function_id)
            visit_value(definition.get('instructions') or [], function_id)

        visit_function(str(ecir.get('entry_function_id') or ''))
        return records

    @staticmethod
    def _resolve_delete_tree_reference(
        ecir: dict[str, Any], instruction: dict[str, Any],
    ) -> dict[str, Any] | None:
        value = (instruction.get('arguments') or {}).get(
            'official.directory.delete_tree.parameter.directory'
        )
        if isinstance(value, dict) and value.get('kind') == 'directory_ref':
            return value
        if not isinstance(value, dict) or value.get('kind') != 'reference':
            return None
        if value.get('scope') != 'project':
            return None
        variable_id = str(value.get('variable_id') or '')
        candidate = (ecir.get('project_variable_overrides') or {}).get(variable_id)
        if candidate is None:
            definition = next((
                item for item in (ecir.get('project_variables') or [])
                if str(item.get('variable_id') or '') == variable_id
            ), None)
            candidate = (definition or {}).get('default_value')
        return (
            candidate
            if isinstance(candidate, dict) and candidate.get('kind') == 'directory_ref'
            else None
        )

    def _dangerous_operation_requirements(
        self, ecir: dict[str, Any],
    ) -> list[dict[str, Any]]:
        contract = official_function_registry_v6.require(
            'official.directory.delete_tree'
        )
        contract_fingerprint = contract.fingerprint()
        execution_config_revision = content_revision(canonical_json_bytes({
            'entry_function_id': ecir.get('entry_function_id'),
            'function_arguments': ecir.get('function_arguments') or {},
            'project_variable_overrides': ecir.get('project_variable_overrides') or {},
            'target_overrides': ecir.get('target_overrides') or {},
            'runtime_data_directory': ecir.get('runtime_data_directory') or '',
        }))
        result: list[dict[str, Any]] = []
        for statement_id, record in sorted(self._instruction_records(ecir).items()):
            instruction = record['instruction']
            if str(instruction.get('opcode') or '') != 'directory.delete_tree':
                continue
            review = instruction.get('dangerous_author_review') or {}
            if (
                not str(review.get('fingerprint') or '')
                or str(review.get('contract_fingerprint') or '') != contract_fingerprint
            ):
                raise PlayerBundleError(
                    f'递归删除语句 {statement_id} 缺少与当前契约绑定的作者审核'
                )
            reference = self._resolve_delete_tree_reference(ecir, instruction)
            if reference is None:
                raise PlayerBundleError(
                    f'递归删除语句 {statement_id} 的目录在运行前无法确定；'
                    '请直接绑定已授权目录或 Player 目录字段'
                )
            authorization_root_id = str(
                reference.get('authorization_root_id') or ''
            ).strip()
            if not authorization_root_id:
                raise PlayerBundleError(
                    f'递归删除语句 {statement_id} 的目录缺少授权根身份'
                )
            display_path = str(
                reference.get('path')
                or reference.get('display_name')
                or '已授权目录'
            )
            confirmation_id = content_revision(canonical_json_bytes({
                'statement_id': statement_id,
                'authorization_root_id': authorization_root_id,
                'execution_config_revision': execution_config_revision,
                'contract_fingerprint': contract_fingerprint,
            }))
            result.append({
                'confirmation_id': confirmation_id,
                'statement_id': statement_id,
                'function_id': 'official.directory.delete_tree',
                'display_name': '递归删除目录',
                'display_path': display_path,
                'authorization_root_id': authorization_root_id,
                'execution_config_revision': execution_config_revision,
                'contract_fingerprint': contract_fingerprint,
            })
        return result

    @staticmethod
    def _validated_dangerous_confirmations(
        requirements: list[dict[str, Any]], supplied: Any,
    ) -> list[dict[str, Any]]:
        values = supplied if isinstance(supplied, list) else []
        by_id: dict[str, dict[str, Any]] = {}
        for item in values:
            if not isinstance(item, dict):
                raise PlayerBundleError('危险操作确认格式无效')
            confirmation_id = str(item.get('confirmation_id') or '')
            if not confirmation_id or confirmation_id in by_id:
                raise PlayerBundleError('危险操作确认包含空或重复身份')
            by_id[confirmation_id] = item
        expected_ids = {str(item['confirmation_id']) for item in requirements}
        if set(by_id) - expected_ids:
            raise PlayerBundleError('危险操作确认不属于当前运行配置')
        if expected_ids - set(by_id):
            raise PlayerBundleError('运行包含递归删除目录，请先在 Player 中明确确认')
        confirmations: list[dict[str, Any]] = []
        for requirement in requirements:
            supplied_item = by_id[str(requirement['confirmation_id'])]
            if supplied_item.get('confirmed') is not True:
                raise PlayerBundleError('递归删除目录未获得明确确认')
            confirmations.append({
                'confirmed': True,
                'statement_id': requirement['statement_id'],
                'authorization_root_id': requirement['authorization_root_id'],
                'execution_config_revision': requirement['execution_config_revision'],
                'contract_fingerprint': requirement['contract_fingerprint'],
            })
        return confirmations

    def _prepare_execution(
        self, payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
        profile_id = str(payload.get('profile_id') or '').strip()
        raw_revision = payload.get('profile_revision')
        if raw_revision is not None and (
            isinstance(raw_revision, bool) or not isinstance(raw_revision, int) or raw_revision < 1
        ):
            raise PlayerBundleError('配置方案 revision 无效')
        if raw_revision is not None and not profile_id:
            raise PlayerBundleError('未选择已保存配置方案时不能提供 profile_revision')
        profile = self._profile(profile_id, expected_revision=raw_revision)
        if profile is not None and raw_revision is None:
            raise PlayerBundleError('运行已保存方案必须提供 profile_revision')
        selected_target_id = str(
            payload.get('target_id') or (profile or {}).get('target_id') or ''
        )
        target = self._target(selected_target_id)
        execution_platform = self._assert_execution_platform(target)
        player_values = copy.deepcopy(dict((profile or {}).get('values') or {}))
        player_values.update(copy.deepcopy(dict(payload.get('player_values') or {})))
        validate_player_target_scope(
            self._form,
            player_values,
            str((target or {}).get('target_id') or ''),
            error=PlayerBundleError,
        )
        runtime_ecir = copy.deepcopy(self._ecir)
        runtime_ecir['targets'] = copy.deepcopy(self._project.get('targets') or [])
        runtime_ecir['target_platform'] = execution_platform
        runtime_ecir['default_target_id'] = str((target or {}).get('target_id') or '') or None
        runtime_ecir['runtime_data_directory'] = str(
            self._data_root() / 'project-data'
        )
        ecir = apply_player_values(
            runtime_ecir,
            self._form,
            player_values,
            str(payload.get('action_control_id') or ''),
            selected_target_id=str((target or {}).get('target_id') or ''),
        )
        return target, ecir, selected_target_id

    def dangerous_operation_requirements(
        self, payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require()
        _target, ecir, _target_id = self._prepare_execution(payload)
        return {'operations': self._dangerous_operation_requirements(ecir)}

    def _player_recording_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._recording_feature_enabled():
            return {
                'enabled': False,
                'status': 'disabled',
                'reason': 'feature_not_published',
            }
        profile_id = str(payload.get('profile_id') or '').strip()
        revision = payload.get('profile_revision')
        if not profile_id or not isinstance(revision, int):
            return {
                'enabled': False,
                'status': 'disabled',
                'reason': 'recording_requires_saved_profile',
            }
        profile = self._raw_profile(profile_id, revision)
        settings = copy.deepcopy((profile or {}).get('recording') or {})
        if not settings.get('enabled'):
            return {**settings, 'enabled': False, 'status': 'disabled', 'reason': 'profile_disabled'}
        if int(settings.get('confirmed_profile_revision') or 0) != revision:
            return {
                **settings,
                'enabled': False,
                'requested_enabled': True,
                'status': 'confirmation_required',
                'reason': 'profile_revision_not_confirmed',
            }
        profile_target_id = str((profile or {}).get('target_id') or '')
        requested_target_id = str(payload.get('target_id') or profile_target_id)
        if requested_target_id != profile_target_id:
            return {
                **settings,
                'enabled': False,
                'requested_enabled': True,
                'status': 'confirmation_required',
                'reason': 'target_override_not_confirmed',
            }
        return {**settings, 'enabled': True, 'status': 'confirmed', 'profile_revision': revision}

    def _monitor_player_recording(self, execution_id: str, project_path: str) -> None:
        cursor = 0
        try:
            while True:
                snapshot = vnext_runtime.wait_snapshot(execution_id, cursor, 2.0)
                cursor = max(
                    cursor,
                    int(snapshot.get('event_cursor') or 0),
                    max((int(item.get('sequence') or 0) for item in snapshot.get('events') or []), default=0),
                )
                status = str(snapshot.get('status') or '')
                if status not in {'completed', 'failed', 'cancelled'}:
                    continue
                if status == 'failed':
                    with contextlib.suppress(Exception):
                        self._recording.mark(project_path, '任务失败')
                self._recording.stop(
                    project_path,
                    'user_cancelled' if status == 'cancelled' else 'completed',
                )
                return
        except Exception:
            # Recording lifecycle is diagnostic infrastructure. Runtime
            # success/failure remains authoritative and must not be replaced
            # by a monitor-thread error.
            with contextlib.suppress(Exception):
                self._recording.stop(project_path, 'driver_failed')
        finally:
            with self._lock:
                self._recording_monitors.pop(execution_id, None)

    def recording_status(self) -> dict[str, Any]:
        self._require()
        if not self._recording_feature_enabled():
            return {'active': False, 'status': 'disabled', 'reason': 'feature_not_published'}
        return self._recording.status(self._runtime_root)

    def stop_recording(self) -> dict[str, Any]:
        self._require()
        self._require_recording_feature()
        return self._recording.stop(self._runtime_root, 'user_stopped')

    def recording_sessions(self) -> dict[str, Any]:
        self._require()
        if not self._recording_feature_enabled():
            return {'sessions': []}
        return {'sessions': RecordingStorageV6.list_sessions(self._runtime_root)}

    def recording_session(self, session_id: str) -> dict[str, Any]:
        self._require()
        self._require_recording_feature()
        detail = RecordingStorageV6.session_detail(self._runtime_root, session_id)
        frames = RecordingStorageV6.list_frames(self._runtime_root, session_id, limit=500)
        return {**detail, 'frames': frames['frames'], 'frame_total': frames['total']}

    def recording_frame_data(self, session_id: str, sequence: int) -> dict[str, Any]:
        self._require()
        self._require_recording_feature()
        frame = RecordingStorageV6.resolve_frame(self._runtime_root, session_id, sequence)
        RecordingStorageV6.require_frame_integrity(frame)
        return {
            'frame': {key: value for key, value in frame.record.items() if not key.startswith('_')},
            'mime_type': 'image/png',
            'data_base64': base64.b64encode(frame.path.read_bytes()).decode('ascii'),
        }

    def delete_recording_session(self, session_id: str) -> dict[str, Any]:
        self._require()
        self._require_recording_feature()
        return RecordingStorageV6.delete_session(self._runtime_root, session_id)

    def create_recording_export(self, session_id: str) -> dict[str, Any]:
        self._require()
        self._require_recording_feature()
        return RecordingStorageV6.create_export(self._runtime_root, session_id, mode='default')

    def recording_export_path(self, session_id: str, export_id: str) -> Path:
        self._require()
        self._require_recording_feature()
        return RecordingStorageV6.export_path(self._runtime_root, session_id, export_id)

    def start(
        self,
        payload: dict[str, Any],
        *,
        execution_id: str = '',
    ) -> dict[str, Any]:
        """Start one ordinary Player run.

        ``execution_id`` is an internal host-control seam used by the
        per-user Player Hub.  Interactive HTTP callers never provide it.  A
        scheduled dispatch derives a stable run identity before admission and
        must pass that identity through to the same Runtime path; otherwise a
        lost acknowledgement could manufacture a second run.
        """
        self._require()
        pinned_updates: dict[str, str] = {}
        for domain, client in self._update_clients.items():
            try:
                pinned_updates[domain] = client.assert_task_start_allowed()
            except UpdateClientError as exc:
                raise PlayerBundleError(str(exc)) from exc
        target, ecir, selected_target_id = self._prepare_execution(payload)
        content_release_id = pinned_updates.get(
            'project_content', str(self._manifest.get('release_id') or ''),
        )
        ecir['release_id'] = content_release_id
        ecir['update_release_ids'] = copy.deepcopy(pinned_updates)
        requirements = self._dangerous_operation_requirements(ecir)
        ecir['dangerous_operation_confirmations'] = (
            self._validated_dangerous_confirmations(
                requirements, payload.get('dangerous_confirmations'),
            )
        )
        try:
            target = merge_target_overrides(
                target,
                ecir.get('target_overrides') or {},
            )
            message_context = None
            if program_uses_messages(ecir):
                project_namespace = str(self._manifest.get('project_id') or '').strip()
                if not project_namespace:
                    raise PlayerBundleError('Player 包缺少消息项目命名空间')
                message_service = MessageRuntimeV6()
                instance_id = str(payload.get('message_instance_id') or '').strip()
                endpoint_key = str(
                    os.environ.get('EASYCODE_PLAYER_INSTANCE_KEY') or ''
                ).strip()
                if not endpoint_key:
                    data_identity = str(self._data_root().resolve()).casefold()
                    endpoint_key = 'player-' + hashlib.sha256(
                        data_identity.encode('utf-8')
                    ).hexdigest()[:32]
                display_name = str(
                    os.environ.get('EASYCODE_PLAYER_INSTANCE_NAME') or '实例1'
                ).strip()
                signing_key_id = str(
                    self._signature.get('key_id') or ''
                )
                trust_domain = 'product_' + hashlib.sha256(
                    f'{project_namespace}\0{signing_key_id}'.encode('utf-8')
                ).hexdigest()[:32]
                if instance_id:
                    message_service.register_instance(
                        project_namespace,
                        display_name,
                        instance_id=instance_id,
                        endpoint_key=endpoint_key,
                        endpoint_kind='player',
                        trust_domain=trust_domain,
                    )
                else:
                    registered = message_service.register_instance(
                        project_namespace,
                        display_name,
                        endpoint_key=endpoint_key,
                        endpoint_kind='player',
                        trust_domain=trust_domain,
                    )
                    instance_id = str(registered['instance_id'])
                message_context = message_service.instance_context(
                    project_namespace,
                    instance_id=instance_id,
                )
            recording_plan = self._player_recording_plan(payload)
            for client in self._update_clients.values():
                client.mark_runtime_state(running_or_paused=True)
            result = vnext_runtime.start(
                ecir,
                debug=payload.get('debug') or {},
                target=target,
                execution_id=str(execution_id or ''),
                message_context=message_context,
            )
            execution_id = str(result.get('execution_id') or '')
            if execution_id:
                with self._lock:
                    self._execution_ids.add(execution_id)
                    monitor = threading.Thread(
                        target=self._monitor_update_execution,
                        args=(execution_id,),
                        daemon=True,
                        name=f'player-update-run-{execution_id[-8:]}',
                    )
                    self._update_monitors[execution_id] = monitor
                    monitor.start()
            result['release_id'] = content_release_id
            result['update_release_ids'] = copy.deepcopy(pinned_updates)
            if recording_plan.get('enabled') and target is not None and execution_id:
                recording_options = {
                    'recording_mode': recording_plan.get('strategy'),
                    'target_fps': recording_plan.get('target_fps'),
                    'max_duration_ms': recording_plan.get('max_duration_ms'),
                    'max_session_bytes': recording_plan.get('max_session_bytes'),
                    'min_free_bytes': recording_plan.get('min_free_bytes'),
                }
                try:
                    recording_state = self._recording.start(
                        self._runtime_root,
                        target,
                        recording_options,
                        run_id=execution_id,
                        instance_id=str(
                            os.environ.get('EASYCODE_PLAYER_INSTANCE_ID') or 'player-1'
                        ),
                        storage_root=str(self._data_root() / 'recordings'),
                    )
                    monitor = threading.Thread(
                        target=self._monitor_player_recording,
                        args=(execution_id, self._runtime_root),
                        daemon=True,
                        name=f'player-recording-{execution_id[-8:]}',
                    )
                    with self._lock:
                        self._recording_monitors[execution_id] = monitor
                    monitor.start()
                    result['recording'] = recording_state
                except Exception as recording_error:
                    result['recording'] = {
                        'active': False,
                        'status': 'error',
                        'terminal_reason': 'driver_failed',
                        'last_error': str(recording_error),
                    }
            else:
                result['recording'] = {
                    'active': False,
                    **recording_plan,
                    **(
                        {'status': 'unsupported', 'reason': 'target_missing'}
                        if recording_plan.get('enabled') and target is None
                        else {}
                    ),
                }
            return result
        except (MessageRuntimeError, RuntimeFailure, ValueError) as exc:
            with self._lock:
                busy = self._runtime_busy()
                for client in self._update_clients.values():
                    client.mark_runtime_state(running_or_paused=busy)
            raise PlayerBundleError(str(exc)) from exc

    def shutdown(self) -> None:
        self._update_scheduler_stop.set()
        with contextlib.suppress(Exception):
            if self._runtime_root:
                self._recording.stop(self._runtime_root, 'user_stopped')
        with self._lock:
            root = self._runtime_root
            active_capture = copy.deepcopy(self._active_capture or {})
            self._bundle_path = self._runtime_root = ''
            self._manifest, self._signature = {}, {}
            self._ecir, self._base_form, self._form, self._project = {}, {}, {}, {}
            self._publish_report = {}
            self._extension_lock = {}
            self._extensions = {}
            self._override_assets = {}
            self._profile_override_assets = {}
            self._active_capture = None
            self._execution_ids = set()
            self._recording_monitors = {}
            update_clients = list(self._update_clients.values())
            self._update_config = {}
            self._update_clients = {}
            self._update_preferences = {}
            self._update_monitors = {}
            self._update_scheduler_thread = None
        for client in update_clients:
            with contextlib.suppress(Exception):
                client.close()
        if active_capture:
            self._release_control_capture(active_capture)
        if root:
            shutil.rmtree(root, ignore_errors=True)


vnext_player_bundle_manager = VNextPlayerBundleManager()
