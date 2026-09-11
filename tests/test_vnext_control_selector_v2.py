from __future__ import annotations

import pytest

from core.vnext.android_control_v6 import AndroidControlError, AndroidControlNode, find_node, selector_for_node
from core.vnext.control_selector_v2 import ControlSelectorV2Error, build_selector_v2, resolve_ordered


def _node(path: tuple[int, ...], *, resource_id: str = "demo:id/login", text: str = "登录") -> AndroidControlNode:
    return AndroidControlNode(
        class_name="android.widget.Button",
        package_name="demo",
        resource_id=resource_id,
        text=text,
        content_description="",
        bounds=(10 + path[-1] * 20, 20, 100 + path[-1] * 20, 60),
        path=path,
        clickable=True,
        editable=False,
        enabled=True,
        scrollable=False,
        checked=False,
        selected=False,
        focusable=True,
        focused=False,
    )


def test_one_capture_builds_and_tests_multiple_strategies() -> None:
    nodes = [_node((0,)), _node((1,), resource_id="demo:id/cancel", text="取消")]
    selector = selector_for_node(nodes[0], "target.android", "android_uiautomator", snapshot_nodes=nodes)

    assert selector["control_selector.field.schema_version"] == 2
    strategies = selector["control_selector.field.strategies"]
    assert len(strategies) >= 3
    assert strategies[0]["strategy_id"] == selector["control_selector.field.primary_strategy_id"]
    assert any(strategy["last_test"]["status"] == "success" for strategy in strategies)


def test_runtime_uses_ordered_unique_fallback_and_returns_evidence() -> None:
    base = selector_for_node(_node((0,)), "target.android", "android_uiautomator")
    ordered = base["control_selector.field.strategies"]
    ordered.insert(0, {
        "strategy_id": "strategy.missing",
        "kind": "attributes",
        "predicates": [{"field": "resource_id", "operator": "equals", "value": "missing"}],
        "relation_path": [],
        "stability_hints": [],
        "last_test": {"status": "not_found", "match_count": 0},
    })
    found, strategy_id = resolve_ordered(base, lambda strategy: [] if strategy["strategy_id"] == "strategy.missing" else ["control"])

    assert found == "control"
    assert strategy_id != "strategy.missing"


def test_ambiguous_strategy_stops_instead_of_falling_through() -> None:
    first = _node((0,))
    second = _node((1,))
    selector = selector_for_node(first, "target.android", "android_uiautomator")
    selector["control_selector.field.strategies"] = [{
        "strategy_id": "strategy.ambiguous",
        "kind": "attributes",
        "predicates": [{"field": "text", "operator": "equals", "value": "登录"}],
        "relation_path": [],
        "stability_hints": [],
        "last_test": {"status": "ambiguous", "match_count": 2},
    }]

    with pytest.raises(AndroidControlError) as captured:
        find_node([first, second], selector, provider="android_uiautomator", target_id="target.android")
    assert captured.value.error_id == "control.selector_ambiguous"


def test_selector_schema_rejects_duplicate_strategy_ids() -> None:
    base = {
        "control_selector.field.schema_version": 1,
        "control_selector.field.provider": "windows_uia",
        "control_selector.field.target_id": "target.windows",
        "control_selector.field.automation_id": "save",
    }
    selector = build_selector_v2(base)
    selector["control_selector.field.strategies"].append(selector["control_selector.field.strategies"][0])
    with pytest.raises(ControlSelectorV2Error):
        resolve_ordered(selector, lambda _strategy: [])
