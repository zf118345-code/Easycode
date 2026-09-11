"""Deterministic multi-strategy ControlSelectorV2 helpers.

The selector remains a plain JSON object so ProgramDocument, Player profiles,
capture hosts, and platform drivers share one serializable contract.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Callable, Iterable


PREFIX = "control_selector.field."
STRATEGIES_FIELD = f"{PREFIX}strategies"


class ControlSelectorV2Error(RuntimeError):
    def __init__(self, error_id: str, message: str, *, strategy_id: str = "") -> None:
        super().__init__(message)
        self.error_id = error_id
        self.strategy_id = strategy_id


def field(selector: dict[str, Any], name: str) -> Any:
    return selector.get(f"{PREFIX}{name}")


def _predicate(name: str, value: Any) -> dict[str, Any]:
    return {"field": name, "operator": "equals", "value": copy.deepcopy(value)}


def _text(selector: dict[str, Any], name: str) -> str:
    return str(field(selector, name) or "").strip()


def _strategy(
    strategy_id: str,
    kind: str,
    predicates: list[dict[str, Any]],
    *,
    relation_path: Any = None,
    stability_hints: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "kind": kind,
        "predicates": predicates,
        "relation_path": copy.deepcopy(relation_path if relation_path is not None else []),
        "stability_hints": list(stability_hints),
        "last_test": {"status": "not_tested", "match_count": None},
    }


def build_selector_v2(
    base: dict[str, Any],
    *,
    selector_id: str | None = None,
    captured_space_version: str = "",
    test_strategy: Callable[[dict[str, Any]], int | None] | None = None,
) -> dict[str, Any]:
    """Upgrade one captured control snapshot into ordered deterministic routes."""
    selector = copy.deepcopy(base)
    provider = _text(selector, "provider")
    target_id = _text(selector, "target_id")
    if not provider or not target_id:
        raise ControlSelectorV2Error("control.selector_invalid", "控件选择器缺少平台或运行目标")

    strategies: list[dict[str, Any]] = []
    resource_id = _text(selector, "resource_id")
    automation_id = _text(selector, "automation_id")
    package_name = _text(selector, "package_name")
    class_name = _text(selector, "class_name")
    control_type = _text(selector, "control_type")
    name = _text(selector, "name") or _text(selector, "text") or _text(selector, "content_description")
    stable_id_name, stable_id = ("resource_id", resource_id) if resource_id else ("automation_id", automation_id)
    if stable_id:
        predicates = [_predicate(stable_id_name, stable_id)]
        if package_name:
            predicates.append(_predicate("package_name", package_name))
        if class_name:
            predicates.append(_predicate("class_name", class_name))
        strategies.append(_strategy("strategy.stable_id", "attributes", predicates, stability_hints=["stable_id"]))

    path = field(selector, "path") or field(selector, "ancestor_path")
    if isinstance(path, list) and path:
        strategies.append(_strategy(
            "strategy.relation_path", "relation_path", [], relation_path=path,
            stability_hints=["hierarchy_sensitive"],
        ))

    if name:
        semantic_field = "name"
        if not _text(selector, "name") and _text(selector, "text"):
            semantic_field = "text"
        elif not _text(selector, "name") and _text(selector, "content_description"):
            semantic_field = "content_description"
        predicates = [_predicate(semantic_field, name)]
        if class_name:
            predicates.append(_predicate("class_name", class_name))
        elif control_type:
            predicates.append(_predicate("control_type", control_type))
        strategies.append(_strategy("strategy.semantic", "attributes", predicates, stability_hints=["text_may_change"]))

    rect = field(selector, "rect")
    if isinstance(rect, dict) and rect.get("kind") == "rect" and int(rect.get("width") or 0) > 0 and int(rect.get("height") or 0) > 0:
        predicates = []
        if stable_id:
            predicates.append(_predicate(stable_id_name, stable_id))
        elif name:
            predicates.append(_predicate("name", name))
        strategies.append(_strategy(
            "strategy.captured_rect", "captured_rect", predicates, relation_path=rect,
            stability_hints=["position_sensitive"],
        ))

    if not strategies:
        raise ControlSelectorV2Error("control.selector_invalid", "控件选择器缺少可重新定位的稳定策略")
    if test_strategy is not None:
        for strategy in strategies:
            count = test_strategy(copy.deepcopy(strategy))
            status = "not_tested" if count is None else "success" if count == 1 else "not_found" if count == 0 else "ambiguous"
            strategy["last_test"] = {"status": status, "match_count": count}

    selector[f"{PREFIX}schema_version"] = 2
    selector[f"{PREFIX}selector_id"] = selector_id or f"selector.{uuid.uuid4().hex}"
    selector[f"{PREFIX}primary_strategy_id"] = strategies[0]["strategy_id"]
    selector[STRATEGIES_FIELD] = strategies
    selector[f"{PREFIX}captured_space_version"] = captured_space_version or target_id
    return selector


def strategies(selector: dict[str, Any]) -> list[dict[str, Any]]:
    if int(field(selector, "schema_version") or 0) != 2:
        return []
    raw = field(selector, "strategies")
    if not isinstance(raw, list) or not raw:
        raise ControlSelectorV2Error("control.selector_invalid", "ControlSelectorV2 缺少定位策略")
    result = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ControlSelectorV2Error("control.selector_invalid", "控件定位策略格式无效")
        strategy_id = str(item.get("strategy_id") or "")
        if not strategy_id or strategy_id in seen:
            raise ControlSelectorV2Error("control.selector_invalid", "控件定位策略 ID 无效或重复")
        if item.get("kind") not in {"attributes", "relation_path", "captured_rect"}:
            raise ControlSelectorV2Error("control.selector_invalid", f"未知控件定位策略：{strategy_id}")
        seen.add(strategy_id)
        result.append(copy.deepcopy(item))
    return result


def resolve_ordered(
    selector: dict[str, Any],
    match: Callable[[dict[str, Any]], list[Any]],
) -> tuple[Any | None, str]:
    """Resolve in frozen order; ambiguity is terminal and never falls through."""
    for strategy in strategies(selector):
        strategy_id = str(strategy["strategy_id"])
        matches = match(strategy)
        if len(matches) == 1:
            return matches[0], strategy_id
        if len(matches) > 1:
            raise ControlSelectorV2Error(
                "control.selector_ambiguous",
                f"控件定位策略 {strategy_id} 匹配到多个控件，已停止以避免误操作",
                strategy_id=strategy_id,
            )
    return None, ""


def record_matches_strategy(record: dict[str, Any], strategy: dict[str, Any]) -> bool:
    for predicate in strategy.get("predicates") or []:
        if not isinstance(predicate, dict) or predicate.get("operator") != "equals":
            return False
        name = str(predicate.get("field") or "")
        expected = predicate.get("value")
        actual = record.get(name)
        if isinstance(expected, str):
            if " ".join(str(actual or "").split()) != " ".join(expected.split()):
                return False
        elif actual != expected:
            return False
    kind = strategy.get("kind")
    relation = strategy.get("relation_path")
    if kind == "relation_path":
        return record.get("path") == relation or record.get("ancestor_path") == relation
    if kind == "captured_rect":
        return record.get("rect") == relation
    return True


__all__ = [
    "ControlSelectorV2Error", "PREFIX", "STRATEGIES_FIELD", "build_selector_v2",
    "field", "record_matches_strategy", "resolve_ordered", "strategies",
]
