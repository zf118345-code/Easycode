from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app import create_app
from api.routers.vnext_router import create_vnext_router
from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore
from core.vnext.extension_schema_v6 import (
    EasyCodeLockV1,
    ExtensionSchemaError,
    ExtensionManifestV1,
    FunctionContractFileV1,
    HostVariantV1,
    MANIFEST_FILE,
    MANIFEST_SIGNATURE_FILE,
    PublishedExtensionV1,
    sign_manifest,
    SealedRuntimeV1,
    validate_published_extension,
)
from core.vnext.extensions import ExtensionTrustStore, VNextExtensionRegistry
from core.vnext.player_bundle import VNextPlayerBundleManager
from core.vnext.program_commands import insert_call, update_call_argument
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_contracts import FunctionContract, FunctionContractRegistry, ParameterContract
from core.vnext.program_types import IntValue, create_program_document
from core.vnext.publish import VNextPublisher
from core.vnext.runtime import RuntimeFailure, vnext_runtime
from core.vnext.target_service import TargetConfiguration, target_configuration_revision
from core.vnext.workspace import VNextWorkspaceManager


PACKAGE_ID = "com.example.demo"
PUBLISHER_ID = "com.example"
FUNCTION_ID = "com.example.demo.add"
LEFT_ID = "com.example.demo.add.left"
RIGHT_ID = "com.example.demo.add.right"


def _json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def extension_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    signing = AuthorSigningKeyStore(tmp_path / "signing-keys")
    trust = ExtensionTrustStore(tmp_path / "trust")
    monkeypatch.setattr(
        VNextExtensionRegistry,
        "signing_key_store_factory",
        staticmethod(lambda: signing),
    )
    monkeypatch.setattr(
        VNextExtensionRegistry,
        "trust_store_factory",
        staticmethod(lambda: trust),
    )
    monkeypatch.setenv("EASYCODE_USER_EXTENSIONS_DIR", str(tmp_path / "user-extensions"))
    monkeypatch.setenv("EASYCODE_OFFICIAL_EXTENSIONS_DIR", str(tmp_path / "official-extensions"))
    return signing, trust


def _workspace(project: Path) -> tuple[VNextWorkspaceManager, dict]:
    manager = VNextWorkspaceManager()
    opened = manager.open(str(project), initialize=True)
    workspace = opened["workspace"]
    assert workspace is not None
    return manager, workspace


def _scaffold_function_extension(
    project: Path,
    manager: VNextWorkspaceManager,
    workspace: dict,
    signing: AuthorSigningKeyStore,
    *,
    implementation: str = """def add(context, left, right):
    context.log(f\"adding {left} + {right}\")
    return left + right
""",
    timeout_ms: int = 1_000,
) -> Path:
    created = manager.scaffold_extension(
        workspace["workspace_id"],
        workspace["generation"],
        package_id=PACKAGE_ID,
        publisher_id=PUBLISHER_ID,
        publisher_name="Example Publisher",
        display_name="Example Extension",
        description="Signed extension harness",
        scope="project",
    )
    root = Path(created["path"])
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["variants"][0]["entrypoints"] = {FUNCTION_ID: "add"}
    contracts = {
        "contract_schema_version": 1,
        "contribution_id": f"{PACKAGE_ID}.functions",
        "functions": [{
            "function_id": FUNCTION_ID,
            "qualified_name": "测试.相加",
            "description": "Add two integers",
            "contract_version": "1.0.0",
            "parameters": [
                {"parameter_id": LEFT_ID, "name": "left", "display_name": "左值", "value_type": "int64", "required": True},
                {"parameter_id": RIGHT_ID, "name": "right", "display_name": "右值", "value_type": "int64", "required": True},
            ],
            "return_type": "int64",
            "targets": ["none"],
            "permissions": [],
            "timeout_ms": timeout_ms,
            "contract_tests": [{
                "test_id": "adds-two-values",
                "arguments": {LEFT_ID: 2, RIGHT_ID: 3},
                "expected": 5,
            }],
        }],
    }
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    FunctionContractFileV1.model_validate(contracts)
    _json_write(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    _json_write(root / "contracts" / "functions.json", contracts)
    (root / "src" / "main.py").write_text(implementation, encoding="utf-8")
    identity = signing.get_or_create(f"extension:{PUBLISHER_ID}")
    _json_write(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))
    return root


