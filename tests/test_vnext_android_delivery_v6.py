from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.vnext.android_delivery_v6 import (
    _ANDROID_OPCODES,
    AndroidDeliveryError,
    AndroidDeliveryServiceV6,
    AndroidToolchainV6,
)
from core.vnext.bundle_signing_v6 import (
    AuthorSigningIdentity,
    canonical_json_bytes,
    public_key_id,
    sign_entries,
    trust_root_document,
)
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.pure_operations_v6 import (
    PURE_OPERATION_REGISTRY_VERSION,
    pure_operation_registry_hash,
)


def _bundle(
    tmp_path: Path,
    *,
    opcode: str = 'log.write',
    extensions=(),
    registry_version: int = PURE_OPERATION_REGISTRY_VERSION,
    program_model_version: int = 1,
    supported_platforms: tuple[str, ...] = ('android_adb', 'no_target', 'windows'),
    verified_platforms: tuple[str, ...] = (),
    minimum_android_api: int = 21,
    android_api_requirements=(),
    instruction_capabilities=(),
    report_required_capabilities=(),
    manifest_overrides: dict | None = None,
    extra_entries: dict[str, bytes] | None = None,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    identity = AuthorSigningIdentity('project.android', public_key_id(public), private, public)
    entries = {
        'manifest.json': canonical_json_bytes({
            'bundle_format': 2,
            'project_id': 'project.android',
            'release_id': 'release.android.1',
            'source_included': False,
        }),
        'runtime/ecir.json': canonical_json_bytes({
            'ecir_version': 1,
            'program_model_version': program_model_version,
            'pure_operation_registry': {
                'registry_version': registry_version,
                'content_hash': pure_operation_registry_hash(),
            },
            'entry_function_id': 'function.main',
            'minimum_android_api': minimum_android_api,
            'android_api_requirements': list(android_api_requirements),
            'functions': [{
                'function_id': 'function.main',
                'instructions': [{
                    'instruction_id': 'statement.main',
                    'opcode': opcode,
                    'arguments': {},
                    'capabilities': list(instruction_capabilities),
                }],
            }],
        }),
        'runtime/project.json': canonical_json_bytes({
            'targets_schema_version': 1,
            'targets': [{
                'target_id': 'target.android', 'name': '本机', 'type': 'android_local',
            }],
            'default_target_id': 'target.android',
        }),
        'runtime/easycode.lock': canonical_json_bytes({
            'lock_version': 1,
            'project_format': 6,
            'toolchain': {
                'compiler_version': '6.0.0',
                'program_schema': 1,
                'ecir': 1,
                'pure_value_registry_version': registry_version,
                'pure_value_registry_sha256': pure_operation_registry_hash(),
            },
            'official_functions': [],
            'extensions': list(extensions),
        }),
        'player/form.json': canonical_json_bytes({
            'schema_version': 3, 'title': 'Android', 'pages': [],
        }),
        'publish-report.json': canonical_json_bytes({
            'valid': True,
            'source_included': False,
            'supported_platforms': list(supported_platforms),
            'verified_platforms': list(verified_platforms),
            'extensions': [],
            'minimum_android_api': minimum_android_api,
            'android_api_requirements': list(android_api_requirements),
            'player_terminal_actions': [],
            'player_terminal_capabilities': [],
            'required_capabilities': list(report_required_capabilities),
        }),
    }
    entries.update(extra_entries or {})
    manifest = json.loads(entries['manifest.json'])
    manifest.update({
        'signing_key_id': identity.key_id,
        'easycode_lock_sha256': hashlib.sha256(entries['runtime/easycode.lock']).hexdigest(),
        'extension_package_count': len(extensions),
    })
    manifest.update(manifest_overrides or {})
    entries['manifest.json'] = canonical_json_bytes(manifest)
    integrity, envelope = sign_entries(entries, identity)
    bundle = tmp_path / 'project.ecplayer'
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
        archive.writestr('META-INF/integrity.json', canonical_json_bytes(integrity))
        archive.writestr('META-INF/signature.json', canonical_json_bytes(envelope))
    trust = tmp_path / 'trust-root.json'
    trust.write_bytes(canonical_json_bytes(trust_root_document(envelope, 'project.android')))
    return bundle, trust


def test_android_preflight_accepts_only_signed_source_free_supported_bundle(tmp_path: Path) -> None:
    bundle, trust = _bundle(tmp_path)
    service = AndroidDeliveryServiceV6(tmp_path)

    result = service.validate_bundle(bundle, trust)

    assert result['release_id'] == 'release.android.1'
    assert result['extension_count'] == 0
    assert result['integrity_sha256']
    assert result['android_local_contract_status'] == 'planned'
    assert result['verified_platforms'] == []
    assert result['release_readiness'] == 'blocked_physical_device_harness'
    assert result['release_blockers'] == [
        'disconnected_physical_device_harness',
        'native_abi_closure_unverified',
    ]
    assert result['application_updates_enabled'] is False


def test_android_preflight_recomputes_capabilities_instead_of_trusting_report(tmp_path: Path) -> None:
    bundle, trust = _bundle(
        tmp_path,
        instruction_capabilities=('network',),
        report_required_capabilities=(),
    )

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.publish_report_invalid'


def test_android_preflight_rejects_signed_bundle_with_incomplete_release_identity(tmp_path: Path) -> None:
    bundle, trust = _bundle(tmp_path, manifest_overrides={'signing_key_id': ''})

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.bundle_manifest_invalid'


def test_android_application_update_permission_is_derived_from_signed_bundle(tmp_path: Path) -> None:
    update_config = canonical_json_bytes({
        'schema_version': 1,
        'protocol': 'easycode-update-feed',
        'telemetry': False,
        'domains': {
            'player_application': {
                'product_id': 'player.android',
                'channel': 'stable',
                'feed_base_url': 'https://updates.example.test/player/',
                'required_policy_capability': False,
                'pinned_root': {},
                'initial_preferences': {},
            },
        },
    })
    bundle, trust = _bundle(tmp_path, extra_entries={'update/config.json': update_config})

    result = AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert result['application_updates_enabled'] is True


def test_android_support_declaration_does_not_impersonate_real_device_verification(tmp_path: Path) -> None:
    bundle, trust = _bundle(
        tmp_path,
        supported_platforms=('android_local',),
    )

    result = AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert result['supported_platforms'] == ['android_local']
    assert result['verified_platforms'] == []
    assert result['android_local_contract_status'] == 'planned'
    assert result['release_readiness'] == 'blocked_physical_device_harness'


def test_android_verified_platform_must_also_be_supported(tmp_path: Path) -> None:
    bundle, trust = _bundle(
        tmp_path,
        verified_platforms=('android_local',),
    )

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.publish_report_invalid'


def test_android_preflight_fails_closed_for_extensions_and_unknown_operations(tmp_path: Path) -> None:
    extension_bundle, extension_trust = _bundle(
        tmp_path / 'extension',
        extensions=({'package_id': 'vendor.fake', 'version': '1.0.0'},),
    )
    service = AndroidDeliveryServiceV6(tmp_path)
    with pytest.raises(AndroidDeliveryError) as extension_error:
        service.validate_bundle(extension_bundle, extension_trust)
    assert extension_error.value.code == 'android.extension_invalid'
    assert extension_error.value.diagnostics == []

    unknown_bundle, unknown_trust = _bundle(tmp_path / 'unknown', opcode='network.http_request')
    with pytest.raises(AndroidDeliveryError) as operation_error:
        service.validate_bundle(unknown_bundle, unknown_trust)
    assert operation_error.value.code == 'android.operation_unsupported'


def test_android_extension_floor_must_match_signed_project_requirement_closure(tmp_path: Path) -> None:
    extension = {
        'package_id': 'vendor.android',
        'version': '1.0.0',
        'selected_variants': [{
            'target': 'android_native',
            'host': 'android_native',
            'runtime': 'android-kotlin-v1',
            'variant_id': 'android.api28',
            'minimum_android_api': 28,
        }],
    }
    bundle, trust = _bundle(tmp_path / 'mismatch', extensions=(extension,))

    with pytest.raises(AndroidDeliveryError) as mismatch:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert mismatch.value.code == 'android.minimum_api_invalid'

    requirement = {
        'kind': 'extension',
        'package_id': 'vendor.android',
        'display_name': 'Android 扩展',
        'minimum_android_api': 28,
        'statement_ids': [],
    }
    matched_bundle, matched_trust = _bundle(
        tmp_path / 'matched',
        extensions=(extension,),
        minimum_android_api=28,
        android_api_requirements=(requirement,),
    )
    with pytest.raises(AndroidDeliveryError) as unavailable:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(matched_bundle, matched_trust)
    assert unavailable.value.code == 'android.extension_invalid'


def test_android_api21_extension_does_not_create_redundant_raise_requirement(tmp_path: Path) -> None:
    extension = {
        'package_id': 'vendor.android21',
        'version': '1.0.0',
        'selected_variants': [{
            'target': 'android_native',
            'host': 'android_native',
            'runtime': 'android-kotlin-v1',
            'variant_id': 'android.api21',
            'minimum_android_api': 21,
        }],
    }
    bundle, trust = _bundle(tmp_path, extensions=(extension,))

    with pytest.raises(AndroidDeliveryError) as unavailable:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert unavailable.value.code == 'android.extension_invalid'


@pytest.mark.parametrize('opcode', [
    'text.recognize',
    'standard.text.match',
    'standard.text.wait_visible',
])
def test_android_preflight_accepts_offline_ocr_runtime_operations(
    tmp_path: Path,
    opcode: str,
) -> None:
    bundle, trust = _bundle(tmp_path / opcode.replace('.', '-'), opcode=opcode)

    result = AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert result['release_id'] == 'release.android.1'


def test_android_preflight_rejects_stale_registry_lock_before_build(tmp_path: Path) -> None:
    bundle, trust = _bundle(tmp_path, registry_version=4)

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.registry_incompatible'


def test_android_preflight_rejects_incompatible_program_model_before_build(tmp_path: Path) -> None:
    bundle, trust = _bundle(tmp_path, program_model_version=0)

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.ecir_incompatible'


def test_android_preflight_rejects_even_signed_source_or_edit_projection(tmp_path: Path) -> None:
    bundle, trust = _bundle(
        tmp_path,
        extra_entries={'program/functions/source.json': b'{"editable":true}'},
    )

    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6(tmp_path).validate_bundle(bundle, trust)

    assert captured.value.code == 'android.source_isolation_failed'


def test_release_signing_has_no_repository_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        'EASYCODE_ANDROID_RELEASE_STORE_FILE',
        'EASYCODE_ANDROID_RELEASE_STORE_PASSWORD',
        'EASYCODE_ANDROID_RELEASE_KEY_ALIAS',
        'EASYCODE_ANDROID_RELEASE_KEY_PASSWORD',
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(AndroidDeliveryError) as captured:
        AndroidDeliveryServiceV6._release_signing_properties()
    assert captured.value.code == 'android.release_signing_missing'


def test_planned_android_contract_blocks_release_before_gradle_or_signing(tmp_path: Path) -> None:
    bundle, trust = _bundle(tmp_path / 'bundle')
    sdk = tmp_path / 'sdk'
    java_home = tmp_path / 'jdk'
    gradle_home = tmp_path / 'gradle'
    for path in (
        java_home / 'bin' / 'java.exe',
        gradle_home / 'bin' / 'gradle.bat',
        sdk / 'platforms' / 'android-37.0' / 'android.jar',
        sdk / 'build-tools' / '37.0.0' / 'apksigner.bat',
        sdk / 'build-tools' / '37.0.0' / 'aapt2.exe',
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
    calls: list[list[str]] = []

    def runner(argv, **_kwargs):
        calls.append(list(argv))
        raise AssertionError('release readiness should reject before executing Gradle')

    service = AndroidDeliveryServiceV6(
        tmp_path,
        toolchain=AndroidToolchainV6(
            java_home=java_home,
            sdk_root=sdk,
            gradle_home=gradle_home,
            gradle_user_home=tmp_path / 'gradle-cache',
        ),
        runner=runner,
    )

    with pytest.raises(AndroidDeliveryError) as captured:
        service.build(bundle, trust, variant='productionRelease')

    assert captured.value.code == 'android.release_readiness_blocked'
    assert calls == []


def test_adb_bridge_uses_explicit_serial_and_reports_real_device_state(tmp_path: Path) -> None:
    sdk = tmp_path / 'sdk'
    adb = sdk / 'platform-tools' / 'adb.exe'
    adb.parent.mkdir(parents=True)
    adb.write_bytes(b'')
    calls: list[list[str]] = []

    def runner(argv, **_kwargs):
        calls.append(list(argv))
        if argv[-2:] == ['devices', '-l']:
            return subprocess.CompletedProcess(
                argv, 0,
                'List of devices attached\nSERIAL-1 device product:p model:Pixel_9 device:test transport_id:4\n'
                'SERIAL-2 unauthorized usb:1-1\n',
                '',
            )
        if 'am' in argv:
            return subprocess.CompletedProcess(argv, 0, 'Status: ok\n', '')
        raise AssertionError(argv)

    toolchain = AndroidToolchainV6(
        java_home=tmp_path / 'jdk',
        sdk_root=sdk,
        gradle_home=tmp_path / 'gradle',
        gradle_user_home=tmp_path / 'gradle-cache',
    )
    service = AndroidDeliveryServiceV6(tmp_path, toolchain=toolchain, runner=runner)

    assert service.devices() == [
        {
            'serial': 'SERIAL-1', 'state': 'device', 'product': 'p',
            'model': 'Pixel_9', 'device': 'test', 'transport_id': '4',
        },
        {'serial': 'SERIAL-2', 'state': 'unauthorized'},
    ]
    launched = service.launch('SERIAL-1', 'com.easycode.player.debug')
    assert launched['component'] == (
        'com.easycode.player.debug/com.easycode.player.PlayerActivity'
    )
    assert any(call[:3] == [str(adb), '-s', 'SERIAL-1'] for call in calls)
    with pytest.raises(AndroidDeliveryError, match='序列号格式无效'):
        service.launch('SERIAL-1; rm -rf /', 'com.easycode.player.debug')


def test_toolchain_environment_keeps_gradle_cache_on_configured_drive(tmp_path: Path) -> None:
    cache = tmp_path / 'gradle-cache'
    toolchain = AndroidToolchainV6(
        java_home=tmp_path / 'jdk',
        sdk_root=tmp_path / 'sdk',
        gradle_home=tmp_path / 'gradle',
        gradle_user_home=cache,
    )
    environment = toolchain.environment()
    assert environment['GRADLE_USER_HOME'] == str(cache.resolve())
    assert environment['JAVA_HOME'] == str((tmp_path / 'jdk').resolve())


def test_android_runtime_registry_identity_matches_python_lock_contract() -> None:
    source = (
        Path(__file__).parents[1]
        / 'android/app/src/main/java/com/easycode/player/bundle/RuntimeRegistryContract.kt'
    ).read_text(encoding='utf-8')
    version = re.search(r'const val VERSION = (\d+)', source)
    content_hash = re.search(r'const val CONTENT_HASH = "([0-9a-f]{64})"', source)

    assert version and int(version.group(1)) == PURE_OPERATION_REGISTRY_VERSION == 10
    assert content_hash and content_hash.group(1) == pure_operation_registry_hash()


@pytest.mark.parametrize('label', ['sdkVersion', 'minSdkVersion'])
def test_android_apk_inspector_accepts_build_tools_min_sdk_labels(label: str) -> None:
    assert AndroidDeliveryServiceV6._minimum_sdk_from_badging(
        f"package: name='com.easycode.player.debug' versionCode='1' versionName='6.0.0'\n"
        f"{label}:'24'\n"
    ) == 24


def test_android_apk_inspector_collects_unique_requested_permissions() -> None:
    badging = (
        "uses-permission: name='android.permission.INTERNET'\n"
        "uses-permission-sdk-23: name='android.permission.POST_NOTIFICATIONS'\n"
        "uses-permission: name='android.permission.INTERNET'\n"
    )

    assert AndroidDeliveryServiceV6._permissions_from_badging(badging) == [
        'android.permission.INTERNET',
        'android.permission.POST_NOTIFICATIONS',
    ]


def test_android_manifest_permissions_follow_published_capability_closure() -> None:
    pure = AndroidDeliveryServiceV6._required_android_manifest_permissions({
        'required_capabilities': [],
        'extension_android_manifest_permissions': [],
        'application_updates_enabled': False,
    })
    assert 'android.permission.INTERNET' not in pure
    assert 'android.permission.SYSTEM_ALERT_WINDOW' not in pure
    assert 'android.permission.FOREGROUND_SERVICE' in pure

    updater = AndroidDeliveryServiceV6._required_android_manifest_permissions({
        'required_capabilities': [],
        'extension_android_manifest_permissions': [],
        'application_updates_enabled': True,
    })
    assert 'android.permission.INTERNET' in updater
    assert 'android.permission.REQUEST_INSTALL_PACKAGES' in updater

    interactive = AndroidDeliveryServiceV6._required_android_manifest_permissions({
        'required_capabilities': ['messaging', 'target.frame.read'],
        'extension_android_manifest_permissions': ['android.permission.CAMERA'],
        'application_updates_enabled': False,
    })
    assert {
        'android.permission.INTERNET',
        'android.permission.ACCESS_WIFI_STATE',
        'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION',
        'android.permission.SYSTEM_ALERT_WINDOW',
        'android.permission.CAMERA',
    } <= set(interactive)


def test_generated_android_manifest_removes_dependency_permissions_outside_closure(tmp_path: Path) -> None:
    manifest = tmp_path / 'android/app/src/main/AndroidManifest.xml'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '  <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />\n'
        '  <uses-permission android:name="android.permission.INTERNET" />\n'
        '  <application />\n'
        '</manifest>\n',
        encoding='utf-8',
    )
    generated, required = AndroidDeliveryServiceV6(tmp_path)._prepare_android_manifest_input({
        'required_capabilities': [],
        'extension_android_manifest_permissions': [],
        'application_updates_enabled': False,
    })
    text = generated.read_text(encoding='utf-8')

    assert 'android.permission.FOREGROUND_SERVICE' in required
    assert 'android.permission.INTERNET' not in required
    assert 'android.permission.INTERNET' in text
    assert 'tools:node="remove"' in text


def test_android_ocr_is_bundled_and_both_preflight_layers_accept_same_operations() -> None:
    repository = Path(__file__).parents[1]
    gradle = (repository / 'android/app/build.gradle.kts').read_text(encoding='utf-8')
    kotlin_preflight = (
        repository
        / 'android/app/src/main/java/com/easycode/player/bundle/AndroidPackagePreflight.kt'
    ).read_text(encoding='utf-8')
    expected = {
        'text.recognize',
        'standard.text.match',
        'standard.text.wait_visible',
    }

    assert 'com.google.mlkit:text-recognition-chinese:16.0.1' in gradle
    assert 'play-services-mlkit-text-recognition' not in gradle
    assert expected <= _ANDROID_OPCODES
    assert all(f'"{opcode}"' in kotlin_preflight for opcode in expected)


def test_android_visual_action_results_match_the_shared_record_contract() -> None:
    repository = Path(__file__).parents[1]
    host = (
        repository
        / 'android/app/src/main/java/com/easycode/player/runtime/AndroidPlatformHost.kt'
    ).read_text(encoding='utf-8')

    assert '"standard.image.click_position_until_visible"' in host
    assert '"standard.image.click_position_until_hidden"' in host
    assert '"image_click_loop_result.field.clicks"' not in host
    assert '"image_click_loop_result.field.click_count"' in host
    for field_id in (
        'image_click_condition_result.field.reached',
        'image_click_condition_result.field.click_count',
        'image_click_condition_result.field.last_match',
    ):
        assert f'"{field_id}"' in host


def test_every_android_supported_official_opcode_is_accepted_by_both_preflight_layers() -> None:
    repository = Path(__file__).parents[1]
    kotlin_preflight = (
        repository
        / 'android/app/src/main/java/com/easycode/player/bundle/AndroidPackagePreflight.kt'
    ).read_text(encoding='utf-8')
    supported_block = kotlin_preflight.split(
        'private val supportedOpcodes = setOf(', 1
    )[1].split('\n    )', 1)[0]
    kotlin_opcodes = set(re.findall(r'"([a-z][a-z0-9_.]+)"', supported_block))
    expected = {
        function['opcode']
        for function in official_function_registry_v6.complete_catalog()
        if next(
            item for item in function['platform_support']
            if item['platform'] == 'android_local'
        )['support'] != 'unsupported'
    }

    assert expected <= _ANDROID_OPCODES
    assert expected <= kotlin_opcodes
    assert set(_ANDROID_OPCODES) == kotlin_opcodes


def test_android_local_does_not_publish_guaranteed_failure_wait_exit() -> None:
    contract = official_function_registry_v6.require('official.application.wait_exit')
    matrix = {item.platform: item.support for item in contract.platform_support}
    assert matrix['windows'] != 'unsupported'
    assert matrix['android_adb'] != 'unsupported'
    assert matrix['android_local'] == 'unsupported'
    assert 'host.app.wait_exit' not in _ANDROID_OPCODES


def test_android_player_keeps_shared_web_draft_across_responsive_rotation() -> None:
    manifest = (
        Path(__file__).parents[1]
        / 'android/app/src/main/AndroidManifest.xml'
    ).read_text(encoding='utf-8')

    activity = re.search(
        r'<activity\s+android:name="\.PlayerActivity"(?P<body>.*?)>',
        manifest,
        flags=re.DOTALL,
    )
    assert activity is not None
    config = re.search(r'android:configChanges="([^"]+)"', activity.group('body'))
    assert config is not None
    handled = set(config.group(1).split('|'))
    assert {
        'fontScale',
        'keyboardHidden',
        'orientation',
        'screenLayout',
        'screenSize',
        'smallestScreenSize',
    } <= handled


def test_android_manifest_can_discover_normal_launcher_apps_without_broad_package_access() -> None:
    manifest = (
        Path(__file__).parents[1]
        / 'android/app/src/main/AndroidManifest.xml'
    ).read_text(encoding='utf-8')
    queries = re.search(r'<queries>(?P<body>.*?)</queries>', manifest, flags=re.DOTALL)
    assert queries is not None
    assert 'android.intent.action.MAIN' in queries.group('body')
    assert 'android.intent.category.LAUNCHER' in queries.group('body')
    assert 'android.permission.QUERY_ALL_PACKAGES' not in manifest


def test_android_runtime_does_not_branch_on_test_phone_vendor() -> None:
    root = Path(__file__).parents[1] / 'android/app/src/main'
    source = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted(root.rglob('*'))
        if path.suffix in {'.kt', '.java', '.xml'}
    ).lower()

    forbidden_vendor_markers = {
        'xiaomi', 'com.miui', 'ro.miui',
        'com.huawei', 'ro.build.version.emui',
        'com.coloros', 'com.vivo', 'com.samsung',
    }
    assert not (forbidden_vendor_markers & set(source.split()))
    for marker in forbidden_vendor_markers:
        assert marker not in source


