"""Install, verify, or remove the project-scoped EasyCode extension showcase.

The showcase is intentionally ordinary extension content. It exercises the
same signed manifest, typed controls, Worker, lock, function catalog, and
reference-safe removal paths available to third-party authors.
"""

from __future__ import annotations

import argparse
import json
import sys
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


PACKAGE_ID = "com.easycode.harness.showcase"
PUBLISHER_ID = "com.easycode.harness"
SCOPE = "project"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parameter(function: str, name: str, label: str, value_type: str, **extra: Any) -> dict[str, Any]:
    return {
        "parameter_id": f"{function}.{name}",
        "name": name,
        "display_name": label,
        "value_type": value_type,
        **extra,
    }


def contracts() -> dict[str, Any]:
    text_id = f"{PACKAGE_ID}.text.decorate"
    number_id = f"{PACKAGE_ID}.number.clamp"
    list_id = f"{PACKAGE_ID}.list.join"
    return {
        "contract_schema_version": 1,
        "contribution_id": f"{PACKAGE_ID}.functions",
        "functions": [
            {
                "function_id": text_id,
                "qualified_name": "展示扩展.装饰文本",
                "description": "演示文本、布尔值、可选参数与外部 Python Worker。",
                "contract_version": "1.0.0",
                "parameters": [
                    parameter(text_id, "content", "内容", "string", required=True, control={"control": "text"}),
                    parameter(text_id, "prefix", "前缀", "string", required=False, default="[扩展] ", control={"control": "text"}),
                    parameter(text_id, "uppercase", "转为大写", "bool", required=False, default=False, control={"control": "switch"}),
                ],
                "return_type": "string",
                "targets": ["windows", "android_adb", "none"],
                "permissions": [],
                "timeout_ms": 1_000,
                "contract_tests": [{
                    "test_id": "decorate-text",
                    "arguments": {
                        f"{text_id}.content": "easycode",
                        f"{text_id}.prefix": "UI: ",
                        f"{text_id}.uppercase": True,
                    },
                    "expected": "UI: EASYCODE",
                }],
            },
            {
                "function_id": number_id,
                "qualified_name": "展示扩展.限制数值",
                "description": "演示多个数值输入、计算值和返回结果。",
                "contract_version": "1.0.0",
                "parameters": [
                    parameter(number_id, "value", "当前值", "float64", required=True, control={"control": "number"}),
                    parameter(number_id, "minimum", "最小值", "float64", required=False, default=0, control={"control": "number"}),
                    parameter(number_id, "maximum", "最大值", "float64", required=False, default=100, control={"control": "number"}),
                ],
                "return_type": "float64",
                "targets": ["windows", "android_adb", "none"],
                "permissions": [],
                "timeout_ms": 1_000,
                "contract_tests": [{
                    "test_id": "clamp-number",
                    "arguments": {
                        f"{number_id}.value": 18,
                        f"{number_id}.minimum": 20,
                        f"{number_id}.maximum": 30,
                    },
                    "expected": 20.0,
                }],
            },
            {
                "function_id": list_id,
                "qualified_name": "展示扩展.连接文本列表",
                "description": "演示列表参数和可复用的外部函数返回值。",
                "contract_version": "1.0.0",
                "parameters": [
                    parameter(list_id, "items", "文本列表", "list<string>", required=True),
                    parameter(list_id, "separator", "分隔符", "string", required=False, default="、", control={"control": "text"}),
                ],
                "return_type": "string",
                "targets": ["windows", "android_adb", "none"],
                "permissions": [],
                "timeout_ms": 1_000,
                "contract_tests": [{
                    "test_id": "join-list",
                    "arguments": {
                        f"{list_id}.items": ["窗口", "模拟器", "手机"],
                        f"{list_id}.separator": " / ",
                    },
                    "expected": "窗口 / 模拟器 / 手机",
                }],
            },
        ],
    }


def workspace_contract() -> dict[str, Any]:
    return {
        "workspace_schema_version": 1,
        "contribution_id": f"{PACKAGE_ID}.workspace",
        "workspaces": [{
            "ui_system_version": 1,
            "workspace_id": f"{PACKAGE_ID}.workspace.main",
            "display_name": "扩展展示",
            "topology": "navigator-content-inspector",
            "primary_object": "展示项目",
            "page_actions": [{
                "command_id": f"{PACKAGE_ID}.workspace.create",
                "label": "新建展示项目",
                "level": "primary",
            }],
            "states": ["loading", "error", "empty", "filtered-empty", "selection", "readonly"],
            "has_inspector": True,
            "narrow_behavior": "mutually-exclusive-drawers",
            "keyboard_entry": "从扩展中心打开；键盘焦点按列表、正文、检查器顺序移动",
            "permission_summary": "只读写当前扩展命名空间的展示数据",
            "danger_commands": [],
        }],
    }


