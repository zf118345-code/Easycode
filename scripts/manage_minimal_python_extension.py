"""Build, import, exercise, or remove the minimal EasyCode Python extension.

This is the canonical extension-author golden path.  The source package is
created outside the destination project, signed, then imported through the
same registry operation used by the UI.  It is never silently preinstalled.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore
from core.vnext.extension_schema_v6 import (
    ExtensionManifestV1,
    FunctionContractFileV1,
    MANIFEST_FILE,
    MANIFEST_SIGNATURE_FILE,
    sign_manifest,
)
from core.vnext.extensions import VNextExtensionRegistry
from core.vnext.runtime import RuntimeFailure
from core.vnext.workspace import VNextWorkspaceManager


PACKAGE_ID = "com.easycode.examples.minimalpython"
PUBLISHER_ID = "com.easycode.examples"
FUNCTION_ID = f"{PACKAGE_ID}.numbers.add"
LEFT_ID = f"{FUNCTION_ID}.left"
RIGHT_ID = f"{FUNCTION_ID}.right"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def contracts() -> dict[str, Any]:
    return {
        "contract_schema_version": 1,
        "contribution_id": f"{PACKAGE_ID}.functions",
        "functions": [{
            "function_id": FUNCTION_ID,
            "qualified_name": "示例扩展.两个数相加",
            "description": "最小 Python 扩展示例；用于体验导入、信任、调用和卸载全流程。",
            "contract_version": "1.0.0",
            "parameters": [
                {"parameter_id": LEFT_ID, "name": "left", "display_name": "左值", "value_type": "float64", "required": True, "control": {"control": "number"}},
                {"parameter_id": RIGHT_ID, "name": "right", "display_name": "右值", "value_type": "float64", "required": True, "control": {"control": "number"}},
            ],
            "return_type": "float64",
            "targets": ["windows", "android_adb", "none"],
            "permissions": [],
            "timeout_ms": 1_000,
            "contract_tests": [{
                "test_id": "adds-two-numbers",
                "arguments": {LEFT_ID: 2.5, RIGHT_ID: 3.5},
                "expected": 6.0,
            }],
        }],
    }


SOURCE = '''def add_numbers(context, left, right):
    context.log("最小 Python 扩展：相加完成")
    return float(left) + float(right)
'''


def build_source_package(parent: Path) -> Path:
    """Create a signed source package in an isolated authoring project."""
    authoring_project = parent / "authoring-project"
    VNextWorkspaceManager().open(str(authoring_project), initialize=True)
    created = VNextExtensionRegistry.scaffold(
        str(authoring_project),
        package_id=PACKAGE_ID,
        publisher_id=PUBLISHER_ID,
        publisher_name="EasyCode Examples",
        display_name="最小 Python 扩展",
        description="一个可导入、可卸载、无权限的相加函数示例。",
        scope="project",
    )
    root = Path(created["path"])
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["variants"][0]["entrypoints"] = {FUNCTION_ID: "add_numbers"}
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    contract_file = FunctionContractFileV1.model_validate(contracts())
    write_json(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    write_json(root / "contracts" / "functions.json", contract_file.model_dump(mode="json"))
    (root / "src" / "main.py").write_text(SOURCE, encoding="utf-8")
    (root / "README.md").write_text(
        "# 最小 Python 扩展\n\n"
        "在 EasyCode 的扩展页选择本文件夹导入。安装不等于信任；请查看声明后显式信任、构建并启用。\n"
        "启用后在函数库的“扩展”页搜索“两个数相加”。该包不申请文件、网络、输入或捕获权限。\n",
        encoding="utf-8",
    )
    identity = AuthorSigningKeyStore().get_or_create(f"extension:{PUBLISHER_ID}")
    write_json(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))
    return root


def remove_existing(project: Path, scope: str) -> None:
    try:
        package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, scope)
    except RuntimeFailure:
        return
    if package.get("enabled"):
        VNextExtensionRegistry.disable(str(project), PACKAGE_ID, scope)
    VNextExtensionRegistry.delete_package(str(project), PACKAGE_ID, scope)


def install(project: Path, scope: str = "project") -> dict[str, Any]:
    if scope not in {"project", "user"}:
        raise ValueError("scope 必须是 project 或 user")
    remove_existing(project, scope)
    with tempfile.TemporaryDirectory(prefix="EasyCodeMinimalPython-") as temporary:
        source = build_source_package(Path(temporary))
        imported = VNextExtensionRegistry.import_package(
            str(project), source_path=str(source), scope=scope,
        )
    VNextExtensionRegistry.trust(str(project), PACKAGE_ID, scope, mode="explicit")
    sealed = VNextExtensionRegistry.build_sealed(str(project), PACKAGE_ID, scope)
    enabled = VNextExtensionRegistry.enable(str(project), PACKAGE_ID, scope)
    contract_tests = VNextExtensionRegistry.contract_tests(str(project), PACKAGE_ID, scope)
    definitions, errors = VNextExtensionRegistry.definitions(str(project))
    return {
        "package_id": PACKAGE_ID,
        "scope": scope,
        "imported": bool(imported.get("imported")),
        "signature_verified": bool(imported["package"].get("signature_verified")),
        "trusted": True,
        "sealed_formats": [item.get("format") for item in sealed.get("artifacts") or []],
        "enabled": bool(enabled.get("enabled")),
        "lock_current": VNextExtensionRegistry.package(str(project), PACKAGE_ID, scope).get("lock_current"),
        "contract_tests": contract_tests,
        "catalog_function_ids": [item["function_id"] for item in definitions if item.get("package_id") == PACKAGE_ID],
        "catalog_errors": errors,
    }


def remove(project: Path, scope: str = "project") -> dict[str, Any]:
    remove_existing(project, scope)
    return {"package_id": PACKAGE_ID, "scope": scope, "removed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "install", "remove", "status"))
    parser.add_argument("--project", type=Path)
    parser.add_argument("--output", type=Path, help="build 时存放外部作者项目；不得是已有非空目录")
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    args = parser.parse_args()
    if args.action == "build":
        if args.output is None:
            parser.error("build 需要 --output")
        output = args.output.resolve()
        if output.exists() and any(output.iterdir()):
            parser.error(f"输出目录必须不存在或为空：{output}")
        result = {"built": True, "package_path": str(build_source_package(output))}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.project is None:
        parser.error(f"{args.action} 需要 --project")
    project = args.project.resolve()
    if not (project / "project.json").is_file():
        parser.error(f"不是 EasyCode 项目：{project}")
    if args.action == "install":
        result = install(project, args.scope)
    elif args.action == "remove":
        result = remove(project, args.scope)
    else:
        result = VNextExtensionRegistry.package(str(project), PACKAGE_ID, args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
