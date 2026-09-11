"""Stable named-record contracts for project format 6.

The runtime stores record values as dictionaries keyed by ``field_id``.  This
module is the single authoritative catalogue used by the compiler, member
picker and runtime validation; display names are presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RecordAuthoringMode = Literal["constructible", "reference_only", "capture_only"]
RecordEditorStrategy = Literal[
    "inline_record", "focused", "reference", "capture",
]

_NO_DEFAULT = object()


@dataclass(frozen=True)
class RecordFieldV6:
    field_id: str
    display_name: str
    value_type: str
    description: str = ""
    required: bool = True
    has_default: bool = False
    default: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordTypeV6:
    type_id: str
    display_name: str
    fields: tuple[RecordFieldV6, ...]
    required_any: tuple[str, ...] = ()
    non_negative: tuple[str, ...] = ()
    # Safe by default: a newly registered runtime record cannot accidentally
    # become a directly constructible authoring form.
    authoring_mode: RecordAuthoringMode = "reference_only"
    editor_strategy: RecordEditorStrategy = "reference"


def _field(
    owner: str,
    name: str,
    display_name: str,
    value_type: str,
    description: str = "",
    *,
    required: bool | None = None,
    default: Any = _NO_DEFAULT,
    constraints: dict[str, Any] | None = None,
    control: str = "auto",
    importance: str = "primary",
    placeholder: str = "",
    help_text: str = "",
    visible_when: dict[str, Any] | None = None,
    actions: tuple[dict[str, Any], ...] = (),
) -> RecordFieldV6:
    resolved_required = (
        not value_type.startswith("optional<")
        if required is None
        else required
    )
    ui: dict[str, Any] = {
        "control": control,
        "importance": importance,
    }
    if placeholder:
        ui["placeholder"] = placeholder
    resolved_help = help_text or description
    if resolved_help:
        ui["help"] = resolved_help
    if visible_when is not None:
        ui["visible_when"] = dict(visible_when)
    if actions:
        ui["actions"] = [dict(action) for action in actions]
    return RecordFieldV6(
        field_id=f"{owner}.field.{name}",
        display_name=display_name,
        value_type=value_type,
        description=description,
        required=resolved_required,
        has_default=default is not _NO_DEFAULT,
        default=None if default is _NO_DEFAULT else default,
        constraints=dict(constraints or {}),
        ui=ui,
    )


def _stable_field(
    field_id: str,
    display_name: str,
    value_type: str,
    description: str = "",
    *,
    required: bool | None = None,
    default: Any = _NO_DEFAULT,
    constraints: dict[str, Any] | None = None,
    control: str = "auto",
    importance: str = "primary",
    placeholder: str = "",
    help_text: str = "",
    visible_when: dict[str, Any] | None = None,
    actions: tuple[dict[str, Any], ...] = (),
) -> RecordFieldV6:
    """Describe an already-frozen runtime field whose ID predates namespacing."""

    synthetic = _field(
        "stable", "field", display_name, value_type, description,
        required=required,
        default=default,
        constraints=constraints,
        control=control,
        importance=importance,
        placeholder=placeholder,
        help_text=help_text,
        visible_when=visible_when,
        actions=actions,
    )
    return RecordFieldV6(
        field_id=field_id,
        display_name=synthetic.display_name,
        value_type=synthetic.value_type,
        description=synthetic.description,
        required=synthetic.required,
        has_default=synthetic.has_default,
        default=synthetic.default,
        constraints=synthetic.constraints,
        ui=synthetic.ui,
    )


def record_field_payload(field_contract: RecordFieldV6) -> dict[str, Any]:
    """Serialize one record field using the same shape as function parameters."""

    return {
        "field_id": field_contract.field_id,
        "display_name": field_contract.display_name,
        "value_type": field_contract.value_type,
        "description": field_contract.description,
        "required": field_contract.required,
        "has_default": field_contract.has_default,
        "default": field_contract.default,
        "constraints": dict(field_contract.constraints),
        "ui": dict(field_contract.ui),
    }


def record_type_payload(contract: RecordTypeV6) -> dict[str, Any]:
    """Serialize authoritative authoring and validation metadata for one record."""

    return {
        "type_id": contract.type_id,
        "display_name": contract.display_name,
        "authoring_mode": contract.authoring_mode,
        "editor_strategy": contract.editor_strategy,
        "required_any": list(contract.required_any),
        "non_negative": list(contract.non_negative),
        "fields": [record_field_payload(item) for item in contract.fields],
    }


def _inline_record(**values: Any) -> RecordTypeV6:
    return RecordTypeV6(
        **values, authoring_mode="constructible", editor_strategy="inline_record",
    )


def _focused_record(**values: Any) -> RecordTypeV6:
    return RecordTypeV6(
        **values, authoring_mode="constructible", editor_strategy="focused",
    )


def _reference_record(**values: Any) -> RecordTypeV6:
    return RecordTypeV6(
        **values, authoring_mode="reference_only", editor_strategy="reference",
    )


def _capture_record(**values: Any) -> RecordTypeV6:
    return RecordTypeV6(
        **values, authoring_mode="capture_only", editor_strategy="capture",
    )


RECORD_TYPE_CONTRACTS: dict[str, RecordTypeV6] = {
    "color": _inline_record(
        type_id="color", display_name="颜色", fields=(
            _field(
                "color", "red", "红", "int64", control="number",
                constraints={"minimum": 0, "maximum": 255}, placeholder="0–255",
            ),
            _field(
                "color", "green", "绿", "int64", control="number",
                constraints={"minimum": 0, "maximum": 255}, placeholder="0–255",
            ),
            _field(
                "color", "blue", "蓝", "int64", control="number",
                constraints={"minimum": 0, "maximum": 255}, placeholder="0–255",
            ),
            _field(
                "color", "alpha", "透明度", "int64", control="number",
                constraints={"minimum": 0, "maximum": 255}, placeholder="0–255",
            ),
        ),
    ),
    "size": _inline_record(
        type_id="size", display_name="尺寸", fields=(
            _stable_field(
                "width", "宽度", "int64", "范围 1 至 32767",
                required=True, constraints={"minimum": 1, "maximum": 32767},
                control="number", placeholder="例如：1280",
            ),
            _stable_field(
                "height", "高度", "int64", "范围 1 至 32767",
                required=True, constraints={"minimum": 1, "maximum": 32767},
                control="number", placeholder="例如：720",
            ),
        ),
    ),
    "key_chord": _inline_record(
        type_id="key_chord", display_name="按键组合", fields=(
            _field(
                "key_chord", "keys", "按键", "list<string>",
                constraints={"min_items": 1, "max_items": 4, "unique_items": True},
                control="list", placeholder="例如：Ctrl + A",
            ),
        ),
    ),
    "frame_ref": _reference_record(
        type_id="frame_ref",
        display_name="画面引用",
        fields=(
            _field("frame_ref", "frame_id", "帧 ID", "string", "当前运行内的不可变画面编号"),
            _field("frame_ref", "source_target", "来源目标", "target_ref"),
            _field("frame_ref", "space_version", "空间版本", "string"),
            _field("frame_ref", "sequence", "采集序号", "int64"),
            _field("frame_ref", "captured_at", "采集时间", "datetime"),
            _field("frame_ref", "width", "宽度", "int64"),
            _field("frame_ref", "height", "高度", "int64"),
        ),
    ),
    "image_sample": _reference_record(
        type_id="image_sample",
        display_name="画面区域样本",
        fields=(
            _field("image_sample", "sample_id", "样本 ID", "string", "仅在当前运行内有效的图片样本编号"),
            _field("image_sample", "source_frame", "来源画面", "frame_ref"),
            _field("image_sample", "source_target", "来源目标", "target_ref"),
            _field("image_sample", "space_version", "空间版本", "string"),
            _field("image_sample", "region", "实际区域", "rect"),
            _field("image_sample", "width", "宽度", "int64"),
            _field("image_sample", "height", "高度", "int64"),
        ),
    ),
    "image_comparison": _reference_record(
        type_id="image_comparison",
        display_name="图像比较结果",
        fields=(
            _field("image_comparison", "similarity", "相似度", "percentage"),
            _field("image_comparison", "same_size", "尺寸一致", "bool"),
            _field("image_comparison", "compared_width", "比较宽度", "int64"),
            _field("image_comparison", "compared_height", "比较高度", "int64"),
            _field("image_comparison", "changed_pixel_ratio", "变化像素比例", "percentage"),
            _field("image_comparison", "difference_region", "变化区域", "optional<rect>"),
            _field("image_comparison", "left", "左侧样本", "image_sample"),
            _field("image_comparison", "right", "右侧样本", "image_sample"),
        ),
    ),
    "image_match": _reference_record(
        type_id="image_match",
        display_name="图像匹配结果",
        fields=(
            _field("image_match", "region", "匹配区域", "rect"),
            _field("image_match", "center", "中心", "point"),
            _field("image_match", "similarity", "相似度", "percentage"),
            _field("image_match", "source_asset", "来源图片", "asset_ref<image>"),
            _field("image_match", "source_frame", "来源画面", "frame_ref"),
            _field("image_match", "source_target", "来源目标", "target_ref"),
            _field("image_match", "space_version", "空间版本", "string"),
        ),
    ),
    "ocr_line": _reference_record(
        type_id="ocr_line",
        display_name="文字识别行",
        fields=(
            _field("ocr_line", "text", "文字", "string"),
            _field("ocr_line", "region", "区域", "rect"),
        ),
    ),
    "ocr_result": _reference_record(
        type_id="ocr_result",
        display_name="文字识别结果",
        fields=(
            _field("ocr_result", "text", "全文", "string"),
            _field("ocr_result", "lines", "文字行", "list<ocr_line>"),
            _field("ocr_result", "region", "识别区域", "rect"),
            _field("ocr_result", "source_frame", "来源画面", "frame_ref"),
            _field("ocr_result", "source_target", "来源目标", "target_ref"),
            _field("ocr_result", "space_version", "空间版本", "string"),
        ),
    ),
    "ocr_preprocess": _inline_record(
        type_id="ocr_preprocess",
        display_name="OCR 预处理",
        fields=(
            _field("ocr_preprocess", "grayscale", "灰度化", "bool", required=False, default=False, control="toggle"),
            _field("ocr_preprocess", "binary", "二值化", "bool", required=False, default=False, control="toggle"),
            _field(
                "ocr_preprocess", "threshold", "阈值", "int64",
                required=False,
                default=127,
                constraints={"minimum": 0, "maximum": 255},
                control="slider-number",
                placeholder="0–255",
                help_text="仅在开启二值化时生效。",
                visible_when={
                    "field_id": "ocr_preprocess.field.binary",
                    "operator": "equals",
                    "value": True,
                },
            ),
            _field("ocr_preprocess", "invert", "反色", "bool", required=False, default=False, control="toggle"),
        ),
    ),
    "image_click_loop_result": _reference_record(
        type_id="image_click_loop_result",
        display_name="图像连续点击结果",
        fields=(
            _field("image_click_loop_result", "hidden", "已消失", "bool"),
            _field("image_click_loop_result", "click_count", "点击次数", "int64"),
            _field("image_click_loop_result", "last_match", "最后匹配", "optional<image_match>"),
        ),
    ),
    "image_click_condition_result": _reference_record(
        type_id="image_click_condition_result",
        display_name="点击并验证结果",
        fields=(
            _field("image_click_condition_result", "reached", "目标状态已达到", "bool"),
            _field("image_click_condition_result", "click_count", "点击次数", "int64"),
            _field("image_click_condition_result", "last_match", "最后匹配", "optional<image_match>"),
        ),
    ),
    "tree_delete_report": _reference_record(
        type_id="tree_delete_report",
        display_name="目录递归删除报告",
        fields=(
            _field("tree_delete_report", "complete", "全部完成", "bool"),
            _field("tree_delete_report", "files_deleted", "已删除文件", "int64"),
            _field("tree_delete_report", "directories_deleted", "已删除目录", "int64"),
            _field("tree_delete_report", "failures", "失败明细", "list<json_value>"),
        ),
    ),
    "filesystem_filter": _inline_record(
        type_id="filesystem_filter",
        display_name="目录筛选",
        fields=(
            _field(
                "filesystem_filter", "pattern", "名称模式", "optional<string>",
                "支持 * 和 ? 通配符", default="*", control="text",
                placeholder="例如：*.png",
            ),
            _field(
                "filesystem_filter", "limit", "最大条数", "optional<int64>",
                default=None, constraints={"minimum": 1, "maximum": 1000},
                control="number", placeholder="留空最多返回 1000 条",
            ),
        ),
    ),
    "filesystem_entry": _reference_record(
        type_id="filesystem_entry",
        display_name="文件系统条目",
        fields=(
            _field("filesystem_entry", "name", "名称", "string"),
            _field("filesystem_entry", "entry_type", "类型", "enum<filesystem_entry_type>"),
            _field("filesystem_entry", "size", "大小", "optional<int64>"),
            _field("filesystem_entry", "file", "文件引用", "optional<file_ref>"),
            _field("filesystem_entry", "directory", "目录引用", "optional<directory_ref>"),
        ),
    ),
    "tree_operation_report": _reference_record(
        type_id="tree_operation_report",
        display_name="目录操作报告",
        fields=(
            _field("tree_operation_report", "complete", "全部完成", "bool"),
            _field("tree_operation_report", "processed_files", "已处理文件", "int64"),
            _field("tree_operation_report", "processed_directories", "已处理目录", "int64"),
            _field("tree_operation_report", "skipped", "跳过项", "list<string>"),
            _field("tree_operation_report", "failures", "失败明细", "list<json_value>"),
            _field("tree_operation_report", "destination", "目标目录", "optional<directory_ref>"),
        ),
    ),
    "window_selector": _inline_record(
        type_id="window_selector",
        display_name="窗口选择器",
        fields=(
            _field(
                "window_selector", "title", "窗口标题", "optional<string>",
                control="text", placeholder="例如：记事本",
            ),
            _field(
                "window_selector",
                "match_mode",
                "标题匹配方式",
                "optional<enum<window_match_mode>>",
                "未填写时使用“包含”",
                default="contains",
                control="select",
            ),
            _field(
                "window_selector", "class_name", "窗口类名", "optional<string>",
                control="text", importance="advanced", placeholder="例如：Notepad",
            ),
            _field(
                "window_selector", "process_id", "进程 ID", "optional<int64>",
                constraints={"minimum": 0}, control="number",
                importance="advanced", placeholder="例如：1234",
            ),
            _field(
                "window_selector",
                "index",
                "匹配序号",
                "optional<int64>",
                "从 0 开始；存在多个匹配窗口时选择第几个",
                default=0,
                constraints={"minimum": 0},
                control="number",
                importance="advanced",
                placeholder="从 0 开始",
            ),
        ),
        required_any=(
            "window_selector.field.title",
            "window_selector.field.class_name",
            "window_selector.field.process_id",
        ),
        non_negative=(
            "window_selector.field.process_id",
            "window_selector.field.index",
        ),
    ),
    "message_recipient_status": _reference_record(
        type_id="message_recipient_status",
        display_name="消息收件状态",
        fields=(
            _stable_field("message_id", "消息 ID", "string"),
            _stable_field("recipient", "接收实例", "instance_ref"),
            _stable_field("recipient_display_name", "接收实例名称", "string"),
            _stable_field("status", "状态", "string"),
            _stable_field("transport", "传输方式", "string"),
            _stable_field("transport_error", "传输错误", "string"),
            _stable_field("created_at", "创建时间", "datetime"),
            _stable_field("expires_at", "过期时间", "datetime"),
        ),
    ),
    "message_batch": _reference_record(
        type_id="message_batch",
        display_name="消息发送批次",
        fields=(
            _stable_field("batch_id", "批次 ID", "string"),
            _stable_field("name", "消息名称", "string"),
            _stable_field("created_at", "创建时间", "datetime"),
            _stable_field("expires_at", "过期时间", "datetime"),
            _stable_field("recipients", "收件明细", "list<message_recipient_status>"),
        ),
    ),
    "received_message": _reference_record(
        type_id="received_message",
        display_name="收到的消息",
        fields=(
            _stable_field("message_id", "消息 ID", "string"),
            _stable_field("batch_id", "批次 ID", "string"),
            _stable_field("name", "消息名称", "string"),
            _stable_field("content", "内容", "message_value"),
            _stable_field("sender", "发送实例", "instance_ref"),
            _stable_field("sender_display_name", "发送实例名称", "string"),
            _stable_field("created_at", "创建时间", "datetime"),
            _stable_field("expires_at", "过期时间", "datetime"),
        ),
    ),
    "message_read_wait_result": _reference_record(
        type_id="message_read_wait_result",
        display_name="消息已读结果",
        fields=(
            _stable_field("batch_id", "批次 ID", "string"),
            _stable_field("mode", "等待方式", "enum<read_wait_mode>"),
            _stable_field("condition_met", "条件已满足", "bool"),
            _stable_field("terminal", "全部已有终态", "bool"),
            _stable_field("read_instances", "已读实例", "list<instance_ref>"),
            _stable_field("unread_instances", "未读实例", "list<instance_ref>"),
            _stable_field("expired_instances", "已过期实例", "list<instance_ref>"),
            _stable_field("failed_instances", "失败实例", "list<instance_ref>"),
            _stable_field("cancelled_instances", "已取消实例", "list<instance_ref>"),
        ),
    ),
    "message_cancel_result": _reference_record(
        type_id="message_cancel_result",
        display_name="消息取消结果",
        fields=(
            _stable_field("batch_id", "批次 ID", "string"),
            _stable_field("cancelled_instances", "已取消实例", "list<instance_ref>"),
            _stable_field("not_cancelled_instances", "未取消实例", "list<instance_ref>"),
            _stable_field("recipients", "收件明细", "list<message_recipient_status>"),
        ),
    ),
}

# Platform/runtime records whose implementations already use stable field IDs.
# Keep these in the same registry so member selection never scrapes arbitrary
# dictionaries returned by a driver.
RECORD_TYPE_CONTRACTS.update({
    "target_info": _reference_record(
        type_id="target_info", display_name="目标状态", fields=(
            _field("target_info", "target_id", "目标 ID", "string"),
            _field("target_info", "name", "目标名称", "string"),
            _field("target_info", "kind", "目标类型", "string"),
            _field("target_info", "online", "在线", "bool"),
            _field("target_info", "ready", "可操作", "bool"),
            _field("target_info", "viewport", "工作区域", "optional<rect>"),
            _field("target_info", "space_version", "空间版本", "string"),
            _field("target_info", "capabilities", "可用能力", "list<string>"),
            _field("target_info", "detail", "状态说明", "string"),
        ),
    ),
    "application_run_ref": _reference_record(
        type_id="application_run_ref", display_name="应用运行引用", fields=(
            _field("application_run_ref", "run_id", "运行 ID", "string"),
            _field("application_run_ref", "platform", "平台", "string"),
            _field("application_run_ref", "application", "应用引用", "application_ref"),
            _field("application_run_ref", "process_id", "进程 ID", "int64"),
            _field("application_run_ref", "target_id", "目标 ID", "string"),
            _field("application_run_ref", "started_at", "启动时间", "datetime"),
        ),
    ),
    "application_exit_result": _reference_record(
        type_id="application_exit_result", display_name="应用退出结果", fields=(
            _field("application_exit_result", "run_id", "运行 ID", "string"),
            _field("application_exit_result", "exit_code", "退出代码", "int64"),
            _field("application_exit_result", "finished_at", "退出时间", "datetime"),
        ),
    ),
    "window_ref": _reference_record(
        type_id="window_ref", display_name="窗口引用", fields=(
            _field("window_ref", "token", "窗口令牌", "string"),
            _field("window_ref", "handle", "窗口句柄", "int64"),
            _field("window_ref", "process_id", "进程 ID", "int64"),
            _field("window_ref", "title", "标题", "string"),
            _field("window_ref", "class_name", "窗口类名", "string"),
        ),
    ),
    "window_status": _reference_record(
        type_id="window_status", display_name="窗口状态", fields=(
            _field("window_status", "title", "标题", "string"),
            _field("window_status", "position", "位置", "point"),
            _field("window_status", "size", "尺寸", "size"),
            _field("window_status", "visible", "可见", "bool"),
            _field("window_status", "minimized", "已最小化", "bool"),
            _field("window_status", "maximized", "已最大化", "bool"),
            _field("window_status", "foreground", "位于前台", "bool"),
            _field("window_status", "process_id", "进程 ID", "int64"),
        ),
    ),
    "control_ref": _reference_record(
        type_id="control_ref", display_name="控件引用", fields=(
            _field("control_ref", "token", "控件令牌", "string"),
            _field("control_ref", "target_id", "目标 ID", "string"),
            _field("control_ref", "name", "名称", "string"),
            _field("control_ref", "automation_id", "自动化 ID", "string"),
            _field("control_ref", "control_type", "控件类型", "string"),
            _field("control_ref", "rect", "区域", "rect"),
        ),
    ),
    "control_status": _reference_record(
        type_id="control_status", display_name="控件状态", fields=(
            _field("control_status", "enabled", "已启用", "optional<bool>"),
            _field("control_status", "visible", "可见", "optional<bool>"),
            _field("control_status", "checked", "已勾选", "optional<bool>"),
            _field("control_status", "selected", "已选中", "optional<bool>"),
            _field("control_status", "editable", "可编辑", "optional<bool>"),
            _field("control_status", "focusable", "可聚焦", "optional<bool>"),
            _field("control_status", "focused", "已聚焦", "optional<bool>"),
            _field("control_status", "current_value", "当前值", "optional<string>"),
            _field("control_status", "rect", "区域", "rect"),
        ),
    ),
    "control_selector": _capture_record(
        type_id="control_selector", display_name="控件选择器", fields=(
            _field("control_selector", "schema_version", "版本", "optional<int64>"),
            _field("control_selector", "selector_id", "选择器身份", "optional<string>"),
            _field("control_selector", "primary_strategy_id", "主定位策略", "optional<string>"),
            _field("control_selector", "captured_space_version", "捕获空间版本", "optional<string>"),
            _field("control_selector", "strategies", "定位策略", "optional<json_value>"),
            _field("control_selector", "provider", "内部适配器", "optional<string>"),
            _field("control_selector", "target_id", "来源目标", "optional<string>"),
            _field("control_selector", "package_name", "应用包名", "optional<string>"),
            _field("control_selector", "resource_id", "资源 ID", "optional<string>"),
            _field("control_selector", "name", "名称", "optional<string>"),
            _field("control_selector", "text", "文字", "optional<string>"),
            _field("control_selector", "content_description", "内容描述", "optional<string>"),
            _field("control_selector", "automation_id", "自动化 ID", "optional<string>"),
            _field("control_selector", "class_name", "类名", "optional<string>"),
            _field("control_selector", "control_type", "控件类型", "optional<string>"),
            _field("control_selector", "index", "同类序号", "optional<int64>"),
            _field("control_selector", "path", "层级路径", "optional<list<int64>>"),
            _field("control_selector", "rect", "捕获区域", "optional<rect>"),
            _field("control_selector", "ancestor_path", "祖先路径", "optional<json_value>"),
        ),
    ),
    "http_pair": _inline_record(
        type_id="http_pair", display_name="HTTP 名称和值", fields=(
            _field("http_pair", "name", "名称", "string", control="text", placeholder="例如：Authorization"),
            _field("http_pair", "value", "值", "string", control="text", placeholder="输入对应的值"),
            _field("http_pair", "sensitive", "敏感内容", "bool", required=False, default=False, control="toggle"),
        ),
    ),
    "http_body": _inline_record(
        type_id="http_body", display_name="HTTP 正文", fields=(
            _field("http_body", "kind", "正文类型", "enum<http_body_kind>", control="select"),
            _field(
                "http_body", "text", "文本", "optional<string>", control="text",
                placeholder="输入请求正文",
                visible_when={"field_id": "http_body.field.kind", "operator": "equals", "value": "text"},
            ),
            _field(
                "http_body", "content_type", "内容类型", "optional<string>",
                default=None, control="text", importance="advanced",
                placeholder="例如：text/plain; charset=utf-8",
                visible_when={"field_id": "http_body.field.kind", "operator": "equals", "value": "text"},
            ),
            _field(
                "http_body", "value", "JSON 数据", "optional<json_value>", control="json",
                placeholder='例如：{"name": "小明"}',
                visible_when={"field_id": "http_body.field.kind", "operator": "equals", "value": "json"},
            ),
        ),
    ),
    "multipart_field": _focused_record(
        type_id="multipart_field", display_name="上传字段", fields=(
            _field("multipart_field", "kind", "字段类型", "enum<multipart_field_kind>", control="select"),
            _field("multipart_field", "name", "名称", "string", control="text", placeholder="例如：attachment"),
            _field(
                "multipart_field", "value", "文本值", "optional<string>", control="text",
                visible_when={"field_id": "multipart_field.field.kind", "operator": "equals", "value": "text"},
            ),
            _field(
                "multipart_field", "file", "文件", "optional<file_ref<read>>", control="file",
                visible_when={"field_id": "multipart_field.field.kind", "operator": "equals", "value": "file"},
                actions=({"id": "choose-file-read", "platforms": ["android_adb", "android_local", "windows"]},),
            ),
            _field(
                "multipart_field", "filename", "文件名", "optional<string>", control="text", importance="advanced",
                placeholder="留空使用原文件名",
                visible_when={"field_id": "multipart_field.field.kind", "operator": "equals", "value": "file"},
            ),
            _field(
                "multipart_field", "content_type", "内容类型", "optional<string>", control="text", importance="advanced",
                placeholder="例如：application/octet-stream",
                visible_when={"field_id": "multipart_field.field.kind", "operator": "equals", "value": "file"},
            ),
        ),
    ),
    "http_response": _reference_record(
        type_id="http_response", display_name="HTTP 响应", fields=(
            _field("http_response", "status", "状态码", "int64"),
            _field("http_response", "headers", "响应头", "list<http_pair>"),
            _field("http_response", "final_url", "最终网址", "url"),
            _field("http_response", "content_type", "内容类型", "string"),
            _field("http_response", "body", "响应正文", "string"),
            _field("http_response", "response_bytes", "响应字节数", "int64"),
        ),
    ),
    "http_download_result": _reference_record(
        type_id="http_download_result", display_name="HTTP 下载结果", fields=(
            _field("http_download_result", "status", "状态码", "int64"),
            _field("http_download_result", "headers", "响应头", "list<http_pair>"),
            _field("http_download_result", "final_url", "最终网址", "url"),
            _field("http_download_result", "content_type", "内容类型", "string"),
            _field("http_download_result", "committed", "已保存", "bool"),
            _field("http_download_result", "file", "文件", "optional<file_ref>"),
            _field("http_download_result", "bytes_written", "写入字节数", "int64"),
            _field("http_download_result", "error_body", "错误正文", "string"),
            _field("http_download_result", "response_bytes", "响应字节数", "int64"),
        ),
    ),
})


def record_type_contract(type_id: str) -> RecordTypeV6 | None:
    """Return the contract for one stable record type, if it is known."""

    normalized = str(type_id or "").strip()
    while normalized.startswith("optional<") and normalized.endswith(">"):
        normalized = normalized[len("optional<"):-1].strip()
    if normalized.startswith("record<") and normalized.endswith(">"):
        normalized = normalized[len("record<"):-1].strip()
    elif normalized.startswith("record."):
        normalized = normalized[len("record."):].strip()
    direct = RECORD_TYPE_CONTRACTS.get(normalized)
    if direct is not None:
        return direct

    def generic_pair(prefix: str) -> tuple[str, str] | None:
        marker = f'{prefix}<'
        if not normalized.startswith(marker) or not normalized.endswith('>'):
            return None
        inner = normalized[len(marker):-1]
        depth = 0
        for index, character in enumerate(inner):
            if character == '<':
                depth += 1
            elif character == '>':
                depth -= 1
            elif character == ',' and depth == 0:
                left, right = inner[:index].strip(), inner[index + 1:].strip()
                return (left, right) if left and right else None
        return None

    pair = generic_pair('zip_pair')
    if pair is not None:
        left, right = pair
        return _focused_record(
            type_id=normalized,
            display_name='组合项',
            fields=(
                _field('zip_pair', 'left', '左侧项', left),
                _field('zip_pair', 'right', '右侧项', right),
            ),
        )
    pair = generic_pair('map_entry')
    if pair is not None:
        key_type, value_type = pair
        return _focused_record(
            type_id=normalized,
            display_name='字典项',
            fields=(
                _field('map_entry', 'key', '键', key_type),
                _field('map_entry', 'value', '值', value_type),
            ),
        )
    return None


def editor_strategy_for_type(value_type: str) -> str | None:
    """Resolve a stable first-render strategy for named records and record lists."""

    normalized = str(value_type or "").strip()
    while normalized.startswith("optional<") and normalized.endswith(">"):
        normalized = normalized[len("optional<"):-1].strip()

    collection = False
    if normalized.startswith("list<") and normalized.endswith(">"):
        collection = True
        normalized = normalized[len("list<"):-1].strip()
    if normalized.startswith("record<") and normalized.endswith(">"):
        normalized = normalized[len("record<"):-1].strip()
    elif normalized.startswith("record."):
        normalized = normalized[len("record."):].strip()

    contract = record_type_contract(normalized)
    if contract is None:
        return None
    if collection and contract.authoring_mode == "constructible":
        return "row_list"
    return contract.editor_strategy


def record_catalog_payload() -> list[dict[str, Any]]:
    """Return a deterministic JSON-ready catalogue for IDE/Player consumers."""

    return [
        record_type_payload(contract)
        for contract in RECORD_TYPE_CONTRACTS.values()
    ]


__all__ = [
    "RECORD_TYPE_CONTRACTS",
    "RecordAuthoringMode",
    "RecordEditorStrategy",
    "RecordFieldV6",
    "RecordTypeV6",
    "editor_strategy_for_type",
    "record_catalog_payload",
    "record_field_payload",
    "record_type_payload",
    "record_type_contract",
]