SOURCE = '''def decorate_text(context, content, prefix="[扩展] ", uppercase=False):
    result = str(content).upper() if uppercase else str(content)
    context.log("展示扩展：文本装饰完成")
    return f"{prefix}{result}"


def clamp_number(context, value, minimum=0, maximum=100):
    if minimum > maximum:
        raise ValueError("最小值不能大于最大值")
    return float(max(minimum, min(maximum, value)))


def join_text_list(context, items, separator="、"):
    return str(separator).join(str(item) for item in items)
'''


def remove_existing(project: Path) -> None:
    try:
        package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, SCOPE)
    except RuntimeFailure:
        return
    if package.get("enabled"):
        VNextExtensionRegistry.disable(str(project), PACKAGE_ID, SCOPE)
    VNextExtensionRegistry.delete_package(str(project), PACKAGE_ID, SCOPE)


def install(project: Path) -> dict[str, Any]:
    remove_existing(project)
    created = VNextExtensionRegistry.scaffold(
        str(project),
        package_id=PACKAGE_ID,
        publisher_id=PUBLISHER_ID,
        publisher_name="EasyCode Harness",
        display_name="扩展展示与外部函数测试",
        description="可随时卸载的项目级测试扩展，不进入正式产品清单。",
        scope=SCOPE,
    )
    root = Path(created["path"])
    manifest_value = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    function_ids = [item["function_id"] for item in contracts()["functions"]]
    manifest_value["variants"][0]["entrypoints"] = {
        function_ids[0]: "decorate_text",
        function_ids[1]: "clamp_number",
        function_ids[2]: "join_text_list",
    }
    manifest_value["contributions"]["workspaces"] = [{
        "contribution_id": f"{PACKAGE_ID}.workspace",
        "path": "workspaces/main.json",
    }]
    manifest = ExtensionManifestV1.model_validate(manifest_value)
    contract_file = FunctionContractFileV1.model_validate(contracts())
    write_json(root / MANIFEST_FILE, manifest.model_dump(mode="json", exclude_none=True))
    write_json(root / "contracts" / "functions.json", contract_file.model_dump(mode="json"))
    write_json(root / "workspaces" / "main.json", workspace_contract())
    (root / "src" / "main.py").write_text(SOURCE, encoding="utf-8")
    (root / "README.md").write_text(
        "# 扩展展示与外部函数测试\n\n"
        "项目级、可拆卸的中立 Harness。启用后在函数库的“扩展”分页中查看；"
        "双击函数后与官方函数使用方式相同。不要将本目录复制进正式发布项目。\n",
        encoding="utf-8",
    )
    identity = AuthorSigningKeyStore().get_or_create(f"extension:{PUBLISHER_ID}")
    write_json(root / MANIFEST_SIGNATURE_FILE, sign_manifest(root, manifest, identity))
    VNextExtensionRegistry.trust(str(project), PACKAGE_ID, SCOPE, mode="local_development")
    VNextExtensionRegistry.build_sealed(str(project), PACKAGE_ID, SCOPE)
    VNextExtensionRegistry.enable(str(project), PACKAGE_ID, SCOPE)
    tests = VNextExtensionRegistry.contract_tests(str(project), PACKAGE_ID, SCOPE)
    definitions, errors = VNextExtensionRegistry.definitions(str(project))
    return {
        "package_id": PACKAGE_ID,
        "path": str(root),
        "enabled": True,
        "catalog_function_ids": [item["function_id"] for item in definitions if item.get("package_id") == PACKAGE_ID],
        "contract_tests": tests,
        "catalog_errors": errors,
    }


def remove(project: Path) -> dict[str, Any]:
    remove_existing(project)
    return {"package_id": PACKAGE_ID, "removed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "remove", "status"))
    parser.add_argument("--project", type=Path, default=Path(r"D:\PycharmProjects\DDT"))
    args = parser.parse_args()
    project = args.project.resolve()
    if not (project / "project.json").is_file():
        parser.error(f"不是 EasyCode 项目：{project}")
    if args.action == "install":
        result = install(project)
    elif args.action == "remove":
        result = remove(project)
    else:
        result = VNextExtensionRegistry.package(str(project), PACKAGE_ID, SCOPE)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
