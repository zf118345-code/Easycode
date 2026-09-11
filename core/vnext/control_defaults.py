"""Portable default Control metadata for extension parameters.

This module deliberately contains no parser or editable-source concepts.  It
is used by the native-extension manifest adapter while extensions transition
to the stable format-6 type registry.
"""

from __future__ import annotations

from typing import Any

_ALL_PLATFORMS = ("android_adb", "android_local", "windows")


def parameter_ui_for_type(value_type: str) -> dict[str, Any]:
    """Return a serialisable default Control contract for a declared type.

    Both stable format-6 type IDs and the currently supported extension
    manifest aliases are accepted.  This is a UI projection only; type
    identity remains the manifest's stable ``value_type``.
    """

    declared = str(value_type or "any").strip().lower()
    normalized = declared
    for prefix in ("optional<", "可选<"):
        if normalized.startswith(prefix) and normalized.endswith(">"):
            normalized = normalized[len(prefix):-1].strip()
            break
    if "<" in normalized:
        normalized = normalized.split("<", 1)[0]
    controls = {
        "string": "text", "文本": "text",
        "int64": "number", "整数": "number",
        "float64": "number", "number": "number", "小数": "number",
        "bool": "toggle", "布尔": "toggle",
        "duration": "duration", "持续时间": "duration",
        "time": "time", "datetime": "time", "时间点": "time",
        "color": "color", "颜色": "color",
        "point": "coordinate", "坐标": "coordinate",
        "rect": "region", "矩形": "region",
        "asset_ref": "resource", "图片资源": "resource",
        "file_ref": "file", "文件引用": "file",
        "directory_ref": "directory", "目录引用": "directory",
        "control_selector": "control-selector", "control_ref": "control-selector",
        "selector": "control-selector", "控件选择器": "control-selector",
        "path": "gesture-path", "gesture_path": "gesture-path", "拖拽路径": "gesture-path",
        "list": "list", "列表": "list",
        "map": "key-value", "字典": "key-value",
    }
    control = controls.get(normalized, "expression")
    actions: list[dict[str, Any]] = []
    platforms = list(_ALL_PLATFORMS)
    if control == "coordinate":
        actions.append({"id": "pick-point", "capture_kind": "point", "platforms": platforms})
    elif control == "region":
        actions.append({"id": "pick-region", "capture_kind": "region", "platforms": platforms})
    elif control == "color":
        actions.append({"id": "pick-color", "capture_kind": "color", "platforms": platforms})
    elif control == "resource":
        actions.extend([
            {"id": "choose-resource", "platforms": platforms},
            {"id": "capture-image", "capture_kind": "image", "platforms": platforms},
        ])
    elif control == "control-selector":
        actions.append({"id": "capture-control", "capture_kind": "control", "platforms": list(_ALL_PLATFORMS)})
    elif control == "gesture-path":
        actions.append({"id": "capture-path", "capture_kind": "path", "platforms": platforms})
    elif control == "file":
        # File read and save destinations are intentionally different system
        # picker actions.  Access remains part of the strong reference type;
        # Android never accepts a path-looking string as a substitute.
        access = declared.partition("<")[2].removesuffix(">") if "<" in declared else ""
        if not access or "read" in access:
            actions.append({"id": "choose-file-read", "platforms": list(_ALL_PLATFORMS)})
        if not access or "write" in access:
            actions.append({"id": "choose-file-save", "platforms": list(_ALL_PLATFORMS)})
    elif control == "directory":
        actions.append({"id": "choose-directory", "platforms": list(_ALL_PLATFORMS)})
    return {
        "control": control,
        "actions": actions,
        "player_supported": True,
    }


__all__ = ["parameter_ui_for_type"]