def _trust_build_enable(project: Path) -> dict:
    with pytest.raises(RuntimeFailure, match="尚未在本机信任"):
        VNextExtensionRegistry.enable(str(project), PACKAGE_ID, "project")
    VNextExtensionRegistry.trust(str(project), PACKAGE_ID, "project", mode="explicit")
    built = VNextExtensionRegistry.build_sealed(str(project), PACKAGE_ID, "project")
    enabled = VNextExtensionRegistry.enable(str(project), PACKAGE_ID, "project")
    assert built["artifacts"][0]["format"] == "ecx-runtime-1"
    assert enabled["lock"]["package_id"] == PACKAGE_ID
    return enabled


def _linked_extension_program() -> dict:
    instruction = {
        "instruction_id": "statement.extension.add",
        "function_id": FUNCTION_ID,
        "opcode": "call.extension",
        "arguments": {LEFT_ID: 2, RIGHT_ID: 3},
        "parameter_ids": {LEFT_ID: LEFT_ID, RIGHT_ID: RIGHT_ID},
        "result_type": "int64",
        "result_slot": "sum",
        "source": {},
        "platforms": ["no_target"],
        "capabilities": [],
        "callee_function_id": FUNCTION_ID,
    }
    return {
        "diagnostics": [],
        "ecir": {
            "entry_function_id": "function.main",
            "functions": [{
                "function_id": "function.main",
                "name": "主程序",
                "parameters": [],
                "parameter_definitions": [],
                "return_type": "null",
                "instructions": [instruction],
            }],
            "project_variables": [],
            "required_capabilities": [],
            "supported_platforms": ["no_target"],
            "targets": [],
            "default_target_id": None,
        },
    }


def _terminal(execution_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = vnext_runtime.snapshot(execution_id)
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.02)
    raise AssertionError("Player extension run did not finish")


def test_program_compiler_keeps_extension_callee_and_stable_parameter_ids() -> None:
    registry = FunctionContractRegistry((FunctionContract(
        function_id=FUNCTION_ID,
        qualified_name="测试.相加",
        opcode="call.extension",
        parameters=(
            ParameterContract(LEFT_ID, "left", "左值", "int64"),
            ParameterContract(RIGHT_ID, "right", "右值", "int64"),
        ),
        return_type="int64",
        platforms=("no_target",),
    ),))
    document = create_program_document("主程序", function_id="function.main", document_id="document.main")
    inserted = insert_call(document, registry, FUNCTION_ID)
    document = update_call_argument(
        inserted.document, registry, inserted.selected_statement_id, LEFT_ID,
        IntValue(value_id="value.left", value=2),
    ).document
    document = update_call_argument(
        document, registry, inserted.selected_statement_id, RIGHT_ID,
        IntValue(value_id="value.right", value=3),
    ).document
    compiled = compile_program_document(document, registry, target_platform="no_target")
    assert compiled["valid"] is True
    instruction = compiled["ecir"]["functions"][0]["instructions"][0]
    assert instruction["opcode"] == "call.extension"
    assert instruction["callee_function_id"] == FUNCTION_ID
    assert set(instruction["arguments"]) == {LEFT_ID, RIGHT_ID}


