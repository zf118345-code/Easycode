"""Create signed Android extension bundles for real APK/worker verification.

The fixture JAR is compiled outside EasyCode.  This script then exercises the
same trust, seal, lock and publish services used by the IDE.  It deliberately
produces success, failure and timeout content bundles signed by one project
identity so an installed APK can verify worker recovery without rebuilding its
static extension module.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.bundle_signing_v6 import (  # noqa: E402
    AuthorSigningKeyStore,
    trust_root_document,
)
from core.vnext.extension_schema_v6 import (  # noqa: E402
    ExtensionManifestV1,
    MANIFEST_FILE,
    MANIFEST_SIGNATURE_FILE,
    sign_manifest,
)
from core.vnext.extensions import (  # noqa: E402
    ExtensionTrustStore,
    VNextExtensionRegistry,
)
from core.vnext.player_service import VNextPlayerService  # noqa: E402
from core.vnext.publish import VNextPublisher  # noqa: E402
from core.vnext.pure_operations_v6 import (  # noqa: E402
    PURE_OPERATION_REGISTRY_VERSION,
    pure_operation_registry_hash,
)
from core.vnext.target_service import (  # noqa: E402
    TargetConfiguration,
    target_configuration_revision,
)
from core.vnext.workspace import VNextWorkspaceManager  # noqa: E402


PACKAGE_ID = "com.easycode.harness.androidextension"
PUBLISHER_ID = "com.easycode.harness"
VARIANT_ID = "android.api21"
FUNCTIONS = {
    "com.easycode.harness.androidextension.add": (
        "Android 扩展·返回 5", "int64", "com.easycode.harness.AddExtension", 1_000,
    ),
    "com.easycode.harness.androidextension.fail": (
        "Android 扩展·结构化失败", "null", "com.easycode.harness.FailingExtension", 1_000,
    ),
    "com.easycode.harness.androidextension.slow": (
        "Android 扩展·超时", "null", "com.easycode.harness.SlowExtension", 100,
    ),
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def instruction(function_id: str) -> dict:
    _name, return_type, _class_name, timeout_ms = FUNCTIONS[function_id]
    return {
        "instruction_id": f"statement.{function_id.rsplit('.', 1)[-1]}",
        "function_id": function_id,
        "opcode": "call.extension",
        "callee_function_id": function_id,
        "arguments": {},
        "parameter_ids": {},
        "result_type": return_type,
        "result_slot": "extension_result" if return_type != "null" else None,
        "timeout_ms": timeout_ms,
        "source": {},
        "platforms": ["android_local"],
        "capabilities": [],
    }


def linked(function_id: str) -> dict:
    return {
        "diagnostics": [],
        "ecir": {
            "ecir_version": 1,
            "program_model_version": 1,
            "pure_operation_registry": {
                "registry_version": PURE_OPERATION_REGISTRY_VERSION,
                "content_hash": pure_operation_registry_hash(),
            },
            "entry_function_id": "function.main",
            "target_platform": "android_local",
            "supported_platforms": ["android_local"],
            "minimum_android_api": 21,
            "android_api_requirements": [],
            "required_capabilities": [],
            "functions": [{
                "function_id": "function.main",
                "name": "主程序",
                "parameters": [],
                "parameter_definitions": [],
                "return_type": "null",
                "instructions": [instruction(function_id)],
            }],
            "project_variables": [],
            "targets": [{
                "target_id": "target.android",
                "name": "Android 本机",
                "type": "android_local",
            }],
            "default_target_id": "target.android",
        },
    }


def create(arguments: argparse.Namespace) -> dict:
    output = arguments.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"输出目录必须为空，不会覆盖现有证据：{output}")
    output.mkdir(parents=True, exist_ok=True)
    jar = arguments.jar.resolve()
    if not jar.is_file():
        raise FileNotFoundError(jar)

    project_root = output / "project"
    signing = AuthorSigningKeyStore(output / "keys")
    trust = ExtensionTrustStore(output / "trust")
    original_signing = VNextExtensionRegistry.signing_key_store_factory
    original_trust = VNextExtensionRegistry.trust_store_factory
    VNextExtensionRegistry.signing_key_store_factory = staticmethod(lambda: signing)
    VNextExtensionRegistry.trust_store_factory = staticmethod(lambda: trust)
    try:
        manager = VNextWorkspaceManager()
        opened = manager.open(str(project_root), initialize=True)
        workspace = opened["workspace"]
        if workspace is None:
            raise RuntimeError("无法初始化 Android 扩展 Harness 项目")
        created = manager.scaffold_extension(
            workspace["workspace_id"], workspace["generation"],
            package_id=PACKAGE_ID,
            publisher_id=PUBLISHER_ID,
            publisher_name="EasyCode Harness",
            display_name="Android Extension Harness",
            description="Real signed Kotlin/JVM worker fixture",
            scope="project",
        )
        extension_root = Path(created["path"])
        manifest_value = json.loads((extension_root / MANIFEST_FILE).read_text(encoding="utf-8"))
        manifest_value["variants"] = [{
            "variant_id": VARIANT_ID,
            "host": "android_native",
            "runtime": "android-kotlin-v1",
            "targets": ["android_native"],
            "minimum_android_api": 21,
            "entrypoints": {
                function_id: values[2] for function_id, values in FUNCTIONS.items()
            },
        }]
        manifest_value["contributions"]["function_contracts"][0]["variant_bindings"] = [VARIANT_ID]
        contract_path = extension_root / "contracts" / "functions.json"
        contract_value = json.loads(contract_path.read_text(encoding="utf-8"))
        contract_value["functions"] = [{
            "function_id": function_id,
            "qualified_name": values[0],
            "description": "Android extension process harness",
            "contract_version": "1.0.0",
            "parameters": [],
            "return_type": values[1],
            "targets": ["android_native"],
            "permissions": [],
            "timeout_ms": values[3],
            "contract_tests": [],
        } for function_id, values in FUNCTIONS.items()]
        manifest = ExtensionManifestV1.model_validate(manifest_value)
        write_json(extension_root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
        write_json(contract_path, contract_value)
        identity = signing.get_or_create(f"extension:{PUBLISHER_ID}")
        write_json(extension_root / MANIFEST_SIGNATURE_FILE, sign_manifest(extension_root, manifest, identity))

        VNextExtensionRegistry.trust(str(project_root), PACKAGE_ID, "project", mode="explicit")
        manager.seal_android_jvm_extension(
            workspace["workspace_id"], workspace["generation"], PACKAGE_ID, "project",
            variant_id=VARIANT_ID, module_path=str(jar),
        )
        VNextExtensionRegistry.enable(str(project_root), PACKAGE_ID, "project")
        closure = VNextExtensionRegistry.publish_closure(str(project_root))
        if closure["errors"]:
            raise RuntimeError(json.dumps(closure["errors"], ensure_ascii=False))

        form = VNextPlayerService.normalize_form({
            "schema_version": 3,
            "title": "Android Extension Harness",
            "pages": [],
        })
        targets = [{
            "target_id": "target.android",
            "name": "Android 本机",
            "type": "android_local",
        }]
        target_configuration = TargetConfiguration(
            schema_version=1,
            targets=tuple(targets),
            default_target_id="target.android",
        )
        project = {
            "project_id": "android_extension_harness",
            "name": "Android Extension Harness",
            "targets_schema_version": 1,
            "targets": targets,
            "default_target_id": "target.android",
            "target_configuration_revision": target_configuration_revision(target_configuration),
        }
        write_json(project_root / "project.json", project)
        publisher = VNextPublisher(str(project_root), signing_key_store=signing)
        bundles: dict[str, str] = {}
        published_signature: dict | None = None
        for mode, function_id in (
            ("success", "com.easycode.harness.androidextension.add"),
            ("failure", "com.easycode.harness.androidextension.fail"),
            ("timeout", "com.easycode.harness.androidextension.slow"),
        ):
            program = linked(function_id)
            report = publisher.report(program, form, extension_packages=closure)
            if not report["valid"] or report["minimum_android_api"] != 21:
                raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
            published = publisher.build(
                program, form, project, report, extension_packages=closure,
            )
            published_signature = published["signature"]
            destination = output / f"{mode}.ecplayer"
            shutil.copyfile(published["path"], destination)
            bundles[mode] = str(destination)
        assert published_signature is not None
        trust_root = output / "trust-root.json"
        write_json(trust_root, trust_root_document(published_signature, project["project_id"]))
        result = {
            "schema_version": 1,
            "project": str(project_root),
            "jar": str(jar),
            "minimum_android_api": 21,
            "bundles": bundles,
            "trust_root": str(trust_root),
        }
        write_json(output / "harness.json", result)
        return result
    finally:
        VNextExtensionRegistry.signing_key_store_factory = original_signing
        VNextExtensionRegistry.trust_store_factory = original_trust


def main() -> int:
    parser = argparse.ArgumentParser(description="Create real Android extension worker harness bundles")
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = create(parser.parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
