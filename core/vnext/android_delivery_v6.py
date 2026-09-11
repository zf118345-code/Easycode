"""Android APK build and local ADB delivery boundary for format-6 Players.

The service deliberately has no emulator or ``adb input`` fallback: ADB only
installs/starts the native APK, transfers an already signed content package,
and retrieves its logs.  Capture and input remain inside the APK through
MediaProjection and AccessibilityService.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .bundle_signing_v6 import BUNDLE_FORMAT_V6, BundleSignatureError, verify_signed_archive
from .extension_schema_v6 import (
    EasyCodeLockV1,
    ExtensionSchemaError,
    PublishedExtensionV1,
    extension_android_manifest_permissions,
    validate_published_extension,
)
from .player_bindings import player_terminal_action_closure
from .pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash


class AndroidDeliveryError(RuntimeError):
    def __init__(self, code: str, message: str, *, diagnostics: list[dict[str, Any]] | None = None) -> None:
        self.code = code
        self.diagnostics = diagnostics or []
        super().__init__(f'[{code}] {message}')


@dataclass(frozen=True)
class AndroidCommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AndroidToolchainV6:
    java_home: Path = Path(r'D:\EasyCodeToolchains\jdk17')
    sdk_root: Path = Path(r'D:\EasyCodeToolchains\android-sdk')
    gradle_home: Path = Path(r'D:\EasyCodeToolchains\gradle-9.5.1')
    gradle_user_home: Path = Path(r'D:\EasyCodeToolchains\gradle-cache')
    build_tools_version: str = '37.0.0'

    @property
    def gradle(self) -> Path:
        return self.gradle_home / 'bin' / ('gradle.bat' if os.name == 'nt' else 'gradle')

    @property
    def adb(self) -> Path:
        return self.sdk_root / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')

    @property
    def apksigner(self) -> Path:
        return self.sdk_root / 'build-tools' / self.build_tools_version / (
            'apksigner.bat' if os.name == 'nt' else 'apksigner'
        )

    @property
    def aapt2(self) -> Path:
        return self.sdk_root / 'build-tools' / self.build_tools_version / (
            'aapt2.exe' if os.name == 'nt' else 'aapt2'
        )

    def environment(self) -> dict[str, str]:
        value = os.environ.copy()
        value.update({
            'JAVA_HOME': str(self.java_home.resolve()),
            'ANDROID_HOME': str(self.sdk_root.resolve()),
            'ANDROID_SDK_ROOT': str(self.sdk_root.resolve()),
            'GRADLE_USER_HOME': str(self.gradle_user_home.resolve()),
        })
        return value

    def validate(self, *, need_gradle: bool = False, need_adb: bool = False) -> None:
        required: list[tuple[str, Path]] = []
        if need_gradle:
            required.extend((
                ('JDK 17', self.java_home / 'bin' / ('java.exe' if os.name == 'nt' else 'java')),
                ('Gradle 9.5.1', self.gradle),
                ('Android API 37', self.sdk_root / 'platforms' / 'android-37.0' / 'android.jar'),
                ('Android build-tools 37.0.0', self.apksigner),
                ('aapt2 37.0.0', self.aapt2),
            ))
        if need_adb:
            required.append(('ADB 37.0.1', self.adb))
        missing = [f'{label}: {path}' for label, path in required if not path.is_file()]
        if missing:
            raise AndroidDeliveryError('android.toolchain_missing', 'Android 工具链不完整', diagnostics=[
                {'missing': item} for item in missing
            ])
        self.gradle_user_home.mkdir(parents=True, exist_ok=True)


_ANDROID_OPCODES = frozenset({
    'log.write', 'wait.duration', 'wait.until', 'random.integer', 'time.now', 'time.today',
    'project.data_directory', 'data.assign', 'data.assign_local', 'data.assign_project',
    'call.project', 'call.extension', 'control.if', 'control.repeat', 'control.while', 'control.for_each',
    'control.for_each_map', 'control.break', 'control.continue', 'control.fail', 'control.try',
    'control.return', 'control.target_scope', 'target.wait_online', 'target.status',
    'target.capture_frame', 'frame.save', 'frame.crop_region', 'color.read', 'color.find', 'host.app.start',
    'vision.find', 'vision.find_all', 'vision.compare_samples',
    'clipboard.read_text', 'clipboard.write_text',
    'text.recognize',
    'standard.control.wait_visible', 'standard.control.wait_hidden',
    'standard.image.wait_visible', 'standard.image.wait_hidden',
    'standard.image.click_once', 'standard.image.click_until_hidden',
    'standard.image.click_position_until_visible', 'standard.image.click_position_until_hidden',
    'standard.text.match', 'standard.text.wait_visible',
    'input.click', 'input.text', 'input.scroll', 'input.drag', 'input.key',
    'control.find', 'control.click', 'control.click_selector', 'control.read_text', 'control.input_text',
    'control.read_status', 'control.focus', 'control.set_value', 'control.select',
    'control.toggle', 'control.scroll_into_view',
    'control.listen', 'message.send', 'message.wait_receive', 'message.wait_read',
    'message.cancel',
    'network.request', 'network.upload_file', 'network.download_file',
    'file.exists', 'file.read_text', 'file.write_text', 'file.append_text',
    'file.replace_text', 'file.read_json', 'file.write_json', 'file.delete', 'file.copy',
    'file.move', 'directory.exists', 'directory.create', 'directory.list', 'directory.copy',
    'directory.move', 'directory.delete', 'directory.delete_tree',
})
_ANDROID_ACTIONS = frozenset({
    'pick-point', 'pick-region', 'pick-color', 'capture-image', 'choose-resource', 'capture-control', 'capture-path',
    'choose-file-read', 'choose-file-save', 'choose-directory',
})

_ANDROID_PERMISSION = 'http://schemas.android.com/apk/res/android'
_ANDROID_TOOLS = 'http://schemas.android.com/tools'
_ANDROID_MINIMUM_WEBVIEW_MAJOR = 64
_ANDROID_BASE_MANIFEST_PERMISSIONS = frozenset({
    'android.permission.FOREGROUND_SERVICE',
    'android.permission.FOREGROUND_SERVICE_SPECIAL_USE',
    'android.permission.POST_NOTIFICATIONS',
    'android.permission.RECEIVE_BOOT_COMPLETED',
    'android.permission.WAKE_LOCK',
})
_ANDROID_NETWORK_MANIFEST_PERMISSIONS = frozenset({
    'android.permission.INTERNET',
    'android.permission.ACCESS_NETWORK_STATE',
})
_ANDROID_LAN_MANIFEST_PERMISSIONS = frozenset({
    'android.permission.ACCESS_WIFI_STATE',
    'android.permission.CHANGE_WIFI_MULTICAST_STATE',
})
_ANDROID_CAPTURE_MANIFEST_PERMISSIONS = frozenset({
    'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION',
    'android.permission.SYSTEM_ALERT_WINDOW',
})
_ANDROID_APPLICATION_UPDATE_MANIFEST_PERMISSIONS = frozenset({
    'android.permission.REQUEST_INSTALL_PACKAGES',
})
_SERIAL = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')
_PACKAGE = re.compile(r'^com\.easycode\.player(?:\.debug|\.emulator(?:\.debug)?)?$')
_SOURCE_SUFFIXES = frozenset({'.easy', '.py', '.pyc', '.kt', '.java', '.ts', '.tsx', '.vue', '.gradle', '.kts'})


class AndroidDeliveryServiceV6:
    VARIANTS = {
        'productionDebug': ('assembleProductionDebug', 'production/debug/app-production-debug.apk', 'com.easycode.player.debug'),
        'emulatorDebug': ('assembleEmulatorDebug', 'emulator/debug/app-emulator-debug.apk', 'com.easycode.player.emulator.debug'),
        'productionRelease': ('assembleProductionRelease', 'production/release/app-production-release.apk', 'com.easycode.player'),
    }

    def __init__(
        self,
        repository_root: str | Path | None = None,
        *,
        toolchain: AndroidToolchainV6 | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.repository_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
        self.android_root = self.repository_root / 'android'
        self.toolchain = toolchain or AndroidToolchainV6()
        self._runner = runner or subprocess.run

    @staticmethod
    def _json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            value = json.loads(archive.read(name).decode('utf-8-sig'))
        except Exception as exc:
            raise AndroidDeliveryError('android.bundle_invalid', f'Player 包文件无法读取：{name}') from exc
        if not isinstance(value, dict):
            raise AndroidDeliveryError('android.bundle_invalid', f'Player 包文件不是 JSON 对象：{name}')
        return value

    @staticmethod
    def _reject_source_members(archive: zipfile.ZipFile) -> None:
        for member in archive.infolist():
            raw = member.filename
            normalized = raw.replace('\\', '/')
            parts = normalized.split('/')
            lower = normalized.lower()
            if (
                raw != normalized
                or normalized.startswith('/')
                or any(part in {'', '.', '..'} for part in parts)
                or lower.startswith(('program/', '.easycode/'))
                or '/src/' in lower
                or PurePosixPath(lower).suffix in _SOURCE_SUFFIXES
            ):
                raise AndroidDeliveryError(
                    'android.source_isolation_failed',
                    f'Android Player 包包含源码、编辑投影或不安全路径：{raw}',
                )

    @staticmethod
    def _walk_instructions(value: Any):
        if isinstance(value, list):
            for item in value:
                yield from AndroidDeliveryServiceV6._walk_instructions(item)
        elif isinstance(value, dict):
            if value.get('instruction_id') and value.get('opcode'):
                yield value
            for item in value.values():
                yield from AndroidDeliveryServiceV6._walk_instructions(item)

    def _validate_android_extensions(
        self,
        bundle: Path,
        lock_value: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Verify Android extension signatures and return static-link modules."""

        try:
            lock = EasyCodeLockV1.model_validate(lock_value)
        except Exception as exc:
            raise AndroidDeliveryError('android.extension_invalid', f'扩展锁格式无效：{exc}') from exc
        if not lock.extensions:
            return []
        temporary_parent = self.repository_root / '.artifacts' / 'android-extension-validation'
        temporary_parent.mkdir(parents=True, exist_ok=True)
        modules: list[dict[str, Any]] = []
        seen_functions: set[str] = set()
        seen_variants: set[tuple[str, str]] = set()
        try:
            with tempfile.TemporaryDirectory(prefix='verify-', dir=temporary_parent) as temporary_name:
                root = Path(temporary_name)
                with zipfile.ZipFile(bundle, 'r') as archive:
                    names = set(archive.namelist())
                    for locked in lock.extensions:
                        descriptor_path = f'runtime/extensions/{locked.package_id}/extension.json'
                        if descriptor_path not in names:
                            raise AndroidDeliveryError(
                                'android.extension_invalid',
                                f'Android 扩展缺少发布描述：{locked.package_id}',
                            )
                        try:
                            descriptor = PublishedExtensionV1.model_validate(
                                json.loads(archive.read(descriptor_path).decode('utf-8-sig'))
                            )
                        except Exception as exc:
                            raise AndroidDeliveryError(
                                'android.extension_invalid',
                                f'Android 扩展发布描述无效：{locked.package_id}（{exc}）',
                            ) from exc
                        package_root = root / 'runtime' / 'extensions' / locked.package_id
                        package_root.mkdir(parents=True, exist_ok=True)
                        for variant in descriptor.variants:
                            for relative in (variant.artifact_path, variant.artifact_signature_path):
                                if relative not in names:
                                    raise AndroidDeliveryError(
                                        'android.extension_invalid',
                                        f'Android 扩展文件缺失：{relative}',
                                    )
                                destination = root.joinpath(*PurePosixPath(relative).parts)
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                destination.write_bytes(archive.read(relative))
                        try:
                            validated = validate_published_extension(root, descriptor, locked)
                        except ExtensionSchemaError as exc:
                            raise AndroidDeliveryError(
                                'android.extension_invalid',
                                f'Android 扩展签名或密封闭包无效：{locked.package_id}（{exc}）',
                            ) from exc
                        contracts = {
                            contract.function_id: contract
                            for contract in descriptor.function_contracts
                        }
                        for variant in descriptor.variants:
                            if variant.host != 'android_native' or variant.runtime != 'android-kotlin-v1':
                                raise AndroidDeliveryError(
                                    'android.extension_variant_unsupported',
                                    f'APK 只能携带 Android Kotlin/JVM 扩展变体：{locked.package_id}/{variant.variant_id}',
                                )
                            variant_key = (locked.package_id, variant.variant_id)
                            if variant_key in seen_variants:
                                continue
                            seen_variants.add(variant_key)
                            artifact = validated['artifacts'].get(variant.variant_id) or {}
                            runtime = artifact.get('runtime') or {}
                            module_path = str(runtime.get('module') or '')
                            artifact_path = Path(str(artifact.get('artifact_path') or ''))
                            if not module_path or not artifact_path.is_file():
                                raise AndroidDeliveryError(
                                    'android.extension_invalid',
                                    f'Android 扩展缺少 JAR module：{locked.package_id}/{variant.variant_id}',
                                )
                            with zipfile.ZipFile(artifact_path, 'r') as sealed:
                                module_bytes = sealed.read(module_path)
                            try:
                                with zipfile.ZipFile(io.BytesIO(module_bytes), 'r') as jar:
                                    jar_names = {name.replace('\\', '/') for name in jar.namelist()}
                            except (OSError, zipfile.BadZipFile) as exc:
                                raise AndroidDeliveryError(
                                    'android.extension_invalid',
                                    f'Android 扩展 module 不是有效 JAR：{locked.package_id}/{variant.variant_id}',
                                ) from exc
                            for function_id, class_name in variant.entrypoints.items():
                                class_path = class_name.replace('.', '/').replace('$', '$') + '.class'
                                if class_path not in jar_names:
                                    raise AndroidDeliveryError(
                                        'android.extension_entrypoint_missing',
                                        f'Android 扩展入口类不存在：{function_id} -> {class_name}',
                                    )
                                if function_id in seen_functions:
                                    raise AndroidDeliveryError(
                                        'android.extension_function_duplicate',
                                        f'Android 扩展函数入口重复：{function_id}',
                                    )
                                seen_functions.add(function_id)
                            function_permissions = sorted({
                                permission
                                for function_id in variant.entrypoints
                                for permission in contracts[function_id].permissions
                            })
                            modules.append({
                                'package_id': locked.package_id,
                                'variant_id': variant.variant_id,
                                'minimum_android_api': variant.minimum_android_api,
                                'artifact_sha256': variant.artifact_sha256,
                                'module_path': module_path,
                                'module_sha256': hashlib.sha256(module_bytes).hexdigest(),
                                'module_bytes': module_bytes,
                                'entrypoints': dict(variant.entrypoints),
                                'permissions': function_permissions,
                                'declared_permissions': sorted(descriptor.permissions),
                                'android_manifest_permissions': list(
                                    extension_android_manifest_permissions(descriptor.permissions)
                                ),
                            })
        except AndroidDeliveryError:
            raise
        except (OSError, zipfile.BadZipFile, KeyError) as exc:
            raise AndroidDeliveryError('android.extension_invalid', f'Android 扩展无法读取：{exc}') from exc
        return modules

    def validate_bundle(self, bundle_path: str | Path, trust_root_path: str | Path) -> dict[str, Any]:
        bundle = Path(bundle_path).expanduser().resolve()
        trust_root = Path(trust_root_path).expanduser().resolve()
        if not bundle.is_file() or not trust_root.is_file():
            raise AndroidDeliveryError('android.bundle_missing', 'Player 包或发布者信任根不存在')
        try:
            with zipfile.ZipFile(bundle, 'r') as archive:
                signature = verify_signed_archive(archive, trust_root)
                self._reject_source_members(archive)
                manifest = self._json_member(archive, 'manifest.json')
                ecir = self._json_member(archive, 'runtime/ecir.json')
                project = self._json_member(archive, 'runtime/project.json')
                lock_bytes = archive.read('runtime/easycode.lock')
                lock = self._json_member(archive, 'runtime/easycode.lock')
                form = self._json_member(archive, 'player/form.json')
                report = self._json_member(archive, 'publish-report.json')
                update_config = (
                    self._json_member(archive, 'update/config.json')
                    if 'update/config.json' in archive.namelist()
                    else {}
                )
        except AndroidDeliveryError:
            raise
        except (BundleSignatureError, zipfile.BadZipFile, KeyError) as exc:
            raise AndroidDeliveryError('android.bundle_signature_invalid', str(exc)) from exc

        if (
            int(manifest.get('bundle_format') or 0) != BUNDLE_FORMAT_V6
            or not str(manifest.get('project_id') or '')
            or not str(manifest.get('release_id') or '')
            or str(manifest.get('signing_key_id') or '') != signature['key_id']
        ):
            raise AndroidDeliveryError(
                'android.bundle_manifest_invalid',
                'Player 包版本、身份或发布签名声明无效',
            )
        if manifest.get('source_included') is not False:
            raise AndroidDeliveryError('android.source_isolation_failed', 'Android APK 只接受无项目源码的 Player 包')
        if (
            str(manifest.get('easycode_lock_sha256') or '') != hashlib.sha256(lock_bytes).hexdigest()
            or int(manifest.get('extension_package_count') or 0) != len(lock.get('extensions') or [])
        ):
            raise AndroidDeliveryError(
                'android.bundle_manifest_invalid',
                'Player 包清单与 easycode.lock 闭包不一致',
            )
        if report.get('valid') is not True or report.get('source_included') is not False:
            raise AndroidDeliveryError('android.publish_report_invalid', 'Player 发布报告未通过或未证明源码隔离')
        if int(ecir.get('ecir_version') or 0) != 1 or int(ecir.get('program_model_version') or 0) != 1:
            raise AndroidDeliveryError(
                'android.ecir_incompatible',
                'Android Runtime 只接受 ECIR v1 / Program Model v1',
            )
        minimum_android_api = ecir.get('minimum_android_api')
        report_android_api = report.get('minimum_android_api')
        if (
            isinstance(minimum_android_api, bool)
            or not isinstance(minimum_android_api, int)
            or not 21 <= minimum_android_api <= 37
            or report_android_api != minimum_android_api
        ):
            raise AndroidDeliveryError(
                'android.minimum_api_invalid',
                'ECIR 与发布报告必须声明相同且有效的 Android 最低 API（21..37）',
            )
        api_requirements = ecir.get('android_api_requirements') or []
        if (
            not isinstance(api_requirements, list)
            or report.get('android_api_requirements', []) != api_requirements
        ):
            raise AndroidDeliveryError(
                'android.minimum_api_invalid',
                'Android 最低版本依据与发布报告不一致',
            )
        requirement_floors: list[int] = []
        for requirement in api_requirements:
            floor = requirement.get('minimum_android_api') if isinstance(requirement, Mapping) else None
            if isinstance(floor, bool) or not isinstance(floor, int) or not 22 <= floor <= 37:
                raise AndroidDeliveryError(
                    'android.minimum_api_invalid',
                    'Android 最低版本依据包含无效能力要求',
                )
            requirement_floors.append(floor)
        if max([21, *requirement_floors]) != minimum_android_api:
            raise AndroidDeliveryError(
                'android.minimum_api_invalid',
                'Android 最低版本没有与项目所用能力的最高要求一致',
            )
        toolchain = lock.get('toolchain') or {}
        ecir_registry = ecir.get('pure_operation_registry') or {}
        expected_registry_hash = pure_operation_registry_hash()
        if (
            not isinstance(toolchain, Mapping)
            or toolchain.get('pure_value_registry_version') != PURE_OPERATION_REGISTRY_VERSION
            or toolchain.get('pure_value_registry_sha256') != expected_registry_hash
            or not isinstance(ecir_registry, Mapping)
            or ecir_registry.get('registry_version') != PURE_OPERATION_REGISTRY_VERSION
            or ecir_registry.get('content_hash') != expected_registry_hash
        ):
            raise AndroidDeliveryError(
                'android.registry_incompatible',
                f'Player 包纯值注册表与 Android Runtime v{PURE_OPERATION_REGISTRY_VERSION} 不兼容',
            )
        extensions = lock.get('extensions') or []
        if not isinstance(extensions, list):
            raise AndroidDeliveryError('android.bundle_invalid', 'easycode.lock 扩展闭包格式无效')
        extension_floors: dict[str, int] = {}
        for extension in extensions:
            if not isinstance(extension, Mapping):
                raise AndroidDeliveryError('android.bundle_invalid', 'easycode.lock 扩展记录格式无效')
            package_id = str(extension.get('package_id') or '')
            selected_variants = extension.get('selected_variants') or []
            if not isinstance(selected_variants, list):
                raise AndroidDeliveryError('android.bundle_invalid', 'easycode.lock 扩展变体格式无效')
            floors: list[int] = []
            for variant in selected_variants:
                if not isinstance(variant, Mapping) or variant.get('host') != 'android_native':
                    continue
                floor = variant.get('minimum_android_api')
                if isinstance(floor, bool) or not isinstance(floor, int) or not 21 <= floor <= 37:
                    raise AndroidDeliveryError(
                        'android.minimum_api_invalid',
                        f'Android 扩展 {package_id or "<unknown>"} 没有声明有效最低 API',
                    )
                floors.append(floor)
            if floors:
                if not package_id or package_id in extension_floors:
                    raise AndroidDeliveryError('android.bundle_invalid', 'Android 扩展身份缺失或重复')
                extension_floors[package_id] = max(floors)
        requirement_extension_floors: dict[str, int] = {}
        for requirement in api_requirements:
            if not isinstance(requirement, Mapping) or requirement.get('kind') != 'extension':
                continue
            package_id = str(requirement.get('package_id') or '')
            floor = requirement.get('minimum_android_api')
            if not package_id or package_id in requirement_extension_floors or not isinstance(floor, int):
                raise AndroidDeliveryError('android.minimum_api_invalid', 'Android 扩展最低版本依据格式无效')
            requirement_extension_floors[package_id] = floor
        expected_extension_floors = {
            package_id: floor for package_id, floor in extension_floors.items() if floor > 21
        }
        if requirement_extension_floors != expected_extension_floors:
            raise AndroidDeliveryError(
                'android.minimum_api_invalid',
                'Android 扩展变体与项目最低版本依据不一致',
            )
        android_extension_modules = self._validate_android_extensions(bundle, lock)
        extension_permissions = sorted({
            permission
            for module in android_extension_modules
            for permission in module['declared_permissions']
        })
        if report.get('extension_permissions', []) != extension_permissions:
            raise AndroidDeliveryError(
                'android.publish_report_invalid',
                'Android 扩展权限闭包与发布报告不一致',
            )
        available_extension_functions = {
            function_id
            for module in android_extension_modules
            for function_id in module['entrypoints']
        }
        targets = project.get('targets') or []
        invalid_targets = [
            str(item.get('target_id') or '') for item in targets
            if not isinstance(item, Mapping) or item.get('type') != 'android_local'
        ]
        if invalid_targets:
            raise AndroidDeliveryError(
                'android.target_unsupported',
                f'APK 只能包含 Android 本机目标：{invalid_targets[0]}',
            )
        unsupported: list[str] = []
        instruction_capabilities: set[str] = set()
        for instruction in self._walk_instructions(ecir.get('functions') or []):
            opcode = str(instruction.get('opcode') or '')
            statement_id = str(instruction.get('instruction_id') or '')
            if opcode not in _ANDROID_OPCODES:
                unsupported.append(f'{statement_id}:{opcode}')
            raw_capabilities = instruction.get('capabilities') or []
            if not isinstance(raw_capabilities, list) or any(
                not isinstance(item, str) or not item for item in raw_capabilities
            ):
                raise AndroidDeliveryError(
                    'android.publish_report_invalid',
                    f'Android 指令能力闭包格式无效：{statement_id}',
                )
            instruction_capabilities.update(raw_capabilities)
            if (
                opcode == 'call.extension'
                and str(instruction.get('callee_function_id') or '') not in available_extension_functions
            ):
                unsupported.append(f'{statement_id}:missing-extension-entrypoint')
            if opcode == 'directory.delete_tree':
                review = instruction.get('dangerous_author_review') or {}
                if not isinstance(review, Mapping) or not review.get('fingerprint') or not review.get('contract_fingerprint'):
                    unsupported.append(f'{statement_id}:missing-dangerous-review')
            if opcode.startswith('network.') and not isinstance(instruction.get('network_authorization'), Mapping):
                unsupported.append(f'{statement_id}:missing-network-authorization')
        if unsupported:
            raise AndroidDeliveryError(
                'android.operation_unsupported',
                f'Android Runtime 不支持或不能安全审核指令：{sorted(unsupported)[0]}',
            )
        if int(form.get('schema_version') or 0) != 3:
            raise AndroidDeliveryError('android.form_unsupported', 'Android Player 只接受 Control Schema 3')
        for page in form.get('pages') or []:
            for control in (page.get('controls') or []) if isinstance(page, Mapping) else []:
                for action in (control.get('terminal_actions') or []) if isinstance(control, Mapping) else []:
                    platforms = set(action.get('platforms') or []) if isinstance(action, Mapping) else set()
                    action_id = str(action.get('action_id') or '') if isinstance(action, Mapping) else ''
                    if 'android_local' in platforms and action_id not in _ANDROID_ACTIONS:
                        raise AndroidDeliveryError(
                            'android.player_action_unsupported',
                            f'Android Player 没有真实字段动作实现：{action_id}',
                        )
        terminal_closure = player_terminal_action_closure(form)
        if report.get('player_terminal_actions') != terminal_closure:
            raise AndroidDeliveryError(
                'android.publish_report_invalid',
                'Player 字段动作发布闭包与表单不一致',
            )
        terminal_capabilities = sorted({str(item['capability']) for item in terminal_closure})
        if report.get('player_terminal_capabilities') != terminal_capabilities:
            raise AndroidDeliveryError(
                'android.publish_report_invalid',
                'Player 字段动作能力闭包与发布报告不一致',
            )
        required_capabilities = sorted(
            instruction_capabilities | set(terminal_capabilities) | set(extension_permissions)
        )
        if report.get('required_capabilities', []) != required_capabilities:
            raise AndroidDeliveryError(
                'android.publish_report_invalid',
                'Android 指令、Player 与扩展能力闭包和发布报告不一致',
            )
        supported_platforms = sorted(str(item) for item in report.get('supported_platforms') or [])
        verified_platforms = sorted(str(item) for item in report.get('verified_platforms') or [])
        if not set(verified_platforms).issubset(supported_platforms):
            raise AndroidDeliveryError(
                'android.publish_report_invalid',
                '发布报告的 verified_platforms 不能超出 supported_platforms',
            )
        android_local_verified = (
            'android_local' in supported_platforms and
            'android_local' in verified_platforms
        )
        return {
            'bundle': str(bundle),
            'trust_root': str(trust_root),
            'project_id': str(manifest.get('project_id') or ''),
            'release_id': str(manifest.get('release_id') or ''),
            'key_id': signature['key_id'],
            'integrity_sha256': signature['integrity_sha256'],
            'extension_count': len(android_extension_modules),
            'android_extension_modules': android_extension_modules,
            'extension_permissions': extension_permissions,
            'extension_android_manifest_permissions': sorted({
                permission
                for module in android_extension_modules
                for permission in module['android_manifest_permissions']
            }),
            'required_capabilities': required_capabilities,
            'supported_platforms': supported_platforms,
            'verified_platforms': verified_platforms,
            'android_local_contract_status': 'verified' if android_local_verified else 'planned',
            'release_readiness': 'ready' if android_local_verified else 'blocked_physical_device_harness',
            'release_blockers': [] if android_local_verified else [
                'disconnected_physical_device_harness',
                'native_abi_closure_unverified',
            ],
            'application_updates_enabled': 'player_application' in (
                update_config.get('domains') if isinstance(update_config.get('domains'), Mapping) else {}
            ),
            'minimum_android_api': minimum_android_api,
            'android_api_requirements': api_requirements,
        }

    def _run(
        self,
        argv: Sequence[str | Path],
        *,
        cwd: Path | None = None,
        timeout: float = 600,
        check: bool = True,
    ) -> AndroidCommandResult:
        command = tuple(str(item) for item in argv)
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            completed = self._runner(
                list(command),
                cwd=str(cwd or self.repository_root),
                env=self.toolchain.environment(),
                text=True,
                encoding='utf-8',
                errors='replace',
                capture_output=True,
                timeout=timeout,
                check=False,
                creationflags=flags,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AndroidDeliveryError('android.command_failed', f'无法执行 Android 工具：{command[0]}（{exc}）') from exc
        result = AndroidCommandResult(command, int(completed.returncode), completed.stdout or '', completed.stderr or '')
        if check and result.returncode != 0:
            tail = (result.stderr or result.stdout).strip()[-4000:]
            raise AndroidDeliveryError(
                'android.command_failed',
                f'Android 命令失败（exit={result.returncode}）：{tail or command[0]}',
                diagnostics=[{'argv': list(command), 'returncode': result.returncode}],
            )
        return result

    def _prepare_android_extension_inputs(self, metadata: Mapping[str, Any]) -> tuple[Path, Path]:
        root = self.android_root / 'app' / 'build' / 'easycodeExtensionInputs'
        if root.exists():
            shutil.rmtree(root)
        jars = root / 'jars'
        jars.mkdir(parents=True, exist_ok=True)
        registry_modules: list[dict[str, Any]] = []
        for index, module in enumerate(metadata.get('android_extension_modules') or []):
            module_bytes = module.get('module_bytes')
            if not isinstance(module_bytes, bytes):
                raise AndroidDeliveryError('android.extension_invalid', 'Android 扩展构建模块缺少已验证 JAR 字节')
            module_hash = hashlib.sha256(module_bytes).hexdigest()
            if module_hash != module.get('module_sha256'):
                raise AndroidDeliveryError('android.extension_invalid', 'Android 扩展构建模块哈希在构建前发生变化')
            jar_name = f'{index:04d}-{module_hash}.jar'
            (jars / jar_name).write_bytes(module_bytes)
            registry_modules.append({
                'package_id': module['package_id'],
                'variant_id': module['variant_id'],
                'minimum_android_api': module['minimum_android_api'],
                'artifact_sha256': module['artifact_sha256'],
                'module_sha256': module_hash,
                'permissions': list(module['permissions']),
                'declared_permissions': list(module['declared_permissions']),
                'android_manifest_permissions': list(module['android_manifest_permissions']),
                'entrypoints': [
                    {'function_id': function_id, 'class_name': class_name}
                    for function_id, class_name in sorted(module['entrypoints'].items())
                ],
            })
        registry = root / 'extensions.json'
        registry.write_text(
            json.dumps(
                {'schema_version': 1, 'modules': registry_modules},
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
                allow_nan=False,
            ) + '\n',
            encoding='utf-8',
        )
        return jars, registry

    @staticmethod
    def _required_android_manifest_permissions(metadata: Mapping[str, Any]) -> list[str]:
        capabilities = {str(item) for item in metadata.get('required_capabilities') or []}
        permissions = set(_ANDROID_BASE_MANIFEST_PERMISSIONS)
        if capabilities.intersection({'network', 'messaging'}) or metadata.get('application_updates_enabled'):
            permissions.update(_ANDROID_NETWORK_MANIFEST_PERMISSIONS)
        if metadata.get('application_updates_enabled'):
            permissions.update(_ANDROID_APPLICATION_UPDATE_MANIFEST_PERMISSIONS)
        if 'messaging' in capabilities:
            permissions.update(_ANDROID_LAN_MANIFEST_PERMISSIONS)
        if 'target.frame.read' in capabilities or any(
            capability.startswith('player.capture.') for capability in capabilities
        ):
            permissions.update(_ANDROID_CAPTURE_MANIFEST_PERMISSIONS)
        permissions.update(str(item) for item in metadata.get('extension_android_manifest_permissions') or [])
        return sorted(permissions)

    def _prepare_android_manifest_input(self, metadata: Mapping[str, Any]) -> tuple[Path, list[str]]:
        source = self.android_root / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
        try:
            root = ET.parse(source).getroot()
        except (OSError, ET.ParseError) as exc:
            raise AndroidDeliveryError(
                'android.manifest_template_invalid', f'Android Manifest 模板无效：{source}',
            ) from exc
        required = self._required_android_manifest_permissions(metadata)
        required_set = set(required)
        permission_name = f'{{{_ANDROID_PERMISSION}}}name'
        tools_node = f'{{{_ANDROID_TOOLS}}}node'
        for element in list(root):
            if element.tag != 'uses-permission':
                continue
            if str(element.attrib.get(permission_name) or '') in required_set:
                element.attrib.pop(tools_node, None)
            else:
                # AAR manifests (notably offline ML Kit's transport runtime)
                # may add network permissions.  A signed no-network closure
                # must remove those during manifest merging, not merely omit
                # them from the app template.
                element.set(tools_node, 'remove')
        present = {
            str(element.attrib.get(permission_name) or '')
            for element in root.findall('uses-permission')
            if element.attrib.get(tools_node) != 'remove'
        }
        missing = sorted(required_set - present)
        for permission in missing:
            element = ET.Element('uses-permission')
            element.set(permission_name, permission)
            root.insert(0, element)
        ET.register_namespace('android', _ANDROID_PERMISSION)
        ET.register_namespace('tools', _ANDROID_TOOLS)
        payload = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        digest = hashlib.sha256(payload).hexdigest()
        destination = self.android_root / 'app' / 'build' / 'easycodeManifestInputs' / digest / 'AndroidManifest.xml'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != payload:
            temporary = destination.with_suffix('.tmp')
            temporary.write_bytes(payload)
            os.replace(temporary, destination)
        return destination, required

    @staticmethod
    def _release_signing_properties() -> dict[str, str]:
        mapping = {
            'easycode.release.storeFile': 'EASYCODE_ANDROID_RELEASE_STORE_FILE',
            'easycode.release.storePassword': 'EASYCODE_ANDROID_RELEASE_STORE_PASSWORD',
            'easycode.release.keyAlias': 'EASYCODE_ANDROID_RELEASE_KEY_ALIAS',
            'easycode.release.keyPassword': 'EASYCODE_ANDROID_RELEASE_KEY_PASSWORD',
        }
        values = {prop: str(os.environ.get(name) or '').strip() for prop, name in mapping.items()}
        missing = [name for prop, name in mapping.items() if not values[prop]]
        if missing:
            raise AndroidDeliveryError(
                'android.release_signing_missing',
                'release 只接受外部 keystore/CI secret；缺少：' + ', '.join(missing),
            )
        store = Path(values['easycode.release.storeFile']).expanduser().resolve()
        if not store.is_file():
            raise AndroidDeliveryError('android.release_keystore_missing', f'release keystore 不存在：{store}')
        values['easycode.release.storeFile'] = str(store)
        return values

    def build(
        self,
        bundle_path: str | Path,
        trust_root_path: str | Path,
        *,
        variant: str = 'productionDebug',
        output_path: str | Path | None = None,
        verify_reproducible: bool = False,
        version_code: int = 1,
        version_name: str = '6.0.0',
    ) -> dict[str, Any]:
        if variant not in self.VARIANTS:
            raise AndroidDeliveryError('android.variant_invalid', f'Android 构建变体无效：{variant}')
        if isinstance(version_code, bool) or not isinstance(version_code, int) or version_code < 1:
            raise AndroidDeliveryError('android.version_code_invalid', 'Android versionCode 必须是正整数')
        version_name = str(version_name or '').strip()
        if not version_name or len(version_name) > 64 or any(character in version_name for character in '\r\n\x00'):
            raise AndroidDeliveryError('android.version_name_invalid', 'Android versionName 必须是 1 到 64 个可显示字符')
        self.toolchain.validate(need_gradle=True)
        metadata = self.validate_bundle(bundle_path, trust_root_path)
        if variant == 'productionRelease' and metadata['android_local_contract_status'] != 'verified':
            raise AndroidDeliveryError(
                'android.release_readiness_blocked',
                'ADR-053 要求签名 APK 在断开 IDE、后端和数据线的真机 Harness 通过后，'
                'Compiler/Publisher 才能把 android_local 标记 verified；当前只能构建 debug 候选 APK',
                diagnostics=[{
                    'status': metadata['android_local_contract_status'],
                    'required_evidence': 'disconnected_physical_device_harness',
                }, {
                    'status': 'unverified',
                    'required_evidence': 'native_abi_closure_with_real_runtime_dependencies',
                }],
            )
        task, relative_apk, application_id = self.VARIANTS[variant]
        frontend_root = self.repository_root / 'frontend'
        player_web = self.repository_root / 'release' / 'player-web'
        npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
        if not npm:
            raise AndroidDeliveryError(
                'android.player_web_toolchain_missing',
                'Android Player 需要 Node/npm 构建共享 Player 渲染层',
            )
        self._run([npm, 'run', 'build:player'], cwd=frontend_root, timeout=600)
        if not (player_web / 'player.html').is_file():
            raise AndroidDeliveryError(
                'android.player_web_missing',
                '共享 Player Web 构建成功但 player.html 不存在',
            )
        extension_jars, extension_registry = self._prepare_android_extension_inputs(metadata)
        android_manifest, required_manifest_permissions = self._prepare_android_manifest_input(metadata)
        properties = {
            'easycode.player.bundle': metadata['bundle'],
            'easycode.player.trustRoot': metadata['trust_root'],
            'easycode.player.webAssets': str(player_web.resolve()),
            'easycode.applicationUpdatesEnabled': str(metadata['application_updates_enabled']).lower(),
            'easycode.versionCode': str(version_code),
            'easycode.versionName': version_name,
            'easycode.minSdk': str(metadata['minimum_android_api']),
            'easycode.extensionJars': str(extension_jars.resolve()),
            'easycode.extensionRegistry': str(extension_registry.resolve()),
            'easycode.manifest': str(android_manifest.resolve()),
        }
        if variant == 'productionRelease':
            properties.update(self._release_signing_properties())
        command: list[str | Path] = [self.toolchain.gradle, '--no-daemon', '--max-workers=1']
        # Reproducibility compares two complete executions of the same task
        # graph. Comparing a possibly stale incremental APK with a forced
        # rebuild measures cache history rather than output determinism.
        if verify_reproducible:
            command.append('--rerun-tasks')
        command.append(f':app:{task}')
        command.extend(f'-P{key}={value}' for key, value in properties.items())
        self._run(command, cwd=self.android_root, timeout=1800)
        built = self.android_root / 'app' / 'build' / 'outputs' / 'apk' / relative_apk
        if not built.is_file():
            raise AndroidDeliveryError('android.apk_missing', f'Gradle 成功但 APK 不存在：{built}')
        first_hash = self._sha256_file(built)
        if verify_reproducible:
            second_command = list(command)
            self._run(second_command, cwd=self.android_root, timeout=1800)
            second_hash = self._sha256_file(built)
            if second_hash != first_hash:
                raise AndroidDeliveryError(
                    'android.build_not_reproducible',
                    f'同输入两次 APK 哈希不同：{first_hash} != {second_hash}',
                )
        artifact = built
        if output_path is not None:
            destination = Path(output_path).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f'.{destination.name}.tmp')
            shutil.copyfile(built, temporary)
            os.replace(temporary, destination)
            artifact = destination
        evidence = self.inspect_apk(artifact, expected_application_id=application_id)
        if int(evidence['min_sdk']) != int(metadata['minimum_android_api']):
            raise AndroidDeliveryError(
                'android.minimum_api_mismatch',
                f'构建 APK minSdk={evidence["min_sdk"]}，项目要求 {metadata["minimum_android_api"]}',
            )
        missing_extension_permissions = sorted(
            set(required_manifest_permissions)
            - set(evidence['requested_permissions'])
        )
        if missing_extension_permissions:
            raise AndroidDeliveryError(
                'android.extension_permission_missing',
                '构建 APK 缺少发布闭包所需 Android 权限：'
                + '、'.join(missing_extension_permissions),
            )
        unexpected_permissions = sorted(
            set(evidence['requested_permissions'])
            - set(required_manifest_permissions)
            - {f'{application_id}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'}
        )
        if unexpected_permissions:
            raise AndroidDeliveryError(
                'android.permission_closure_mismatch',
                '构建 APK 携带发布闭包未要求的 Android 权限：'
                + '、'.join(unexpected_permissions),
            )
        if int(evidence['version_code']) != version_code:
            raise AndroidDeliveryError(
                'android.version_code_mismatch',
                f'构建 APK versionCode={evidence["version_code"]}，预期 {version_code}',
            )
        evidence.update({
            'schema_version': 1,
            'variant': variant,
            'bundle_release_id': metadata['release_id'],
            'bundle_integrity_sha256': metadata['integrity_sha256'],
            'bundle_key_id': metadata['key_id'],
            'delivery_class': 'debug_candidate' if variant.endswith('Debug') else 'release',
            'android_local_contract_status': metadata['android_local_contract_status'],
            'release_readiness': metadata['release_readiness'],
            'release_blockers': metadata['release_blockers'],
            'configured_abi_filters': (
                ['arm64-v8a', 'armeabi-v7a'] if variant.startswith('production')
                else ['x86_64']
            ),
            'abi_contract_status': (
                'native_code_declared' if evidence['declared_native_code']
                else 'architecture_neutral_jvm_candidate'
            ),
            'reproducibility_checked': bool(verify_reproducible),
            'reproducible': True if verify_reproducible else None,
            'toolchain': {
                'compile_sdk': 37,
                'target_sdk': 37,
                'min_sdk': metadata['minimum_android_api'],
                'build_tools': self.toolchain.build_tools_version,
                'gradle_user_home': str(self.toolchain.gradle_user_home.resolve()),
            },
            'minimum_webview_major': _ANDROID_MINIMUM_WEBVIEW_MAJOR,
            'extension_permissions': metadata['extension_permissions'],
            'extension_android_manifest_permissions': metadata['extension_android_manifest_permissions'],
            'required_android_manifest_permissions': required_manifest_permissions,
            'device_verification': {
                'physical_device': 'unverified',
                'accessibility_service': 'unverified',
                'media_projection': 'unverified',
                'saf_provider': 'unverified',
            },
        })
        evidence_path = artifact.with_suffix(artifact.suffix + '.evidence.json')
        self._atomic_json(evidence_path, evidence)
        evidence['evidence_path'] = str(evidence_path)
        return evidence

    def inspect_apk(self, apk_path: str | Path, *, expected_application_id: str | None = None) -> dict[str, Any]:
        self.toolchain.validate(need_gradle=True)
        apk = Path(apk_path).expanduser().resolve()
        if not apk.is_file():
            raise AndroidDeliveryError('android.apk_missing', f'APK 不存在：{apk}')
        with zipfile.ZipFile(apk, 'r') as archive:
            forbidden = [
                name for name in archive.namelist()
                if PurePosixPath(name).suffix.lower() in {'.easy', '.py', '.pyc', '.kt', '.java', '.ts', '.tsx', '.vue'}
            ]
            names = set(archive.namelist())
            if forbidden:
                raise AndroidDeliveryError('android.apk_source_leak', f'APK 包含源码文件：{forbidden[0]}')
            if 'assets/player/project.ecplayer' not in names or 'assets/player/trust-root.json' not in names:
                raise AndroidDeliveryError('android.apk_content_missing', 'APK 未内嵌签名 Player 包或信任根')
            if 'assets/player/extensions.json' not in names:
                raise AndroidDeliveryError('android.apk_content_missing', 'APK 未内嵌构建期扩展注册表')
        signature = self._run([self.toolchain.apksigner, 'verify', '--verbose', '--print-certs', apk], timeout=120)
        badging = self._run([self.toolchain.aapt2, 'dump', 'badging', apk], timeout=120)
        match = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'", badging.stdout)
        if match is None:
            raise AndroidDeliveryError('android.apk_manifest_invalid', 'aapt2 无法读取 APK package 信息')
        application_id, version_code, version_name = match.groups()
        if expected_application_id and application_id != expected_application_id:
            raise AndroidDeliveryError(
                'android.apk_application_id_mismatch',
                f'APK applicationId={application_id}，预期 {expected_application_id}',
            )
        minimum_sdk = self._minimum_sdk_from_badging(badging.stdout)
        if minimum_sdk is None:
            raise AndroidDeliveryError('android.apk_manifest_invalid', 'aapt2 无法读取 APK 最低 SDK')
        return {
            'apk_path': str(apk),
            'apk_sha256': self._sha256_file(apk),
            'apk_size': apk.stat().st_size,
            'application_id': application_id,
            'version_code': version_code,
            'version_name': version_name,
            'min_sdk': minimum_sdk,
            'signature_verified': True,
            'signature_report': '\n'.join(signature.stdout.splitlines()[-24:]),
            'source_free_scan': True,
            'declared_native_code': self._native_code_from_badging(badging.stdout),
            'requested_permissions': self._permissions_from_badging(badging.stdout),
        }

    @staticmethod
    def _minimum_sdk_from_badging(badging: str) -> int | None:
        # Build Tools 37 renamed this line from sdkVersion to
        # minSdkVersion. Accept both official spellings so inspecting an APK
        # is independent from the locally selected build-tools revision.
        match = re.search(r"^(?:sdkVersion|minSdkVersion):'(\d+)'", badging, flags=re.MULTILINE)
        return int(match.group(1)) if match is not None else None

    @staticmethod
    def _native_code_from_badging(badging: str) -> list[str]:
        match = re.search(r"^native-code:\s+(.+)$", badging, flags=re.MULTILINE)
        if match is None:
            return []
        return re.findall(r"'([^']+)'", match.group(1))

    @staticmethod
    def _permissions_from_badging(badging: str) -> list[str]:
        return sorted(set(re.findall(
            r"^uses-permission(?::\s+|-[^:]+:\s+)name='([^']+)'",
            badging,
            flags=re.MULTILINE,
        )))

    def devices(self) -> list[dict[str, str]]:
        self.toolchain.validate(need_adb=True)
        result = self._run([self.toolchain.adb, 'devices', '-l'], timeout=30)
        devices: list[dict[str, str]] = []
        for raw in result.stdout.splitlines()[1:]:
            line = raw.strip()
            if not line or line.startswith('*'):
                continue
            fields = line.split()
            if len(fields) < 2:
                continue
            details = {'serial': fields[0], 'state': fields[1]}
            for field in fields[2:]:
                if ':' in field:
                    key, value = field.split(':', 1)
                    if key in {'product', 'model', 'device', 'transport_id'}:
                        details[key] = value
            devices.append(details)
        return devices

    @staticmethod
    def _validated_serial(serial: str) -> str:
        value = str(serial or '').strip()
        if not _SERIAL.fullmatch(value):
            raise AndroidDeliveryError('android.serial_invalid', 'ADB 设备序列号格式无效')
        return value

    @staticmethod
    def _validated_package(package: str) -> str:
        value = str(package or '').strip()
        if not _PACKAGE.fullmatch(value):
            raise AndroidDeliveryError('android.package_invalid', '只允许操作 EasyCode Android Player 包')
        return value

    def _require_online(self, serial: str) -> str:
        value = self._validated_serial(serial)
        state = next((item['state'] for item in self.devices() if item['serial'] == value), '')
        if state != 'device':
            raise AndroidDeliveryError('android.device_unavailable', f'ADB 设备未在线或未授权：{value} ({state or "missing"})')
        return value

    def install(self, serial: str, apk_path: str | Path) -> dict[str, Any]:
        serial = self._require_online(serial)
        evidence = self.inspect_apk(apk_path)
        package = self._validated_package(str(evidence['application_id']))
        result = self._run([self.toolchain.adb, '-s', serial, 'install', '-r', evidence['apk_path']], timeout=300)
        if 'Success' not in result.stdout and 'Success' not in result.stderr:
            raise AndroidDeliveryError('android.install_failed', 'ADB 未返回安装成功')
        return {'installed': True, 'serial': serial, 'application_id': package, 'apk_sha256': evidence['apk_sha256']}

    def launch(self, serial: str, package: str) -> dict[str, Any]:
        serial = self._require_online(serial)
        package = self._validated_package(package)
        component = f'{package}/com.easycode.player.PlayerActivity'
        result = self._run([
            self.toolchain.adb, '-s', serial, 'shell', 'am', 'start', '-W', '-n', component,
        ], timeout=60)
        if 'Error:' in result.stdout or 'Exception' in result.stdout:
            raise AndroidDeliveryError('android.launch_failed', result.stdout.strip())
        return {'launched': True, 'serial': serial, 'application_id': package, 'component': component}

    def push_bundle(
        self,
        serial: str,
        package: str,
        bundle_path: str | Path,
        trust_root_path: str | Path,
    ) -> dict[str, Any]:
        serial = self._require_online(serial)
        package = self._validated_package(package)
        metadata = self.validate_bundle(bundle_path, trust_root_path)
        remote_root = f'/sdcard/Android/data/{package}/files/inbox'
        temporary = f'{remote_root}/.project.ecplayer.incoming'
        final = f'{remote_root}/project.ecplayer'
        self._run([self.toolchain.adb, '-s', serial, 'shell', 'mkdir', '-p', remote_root], timeout=60)
        self._run([self.toolchain.adb, '-s', serial, 'push', metadata['bundle'], temporary], timeout=300)
        self._run([self.toolchain.adb, '-s', serial, 'shell', 'mv', temporary, final], timeout=60)
        return {
            'transferred': True,
            'serial': serial,
            'application_id': package,
            'release_id': metadata['release_id'],
            'integrity_sha256': metadata['integrity_sha256'],
            'remote_path': final,
            'activation': 'next_player_start',
        }

    def logs(self, serial: str, package: str, *, lines: int = 400) -> dict[str, Any]:
        serial = self._require_online(serial)
        package = self._validated_package(package)
        count = max(1, min(int(lines), 5000))
        pid_result = self._run(
            [self.toolchain.adb, '-s', serial, 'shell', 'pidof', package], timeout=30, check=False,
        )
        pid = pid_result.stdout.strip().split()[0] if pid_result.returncode == 0 and pid_result.stdout.strip() else ''
        command: list[str | Path] = [self.toolchain.adb, '-s', serial, 'logcat', '-d', '-v', 'threadtime', '-t', str(count)]
        if pid.isdigit():
            command.extend(['--pid', pid])
        result = self._run(command, timeout=60)
        return {
            'serial': serial,
            'application_id': package,
            'pid': int(pid) if pid.isdigit() else None,
            'lines': result.stdout.splitlines()[-count:],
            'scope': 'process' if pid.isdigit() else 'device_tail_process_not_running',
        }

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, raw_temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
        temporary = Path(raw_temporary)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


android_delivery_service_v6 = AndroidDeliveryServiceV6()