def test_android_extension_variant_requires_and_projects_explicit_api_floor(
    extension_environment, tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="minimum_android_api"):
        HostVariantV1.model_validate({
            "variant_id": "android.missing-floor",
            "host": "android_native",
            "runtime": "android-kotlin-v1",
            "targets": ["android_native"],
            "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
        })

    signing, _trust = extension_environment
    project = tmp_path / "android-floor-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["variants"][0]["entrypoints"] = {}
    manifest_value["variants"].append({
        "variant_id": "android.api28",
        "host": "android_native",
        "runtime": "android-kotlin-v1",
        "targets": ["android_native"],
        "minimum_android_api": 28,
        "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
    })
    manifest_value["contributions"]["function_contracts"][0]["variant_bindings"].append("android.api28")
    contracts_path = root / "contracts" / "functions.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts["functions"][0]["targets"] = ["android_native"]
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    _json_write(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    _json_write(contracts_path, contracts)
    identity = signing.get_or_create(f"extension:{PUBLISHER_ID}")
    _json_write(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))

    package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")
    assert package["valid"] is True, package["diagnostics"]
    assert package["functions"][0]["platforms"] == ["android_local"]
    assert package["functions"][0]["minimum_android_api"] == 28


def test_external_android_jar_is_validated_sealed_signed_and_exposed_by_api(
    extension_environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "android-jar-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["variants"].append({
        "variant_id": "android.api24",
        "host": "android_native",
        "runtime": "android-kotlin-v1",
        "targets": ["android_native"],
        "minimum_android_api": 24,
        "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
    })
    manifest_value["contributions"]["function_contracts"][0]["variant_bindings"].append("android.api24")
    contracts_path = root / "contracts" / "functions.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts["functions"][0]["targets"] = ["none", "android_native"]
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    _json_write(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    _json_write(contracts_path, contracts)
    identity = signing.get_or_create(f"extension:{PUBLISHER_ID}")
    _json_write(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))
    VNextExtensionRegistry.trust(str(project), PACKAGE_ID, "project", mode="explicit")

    jar = tmp_path / "demo.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("META-INF/", b"")
        archive.writestr("com/example/demo/", b"")
        archive.writestr("com/example/demo/AddExtension.class", b"\xca\xfe\xba\xbe")
        archive.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\n")

    result = manager.seal_android_jvm_extension(
        workspace["workspace_id"], workspace["generation"], PACKAGE_ID, "project",
        variant_id="android.api24", module_path=str(jar),
    )
    assert result["sealed"] is True
    assert result["minimum_android_api"] == 24
    assert result["artifact"]["descriptor"]["module"] == "runtime/module.jar"
    artifact = root / "dist" / "android.api24.ecxrt"
    assert artifact.is_file()
    with zipfile.ZipFile(artifact) as archive:
        assert archive.read("runtime/module.jar") == jar.read_bytes()

    monkeypatch.setattr("api.routers.vnext_router.vnext_workspace_manager", manager)
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    another = tmp_path / "replacement.jar"
    with zipfile.ZipFile(another, "w") as archive:
        archive.writestr("com/example/demo/AddExtension.class", b"\xca\xfe\xba\xbe\x00")
    response = client.post(
        f"/api/vnext/extensions/{PACKAGE_ID}/seal-android-jvm",
        headers={
            "X-Workspace-Id": workspace["workspace_id"],
            "X-Workspace-Generation": str(workspace["generation"]),
        },
        json={"scope": "project", "variant_id": "android.api24", "module_path": str(another)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["module_sha256"] != result["module_sha256"]


def test_android_jar_seal_rejects_missing_entrypoint_and_source_payload(
    extension_environment, tmp_path: Path,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "invalid-android-jar-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["variants"] = [{
        "variant_id": "android.api24", "host": "android_native",
        "runtime": "android-kotlin-v1", "targets": ["android_native"],
        "minimum_android_api": 24,
        "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
    }]
    manifest_value["contributions"]["function_contracts"][0]["variant_bindings"] = ["android.api24"]
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    missing = tmp_path / "missing.jar"
    with zipfile.ZipFile(missing, "w") as archive:
        archive.writestr("com/example/demo/Other.class", b"class")
    with pytest.raises(RuntimeFailure, match="入口类不存在"):
        VNextExtensionRegistry._build_android_jvm_variant(missing, manifest, manifest.host_variants[0])
    source = tmp_path / "source.jar"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("com/example/demo/AddExtension.class", b"class")
        archive.writestr("com/example/demo/AddExtension.kt", b"class AddExtension")
    with pytest.raises(RuntimeFailure, match="包含源码"):
        VNextExtensionRegistry._build_android_jvm_variant(source, manifest, manifest.host_variants[0])


def test_android_kotlin_variant_and_sealed_runtime_require_jvm_class_and_jar_module() -> None:
    with pytest.raises(ValidationError, match="JVM 二进制类名"):
        HostVariantV1.model_validate({
            "variant_id": "android.api24",
            "host": "android_native",
            "runtime": "android-kotlin-v1",
            "targets": ["android_native"],
            "minimum_android_api": 24,
            "entrypoints": {FUNCTION_ID: "add"},
        })

    valid = SealedRuntimeV1.model_validate({
        "format": "ecx-runtime-1",
        "package_id": PACKAGE_ID,
        "version": "1.0.0",
        "variant_id": "android.api24",
        "host": "android_native",
        "runtime": "android-kotlin-v1",
        "minimum_android_api": 24,
        "targets": ["android_native"],
        "module": "runtime/demo.jar",
        "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
        "files": [{"path": "runtime/demo.jar", "size": 3, "sha256": "a" * 64}],
    })
    assert valid.module == "runtime/demo.jar"

    with pytest.raises(ValidationError, match="JAR module"):
        SealedRuntimeV1.model_validate({
            **valid.model_dump(mode="json"),
            "module": "runtime/demo.dex",
            "files": [{"path": "runtime/demo.dex", "size": 3, "sha256": "a" * 64}],
        })


def test_extension_permission_registry_rejects_unknown_ids_and_enforces_android_floor(
    extension_environment, tmp_path: Path,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "android-permission-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    original = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    unknown = json.loads(json.dumps(original))
    unknown["permissions"] = ["vendor.made_up_permission"]
    with pytest.raises(ValidationError, match="未知扩展权限 ID"):
        ExtensionManifestV1.model_validate(unknown)

    original["permissions"] = ["target.input"]
    original["variants"] = [{
        "variant_id": "android.api21", "host": "android_native",
        "runtime": "android-kotlin-v1", "targets": ["android_native"],
        "minimum_android_api": 21,
        "entrypoints": {FUNCTION_ID: "com.example.demo.AddExtension"},
    }]
    original["contributions"]["function_contracts"][0]["variant_bindings"] = ["android.api21"]
    contracts_path = root / "contracts" / "functions.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts["functions"][0]["targets"] = ["android_native"]
    contracts["functions"][0]["permissions"] = ["target.input"]
    manifest = ExtensionManifestV1.model_validate(original)
    _json_write(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    _json_write(contracts_path, contracts)
    identity = signing.get_or_create(f"extension:{PUBLISHER_ID}")
    _json_write(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))

    package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")
    assert package["valid"] is False
    assert any("API 24" in item["message"] for item in package["diagnostics"])

def test_android_extension_floor_is_added_to_final_publish_ecir(tmp_path: Path) -> None:
    linked = {
        "diagnostics": [],
        "ecir": {
            "entry_function_id": "function.main",
            "target_platform": "android_local",
            "supported_platforms": ["android_local"],
            "minimum_android_api": 21,
            "android_api_requirements": [],
            "required_capabilities": [],
            "functions": [{
                "function_id": "function.main", "name": "主程序",
                "parameters": [], "parameter_definitions": [],
                "return_type": "null", "instructions": [],
            }],
            "project_variables": [], "targets": [], "default_target_id": None,
        },
    }
    extensions = {"packages": [{
        "package": {
            "package_id": "com.example.android28", "display_name": "Android 28 控件扩展",
            "permissions": [], "network": {"level": "none", "rules": []},
            "function_contracts": [], "host_variants": [],
        },
        "lock": {
            "package_id": "com.example.android28", "version": "1.0.0",
            "dependencies": [],
            "selected_variants": [{
                "host": "android_native", "target": "android_native",
                "variant_id": "android.api28", "runtime": "android-kotlin-v1",
                "minimum_android_api": 28,
                "artifact_sha256": "a" * 64, "artifact_signature_sha256": "b" * 64,
            }],
        },
        "artifacts": [{
            "sha256": "a" * 64,
            "descriptor": {
                "variant_id": "android.api28", "host": "android_native",
                "runtime": "android-kotlin-v1", "targets": ["android_native"],
            },
        }],
    }]}

    report = VNextPublisher(str(tmp_path)).report(
        linked, {"schema_version": 3, "title": "运行", "pages": []},
        extension_packages=extensions,
    )

    assert report["minimum_android_api"] == 28
    assert report["android_api_requirements"] == [{
        "kind": "extension",
        "package_id": "com.example.android28",
        "display_name": "Android 28 控件扩展",
        "minimum_android_api": 28,
        "statement_ids": [],
    }]


def test_android_api21_extension_keeps_baseline_without_redundant_requirement(tmp_path: Path) -> None:
    linked = {
        "diagnostics": [],
        "ecir": {
            "entry_function_id": "function.main",
            "target_platform": "android_local",
            "supported_platforms": ["android_local"],
            "minimum_android_api": 21,
            "android_api_requirements": [],
            "required_capabilities": [],
            "functions": [], "project_variables": [], "targets": [], "default_target_id": None,
        },
    }
    extensions = {"packages": [{
        "package": {"package_id": "com.example.android21", "display_name": "Android 21 扩展"},
        "lock": {
            "package_id": "com.example.android21",
            "selected_variants": [{
                "host": "android_native", "minimum_android_api": 21,
            }],
        },
    }]}

    report = VNextPublisher(str(tmp_path)).report(
        linked, {"schema_version": 3, "title": "运行", "pages": []},
        extension_packages=extensions,
    )

    assert report["minimum_android_api"] == 21
    assert report["android_api_requirements"] == []


def test_published_android_variant_floor_must_equal_signed_lock(tmp_path: Path) -> None:
    locked = EasyCodeLockV1.model_validate({
        "lock_version": 1,
        "project_format": 6,
        "toolchain": {
            "compiler_version": "6.0.0", "program_schema": 1, "ecir": 1,
            "pure_value_registry_version": 10,
            "pure_value_registry_sha256": "f" * 64,
        },
        "extensions": [{
            "package_id": "com.example.android", "version": "1.0.0", "scope": "project",
            "manifest_sha256": "a" * 64, "content_sha256": "b" * 64,
            "publisher_id": "com.example", "publisher_key_fingerprint": "c" * 64,
            "publisher_public_key": "unused-in-this-early-check", "trust_mode": "local_trusted_code",
            "selected_variants": [{
                "target": "android_native", "host": "android_native",
                "variant_id": "android.api28", "runtime": "android-kotlin-v1",
                "minimum_android_api": 28,
                "artifact_sha256": "d" * 64, "artifact_signature_sha256": "e" * 64,
            }],
        }],
    }).extensions[0]
    descriptor = PublishedExtensionV1.model_validate({
        "runtime_extension_schema": 1,
        "package_id": "com.example.android", "version": "1.0.0",
        "publisher_id": "com.example", "publisher_key_fingerprint": "c" * 64,
        "publisher_public_key": "unused-in-this-early-check",
        "manifest_sha256": "a" * 64, "content_sha256": "b" * 64,
        "trust_mode": "local_trusted_code", "network": {"level": "none", "rules": []},
        "variants": [{
            "target": "android_native", "host": "android_native",
            "runtime": "android-kotlin-v1", "minimum_android_api": 29,
            "variant_id": "android.api28",
            "artifact_path": "runtime/extensions/com.example.android/android.api28.ecxrt",
            "artifact_signature_path": "runtime/extensions/com.example.android/android.api28.ecxrt.sig",
            "artifact_sha256": "d" * 64, "artifact_signature_sha256": "e" * 64,
            "entrypoints": {},
        }],
    })

    with pytest.raises(ExtensionSchemaError, match="宿主变体"):
        validate_published_extension(tmp_path, descriptor, locked)


def test_strict_manifest_and_signed_file_closure_reject_unknown_path_duplicate_and_tamper(
    extension_environment, tmp_path: Path,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "strict-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    manifest = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ExtensionManifestV1.model_validate({**manifest, "unknown_behavior": True})
    invalid_path = json.loads(json.dumps(manifest))
    invalid_path["contributions"]["function_contracts"][0]["path"] = "../escape.json"
    with pytest.raises(ValidationError):
        ExtensionManifestV1.model_validate(invalid_path)
    contract = json.loads((root / "contracts" / "functions.json").read_text(encoding="utf-8"))
    contract["functions"].append(contract["functions"][0])
    with pytest.raises(ValidationError):
        FunctionContractFileV1.model_validate(contract)

    (root / "contracts" / "functions.json").write_text("{}\n", encoding="utf-8")
    package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")
    assert package["valid"] is False
    assert package["signature_verified"] is False
    assert "签名文件闭包" in package["diagnostics"][0]["message"]


def test_extension_statement_summary_accepts_declared_slots_and_rejects_unknown_slots() -> None:
    base = {
        "contract_schema_version": 1,
        "contribution_id": "com.example.summary.functions",
        "functions": [{
            "function_id": "com.example.summary.echo",
            "qualified_name": "测试.回显",
            "description": "回显一段内容",
            "statement_summary": "回显{content}",
            "parameters": [{
                "parameter_id": "com.example.summary.echo.content",
                "name": "content",
                "display_name": "内容",
                "value_type": "string",
                "required": True,
            }],
            "return_type": "string",
            "targets": ["none"],
        }],
    }

    contract = FunctionContractFileV1.model_validate(base)
    assert contract.functions[0].statement_summary == "回显{content}"

    invalid = json.loads(json.dumps(base))
    invalid["functions"][0]["statement_summary"] = "回显{missing}"
    with pytest.raises(ValidationError, match="不存在的参数"):
        FunctionContractFileV1.model_validate(invalid)


def test_lock_is_explicit_worker_uses_contract_ids_and_reference_blocks_lifecycle(
    extension_environment, tmp_path: Path,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "lock-project"
    manager, workspace = _workspace(project)
    root = _scaffold_function_extension(project, manager, workspace, signing)
    _trust_build_enable(project)

    lock_path = project / "easycode.lock"
    locked = lock_path.read_bytes()
    VNextExtensionRegistry.packages(str(project))
    assert lock_path.read_bytes() == locked
    logs: list[tuple[str, str]] = []
    result = VNextExtensionRegistry.invoke(
        str(project), FUNCTION_ID, {LEFT_ID: 7, RIGHT_ID: 8}, {},
        lambda: False, lambda level, message: logs.append((level, message)),
    )
    assert result == 15
    assert logs == [("info", "adding 7 + 8")]

    assets = json.loads((project / "assets" / "registry.json").read_text(encoding="utf-8"))
    assets["extension_harness_reference"] = FUNCTION_ID
    _json_write(project / "assets" / "registry.json", assets)
    assert json.loads((project / "assets" / "registry.json").read_text(encoding="utf-8"))["extension_harness_reference"] == FUNCTION_ID
    assert [
        item["function_id"]
        for item in VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")["functions"]
    ] == [FUNCTION_ID]
    assert VNextExtensionRegistry.references(str(project), PACKAGE_ID, "project") == [{
        "path": "assets/registry.json",
        "json_path": "extension_harness_reference",
        "identifier": FUNCTION_ID,
    }]
    with pytest.raises(RuntimeFailure, match="1 处.*引用"):
        VNextExtensionRegistry.disable(str(project), PACKAGE_ID, "project")

    assets.pop("extension_harness_reference")
    _json_write(project / "assets" / "registry.json", assets)
    VNextExtensionRegistry.disable(str(project), PACKAGE_ID, "project")
    VNextExtensionRegistry.delete_package(str(project), PACKAGE_ID, "project")
    assert not root.exists()


def test_worker_timeout_isolated_from_host(extension_environment, tmp_path: Path) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "timeout-project"
    manager, workspace = _workspace(project)
    _scaffold_function_extension(
        project, manager, workspace, signing,
        timeout_ms=50,
        implementation="""import time
def add(context, left, right):
    time.sleep(0.25)
    return left + right
""",
    )
    _trust_build_enable(project)
    with pytest.raises(RuntimeFailure) as error:
        VNextExtensionRegistry.invoke(
            str(project), FUNCTION_ID, {LEFT_ID: 1, RIGHT_ID: 2}, {},
            lambda: False, lambda _level, _message: None,
        )
    assert error.value.error_id == "extension.timeout"
    assert VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")["enabled"] is True


def test_signed_extension_publishes_source_free_and_player_loads_and_calls_it(
    extension_environment, tmp_path: Path,
) -> None:
    signing, _trust = extension_environment
    project = tmp_path / "publish-project"
    manager, workspace = _workspace(project)
    _scaffold_function_extension(project, manager, workspace, signing)
    _trust_build_enable(project)
    closure = VNextExtensionRegistry.publish_closure(str(project))
    assert closure["errors"] == []

    linked = _linked_extension_program()
    form = {"schema_version": 3, "title": "运行", "pages": []}
    target_config = TargetConfiguration(schema_version=1, targets=[], default_target_id=None)
    project_manifest = {
        "project_id": "extension_player_product",
        "name": "Extension Player",
        "targets_schema_version": 1,
        "targets": [],
        "default_target_id": None,
        "target_configuration_revision": target_configuration_revision(target_config),
    }
    publisher = VNextPublisher(str(project), signing_key_store=signing)
    report = publisher.report(linked, form, extension_packages=closure)
    assert report["valid"] is True, report["errors"]
    assert report["extensions"][0]["variants"][0]["artifact_verified"] is True
    published = publisher.build(linked, form, project_manifest, report, extension_packages=closure)

    with zipfile.ZipFile(published["path"]) as archive:
        names = archive.namelist()
        assert "runtime/easycode.lock" in names
        assert any(name.endswith(".ecxrt") for name in names)
        assert not any("/src/" in name or "/tests/" in name or "/.vscode/" in name for name in names)
        assert not any(name.endswith((".py", ".pyi", ".toml")) for name in names)

    player = VNextPlayerBundleManager(expected_public_key=published["signature"]["public_key"])
    bootstrap = player.load(published["path"])
    assert bootstrap["extensions"][0]["package_id"] == PACKAGE_ID
    started = player.start({})
    terminal = _terminal(started["execution_id"])
    assert terminal["status"] == "completed", terminal.get("error")
    assert terminal["variables"]["sum"] == 5
    assert any(item["category"] == "extension" and "adding 2 + 3" in item["message"] for item in terminal["events"])
    player.shutdown()


def test_old_extension_source_editor_routes_are_fixed_410() -> None:
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    cases = (
        ("post", "/api/vnext/extensions"),
        ("put", f"/api/vnext/extensions/{PACKAGE_ID}"),
        ("post", f"/api/vnext/extensions/{PACKAGE_ID}/functions"),
        ("get", f"/api/vnext/extensions/{PACKAGE_ID}/source"),
        ("put", f"/api/vnext/extensions/{PACKAGE_ID}/source"),
        ("delete", f"/api/vnext/extensions/{PACKAGE_ID}/functions/legacy.function"),
    )
    for method, path in cases:
        response = client.request(method, path, json={"legacy": True})
        assert response.status_code == 410, (method, path, response.text)
        assert response.json()["detail"]["code"] == "extension_source_editor_retired"


def test_current_app_does_not_mount_legacy_capability_router() -> None:
    paths = set(create_app().openapi()["paths"])
    assert not {path for path in paths if path.startswith("/api/capabilities")}
    assert "/api/vnext/extensions" in paths
