"""Create a signed Player bundle that exercises every terminal field action.

This is a disposable interaction Harness, not a product template.  It keeps
all generated state below the requested output directory and prints the exact
bundle and trust-root paths needed by ``player.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore, trust_root_document
from core.vnext.control_defaults import parameter_ui_for_type
from core.vnext.function_contracts_v6 import OFFICIAL_FUNCTION_CONTRACTS
from core.vnext.player_bindings import player_type_fingerprint
from core.vnext.player_service import VNextPlayerService
from core.vnext.program_contracts import contract_capabilities
from core.vnext.publish import VNextPublisher
from core.vnext.pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash
from core.vnext.target_service import TargetConfiguration, target_configuration_revision


PLATFORMS = ["windows", "android_adb", "android_local"]


_CAPABILITIES_BY_OPCODE: dict[str, tuple[str, ...]] = {}
for _contract in OFFICIAL_FUNCTION_CONTRACTS:
    _current = set(_CAPABILITIES_BY_OPCODE.get(_contract.opcode, ()))
    _current.update(contract_capabilities(_contract))
    _CAPABILITIES_BY_OPCODE[_contract.opcode] = tuple(sorted(_current))


def _attach_instruction_capabilities(value: object) -> None:
    """Make hand-authored Harness ECIR obey the compiler's closure contract."""

    if isinstance(value, list):
        for item in value:
            _attach_instruction_capabilities(item)
        return
    if not isinstance(value, dict):
        return
    if value.get("instruction_id") and value.get("opcode"):
        value["capabilities"] = list(_CAPABILITIES_BY_OPCODE.get(str(value["opcode"]), ()))
    for item in value.values():
        _attach_instruction_capabilities(item)


def _instruction_capability_closure(value: object) -> list[str]:
    capabilities: set[str] = set()
    if isinstance(value, list):
        for item in value:
            capabilities.update(_instruction_capability_closure(item))
    elif isinstance(value, dict):
        if value.get("instruction_id") and value.get("opcode"):
            capabilities.update(str(item) for item in value.get("capabilities", []))
        for item in value.values():
            capabilities.update(_instruction_capability_closure(item))
    return sorted(capabilities)


