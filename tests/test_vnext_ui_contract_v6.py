from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.vnext.extension_schema_v6 import WorkspaceUiContractV1


def valid_contract() -> dict[str, object]:
    return {
        "ui_system_version": 1,
        "workspace_id": "com.example.showcase.workspace",
        "display_name": "展示工作区",
        "topology": "navigator-content-inspector",
        "primary_object": "展示项目",
        "page_actions": [{
            "command_id": "com.example.showcase.create",
            "label": "新建展示项目",
            "level": "primary",
        }],
        "states": ["loading", "error", "empty", "filtered-empty", "selection", "readonly"],
        "has_inspector": True,
        "narrow_behavior": "mutually-exclusive-drawers",
        "keyboard_entry": "从扩展中心打开",
        "permission_summary": "只访问当前扩展命名空间",
        "danger_commands": [],
    }


def test_workspace_ui_contract_accepts_complete_host_rendered_surface() -> None:
    assert WorkspaceUiContractV1.model_validate(valid_contract()).ui_system_version == 1


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"states": ["loading", "error"]}, "工作区缺少必要状态"),
        ({"narrow_behavior": "single-column"}, "带检查器的窄屏工作区必须使用互斥抽屉"),
        ({"page_actions": [
            {"command_id": "com.example.one", "label": "新建", "level": "primary"},
            {"command_id": "com.example.two", "label": "导入", "level": "primary"},
        ]}, "同一工作区只能声明一个主操作"),
    ],
)
def test_workspace_ui_contract_rejects_visual_divergence(update: dict[str, object], message: str) -> None:
    value = valid_contract()
    value.update(update)
    with pytest.raises(ValidationError, match=message):
        WorkspaceUiContractV1.model_validate(value)
