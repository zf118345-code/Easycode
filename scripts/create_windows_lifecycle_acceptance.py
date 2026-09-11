"""Create a signed, source-free Windows application lifecycle acceptance bundle.

The bundle is intentionally small and is assembled with an already frozen
EasyCode Player runtime.  Its assertions run inside that frozen runtime:
start an exact executable, observe the same process, stop it, observe its exit,
and reject any accidental false-positive completion.
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

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore, trust_root_document  # noqa: E402
from core.vnext.file_runtime_v6 import windows_file_reference  # noqa: E402
from core.vnext.publish import VNextPublisher  # noqa: E402
from core.vnext.pure_operations_v6 import (  # noqa: E402
    PURE_OPERATION_REGISTRY_VERSION,
    pure_operation_registry_hash,
)
from core.vnext.target_service import TargetConfiguration, target_configuration_revision  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _reference(slot: str) -> dict:
    return {"kind": "reference", "scope": "local", "symbol_id": slot}


def _fail(instruction_id: str, error_id: str, message: str) -> dict:
    return {
        "instruction_id": instruction_id,
        "opcode": "control.fail",
        "arguments": {"error_id": error_id, "message": message, "details": None},
        "result_slot": None,
        "platforms": ["windows", "no_target"],
        "capabilities": [],
        "source": {},
    }


def _assert_true(instruction_id: str, slot: str, error_id: str, message: str) -> dict:
    return {
        "instruction_id": instruction_id,
        "opcode": "control.if",
        "arguments": {
            "condition": _reference(slot),
            "then": [],
            "additional_branches": [],
            "otherwise": [_fail(f"{instruction_id}.fail", error_id, message)],
        },
        "result_slot": None,
        "platforms": ["windows", "no_target"],
        "capabilities": [],
        "source": {},
    }


def _assert_false(instruction_id: str, slot: str, error_id: str, message: str) -> dict:
    return {
        "instruction_id": instruction_id,
        "opcode": "control.if",
        "arguments": {
            "condition": _reference(slot),
            "then": [_fail(f"{instruction_id}.fail", error_id, message)],
            "additional_branches": [],
            "otherwise": [],
        },
        "result_slot": None,
        "platforms": ["windows", "no_target"],
        "capabilities": [],
        "source": {},
    }


def _linked(executable: Path) -> dict:
    file_reference = windows_file_reference(
        str(executable),
        str(executable.parent),
        access=("execute",),
        authorization_root_id="acceptance.windows-lifecycle",
        source="author",
    )
    app = {
        "kind": "record",
        "record_type": "application_ref",
        "fields": {
            "application_ref.field.platform": "windows",
            "application_ref.field.executable": {"kind": "json", "value": file_reference},
        },
    }
    instructions = [
        {
            "instruction_id": "acceptance.application.start",
            "function_id": "official.application.start",
            "opcode": "host.app.start",
            "arguments": {
                "official.application.start.parameter.application": app,
                "official.application.start.parameter.arguments": {"kind": "list", "items": []},
            },
            "parameter_ids": {},
            "result_type": "application_run_ref",
            "result_slot": "application_run",
            "platforms": ["windows", "no_target"],
            "capabilities": ["application.launch", "host.launch_application"],
            "source": {},
        },
        {
            "instruction_id": "acceptance.application.running-before",
            "function_id": "official.application.is_running",
            "opcode": "host.app.is_running",
            "arguments": {
                "official.application.is_running.parameter.process": _reference("application_run"),
            },
            "parameter_ids": {},
            "result_type": "bool",
            "result_slot": "running_before",
            "platforms": ["windows", "no_target"],
            "capabilities": ["application.lifecycle"],
            "source": {},
        },
        _assert_true(
            "acceptance.assert-running-before",
            "running_before",
            "acceptance.application_not_running_after_start",
            "应用启动后未处于运行状态",
        ),
        {
            "instruction_id": "acceptance.application.stop",
            "function_id": "official.application.stop",
            "opcode": "host.app.stop",
            "arguments": {
                "official.application.stop.parameter.process": _reference("application_run"),
                "official.application.stop.parameter.timeout": {"kind": "duration", "milliseconds": 5000},
            },
            "parameter_ids": {},
            "result_type": "bool",
            "result_slot": "stop_result",
            "platforms": ["windows", "no_target"],
            "capabilities": ["application.lifecycle"],
            "source": {},
        },
        _assert_true(
            "acceptance.assert-stop-result",
            "stop_result",
            "acceptance.application_stop_false",
            "应用停止没有返回成功",
        ),
        {
            "instruction_id": "acceptance.application.running-after",
            "function_id": "official.application.is_running",
            "opcode": "host.app.is_running",
            "arguments": {
                "official.application.is_running.parameter.process": _reference("application_run"),
            },
            "parameter_ids": {},
            "result_type": "bool",
            "result_slot": "running_after",
            "platforms": ["windows", "no_target"],
            "capabilities": ["application.lifecycle"],
            "source": {},
        },
        _assert_false(
            "acceptance.assert-not-running-after",
            "running_after",
            "acceptance.application_still_running_after_stop",
            "应用停止后仍处于运行状态",
        ),
        {
            "instruction_id": "acceptance.application.wait-exit",
            "function_id": "official.application.wait_exit",
            "opcode": "host.app.wait_exit",
            "arguments": {
                "official.application.wait_exit.parameter.process": _reference("application_run"),
                "official.application.wait_exit.parameter.timeout": {"kind": "duration", "milliseconds": 1000},
            },
            "parameter_ids": {},
            "result_type": "optional<application_exit_result>",
            "result_slot": "exit_result",
            "platforms": ["windows", "no_target"],
            "capabilities": ["application.lifecycle"],
            "source": {},
        },
        {
            "instruction_id": "acceptance.assert-exit-result",
            "opcode": "control.if",
            "arguments": {
                "condition": {
                    "kind": "compare",
                    "left": _reference("exit_result"),
                    "operator": "ne",
                    "right": None,
                    "operand_type": "optional<application_exit_result>",
                },
                "then": [],
                "additional_branches": [],
                "otherwise": [_fail(
                    "acceptance.assert-exit-result.fail",
                    "acceptance.application_exit_result_missing",
                    "停止后没有取得应用退出结果",
                )],
            },
            "result_slot": None,
            "platforms": ["windows", "no_target"],
            "capabilities": [],
            "source": {},
        },
    ]
    return {
        "diagnostics": [],
        "ecir": {
            "ecir_version": 1,
            "program_model_version": 1,
            "pure_operation_registry": {
                "registry_version": PURE_OPERATION_REGISTRY_VERSION,
                "content_hash": pure_operation_registry_hash(),
            },
            "entry_function_id": "function.windows-lifecycle",
            "target_platform": "windows",
            "supported_platforms": ["windows"],
            "required_capabilities": [
                "application.launch",
                "application.lifecycle",
                "host.launch_application",
            ],
            "functions": [{
                "function_id": "function.windows-lifecycle",
                "name": "Windows 应用生命周期验收",
                "parameters": [],
                "parameter_definitions": [],
                "return_type": "null",
                "instructions": instructions,
            }],
            "project_variables": [],
            "targets": [{
                "target_id": "target.windows-desktop",
                "name": "Windows 全屏幕",
                "type": "windows",
                "window_title": "",
                "window_match": "contains",
                "work_area": {"mode": "desktop"},
                "allow_physical_fallback": True,
            }],
            "default_target_id": "target.windows-desktop",
        },
    }


def create(executable: Path, output: Path) -> dict:
    executable = executable.resolve()
    output = output.resolve()
    if not executable.is_file() or executable.suffix.casefold() != ".exe":
        raise RuntimeError(f"验收程序必须是现有 .exe：{executable}")
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"输出目录必须为空，不会覆盖现有证据：{output}")
    project_root = output / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    _write_json(project_root / "assets" / "registry.json", {
        "schema_version": 1,
        "assets": {},
        "folders": {"image": [], "ocr": [], "page": []},
    })
    _write_json(project_root / "easycode.lock", {
        "lock_version": 1,
        "project_format": 6,
        "toolchain": {
            "compiler_version": "6.0.0",
            "program_schema": 1,
            "ecir": 1,
            "pure_value_registry_version": PURE_OPERATION_REGISTRY_VERSION,
            "pure_value_registry_sha256": pure_operation_registry_hash(),
        },
        "official_functions": [],
        "extensions": [],
    })
    target_values = ({
        "target_id": "target.windows-desktop",
        "name": "Windows 全屏幕",
        "type": "windows",
        "window_title": "",
        "window_match": "contains",
        "work_area": {"mode": "desktop"},
        "allow_physical_fallback": True,
    },)
    targets = TargetConfiguration(
        schema_version=1,
        targets=target_values,
        default_target_id="target.windows-desktop",
    )
    project = {
        "project_id": "acceptance_windows_lifecycle",
        "name": "Windows 应用生命周期验收",
        "targets_schema_version": 1,
        "targets": list(target_values),
        "default_target_id": "target.windows-desktop",
        "target_configuration_revision": target_configuration_revision(targets),
    }
    _write_json(project_root / "project.json", project)
    form = {"schema_version": 3, "title": "Windows 应用生命周期验收", "pages": []}
    linked = _linked(executable)
    signing = AuthorSigningKeyStore(output / "keys")
    publisher = VNextPublisher(str(project_root), signing_key_store=signing)
    report = publisher.report(linked, form)
    if not report.get("valid"):
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
    published = publisher.build(linked, form, project, report)
    bundle = output / "windows-lifecycle.ecplayer"
    shutil.copyfile(published["path"], bundle)
    trust_root = output / "trust-root.json"
    _write_json(trust_root, trust_root_document(published["signature"], project["project_id"]))
    result = {
        "schema_version": 1,
        "executable": str(executable),
        "bundle": str(bundle),
        "trust_root": str(trust_root),
        "release_id": published["release_id"],
        "signature": published["signature"],
    }
    _write_json(output / "harness.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 Windows 应用生命周期真实验收包")
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = create(arguments.executable, arguments.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
