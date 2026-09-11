from __future__ import annotations

import pytest

from core.vnext.android_control_v6 import (
    AndroidControlError,
    control_candidates_at,
    find_node,
    node_at_point,
    parse_uiautomator_xml,
    scale_point,
    selector_for_node,
)


UI_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" class="android.widget.FrameLayout" package="demo" bounds="[0,0][1080,1920]">
    <node index="0" text="登录" resource-id="demo:id/login" class="android.widget.Button"
      package="demo" content-desc="登录按钮" clickable="true" enabled="true" visible-to-user="true"
      checked="false" selected="true" focusable="true" focused="false" scrollable="false"
      bounds="[100,200][500,320]" />
    <node index="1" text="" resource-id="demo:id/name" class="android.widget.EditText"
      package="demo" clickable="true" editable="true" enabled="true" bounds="[100,350][800,450]" />
  </node>
</hierarchy>'''

SURFACE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0"><node index="0" text="" resource-id="" class="android.view.SurfaceView"
package="game" clickable="false" enabled="true" bounds="[0,0][1080,1920]" /></hierarchy>'''


def test_uiautomator_capture_and_relocation_use_stable_selector() -> None:
    nodes = parse_uiautomator_xml(UI_XML)
    selected = node_at_point(nodes, 220, 240)
    selector = selector_for_node(selected, "target.emulator", "android_uiautomator", snapshot_nodes=nodes)
    assert selector["control_selector.field.resource_id"] == "demo:id/login"
    assert selector["control_selector.field.name"] == "登录"
    assert find_node(nodes, selector, provider="android_uiautomator", target_id="target.emulator") == selected
    assert selected.visible is True
    assert selected.checked is False
    assert selected.selected is True
    assert selected.focusable is True
    assert selected.focused is False


def test_control_selector_cannot_cross_target_or_provider() -> None:
    nodes = parse_uiautomator_xml(UI_XML)
    selector = selector_for_node(nodes[1], "target.emulator", "android_uiautomator")
    with pytest.raises(AndroidControlError, match="不属于当前目标") as cross_target:
        find_node(nodes, selector, provider="android_uiautomator", target_id="target.phone")
    assert cross_target.value.error_id == "control.reference_invalid"
    with pytest.raises(AndroidControlError, match="平台适配器") as provider:
        find_node(nodes, selector, provider="android_accessibility", target_id="target.emulator")
    assert provider.value.error_id == "control.selector_provider_mismatch"


def test_surface_view_is_not_fabricated_as_a_control() -> None:
    nodes = parse_uiautomator_xml(SURFACE_XML)
    with pytest.raises(AndroidControlError, match="图像、OCR 或坐标") as error:
        node_at_point(nodes, 400, 800)
    assert error.value.error_id == "control.semantic_tree_unavailable"


def test_valid_selector_not_found_remains_normal_empty_result() -> None:
    nodes = parse_uiautomator_xml(UI_XML)
    selector = selector_for_node(nodes[1], "target.emulator", "android_uiautomator")
    selector["control_selector.field.schema_version"] = 1
    selector["control_selector.field.resource_id"] = "demo:id/missing"
    assert find_node(nodes, selector, provider="android_uiautomator", target_id="target.emulator") is None


def test_control_coordinates_scale_between_scrcpy_frame_and_android_tree() -> None:
    assert scale_point((295, 640), (590, 1280), (1080, 2340)) == (540, 1170)
    assert scale_point((540, 1170), (1080, 2340), (590, 1280)) == (295, 640)
    with pytest.raises(AndroidControlError) as error:
        scale_point((590, 0), (590, 1280), (1080, 2340))
    assert error.value.error_id == "control.coordinate_space_invalid"


def test_control_picker_returns_deepest_then_semantic_parents_in_frame_space() -> None:
    nodes = parse_uiautomator_xml(UI_XML)
    candidates = control_candidates_at(
        nodes, 110, 120, "target.emulator", "android_uiautomator",
        source_size=(540, 960),
    )
    assert candidates[0]["label"] == "登录"
    assert candidates[0]["frame_rect"] == [50, 100, 200, 60]
    assert candidates[0]["selector"]["control_selector.field.target_id"] == "target.emulator"
    assert all(item["selector"]["control_selector.field.provider"] == "android_uiautomator" for item in candidates)