def _field(
    control_id: str,
    label: str,
    value_type: str,
    *,
    default: object | None = None,
    constraints: dict[str, object] | None = None,
    actions: list[str] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    safe_constraints = dict(constraints or {})
    # Capture fields start empty until the user explicitly records or selects
    # a value.  Model that state in the type instead of publishing an invalid
    # ``None`` default for a required reference type.
    declared_type = (
        value_type
        if default is not None or value_type.startswith("optional<")
        else f"optional<{value_type}>"
    )
    parameter_ui = parameter_ui_for_type(declared_type)
    allowed = actions or [str(item["id"]) for item in parameter_ui["actions"]]
    terminal_actions = []
    for action in parameter_ui["actions"]:
        if str(action["id"]) not in allowed:
            continue
        terminal_actions.append({
            "action_id": str(action["id"]),
            "platforms": list(action["platforms"]),
        })
    variable_id = f"variable_{control_id}"
    variable = {
        "variable_id": variable_id,
        "display_name": label,
        "value_type": declared_type,
        "default_value": default,
        # File extensions and similar terminal-picker restrictions belong to
        # the Player control.  They are not scalar project-value constraints.
        "constraints": {},
    }
    control = {
        "control_id": control_id,
        "type": parameter_ui["control"],
        "label": label,
        "help": "由作者明确开放；系统返回前保持当前值不变。",
        "required": False,
        "binding": {"kind": "project_variable", "variable_id": variable_id},
        "source_type": declared_type,
        "type_fingerprint": player_type_fingerprint(declared_type, {}),
        "platforms": list(PLATFORMS),
        "constraints": safe_constraints,
        "parameter_ui": parameter_ui,
        "terminal_actions": terminal_actions,
    }
    if default is not None:
        control["default"] = default
    return variable, control


def create_fixture(
    output_root: Path,
    *,
    adb_serials: tuple[str, ...] = (),
    include_android_local: bool = False,
    exercise_android_runtime: bool = False,
    exercise_android_controls: bool = False,
    exercise_android_vision_marker: bool = False,
    exercise_android_files: bool = False,
    exercise_android_remaining_basics: bool = False,
    exercise_android_recording: bool = False,
    exercise_android_messages: bool = False,
    exercise_android_message_listener: bool = False,
    android_message_recipient: str = "",
    android_application_id: str = "com.easycode.player.emulator.debug",
) -> dict[str, str]:
    if (
        exercise_android_runtime
        or exercise_android_controls
        or exercise_android_vision_marker
        or exercise_android_files
        or exercise_android_remaining_basics
        or exercise_android_recording
        or exercise_android_messages
        or exercise_android_message_listener
    ) and not include_android_local:
        raise ValueError("Android 运行验证只能与 --include-android-local 一起使用")
    if exercise_android_vision_marker and not exercise_android_controls:
        raise ValueError("--exercise-android-vision-marker 需要同时启用 --exercise-android-controls")
    if exercise_android_remaining_basics and not (
        exercise_android_runtime and exercise_android_files
    ):
        raise ValueError(
            "--exercise-android-remaining-basics 需要同时启用 "
            "--exercise-android-runtime 与 --exercise-android-files"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="player-capture-", dir=output_root))
    project_root = root / "project"
    assets = project_root / "assets"
    assets.mkdir(parents=True)
    marker_asset_id = "asset_android_vision_marker"
    registry_assets: dict[str, object] = {}
    if exercise_android_vision_marker:
        marker_path = assets / "image" / f"{marker_asset_id}.png"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker = Image.new("RGB", (64, 64))
        pixels = marker.load()
        for y in range(64):
            for x in range(64):
                pixels[x, y] = (
                    (255, 255, 255) if 27 <= x <= 36 or 27 <= y <= 36 else
                    (230, 70, 50) if x < 32 and y < 32 else
                    (40, 180, 90) if x >= 32 and y < 32 else
                    (50, 100, 220) if x < 32 else
                    (245, 195, 40)
                )
        marker.save(marker_path, format="PNG", optimize=False)
        marker_bytes = marker_path.read_bytes()
        registry_assets[marker_asset_id] = {
            "asset_id": marker_asset_id,
            "display_name": "Android 图像测试标记",
            "category": "image",
            "folder": "",
            "path": f"assets/image/{marker_asset_id}.png",
            "extension": ".png",
            "mime_type": "image/png",
            "size_bytes": len(marker_bytes),
            "width": 64,
            "height": 64,
            "sha256": hashlib.sha256(marker_bytes).hexdigest(),
            "source": "generated-harness",
            "aliases": [],
        }
    (assets / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "assets": registry_assets,
        "folders": {"image": [], "ocr": [], "page": []},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    (project_root / "easycode.lock").write_text(json.dumps({
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
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    specs = [
        ("point", "点击坐标", "point", {"kind": "point", "x": 480, "y": 320}, {}, None),
        ("region", "识别区域", "rect", {"x": 120, "y": 100, "width": 640, "height": 360}, {}, None),
        ("image", "目标图片", "asset_ref<image>", None, {}, None),
        ("path", "拖拽路径", "path", None, {}, None),
        ("control", "控件", "control_selector", None, {}, ["capture-control"]),
        ("input_file", "读取文件", "file_ref<read>", None, {"extensions": [".json", ".txt"]}, None),
        ("output_file", "保存文件", "file_ref<write>", None, {"extensions": [".json", ".txt"]}, None),
        ("directory", "工作目录", "directory_ref<list>", None, {}, None),
    ]
    variables: list[dict[str, object]] = []
    controls: list[dict[str, object]] = []
    for control_id, label, value_type, default, constraints, actions in specs:
        variable, control = _field(
            control_id, label, value_type,
            default=default, constraints=constraints, actions=actions,
        )
        variables.append(variable)
        controls.append(control)
    if exercise_android_message_listener:
        # This is an assertion flag for the disposable Harness, not a Player
        # field.  It prevents an empty listener wait window from being
        # reported as successful merely because the main flow completed.
        variables.append({
            "variable_id": "variable_listener_received",
            "display_name": "监听消息已处理",
            "value_type": "bool",
            "default_value": False,
            "constraints": {},
        })

    windows_target = {
        "target_id": "target_windows",
        "name": "Windows 测试窗口",
        "type": "windows",
        "window_title": "EasyCode Capture Harness",
        "window_match": "contains",
        "work_area": {"mode": "client"},
        "allow_physical_fallback": True,
    }
    if include_android_local:
        if adb_serials:
            raise ValueError("Android 本机 Harness 不能同时声明 Windows/ADB 目标")
        targets: list[dict[str, object]] = [{
            "target_id": "target_android_local",
            "name": "当前 Android 设备",
            "type": "android_local",
        }]
        default_target_id = "target_android_local"
    else:
        targets = [windows_target]
        for index, serial in enumerate(adb_serials, start=1):
            clean_serial = serial.strip()
            if not clean_serial:
                raise ValueError("--adb-serial 不能为空")
            targets.append({
                "target_id": f"target_adb_{index}",
                "name": f"ADB 设备 {index} · {clean_serial}",
                "type": "android_adb",
                "device_serial": clean_serial,
            })
        default_target_id = "target_windows"
    instructions: list[dict[str, object]] = []
    required_capabilities: list[str] = []
    if exercise_android_runtime:
        required_capabilities.append("frame.read")
        instructions = [
            {
                "instruction_id": "statement_capture_frame",
                "opcode": "target.capture_frame",
                "arguments": {},
                "result_slot": "local_frame",
            },
            {
                "instruction_id": "statement_ocr",
                "opcode": "text.recognize",
                "arguments": {
                    "official.text.recognize.parameter.region": None,
                    "official.text.recognize.parameter.language": "auto",
                    "official.text.recognize.parameter.frame": {
                        "kind": "reference",
                        "scope": "local",
                        "symbol_id": "local_frame",
                    },
                    "official.text.recognize.parameter.preprocess": {
                        "ocr_preprocess.field.grayscale": False,
                        "ocr_preprocess.field.binary": False,
                        "ocr_preprocess.field.threshold": 127,
                        "ocr_preprocess.field.invert": False,
                    },
                },
                "result_slot": "local_ocr",
            },
            {
                "instruction_id": "statement_log_ocr",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-harness",
                    "official.log.output.parameter.content": {
                        "kind": "member_access",
                        "source": {
                            "kind": "reference",
                            "scope": "local",
                            "symbol_id": "local_ocr",
                        },
                        "field_id": "ocr_result.field.text",
                    },
                },
            },
            {
                "instruction_id": "statement_text_match",
                "opcode": "standard.text.match",
                "arguments": {
                    "official.text.match.parameter.text": "Player",
                    "official.text.match.parameter.mode": "contains",
                    "official.text.match.parameter.region": None,
                    "official.text.match.parameter.language": "auto",
                },
                "result_slot": "local_text_match",
            },
            {
                "instruction_id": "statement_text_wait",
                "opcode": "standard.text.wait_visible",
                "arguments": {
                    "official.text.wait_visible.parameter.text": "Player",
                    "official.text.wait_visible.parameter.mode": "contains",
                    "official.text.wait_visible.parameter.region": None,
                    "official.text.wait_visible.parameter.language": "auto",
                    "official.text.wait_visible.parameter.timeout": 3000,
                    "official.text.wait_visible.parameter.interval": 100,
                    "official.text.wait_visible.parameter.stable_frames": 1,
                },
                "result_slot": "local_text_wait",
            },
            {
                "instruction_id": "statement_log_standard_text",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-harness",
                    "official.log.output.parameter.content": "文字匹配与等待流程已执行",
                },
            },
        ]
    if exercise_android_controls:
        required_capabilities.extend([
            "application.launch", "control.semantic", "target.input", "input.key",
        ])
        if exercise_android_vision_marker:
            required_capabilities.append("target.capture_frame")
        input_selector = {
            "control_selector.field.provider": "android_accessibility",
            "control_selector.field.target_id": "target_android_local",
            "control_selector.field.package_name": android_application_id,
            "control_selector.field.resource_id": "",
            "control_selector.field.text": "",
            "control_selector.field.content_description": "EasyCode 测试输入框",
            "control_selector.field.class_name": "android.widget.EditText",
            "control_selector.field.index": 0,
            "control_selector.field.path": [],
        }
        button_selector = {
            "control_selector.field.provider": "android_accessibility",
            "control_selector.field.target_id": "target_android_local",
            "control_selector.field.package_name": android_application_id,
            "control_selector.field.resource_id": "",
            "control_selector.field.text": "",
            "control_selector.field.content_description": "EasyCode 测试确认",
            "control_selector.field.class_name": "android.widget.Button",
            "control_selector.field.index": 0,
            "control_selector.field.path": [],
        }
        result_selector = {
            "control_selector.field.provider": "android_accessibility",
            "control_selector.field.target_id": "target_android_local",
            "control_selector.field.package_name": android_application_id,
            "control_selector.field.resource_id": "",
            "control_selector.field.text": "",
            "control_selector.field.content_description": "EasyCode 测试结果",
            "control_selector.field.class_name": "android.widget.TextView",
            "control_selector.field.index": 0,
            "control_selector.field.path": [],
        }
        coordinate_button_selector = {
            "control_selector.field.provider": "android_accessibility",
            "control_selector.field.target_id": "target_android_local",
            "control_selector.field.package_name": android_application_id,
            "control_selector.field.resource_id": "",
            "control_selector.field.text": "",
            "control_selector.field.content_description": "EasyCode 坐标测试",
            "control_selector.field.class_name": "android.widget.Button",
            "control_selector.field.index": 0,
            "control_selector.field.path": [],
        }
        gesture_selector = {
            "control_selector.field.provider": "android_accessibility",
            "control_selector.field.target_id": "target_android_local",
            "control_selector.field.package_name": android_application_id,
            "control_selector.field.resource_id": "",
            "control_selector.field.text": "",
            "control_selector.field.content_description": "EasyCode 手势测试区",
            "control_selector.field.class_name": "",
            "control_selector.field.index": 0,
            "control_selector.field.path": [],
        }
        instructions.extend([
            {
                "instruction_id": "statement_start_semantic_harness",
                "opcode": "host.app.start",
                "arguments": {
                    "official.application.start.parameter.application": {
                        "application_ref.field.platform": "android_local",
                        "application_ref.field.package": android_application_id,
                        # The debug applicationId has flavor/build suffixes,
                        # while the compiled Activity keeps the stable Kotlin
                        # namespace. A fully-qualified component is required.
                        "application_ref.field.activity": "com.easycode.player.input.SemanticControlHarnessActivity",
                    },
                    "official.application.start.parameter.arguments": [],
                },
                "result_slot": "local_application_run",
            },
            {
                "instruction_id": "statement_wait_semantic_harness",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 800},
            },
            {
                "instruction_id": "statement_find_semantic_input",
                "opcode": "control.find",
                "arguments": {"official.control.find.parameter.selector": input_selector},
                "result_slot": "local_semantic_input",
            },
            {
                "instruction_id": "statement_input_semantic_text",
                "opcode": "control.input_text",
                "arguments": {
                    "official.control.type_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_input",
                    },
                    "official.control.type_text.parameter.content": "EasyCode Android 控件已验证",
                    "official.control.type_text.parameter.mode": "auto",
                },
            },
            {
                "instruction_id": "statement_wait_semantic_input_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_read_semantic_input",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_input",
                    },
                },
                "result_slot": "local_semantic_input_text",
            },
            {
                "instruction_id": "statement_log_semantic_input",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-control-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_input_text",
                    },
                },
            },
            {
                "instruction_id": "statement_focus_semantic_input",
                "opcode": "control.click",
                "arguments": {
                    "official.control.click.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_input",
                    },
                    "official.control.click.parameter.mode": "auto",
                },
            },
            {
                "instruction_id": "statement_input_focused_text",
                "opcode": "input.text",
                "arguments": {
                    "official.input.type_text.parameter.content": "EasyCode 直接输入已验证",
                    "official.input.type_text.parameter.mode": "auto",
                },
            },
            {
                "instruction_id": "statement_wait_focused_input_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_read_focused_input",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_input",
                    },
                },
                "result_slot": "local_focused_input_text",
            },
            {
                "instruction_id": "statement_log_focused_input",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-input-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_focused_input_text",
                    },
                },
            },
            {
                "instruction_id": "statement_hide_keyboard",
                "opcode": "input.key",
                "arguments": {
                    "official.input.key.parameter.key": "back",
                    "official.input.key.parameter.action": "press",
                    "official.input.key.parameter.hold": 0,
                },
            },
            {
                "instruction_id": "statement_wait_keyboard_hidden",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_find_semantic_button",
                "opcode": "control.find",
                "arguments": {"official.control.find.parameter.selector": button_selector},
                "result_slot": "local_semantic_button",
            },
            {
                "instruction_id": "statement_click_semantic_button",
                "opcode": "control.click",
                "arguments": {
                    "official.control.click.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_button",
                    },
                    "official.control.click.parameter.mode": "auto",
                },
            },
            {
                "instruction_id": "statement_wait_semantic_click_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_find_semantic_result",
                "opcode": "control.find",
                "arguments": {"official.control.find.parameter.selector": result_selector},
                "result_slot": "local_semantic_result",
            },
            {
                "instruction_id": "statement_read_semantic_result",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_result",
                    },
                },
                "result_slot": "local_semantic_result_text",
            },
            {
                "instruction_id": "statement_log_semantic_result",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-control-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_result_text",
                    },
                },
            },
            {
                "instruction_id": "statement_find_coordinate_button",
                "opcode": "control.find",
                "arguments": {"official.control.find.parameter.selector": coordinate_button_selector},
                "result_slot": "local_coordinate_button",
            },
            {
                "instruction_id": "statement_click_derived_coordinate",
                "opcode": "input.click",
                "arguments": {
                    "official.input.click.parameter.position": {
                        "kind": "operation",
                        "operation_id": "core.rect_center.v1",
                        "result_type": "point",
                        "inputs": {
                            "core.rect_center.v1.input.rect": {
                                "kind": "member_access",
                                "source": {
                                    "kind": "reference",
                                    "scope": "local",
                                    "symbol_id": "local_coordinate_button",
                                },
                                "field_id": "control_ref.field.rect",
                            },
                        },
                    },
                    "official.input.click.parameter.button": "primary",
                    "official.input.click.parameter.count": 1,
                    "official.input.click.parameter.hold": 0,
                    "official.input.click.parameter.interval": 80,
                },
            },
            {
                "instruction_id": "statement_wait_coordinate_click_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_read_coordinate_result",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_result",
                    },
                },
                "result_slot": "local_coordinate_result_text",
            },
            {
                "instruction_id": "statement_log_coordinate_result",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-input-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_coordinate_result_text",
                    },
                },
            },
            {
                "instruction_id": "statement_find_gesture_surface",
                "opcode": "control.find",
                "arguments": {"official.control.find.parameter.selector": gesture_selector},
                "result_slot": "local_gesture_surface",
            },
            {
                "instruction_id": "statement_drag_gesture_surface",
                "opcode": "input.drag",
                "arguments": {
                    "official.input.drag.parameter.path": {
                        "kind": "path",
                        "points": [
                            {
                                "kind": "operation",
                                "operation_id": "core.rect_center.v1",
                                "result_type": "point",
                                "inputs": {
                                    "core.rect_center.v1.input.rect": {
                                        "kind": "member_access",
                                        "source": {"kind": "reference", "scope": "local", "symbol_id": "local_gesture_surface"},
                                        "field_id": "control_ref.field.rect",
                                    },
                                },
                            },
                            {
                                "kind": "operation",
                                "operation_id": "core.point_offset.v1",
                                "result_type": "point",
                                "inputs": {
                                    "core.point_offset.v1.input.point": {
                                        "kind": "operation",
                                        "operation_id": "core.rect_center.v1",
                                        "result_type": "point",
                                        "inputs": {
                                            "core.rect_center.v1.input.rect": {
                                                "kind": "member_access",
                                                "source": {"kind": "reference", "scope": "local", "symbol_id": "local_gesture_surface"},
                                                "field_id": "control_ref.field.rect",
                                            },
                                        },
                                    },
                                    "core.point_offset.v1.input.offset": {"kind": "point", "x": 120, "y": 0},
                                },
                            },
                        ],
                    },
                    "official.input.drag.parameter.duration": 350,
                    "official.input.drag.parameter.easing": "linear",
                },
            },
            {
                "instruction_id": "statement_wait_drag_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_read_drag_result",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_result",
                    },
                },
                "result_slot": "local_drag_result_text",
            },
            {
                "instruction_id": "statement_log_drag_result",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-input-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_drag_result_text",
                    },
                },
            },
            {
                "instruction_id": "statement_scroll_gesture_surface",
                "opcode": "input.scroll",
                "arguments": {
                    "official.input.scroll.parameter.direction": "down",
                    "official.input.scroll.parameter.mode": "touch",
                    "official.input.scroll.parameter.distance": 0.1,
                    "official.input.scroll.parameter.start": {
                        "kind": "operation",
                        "operation_id": "core.rect_center.v1",
                        "result_type": "point",
                        "inputs": {
                            "core.rect_center.v1.input.rect": {
                                "kind": "member_access",
                                "source": {"kind": "reference", "scope": "local", "symbol_id": "local_gesture_surface"},
                                "field_id": "control_ref.field.rect",
                            },
                        },
                    },
                    "official.input.scroll.parameter.duration": 350,
                    "official.input.scroll.parameter.hold": 80,
                },
            },
            {
                "instruction_id": "statement_wait_scroll_commit",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 250},
            },
            {
                "instruction_id": "statement_read_scroll_result",
                "opcode": "control.read_text",
                "arguments": {
                    "official.control.read_text.parameter.control": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_semantic_result",
                    },
                },
                "result_slot": "local_scroll_result_text",
            },
            {
                "instruction_id": "statement_log_scroll_result",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-input-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_scroll_result_text",
                    },
                },
            },
            *([
                {
                    "instruction_id": "statement_capture_vision_marker_frame",
                    "opcode": "target.capture_frame",
                    "arguments": {},
                    "result_slot": "local_vision_marker_frame",
                },
                {
                    "instruction_id": "statement_find_vision_marker",
                    "opcode": "vision.find",
                    "arguments": {
                        "official.image.find.parameter.image": {
                            "kind": "asset_ref", "asset_id": marker_asset_id,
                        },
                        "official.image.find.parameter.similarity": 0.98,
                        "official.image.find.parameter.region": None,
                        "official.image.find.parameter.frame": {
                            "kind": "reference", "scope": "local", "symbol_id": "local_vision_marker_frame",
                        },
                    },
                    "result_slot": "local_vision_marker_match",
                },
                {
                    "instruction_id": "statement_log_vision_marker_similarity",
                    "opcode": "log.write",
                    "arguments": {
                        "official.log.output.parameter.level": "info",
                        "official.log.output.parameter.category": "android-vision-harness",
                        "official.log.output.parameter.content": {
                            "kind": "member_access",
                            "source": {"kind": "reference", "scope": "local", "symbol_id": "local_vision_marker_match"},
                            "field_id": "image_match.field.similarity",
                        },
                    },
                },
                {
                    "instruction_id": "statement_wait_vision_marker",
                    "opcode": "standard.image.wait_visible",
                    "arguments": {
                        "official.image.wait_visible.parameter.image": {
                            "kind": "asset_ref", "asset_id": marker_asset_id,
                        },
                        "official.image.wait_visible.parameter.similarity": 0.98,
                        "official.image.wait_visible.parameter.region": None,
                        "official.image.wait_visible.parameter.timeout": 3000,
                        "official.image.wait_visible.parameter.interval": 100,
                        "official.image.wait_visible.parameter.stable_frames": 1,
                    },
                    "result_slot": "local_vision_marker_wait",
                },
                {
                    "instruction_id": "statement_log_vision_marker_wait",
                    "opcode": "log.write",
                    "arguments": {
                        "official.log.output.parameter.level": "info",
                        "official.log.output.parameter.category": "android-vision-harness",
                        "official.log.output.parameter.content": "Android 图像查找与等待已验证",
                    },
                },
            ] if exercise_android_vision_marker else []),
            {
                "instruction_id": "statement_return_to_player",
                "opcode": "input.key",
                "arguments": {
                    "official.input.key.parameter.key": "back",
                    "official.input.key.parameter.action": "press",
                    "official.input.key.parameter.hold": 0,
                },
            },
            {
                "instruction_id": "statement_log_return_to_player",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-input-harness",
                    "official.log.output.parameter.content": "Android 返回键已验证",
                },
            },
        ])
    if exercise_android_files:
        data_directory = {
            "kind": "reference", "scope": "local", "symbol_id": "local_project_data",
        }

        def child_file(result_type: str, name: str) -> dict[str, object]:
            return {
                "kind": "operation",
                "operation_id": "core.file_ref_child.v1",
                "result_type": result_type,
                "inputs": {
                    "core.file_ref_child.v1.input.directory": data_directory,
                    "core.file_ref_child.v1.input.relative_path": name,
                },
            }

        instructions.extend([
            {
                "instruction_id": "statement_project_data_directory",
                "opcode": "project.data_directory",
                "arguments": {},
                "result_slot": "local_project_data",
            },
            {
                "instruction_id": "statement_write_private_text",
                "opcode": "file.write_text",
                "arguments": {
                    "official.file.write_text.parameter.file": child_file("file_ref<write>", "g6-runtime.txt"),
                    "official.file.write_text.parameter.content": "EasyCode Android 文件已验证",
                    "official.file.write_text.parameter.encoding": "utf-8",
                },
            },
            {
                "instruction_id": "statement_append_private_text",
                "opcode": "file.append_text",
                "arguments": {
                    "official.file.append_text.parameter.file": child_file("file_ref<write>", "g6-runtime.txt"),
                    "official.file.append_text.parameter.content": "\n追加已验证",
                    "official.file.append_text.parameter.encoding": "utf-8",
                },
            },
            {
                "instruction_id": "statement_replace_private_text",
                "opcode": "file.replace_text",
                "arguments": {
                    "official.file.replace_text.parameter.file": child_file("file_ref<write>", "g6-runtime.txt"),
                    "official.file.replace_text.parameter.search": "追加已验证",
                    "official.file.replace_text.parameter.replacement": "替换已验证",
                    "official.file.replace_text.parameter.scope": "all",
                    "official.file.replace_text.parameter.encoding": "utf-8",
                },
                "result_slot": "local_replace_count",
            },
            {
                "instruction_id": "statement_read_private_text",
                "opcode": "file.read_text",
                "arguments": {
                    "official.file.read_text.parameter.file": child_file("file_ref<read>", "g6-runtime.txt"),
                    "official.file.read_text.parameter.encoding": "utf-8",
                },
                "result_slot": "local_private_text",
            },
            {
                "instruction_id": "statement_log_private_text",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-file-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_private_text",
                    },
                },
            },
            {
                "instruction_id": "statement_write_private_json",
                "opcode": "file.write_json",
                "arguments": {
                    "official.file.write_json.parameter.file": child_file("file_ref<write>", "g6-runtime.json"),
                    "official.file.write_json.parameter.data": {
                        "verified": True, "platform": "android_local", "sequence": [1, 2, 3],
                    },
                },
            },
            {
                "instruction_id": "statement_read_private_json",
                "opcode": "file.read_json",
                "arguments": {
                    "official.file.read_json.parameter.file": child_file("file_ref<read>", "g6-runtime.json"),
                },
                "result_slot": "local_private_json",
            },
            {
                "instruction_id": "statement_log_private_json",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-file-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_private_json",
                    },
                },
            },
            {
                "instruction_id": "statement_list_private_directory",
                "opcode": "directory.list",
                "arguments": {
                    "official.directory.list.parameter.directory": data_directory,
                    "official.directory.list.parameter.filter": {},
                    "official.directory.list.parameter.recursive": False,
                },
                "result_slot": "local_private_entries",
            },
            {
                "instruction_id": "statement_log_private_directory",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-file-harness",
                    "official.log.output.parameter.content": {
                        "kind": "reference", "scope": "local", "symbol_id": "local_private_entries",
                    },
                },
            },
        ])
        if exercise_android_remaining_basics:
            required_capabilities.extend([
                "target.capture_frame", "filesystem", "host.clipboard",
                "clipboard_read", "clipboard_write",
            ])
            instructions.extend([
                {
                    "instruction_id": "statement_save_android_frame",
                    "opcode": "frame.save",
                    "function_id": "official.frame.save",
                    "arguments": {
                        "official.frame.save.parameter.file": child_file(
                            "file_ref<write>", "android-frame.png",
                        ),
                        "official.frame.save.parameter.frame": {
                            "kind": "reference", "scope": "local",
                            "symbol_id": "local_frame",
                        },
                        "official.frame.save.parameter.region": None,
                        "official.frame.save.parameter.format": "png",
                        "official.frame.save.parameter.quality": 90,
                    },
                    "result_slot": "local_saved_frame",
                },
                {
                    "instruction_id": "statement_android_frame_exists",
                    "opcode": "file.exists",
                    "function_id": "official.file.exists",
                    "arguments": {
                        "official.file.exists.parameter.file": child_file(
                            "file_ref<read>", "android-frame.png",
                        ),
                    },
                    "result_slot": "local_saved_frame_exists",
                },
                {
                    "instruction_id": "statement_assert_android_frame_saved",
                    "opcode": "control.if",
                    "arguments": {
                        "condition": {
                            "kind": "reference", "scope": "local",
                            "symbol_id": "local_saved_frame_exists",
                        },
                        "then": [],
                        "additional_branches": [],
                        "otherwise": [{
                            "instruction_id": "statement_fail_android_frame_save",
                            "opcode": "control.fail",
                            "arguments": {
                                "error_id": "harness.android_frame_not_saved",
                                "message": "Android 画面保存后目标文件不存在",
                            },
                        }],
                    },
                },
                {
                    "instruction_id": "statement_read_android_color",
                    "opcode": "color.read",
                    "function_id": "official.color.read",
                    "arguments": {
                        "official.color.read.parameter.position": {
                            "kind": "point", "x": 0, "y": 0,
                        },
                        "official.color.read.parameter.frame": {
                            "kind": "reference", "scope": "local",
                            "symbol_id": "local_frame",
                        },
                    },
                    "result_slot": "local_android_color",
                },
                {
                    "instruction_id": "statement_find_android_color",
                    "opcode": "color.find",
                    "function_id": "official.color.find",
                    "arguments": {
                        "official.color.find.parameter.color": {
                            "kind": "reference", "scope": "local",
                            "symbol_id": "local_android_color",
                        },
                        "official.color.find.parameter.tolerance": 0,
                        "official.color.find.parameter.region": None,
                        "official.color.find.parameter.frame": {
                            "kind": "reference", "scope": "local",
                            "symbol_id": "local_frame",
                        },
                    },
                    "result_slot": "local_android_color_point",
                },
                {
                    "instruction_id": "statement_assert_android_color_found",
                    "opcode": "control.if",
                    "arguments": {
                        "condition": {
                            "kind": "compare", "operator": "ne",
                            "operand_type": "optional<point>",
                            "left": {
                                "kind": "reference", "scope": "local",
                                "symbol_id": "local_android_color_point",
                            },
                            "right": None,
                        },
                        "then": [],
                        "additional_branches": [],
                        "otherwise": [{
                            "instruction_id": "statement_fail_android_color_find",
                            "opcode": "control.fail",
                            "arguments": {
                                "error_id": "harness.android_color_not_found",
                                "message": "Android 从同一帧读取的颜色无法重新找到",
                            },
                        }],
                    },
                },
                {
                    "instruction_id": "statement_write_android_clipboard",
                    "opcode": "clipboard.write_text",
                    "function_id": "official.clipboard.write_text",
                    "arguments": {
                        "official.clipboard.write_text.parameter.content":
                            "EasyCode Android 剪贴板已验证",
                    },
                },
                {
                    "instruction_id": "statement_read_android_clipboard",
                    "opcode": "clipboard.read_text",
                    "function_id": "official.clipboard.read_text",
                    "arguments": {},
                    "result_slot": "local_android_clipboard",
                },
                {
                    "instruction_id": "statement_assert_android_clipboard",
                    "opcode": "control.if",
                    "arguments": {
                        "condition": {
                            "kind": "compare", "operator": "eq",
                            "operand_type": "optional<string>",
                            "left": {
                                "kind": "reference", "scope": "local",
                                "symbol_id": "local_android_clipboard",
                            },
                            "right": "EasyCode Android 剪贴板已验证",
                        },
                        "then": [{
                            "instruction_id": "statement_log_android_remaining_basics",
                            "opcode": "log.write",
                            "function_id": "official.log.output",
                            "arguments": {
                                "official.log.output.parameter.level": "info",
                                "official.log.output.parameter.category":
                                    "android-basics-harness",
                                "official.log.output.parameter.content":
                                    "Android 画面保存、颜色与剪贴板已验证",
                            },
                        }],
                        "additional_branches": [],
                        "otherwise": [{
                            "instruction_id": "statement_fail_android_clipboard",
                            "opcode": "control.fail",
                            "arguments": {
                                "error_id": "harness.android_clipboard_mismatch",
                                "message": "Android 剪贴板写入后读回内容不一致",
                            },
                        }],
                    },
                },
            ])
    if exercise_android_recording:
        instructions.extend([
            {
                "instruction_id": "statement_recording_window",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 5_000},
            },
            {
                "instruction_id": "statement_log_recording_window",
                "opcode": "log.write",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-recording-harness",
                    "official.log.output.parameter.content": "Android 本机多帧录制窗口已完成",
                },
            },
        ])
    if exercise_android_messages:
        instructions.extend([
            {
                "instruction_id": "statement_wait_real_lan_message",
                "opcode": "message.wait_receive",
                "function_id": "official.message.wait_receive",
                "arguments": {
                    "official.message.wait_receive.parameter.name": "真实互通测试",
                    "official.message.wait_receive.parameter.sender": None,
                    "official.message.wait_receive.parameter.timeout": 10_000,
                },
                "result_slot": "local_real_lan_message",
            },
            {
                "instruction_id": "statement_assert_real_lan_message",
                "opcode": "control.if",
                "arguments": {
                    "condition": {
                        "kind": "compare",
                        "operator": "ne",
                        "operand_type": "optional<received_message>",
                        "left": {
                            "kind": "reference",
                            "scope": "local",
                            "symbol_id": "local_real_lan_message",
                        },
                        "right": None,
                    },
                    "then": [{
                        "instruction_id": "statement_log_real_lan_message",
                        "opcode": "log.write",
                        "function_id": "official.log.output",
                        "arguments": {
                            "official.log.output.parameter.level": "info",
                            "official.log.output.parameter.category": "android-message-harness",
                            "official.log.output.parameter.content": "Android 已通过项目脚本读取真实 LAN 消息",
                        },
                    }],
                    "additional_branches": [],
                    "otherwise": [{
                        "instruction_id": "statement_fail_missing_real_lan_message",
                        "opcode": "control.fail",
                        "arguments": {
                            "error_id": "harness.message_not_received",
                            "message": "等待窗口内没有收到真实 LAN 消息",
                        },
                    }],
                },
            },
        ])
    if exercise_android_message_listener:
        required_capabilities.append("messaging")
        instructions.extend([
            {
                "instruction_id": "statement_log_listener_main_before",
                "opcode": "log.write",
                "function_id": "official.log.output",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-listener-harness",
                    "official.log.output.parameter.content": "监听主流程：开始等待",
                },
            },
            {
                "instruction_id": "statement_listen_real_lan_message",
                "opcode": "control.listen",
                "arguments": {
                    "event_source": {
                        "kind": "message",
                        "name": "监听互通测试",
                        "sender": None,
                    },
                    "receive_slot": "local_listener_message",
                    "condition": None,
                    "handler_function_id": "function_listener_handler",
                    "handler_arguments": {
                        "parameter_listener_message": {
                            "kind": "reference",
                            "scope": "local",
                            "symbol_id": "local_listener_message",
                        },
                    },
                    "dispatch": {
                        "serial": True,
                        "fifo": True,
                        "safe_checkpoint": True,
                    },
                },
            },
            {
                "instruction_id": "statement_listener_wait_window",
                "opcode": "wait.duration",
                "arguments": {"official.wait.duration.parameter.duration": 8_000},
            },
            {
                "instruction_id": "statement_assert_listener_message",
                "opcode": "control.if",
                "arguments": {
                    "condition": {
                        "kind": "reference",
                        "scope": "project",
                        "variable_id": "variable_listener_received",
                    },
                    "then": [{
                        "instruction_id": "statement_log_listener_main_after",
                        "opcode": "log.write",
                        "function_id": "official.log.output",
                        "arguments": {
                            "official.log.output.parameter.level": "info",
                            "official.log.output.parameter.category": "android-listener-harness",
                            "official.log.output.parameter.content": "监听主流程：处理后继续并完成",
                        },
                    }],
                    "additional_branches": [],
                    "otherwise": [{
                        "instruction_id": "statement_fail_missing_listener_message",
                        "opcode": "control.fail",
                        "arguments": {
                            "error_id": "harness.listener_not_dispatched",
                            "message": "监听窗口内没有处理真实 LAN 消息",
                        },
                    }],
                },
            },
        ])
    if android_message_recipient:
        instructions.extend([
            {
                "instruction_id": "statement_send_real_lan_message",
                "opcode": "message.send",
                "function_id": "official.message.send",
                "arguments": {
                    "official.message.send.parameter.recipients": [{
                        "kind": "entity_ref",
                        "reference_type": "instance_ref",
                        "reference_id": android_message_recipient,
                    }],
                    "official.message.send.parameter.name": "真实互通测试",
                    "official.message.send.parameter.content": {
                        "room_code": "317",
                        "source": "android",
                        "sequence": 1,
                    },
                    "official.message.send.parameter.ttl": 600_000,
                },
                "result_slot": "local_real_lan_batch",
            },
            {
                "instruction_id": "statement_send_real_listener_message",
                "opcode": "message.send",
                "function_id": "official.message.send",
                "arguments": {
                    "official.message.send.parameter.recipients": [{
                        "kind": "entity_ref",
                        "reference_type": "instance_ref",
                        "reference_id": android_message_recipient,
                    }],
                    "official.message.send.parameter.name": "监听互通测试",
                    "official.message.send.parameter.content": {
                        "room_code": "317",
                        "source": "android-listener",
                        "sequence": 2,
                    },
                    "official.message.send.parameter.ttl": 600_000,
                },
                "result_slot": "local_real_listener_batch",
            },
            {
                "instruction_id": "statement_log_sent_lan_messages",
                "opcode": "log.write",
                "function_id": "official.log.output",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-message-harness",
                    "official.log.output.parameter.content": "Android 已通过项目脚本发送同步与监听 LAN 消息",
                },
            },
        ])
    _attach_instruction_capabilities(instructions)
    ecir = {
        "ecir_version": 1,
        "program_model_version": 1,
        "pure_operation_registry": {
            "registry_version": PURE_OPERATION_REGISTRY_VERSION,
            "content_hash": pure_operation_registry_hash(),
        },
        "entry_function_id": "function_main",
        "supported_platforms": list(PLATFORMS),
        "targets": targets,
        "project_variables": variables,
        "required_capabilities": _instruction_capability_closure(instructions),
        "functions": [{
            "function_id": "function_main",
            "name": "主程序",
            "parameters": [],
            "parameter_definitions": [],
            "return_type": "null",
            "instructions": instructions,
        }] + ([{
            "function_id": "function_listener_handler",
            "name": "处理监听消息",
            "parameters": ["parameter_listener_message"],
            "parameter_definitions": [{
                "parameter_id": "parameter_listener_message",
                "name": "消息",
                "display_name": "消息",
                "value_type": "received_message",
                "required": True,
                "default": None,
            }],
            "return_type": "null",
            "instructions": [{
                "instruction_id": "statement_mark_listener_received",
                "opcode": "data.assign_project",
                "arguments": {
                    "target": {
                        "scope": "project",
                        "variable_id": "variable_listener_received",
                        "value_type": "bool",
                    },
                    "value": True,
                },
            }, {
                "instruction_id": "statement_log_listener_handler",
                "opcode": "log.write",
                "function_id": "official.log.output",
                "arguments": {
                    "official.log.output.parameter.level": "info",
                    "official.log.output.parameter.category": "android-listener-harness",
                    "official.log.output.parameter.content": "监听处理函数：已收到并处理消息",
                },
            }],
        }] if exercise_android_message_listener else []),
    }
    form = VNextPlayerService.normalize_form({
        "schema_version": 3,
        "title": "Player 捕获交互 Harness",
        "pages": [{
            "page_id": "capture",
            "title": "字段采集",
            "controls": controls,
        }],
    })
    target_configuration = TargetConfiguration(
        schema_version=1,
        targets=tuple(targets),
        default_target_id=default_target_id,
    )
    project = {
        "project_id": "player_capture_harness",
        "name": "Player 捕获交互 Harness",
        "targets_schema_version": 1,
        "targets": targets,
        "default_target_id": default_target_id,
        "target_configuration_revision": target_configuration_revision(target_configuration),
    }
    (project_root / "project.json").write_text(
        json.dumps(project, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    publisher = VNextPublisher(
        str(project_root),
        signing_key_store=AuthorSigningKeyStore(root / "keys"),
    )
    linked = {"diagnostics": [], "ecir": ecir}
    report = publisher.report(linked, form)
    if not report["valid"]:
        raise RuntimeError(json.dumps(report["errors"], ensure_ascii=False, indent=2))
    published = publisher.build(linked, form, project, report)
    trust_root = root / "trust-root.json"
    trust_root.write_text(json.dumps(
        trust_root_document(published["signature"], project["project_id"]),
        ensure_ascii=False,
    ) + "\n", encoding="utf-8")
    return {
        "root": str(root.resolve()),
        "bundle": str(Path(published["path"]).resolve()),
        "trust_root": str(trust_root.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="创建 Player 全字段捕获交互 Harness")
    parser.add_argument("--output", default="output/player-capture-harness")
    parser.add_argument(
        "--adb-serial",
        action="append",
        default=[],
        help="增加一个显式 ADB 设备目标；可重复使用",
    )
    parser.add_argument(
        "--include-android-local",
        action="store_true",
        help="加入 Android 本机目标（仅用于 Android Player Harness）",
    )
    parser.add_argument(
        "--exercise-android-runtime",
        action="store_true",
        help="让 Android 本机 Harness 实际取帧、执行 OCR 并写入日志",
    )
    parser.add_argument(
        "--exercise-android-controls",
        action="store_true",
        help="启动调试控件页并实际执行查找、输入、点击和读取",
    )
    parser.add_argument(
        "--exercise-android-vision-marker",
        action="store_true",
        help="在调试控件页上使用包内模板实际查找图像",
    )
    parser.add_argument(
        "--exercise-android-files",
        action="store_true",
        help="在 Android 项目私有目录实际执行文本、JSON 与目录操作",
    )
    parser.add_argument(
        "--exercise-android-recording",
        action="store_true",
        help="为 Android 本机录制保留五秒真实多帧运行窗口",
    )
    parser.add_argument(
        "--exercise-android-remaining-basics",
        action="store_true",
        help="实际断言 Android 画面保存、颜色读取/查找和剪贴板读写",
    )
    parser.add_argument(
        "--exercise-android-messages",
        action="store_true",
        help="让 Android 本机 Harness 等待并读取一条真实局域网消息",
    )
    parser.add_argument(
        "--exercise-android-message-listener",
        action="store_true",
        help="让 Android 主流程在安全边界处理一条真实 LAN 监听消息并继续运行",
    )
    parser.add_argument(
        "--android-message-recipient",
        default="",
        help="加入 Android→LAN 发送验证并指定稳定 instance_ref reference_id",
    )
    parser.add_argument(
        "--android-application-id",
        default="com.easycode.player.emulator.debug",
        help="承载 Android 调试控件页的应用 ID",
    )
    args = parser.parse_args()
    print(json.dumps(create_fixture(
        Path(args.output),
        adb_serials=tuple(args.adb_serial),
        include_android_local=bool(args.include_android_local),
        exercise_android_runtime=bool(args.exercise_android_runtime),
        exercise_android_controls=bool(args.exercise_android_controls),
        exercise_android_vision_marker=bool(args.exercise_android_vision_marker),
        exercise_android_files=bool(args.exercise_android_files),
        exercise_android_remaining_basics=bool(args.exercise_android_remaining_basics),
        exercise_android_recording=bool(args.exercise_android_recording),
        exercise_android_messages=bool(args.exercise_android_messages),
        exercise_android_message_listener=bool(args.exercise_android_message_listener),
        android_message_recipient=str(args.android_message_recipient).strip(),
        android_application_id=str(args.android_application_id),
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
