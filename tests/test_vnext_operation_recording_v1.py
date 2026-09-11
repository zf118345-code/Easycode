from __future__ import annotations

from core.vnext.operation_recording_v1 import OperationRecordingServiceV1
from core.vnext.workspace import VNextWorkspaceManager


def test_operation_recording_keeps_draft_then_commits_one_undoable_program_edit(tmp_path) -> None:
    manager = VNextWorkspaceManager()
    opened = manager.open(str(tmp_path / "operation-recording"), initialize=True, project_name="录制测试")
    workspace = opened["workspace"]
    function_id = opened["programs"][0]["function_id"]
    before = manager.load_program(workspace["workspace_id"], workspace["generation"], function_id)
    service = OperationRecordingServiceV1()
    session = service.start(
        workspace["project_path"], function_id=function_id, expected_revision=before["revision"],
        target_id="target.windows", target_type="windows", location={"block": "root"},
    )

    service.append(workspace["project_path"], session["session_id"], {"kind": "click", "point": [120, 80], "occurred_at_ms": session["created_at_ms"] + 100})
    service.append(workspace["project_path"], session["session_id"], {"kind": "text_input", "text": "hello", "occurred_at_ms": session["created_at_ms"] + 250})
    review = service.stop(workspace["project_path"], session["session_id"])
    assert len(before["document"]["function"]["statements"]) == 0
    assert len(review["review_events"]) == 2
    assert review["review_events"][0]["suggestions"]

    committed = service.commit(
        workspace["project_path"], session["session_id"], manager._programs,
        workspace["workspace_id"], workspace["generation"], review["review_events"],
    )
    statements = committed["program"]["document"]["function"]["statements"]
    assert [item["function_id"] for item in statements] == ["official.input.click", "official.input.type_text"]
    assert committed["program"]["can_undo"] is True

    restored = manager.undo_program(workspace["workspace_id"], workspace["generation"], function_id, committed["program"]["revision"])
    assert restored["document"]["function"]["statements"] == []


def test_control_capture_records_direct_selector_action_and_text_is_merged() -> None:
    service = OperationRecordingServiceV1()
    selector = {
        "control_selector.field.schema_version": 2,
        "control_selector.field.provider": "windows_uia",
        "control_selector.field.target_id": "target.windows",
        "control_selector.field.selector_id": "selector.login",
        "control_selector.field.automation_id": "login",
        "control_selector.field.strategies": [{"strategy_id": "strategy.stable_id", "kind": "attributes", "predicates": []}],
    }
    commands = service.commands([
        {"kind": "click", "selector": selector, "enabled": True, "delay_ms": 0},
        {"kind": "text_input", "text": "账号", "enabled": True, "delay_ms": 0},
    ], {"block": "root", "parent_statement_id": None, "clause_id": None, "before_statement_id": None})
    assert commands[0]["function_id"] == "official.control.click_selector"
    assert commands[1]["function_id"] == "official.input.type_text"
