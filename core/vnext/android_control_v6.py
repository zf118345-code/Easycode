"""ADB UIAutomator adapter for the format-6 cross-platform control contract."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable


SELECTOR_PREFIX = "control_selector.field."
REFERENCE_PREFIX = "control_ref.field."
SEMANTIC_TREE_MESSAGE = "当前页面不提供可识别控件，请使用图像、OCR 或坐标"
_BOUNDS = re.compile(r"^\[(-?\d+),(-?\d+)]\[(-?\d+),(-?\d+)]$")
_DEVICE_LOCKS: dict[str, threading.Lock] = {}
_DEVICE_LOCKS_GUARD = threading.Lock()


class AndroidControlError(RuntimeError):
    def __init__(self, error_id: str, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = transient


@dataclass(frozen=True)
class AndroidControlNode:
    package_name: str
    resource_id: str
    text: str
    content_description: str
    class_name: str
    bounds: tuple[int, int, int, int]
    path: tuple[int, ...]
    clickable: bool
    editable: bool
    enabled: bool
    visible: bool | None = None
    checked: bool | None = None
    selected: bool | None = None
    focusable: bool | None = None
    focused: bool | None = None
    scrollable: bool | None = None

    @property
    def area(self) -> int:
        left, top, right, bottom = self.bounds
        return max(0, right - left) * max(0, bottom - top)

    @property
    def display_name(self) -> str:
        return self.text or self.content_description or self.resource_id.rsplit("/", 1)[-1] or self.class_name.rsplit(".", 1)[-1]

    @property
    def semantic(self) -> bool:
        leaf = self.class_name.rsplit(".", 1)[-1].lower()
        if leaf in {"surfaceview", "textureview", "viewrootimpl", "decorview"}:
            return False
        semantic_roles = {
            "button", "imagebutton", "textview", "edittext", "checkbox", "radiobutton",
            "switch", "seekbar", "spinner", "listview", "recyclerview", "scrollview", "webview",
            "autocompletetextview", "multiautocompletetextview",
        }
        return bool(
            self.resource_id or self.text or self.content_description or
            self.clickable or self.editable or leaf in semantic_roles
        )

    def contains(self, x: int, y: int) -> bool:
        left, top, right, bottom = self.bounds
        return left <= x < right and top <= y < bottom


def _bool(value: str | None) -> bool:
    return str(value or "").lower() == "true"


def _optional_bool(value: str | None) -> bool | None:
    return None if value is None else _bool(value)


def _rect(value: str | None) -> tuple[int, int, int, int]:
    match = _BOUNDS.match(str(value or ""))
    if not match:
        return (0, 0, 0, 0)
    left, top, right, bottom = (int(item) for item in match.groups())
    return (left, top, max(left, right), max(top, bottom))


def parse_uiautomator_xml(payload: bytes | str) -> list[AndroidControlNode]:
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if len(raw) > 8 * 1024 * 1024:
        raise AndroidControlError("control.tree_too_large", "控件树超过 8MB 上限")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError) as exc:
        raise AndroidControlError("control.driver_unavailable", f"ADB 控件树无法解析：{exc}", transient=True) from exc
    nodes: list[AndroidControlNode] = []

    def visit(element: ET.Element, path: tuple[int, ...], depth: int) -> None:
        if depth > 64:
            raise AndroidControlError("control.tree_too_large", "控件树层级超过 64 层")
        if element.tag == "node":
            attributes = element.attrib
            nodes.append(AndroidControlNode(
                package_name=str(attributes.get("package") or ""),
                resource_id=str(attributes.get("resource-id") or ""),
                text=str(attributes.get("text") or ""),
                content_description=str(attributes.get("content-desc") or ""),
                class_name=str(attributes.get("class") or ""),
                bounds=_rect(attributes.get("bounds")),
                path=path,
                clickable=_bool(attributes.get("clickable")),
                editable=_bool(attributes.get("editable")) or str(attributes.get("class") or "").endswith(
                    ("EditText", "AutoCompleteTextView", "MultiAutoCompleteTextView")
                ),
                enabled=not attributes.get("enabled") or _bool(attributes.get("enabled")),
                visible=_optional_bool(attributes.get("visible-to-user")),
                checked=_optional_bool(attributes.get("checked")),
                selected=_optional_bool(attributes.get("selected")),
                focusable=_optional_bool(attributes.get("focusable")),
                focused=_optional_bool(attributes.get("focused")),
                scrollable=_optional_bool(attributes.get("scrollable")),
            ))
            if len(nodes) > 10_000:
                raise AndroidControlError("control.tree_too_large", "控件树节点超过 10000 个")
        for index, child in enumerate(list(element)):
            visit(child, (*path, index), depth + 1)

    visit(root, (), 0)
    return nodes


def meaningful_nodes(nodes: list[AndroidControlNode]) -> list[AndroidControlNode]:
    return [node for node in nodes if node.semantic and node.area > 0]


def control_tree_size(nodes: list[AndroidControlNode]) -> tuple[int, int]:
    width = max((node.bounds[2] for node in nodes), default=0)
    height = max((node.bounds[3] for node in nodes), default=0)
    if width <= 0 or height <= 0:
        raise AndroidControlError("control.driver_unavailable", "控件树缺少有效画面尺寸", transient=True)
    return width, height


def scale_point(
    point: tuple[int, int] | list[int],
    source_size: tuple[int, int] | list[int],
    destination_size: tuple[int, int] | list[int],
) -> tuple[int, int]:
    if len(point) != 2 or len(source_size) != 2 or len(destination_size) != 2:
        raise AndroidControlError("control.coordinate_space_invalid", "控件坐标空间格式无效")
    x, y = (int(item) for item in point)
    source_width, source_height = (int(item) for item in source_size)
    destination_width, destination_height = (int(item) for item in destination_size)
    if source_width <= 0 or source_height <= 0 or destination_width <= 0 or destination_height <= 0:
        raise AndroidControlError("control.coordinate_space_invalid", "控件坐标空间尺寸无效")
    if not (0 <= x < source_width and 0 <= y < source_height):
        raise AndroidControlError("control.coordinate_space_invalid", "控件坐标超出来源画面")
    mapped_x = min(destination_width - 1, max(0, round(x * destination_width / source_width)))
    mapped_y = min(destination_height - 1, max(0, round(y * destination_height / source_height)))
    return mapped_x, mapped_y


def _node_record(node: AndroidControlNode) -> dict[str, Any]:
    left, top, right, bottom = node.bounds
    return {
        "package_name": node.package_name,
        "resource_id": node.resource_id,
        "name": node.display_name,
        "text": node.text,
        "content_description": node.content_description,
        "class_name": node.class_name,
        "control_type": node.class_name.rsplit(".", 1)[-1],
        "path": list(node.path),
        "rect": {"kind": "rect", "x": left, "y": top, "width": max(0, right - left), "height": max(0, bottom - top)},
    }


def selector_for_node(
    node: AndroidControlNode,
    target_id: str,
    provider: str,
    *,
    snapshot_nodes: list[AndroidControlNode] | None = None,
) -> dict[str, Any]:
    left, top, right, bottom = node.bounds
    base = {
        f"{SELECTOR_PREFIX}schema_version": 1,
        f"{SELECTOR_PREFIX}provider": provider,
        f"{SELECTOR_PREFIX}target_id": target_id,
        f"{SELECTOR_PREFIX}package_name": node.package_name,
        f"{SELECTOR_PREFIX}resource_id": node.resource_id,
        f"{SELECTOR_PREFIX}name": node.display_name,
        f"{SELECTOR_PREFIX}text": node.text,
        f"{SELECTOR_PREFIX}content_description": node.content_description,
        f"{SELECTOR_PREFIX}class_name": node.class_name,
        f"{SELECTOR_PREFIX}control_type": node.class_name.rsplit(".", 1)[-1],
        f"{SELECTOR_PREFIX}index": 0,
        f"{SELECTOR_PREFIX}path": list(node.path),
        f"{SELECTOR_PREFIX}rect": {
            "kind": "rect", "x": left, "y": top,
            "width": max(0, right - left), "height": max(0, bottom - top),
        },
        f"{SELECTOR_PREFIX}ancestor_path": [],
    }
    from core.vnext.control_selector_v2 import build_selector_v2, record_matches_strategy

    records = [_node_record(candidate) for candidate in meaningful_nodes(snapshot_nodes or [])]
    return build_selector_v2(
        base,
        captured_space_version=f"{target_id}:{provider}",
        test_strategy=(lambda strategy: sum(record_matches_strategy(record, strategy) for record in records)) if records else None,
    )


def node_at_point(nodes: list[AndroidControlNode], x: int, y: int) -> AndroidControlNode:
    semantic = meaningful_nodes(nodes)
    if not semantic:
        raise AndroidControlError("control.semantic_tree_unavailable", SEMANTIC_TREE_MESSAGE)
    candidates = [node for node in semantic if node.contains(x, y)]
    if not candidates:
        raise AndroidControlError("control.not_at_point", "当前位置没有可识别控件；请重新取点，或使用图像、OCR 或坐标")
    return min(candidates, key=lambda node: (node.area, -len(node.path)))


def control_candidates_at(
    nodes: list[AndroidControlNode],
    x: int,
    y: int,
    target_id: str,
    provider: str,
    *,
    source_size: tuple[int, int] | list[int] | None = None,
) -> list[dict[str, Any]]:
    """Return the deepest semantic node followed by its semantic parents.

    ``frame_rect`` is expressed in the frozen capture frame while the selector
    keeps the adapter's native coordinate space.  This separation lets the
    common picker draw a precise frame without weakening runtime relocation.
    """

    tree_size = control_tree_size(nodes)
    frame_size = tuple(int(item) for item in (source_size or tree_size))
    mapped = (int(x), int(y))
    if source_size is not None:
        mapped = scale_point(mapped, frame_size, tree_size)
    deepest = node_at_point(nodes, mapped[0], mapped[1])
    by_path = {node.path: node for node in meaningful_nodes(nodes)}
    lineage: list[AndroidControlNode] = []
    cursor = deepest.path
    while cursor:
        node = by_path.get(cursor)
        if node is not None and (not lineage or node.bounds != lineage[-1].bounds or node.display_name != lineage[-1].display_name):
            lineage.append(node)
        cursor = cursor[:-1]
    if not lineage:
        lineage = [deepest]

    tree_width, tree_height = tree_size
    frame_width, frame_height = frame_size

    def frame_rect(node: AndroidControlNode) -> list[int]:
        left, top, right, bottom = node.bounds
        x0 = round(left * frame_width / tree_width)
        y0 = round(top * frame_height / tree_height)
        x1 = round(right * frame_width / tree_width)
        y1 = round(bottom * frame_height / tree_height)
        return [
            max(0, min(frame_width - 1, x0)),
            max(0, min(frame_height - 1, y0)),
            max(1, min(frame_width, x1) - max(0, x0)),
            max(1, min(frame_height, y1) - max(0, y0)),
        ]

    return [
        {
            "label": node.display_name or node.class_name.rsplit(".", 1)[-1] or "未命名控件",
            "role": node.class_name.rsplit(".", 1)[-1] or "control",
            "frame_rect": frame_rect(node),
            "selector": selector_for_node(node, target_id, provider, snapshot_nodes=nodes),
        }
        for node in lineage
    ]


def _selector_value(selector: dict[str, Any], name: str) -> str:
    return str(selector.get(f"{SELECTOR_PREFIX}{name}") or "")


def resolve_node(
    nodes: list[AndroidControlNode], selector: Any, *, provider: str, target_id: str,
) -> tuple[AndroidControlNode | None, str]:
    if not isinstance(selector, dict):
        raise AndroidControlError("control.selector_invalid", "需要强类型控件选择器")
    declared_provider = _selector_value(selector, "provider")
    if declared_provider and declared_provider != provider:
        raise AndroidControlError("control.selector_provider_mismatch", "控件选择器不属于当前平台适配器")
    declared_target = _selector_value(selector, "target_id")
    if declared_target and declared_target != target_id:
        raise AndroidControlError("control.reference_invalid", "控件选择器不属于当前目标")
    stable = {
        "package_name": _selector_value(selector, "package_name"),
        "resource_id": _selector_value(selector, "resource_id"),
        "text": _selector_value(selector, "text"),
        "content_description": _selector_value(selector, "content_description"),
        "class_name": _selector_value(selector, "class_name"),
    }
    path = selector.get(f"{SELECTOR_PREFIX}path")
    clean_path = tuple(int(item) for item in path) if isinstance(path, list) and all(isinstance(item, int) and item >= 0 for item in path) else ()
    if not any(stable.values()) and not clean_path:
        raise AndroidControlError("control.selector_invalid", "控件选择器缺少可重新定位的稳定字段")
    semantic = meaningful_nodes(nodes)
    if not semantic:
        raise AndroidControlError("control.semantic_tree_unavailable", SEMANTIC_TREE_MESSAGE)

    if int(selector.get(f"{SELECTOR_PREFIX}schema_version") or 0) == 2:
        from core.vnext.control_selector_v2 import ControlSelectorV2Error, record_matches_strategy, resolve_ordered

        records = [(node, _node_record(node)) for node in semantic]
        try:
            return resolve_ordered(
                selector,
                lambda strategy: [node for node, record in records if record_matches_strategy(record, strategy)],
            )
        except ControlSelectorV2Error as exc:
            raise AndroidControlError(exc.error_id, str(exc)) from exc

    def matches(node: AndroidControlNode) -> bool:
        values = {
            "package_name": node.package_name,
            "resource_id": node.resource_id,
            "text": node.text,
            "content_description": node.content_description,
            "class_name": node.class_name,
        }
        return all(not expected or values[key] == expected for key, expected in stable.items())

    candidates = [node for node in semantic if matches(node)]
    if clean_path:
        exact = next((node for node in candidates if node.path == clean_path), None)
        if exact is not None:
            return exact, "legacy.path"
    index = selector.get(f"{SELECTOR_PREFIX}index", 0)
    try:
        position = max(0, int(index or 0))
    except (TypeError, ValueError) as exc:
        raise AndroidControlError("control.selector_invalid", "控件选择器序号无效") from exc
    return (candidates[position], "legacy.attributes") if position < len(candidates) else (None, "")


def find_node(nodes: list[AndroidControlNode], selector: Any, *, provider: str, target_id: str) -> AndroidControlNode | None:
    node, _strategy_id = resolve_node(nodes, selector, provider=provider, target_id=target_id)
    return node


def _adb_executable() -> str:
    direct = shutil.which("adb")
    if direct:
        return direct
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(variable, "")
        candidate = os.path.join(root, "platform-tools", "adb.exe") if root else ""
        if candidate and os.path.isfile(candidate):
            return candidate
    bundled = r"D:\EasyCodeToolchains\android-sdk\platform-tools\adb.exe"
    if os.path.isfile(bundled):
        return bundled
    raise AndroidControlError("control.driver_unavailable", "未找到 ADB，无法读取控件树")


class AdbUiAutomatorAdapter:
    provider = "android_uiautomator"

    def __init__(self, device_serial: str, *, runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None) -> None:
        self.device_serial = str(device_serial or "").strip()
        if not self.device_serial:
            raise AndroidControlError("control.driver_unavailable", "ADB 控件适配器缺少设备序列号")
        self._runner = runner or subprocess.run
        self.display_size = (0, 0)

    def _run(self, arguments: list[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
        command = [_adb_executable(), "-s", self.device_serial, *arguments]
        flags: dict[str, Any] = {}
        if os.name == "nt":
            flags["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = self._runner(command, capture_output=True, timeout=timeout, **flags)
        except (OSError, subprocess.SubprocessError) as exc:
            raise AndroidControlError("control.driver_unavailable", f"ADB 控件查询失败：{exc}", transient=True) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()
            raise AndroidControlError("control.driver_unavailable", detail or "ADB 控件查询失败", transient=True)
        return result

    def snapshot(self) -> list[AndroidControlNode]:
        remote = "/data/local/tmp/easycode-uiautomator.xml"
        with _device_lock(self.device_serial):
            self._run(["shell", "uiautomator", "dump", "--compressed", remote], 5.0)
            try:
                payload = self._run(["exec-out", "cat", remote], 5.0).stdout
            finally:
                try:
                    self._run(["shell", "rm", remote], 2.0)
                except AndroidControlError:
                    pass
        nodes = parse_uiautomator_xml(payload)
        self.display_size = control_tree_size(nodes)
        if not meaningful_nodes(nodes):
            raise AndroidControlError("control.semantic_tree_unavailable", SEMANTIC_TREE_MESSAGE)
        return nodes

    def capture_at(
        self, x: int, y: int, target_id: str,
        source_size: tuple[int, int] | list[int] | None = None,
    ) -> dict[str, Any]:
        nodes = self.snapshot()
        point = (int(x), int(y))
        if source_size is not None:
            point = scale_point(point, source_size, self.display_size)
        return selector_for_node(
            node_at_point(nodes, point[0], point[1]), target_id, self.provider,
            snapshot_nodes=nodes,
        )

    def capture_candidates_at(
        self, x: int, y: int, target_id: str,
        source_size: tuple[int, int] | list[int] | None = None,
    ) -> list[dict[str, Any]]:
        nodes = self.snapshot()
        return control_candidates_at(
            nodes, int(x), int(y), target_id, self.provider,
            source_size=source_size,
        )

    def find(self, selector: Any, target_id: str) -> AndroidControlNode | None:
        node, strategy_id = resolve_node(self.snapshot(), selector, provider=self.provider, target_id=target_id)
        self.last_strategy_id = strategy_id
        return node


def _device_lock(serial: str) -> threading.Lock:
    with _DEVICE_LOCKS_GUARD:
        return _DEVICE_LOCKS.setdefault(serial, threading.Lock())


__all__ = [
    "AdbUiAutomatorAdapter", "AndroidControlError", "AndroidControlNode",
    "SEMANTIC_TREE_MESSAGE", "control_candidates_at", "control_tree_size", "find_node", "meaningful_nodes", "node_at_point",
    "parse_uiautomator_xml", "resolve_node", "scale_point", "selector_for_node",
]
