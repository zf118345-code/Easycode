"""Deterministic source-free vNext Player bundle and publication report."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .bundle_signing_v6 import (
    BUNDLE_FORMAT_V6,
    INTEGRITY_PATH,
    SIGNATURE_PATH,
    AuthorSigningKeyStore,
    BundleSignatureError,
    canonical_json_bytes,
    create_integrity_document_from_records,
    sha256_hex,
    sign_integrity_document,
    verify_signed_archive,
)
from .network_publish_v6 import NetworkPublishClosureError, network_publish_report
from .network_runtime_v6 import NetworkRuntimeV6
from .extension_schema_v6 import (
    EasyCodeLockV1,
    PublishedExtensionV1,
    resolve_package_path,
)
from .player_bindings import (
    PLAYER_TERMINAL_ACTION_SPECS,
    PlayerBindingError,
    player_terminal_action_closure,
    validate_player_form_bindings,
)
from .update_service_v6 import (
    UpdateConfigurationError,
    bundled_update_configuration,
    load_project_update_configuration,
)


class VNextPublisher:
    def __init__(
        self,
        project_path: str,
        *,
        signing_key_store: AuthorSigningKeyStore | None = None,
    ) -> None:
        self.root = Path(project_path).resolve()
        self.signing_key_store = signing_key_store or AuthorSigningKeyStore()

    @staticmethod
    def _json_bytes(value: Any) -> bytes:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
                allow_nan=False,
            )
            + '\n'
        ).encode('utf-8')

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()

    @staticmethod
    def _zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        return info

    @staticmethod
    def _with_android_requirements(
        linked: dict[str, Any],
        extension_packages: dict[str, Any] | None,
        form: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply Player-action and sealed-extension floors to final Android ECIR."""

        result = copy.deepcopy(linked)
        ecir = result.get('ecir')
        if not isinstance(ecir, dict):
            return result
        platforms = set(ecir.get('supported_platforms') or [])
        if ecir.get('target_platform') != 'android_local' and 'android_local' not in platforms:
            return result
        requirements = [
            copy.deepcopy(item)
            for item in ecir.get('android_api_requirements') or []
            if isinstance(item, dict) and item.get('kind') not in {'extension', 'player_terminal_action'}
        ]
        for action in player_terminal_action_closure(form or {}):
            if 'android_local' not in set(action.get('platforms') or []):
                continue
            action_id = str(action.get('action_id') or '')
            spec = PLAYER_TERMINAL_ACTION_SPECS.get(action_id) or {}
            floor = spec.get('minimum_android_api')
            if isinstance(floor, bool) or not isinstance(floor, int) or not 21 <= floor <= 37:
                raise ValueError(f'Player 字段动作缺少有效 Android 最低 API：{action_id}')
            if floor <= 21:
                continue
            requirements.append({
                'kind': 'player_terminal_action',
                'action_id': action_id,
                'control_id': str(action.get('control_id') or ''),
                'display_name': action_id,
                'minimum_android_api': floor,
                'statement_ids': [],
            })
        for item in (extension_packages or {}).get('packages') or []:
            package = item.get('package') or {}
            locked = item.get('lock') or {}
            floors = [
                variant.get('minimum_android_api')
                for variant in locked.get('selected_variants') or []
                if variant.get('host') == 'android_native'
                and isinstance(variant.get('minimum_android_api'), int)
                and not isinstance(variant.get('minimum_android_api'), bool)
            ]
            if not floors:
                continue
            floor = max(floors)
            # API 21 is the Android-local baseline, not an additional reason
            # that raises this particular project's generated APK floor.
            if floor <= 21:
                continue
            package_id = str(locked.get('package_id') or package.get('package_id') or '')
            requirements.append({
                'kind': 'extension',
                'package_id': package_id,
                'display_name': str(package.get('display_name') or package_id or 'Android 扩展'),
                'minimum_android_api': floor,
                'statement_ids': [],
            })
        requirements.sort(key=lambda value: (
            int(value.get('minimum_android_api') or 21),
            str(value.get('kind') or ''),
            str(value.get('contract_function_id') or value.get('package_id') or ''),
        ))
        ecir['android_api_requirements'] = requirements
        ecir['minimum_android_api'] = max([
            21,
            *(int(item.get('minimum_android_api') or 21) for item in requirements),
        ])
        return result

    @classmethod
    def _write_bytes(cls, archive: zipfile.ZipFile, name: str, content: bytes) -> None:
        archive.writestr(cls._zip_info(name), content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)

    @classmethod
    def _write_file(cls, archive: zipfile.ZipFile, name: str, source: Path) -> None:
        with source.open('rb') as input_stream, archive.open(cls._zip_info(name), 'w', force_zip64=True) as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)

    def _extension_runtime_entries(
        self, extension_packages: dict[str, Any] | None,
    ) -> tuple[dict[str, bytes], dict[str, Any]]:
        closure = extension_packages or {
            "packages": [],
            "lock": json.loads((self.root / "easycode.lock").read_text(encoding="utf-8-sig")),
        }
        if closure.get("errors"):
            raise ValueError("扩展发布闭包未通过")
        lock_value = copy.deepcopy(closure.get("lock") or {})
        locked = EasyCodeLockV1.model_validate(lock_value)
        entries: dict[str, bytes] = {}
        published_ids: set[str] = set()
        for item in closure.get("packages") or []:
            package = dict(item.get("package") or {})
            record = dict(item.get("lock") or {})
            package_id = str(record.get("package_id") or "")
            if package_id in published_ids:
                raise ValueError(f"扩展发布闭包包含重复 package_id：{package_id}")
            published_ids.add(package_id)
            root = Path(str(package.get("path") or "")).resolve()
            artifacts = {
                str((artifact.get("descriptor") or {}).get("variant_id") or ""): artifact
                for artifact in item.get("artifacts") or []
            }
            published_variants: list[dict[str, Any]] = []
            written_artifacts: set[str] = set()
            host_variants = {
                str(variant.get("variant_id") or ""): variant
                for variant in package.get("host_variants") or []
            }
            for selected in record.get("selected_variants") or []:
                variant_id = str(selected.get("variant_id") or "")
                artifact = artifacts.get(variant_id)
                declared = host_variants.get(variant_id)
                if artifact is None or declared is None:
                    raise ValueError(f"扩展缺少锁定密封变体：{package_id}/{variant_id}")
                artifact_source = resolve_package_path(root, str(artifact["path"]))
                signature_source = resolve_package_path(root, str(artifact["signature_path"]))
                artifact_bytes = artifact_source.read_bytes()
                signature_bytes = signature_source.read_bytes()
                if sha256_hex(artifact_bytes) != selected.get("artifact_sha256"):
                    raise ValueError(f"扩展密封产物与 lock 不一致：{package_id}/{variant_id}")
                if sha256_hex(signature_bytes) != selected.get("artifact_signature_sha256"):
                    raise ValueError(f"扩展密封签名与 lock 不一致：{package_id}/{variant_id}")
                base = f"runtime/extensions/{package_id}/{variant_id}"
                artifact_path = f"{base}.ecxrt"
                signature_path = f"{base}.ecxrt.sig"
                if variant_id not in written_artifacts:
                    entries[artifact_path] = artifact_bytes
                    entries[signature_path] = signature_bytes
                    written_artifacts.add(variant_id)
                published_variants.append({
                    "target": selected["target"],
                    "host": selected["host"],
                    "runtime": selected["runtime"],
                    "minimum_android_api": selected.get("minimum_android_api"),
                    "variant_id": variant_id,
                    "artifact_path": artifact_path,
                    "artifact_signature_path": signature_path,
                    "artifact_sha256": selected["artifact_sha256"],
                    "artifact_signature_sha256": selected["artifact_signature_sha256"],
                    "entrypoints": copy.deepcopy(declared.get("entrypoints") or {}),
                })
            descriptor = PublishedExtensionV1.model_validate({
                "runtime_extension_schema": 1,
                "package_id": package_id,
                "version": record["version"],
                "publisher_id": record["publisher_id"],
                "publisher_key_fingerprint": record["publisher_key_fingerprint"],
                "publisher_public_key": record["publisher_public_key"],
                "manifest_sha256": record["manifest_sha256"],
                "content_sha256": record["content_sha256"],
                "trust_mode": record["trust_mode"],
                "permissions": package.get("permissions") or [],
                "network": package.get("network") or {"level": "none", "rules": []},
                "dependencies": record.get("dependencies") or [],
                "contributions": record.get("contributions") or [],
                "function_contracts": package.get("function_contracts") or [],
                "variants": published_variants,
            })
            entries[f"runtime/extensions/{package_id}/extension.json"] = self._json_bytes(
                descriptor.model_dump(mode="json")
            )
        locked_ids = {item.package_id for item in locked.extensions}
        if published_ids != locked_ids:
            missing = sorted(locked_ids - published_ids)
            extra = sorted(published_ids - locked_ids)
            raise ValueError(f"扩展发布闭包与 easycode.lock 不一致：missing={missing}, extra={extra}")
        entries["runtime/easycode.lock"] = self._json_bytes(locked.model_dump(mode="json"))
        return entries, locked.model_dump(mode="json")

    def report(
        self, linked: dict[str, Any], form: dict[str, Any],
        extension_errors: list[dict[str, str]] | None = None,
        extension_packages: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        linked = self._with_android_requirements(linked, extension_packages, form)
        errors = [dict(item) for item in linked.get('diagnostics') or [] if item.get('severity') == 'error']
        warnings = [dict(item) for item in linked.get('diagnostics') or [] if item.get('severity') != 'error']
        for item in extension_errors or []:
            errors.append({'code': 'P2001', 'severity': 'error', 'message': item.get('message'), 'source': item.get('source')})
        dependencies: list[dict[str, Any]] = []
        extension_summary: list[dict[str, Any]] = []
        extension_permissions: set[str] = set()
        extension_network_sources: list[dict[str, Any]] = []
        for item in (extension_packages or {}).get('packages') or []:
            package = item.get('package') or {}
            locked = item.get('lock') or {}
            artifacts = item.get('artifacts') or []
            package_id = str(locked.get('package_id') or package.get('package_id') or '')
            dependencies.append({
                'package_id': package_id,
                'exact': copy.deepcopy(locked.get('dependencies') or []),
            })
            extension_permissions.update(str(value) for value in package.get('permissions') or [])
            extension_network = package.get('network') if isinstance(package.get('network'), dict) else {}
            extension_level = str(extension_network.get('level') or 'none')
            if extension_level != 'none':
                extension_network_sources.append({
                    'source': 'extension_manifest',
                    'package_id': package_id,
                    'network_level': 'lan' if extension_level == 'local_lan' else extension_level,
                    'rules': copy.deepcopy(extension_network.get('rules') or []),
                })
            if not artifacts:
                errors.append({
                    'code': 'P2004', 'severity': 'error',
                    'message': f'扩展 {package_id} 没有锁定的 ecx-runtime-1 密封运行产物',
                    'source': package.get('path'),
                })
            extension_summary.append({
                'package_id': package_id,
                'version': locked.get('version'),
                'publisher_key_fingerprint': locked.get('publisher_key_fingerprint'),
                'variants': [{
                    'variant_id': (artifact.get('descriptor') or {}).get('variant_id'),
                    'host': (artifact.get('descriptor') or {}).get('host'),
                    'targets': (artifact.get('descriptor') or {}).get('targets') or [],
                    'runtime': (artifact.get('descriptor') or {}).get('runtime'),
                    'sha256': artifact.get('sha256'),
                    'artifact_verified': True,
                    'real_host_verified': (
                        None
                        if (artifact.get('descriptor') or {}).get('host') == 'android_native'
                        else True
                    ),
                } for artifact in artifacts],
            })
        controls = [control for page in form.get('pages') or [] for control in page.get('controls') or []]
        if not controls:
            warnings.append({'code': 'P1001', 'severity': 'warning', 'message': 'Player 尚未发布任何配置控件'})
        ecir = linked.get('ecir') or {}
        extension_calls: set[str] = set()

        def collect_extension_calls(value: Any) -> None:
            if isinstance(value, list):
                for child in value:
                    collect_extension_calls(child)
                return
            if not isinstance(value, dict):
                return
            if value.get('opcode') == 'call.extension':
                extension_calls.add(str(value.get('callee_function_id') or ''))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    collect_extension_calls(child)

        collect_extension_calls(ecir.get('functions') or [])
        supported_extension_platforms = set(ecir.get('supported_platforms') or [])
        platform_requirements = {
            'windows': ('windows', 'windows'),
            'android_adb': ('windows', 'android_adb'),
            'android_local': ('android_native', 'android_native'),
            'no_target': ('windows', 'none'),
        }
        for item in (extension_packages or {}).get('packages') or []:
            package = item.get('package') or {}
            record = item.get('lock') or {}
            contracts = {
                str(contract.get('function_id') or ''): contract
                for contract in package.get('function_contracts') or []
            }
            selected = list(record.get('selected_variants') or [])
            for function_id in sorted(extension_calls & set(contracts)):
                contract_targets = set(contracts[function_id].get('targets') or [])
                for platform in sorted(supported_extension_platforms & set(platform_requirements)):
                    host, preferred_target = platform_requirements[platform]
                    target = preferred_target if preferred_target in contract_targets else (
                        'none' if 'none' in contract_targets else ''
                    )
                    if not target:
                        errors.append({
                            'code': 'P2005', 'severity': 'error',
                            'message': f'扩展函数 {function_id} 不支持发布平台 {platform}',
                            'source': function_id,
                        })
                        continue
                    compatible = next((
                        variant for variant in selected
                        if variant.get('host') == host
                        and variant.get('target') == target
                        and variant.get('artifact_sha256')
                        and variant.get('artifact_signature_sha256')
                    ), None)
                    if compatible is None:
                        errors.append({
                            'code': 'P2006', 'severity': 'error',
                            'message': (
                                f'扩展函数 {function_id} 缺少 {platform} 的'
                                '已签名 ecx-runtime-1 密封宿主变体'
                            ),
                            'source': str(package.get('path') or function_id),
                        })
        try:
            network_report = network_publish_report(ecir)
        except NetworkPublishClosureError as exc:
            network_report = {
                'schema_version': 1,
                'network_level': 'invalid',
                'sources': [],
                'calls': [],
                'file_permissions': [],
                'warnings': [],
            }
            errors.append({
                'code': 'P2201',
                'severity': 'error',
                'message': str(exc),
                'source': 'runtime/ecir.json',
            })
        network_report['sources'].extend(extension_network_sources)
        network_report['sources'] = sorted(
            network_report['sources'],
            key=lambda item: (
                str(item.get('network_level') or ''),
                str(item.get('package_id') or ''),
                str(item.get('rule_id') or ''),
            ),
        )
        if any(item.get('network_level') == 'public' for item in extension_network_sources):
            network_report['network_level'] = 'public'
        elif extension_network_sources and network_report['network_level'] == 'none':
            network_report['network_level'] = 'lan'
        required_capabilities = {
            str(item) for item in ecir.get('required_capabilities') or []
        }
        for call in network_report['calls']:
            if not NetworkRuntimeV6.supports(str(call.get('opcode') or '')):
                errors.append({
                    'code': 'P2202',
                    'severity': 'error',
                    'message': f'网络调用缺少运行适配器：{call.get("opcode")}',
                    'source': call.get('statement_id'),
                })
        missing_network_permissions = (
            ({'network'} if network_report['calls'] else set())
            | set(network_report['file_permissions'])
        ) - required_capabilities
        if missing_network_permissions:
            errors.append({
                'code': 'P2203',
                'severity': 'error',
                'message': (
                    '网络调用的发布权限闭包不完整：'
                    + '、'.join(sorted(missing_network_permissions))
                ),
                'source': 'runtime/ecir.json',
            })
        warnings.extend({
            **item,
            'severity': 'warning',
            'source': 'runtime/ecir.json',
        } for item in network_report['warnings'])
        functions = {
            str(item.get('function_id') or ''): item
            for item in ecir.get('functions') or [] if item.get('function_id')
        }
        function_parameter_bindings: dict[str, set[str]] = {}
        supported_platforms = set(ecir.get('supported_platforms') or [])
        raw_android_api = ecir.get('minimum_android_api')
        android_build_declared = (
            ecir.get('target_platform') == 'android_local'
            or 'android_local' in supported_platforms
        )
        if android_build_declared and (
            isinstance(raw_android_api, bool)
            or not isinstance(raw_android_api, int)
            or not 21 <= raw_android_api <= 37
        ):
            errors.append({
                'code': 'P2301',
                'severity': 'error',
                'message': '运行产物缺少有效的 Android 最低 API（必须为 21..37）',
                'source': 'runtime/ecir.json',
            })
            minimum_android_api = 21
        elif isinstance(raw_android_api, int) and not isinstance(raw_android_api, bool):
            minimum_android_api = raw_android_api
        else:
            minimum_android_api = 21
        publish_targets = list(ecir.get('targets') or [])
        project_manifest = self.root / 'project.json'
        if project_manifest.is_file():
            try:
                stored_project = json.loads(project_manifest.read_text(encoding='utf-8-sig'))
                publish_targets = list(stored_project.get('targets') or publish_targets)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                # The workspace/publish service reports a corrupt manifest at
                # its own boundary; binding validation still uses the linked
                # target closure and never invents a target.
                pass
        try:
            validate_player_form_bindings(
                ecir,
                form,
                targets=publish_targets,
            )
        except PlayerBindingError as exc:
            errors.append({
                'code': exc.code,
                'severity': 'error',
                'message': str(exc),
                'source': 'player/form.json',
            })
        terminal_actions = player_terminal_action_closure(form)
        terminal_capabilities = sorted({
            str(item['capability']) for item in terminal_actions
        })
        for control in controls:
            label = str(control.get('label') or control.get('control_id') or '未命名控件')
            binding = control.get('binding') if isinstance(control.get('binding'), dict) else {}
            if binding.get('kind') == 'function_parameter':
                function_id = str(binding.get('function_id') or '')
                parameter_id = str(binding.get('parameter_id') or '')
                function_parameter_bindings.setdefault(function_id, set()).add(parameter_id)
            declared_platforms = {str(item) for item in control.get('platforms') or [] if str(item)}
            if declared_platforms and supported_platforms and not declared_platforms.intersection(supported_platforms):
                errors.append({'code': 'P2105', 'severity': 'error', 'message': f'Player 控件“{label}”不支持项目的目标平台'})
        invokable_function_ids = {str(ecir.get('entry_function_id') or '')}
        invokable_function_ids.update(
            str((control.get('binding') or {}).get('function_id') or '')
            for control in controls if (control.get('binding') or {}).get('kind') == 'function_action'
        )
        for function_id in invokable_function_ids:
            function = functions.get(function_id)
            if function is None:
                continue
            covered = function_parameter_bindings.get(function_id, set())
            missing = [
                str(item.get('display_name') or item.get('parameter_id') or '')
                for item in function.get('parameter_definitions') or []
                if item.get('required', True)
                and item.get('default') is None
                and str(item.get('parameter_id') or '') not in covered
            ]
            if missing:
                errors.append({
                    'code': 'P2110', 'severity': 'error',
                    'message': f'Player 可执行函数“{function.get("name") or function_id}”缺少必填参数控件：{"、".join(missing)}',
                })
        published_capabilities = sorted(
            required_capabilities | set(terminal_capabilities) | extension_permissions
        )
        try:
            project_id = str(stored_project.get('project_id') or '') if 'stored_project' in locals() else ''
            update_configuration = load_project_update_configuration(
                self.root, project_id=project_id,
            )
            update_domains = {
                domain: {
                    'enabled': bool(value['enabled']),
                    'provider': value['provider'] if value['enabled'] else None,
                    'channel': value['channel'] if value['enabled'] else None,
                    'required_policy_capability': bool(value['required_policy_capability']),
                }
                for domain, value in update_configuration['domains'].items()
            }
        except UpdateConfigurationError as exc:
            errors.append({
                'code': exc.code,
                'severity': 'error',
                'message': str(exc),
                'source': 'updates.json',
            })
            update_domains = {}
        updates_enabled = any(item.get('enabled') for item in update_domains.values())
        return {
            'valid': not errors, 'errors': errors, 'warnings': warnings,
            'source_included': False, 'player_pages': len(form.get('pages') or []),
            'player_controls': len(controls),
            'required_capabilities': published_capabilities,
            'player_terminal_actions': terminal_actions,
            'player_terminal_capabilities': terminal_capabilities,
            'network': network_report,
            'network_level': network_report['network_level'],
            'network_sources': network_report['sources'],
            'supported_platforms': list(ecir.get('supported_platforms') or []),
            'android_build_declared': android_build_declared,
            'minimum_android_api': minimum_android_api,
            'android_api_requirements': list(ecir.get('android_api_requirements') or []),
            # Runtime verification is promoted only after the corresponding
            # real-host Harness. Compilability/support must never be treated
            # as proof that a packaged Player passed device acceptance.
            'verified_platforms': [],
            'contains_native_extensions': bool(extension_summary),
            'extension_dependencies': dependencies,
            'extension_permissions': sorted(extension_permissions),
            'extensions': extension_summary,
            'online_maintenance': {
                'updates_enabled': updates_enabled,
                'domains': update_domains,
                'task_execution_requires_network': False,
                'automatic_telemetry': False,
                'disclosure': (
                    '任务本身可离线运行；已缓存的签名强制更新策略可能在宽限结束后阻止旧版本开始新任务。'
                    if any(item.get('required_policy_capability') for item in update_domains.values())
                    else '更新检查属于独立在线维护服务，不改变任务运行网络等级。'
                ) if updates_enabled else '未启用在线更新；发布包不包含更新端点、调度器或更新入口。',
            },
        }

    def build(
        self, linked: dict[str, Any], form: dict[str, Any], project: dict[str, Any],
        report: dict[str, Any], *, extension_packages: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        linked = self._with_android_requirements(linked, extension_packages, form)
        if not report.get('valid') or not linked.get('ecir'):
            raise ValueError('发布检查未通过')
        if report.get('android_build_declared') and (
            report.get('minimum_android_api') != linked['ecir'].get('minimum_android_api')
            or report.get('android_api_requirements', []) != linked['ecir'].get('android_api_requirements', [])
        ):
            raise ValueError('发布报告与 Android 最低版本闭包不一致')
        product_id = str(project.get('project_id') or '').strip()
        if not product_id:
            raise ValueError('项目缺少稳定 project_id，不能发布')
        try:
            signing_identity = self.signing_key_store.get_or_create(product_id)
        except BundleSignatureError as exc:
            raise ValueError(str(exc)) from exc
        destination_dir = self.root / 'dist'
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = ''.join(character if character.isalnum() or character in {'-', '_'} else '_' for character in str(project.get('name') or 'EasyCode'))
        destination = destination_dir / f'{safe_name}.ecplayer'
        descriptor, temporary_name = tempfile.mkstemp(prefix='.publish-', suffix='.zip', dir=destination_dir)
        os.close(descriptor)
        temporary = Path(temporary_name)
        ecir = copy.deepcopy(linked['ecir'])
        ecir['project_path'] = '.'
        runtime_project = {
            'project_id': product_id,
            'name': project.get('name'),
            'targets_schema_version': project.get('targets_schema_version', 1),
            'targets': copy.deepcopy(project.get('targets') or []),
            'default_target_id': project.get('default_target_id'),
            'target_configuration_revision': project.get(
                'target_configuration_revision'
            ),
        }
        entries: dict[str, bytes] = {
            'runtime/ecir.json': self._json_bytes(ecir),
            'runtime/project.json': self._json_bytes(runtime_project),
            'player/form.json': self._json_bytes(form),
            'publish-report.json': self._json_bytes(report),
        }
        update_configuration = load_project_update_configuration(self.root, project_id=product_id)
        bundled_updates = bundled_update_configuration(update_configuration)
        if bundled_updates is not None:
            entries['update/config.json'] = self._json_bytes(bundled_updates)
        extension_entries, runtime_lock = self._extension_runtime_entries(extension_packages)
        entries.update(extension_entries)
        asset_files: list[tuple[str, Path]] = []
        assets_root = self.root / 'assets'
        if assets_root.is_dir():
            resolved_assets_root = assets_root.resolve()
            for path in sorted(assets_root.rglob('*')):
                if path.is_symlink():
                    raise ValueError(f'资源目录不允许符号链接：{path.relative_to(self.root)}')
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved_assets_root != resolved.parent and resolved_assets_root not in resolved.parents:
                    raise ValueError(f'资源文件越出项目资源目录：{path}')
                asset_files.append((path.relative_to(self.root).as_posix(), path))

        content_records = [
            {'path': name, 'size': len(content), 'sha256': sha256_hex(content)}
            for name, content in entries.items()
        ]
        for name, path in asset_files:
            size, digest = self._hash_file(path)
            content_records.append({'path': name, 'size': size, 'sha256': digest})
        release_seed = canonical_json_bytes(sorted(content_records, key=lambda item: item['path']))
        release_id = f'release_{sha256_hex(release_seed)[:32]}'
        manifest = {
            'bundle_format': BUNDLE_FORMAT_V6,
            'product': 'EasyCode Player',
            'project_id': product_id,
            'release_id': release_id,
            'name': project.get('name'),
            'minimum_runtime_version': project.get('minimum_runtime_version', '5.0.0'),
            'entry_function_id': ecir.get('entry_function_id'),
            'source_included': False,
            'signing_key_id': signing_identity.key_id,
            'easycode_lock_sha256': sha256_hex(entries['runtime/easycode.lock']),
            'extension_package_count': len(runtime_lock.get('extensions') or []),
        }
        entries['manifest.json'] = self._json_bytes(manifest)
        integrity_records = [
            {'path': name, 'size': len(content), 'sha256': sha256_hex(content)}
            for name, content in entries.items()
        ]
        asset_record_by_path = {
            str(item['path']): item
            for item in content_records
            if str(item['path']).startswith('assets/')
        }
        integrity_records.extend(
            asset_record_by_path[name]
            for name, _path in asset_files
        )
        integrity = create_integrity_document_from_records(integrity_records)
        signature = sign_integrity_document(integrity, signing_identity)
        entries[INTEGRITY_PATH] = self._json_bytes(integrity)
        entries[SIGNATURE_PATH] = self._json_bytes(signature)
        included: list[str] = sorted([*entries, *(name for name, _path in asset_files)])
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for name in sorted(entries):
                    self._write_bytes(archive, name, entries[name])
                for name, path in asset_files:
                    self._write_file(archive, name, path)
            # External tools may still change an asset while the project lock
            # is held.  Verify the exact temporary archive before replacing the
            # last known-good output; a torn build is never made discoverable.
            with zipfile.ZipFile(temporary, 'r') as archive:
                verify_signed_archive(archive, signing_identity.public_key_bytes)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            'created': True,
            'path': str(destination),
            'size': destination.stat().st_size,
            'included_files': included,
            'release_id': release_id,
            'signature': {
                'algorithm': signature['algorithm'],
                'key_id': signature['key_id'],
                'public_key': signature['public_key'],
                'integrity_sha256': signature['signed_sha256'],
            },
            'report': report,
        }
