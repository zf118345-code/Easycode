from __future__ import annotations

import json

import pytest

from core.vnext.control_selector_repair_v2 import ControlSelectorRepairError, ControlSelectorRepairService
from core.vnext.program_repository import ProgramDocumentRepository
from core.vnext.program_types import ProgramDocument, create_program_document


def _selector(value_id: str, selector_id: str, name: str) -> dict:
    return {
        "value_id": value_id,
        "kind": "record",
        "record_type": "control_selector",
        "fields": {
            "control_selector.field.selector_id": {
                "value_id": f"{value_id}_selector_id", "kind": "string", "value": selector_id,
            },
            "control_selector.field.name": {
                "value_id": f"{value_id}_name", "kind": "string", "value": name,
            },
        },
    }


def _document(function_id: str, selector_id: str) -> ProgramDocument:
    payload = create_program_document("测试", function_id=function_id).model_dump(mode="json")
    payload["function"]["statements"] = [{
        "statement_id": f"stmt_{function_id}",
        "kind": "call",
        "function_id": "official.control.find",
        "arguments": {"selector": _selector(f"value_{function_id}", selector_id, "旧按钮")},
        "result_binding": None,
        "step_label": None,
    }]
    return ProgramDocument.model_validate(payload)


def test_repair_previews_then_atomically_updates_all_program_references(tmp_path) -> None:
    repository = ProgramDocumentRepository(tmp_path)
    first = repository.create(_document("func_one", "selector.login"))
    second = repository.create(_document("func_two", "selector.login"))
    service = ControlSelectorRepairService()

    references = service.references(str(tmp_path), "selector.login")
    assert {item["function_id"] for item in references} == {"func_one", "func_two"}
    with pytest.raises(ControlSelectorRepairError) as unconfirmed:
        service.repair(str(tmp_path), "selector.login", _selector("value_new", "selector.login", "新按钮"), expected_revisions={"func_one": first.revision, "func_two": second.revision}, confirmed=False)
    assert unconfirmed.value.error_id == "control.repair_confirmation_required"

    result = service.repair(
        str(tmp_path), "selector.login", _selector("value_new", "selector.login", "新按钮"),
        expected_revisions={"func_one": first.revision, "func_two": second.revision}, confirmed=True,
    )

    assert result["updated_count"] == 2
    for function_id in ("func_one", "func_two"):
        raw = json.loads((tmp_path / "program" / "functions" / f"{function_id}.json").read_text(encoding="utf-8"))
        fields = raw["function"]["statements"][0]["arguments"]["selector"]["fields"]
        assert fields["control_selector.field.name"]["value"] == "新按钮"
        assert fields["control_selector.field.selector_id"]["value"] == "selector.login"
