"""Frozen official function contracts for project format 6.

The registry deliberately separates the complete v1 product contract from the
subset that has a verified runtime implementation.  IDE callers must use
``available_catalog``; publishing uses the complete registry to resolve stable
ids and rejects contracts whose implementation state is not ``available``.
This prevents a menu entry from becoming a promise that no runtime can keep.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .control_defaults import parameter_ui_for_type
from .record_types_v6 import editor_strategy_for_type

CONTRACT_SCHEMA_VERSION = 4
STATEMENT_SUMMARY_SCHEMA_VERSION = 1
OFFICIAL_CONTRACT_VERSION = "1.0.0"
_NO_DEFAULT = object()
PLATFORMS = ("windows", "android_adb", "android_local", "no_target")


def _summary_role(parameter_name: str) -> str:
    if parameter_name in {"destination", "destination_parent", "parent", "target"}:
        return "destination"
    if parameter_name == "condition":
        return "condition"
    if parameter_name in {
        "count", "direction", "duration", "key", "maximum", "minimum", "position", "time",
    }:
        return "qualifier"
    if parameter_name in {"content", "message", "name", "text"}:
        return "content"
    return "object"


def statement_summary_contract(template: str, parameters: Iterable[Any]) -> dict[str, Any]:
    """Project a compact, renderer-neutral statement summary contract.

    The template remains convenient authoring syntax, while this typed wire
    projection prevents IDE clients from reparsing display prose or inventing
    per-function rendering rules. Parameter values still come exclusively
    from ProgramDocument and are not persisted in this presentation contract.
    """

    by_name = {str(parameter.name): parameter for parameter in parameters}
    parts: list[dict[str, Any]] = []
    cursor = 0
    for match in re.finditer(r"\{([^{}]+)\}", str(template or "")):
        if match.start() > cursor:
            parts.append({"kind": "text", "text": template[cursor:match.start()]})
        parameter_name = match.group(1).strip()
        parameter = by_name.get(parameter_name)
        if parameter is None:
            raise ValueError(f"statement summary references unknown parameter: {parameter_name}")
        parts.append({
            "kind": "parameter",
            "parameter_id": str(parameter.parameter_id),
            "parameter_name": parameter_name,
            "role": _summary_role(parameter_name),
            "presentation": "auto",
        })
        cursor = match.end()
    if cursor < len(template):
        parts.append({"kind": "text", "text": template[cursor:]})
    if not parts:
        parts.append({"kind": "text", "text": str(template or "")})
    return {"schema_version": STATEMENT_SUMMARY_SCHEMA_VERSION, "parts": parts}

# Parameter presentation is part of the shared authoring contract. Hosts may
# choose a different layout, but they must not guess which implementation
# details belong in the ordinary form.
_INTERNAL_PARAMETER_IDS = {
    "official.log.output.parameter.category",
    "official.wait.until.parameter.past_policy",
}

_ADVANCED_PARAMETER_NAMES = {
    "arguments", "encoding", "easing", "exit_wait", "frame", "hold",
    "interval", "language", "limit", "max_file_bytes", "max_redirects",
    "max_response_bytes", "mode", "preprocess", "quality", "redirect",
    "recursive", "scope", "stable_frames", "start", "timezone", "ttl",
}

_PARAMETER_HELP: dict[str, str] = {
    "official.log.output.parameter.content": "可以直接输入文字，也可以在文字中插入 [项目 · 变量] 或 [局部 · 变量]。",
    "official.wait.duration.parameter.duration": "可输入 2 秒、500 毫秒，也可输入 [局部 · 等待秒数] 秒。",
    "official.wait.until.parameter.time": "使用 HH:mm:ss；今天已过该时间时，自动等待到明天同一时间。",
    "official.time.now.parameter.timezone": "留空使用运行设备时区；需要固定时可输入 GMT+8 或 Asia/Shanghai。",
    "official.time.today.parameter.timezone": "留空使用运行设备时区；需要固定时可输入 GMT+8 或 Asia/Shanghai。",
    "official.frame.save.parameter.quality": "仅保存为 JPEG 时生效，范围 1–100。",
}

_PARAMETER_PLACEHOLDERS: dict[str, str] = {
    "official.log.output.parameter.content": "例如：当前体力为 [项目 · 当前体力]",
    "official.wait.duration.parameter.duration": "例如：2 秒 或 [局部 · 等待秒数] 秒",
    "official.wait.until.parameter.time": "HH:mm:ss",
    "official.time.now.parameter.timezone": "例如：GMT+8；留空使用设备时区",
    "official.time.today.parameter.timezone": "例如：GMT+8；留空使用设备时区",
    "official.clipboard.write_text.parameter.content": "例如：订单号 [项目 · 订单号]",
    "official.text.match.parameter.text": "例如：登录成功",
    "official.text.wait_visible.parameter.text": "例如：登录成功",
    "official.input.type_text.parameter.content": "例如：账号 [项目 · 用户名]",
    "official.control.type_text.parameter.content": "例如：账号 [项目 · 用户名]",
    "official.control.set_value.parameter.value": "例如：已完成，或 [项目 · 状态]",
    "official.file.write_text.parameter.content": "例如：处理完成于 [局部 · 当前时间]",
    "official.file.append_text.parameter.content": "例如：新增记录 [局部 · 结果]",
    "official.file.replace_text.parameter.search": "例如：旧名称",
    "official.file.replace_text.parameter.replacement": "例如：新名称",
    "official.directory.create.parameter.relative_path": "例如：reports/2026-09",
    "official.directory.copy.parameter.name": "例如：备份-2026-09",
    "official.directory.move.parameter.name": "例如：归档-2026-09",
    "official.network.request.parameter.url": "例如：https://api.example.com/tasks",
    "official.network.upload_file.parameter.url": "例如：https://api.example.com/upload",
    "official.network.download_file.parameter.url": "例如：https://example.com/files/report.pdf",
    "official.message.send.parameter.name": "例如：订单处理完成",
    "official.message.wait_receive.parameter.name": "例如：订单处理完成",
    "official.message.send.parameter.content": "例如：任务完成，或 [局部 · 处理结果]",
}


_NO_TEXT_PLACEHOLDER_CONTROLS = {
    "select", "resource", "toggle", "file", "directory", "target",
    "application", "instance", "instance-multi-select", "control-reference",
    "control-selector", "gesture-path", "key-chord", "list", "key-value",
}


def _base_type(value_type: str) -> str:
    normalized = str(value_type or "").strip()
    while normalized.startswith("optional<") and normalized.endswith(">"):
        normalized = normalized[len("optional<"):-1].strip()
    return normalized


def _number_text(value: Any) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else format(number, "g")


def _numeric_placeholder(value_type: str, constraints: dict[str, Any], default: Any) -> str:
    minimum = constraints.get("minimum")
    maximum = constraints.get("maximum")
    example = default if isinstance(default, (int, float)) and not isinstance(default, bool) else None
    if _base_type(value_type) == "percentage":
        def percentage(value: Any) -> str:
            return f"{_number_text(float(value) * 100)}%"

        if minimum is not None and maximum is not None:
            example = 0.85 if example is None else example
            return f"{percentage(minimum)}–{percentage(maximum)}，例如：{percentage(example)}"
        return "例如：85%"
    if minimum is not None and maximum is not None:
        example = minimum if example is None else example
        return f"{_number_text(minimum)}–{_number_text(maximum)}，例如：{_number_text(example)}"
    if minimum is not None:
        example = minimum if example is None else example
        return f"不小于 {_number_text(minimum)}，例如：{_number_text(example)}"
    if maximum is not None:
        example = maximum if example is None else example
        return f"不大于 {_number_text(maximum)}，例如：{_number_text(example)}"
    return ""


def _parameter_placeholder(
    parameter_id: str,
    name: str,
    display_name: str,
    value_type: str,
    control: str,
    constraints: dict[str, Any],
    default: Any,
) -> str:
    if parameter_id in _PARAMETER_PLACEHOLDERS:
        return _PARAMETER_PLACEHOLDERS[parameter_id]
    if parameter_id in _INTERNAL_PARAMETER_IDS or control in _NO_TEXT_PLACEHOLDER_CONTROLS:
        return ""
    base_type = _base_type(value_type)
    if base_type in {"int64", "float64", "percentage"}:
        constrained = _numeric_placeholder(value_type, constraints, default)
        if constrained:
            return constrained
        semantic_number = {
            "minimum": "例如：0",
            "maximum": "例如：100",
            "limit": "例如：20",
            "stable_frames": "例如：2 帧",
            "count": "例如：2 次",
            "distance": "例如：0.6（移动屏幕宽度或高度的 60%）",
            "max_response_bytes": "例如：4194304（4 MB）",
            "max_file_bytes": "例如：536870912（512 MB）",
            "max_redirects": "例如：5 次",
        }.get(name)
        return semantic_number or f"例如：{display_name}所需的数值"
    if base_type == "duration":
        return {
            "timeout": "例如：10 秒",
            "interval": "例如：200 毫秒",
            "hold": "例如：500 毫秒",
            "duration": "例如：2 秒",
            "ttl": "例如：5 分钟",
        }.get(name, "例如：2 秒")
    return {
        "string": f"例如：{display_name}文本，或 [项目 · 变量]",
        "any": "例如：18、开启，或 [局部 · 识别结果]",
        "message_value": "例如：任务完成，或 [局部 · 结果]",
        "date": "YYYY-MM-DD，例如：2026-09-05",
        "datetime": "YYYY-MM-DD HH:mm:ss，例如：2026-09-05 18:30:00",
        "time": "HH:mm:ss，例如：12:00:00",
        "timezone": "例如：Asia/Shanghai 或 GMT+8",
        "point": "例如：100, 200，或 [局部 · 图片坐标]",
        "rect": "例如：100, 200, 640, 480，或 [项目 · 识别区域]",
        "path": "例如：data/result.json",
        "url": "例如：https://example.com/api",
        "relative_path": "例如：reports/2026-09",
        "json": "例如：{\"name\": \"小明\"}",
        "json_value": "例如：文字、数字、列表或字典",
    }.get(base_type, "")


def _effective_default_label(
    parameter_id: str,
    default: Any,
    value_type: str,
    constraints: dict[str, Any],
) -> str:
    exact = {
        "official.log.output.parameter.category": "脚本日志",
        "official.text.recognize.parameter.preprocess": "不预处理",
        "official.directory.list.parameter.filter": "列出全部",
        "official.application.start.parameter.arguments": "不添加启动参数",
    }.get(parameter_id)
    if exact is not None:
        return exact
    if default is None:
        base_type = _base_type(value_type)
        return {
            "timezone": "当前设备时区（如 Asia/Shanghai）",
            "target_ref": "当前运行目标",
            "frame_ref": "自动获取最新画面",
            "rect": "整个画面",
            "http_body": "不发送正文",
            "instance_ref": "不限定实例",
            "point": "自动选择起点",
        }.get(base_type, "留空")
    for choice in constraints.get("choices") or ():
        if isinstance(choice, dict) and choice.get("value") == default:
            return str(choice.get("label") or default)
    if isinstance(default, dict) and default.get("kind") == "duration":
        milliseconds = int(default.get("milliseconds") or 0)
        if milliseconds % 1000 == 0:
            return f"{milliseconds // 1000} 秒"
        return f"{milliseconds} 毫秒"
    if isinstance(default, bool):
        return "开启" if default else "关闭"
    if _base_type(value_type) == "percentage" and isinstance(default, (int, float)):
        return f"{_number_text(float(default) * 100)}%"
    if default == []:
        return "空列表"
    if default == {}:
        return "空字典"
    return str(default)


def _editor_strategy(value_type: str, control: str) -> str:
    record_strategy = editor_strategy_for_type(value_type)
    if record_strategy is not None:
        return record_strategy

    normalized = str(value_type or "").strip()
    while normalized.startswith("optional<") and normalized.endswith(">"):
        normalized = normalized[len("optional<"):-1].strip()
    if control in {"coordinate", "region", "control-selector", "gesture-path"}:
        return "capture"
    if (
        control in {
            "resource", "file", "directory", "target", "application",
            "instance", "instance-multi-select", "control-reference",
        }
        or normalized.endswith("_ref")
        or normalized.startswith(("asset_ref<", "file_ref<", "directory_ref<"))
    ):
        return "reference"
    if normalized.startswith("list<"):
        return "row_list"
    if normalized.startswith("map<") or normalized in {"json", "json_value"}:
        return "focused"
    return "scalar"

# Enum values are part of the public function contract, not presentation-only
# frontend knowledge. Keeping the stable value, user-facing label and optional
# platform restriction together prevents the IDE, Player and compiler from
# offering different choices for the same parameter.
_ENUM_CHOICES: dict[str, tuple[dict[str, Any], ...]] = {
    "enum<log_level>": (
        {"label": "信息", "value": "info"},
        {"label": "警告", "value": "warning"},
        {"label": "错误", "value": "error"},
    ),
    "enum<past_time_policy>": (
        {"label": "等到明天", "value": "next_day"},
        {"label": "立即继续", "value": "immediate"},
        {"label": "作为错误", "value": "error"},
    ),
    "enum<text_match_mode>": (
        {"label": "包含", "value": "contains"},
        {"label": "完全等于", "value": "exact"},
        {"label": "正则表达式", "value": "regex"},
    ),
    "enum<window_match_mode>": (
        {"label": "包含", "value": "contains"},
        {"label": "完全等于", "value": "exact"},
        {"label": "正则表达式", "value": "regex"},
    ),
    "enum<pointer_button>": (
        {"label": "主按键", "value": "primary"},
        {"label": "右键", "value": "secondary", "platforms": ["windows"]},
        {"label": "中键", "value": "middle", "platforms": ["windows"]},
    ),
    "enum<text_input_mode>": (
        {"label": "自动选择", "value": "auto"},
        {"label": "仅后台输入", "value": "background", "platforms": ["windows"]},
        {"label": "物理键盘", "value": "physical", "platforms": ["windows"]},
        {
            "label": "目标原生输入",
            "value": "target",
            "platforms": ["android_adb", "android_local"],
        },
    ),
    "enum<direction>": (
        {"label": "向上", "value": "up"},
        {"label": "向下", "value": "down"},
        {"label": "向左", "value": "left"},
        {"label": "向右", "value": "right"},
    ),
    "enum<scroll_mode>": (
        {"label": "自动选择", "value": "auto"},
        {"label": "滚轮", "value": "wheel", "platforms": ["windows"]},
        {"label": "触控拖动", "value": "touch"},
    ),
    "enum<gesture_easing>": (
        {"label": "线性", "value": "linear"},
        {"label": "缓入缓出", "value": "ease_in_out"},
    ),
    "enum<text_encoding>": (
        {"label": "UTF-8", "value": "utf-8"},
        {"label": "UTF-8（含 BOM）", "value": "utf-8-sig"},
        {"label": "GB18030", "value": "gb18030"},
    ),
    "enum<replace_scope>": (
        {"label": "全部替换", "value": "all"},
        {"label": "仅第一处", "value": "first"},
    ),
    "enum<file_conflict>": (
        {"label": "报错并保留原文件", "value": "error"},
        {"label": "覆盖目标文件", "value": "overwrite"},
    ),
    "enum<directory_existing>": (
        {"label": "返回已有目录", "value": "return_existing"},
        {"label": "作为错误", "value": "error"},
    ),
    "enum<tree_conflict>": (
        {"label": "作为错误", "value": "error"},
        {"label": "跳过", "value": "skip"},
        {"label": "自动重命名", "value": "auto_rename"},
    ),
    "enum<http_method>": tuple(
        {"label": method, "value": method}
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
    ),
    "enum<http_redirect>": (
        {"label": "不跟随", "value": "none"},
        {"label": "仅同源", "value": "same_origin"},
        {"label": "允许已授权跨源", "value": "cross_origin"},
    ),
    "enum<http_body_kind>": (
        {"label": "文本", "value": "text"},
        {"label": "JSON", "value": "json"},
    ),
    "enum<multipart_field_kind>": (
        {"label": "文本字段", "value": "text"},
        {"label": "文件字段", "value": "file"},
    ),
    "enum<map_conflict>": (
        {"label": "作为错误", "value": "error"},
        {"label": "保留原值", "value": "keep_old"},
        {"label": "使用新值", "value": "keep_new"},
    ),
    "enum<read_wait_mode>": (
        {"label": "全部已读", "value": "all"},
        {"label": "任一已读", "value": "any"},
    ),
    "enum<control_action_mode>": (
        {"label": "自动选择", "value": "auto"},
        {"label": "仅后台操作", "value": "background", "platforms": ["windows"]},
        {"label": "物理输入", "value": "physical", "platforms": ["windows"]},
    ),
    "enum<control_text_mode>": (
        {"label": "自动选择", "value": "auto"},
        {"label": "仅后台输入", "value": "background", "platforms": ["windows"]},
        {"label": "物理键盘", "value": "physical", "platforms": ["windows"]},
    ),
    "enum<key_action>": (
        {"label": "按下并释放", "value": "press"},
        {"label": "仅按下", "value": "down"},
        {"label": "仅释放", "value": "up"},
    ),
    "enum<ocr_language>": (
        {"label": "自动（中英文）", "value": "auto"},
    ),
    "enum<image_file_format>": (
        {"label": "PNG（无损）", "value": "png"},
        {"label": "JPEG（体积较小）", "value": "jpeg"},
    ),
    "enum<image_compare_size_strategy>": (
        {"label": "尺寸必须一致", "value": "strict"},
        {"label": "只比较重叠区域", "value": "intersection"},
        {"label": "将右图缩放到左图", "value": "scale_right_nearest"},
    ),
    "enum<window_display_state>": (
        {"label": "还原", "value": "restored", "platforms": ["windows"]},
        {"label": "最小化", "value": "minimized", "platforms": ["windows"]},
        {"label": "最大化", "value": "maximized", "platforms": ["windows"]},
    ),
    "enum<filesystem_entry_type>": (
        {"label": "文件", "value": "file"},
        {"label": "目录", "value": "directory"},
        {"label": "链接", "value": "link", "platforms": ["windows"]},
    ),
}


def enum_choices(value_type: str) -> tuple[dict[str, Any], ...]:
    """Return a detached authoritative choice list for structured editors."""

    normalized = str(value_type).strip()
    while normalized.startswith("optional<") and normalized.endswith(">"):
        normalized = normalized[len("optional<"):-1].strip()
    return tuple(dict(item) for item in _ENUM_CHOICES.get(normalized, ()))


def _duration(milliseconds: int) -> dict[str, Any]:
    return {"kind": "duration", "milliseconds": milliseconds}


@dataclass(frozen=True)
class ParameterContractV6:
    parameter_id: str
    name: str
    display_name: str
    value_type: str
    required: bool = True
    has_default: bool = False
    default: Any = None
    control: str = "auto"
    constraints: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    ui: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ErrorContractV6:
    error_id: str
    classification: str  # transient | permanent
    description: str

    def to_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class PlatformSupportV6:
    platform: str
    support: str  # supported | conditional | unsupported
    implementation: str  # verified | planned
    required_capabilities: tuple[str, ...] = ()
    minimum_android_api: int | None = None

    def __post_init__(self) -> None:
        if self.platform not in PLATFORMS:
            raise ValueError(f"unknown function platform: {self.platform}")
        if self.support not in {"supported", "conditional", "unsupported"}:
            raise ValueError(f"unknown platform support state: {self.support}")
        if self.implementation not in {"verified", "planned"}:
            raise ValueError(f"unknown platform implementation state: {self.implementation}")
        if self.support == "unsupported" and self.implementation == "verified":
            raise ValueError("an unsupported platform cannot be verified")
        if self.support == "conditional" and not self.required_capabilities:
            raise ValueError("conditional support requires stable capability IDs")
        if self.platform == "android_local" and self.support != "unsupported":
            if self.minimum_android_api is None or not 21 <= self.minimum_android_api <= 37:
                raise ValueError("Android local support requires API 21..37 metadata")
        elif self.minimum_android_api is not None:
            raise ValueError("only supported Android local entries may declare a minimum API")


@dataclass(frozen=True)
class FunctionContractV6:
    function_id: str
    namespace: str
    name: str
    summary: str
    layer: str  # atomic | standard
    parameters: tuple[ParameterContractV6, ...]
    return_type: str
    opcode: str
    host_requirements: tuple[str, ...] = ("windows", "android")
    target_kinds: tuple[str, ...] = ()
    target_capabilities: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    errors: tuple[ErrorContractV6, ...] = ()
    normal_empty: bool = False
    network_level: str = "none"
    dangerous: bool = False
    platform_support: tuple[PlatformSupportV6, ...] = ()
    standard_definition_id: str = ""
    contract_version: str = OFFICIAL_CONTRACT_VERSION

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}"

    @property
    def verified_platforms(self) -> tuple[str, ...]:
        return tuple(
            item.platform
            for item in self.platform_support
            if item.support != "unsupported" and item.implementation == "verified"
        )

    @property
    def implementation_state(self) -> str:
        """Legacy catalog summary derived from the platform matrix."""

        return "available" if self.verified_platforms else "planned"

    def to_dict(self) -> dict[str, Any]:
        value = dataclasses.asdict(self)
        value["schema_version"] = CONTRACT_SCHEMA_VERSION
        value["qualified_name"] = self.qualified_name
        value["statement_summary"] = statement_summary_contract(self.summary, self.parameters)
        value["verified_platforms"] = list(self.verified_platforms)
        value["implementation_state"] = self.implementation_state
        value["contract_fingerprint"] = self.fingerprint()
        return value

    def fingerprint(self) -> str:
        value = dataclasses.asdict(self)
        value["statement_summary"] = statement_summary_contract(self.summary, self.parameters)
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _p(
    owner: str,
    name: str,
    display_name: str,
    value_type: str,
    *,
    required: bool = True,
    default: Any = _NO_DEFAULT,
    control: str = "auto",
    constraints: dict[str, Any] | None = None,
    description: str = "",
    ui: dict[str, Any] | None = None,
) -> ParameterContractV6:
    parameter_id = f"{owner}.parameter.{name}"
    resolved_constraints = dict(constraints or {})
    if control == "select" and "choices" not in resolved_constraints:
        choices = _ENUM_CHOICES.get(value_type)
        if choices is None:
            raise ValueError(f"select parameter has no authoritative choices: {owner}.{name}")
        resolved_constraints["choices"] = [dict(item) for item in choices]
    choices = resolved_constraints.get("choices")
    values: list[Any] = []
    if choices is not None:
        values = [
            item.get("value") if isinstance(item, dict) and "value" in item else item
            for item in choices
        ]
        serialized_values = {
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in values
        }
        if len(values) != len(serialized_values):
            raise ValueError(f"parameter choices contain duplicate values: {owner}.{name}")
        if default is not _NO_DEFAULT and default not in values:
            raise ValueError(f"parameter default is not an allowed choice: {owner}.{name}")
    resolved_ui = dict(ui or {})
    if not resolved_ui:
        if control == "resource":
            resolved_ui = {
                "control": control,
                "actions": [
                    {"id": "choose-resource", "platforms": ["windows", "android_adb", "android_local"]},
                    {
                        "id": "capture-image",
                        "capture_kind": "image",
                        "platforms": ["windows", "android_adb", "android_local"],
                        "default_category": "image",
                        "max_rects": 1,
                    },
                ],
            }
        elif control == "coordinate":
            resolved_ui = {
                "control": control,
                "actions": [{
                    "id": "pick-point", "capture_kind": "point",
                    "platforms": ["windows", "android_adb", "android_local"], "max_rects": 1,
                }],
            }
        elif control == "region":
            resolved_ui = {
                "control": control,
                "actions": [{
                    "id": "pick-region", "capture_kind": "region",
                    "platforms": ["windows", "android_adb", "android_local"], "max_rects": 1,
                }],
            }
        elif control == "color":
            resolved_ui = {
                "control": control,
                "actions": [{
                    "id": "pick-color", "capture_kind": "color",
                    "platforms": ["windows", "android_adb", "android_local"], "max_rects": 1,
                }],
            }
        elif control == "gesture-path":
            resolved_ui = {
                "control": control,
                "actions": [{
                    "id": "capture-path", "capture_kind": "path",
                    "platforms": ["windows", "android_adb", "android_local"], "min_points": 2,
                }],
            }
        elif control in {"file", "directory"}:
            resolved_ui = parameter_ui_for_type(value_type)
        elif control == "control-selector":
            resolved_ui = {
                "control": control,
                "actions": [{
                    "id": "capture-control", "capture_kind": "control",
                    "platforms": ["windows", "android_adb", "android_local"],
                    "result_reference_type": "control_selector",
                }],
            }
        else:
            resolved_ui = {"control": control}
    single_choice_is_effective_default = bool(
        choices
        and len(choices) == 1
        and default is not _NO_DEFAULT
        and values == [default]
    )
    importance = (
        "internal"
        if parameter_id in _INTERNAL_PARAMETER_IDS or single_choice_is_effective_default
        else "advanced"
        if name in _ADVANCED_PARAMETER_NAMES
        else "primary"
    )
    resolved_ui.setdefault("importance", importance)
    resolved_ui.setdefault("editor_strategy", _editor_strategy(value_type, control))
    placeholder = _parameter_placeholder(
        parameter_id,
        name,
        display_name,
        value_type,
        control,
        resolved_constraints,
        default,
    )
    if placeholder:
        resolved_ui.setdefault("placeholder", placeholder)
    help_text = description or _PARAMETER_HELP.get(parameter_id, "")
    if help_text:
        resolved_ui.setdefault("help", help_text)
    if default is not _NO_DEFAULT:
        resolved_ui.setdefault(
            "effective_default_label",
            _effective_default_label(
                parameter_id, default, value_type, resolved_constraints,
            ),
        )
    if parameter_id == "official.frame.save.parameter.quality":
        resolved_ui["importance"] = "contextual"
        resolved_ui.setdefault("visible_when", {
            "parameter_id": "official.frame.save.parameter.format",
            "operator": "equals",
            "value": "jpeg",
        })
    return ParameterContractV6(
        parameter_id=parameter_id,
        name=name,
        display_name=display_name,
        value_type=value_type,
        required=required,
        has_default=default is not _NO_DEFAULT,
        default=None if default is _NO_DEFAULT else default,
        control=control,
        constraints=resolved_constraints,
        description=help_text,
        ui=resolved_ui,
    )


_TARGET_ERRORS = (
    ErrorContractV6("target.reference_invalid", "permanent", "操作目标引用格式无效"),
    ErrorContractV6("target.reference_missing", "permanent", "操作目标已从项目中删除"),
    ErrorContractV6("target.invalid_point", "permanent", "坐标无效或超出当前工作区域"),
    ErrorContractV6("target.invalid_duration", "permanent", "持续时间无效"),
    ErrorContractV6("target.invalid_key", "permanent", "按键或组合键无效"),
    ErrorContractV6("target.invalid_key_action", "permanent", "按键动作无效"),
    ErrorContractV6("target.invalid_key_hold", "permanent", "按键保持时间无效"),
    ErrorContractV6("target.physical_input_disabled", "permanent", "当前目标未允许物理输入"),
    ErrorContractV6("target.input_mode_unsupported", "permanent", "当前目标不支持所选输入模式"),
    ErrorContractV6("target.offline", "transient", "操作目标已离线"),
    ErrorContractV6("target.permission_denied", "permanent", "当前宿主没有所需目标权限"),
    ErrorContractV6("target.driver_failed", "transient", "目标驱动暂时不可用"),
    ErrorContractV6("runtime.argument_type", "permanent", "参数类型无效"),
    ErrorContractV6("runtime.argument_range", "permanent", "参数超出允许范围"),
)
_CLICK_ERRORS = _TARGET_ERRORS + (
    ErrorContractV6("target.pointer_button_unsupported", "permanent", "当前目标不支持所选指针按键"),
    ErrorContractV6("target.invalid_click_count", "permanent", "点击次数无效"),
    ErrorContractV6("target.invalid_click_hold", "permanent", "点击保持时间无效"),
)
_TEXT_INPUT_ERRORS = _TARGET_ERRORS + (
    ErrorContractV6("target.focus_missing", "permanent", "当前没有可输入文本的焦点控件"),
)
_SCROLL_ERRORS = _TARGET_ERRORS + (
    ErrorContractV6("target.scroll_mode_unsupported", "permanent", "当前目标不支持所选滚动模式"),
    ErrorContractV6("target.scroll_direction_unsupported", "permanent", "滚动方向无效"),
    ErrorContractV6("target.invalid_scroll_distance", "permanent", "滚动距离无效"),
)
_DRAG_ERRORS = _TARGET_ERRORS + (
    ErrorContractV6("target.invalid_drag_path", "permanent", "拖拽路径无效"),
    ErrorContractV6("target.drag_easing_unsupported", "permanent", "当前目标不支持所选拖拽缓动"),
)
_VISION_COMMON_ERRORS = _TARGET_ERRORS + (
    ErrorContractV6("vision.region_invalid", "permanent", "分析区域格式无效或宽高不是正数"),
    ErrorContractV6("vision.frame_reference_invalid", "permanent", "画面引用格式或来源不一致"),
    ErrorContractV6("vision.frame_reference_expired", "permanent", "画面引用不属于当前运行或已失效"),
)
_IMAGE_FIND_ERRORS = _VISION_COMMON_ERRORS + (
    ErrorContractV6("vision.asset_reference_invalid", "permanent", "图片资源引用格式无效"),
    ErrorContractV6("vision.asset_missing", "permanent", "图片资源或资源文件不存在"),
    ErrorContractV6("vision.asset_corrupt", "permanent", "图片资源损坏或哈希不一致"),
    ErrorContractV6("vision.similarity_invalid", "permanent", "相似度不在 0 到 1 范围"),
    ErrorContractV6("vision.analysis_failed", "transient", "视觉分析适配器执行失败"),
)
_IMAGE_FIND_ALL_ERRORS = _IMAGE_FIND_ERRORS + (
    ErrorContractV6("vision.limit_invalid", "permanent", "查找结果上限无效"),
)
_OCR_ERRORS = _VISION_COMMON_ERRORS + (
    ErrorContractV6("ocr.engine_unavailable", "permanent", "发布包没有可用 OCR 引擎"),
    ErrorContractV6("ocr.inference_failed", "transient", "OCR 推理适配器执行失败"),
    ErrorContractV6("ocr.preprocess_invalid", "permanent", "OCR 预处理参数无效"),
    ErrorContractV6("ocr.language_unsupported", "permanent", "OCR 不支持所选语言模式"),
)
_APPLICATION_ERRORS = (
    ErrorContractV6("application.reference_invalid", "permanent", "应用引用格式或授权无效"),
    ErrorContractV6("application.executable_forbidden", "permanent", "官方应用启动不允许命令解释器或脚本宿主"),
    ErrorContractV6("application.not_found", "permanent", "应用可执行文件或 Android 组件不存在"),
    ErrorContractV6("application.launch_failed", "transient", "应用启动失败"),
    ErrorContractV6("application.lifecycle_unavailable", "permanent", "当前驱动不能可靠观察该应用退出"),
    ErrorContractV6("application.stop_failed", "transient", "应用未能停止"),
    ErrorContractV6("target.reference_missing", "permanent", "Android 应用启动时没有当前 ADB 目标"),
    ErrorContractV6("runtime.argument_type", "permanent", "超时参数类型无效"),
    ErrorContractV6("runtime.argument_range", "permanent", "超时参数超出允许范围"),
)
_WINDOW_ERRORS = (
    ErrorContractV6("window.selector_invalid", "permanent", "窗口选择器无效"),
    ErrorContractV6("window.reference_invalid", "permanent", "窗口引用已失效或不属于当前宿主"),
    ErrorContractV6("window.permission_denied", "permanent", "EasyCode 与目标应用的 Windows 权限级别不一致"),
    ErrorContractV6("window.operation_failed", "transient", "Windows 窗口操作未完成"),
    ErrorContractV6("window.position_invalid", "permanent", "窗口位置无效"),
    ErrorContractV6("window.size_invalid", "permanent", "窗口尺寸无效"),
    ErrorContractV6("window.display_state_invalid", "permanent", "窗口显示状态无效"),
    ErrorContractV6("window.work_area_too_small", "permanent", "当前屏幕工作区无法完整容纳窗口"),
    ErrorContractV6("runtime.cancelled", "permanent", "窗口操作已取消"),
)
_CONTROL_ERRORS = (
    ErrorContractV6("control.selector_invalid", "permanent", "控件选择器无效"),
    ErrorContractV6("control.reference_invalid", "permanent", "控件引用无效或不属于当前目标"),
    ErrorContractV6("control.reference_stale", "transient", "控件已变化，无法按原选择器重新定位"),
    ErrorContractV6("control.operation_failed", "transient", "控件操作未完成"),
    ErrorContractV6("control.operation_unsupported", "permanent", "当前平台不支持所选控件操作方式"),
    ErrorContractV6("control.driver_unavailable", "transient", "控件语义驱动暂时不可用"),
    ErrorContractV6("control.permission_required", "permanent", "控件能力尚未获得系统授权"),
    ErrorContractV6("control.semantic_tree_unavailable", "permanent", "当前页面不提供可识别控件，请使用图像、OCR 或坐标"),
    ErrorContractV6("control.selector_provider_mismatch", "permanent", "控件选择器不属于当前平台适配器"),
    ErrorContractV6("control.coordinate_space_invalid", "permanent", "控件坐标空间与当前目标不一致"),
    ErrorContractV6("control.physical_input_disabled", "permanent", "当前目标未允许物理控件操作"),
)
_FILE_ERRORS = (
    ErrorContractV6("filesystem.reference_invalid", "permanent", "文件或目录授权引用已失效"),
    ErrorContractV6("filesystem.permission_denied", "permanent", "没有所需文件权限"),
    ErrorContractV6("filesystem.io_failed", "transient", "文件系统操作未完成"),
    ErrorContractV6("file.invalid_reference", "permanent", "文件或目录引用结构无效"),
    ErrorContractV6("file.access_denied", "permanent", "引用没有授予所需能力"),
    ErrorContractV6("file.outside_authorization", "permanent", "路径超出授权根"),
    ErrorContractV6("file.delete_tree_confirmation_required", "permanent", "递归删除缺少与调用及授权根绑定的实际执行确认"),
    ErrorContractV6("file.protected_root", "permanent", "递归删除目标是受保护根"),
    ErrorContractV6("file.symlink_escape", "permanent", "递归删除树包含符号链接或解析越界"),
    ErrorContractV6("file.delete_tree_failed", "transient", "递归删除部分完成并返回失败报告"),
    ErrorContractV6("runtime.cancelled", "permanent", "操作由用户或运行器取消"),
)
_FRAME_SAVE_ERRORS = _VISION_COMMON_ERRORS + _FILE_ERRORS + (
    ErrorContractV6("vision.image_format_unsupported", "permanent", "画面保存格式不受支持"),
    ErrorContractV6("vision.image_quality_invalid", "permanent", "JPEG 质量不在允许范围"),
    ErrorContractV6("vision.image_encode_failed", "transient", "画面编码失败"),
)
_IMAGE_SAMPLE_ERRORS = _VISION_COMMON_ERRORS + (
    ErrorContractV6("vision.sample_reference_invalid", "permanent", "图片样本引用格式或来源不一致"),
    ErrorContractV6("vision.sample_reference_expired", "permanent", "图片样本不属于当前运行或已失效"),
    ErrorContractV6("vision.sample_empty", "permanent", "取样区域与当前画面没有交集"),
    ErrorContractV6("vision.sample_size_mismatch", "permanent", "两个图片样本尺寸不一致"),
    ErrorContractV6("vision.compare_strategy_invalid", "permanent", "图片尺寸处理方式不受支持"),
    ErrorContractV6("vision.pixel_tolerance_invalid", "permanent", "像素变化容差不在 0 到 255 范围"),
)
_COLOR_ERRORS = _VISION_COMMON_ERRORS + (
    ErrorContractV6("vision.color_invalid", "permanent", "颜色值或颜色通道无效"),
    ErrorContractV6("vision.color_tolerance_invalid", "permanent", "颜色容差不在 0 到 255 范围"),
)
_NETWORK_ERRORS = (
    ErrorContractV6("network.url_invalid", "permanent", "URL 结构无效"),
    ErrorContractV6("network.scheme_denied", "permanent", "URL 不是 http/https"),
    ErrorContractV6("network.credentials_in_url", "permanent", "URL 包含禁止的内嵌凭据"),
    ErrorContractV6("network.dns_failed", "transient", "域名解析失败"),
    ErrorContractV6("network.unreachable", "transient", "网络暂时不可达"),
    ErrorContractV6("network.timeout", "transient", "网络请求超时"),
    ErrorContractV6("network.permission_denied", "permanent", "目标主机或端口未进入发布授权闭包"),
    ErrorContractV6("network.address_scope_denied", "permanent", "DNS 地址或重定向超出授权范围"),
    ErrorContractV6("network.tls_failed", "permanent", "安全连接验证失败"),
    ErrorContractV6("network.proxy_failed", "transient", "代理连接失败"),
    ErrorContractV6("network.redirect_denied", "permanent", "重定向目标未获允许"),
    ErrorContractV6("network.redirect_limit", "permanent", "重定向次数超过上限"),
    ErrorContractV6("network.response_too_large", "permanent", "响应正文超过声明上限"),
    ErrorContractV6("network.response_encoding_failed", "permanent", "文本响应编码无效"),
    ErrorContractV6("network.binary_response_unsupported", "permanent", "普通请求收到二进制响应"),
    ErrorContractV6("network.response_interrupted", "transient", "响应在完整接收前中断"),
    ErrorContractV6("network.protocol_failed", "transient", "HTTP 传输协议失败"),
    ErrorContractV6("network.transfer_failed", "transient", "网络或文件传输失败"),
    ErrorContractV6("network.timeout_invalid", "permanent", "总超时配置无效"),
    ErrorContractV6("network.response_limit_invalid", "permanent", "文本响应上限无效"),
    ErrorContractV6("network.redirect_limit_invalid", "permanent", "重定向上限无效"),
    ErrorContractV6("network.redirect_policy_invalid", "permanent", "重定向策略无效"),
    ErrorContractV6("network.method_invalid", "permanent", "HTTP 方法无效"),
    ErrorContractV6("network.body_not_allowed", "permanent", "GET 或 HEAD 请求不能携带正文"),
    ErrorContractV6("network.body_invalid", "permanent", "请求正文不是文本或 JSON"),
    ErrorContractV6("network.pairs_invalid", "permanent", "查询参数或请求头结构无效"),
    ErrorContractV6("network.header_denied", "permanent", "请求头由传输层保留"),
    ErrorContractV6("network.multipart_invalid", "permanent", "multipart 字段结构无效"),
    ErrorContractV6("network.upload_limit_invalid", "permanent", "上传文件上限无效"),
    ErrorContractV6("network.upload_too_large", "permanent", "上传文件超过声明上限"),
    ErrorContractV6("network.download_limit_invalid", "permanent", "下载文件上限无效"),
    ErrorContractV6("network.download_too_large", "permanent", "下载文件超过声明上限"),
    ErrorContractV6("network.download_interrupted", "transient", "下载在完整接收前中断"),
    ErrorContractV6("runtime.cancelled", "permanent", "调用由用户或运行器取消"),
)
_NETWORK_FILE_ERRORS = (
    ErrorContractV6("file.invalid_reference", "permanent", "文件引用结构无效"),
    ErrorContractV6("file.platform_unsupported", "permanent", "当前宿主不支持该文件引用"),
    ErrorContractV6("file.android_host_unsupported", "permanent", "Android 文件引用需要本机 APK 宿主"),
    ErrorContractV6("file.access_denied", "permanent", "文件引用未授予所需权限"),
    ErrorContractV6("file.outside_authorization", "permanent", "文件超出授权根"),
    ErrorContractV6("file.read_failed", "transient", "上传文件读取失败"),
    ErrorContractV6("file.write_failed", "transient", "下载临时文件写入失败"),
    ErrorContractV6("file.atomic_commit_unsupported", "permanent", "目标位置不支持原子提交"),
    ErrorContractV6("file.atomic_commit_failed", "transient", "下载文件原子提交失败"),
    ErrorContractV6("file.reference_changed", "permanent", "下载期间文件引用发生变化"),
    ErrorContractV6("directory.filter_invalid", "permanent", "目录筛选格式、名称模式或条数无效"),
)
_MESSAGE_ERRORS = (
    ErrorContractV6("message.instance_unknown", "permanent", "接收实例未知或未获授权"),
    ErrorContractV6("message.instance_invalid", "permanent", "实例身份或引用格式无效"),
    ErrorContractV6("message.instance_conflict", "permanent", "实例名称或稳定身份发生冲突"),
    ErrorContractV6("message.project_invalid", "permanent", "项目消息命名空间无效"),
    ErrorContractV6("message.transport_unavailable", "transient", "消息传输暂时不可用"),
    ErrorContractV6("message.content_invalid", "permanent", "消息内容不能按值复制"),
    ErrorContractV6("message.database_version", "permanent", "消息数据库版本不受支持"),
    ErrorContractV6("message.idempotency_conflict", "permanent", "相同消息批次编号对应了不同内容"),
    ErrorContractV6("message.decode_failed", "permanent", "消息内容解码失败且未产生已读确认"),
    ErrorContractV6("message.batch_unknown", "permanent", "发送批次不存在或不属于当前实例"),
)
_TIME_ERRORS = (
    ErrorContractV6("time.timezone_invalid", "permanent", "时区名称无效或当前系统不可用"),
)
_WAIT_UNTIL_ERRORS = (
    ErrorContractV6("wait.time_invalid", "permanent", "等待时间或当日已过策略无效"),
    ErrorContractV6("wait.time_already_passed", "permanent", "指定时刻在当日已经过去"),
)
_RANDOM_ERRORS = (
    ErrorContractV6("random.range_invalid", "permanent", "随机整数范围无效"),
)
_CLIPBOARD_ERRORS = (
    ErrorContractV6("clipboard.unavailable", "transient", "系统剪贴板暂时不可用"),
    ErrorContractV6("clipboard.read_failed", "transient", "读取剪贴板失败"),
    ErrorContractV6("clipboard.write_failed", "transient", "写入剪贴板失败"),
)


def _f(
    function_id: str,
    namespace: str,
    name: str,
    summary: str,
    parameters: Iterable[ParameterContractV6],
    return_type: str,
    opcode: str,
    *,
    layer: str = "atomic",
    hosts: tuple[str, ...] = ("windows", "android"),
    targets: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    errors: tuple[ErrorContractV6, ...] = (),
    normal_empty: bool = False,
    network_level: str = "none",
    dangerous: bool = False,
    available: bool = False,
    verified_platforms: tuple[str, ...] = (),
    android_min_api: int = 21,
) -> FunctionContractV6:
    declared_verified = set(verified_platforms)
    if available and not declared_verified:
        # Compatibility for the first runtime slice.  It was verified on the
        # Windows host, including ADB/no-target instances. Android local stays
        # planned until the disconnected physical-device Harness passes.
        declared_verified.update(("windows", "android_adb", "no_target"))
    target_set = set(targets)
    host_set = set(hosts)

    def support_for(platform: str) -> PlatformSupportV6:
        host_supported = (
            platform in {"windows", "android_adb", "no_target"} and "windows" in host_set
        ) or (platform == "android_local" and "android" in host_set)
        target_supported = not target_set or platform in target_set
        if platform == "no_target" and target_set:
            target_supported = False
        supported = host_supported and target_supported
        required = (
            tuple(dict.fromkeys((*capabilities, *permissions)))
            if supported and (capabilities or permissions)
            else ()
        )
        state = "conditional" if required else "supported"
        if not supported:
            state = "unsupported"
        return PlatformSupportV6(
            platform=platform,
            support=state,
            implementation=(
                "verified" if supported and platform in declared_verified else "planned"
            ),
            required_capabilities=required,
            minimum_android_api=(android_min_api if supported and platform == "android_local" else None),
        )

    return FunctionContractV6(
        function_id=function_id,
        namespace=namespace,
        name=name,
        summary=summary,
        layer=layer,
        parameters=tuple(parameters),
        return_type=return_type,
        opcode=opcode,
        host_requirements=hosts,
        target_kinds=targets,
        target_capabilities=capabilities,
        permissions=permissions,
        side_effects=side_effects,
        errors=errors,
        normal_empty=normal_empty,
        network_level=network_level,
        dangerous=dangerous,
        platform_support=tuple(support_for(platform) for platform in PLATFORMS),
        standard_definition_id=f"standard.{function_id}" if layer == "standard" else "",
    )


def _official_contracts() -> tuple[FunctionContractV6, ...]:
    target_types = ("windows", "android_adb", "android_local")
    vision_caps = ("target.capture_frame",)
    input_caps = ("target.input",)
    contracts = [
        _f("official.log.output", "日志", "输出", "输出{content}", [
            _p("official.log.output", "content", "内容", "any"),
            _p(
                "official.log.output",
                "level",
                "级别",
                "enum<log_level>",
                required=False,
                default="info",
                control="select",
            ),
            _p("official.log.output", "category", "分类", "string", required=False, default="script"),
        ], "unit", "log.write", side_effects=("log",), available=True),
        _f("official.wait.duration", "等待", "持续", "等待{duration}", [
            _p("official.wait.duration", "duration", "时长", "duration", default=_duration(1000), control="duration"),
        ], "unit", "wait.duration", available=True),
        _f("official.wait.until", "等待", "直到", "等待到{time}", [
            _p("official.wait.until", "time", "时间点", "time", control="time"),
            _p("official.wait.until", "past_policy", "当日已过", "enum<past_time_policy>", required=False, default="next_day", control="select"),
        ], "unit", "wait.until", errors=_WAIT_UNTIL_ERRORS, available=True),
        _f("official.time.now", "时间", "现在", "取得当前时间", [
            _p("official.time.now", "timezone", "时区", "optional<timezone>", required=False, default=None),
        ], "datetime", "time.now", errors=_TIME_ERRORS, available=True),
        _f("official.time.today", "时间", "今天", "取得今天日期", [
            _p("official.time.today", "timezone", "时区", "optional<timezone>", required=False, default=None),
        ], "date", "time.today", errors=_TIME_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.random.integer", "随机", "整数", "生成{minimum}至{maximum}的随机整数", [
            _p("official.random.integer", "minimum", "最小值", "int64", required=False, default=0, control="number"),
            _p("official.random.integer", "maximum", "最大值", "int64", required=False, default=100, control="number"),
        ], "int64", "random.integer", errors=_RANDOM_ERRORS, available=True),
        _f("official.project.data_directory", "项目", "数据目录", "取得当前项目数据目录", [], "directory_ref<read_write>", "project.data_directory",
           permissions=("filesystem",), verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.clipboard.read_text", "剪贴板", "读取文本", "读取剪贴板文本", [], "optional<string>", "clipboard.read_text",
           capabilities=("host.clipboard",), permissions=("clipboard_read",), errors=_CLIPBOARD_ERRORS,
           normal_empty=True, verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.clipboard.write_text", "剪贴板", "写入文本", "写入剪贴板文本{content}", [
            _p("official.clipboard.write_text", "content", "内容", "string", control="text"),
        ], "unit", "clipboard.write_text", capabilities=("host.clipboard",), permissions=("clipboard_write",),
           side_effects=("clipboard",), errors=_CLIPBOARD_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.target.wait_online", "目标", "等待在线", "等待目标{target}在线", [
            _p("official.target.wait_online", "target", "目标", "target_ref", control="target"),
            _p("official.target.wait_online", "timeout", "超时", "duration", required=False, default=_duration(60000), control="duration"),
        ], "optional<target_info>", "target.wait_online", layer="standard",
           capabilities=("target.registry",), normal_empty=True, errors=_TARGET_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.target.read_status", "目标", "读取状态", "读取目标状态", [
            _p("official.target.read_status", "target", "目标", "optional<target_ref>", required=False, default=None, control="target"),
        ], "target_info", "target.status", capabilities=("target.registry",),
           errors=_TARGET_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.target.capture_frame", "目标", "获取画面", "获取当前目标画面", [], "frame_ref", "target.capture_frame", targets=target_types, capabilities=vision_caps, errors=_TARGET_ERRORS, verified_platforms=("windows", "android_adb")),
        _f("official.frame.save", "画面", "保存", "保存画面到{file}", [
            _p("official.frame.save", "file", "保存到", "file_ref<write>", control="file"),
            _p("official.frame.save", "frame", "画面", "optional<frame_ref>", required=False, default=None),
            _p("official.frame.save", "region", "裁剪区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.frame.save", "format", "图片格式", "enum<image_file_format>", required=False, default="png", control="select"),
            _p("official.frame.save", "quality", "JPEG 质量", "int64", required=False, default=90, control="number", constraints={"minimum": 1, "maximum": 100}),
        ], "file_ref<write>", "frame.save", targets=target_types, capabilities=vision_caps,
           permissions=("filesystem",), side_effects=("filesystem_write",), errors=_FRAME_SAVE_ERRORS,
           verified_platforms=("windows", "android_adb")),
        _f("official.frame.crop_region", "画面", "截取区域", "截取画面{region}作为临时图片", [
            _p("official.frame.crop_region", "region", "区域", "rect", control="region"),
            _p("official.frame.crop_region", "frame", "画面", "optional<frame_ref>", required=False, default=None),
        ], "image_sample", "frame.crop_region", targets=target_types, capabilities=vision_caps,
           errors=_IMAGE_SAMPLE_ERRORS, verified_platforms=("windows", "android_adb")),
        _f("official.image.compare", "图像", "比较", "比较{left}与{right}", [
            _p("official.image.compare", "left", "图片一", "image_sample"),
            _p("official.image.compare", "right", "图片二", "image_sample"),
            _p("official.image.compare", "size_strategy", "尺寸处理", "enum<image_compare_size_strategy>", required=False, default="strict", control="select"),
            _p("official.image.compare", "pixel_tolerance", "像素变化容差", "int64", required=False, default=0, control="number", constraints={"minimum": 0, "maximum": 255}),
        ], "image_comparison", "vision.compare_samples", targets=target_types, capabilities=vision_caps,
           errors=_IMAGE_SAMPLE_ERRORS, verified_platforms=("windows", "android_adb")),
        _f("official.color.read", "颜色", "读取", "读取{position}颜色", [
            _p("official.color.read", "position", "位置", "point", control="coordinate"),
            _p("official.color.read", "frame", "画面", "optional<frame_ref>", required=False, default=None),
        ], "color", "color.read", targets=target_types, capabilities=vision_caps,
           errors=_COLOR_ERRORS, verified_platforms=("windows", "android_adb")),
        _f("official.color.find", "颜色", "查找", "查找颜色{color}", [
            _p("official.color.find", "color", "颜色", "color", control="color"),
            _p("official.color.find", "tolerance", "容差", "int64", required=False, default=0,
               control="number", constraints={"minimum": 0, "maximum": 255}),
            _p("official.color.find", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.color.find", "frame", "画面", "optional<frame_ref>", required=False, default=None),
        ], "optional<point>", "color.find", targets=target_types, capabilities=vision_caps,
           errors=_COLOR_ERRORS, normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.application.start", "应用", "启动", "启动{application}", [
            _p("official.application.start", "application", "应用", "application_ref", control="application"),
            _p("official.application.start", "arguments", "启动参数", "list<string>", required=False, default=[], control="list"),
        ], "application_run_ref", "host.app.start", hosts=("windows", "android"),
           capabilities=("application.launch",), permissions=("host.launch_application",),
           side_effects=("process",), errors=_APPLICATION_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.application.wait_exit", "应用", "等待退出", "等待{process}退出", [
            _p("official.application.wait_exit", "process", "运行引用", "application_run_ref"),
            _p("official.application.wait_exit", "timeout", "超时", "duration", required=False, default=_duration(60000), control="duration"),
        ], "optional<application_exit_result>", "host.app.wait_exit",
           hosts=("windows",), capabilities=("application.lifecycle",),
           normal_empty=True, errors=_APPLICATION_ERRORS,
           verified_platforms=("windows", "no_target")),
        _f("official.application.is_running", "应用", "是否运行", "判断{process}是否仍在运行", [
            _p("official.application.is_running", "process", "运行引用", "application_run_ref"),
        ], "bool", "host.app.is_running", hosts=("windows",),
           capabilities=("application.lifecycle",), errors=_APPLICATION_ERRORS,
           verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.application.stop", "应用", "停止", "停止{process}", [
            _p("official.application.stop", "process", "运行引用", "application_run_ref"),
            _p("official.application.stop", "timeout", "退出等待", "duration", required=False, default=_duration(5000), control="duration"),
        ], "bool", "host.app.stop", hosts=("windows",),
           capabilities=("application.lifecycle",), side_effects=("process",),
           errors=_APPLICATION_ERRORS, verified_platforms=("windows", "android_adb", "no_target")),
        _f("official.window.find", "窗口", "查找", "查找窗口{selector}", [
            _p("official.window.find", "selector", "窗口选择器", "window_selector", control="key-value"),
        ], "optional<window_ref>", "window.find", hosts=("windows",), targets=("windows",),
           capabilities=("window.uia",), normal_empty=True, errors=_WINDOW_ERRORS,
           verified_platforms=("windows",)),
        _f("official.window.wait_visible", "窗口", "等待出现", "等待窗口{selector}出现", [
            _p("official.window.wait_visible", "selector", "窗口选择器", "window_selector", control="key-value"),
            _p("official.window.wait_visible", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.window.wait_visible", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
        ], "optional<window_ref>", "standard.window.wait_visible", layer="standard", hosts=("windows",), targets=("windows",), capabilities=("window.uia",), errors=_WINDOW_ERRORS + _TARGET_ERRORS, normal_empty=True, verified_platforms=("windows",)),
        _f("official.window.current", "窗口", "获取当前目标窗口", "获取当前目标窗口", [], "window_ref", "window.current", hosts=("windows",), targets=("windows",), capabilities=("window.uia",), errors=_WINDOW_ERRORS + _TARGET_ERRORS, verified_platforms=("windows",)),
        _f("official.window.activate", "窗口", "激活", "激活窗口{window}", [_p("official.window.activate", "window", "窗口", "window_ref")], "bool", "window.activate", hosts=("windows",), targets=("windows",), capabilities=("window.uia",), side_effects=("window_focus",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.close", "窗口", "关闭", "关闭窗口{window}", [_p("official.window.close", "window", "窗口", "window_ref")], "bool", "window.close", hosts=("windows",), targets=("windows",), capabilities=("window.uia",), side_effects=("window",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.read_status", "窗口", "读取状态", "读取窗口{window}状态", [_p("official.window.read_status", "window", "窗口", "window_ref")], "window_status", "window.status", hosts=("windows",), targets=("windows",), capabilities=("window.uia",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.move", "窗口", "移动", "移动{window}到{position}", [
            _p("official.window.move", "window", "窗口", "window_ref"),
            _p("official.window.move", "position", "位置", "point", control="coordinate"),
        ], "bool", "window.move", hosts=("windows",), targets=("windows",), capabilities=("window.manage",), side_effects=("window",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.resize", "窗口", "调整大小", "将{window}客户区调整为{size}", [
            _p("official.window.resize", "window", "窗口", "window_ref"),
            _p("official.window.resize", "size", "客户区尺寸", "size"),
        ], "bool", "window.resize", hosts=("windows",), targets=("windows",), capabilities=("window.manage",), side_effects=("window",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.ensure_visible", "窗口", "确保完整可见", "确保{window}完整位于屏幕工作区", [
            _p("official.window.ensure_visible", "window", "窗口", "window_ref"),
        ], "bool", "window.ensure_visible", hosts=("windows",), targets=("windows",), capabilities=("window.manage",), side_effects=("window",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.window.set_display_state", "窗口", "改变显示状态", "将{window}设为{state}", [
            _p("official.window.set_display_state", "window", "窗口", "window_ref"),
            _p("official.window.set_display_state", "state", "显示状态", "enum<window_display_state>", control="select"),
        ], "bool", "window.set_display_state", hosts=("windows",), targets=("windows",), capabilities=("window.manage",), side_effects=("window",), errors=_WINDOW_ERRORS, verified_platforms=("windows",)),
        _f("official.image.find", "图像", "查找", "查找图像{image}", [
            _p("official.image.find", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.find", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number", constraints={"minimum": 0, "maximum": 1}),
            _p("official.image.find", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.find", "frame", "使用画面", "optional<frame_ref>", required=False, default=None),
        ], "optional<image_match>", "vision.find", targets=target_types, capabilities=vision_caps, errors=_IMAGE_FIND_ERRORS, normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.image.find_all", "图像", "查找全部", "查找图像{image}的全部匹配", [
            _p("official.image.find_all", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.find_all", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number", constraints={"minimum": 0, "maximum": 1}),
            _p("official.image.find_all", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.find_all", "frame", "使用画面", "optional<frame_ref>", required=False, default=None),
            _p("official.image.find_all", "limit", "最大结果数", "int64", required=False, default=100, control="number", constraints={"minimum": 1, "maximum": 1000}),
        ], "list<image_match>", "vision.find_all", targets=target_types, capabilities=vision_caps, errors=_IMAGE_FIND_ALL_ERRORS, normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.text.recognize", "文字", "识别", "识别区域文字", [
            _p("official.text.recognize", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.text.recognize", "language", "语言", "enum<ocr_language>", required=False, default="auto", control="select"),
            _p("official.text.recognize", "frame", "使用画面", "optional<frame_ref>", required=False, default=None),
            _p("official.text.recognize", "preprocess", "预处理", "ocr_preprocess", required=False, default={
                "ocr_preprocess.field.grayscale": False,
                "ocr_preprocess.field.binary": False,
                "ocr_preprocess.field.threshold": 127,
                "ocr_preprocess.field.invert": False,
            }),
        ], "ocr_result", "text.recognize", targets=target_types, capabilities=vision_caps, errors=_OCR_ERRORS, verified_platforms=("windows", "android_adb")),
    ]

    # Standard vision/text functions are inspectable ProgramDocuments.  They
    # remain hidden until their definitions and fusion-equivalence tests exist.
    contracts.extend([
        _f("official.image.wait_visible", "图像", "等待出现", "等待图像{image}出现", [
            _p("official.image.wait_visible", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.wait_visible", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.wait_visible", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.wait_visible", "timeout", "超时", "duration", required=False, default=_duration(3000), control="duration"),
            _p("official.image.wait_visible", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
            _p("official.image.wait_visible", "stable_frames", "稳定帧", "int64", required=False, default=1, control="number", constraints={"minimum": 1, "maximum": 100}),
        ], "optional<image_match>", "standard.image.wait_visible", layer="standard", targets=target_types, capabilities=vision_caps, errors=_IMAGE_FIND_ERRORS, normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.image.wait_hidden", "图像", "等待消失", "等待图像{image}消失", [
            _p("official.image.wait_hidden", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.wait_hidden", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.wait_hidden", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.wait_hidden", "timeout", "超时", "duration", required=False, default=_duration(3000), control="duration"),
            _p("official.image.wait_hidden", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
            _p("official.image.wait_hidden", "stable_frames", "稳定帧", "int64", required=False, default=2, control="number"),
        ], "bool", "standard.image.wait_hidden", layer="standard", targets=target_types, capabilities=vision_caps, errors=_IMAGE_FIND_ERRORS, normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.image.click_once", "图像", "点击一次", "查找并点击图像{image}", [
            _p("official.image.click_once", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.click_once", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.click_once", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.click_once", "timeout", "超时", "duration", required=False, default=_duration(3000), control="duration"),
            _p("official.image.click_once", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
            _p("official.image.click_once", "button", "按键", "enum<pointer_button>", required=False, default="primary", control="select"),
        ], "optional<image_match>", "standard.image.click_once", layer="standard", targets=target_types, capabilities=vision_caps + input_caps, errors=_IMAGE_FIND_ERRORS + _TARGET_ERRORS, normal_empty=True, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.image.click_until_hidden", "图像", "点击直到消失", "点击图像{image}直到消失", [
            _p("official.image.click_until_hidden", "image", "图片", "asset_ref<image>", control="resource"),
            _p("official.image.click_until_hidden", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.click_until_hidden", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.click_until_hidden", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.image.click_until_hidden", "interval", "点击间隔", "duration", required=False, default=_duration(200), control="duration"),
            _p("official.image.click_until_hidden", "stable_frames", "稳定帧", "int64", required=False, default=2, control="number"),
            _p("official.image.click_until_hidden", "button", "按键", "enum<pointer_button>", required=False, default="primary", control="select"),
        ], "image_click_loop_result", "standard.image.click_until_hidden", layer="standard", targets=target_types, capabilities=vision_caps + input_caps, errors=_IMAGE_FIND_ERRORS + _TARGET_ERRORS, normal_empty=True, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.image.click_position_until_visible", "图像", "点击位置直到出现", "点击{position}直到图像{image}出现", [
            _p("official.image.click_position_until_visible", "position", "点击位置", "point", control="coordinate"),
            _p("official.image.click_position_until_visible", "image", "等待图片", "asset_ref<image>", control="resource"),
            _p("official.image.click_position_until_visible", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.click_position_until_visible", "region", "查找区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.click_position_until_visible", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.image.click_position_until_visible", "interval", "点击间隔", "duration", required=False, default=_duration(200), control="duration"),
            _p("official.image.click_position_until_visible", "stable_frames", "稳定帧", "int64", required=False, default=1, control="number", constraints={"minimum": 1, "maximum": 100}),
            _p("official.image.click_position_until_visible", "button", "按键", "enum<pointer_button>", required=False, default="primary", control="select"),
        ], "image_click_condition_result", "standard.image.click_position_until_visible", layer="standard", targets=target_types, capabilities=vision_caps + input_caps, errors=_IMAGE_FIND_ERRORS + _TARGET_ERRORS, normal_empty=True, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.image.click_position_until_hidden", "图像", "点击位置直到消失", "点击{position}直到图像{image}消失", [
            _p("official.image.click_position_until_hidden", "position", "点击位置", "point", control="coordinate"),
            _p("official.image.click_position_until_hidden", "image", "等待图片", "asset_ref<image>", control="resource"),
            _p("official.image.click_position_until_hidden", "similarity", "相似度", "percentage", required=False, default=0.85, control="slider-number"),
            _p("official.image.click_position_until_hidden", "region", "查找区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.image.click_position_until_hidden", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.image.click_position_until_hidden", "interval", "点击间隔", "duration", required=False, default=_duration(200), control="duration"),
            _p("official.image.click_position_until_hidden", "stable_frames", "稳定帧", "int64", required=False, default=2, control="number", constraints={"minimum": 1, "maximum": 100}),
            _p("official.image.click_position_until_hidden", "button", "按键", "enum<pointer_button>", required=False, default="primary", control="select"),
        ], "image_click_condition_result", "standard.image.click_position_until_hidden", layer="standard", targets=target_types, capabilities=vision_caps + input_caps, errors=_IMAGE_FIND_ERRORS + _TARGET_ERRORS, normal_empty=True, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.text.match", "文字", "匹配", "识别并匹配文字{text}", [
            _p("official.text.match", "text", "目标文字", "string"),
            _p("official.text.match", "mode", "匹配方式", "enum<text_match_mode>", required=False, default="contains", control="select"),
            _p("official.text.match", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.text.match", "language", "语言", "enum<ocr_language>", required=False, default="auto", control="select"),
        ], "optional<ocr_result>", "standard.text.match", layer="standard", targets=target_types, capabilities=vision_caps, errors=_OCR_ERRORS + (ErrorContractV6("text.regex_invalid", "permanent", "正则表达式无效"),), normal_empty=True, verified_platforms=("windows", "android_adb")),
        _f("official.text.wait_visible", "文字", "等待出现", "等待文字{text}出现", [
            _p("official.text.wait_visible", "text", "目标文字", "string"),
            _p("official.text.wait_visible", "mode", "匹配方式", "enum<text_match_mode>", required=False, default="contains", control="select"),
            _p("official.text.wait_visible", "region", "区域", "optional<rect>", required=False, default=None, control="region"),
            _p("official.text.wait_visible", "language", "语言", "enum<ocr_language>", required=False, default="auto", control="select"),
            _p("official.text.wait_visible", "timeout", "超时", "duration", required=False, default=_duration(3000), control="duration"),
            _p("official.text.wait_visible", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
            _p("official.text.wait_visible", "stable_frames", "稳定帧", "int64", required=False, default=1, control="number", constraints={"minimum": 1, "maximum": 100}),
        ], "optional<ocr_result>", "standard.text.wait_visible", layer="standard", targets=target_types, capabilities=vision_caps, errors=_OCR_ERRORS + (ErrorContractV6("text.regex_invalid", "permanent", "正则表达式无效"),), normal_empty=True, verified_platforms=("windows", "android_adb")),
    ])

    contracts.extend(_input_contracts(target_types, input_caps))
    contracts.extend(_control_contracts())
    contracts.extend(_file_contracts())
    contracts.extend(_network_contracts())
    contracts.extend(_message_contracts())
    return tuple(contracts)


def _input_contracts(target_types: tuple[str, ...], capabilities: tuple[str, ...]) -> list[FunctionContractV6]:
    return [
        _f("official.input.click", "输入", "点击", "点击{position}", [
            _p("official.input.click", "position", "位置", "point", control="coordinate"),
            _p("official.input.click", "button", "按键", "enum<pointer_button>", required=False, default="primary", control="select"),
            _p("official.input.click", "count", "次数", "int64", required=False, default=1, control="number", constraints={"minimum": 1}),
            _p("official.input.click", "hold", "保持时间", "duration", required=False, default=_duration(0), control="duration", constraints={"minimum": 0, "maximum": 60000}),
            _p("official.input.click", "interval", "间隔", "duration", required=False, default=_duration(80), control="duration"),
        ], "unit", "input.click", targets=target_types, capabilities=capabilities, errors=_CLICK_ERRORS, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.input.type_text", "输入", "输入文本", "输入文本{content}", [
            _p("official.input.type_text", "content", "内容", "string", control="text"),
            _p("official.input.type_text", "mode", "输入模式", "enum<text_input_mode>", required=False, default="auto", control="select"),
        ], "unit", "input.text", targets=target_types, capabilities=capabilities, errors=_TEXT_INPUT_ERRORS, side_effects=("input",), verified_platforms=("windows", "android_adb")),
        _f("official.input.scroll", "输入", "滚动", "向{direction}滚动", [
            _p("official.input.scroll", "direction", "方向", "enum<direction>", required=False, default="down", control="select"),
            _p("official.input.scroll", "mode", "模式", "enum<scroll_mode>", required=False, default="auto", control="select"),
            _p("official.input.scroll", "distance", "距离", "float64", required=False, default=0.6, control="number"),
            _p("official.input.scroll", "start", "起点", "optional<point>", required=False, default=None, control="coordinate"),
            _p("official.input.scroll", "duration", "移动时长", "duration", required=False, default=_duration(350), control="duration"),
            _p("official.input.scroll", "hold", "终点保持", "duration", required=False, default=_duration(80), control="duration"),
        ], "unit", "input.scroll", targets=target_types, capabilities=capabilities, errors=_SCROLL_ERRORS, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.input.drag", "输入", "拖拽", "沿{path}拖拽", [
            _p("official.input.drag", "path", "路径", "gesture_path", control="gesture-path"),
            _p("official.input.drag", "duration", "移动时长", "duration", required=False, default=_duration(350), control="duration", constraints={"minimum": 1, "maximum": 60000}),
            _p("official.input.drag", "easing", "缓动", "enum<gesture_easing>", required=False, default="linear", control="select"),
        ], "unit", "input.drag", targets=target_types, capabilities=capabilities, errors=_DRAG_ERRORS, side_effects=("input",), verified_platforms=("windows", "android_adb"), android_min_api=24),
        _f("official.input.key", "输入", "按键", "按下{key}", [
            _p("official.input.key", "key", "按键或组合键", "key_chord", control="key-chord"),
            _p("official.input.key", "action", "动作", "enum<key_action>", required=False, default="press", control="select"),
            _p("official.input.key", "hold", "保持", "duration", required=False, default=_duration(0), control="duration"),
        ], "unit", "input.key", targets=target_types, capabilities=("input.key",), errors=_TARGET_ERRORS, side_effects=("input",), verified_platforms=("windows", "android_adb")),
        _f("official.input.move_pointer", "输入", "移动指针", "移动指针到{position}", [
            _p("official.input.move_pointer", "position", "位置", "point", control="coordinate"),
            _p("official.input.move_pointer", "duration", "移动时长", "duration", required=False, default=_duration(0), control="duration"),
        ], "unit", "input.move_pointer", hosts=("windows",), targets=("windows",), capabilities=("pointer.move",), errors=_TARGET_ERRORS, side_effects=("input",), verified_platforms=("windows",)),
    ]


def _control_contracts() -> list[FunctionContractV6]:
    hosts = ("windows", "android")
    targets = ("windows", "android_adb", "android_local")
    verified = ("windows", "android_adb")
    return [
        _f("official.control.find", "控件", "查找", "查找控件{selector}", [
            _p("official.control.find", "selector", "控件选择器", "control_selector", control="control-selector"),
        ], "optional<control_ref>", "control.find", hosts=hosts, targets=targets, capabilities=("control.semantic",), normal_empty=True, errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.wait_visible", "控件", "等待出现", "等待控件{selector}出现", [
            _p("official.control.wait_visible", "selector", "控件选择器", "control_selector", control="control-selector"),
            _p("official.control.wait_visible", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.control.wait_visible", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
        ], "optional<control_ref>", "standard.control.wait_visible", layer="standard",
           hosts=hosts, targets=targets, capabilities=("control.semantic",), normal_empty=True,
           errors=_CONTROL_ERRORS + _TARGET_ERRORS, verified_platforms=verified),
        _f("official.control.wait_hidden", "控件", "等待消失", "等待控件{selector}消失", [
            _p("official.control.wait_hidden", "selector", "控件选择器", "control_selector", control="control-selector"),
            _p("official.control.wait_hidden", "timeout", "超时", "duration", required=False, default=_duration(10000), control="duration"),
            _p("official.control.wait_hidden", "interval", "检查间隔", "duration", required=False, default=_duration(100), control="duration"),
        ], "bool", "standard.control.wait_hidden", layer="standard",
           hosts=hosts, targets=targets, capabilities=("control.semantic",), normal_empty=True,
           errors=_CONTROL_ERRORS + _TARGET_ERRORS, verified_platforms=verified),
        _f("official.control.click", "控件", "点击", "点击控件{control}", [
            _p("official.control.click", "control", "控件", "control_ref", control="control-reference"),
            _p("official.control.click", "mode", "调用模式", "enum<control_action_mode>", required=False, default="auto", control="select"),
        ], "bool", "control.click", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.click_selector", "控件", "按选择器点击", "点击控件{selector}", [
            _p("official.control.click_selector", "selector", "控件选择器", "control_selector", control="control-selector"),
            _p("official.control.click_selector", "mode", "调用模式", "enum<control_action_mode>", required=False, default="auto", control="select"),
        ], "bool", "control.click_selector", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.read_text", "控件", "读取文本", "读取控件{control}的文字", [
            _p("official.control.read_text", "control", "控件", "control_ref", control="control-reference"),
        ], "string", "control.read_text", hosts=hosts, targets=targets, capabilities=("control.semantic",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.type_text", "控件", "输入文本", "向控件{control}输入{content}", [
            _p("official.control.type_text", "control", "控件", "control_ref", control="control-reference"),
            _p("official.control.type_text", "content", "内容", "string"),
            _p("official.control.type_text", "mode", "输入模式", "enum<control_text_mode>", required=False, default="auto", control="select"),
        ], "unit", "control.input_text", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.read_status", "控件", "读取状态", "读取控件{control}状态", [
            _p("official.control.read_status", "control", "控件", "control_ref", control="control-reference"),
        ], "control_status", "control.read_status", hosts=hosts, targets=targets, capabilities=("control.semantic",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.focus", "控件", "聚焦", "聚焦控件{control}", [
            _p("official.control.focus", "control", "控件", "control_ref", control="control-reference"),
        ], "bool", "control.focus", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.set_value", "控件", "设置值", "设置控件{control}为{value}", [
            _p("official.control.set_value", "control", "控件", "control_ref", control="control-reference"),
            _p("official.control.set_value", "value", "值", "string"),
        ], "bool", "control.set_value", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.select", "控件", "选择项目", "选择控件{control}的项目", [
            _p("official.control.select", "control", "项目控件", "control_ref", control="control-reference"),
        ], "bool", "control.select", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.toggle", "控件", "切换开关", "切换控件{control}开关", [
            _p("official.control.toggle", "control", "开关控件", "control_ref", control="control-reference"),
        ], "bool", "control.toggle", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified),
        _f("official.control.scroll_into_view", "控件", "滚动到控件", "滚动到控件{control}", [
            _p("official.control.scroll_into_view", "control", "控件", "control_ref", control="control-reference"),
        ], "bool", "control.scroll_into_view", hosts=hosts, targets=targets, capabilities=("control.semantic",), side_effects=("input",), errors=_CONTROL_ERRORS, verified_platforms=verified, android_min_api=23),
    ]


def _file_contracts() -> list[FunctionContractV6]:
    all_hosts = ("windows", "android")
    def ff(
        fid: str,
        ns: str,
        name: str,
        summary: str,
        params: list[ParameterContractV6],
        ret: str,
        opcode: str,
        *,
        side=(),
        dangerous=False,
        verified_platforms=("windows", "android_adb", "no_target"),
    ):
        return _f(
            fid,
            ns,
            name,
            summary,
            params,
            ret,
            opcode,
            hosts=all_hosts,
            permissions=("filesystem",),
            side_effects=side,
            errors=_FILE_ERRORS,
            dangerous=dangerous,
            verified_platforms=verified_platforms,
        )
    return [
        ff("official.file.exists", "文件", "存在", "检查文件{file}是否存在", [_p("official.file.exists", "file", "文件", "file_ref<read>", control="file")], "bool", "file.exists"),
        ff("official.file.read_text", "文件", "读取文本", "读取文件{file}的文本", [_p("official.file.read_text", "file", "文件", "file_ref<read>", control="file"), _p("official.file.read_text", "encoding", "编码", "enum<text_encoding>", required=False, default="utf-8", control="select")], "string", "file.read_text"),
        ff("official.file.write_text", "文件", "写入文本", "写入文件{file}", [_p("official.file.write_text", "file", "文件", "file_ref<write>", control="file"), _p("official.file.write_text", "content", "内容", "string"), _p("official.file.write_text", "encoding", "编码", "enum<text_encoding>", required=False, default="utf-8", control="select")], "unit", "file.write_text", side=("filesystem_write",)),
        ff("official.file.append_text", "文件", "追加文本", "追加到文件{file}", [_p("official.file.append_text", "file", "文件", "file_ref<write>", control="file"), _p("official.file.append_text", "content", "内容", "string"), _p("official.file.append_text", "encoding", "编码", "enum<text_encoding>", required=False, default="utf-8", control="select")], "unit", "file.append_text", side=("filesystem_write",)),
        ff("official.file.replace_text", "文件", "替换文本", "在文件{file}中替换文本", [_p("official.file.replace_text", "file", "文件", "file_ref<write>", control="file"), _p("official.file.replace_text", "search", "查找内容", "string"), _p("official.file.replace_text", "replacement", "替换内容", "string"), _p("official.file.replace_text", "scope", "范围", "enum<replace_scope>", required=False, default="all", control="select"), _p("official.file.replace_text", "encoding", "编码", "enum<text_encoding>", required=False, default="utf-8", control="select")], "int64", "file.replace_text", side=("filesystem_write",)),
        ff("official.file.read_json", "文件", "读取JSON", "读取JSON文件{file}", [_p("official.file.read_json", "file", "文件", "file_ref<read>", control="file")], "json_value", "file.read_json"),
        ff("official.file.write_json", "文件", "写入JSON", "写入JSON文件{file}", [_p("official.file.write_json", "file", "文件", "file_ref<write>", control="file"), _p("official.file.write_json", "data", "数据", "json_value", control="json")], "unit", "file.write_json", side=("filesystem_write",)),
        ff("official.file.delete", "文件", "删除", "删除文件{file}", [_p("official.file.delete", "file", "文件", "file_ref<delete>", control="file")], "bool", "file.delete", side=("filesystem_delete",)),
        ff("official.file.copy", "文件", "复制", "复制文件{source}到{destination}", [_p("official.file.copy", "source", "来源", "file_ref<read>", control="file"), _p("official.file.copy", "destination", "目标", "file_ref<write>", control="file"), _p("official.file.copy", "conflict", "冲突策略", "enum<file_conflict>", required=False, default="error", control="select")], "file_ref", "file.copy", side=("filesystem_write",)),
        ff("official.file.move", "文件", "移动", "移动文件{source}到{destination}", [_p("official.file.move", "source", "来源", "file_ref<read_delete>", control="file"), _p("official.file.move", "destination", "目标", "file_ref<write>", control="file"), _p("official.file.move", "conflict", "冲突策略", "enum<file_conflict>", required=False, default="error", control="select")], "file_ref", "file.move", side=("filesystem_write", "filesystem_delete")),
        ff("official.directory.exists", "目录", "存在", "检查目录{directory}是否存在", [_p("official.directory.exists", "directory", "目录", "directory_ref<read>", control="directory")], "bool", "directory.exists"),
        ff("official.directory.create", "目录", "创建", "在{parent}内创建{relative_path}", [_p("official.directory.create", "parent", "父目录", "directory_ref<create>", control="directory"), _p("official.directory.create", "relative_path", "相对位置", "relative_path"), _p("official.directory.create", "existing", "已存在策略", "enum<directory_existing>", required=False, default="return_existing", control="select")], "directory_ref", "directory.create", side=("filesystem_write",)),
        ff("official.directory.list", "目录", "列出", "列出{directory}内容", [_p("official.directory.list", "directory", "目录", "directory_ref<list>", control="directory"), _p("official.directory.list", "filter", "筛选", "filesystem_filter", required=False, default={}), _p("official.directory.list", "recursive", "递归", "bool", required=False, default=False, control="toggle")], "list<filesystem_entry>", "directory.list"),
        ff("official.directory.copy", "目录", "复制", "复制{source}到{destination_parent}", [_p("official.directory.copy", "source", "来源", "directory_ref<read>", control="directory"), _p("official.directory.copy", "destination_parent", "目标父目录", "directory_ref<create>", control="directory"), _p("official.directory.copy", "name", "目标名称", "string"), _p("official.directory.copy", "conflict", "冲突策略", "enum<tree_conflict>", required=False, default="error", control="select")], "tree_operation_report", "directory.copy", side=("filesystem_write",)),
        ff("official.directory.move", "目录", "移动", "移动{source}到{destination_parent}", [_p("official.directory.move", "source", "来源", "directory_ref<move>", control="directory"), _p("official.directory.move", "destination_parent", "目标父目录", "directory_ref<create>", control="directory"), _p("official.directory.move", "name", "目标名称", "string"), _p("official.directory.move", "conflict", "冲突策略", "enum<tree_conflict>", required=False, default="error", control="select")], "tree_operation_report", "directory.move", side=("filesystem_write", "filesystem_delete")),
        ff("official.directory.delete_empty", "目录", "删除", "删除空目录{directory}", [_p("official.directory.delete_empty", "directory", "目录", "directory_ref<delete_empty>", control="directory")], "bool", "directory.delete", side=("filesystem_delete",)),
        ff("official.directory.delete_tree", "目录", "递归删除", "删除目录{directory}及全部后代", [_p("official.directory.delete_tree", "directory", "目录", "directory_ref<delete_tree>", control="directory")], "tree_delete_report", "directory.delete_tree", side=("filesystem_delete",), dangerous=True, verified_platforms=("windows", "android_adb", "no_target")),
    ]


def _network_contracts() -> list[FunctionContractV6]:
    verified_platforms = ("windows", "android_adb", "no_target")

    def shared(owner: str, *, timeout: int) -> list[ParameterContractV6]:
        return [
            _p(owner, "url", "网址", "url"),
            _p(owner, "query", "查询参数", "list<http_pair>", required=False, default=[], control="key-value"),
            _p(owner, "headers", "请求头", "list<http_pair>", required=False, default=[], control="key-value"),
            _p(owner, "redirect", "重定向", "enum<http_redirect>", required=False, default="same_origin", control="select"),
            _p(owner, "timeout", "总超时", "duration", required=False, default=_duration(timeout), control="duration"),
            _p(owner, "max_response_bytes", "最大文本响应", "int64", required=False, default=4 * 1024 * 1024, control="number"),
            _p(owner, "max_redirects", "最大重定向次数", "int64", required=False, default=5, control="number"),
        ]

    request_parameters = [
        _p("official.network.request", "method", "方法", "enum<http_method>", required=False, default="GET", control="select"),
        *shared("official.network.request", timeout=30_000),
        _p("official.network.request", "body", "正文", "optional<http_body>", required=False, default=None),
    ]
    upload_parameters = [
        *shared("official.network.upload_file", timeout=60_000),
        _p("official.network.upload_file", "fields", "multipart 字段", "list<multipart_field>", control="list"),
        _p("official.network.upload_file", "max_file_bytes", "单文件最大大小", "int64", required=False, default=512 * 1024 * 1024, control="number"),
    ]
    download_parameters = [
        *shared("official.network.download_file", timeout=60_000),
        _p("official.network.download_file", "destination", "保存到", "file_ref<write>", control="file"),
        _p("official.network.download_file", "max_file_bytes", "最大下载大小", "int64", required=False, default=512 * 1024 * 1024, control="number"),
    ]
    return [
        _f(
            "official.network.request", "网络", "请求", "使用{method}请求{url}",
            request_parameters, "http_response", "network.request",
            permissions=("network",), side_effects=("network",),
            errors=_NETWORK_ERRORS, network_level="declared",
            verified_platforms=verified_platforms,
        ),
        _f(
            "official.network.upload_file", "网络", "上传文件", "上传文件到{url}",
            upload_parameters, "http_response", "network.upload_file",
            permissions=("network", "filesystem.read"), side_effects=("network",),
            errors=_NETWORK_ERRORS + _NETWORK_FILE_ERRORS, network_level="declared",
            verified_platforms=verified_platforms,
        ),
        _f(
            "official.network.download_file", "网络", "下载文件", "从{url}下载到{destination}",
            download_parameters, "http_download_result", "network.download_file",
            permissions=("network", "filesystem.write"),
            side_effects=("network", "filesystem_write"),
            errors=_NETWORK_ERRORS + _NETWORK_FILE_ERRORS, network_level="declared",
            verified_platforms=verified_platforms,
        ),
    ]


def _message_contracts() -> list[FunctionContractV6]:
    verified_platforms = ("windows", "android_adb", "no_target")
    return [
        _f(
            "official.message.send", "消息", "发送", "向{recipients}发送消息{name}",
            [
                _p("official.message.send", "recipients", "接收实例", "list<instance_ref>", control="instance-multi-select"),
                _p("official.message.send", "name", "消息名称", "string"),
                _p("official.message.send", "content", "内容", "message_value"),
                _p("official.message.send", "ttl", "有效期", "duration", required=False, default=_duration(300000), control="duration"),
            ],
            "message_batch", "message.send",
            permissions=("messaging",), side_effects=("message",),
            errors=_MESSAGE_ERRORS, network_level="lan",
            verified_platforms=verified_platforms, android_min_api=23,
        ),
        _f(
            "official.message.wait_receive", "消息", "等待接收", "等待接收消息{name}",
            [
                _p("official.message.wait_receive", "name", "消息名称", "string"),
                _p("official.message.wait_receive", "sender", "来源实例", "optional<instance_ref>", required=False, default=None, control="instance"),
                _p("official.message.wait_receive", "timeout", "超时", "duration", required=False, default=_duration(60000), control="duration"),
            ],
            "optional<received_message>", "message.wait_receive",
            permissions=("messaging",), errors=_MESSAGE_ERRORS,
            normal_empty=True, network_level="lan",
            verified_platforms=verified_platforms, android_min_api=23,
        ),
        _f(
            "official.message.wait_read", "消息", "等待已读", "等待{batch}被读取",
            [
                _p("official.message.wait_read", "batch", "发送批次", "message_batch"),
                _p(
                    "official.message.wait_read", "mode", "等待方式",
                    "enum<read_wait_mode>", required=False, default="all", control="select",
                    constraints={"choices": [
                        {"label": "全部", "value": "all"},
                        {"label": "任一", "value": "any"},
                    ]},
                ),
                _p("official.message.wait_read", "timeout", "超时", "duration", required=False, default=_duration(60000), control="duration"),
            ],
            "message_read_wait_result", "message.wait_read",
            permissions=("messaging",), errors=_MESSAGE_ERRORS,
            network_level="lan", verified_platforms=verified_platforms,
            android_min_api=23,
        ),
        _f(
            "official.message.cancel", "消息", "取消", "取消{batch}中的未读消息",
            [
                _p("official.message.cancel", "batch", "发送批次", "message_batch"),
                _p("official.message.cancel", "recipient", "接收实例", "optional<instance_ref>", required=False, default=None, control="instance"),
            ],
            "message_cancel_result", "message.cancel",
            permissions=("messaging",), side_effects=("message",),
            errors=_MESSAGE_ERRORS, network_level="lan",
            verified_platforms=verified_platforms, android_min_api=23,
        ),
    ]


OFFICIAL_FUNCTION_CONTRACTS = _official_contracts()


class OfficialFunctionRegistryV6:
    def __init__(self, contracts: Iterable[FunctionContractV6] = OFFICIAL_FUNCTION_CONTRACTS) -> None:
        self._contracts = tuple(contracts)
        self._by_id = {item.function_id: item for item in self._contracts}
        self._by_name = {item.qualified_name: item for item in self._contracts}
        if len(self._by_id) != len(self._contracts):
            raise ValueError("duplicate official function_id")
        if len(self._by_name) != len(self._contracts):
            raise ValueError("duplicate official qualified_name")
        parameter_ids = [parameter.parameter_id for item in self._contracts for parameter in item.parameters]
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("duplicate official parameter_id")
        for contract in self._contracts:
            platforms = tuple(item.platform for item in contract.platform_support)
            if platforms != PLATFORMS:
                raise ValueError(
                    f"function platform matrix must contain {PLATFORMS}: {contract.function_id}"
                )

    def require(self, function_id: str) -> FunctionContractV6:
        try:
            return self._by_id[function_id]
        except KeyError as exc:
            raise KeyError(f"unknown official function: {function_id}") from exc

    def by_qualified_name(self, qualified_name: str) -> FunctionContractV6:
        try:
            return self._by_name[qualified_name]
        except KeyError as exc:
            raise KeyError(f"unknown official function: {qualified_name}") from exc

    def complete_catalog(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._contracts]

    def available_catalog(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._contracts if item.verified_platforms]


official_function_registry_v6 = OfficialFunctionRegistryV6()