def test_android_accessibility_settings_flow_is_resolved_and_connection_tolerant() -> None:
    source = (
        Path(__file__).parents[1]
        / 'android/app/src/main/java/com/easycode/player/PlayerActivity.kt'
    ).read_text(encoding='utf-8')

    assert 'Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)' in source
    assert 'resolveActivity(packageManager)' in source
    assert 'awaitAccessibilityConnection' in source
    assert 'ACCESSIBILITY_CONNECTION_GRACE_MS = 3_000L' in source


def test_android_frozen_capture_uses_overlay_clean_frame_gate_and_product_feedback() -> None:
    root = Path(__file__).parents[1]
    manifest = (root / 'android/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
    controller = (
        root
        / 'android/app/src/main/java/com/easycode/player/capture/FloatingCaptureController.kt'
    ).read_text(encoding='utf-8')
    service = (
        root
        / 'android/app/src/main/java/com/easycode/player/capture/ScreenCaptureService.kt'
    ).read_text(encoding='utf-8')
    compat = (
        root
        / 'android/app/src/main/java/com/easycode/player/util/AndroidCompat.kt'
    ).read_text(encoding='utf-8')

    assert 'android.permission.SYSTEM_ALERT_WINDOW' in manifest
    assert 'CaptureOverlayActivity' not in manifest
    assert 'TYPE_APPLICATION_OVERLAY' in controller
    assert 'hideBubbleForCapture' in controller
    assert 'startFreezeFlash' in controller
    assert 'FrozenCaptureSelection' in controller
    assert '设备方向已变化，请重新采集；旧值保持不变' in service
    assert 'val freshFrameDeadline' in service
    assert 'var image = activeReader.acquireLatestImage()' in service
    assert 'while (image == null && System.nanoTime() < freshFrameDeadline)' in service
    assert 'onCapturedContentResize(width: Int, height: Int)' in service
    assert 'resizeProjectionLocked(width, height)' in service
    assert 'activeDisplay.surface = null' in service
    assert 'AndroidCompat.ensureNotificationChannel' in service
    assert 'IMPORTANCE_LOW' in compat
    assert 'AUTO_CAPTURE_DELAY_MS' not in service
    assert 'addAction(' not in service


def test_android_build_rejects_invalid_version_before_toolchain(tmp_path: Path) -> None:
    service = AndroidDeliveryServiceV6(tmp_path)
    with pytest.raises(AndroidDeliveryError, match='versionCode'):
        service.build('missing.ecplayer', 'missing.json', version_code=0)
    with pytest.raises(AndroidDeliveryError, match='versionName'):
        service.build('missing.ecplayer', 'missing.json', version_name='')


def test_android_visual_analysis_clips_regions_but_frame_export_stays_strict() -> None:
    source = (
        Path(__file__).parents[1]
        / 'android/app/src/main/java/com/easycode/player/capture/AndroidVisionHost.kt'
    ).read_text(encoding='utf-8')

    assert source.count('clipToFrame = true') == 4
    assert 'private fun region(value: Any?, bitmap: Bitmap, clipToFrame: Boolean = false)' in source
    assert 'if (!clipToFrame)' in source
    assert 'val clippedRight = right.coerceIn(0L, bitmap.width.toLong())' in source
    assert 'if (area.width == 0 || area.height == 0) return null' in source
    assert '"ocr_result.field.lines" to emptyList<Map<String, Any?>>()' in source
    # saveFrame deliberately calls the strict default; it may not silently
    # produce a file with dimensions different from the author request.
    assert 'val area = region(arguments["$owner.parameter.region"], frame.bitmap)\n        val format' in source
